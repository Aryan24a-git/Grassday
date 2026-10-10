"""__main__.py - CLI entry point for Grassday.

Usage:
    python -m grassday today          Print today's best window nudge
    python -m grassday today --demo   Use demo data
"""

from __future__ import annotations

import sys
from datetime import datetime

import data
import model
import nudge

# Force UTF-8 encoding for stdout to handle emojis in Windows terminal
if sys.stdout.encoding.lower() != 'utf-8' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')



def cli_today(demo: bool = False) -> None:
    """Print today's best outdoor window to the terminal."""
    lat, lon = 40.7128, -74.0060
    location = "Central Park"

    # Seed demo data if requested
    if demo:
        import demo as demo_module
        demo_module.seed_demo_data(lat=lat, lon=lon, location_name=location)
        print("🎬 Demo mode: loaded synthetic outings.\n")

    # Load model
    X_train, y_train = model.load_training_data()
    clf = model.GrassdayModel(device="cpu")
    if len(X_train) >= 2:
        clf.fit(X_train, y_train)

    cold = model.get_cold_start_status(clf.train_count)

    # Fetch forecast
    try:
        if demo:
            # Force offline mode for demo to skip network timeout
            conn = data.get_db_connection()
            cache_key = data._make_cache_key("forecast_combined", lat, lon)
            cached = data._get_cache(conn, cache_key)
            if cached:
                weather_data, is_cached = cached[0], True
            else:
                weather_data, is_cached = data.fetch_forecast(lat, lon, days=2)
        else:
            weather_data, is_cached = data.fetch_forecast(lat, lon, days=2)
    except ConnectionError as e:
        print(f"❌ {e}")
        print("   Connect to the internet for the first weather fetch, or run with --demo.")
        sys.exit(1)

    if is_cached:
        print("📴 Using cached weather data (offline)\n")

    # Build windows and rank
    windows_df = data.hourly_to_2h_windows(weather_data)
    if windows_df.empty:
        print("❌ No forecast windows available.")
        sys.exit(1)

    ranked = clf.rank_windows(windows_df)
    top = ranked.iloc[0].to_dict()
    drivers = clf.explain(top)

    month_num = datetime.now().month
    season = nudge._get_season(month_num)
    nudge_result = nudge.generate_nudge(
        window=top, drivers=drivers, activity="walk",
        season=season, location=location,
    )

    # ── Print output ──
    start = str(top.get("window_start", "?"))
    time_part = start.split("T")[-1][:5] if "T" in start else start
    temp = top.get("temperature_2m", "?")
    predicted = top.get("predicted", "?")
    q10 = top.get("q10", "?")
    q90 = top.get("q90", "?")

    print("🌿 ─── GRASSDAY ───")
    print()
    print(f"   Go at {time_part} — {temp}°C")
    print(f"   ⭐ Predicted enjoyment: {predicted}/5  (range: {q10}–{q90})")
    print()
    print(f'   💬 "{nudge_result.get("nudge", "")}"')
    print()

    if cold["is_cold_start"]:
        print(f"   🌱 {cold['message']}")
        print()

    print("   👀 Look for:")
    for item in nudge_result.get("notice", []):
        print(f"      • {item}")
    print()
    print("   🎒 Pack:")
    for item in nudge_result.get("pack", []):
        print(f"      • {item}")
    print()
    print(f"   📵 {nudge_result.get('leave_phone_tip', '')}")
    print()

    # Explanation
    print("   🔍 Why this window?")
    for d in drivers:
        arrow = "↑" if d["direction"] == "positive" else "↓"
        print(f"      {arrow} {d['label']}: {d['value']} (Δ{d['delta']:+.2f})")
    print()
    print("🌿 ─── Now close this terminal and go outside. ───")


def main() -> None:
    """Parse CLI arguments and dispatch."""
    args = sys.argv[1:]
    demo = "--demo" in args

    if not args or args[0] == "today":
        cli_today(demo=demo)
    else:
        print(f"Unknown command: {args[0]}")
        print("Usage: python -m grassday today [--demo]")
        sys.exit(1)


if __name__ == "__main__":
    main()
