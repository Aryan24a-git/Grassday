"""app.py - Grassday: local-first outdoor prediction companion."""

from __future__ import annotations

import sys
import time
from datetime import datetime, date, timezone

import pandas as pd
import streamlit as st

import data
import model
import nudge
import pdf_card
import demo as demo_module
import theme

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Grassday",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── Inject Theme ─────────────────────────────────────────────────────────────

st.markdown(theme.get_core_css(), unsafe_allow_html=True)

# ─── Session State ────────────────────────────────────────────────────────────

if "session_start" not in st.session_state:
    st.session_state.session_start = time.time()
if "demo_mode" not in st.session_state:
    st.session_state.demo_mode = "--demo" in sys.argv or st.query_params.get("demo") == "1"

# ─── Sidebar: Settings ───────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Settings")
    loc_name = st.text_input("Location Name", value="Central Park", key="loc_name")
    col_lat, col_lon = st.columns(2)
    with col_lat:
        lat = st.number_input("Latitude", value=40.7128, format="%.4f", key="lat")
    with col_lon:
        lon = st.number_input("Longitude", value=-74.0060, format="%.4f", key="lon")

    activities = st.multiselect(
        "Activities",
        ["Walk", "Sit in park", "Run", "Read outside", "Gardening", "Cycling"],
        default=["Walk", "Sit in park", "Run"],
    )
    ollama_model = st.text_input("Ollama model", value="qwen3")
    
    demo_toggle = st.toggle("🎬 Demo mode", value=st.session_state.demo_mode)
    if demo_toggle != st.session_state.demo_mode:
        st.session_state.demo_mode = demo_toggle
        st.rerun()

    offline_mode = st.toggle("📴 Offline mode", value=False)

    if st.button("🗑️ Reset / Clear Outings"):
        conn = data.get_db_connection()
        with conn:
            conn.execute("DELETE FROM outings")
            conn.execute("DELETE FROM weather_cache")
        get_forecast_cached.clear()
        st.success("Outings and cache cleared!")
        st.rerun()

if st.session_state.demo_mode:
    demo_module.seed_demo_data(lat=lat, lon=lon, location_name=loc_name)

# ─── Core Logic ───────────────────────────────────────────────────────────────

def get_outing_count() -> int:
    try:
        conn = data.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM outings")
        row = cur.fetchone()
        return row["cnt"] if row else 0
    except Exception:
        return 0

@st.cache_data(ttl=300, show_spinner=False)
def get_forecast_cached(lat: float, lon: float, offline: bool) -> tuple:
    if offline:
        conn = data.get_db_connection()
        key = data._make_cache_key("forecast_combined", lat, lon)
        cached = data._get_cache(conn, key)
        if cached:
            return cached[0], True
        return None, True
    try:
        return data.fetch_forecast(lat, lon, days=7)
    except Exception:
        return None, True

@st.cache_data(ttl=300, show_spinner=False)
def build_predictions_cached(
    lat: float, lon: float, offline: bool, acts: tuple, loc: str, model_tag: str, outing_cnt: int
):
    X_train, y_train = model.load_training_data()
    clf = model.GrassdayModel(device="cpu")
    if len(X_train) >= 2:
        clf.fit(X_train, y_train)

    weather_data, is_cached = get_forecast_cached(lat, lon, offline)
    if weather_data is None:
        return None, None, None, None, len(X_train), is_cached

    windows_df = data.hourly_to_2h_windows(weather_data)
    if windows_df.empty:
        return None, None, None, None, len(X_train), is_cached

    ranked = clf.rank_windows(windows_df)
    top_window = ranked.iloc[0].to_dict()
    drivers = clf.explain(top_window)

    season = nudge._get_season(datetime.now().month)
    act = acts[0] if acts else "walk"
    nudge_result = nudge.generate_nudge(
        window=top_window, drivers=drivers, activity=act,
        season=season, location=loc, model_name=model_tag if model_tag else None
    )

    return top_window, ranked, drivers, nudge_result, len(X_train), is_cached

