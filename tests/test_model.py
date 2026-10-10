"""test_model.py - Unit and synthetic preference tests for model.py."""

import numpy as np
import pandas as pd
import pytest

import model


def test_compute_heuristic_prior():
    """Verify heuristic prior reflects meteorological comfort."""
    perfect = {
        "apparent_temperature": 21.0,
        "precipitation": 0.0,
        "wind_speed_10m": 8.0,
        "uv_index": 2.0,
        "pm2_5": 8.0,
        "daylight_fraction": 1.0,
        "sunset_proximity_hours": 0.5,
    }
    score_perfect = model.compute_heuristic_prior(perfect)
    assert score_perfect >= 4.8

    miserable = {
        "apparent_temperature": 2.0,
        "precipitation": 3.5,
        "wind_speed_10m": 35.0,
        "uv_index": 1.0,
        "pm2_5": 40.0,
        "daylight_fraction": 0.0,
        "sunset_proximity_hours": -5.0,
    }
    score_miserable = model.compute_heuristic_prior(miserable)
    assert score_miserable <= 1.5


def test_cold_start_status():
    """Verify cold start progress reporting."""
    status_0 = model.get_cold_start_status(0)
    assert status_0["is_cold_start"] is True
    assert status_0["needed"] == 10

    status_4 = model.get_cold_start_status(4)
    assert status_4["is_cold_start"] is True
    assert status_4["needed"] == 6

    status_12 = model.get_cold_start_status(12)
    assert status_12["is_cold_start"] is False
    assert status_12["needed"] == 0


def test_synthetic_user_preference_tabpfn():
    """
    Test where the user secretly prefers 18-24°C and low wind (<15 km/h).
    Fit TabPFN on synthetic history, and assert it ranks those windows highest.
    """
    np.random.seed(42)

    data_rows = []
    ratings = []

    # 1. Preferred outings (18-24°C, low wind, dry) -> high rating 4.5 - 5.0
    for _ in range(12):
        temp = float(np.random.uniform(18.5, 23.5))
        wind = float(np.random.uniform(5.0, 12.0))
        hour = int(np.random.choice([10, 12, 14, 16]))
        data_rows.append({
            "temperature_2m": temp,
            "apparent_temperature": temp - 0.5,
            "precipitation": 0.0,
            "wind_speed_10m": wind,
            "cloud_cover": 20.0,
            "relative_humidity_2m": 50.0,
            "uv_index": 3.0,
            "pm2_5": 10.0,
            "hour_of_day": hour,
            "day_of_week": 2,
            "daylight_fraction": 1.0,
            "sunset_proximity_hours": float(hour - 18),
            "month_sin": 0.5,
            "month_cos": -0.86,
        })
        ratings.append(float(np.random.uniform(4.5, 5.0)))

    # 2. Bad outings (freezing/scorching, high wind, rain) -> low rating 1.2 - 2.2
    for _ in range(12):
        temp = float(np.random.choice([6.0, 33.0]))
        wind = float(np.random.uniform(22.0, 36.0))
        rain = float(np.random.choice([1.0, 2.5]))
        hour = int(np.random.choice([8, 11, 15]))
        data_rows.append({
            "temperature_2m": temp,
            "apparent_temperature": temp - 2.0 if temp < 10 else temp + 3.0,
            "precipitation": rain,
            "wind_speed_10m": wind,
            "cloud_cover": 85.0,
            "relative_humidity_2m": 80.0,
            "uv_index": 2.0,
            "pm2_5": 25.0,
            "hour_of_day": hour,
            "day_of_week": 3,
            "daylight_fraction": 0.6,
            "sunset_proximity_hours": float(hour - 18),
            "month_sin": 0.5,
            "month_cos": -0.86,
        })
        ratings.append(float(np.random.uniform(1.2, 2.2)))

    X_train = pd.DataFrame(data_rows)
    y_train = pd.Series(ratings, name="rating")

    # Fit TabPFN model
    clf = model.GrassdayModel(device="cpu")
    clf.fit(X_train, y_train)
    assert clf.is_fitted is True

    # Candidate forecast windows:
    # Ideal: 21°C, 8 km/h wind
    window_ideal = {
        "window_start": "2026-10-12T14:00:00",
        "window_end": "2026-10-12T16:00:00",
        "temperature_2m": 21.0,
        "apparent_temperature": 20.5,
        "precipitation": 0.0,
        "wind_speed_10m": 8.0,
        "cloud_cover": 20.0,
        "relative_humidity_2m": 50.0,
        "uv_index": 3.0,
        "pm2_5": 10.0,
        "hour_of_day": 14,
        "day_of_week": 1,
        "daylight_fraction": 1.0,
        "sunset_proximity_hours": -4.0,
        "month_sin": 0.5,
        "month_cos": -0.86,
    }

    # Bad: 8°C, 30 km/h wind, rain
    window_bad = {
        "window_start": "2026-10-12T08:00:00",
        "window_end": "2026-10-12T10:00:00",
        "temperature_2m": 8.0,
        "apparent_temperature": 5.0,
        "precipitation": 2.0,
        "wind_speed_10m": 30.0,
        "cloud_cover": 80.0,
        "relative_humidity_2m": 75.0,
        "uv_index": 1.0,
        "pm2_5": 15.0,
        "hour_of_day": 8,
        "day_of_week": 1,
        "daylight_fraction": 0.5,
        "sunset_proximity_hours": -10.0,
        "month_sin": 0.5,
        "month_cos": -0.86,
    }

    # Hot: 32°C, 25 km/h wind
    window_hot = {
        "window_start": "2026-10-12T12:00:00",
        "window_end": "2026-10-12T14:00:00",
        "temperature_2m": 32.0,
        "apparent_temperature": 34.0,
        "precipitation": 0.0,
        "wind_speed_10m": 25.0,
        "cloud_cover": 10.0,
        "relative_humidity_2m": 60.0,
        "uv_index": 8.0,
        "pm2_5": 15.0,
        "hour_of_day": 12,
        "day_of_week": 1,
        "daylight_fraction": 1.0,
        "sunset_proximity_hours": -6.0,
        "month_sin": 0.5,
        "month_cos": -0.86,
    }

    candidates_df = pd.DataFrame([window_bad, window_ideal, window_hot])
    ranked = clf.rank_windows(candidates_df)

    # Assert: Ideal window is ranked 1st
    top_window = ranked.iloc[0]
    assert top_window["temperature_2m"] == 21.0
    assert top_window["wind_speed_10m"] == 8.0
    assert top_window["predicted"] >= 4.2
    assert top_window["rank_score"] > ranked.iloc[1]["rank_score"]

    # Explainability: top 3 drivers returned
    explanations = clf.explain(window_ideal)
    assert len(explanations) == 3
    for exp in explanations:
        assert "label" in exp
        assert "delta" in exp
        assert "direction" in exp
