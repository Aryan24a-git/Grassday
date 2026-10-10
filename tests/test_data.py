"""test_data.py - Unit tests for data.py with mocked HTTP responses."""

import json
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import pandas as pd

import data


@pytest.fixture
def temp_db(tmp_path):
    """Provide a fresh isolated SQLite database path."""
    db_file = tmp_path / "test_grassday.db"
    return str(db_file)


@pytest.fixture
def sample_weather_payload():
    """Sample Open-Meteo forecast payload with 24 hours of data."""
    hours = [f"2026-10-11T{h:02d}:00" for h in range(24)]
    return {
        "latitude": 40.71,
        "longitude": -74.01,
        "hourly": {
            "time": hours,
            "temperature_2m": [15.0 + i * 0.5 for i in range(24)],
            "apparent_temperature": [14.0 + i * 0.5 for i in range(24)],
            "precipitation": [0.0 if i != 12 else 1.5 for i in range(24)],
            "wind_speed_10m": [10.0] * 24,
            "cloud_cover": [20.0] * 24,
            "relative_humidity_2m": [60.0] * 24,
            "uv_index": [0.0] * 6 + [3.0] * 6 + [6.0] * 6 + [0.0] * 6,
        },
        "daily": {
            "time": ["2026-10-11"],
            "sunrise": ["2026-10-11T06:30"],
            "sunset": ["2026-10-11T18:15"],
        },
    }


@pytest.fixture
def sample_aqi_payload():
    """Sample Open-Meteo air-quality payload."""
    hours = [f"2026-10-11T{h:02d}:00" for h in range(24)]
    return {
        "hourly": {
            "time": hours,
            "pm2_5": [12.5] * 24,
            "uv_index": [1.0] * 24,
        }
    }


def test_fetch_forecast_caching_and_offline_fallback(temp_db, sample_weather_payload, sample_aqi_payload):
    """Verify live fetch caches to SQLite, and offline fallback activates when network fails."""
    # 1. Mock successful live request
    mock_w_resp = MagicMock()
    mock_w_resp.status_code = 200
    mock_w_resp.json.return_value = sample_weather_payload
    mock_w_resp.raise_for_status = MagicMock()

    mock_aq_resp = MagicMock()
    mock_aq_resp.status_code = 200
    mock_aq_resp.json.return_value = sample_aqi_payload
    mock_aq_resp.raise_for_status = MagicMock()

    with patch("requests.get", side_effect=[mock_w_resp, mock_aq_resp]):
        res, is_cached = data.fetch_forecast(40.71, -74.01, days=1, db_path=temp_db)
        assert is_cached is False
        assert "pm2_5" in res["hourly"]
        assert len(res["hourly"]["time"]) == 24

    # 2. Simulate complete network blackout
    with patch("requests.get", side_effect=Exception("Network unreachable")):
        cached_res, is_cached_offline = data.fetch_forecast(40.71, -74.01, days=1, db_path=temp_db)
        assert is_cached_offline is True
        assert cached_res["hourly"]["temperature_2m"][0] == 15.0


def test_hourly_to_2h_windows(sample_weather_payload, sample_aqi_payload):
    """Verify 24 hours of hourly data transforms into 12 2-hour window records with required features."""
    combined = dict(sample_weather_payload)
    combined["hourly"]["pm2_5"] = sample_aqi_payload["hourly"]["pm2_5"]

    windows_df = data.hourly_to_2h_windows(combined)

    assert len(windows_df) == 12  # 24 hours / 2 = 12 windows
    expected_cols = {
        "window_start",
        "window_end",
        "temperature_2m",
        "apparent_temperature",
        "precipitation",
        "wind_speed_10m",
        "cloud_cover",
        "relative_humidity_2m",
        "uv_index",
        "pm2_5",
        "hour_of_day",
        "day_of_week",
        "daylight_fraction",
        "sunset_proximity_hours",
        "month_sin",
        "month_cos",
    }
    assert expected_cols.issubset(set(windows_df.columns))

    # Daylight check: midnight (00:00) should have 0 daylight, midday should be high
    midnight_window = windows_df.iloc[0]
    assert midnight_window["hour_of_day"] == 0
    assert midnight_window["daylight_fraction"] == 0.0

    noon_window = windows_df[windows_df["hour_of_day"] == 12].iloc[0]
    assert noon_window["daylight_fraction"] == 1.0
    assert noon_window["precipitation"] == 1.5  # 12:00 precipitation aggregated correctly


def test_log_outing_persists_with_weather(temp_db, sample_weather_payload, sample_aqi_payload):
    """Verify logging an outing fetches historical weather, attaches features, and saves to SQLite."""
    mock_w_resp = MagicMock()
    mock_w_resp.status_code = 200
    mock_w_resp.json.return_value = sample_weather_payload
    mock_w_resp.raise_for_status = MagicMock()

    mock_aq_resp = MagicMock()
    mock_aq_resp.status_code = 200
    mock_aq_resp.json.return_value = sample_aqi_payload
    mock_aq_resp.raise_for_status = MagicMock()

    with patch("requests.get", side_effect=[mock_w_resp, mock_aq_resp]):
        result = data.log_outing(
            lat=40.71,
            lon=-74.01,
            date_str="2026-10-11",
            time_str="14:30",
            activity="Park walk",
            rating=4.5,
            notes="Crisp autumn air",
            db_path=temp_db,
        )

    assert result["id"] is not None
    assert result["rating"] == 4.5
    assert result["activity"] == "Park walk"
    assert "temperature_2m" in result["features"]
    assert result["features"]["hour_of_day"] == 14  # Window 14:00 - 16:00

    # Verify database record
    conn = data.get_db_connection(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT * FROM outings WHERE id = ?", (result["id"],))
    row = cur.fetchone()
    assert row is not None
    assert row["rating"] == 4.5
    assert row["notes"] == "Crisp autumn air"


def test_rating_validation(temp_db):
    """Verify invalid ratings (outside 1-5) raise ValueError."""
    with pytest.raises(ValueError):
        data.log_outing(40.71, -74.01, "2026-10-11", "12:00", "Walk", rating=0.5, db_path=temp_db)
    with pytest.raises(ValueError):
        data.log_outing(40.71, -74.01, "2026-10-11", "12:00", "Walk", rating=5.5, db_path=temp_db)
