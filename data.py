"""data.py - Local-first data and weather pipeline for Grassday.

Handles Open-Meteo forecast, archive, and air-quality fetching with SQLite caching,
graceful offline fallback, 2-hour feature window aggregation, and outing logging.
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = Path("data")
DEFAULT_DB_PATH = str(DEFAULT_DB_DIR / "grassday.db")

FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_QUALITY_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Initialize SQLite database with required tables and WAL mode enabled."""
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False is required for Streamlit's threaded environment
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")

    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                timezone TEXT DEFAULT 'UTC',
                is_default INTEGER DEFAULT 0
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_cache (
                cache_key TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                date TEXT,
                payload_json TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                outing_time TEXT NOT NULL,
                activity TEXT,
                rating REAL NOT NULL,
                notes TEXT,
                features_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
    return conn


def _make_cache_key(endpoint: str, lat: float, lon: float, date_str: Optional[str] = None) -> str:
    """Generate standardized cache key."""
    rounded_lat = round(lat, 2)
    rounded_lon = round(lon, 2)
    date_part = f"_{date_str}" if date_str else ""
    return f"{endpoint}_{rounded_lat}_{rounded_lon}{date_part}"


def _save_cache(conn: sqlite3.Connection, key: str, endpoint: str, lat: float, lon: float, date_str: Optional[str], data: dict) -> None:
    """Store payload JSON in SQLite cache with ISO UTC timestamp."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO weather_cache (cache_key, endpoint, latitude, longitude, date, payload_json, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (key, endpoint, round(lat, 2), round(lon, 2), date_str, json.dumps(data), now_iso),
        )


def _get_cache(conn: sqlite3.Connection, key: str) -> Optional[Tuple[dict, str]]:
    """Retrieve cached JSON payload and fetched_at timestamp if present."""
    cur = conn.cursor()
    cur.execute("SELECT payload_json, fetched_at FROM weather_cache WHERE cache_key = ?", (key,))
    row = cur.fetchone()
    if row:
        return json.loads(row["payload_json"]), row["fetched_at"]
    return None


def fetch_forecast(lat: float, lon: float, days: int = 7, db_path: str = DEFAULT_DB_PATH) -> Tuple[Dict[str, Any], bool]:
    """
    Fetch forecast and air-quality data for given coordinates.
    Returns: (data_dict, is_cached_fallback).
    """
    conn = get_db_connection(db_path)
    cache_key = _make_cache_key("forecast_combined", lat, lon)

    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,cloud_cover,relative_humidity_2m,uv_index",
        "daily": "sunrise,sunset",
        "forecast_days": days,
        "timezone": "auto",
    }
    aqi_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "pm2_5",
        "forecast_days": days,
        "timezone": "auto",
    }

    try:
        w_resp = requests.get(FORECAST_API_URL, params=weather_params, timeout=10)
        w_resp.raise_for_status()
        w_data = w_resp.json()

        aq_resp = requests.get(AIR_QUALITY_API_URL, params=aqi_params, timeout=10)
        aq_resp.raise_for_status()
        aq_data = aq_resp.json()

        # Combine pm2_5 into hourly
        combined = dict(w_data)
        if "hourly" in combined and "hourly" in aq_data:
            combined["hourly"]["pm2_5"] = aq_data["hourly"].get("pm2_5", [])

        _save_cache(conn, cache_key, "forecast_combined", lat, lon, None, combined)
        return combined, False

    except Exception as err:
        logger.warning("Forecast network request failed (%s). Attempting offline cache fallback.", err)
        cached = _get_cache(conn, cache_key)
        if cached:
            payload, fetched_at = cached
            logger.info("Using cached forecast fetched at %s", fetched_at)
            return payload, True
        raise ConnectionError(f"Network failed and no local cache available for forecast ({lat}, {lon}): {err}") from err


def fetch_history(lat: float, lon: float, date_str: str, db_path: str = DEFAULT_DB_PATH) -> Tuple[Dict[str, Any], bool]:
    """
    Fetch historical weather and air-quality for a specific date (YYYY-MM-DD).
    Returns: (data_dict, is_cached_fallback).
    """
    conn = get_db_connection(db_path)
    cache_key = _make_cache_key("history_combined", lat, lon, date_str)

    history_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,cloud_cover,relative_humidity_2m",
        "daily": "sunrise,sunset",
        "timezone": "auto",
    }
    aq_params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": "pm2_5,uv_index",
        "timezone": "auto",
    }

    try:
        w_resp = requests.get(ARCHIVE_API_URL, params=history_params, timeout=10)
        # If archive returns 400 because date is today/recent, fallback to forecast with past_days
        if w_resp.status_code == 400:
            w_resp = requests.get(
                FORECAST_API_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": date_str,
                    "end_date": date_str,
                    "hourly": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m,cloud_cover,relative_humidity_2m,uv_index",
                    "daily": "sunrise,sunset",
                    "timezone": "auto",
                },
                timeout=10,
            )
        w_resp.raise_for_status()
        w_data = w_resp.json()

        aq_resp = requests.get(AIR_QUALITY_API_URL, params=aq_params, timeout=10)
        aq_resp.raise_for_status()
        aq_data = aq_resp.json()

        combined = dict(w_data)
        if "hourly" in combined:
            if "uv_index" not in combined["hourly"] and "hourly" in aq_data and "uv_index" in aq_data["hourly"]:
                combined["hourly"]["uv_index"] = aq_data["hourly"]["uv_index"]
            if "hourly" in aq_data:
                combined["hourly"]["pm2_5"] = aq_data["hourly"].get("pm2_5", [])

        _save_cache(conn, cache_key, "history_combined", lat, lon, date_str, combined)
        return combined, False

    except Exception as err:
        logger.warning("History network request failed (%s). Attempting offline cache fallback.", err)
        cached = _get_cache(conn, cache_key)
        if cached:
            payload, fetched_at = cached
            logger.info("Using cached history for %s fetched at %s", date_str, fetched_at)
            return payload, True
        raise ConnectionError(f"Network failed and no local cache available for date {date_str}: {err}") from err


def hourly_to_2h_windows(weather_data: dict) -> pd.DataFrame:
    """
    Convert raw Open-Meteo hourly & daily data into 2-hour window feature records.
    Features:
      - temp, apparent temp, precipitation, wind, cloud cover, UV, AQI (PM2.5), humidity
      - hour_of_day, day_of_week
      - daylight_fraction, sunset_proximity_hours, month_sin, month_cos
    """
    hourly = weather_data.get("hourly", {})
    daily = weather_data.get("daily", {})

    times = hourly.get("time", [])
    if not times:
        return pd.DataFrame()

    df_raw = pd.DataFrame({
        "time": pd.to_datetime(times),
        "temperature_2m": hourly.get("temperature_2m", [0.0] * len(times)),
        "apparent_temperature": hourly.get("apparent_temperature", [0.0] * len(times)),
        "precipitation": hourly.get("precipitation", [0.0] * len(times)),
        "wind_speed_10m": hourly.get("wind_speed_10m", [0.0] * len(times)),
        "cloud_cover": hourly.get("cloud_cover", [0.0] * len(times)),
        "relative_humidity_2m": hourly.get("relative_humidity_2m", [50.0] * len(times)),
        "uv_index": hourly.get("uv_index", [0.0] * len(times)),
        "pm2_5": hourly.get("pm2_5", [10.0] * len(times)),
    })

    # Fill NaN or None values with defaults
    df_raw["uv_index"] = df_raw["uv_index"].fillna(0.0)
    df_raw["pm2_5"] = df_raw["pm2_5"].fillna(12.0)
    df_raw["precipitation"] = df_raw["precipitation"].fillna(0.0)

    # Build lookup for sunrise & sunset per date
    daily_times = daily.get("time", [])
    sunrises = daily.get("sunrise", [])
    sunsets = daily.get("sunset", [])
    sun_lookup = {}
    for d_str, sr_str, ss_str in zip(daily_times, sunrises, sunsets):
        try:
            sr_dt = pd.to_datetime(sr_str)
            ss_dt = pd.to_datetime(ss_str)
            sun_lookup[pd.to_datetime(d_str).strftime("%Y-%m-%d")] = (sr_dt, ss_dt)
        except Exception:
            continue

    rows = []
    # Process in 2-hour blocks (step of 2)
    for i in range(0, len(df_raw) - 1, 2):
        chunk = df_raw.iloc[i : i + 2]
        start_time = chunk["time"].iloc[0]
        end_time = chunk["time"].iloc[-1] + pd.Timedelta(hours=1)
        mid_time = start_time + pd.Timedelta(hours=1)

        date_key = start_time.strftime("%Y-%m-%d")
        sr_dt, ss_dt = sun_lookup.get(date_key, (None, None))

        # Daylight fraction calculation
        if sr_dt and ss_dt:
            # Fraction of 2-hour window between sunrise and sunset
            window_start_ts = start_time.timestamp()
            window_end_ts = end_time.timestamp()
            sr_ts = sr_dt.timestamp()
            ss_ts = ss_dt.timestamp()

            overlap_start = max(window_start_ts, sr_ts)
            overlap_end = min(window_end_ts, ss_ts)
            overlap_sec = max(0.0, overlap_end - overlap_start)
            daylight_fraction = round(overlap_sec / 7200.0, 3)

            # Sunset proximity: signed hours from midpoint to sunset (e.g. -1 means 1 hour before sunset)
            sunset_proximity_hours = round((mid_time.timestamp() - ss_ts) / 3600.0, 2)
        else:
            # Fallback if daily sun data is missing: estimate daylight between 06:00 and 18:00
            is_day = 6 <= start_time.hour <= 18
            daylight_fraction = 1.0 if is_day else 0.0
            sunset_proximity_hours = float(start_time.hour - 18)

        month_num = start_time.month
        month_sin = round(math.sin(2 * math.pi * month_num / 12), 4)
        month_cos = round(math.cos(2 * math.pi * month_num / 12), 4)

        row = {
            "window_start": start_time.isoformat(),
            "window_end": end_time.isoformat(),
            "temperature_2m": round(float(chunk["temperature_2m"].mean()), 2),
            "apparent_temperature": round(float(chunk["apparent_temperature"].mean()), 2),
            "precipitation": round(float(chunk["precipitation"].sum()), 2),
            "wind_speed_10m": round(float(chunk["wind_speed_10m"].mean()), 2),
            "cloud_cover": round(float(chunk["cloud_cover"].mean()), 1),
            "relative_humidity_2m": round(float(chunk["relative_humidity_2m"].mean()), 1),
            "uv_index": round(float(chunk["uv_index"].max()), 2),
            "pm2_5": round(float(chunk["pm2_5"].mean()), 2),
            "hour_of_day": int(start_time.hour),
            "day_of_week": int(start_time.dayofweek),
            "daylight_fraction": float(daylight_fraction),
            "sunset_proximity_hours": float(sunset_proximity_hours),
            "month_sin": float(month_sin),
            "month_cos": float(month_cos),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def extract_features_for_time(weather_df: pd.DataFrame, target_dt: datetime) -> Optional[Dict[str, Any]]:
    """Find the 2-hour window covering target_dt and return its features."""
    if weather_df.empty:
        return None

    target_ts = pd.to_datetime(target_dt)
    w_starts = pd.to_datetime(weather_df["window_start"])
    w_ends = pd.to_datetime(weather_df["window_end"])

    mask = (w_starts <= target_ts) & (target_ts < w_ends)
    match = weather_df[mask]
    if not match.empty:
        return match.iloc[0].to_dict()

    # If exact window not matched, choose nearest window midpoint
    midpoints = w_starts + pd.Timedelta(hours=1)
    diffs = (midpoints - target_ts).abs()
    nearest_idx = diffs.idxmin()
    return weather_df.loc[nearest_idx].to_dict()


def log_outing(
    lat: float,
    lon: float,
    date_str: str,
    time_str: str,
    activity: str,
    rating: float,
    notes: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """
    Log a past outing to SQLite, automatically attaching historical weather features.
    date_str format: YYYY-MM-DD
    time_str format: HH:MM or HH:MM:SS
    rating: 1.0 to 5.0
    """
    if not (1.0 <= rating <= 5.0):
        raise ValueError(f"Rating must be between 1.0 and 5.0, got {rating}")

    target_dt_str = f"{date_str}T{time_str}"
    target_dt = pd.to_datetime(target_dt_str)

    # Fetch history for that date
    history_json, is_cached = fetch_history(lat, lon, date_str, db_path=db_path)
    windows_df = hourly_to_2h_windows(history_json)
    features = extract_features_for_time(windows_df, target_dt)

    if features is None:
        features = {}

    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    features_json = json.dumps(features)

    with conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO outings (latitude, longitude, outing_time, activity, rating, notes, features_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (lat, lon, target_dt.isoformat(), activity, rating, notes, features_json, now_iso),
        )
        outing_id = cur.lastrowid

    return {
        "id": outing_id,
        "latitude": lat,
        "longitude": lon,
        "outing_time": target_dt.isoformat(),
        "activity": activity,
        "rating": rating,
        "notes": notes,
        "is_cached_weather": is_cached,
        "features": features,
    }
