"""nudge.py - Local LLM nudge generator via Ollama with template fallback.

Generates personalized outdoor nudges using a locally-running open-weight LLM.
Falls back to deterministic templates when Ollama is unavailable.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Preferred models in priority order (non-Gemma, open-weight)
PREFERRED_MODELS = [
    "qwen3",
    "llama3.2",
    "llama3.1",
    "llama3",
    "mistral",
    "phi4",
    "phi3",
    "deepseek-r1",
    "qwen2.5",
]

OLLAMA_TIMEOUT = 15.0  # seconds for chat completion

SYSTEM_PROMPT = """\
You are Grassday, a gentle outdoor companion. Your job is to nudge someone \
to step outside and put their phone away.

RULES:
- Use ONLY the weather numbers, location, and season provided. NEVER invent \
weather data or make up conditions.
- Keep the nudge warm, brief (≤2 sentences), and specific to the conditions given.
- The "notice" list should contain 3 real things to look for outside that are \
specific to the season and place described.
- The "pack" list should contain 3 practical items to bring based on the \
weather numbers provided.
- The "leave_phone_tip" should be a single playful line encouraging the user \
to leave their phone behind.
- Reply with ONLY valid JSON, no markdown fences, no extra text.

JSON schema:
{
  "nudge": "string (≤2 sentences)",
  "notice": ["string", "string", "string"],
  "pack": ["string", "string", "string"],
  "leave_phone_tip": "string (1 line)"
}\
"""

# ─── Template fallback data ───────────────────────────────────────────────────

SEASON_NOTICES = {
    "spring": [
        "fresh buds on the trees",
        "birdsong from returning migrants",
        "the smell of rain on warm soil",
    ],
    "summer": [
        "the way light filters through full canopies",
        "butterflies near wildflowers",
        "the hum of cicadas in the afternoon",
    ],
    "autumn": [
        "leaves turning amber and crimson",
        "the crunch underfoot on the path",
        "flocks of birds gathering for migration",
    ],
    "winter": [
        "frost patterns on fallen leaves",
        "the crispness of cold air in your lungs",
        "how quiet the world gets after snowfall",
    ],
}

PHONE_TIPS = [
    "Your phone will survive without you for an hour. Can you survive without it?",
    "Leave the phone on the table — your eyes are a better camera today.",
    "Airplane mode: because the sky doesn't need Wi-Fi.",
    "Your notifications can wait. The sunset won't.",
    "Put the phone down. The grass doesn't have a screen refresh rate.",
    "Let your pocket hold the phone. Let your hands hold the breeze.",
]


def _get_season(month: int) -> str:
    """Return season name for a given month (1-12)."""
    if month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    elif month in (9, 10, 11):
        return "autumn"
    else:
        return "winter"


def _is_ollama_alive(timeout: float = 0.5) -> bool:
    """Quick check whether Ollama daemon is reachable on localhost."""
    try:
        import urllib.request
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _detect_model() -> Optional[str]:
    """Auto-detect first available preferred model from Ollama."""
    if not _is_ollama_alive():
        return None
    try:
        import ollama

        client = ollama.Client(timeout=2.0)
        response = client.list()
        # response.models is a list of model objects with .model attribute
        installed = set()
        for m in response.models:
            name = m.model.lower() if hasattr(m, "model") else str(m).lower()
            installed.add(name)
            # Also add base name without tag (e.g. "qwen3" from "qwen3:latest")
            base = name.split(":")[0]
            installed.add(base)

        for pref in PREFERRED_MODELS:
            if pref in installed:
                return pref

        # If none preferred found, return the first installed model (if any)
        if installed:
            return next(iter(installed))

        return None
    except Exception as err:
        logger.debug("Ollama model detection failed: %s", err)
        return None


def _build_user_prompt(
    window: Dict[str, Any],
    drivers: List[Dict[str, Any]],
    activity: str,
    season: str,
    location: str,
) -> str:
    """Build the user message with all context for the LLM."""
    driver_lines = []
    for d in drivers[:3]:
        direction = "helps" if d.get("direction") == "positive" else "hurts"
        driver_lines.append(f"  - {d.get('label', d.get('feature', '?'))}: {d.get('value', '?')} ({direction} your score)")

    return f"""\
Location: {location}
Season: {season}
Activity: {activity}

Best window: {window.get('window_start', '?')} to {window.get('window_end', '?')}
Temperature: {window.get('temperature_2m', '?')}°C (feels like {window.get('apparent_temperature', '?')}°C)
Precipitation: {window.get('precipitation', 0)}mm
Wind: {window.get('wind_speed_10m', '?')} km/h
Cloud cover: {window.get('cloud_cover', '?')}%
UV index: {window.get('uv_index', '?')}
Air quality (PM2.5): {window.get('pm2_5', '?')} μg/m³
Humidity: {window.get('relative_humidity_2m', '?')}%
Daylight: {round(float(window.get('daylight_fraction', 1.0)) * 100)}%
Predicted enjoyment: {window.get('predicted', '?')}/5

Top drivers for this prediction:
{chr(10).join(driver_lines)}