with st.spinner("Finding your best window outside..."):
    outing_cnt = get_outing_count()
    result = build_predictions_cached(
        lat=lat, lon=lon, offline=offline_mode, acts=tuple(activities),
        loc=loc_name, model_tag=ollama_model, outing_cnt=outing_cnt
    )
    
top_window, ranked_df, drivers, nudge_result, train_count, is_cached = result

# ─── 1. Home: Hero & Week View ────────────────────────────────────────────────

if top_window and nudge_result:
    # Build hero time and descriptors
    start_raw = str(top_window.get("window_start", ""))
    try:
        start_dt = pd.to_datetime(start_raw)
        time_str = start_dt.strftime("%I:%M %p").lower().lstrip("0")
    except:
        time_str = start_raw

    temp = top_window.get("temperature_2m", "?")
    desc = f"{temp}°C, "
    if top_window.get("precipitation", 0) > 0.5: desc += "light rain"
    elif top_window.get("cloud_cover", 50) < 30: desc += "clear skies"
    elif top_window.get("pm2_5", 20) < 15: desc += "clean air"
    else: desc += "calm"

    predicted = top_window.get("predicted", 3.0)
    conf = max(0.1, 1.0 - (top_window.get("uncertainty", 1.0) / 4.0))

    st.markdown(theme.render_hero(time_str, desc, conf, predicted, is_cached), unsafe_allow_html=True)
    
    with st.expander("Why this window?", expanded=False):
        st.markdown(theme.render_chips(drivers), unsafe_allow_html=True)
        st.markdown(f"*{nudge_result.get('leave_phone_tip', '')}*")
        st.markdown("**Notice:** " + ", ".join(nudge_result.get("notice", [])))
        st.markdown("**Pack:** " + ", ".join(nudge_result.get("pack", [])))

    # Week View (Top score per day)
    ranked_df["day_name"] = pd.to_datetime(ranked_df["window_start"]).dt.strftime("%a")
    daily_best = ranked_df.groupby("day_name", sort=False).first().reset_index()
    week_days = [{"name": r["day_name"], "score": r["predicted"]} for _, r in daily_best.iterrows()]
    st.markdown(theme.render_week_strip(week_days), unsafe_allow_html=True)

else:
    st.info("No forecast data available. Connect to internet for first run.")

# ─── 2. Log an Outing & Print Card ───────────────────────────────────────────

st.markdown("---")
st.markdown("### Log an Outing")
st.markdown(theme.render_plant_progress(train_count), unsafe_allow_html=True)

with st.form("log_outing", clear_on_submit=True):
    col1, col2 = st.columns(2)
    outing_date = col1.date_input("Date", value=date.today())
    outing_time = col2.time_input("Time", value=datetime.now().time())
    
    act_choice = st.selectbox("Activity", activities if activities else ["Walk"])
    
    # We cannot reliably do liquid blobs on Streamlit inputs via CSS without DOM hacking.
    # Closest robust alternative: a select_slider with leaf/tree emojis.
    rating = st.select_slider(
        "Enjoyment",
        options=[1.0, 2.0, 3.0, 4.0, 5.0],
        value=3.0,
        format_func=lambda x: {1.0: "🥀", 2.0: "🍂", 3.0: "🌿", 4.0: "🌳", 5.0: "🌲"}[x]
    )
    
    notes = st.text_input("Note (optional)")
    submitted = st.form_submit_button("✅ Save", use_container_width=True)

    if submitted:
        data.log_outing(lat, lon, str(outing_date), str(outing_time), act_choice, rating, notes if notes else None)
        get_forecast_cached.clear()
        build_predictions_cached.clear()
        st.rerun()

if top_window and nudge_result:
    st.markdown("---")
    st.markdown("### 🖨️ Print Field Card")
    pdf_bytes = pdf_card.generate_field_card(
        window=top_window, nudge_data=nudge_result,
        location=loc_name, date_str=datetime.now().strftime("%a, %b %d")
    )
    st.download_button("Download A5 Card", pdf_bytes, file_name="grassday.pdf", use_container_width=True)

# ─── 3. Screen-time Budget Footer ─────────────────────────────────────────────

elapsed = int(time.time() - st.session_state.session_start)
st.markdown(theme.render_footer(elapsed), unsafe_allow_html=True)
