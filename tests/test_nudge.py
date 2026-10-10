"""test_nudge.py - Tests for nudge.py template fallback and JSON parsing."""

import json
import pytest
from unittest.mock import patch, MagicMock

import nudge


@pytest.fixture
def sample_window():
    """Sample top-ranked window for nudge generation."""
    return {
        "window_start": "2026-10-12T14:00",
        "window_end": "2026-10-12T16:00",
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
        "predicted": 4.5,
    }


@pytest.fixture
def sample_drivers():
    """Sample explanation drivers."""
    return [
        {"feature": "temperature_2m", "label": "Temperature", "value": 21.0, "delta": 0.8, "direction": "positive"},
        {"feature": "wind_speed_10m", "label": "Wind speed", "value": 8.0, "delta": 0.5, "direction": "positive"},
        {"feature": "precipitation", "label": "Precipitation", "value": 0.0, "delta": 0.3, "direction": "positive"},
    ]


def test_template_fallback_always_succeeds(sample_window, sample_drivers):
    """Template fallback must always return a valid nudge dict, never raise."""
    result = nudge.generate_nudge_template(
        window=sample_window,
        drivers=sample_drivers,
        activity="walk",
        season="autumn",
        location="Central Park",
    )

    assert "nudge" in result
    assert isinstance(result["nudge"], str) and len(result["nudge"]) > 10
    assert isinstance(result["notice"], list) and len(result["notice"]) == 3
    assert isinstance(result["pack"], list) and len(result["pack"]) == 3
    assert isinstance(result["leave_phone_tip"], str) and len(result["leave_phone_tip"]) > 5


def test_template_rain_context():
    """Template adjusts nudge and pack for rainy conditions."""
    rainy_window = {
        "window_start": "2026-10-12T10:00",
        "window_end": "2026-10-12T12:00",
        "temperature_2m": 14.0,
        "apparent_temperature": 12.0,
        "precipitation": 2.5,
        "wind_speed_10m": 15.0,
        "cloud_cover": 90.0,
        "relative_humidity_2m": 85.0,
        "uv_index": 1.0,
        "pm2_5": 8.0,
        "hour_of_day": 10,
        "day_of_week": 3,
        "daylight_fraction": 1.0,
        "sunset_proximity_hours": -8.0,
        "month_sin": 0.5,
        "month_cos": -0.86,
        "predicted": 2.8,
    }
    result = nudge.generate_nudge_template(rainy_window, [], "walk", "autumn", "Home")
    assert "rain" in result["nudge"].lower() or "drizzle" in result["nudge"].lower()
    assert any("rain" in item.lower() or "jacket" in item.lower() for item in result["pack"])


def test_parse_nudge_json_valid():
    """Valid JSON should parse correctly."""
    valid = json.dumps({
        "nudge": "Go outside now!",
        "notice": ["birds", "leaves", "clouds"],
        "pack": ["water", "hat", "shoes"],
        "leave_phone_tip": "Leave it behind.",
    })
    result = nudge._parse_nudge_json(valid)
    assert result is not None
    assert result["nudge"] == "Go outside now!"


def test_parse_nudge_json_with_markdown_fences():
    """JSON wrapped in markdown code fences should still parse."""
    fenced = '```json\n{"nudge": "Go!", "notice": ["a", "b", "c"], "pack": ["x", "y", "z"], "leave_phone_tip": "Bye phone."}\n```'
    result = nudge._parse_nudge_json(fenced)
    assert result is not None
    assert result["nudge"] == "Go!"


def test_parse_nudge_json_invalid():
    """Invalid JSON should return None."""
    assert nudge._parse_nudge_json("not json at all") is None
    assert nudge._parse_nudge_json('{"nudge": "missing fields"}') is None


def test_generate_nudge_falls_back_when_ollama_unavailable(sample_window, sample_drivers):
    """When Ollama is unreachable, generate_nudge must return template output."""
    with patch("nudge._detect_model", return_value=None):
        result = nudge.generate_nudge(
            window=sample_window,
            drivers=sample_drivers,
            activity="walk",
            season="autumn",
            location="Neighborhood",
        )
    assert result["source"] == "template"
    assert "nudge" in result
    assert len(result["notice"]) == 3


def test_generate_nudge_ollama_success(sample_window, sample_drivers):
    """When Ollama returns valid JSON, it should be used directly."""
    fake_response = MagicMock()
    fake_response.message.content = json.dumps({
        "nudge": "Perfect afternoon for a stroll at 21°C.",
        "notice": ["golden leaves", "squirrels gathering acorns", "late afternoon light"],
        "pack": ["light jacket", "water bottle", "comfortable shoes"],
        "leave_phone_tip": "The trees don't post selfies, and they're doing just fine.",
    })

    mock_client = MagicMock()
    mock_client.chat.return_value = fake_response

    with patch("nudge._is_ollama_alive", return_value=True):
        with patch("nudge._detect_model", return_value="qwen3"):
            with patch("ollama.Client", return_value=mock_client):
                result = nudge.generate_nudge_ollama(
                    window=sample_window,
                    drivers=sample_drivers,
                    activity="walk",
                    season="autumn",
                    location="Central Park",
                    model_name="qwen3",
                )

    assert result is not None
    assert "nudge" in result
    assert "Perfect afternoon" in result["nudge"]


def test_season_detection():
    """Verify _get_season returns correct season for each month."""
    assert nudge._get_season(1) == "winter"
    assert nudge._get_season(4) == "spring"
    assert nudge._get_season(7) == "summer"
    assert nudge._get_season(10) == "autumn"