Generate the JSON nudge now.\
"""


def _parse_nudge_json(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse LLM output as nudge JSON, handling common issues."""
    # Strip markdown fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON object from mixed text
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None

    # Validate required fields
    required = {"nudge", "notice", "pack", "leave_phone_tip"}
    if not required.issubset(parsed.keys()):
        return None
    if not isinstance(parsed["notice"], list) or len(parsed["notice"]) < 3:
        return None
    if not isinstance(parsed["pack"], list) or len(parsed["pack"]) < 3:
        return None

    return parsed


def generate_nudge_ollama(
    window: Dict[str, Any],
    drivers: List[Dict[str, Any]],
    activity: str,
    season: str,
    location: str,
    model_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Generate a nudge via local Ollama LLM. Returns parsed JSON dict or None on failure.
    Retries once on JSON parse failure with a stricter re-prompt.
    """
    try:
        import ollama
    except ImportError:
        logger.warning("ollama package not installed. Falling back to template.")
        return None

    if not _is_ollama_alive():
        return None

    if model_name is None:
        model_name = _detect_model()
    if model_name is None:
        logger.warning("No Ollama model detected. Falling back to template.")
        return None

    user_msg = _build_user_prompt(window, drivers, activity, season, location)

    try:
        client = ollama.Client(timeout=OLLAMA_TIMEOUT)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        # First attempt with format='json'
        resp = client.chat(model=model_name, messages=messages, format="json")
        content = resp.message.content if hasattr(resp, "message") else str(resp)
        parsed = _parse_nudge_json(content)

        if parsed is not None:
            return parsed

        # Retry once with stricter instruction
        logger.info("First LLM response was invalid JSON. Retrying with stricter prompt.")
        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": (
                "Your previous response was not valid JSON. "
                "Reply with ONLY the JSON object, no explanation. Use this exact schema:\n"
                '{"nudge": "...", "notice": ["...", "...", "..."], "pack": ["...", "...", "..."], "leave_phone_tip": "..."}'
            ),
        })

        resp2 = client.chat(model=model_name, messages=messages, format="json")
        content2 = resp2.message.content if hasattr(resp2, "message") else str(resp2)
        parsed2 = _parse_nudge_json(content2)

        if parsed2 is not None:
            return parsed2

        logger.warning("LLM failed to produce valid JSON after retry. Falling back to template.")
        return None

    except Exception as err:
        logger.warning("Ollama call failed (%s). Falling back to template.", err)
        return None


def generate_nudge_template(
    window: Dict[str, Any],
    drivers: List[Dict[str, Any]],
    activity: str,
    season: str,
    location: str,
) -> Dict[str, Any]:
    """
    Deterministic template fallback for nudge generation.
    Always succeeds — no network or LLM required.
    """
    temp = window.get("temperature_2m", 20)
    wind = window.get("wind_speed_10m", 10)
    rain = window.get("precipitation", 0)
    start = window.get("window_start", "soon")
    predicted = window.get("predicted", "?")

    # Build contextual nudge
    if rain > 0.5:
        weather_desc = "Light rain expected, but a little drizzle never hurt anyone"
    elif temp > 28:
        weather_desc = f"It's a warm {temp}°C out there — find some shade and enjoy the heat"
    elif temp < 10:
        weather_desc = f"A brisk {temp}°C — bundle up and feel that crisp air"
    else:
        weather_desc = f"A pleasant {temp}°C with {wind:.0f} km/h winds"

    nudge = f"{weather_desc}. Your best window starts at {start} — step outside and breathe."

    # Pack items based on conditions
    pack = []
    if rain > 0.2:
        pack.append("Light rain jacket")
    if temp < 15:
        pack.append("Warm layer or hoodie")
    if temp > 25:
        pack.append("Water bottle")
    if window.get("uv_index", 0) > 5:
        pack.append("Sunscreen")
    if wind > 20:
        pack.append("Windbreaker")

    # Always-useful defaults to pad to 3
    defaults = ["Comfortable shoes", "Water bottle", "A curious mindset"]
    for d in defaults:
        if d not in pack:
            pack.append(d)
        if len(pack) >= 3:
            break
    pack = pack[:3]

    # Season notices
    notices = SEASON_NOTICES.get(season, SEASON_NOTICES["autumn"])

    # Phone tip (deterministic from hour)
    hour = int(window.get("hour_of_day", 12))
    tip = PHONE_TIPS[hour % len(PHONE_TIPS)]

    return {
        "nudge": nudge,
        "notice": notices,
        "pack": pack,
        "leave_phone_tip": tip,
    }


def generate_nudge(
    window: Dict[str, Any],
    drivers: List[Dict[str, Any]],
    activity: str = "walk",
    season: Optional[str] = None,
    location: str = "my neighborhood",
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a nudge using Ollama LLM with automatic template fallback.
    Always returns a valid nudge dict — never raises.
    """
    if season is None:
        month_sin = float(window.get("month_sin", 0))
        month_cos = float(window.get("month_cos", 1))
        # Recover approximate month from sin/cos encoding
        month_approx = round(math.atan2(month_sin, month_cos) * 12 / (2 * math.pi)) % 12
        month_approx = month_approx if month_approx > 0 else 12
        season = _get_season(month_approx)

    # Try LLM first
    result = generate_nudge_ollama(window, drivers, activity, season, location, model_name=model_name)
    if result is not None:
        result["source"] = "ollama"
        return result

    # Fallback to template
    result = generate_nudge_template(window, drivers, activity, season, location)
    result["source"] = "template"
    return result
