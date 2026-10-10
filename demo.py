"""demo.py - Seed fake data for --demo mode so judges can run instantly."""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import data


def seed_demo_data(
    lat: float = 40.71,
    lon: float = -74.01,
    location_name: str = "Central Park",
    db_path: str = data.DEFAULT_DB_PATH,
    num_outings: int = 25,
) -> List[Dict[str, Any]]:
    """
    Pre-populate the database with realistic synthetic outing logs.
    Uses a deterministic seed for reproducibility.
    """
    random.seed(2026)
    conn = data.get_db_connection(db_path)

    # Check if demo data already loaded
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM outings")
    if cur.fetchone()["cnt"] >= num_outings:
        return []

    # Add default location
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO locations (name, latitude, longitude, timezone, is_default) VALUES (?, ?, ?, ?, 1)",
            (location_name, lat, lon, "America/New_York"),
        )

    activities = ["Walk", "Sit in park", "Run", "Read outside", "Gardening", "Cycling"]
    base_date = datetime(2026, 9, 15, tzinfo=timezone.utc)
    outings = []

    for i in range(num_outings):
        day_offset = random.randint(0, 25)
        hour = random.choice([7, 8, 9, 10, 11, 14, 15, 16, 17, 18])
        outing_dt = base_date + timedelta(days=day_offset, hours=hour)
        activity = random.choice(activities)

        # Generate weather features
        temp = round(random.uniform(8.0, 30.0), 1)
        apparent_temp = round(temp + random.uniform(-3.0, 2.0), 1)
        wind = round(random.uniform(3.0, 35.0), 1)
        rain = round(random.choice([0.0, 0.0, 0.0, 0.0, 0.5, 1.2, 3.0]), 1)
        cloud = round(random.uniform(5.0, 95.0), 1)
        humidity = round(random.uniform(30.0, 90.0), 1)
        uv = round(random.uniform(0.0, 10.0), 1)
        pm25 = round(random.uniform(5.0, 45.0), 1)
        daylight = round(random.uniform(0.3, 1.0), 2)
        sunset_prox = round(random.uniform(-8.0, 2.0), 1)
        month_sin = round(math.sin(2 * math.pi * outing_dt.month / 12), 4)
        month_cos = round(math.cos(2 * math.pi * outing_dt.month / 12), 4)

        # Rating: secret preference for 18-24°C, low wind, no rain
        if 18.0 <= temp <= 24.0 and wind < 15.0 and rain == 0.0:
            rating = round(random.uniform(4.2, 5.0), 1)
        elif rain > 1.0 or wind > 28.0 or temp < 10.0 or temp > 28.0:
            rating = round(random.uniform(1.0, 2.5), 1)
        else:
            rating = round(random.uniform(2.8, 4.0), 1)

        features = {
            "temperature_2m": temp,
            "apparent_temperature": apparent_temp,
            "precipitation": rain,
            "wind_speed_10m": wind,
            "cloud_cover": cloud,
            "relative_humidity_2m": humidity,
            "uv_index": uv,
            "pm2_5": pm25,
            "hour_of_day": hour,
            "day_of_week": outing_dt.weekday(),
            "daylight_fraction": daylight,
            "sunset_proximity_hours": sunset_prox,
            "month_sin": month_sin,
            "month_cos": month_cos,
        }

        notes_pool = [
            "Beautiful light through the trees",
            "Could hear birds everywhere",
            "Too windy, cut it short",
            "Perfect temperature for a long walk",
            "Rain started halfway through",
            "Watched the sunset from the bench",
            "Air felt really clean today",
            "",
        ]

        with conn:
            conn.execute(
                """INSERT INTO outings (latitude, longitude, outing_time, activity, rating, notes, features_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lat, lon,
                    outing_dt.isoformat(),
                    activity,
                    rating,
                    random.choice(notes_pool),
                    json.dumps(features),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        outings.append({"date": outing_dt.isoformat(), "activity": activity, "rating": rating})

    # Bundle cached forecast for offline demo
    import os
    forecast_path = os.path.join(os.path.dirname(__file__), "demo_forecast.json")
    if os.path.exists(forecast_path):
        with open(forecast_path, "r", encoding="utf-8") as f:
            demo_forecast = json.load(f)
        
        # We need to structure it like combined API data if needed, but data.py expects just the json
        # Let's insert it into the cache directly under the key for the demo lat/lon
        cache_key = data._make_cache_key("forecast_combined", lat, lon)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO weather_cache (cache_key, timestamp, data_json) VALUES (?, ?, ?)",
                (cache_key, datetime.now(timezone.utc).isoformat(), json.dumps(demo_forecast)),
            )

    return outings
