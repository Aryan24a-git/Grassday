"""api.py - FastAPI backend for Grassday.

Serves ML predictions, outdoor window rankings, LLM nudges, outing logs,
and printable field cards to the modern React frontend.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import data
import model
import nudge
import pdf_card
import demo as demo_module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("grassday_api")

app = FastAPI(title="Grassday API", version="1.0.0")

# Enable CORS for React frontend (Vite default is 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory cache for fast UI updates ──────────────────────────────────────
_prediction_cache: Dict[str, Any] = {}
_cached_model_key: str = ""
_cached_clf: Optional[model.GrassdayModel] = None


def get_trained_model() -> tuple[model.GrassdayModel, int]:
    global _cached_model_key, _cached_clf
    X_train, y_train = model.load_training_data()
    train_count = len(X_train)
    key = f"{train_count}_{y_train.sum() if train_count else 0}"
    if _cached_clf is None or _cached_model_key != key:
        clf = model.GrassdayModel(device="cpu")
        if train_count >= 2:
            clf.fit(X_train, y_train)
        _cached_clf = clf
        _cached_model_key = key
    return _cached_clf, train_count


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/prediction")
def get_prediction(
    lat: float = Query(40.7128, description="Latitude"),
    lon: float = Query(-74.0060, description="Longitude"),
    location_name: str = Query("Central Park", description="Location name"),
    activity: str = Query("Walk", description="Preferred outdoor activity"),
    offline: bool = Query(False, description="Force offline cache"),
    ollama_model: str = Query("qwen3", description="Ollama model tag"),
    demo: bool = Query(False, description="Enable demo mode with seeded data"),
):
    try:
        conn = data.get_db_connection()
        if demo:
            demo_module.seed_demo_data(lat=lat, lon=lon, location_name=location_name)

        clf, train_count = get_trained_model()

        # Fetch weather
        weather_data = None
        is_cached = False
        cache_key = data._make_cache_key("forecast_combined", lat, lon)

        if offline:
            cached = data._get_cache(conn, cache_key)
            if cached:
                weather_data, _ = cached
                is_cached = True
            else:
                raise HTTPException(status_code=503, detail="Offline mode requested but no cache exists for this location.")
        else:
            try:
                weather_data, is_cached = data.fetch_forecast(lat, lon, days=7)
            except Exception as e:
                # Fall back to cache
                cached = data._get_cache(conn, cache_key)
                if cached:
                    weather_data, _ = cached
                    is_cached = True
                else:
                    raise HTTPException(status_code=502, detail=f"Weather API unreachable and no offline cache available: {e}")

        # Process 2-hour windows
        windows_df = data.hourly_to_2h_windows(weather_data)
        if windows_df.empty:
            raise HTTPException(status_code=500, detail="Unable to process weather forecast into windows.")

        # Batch prediction with TabPFN
        ranked_df = clf.rank_windows(windows_df)
        top_window = ranked_df.iloc[0].to_dict()
        drivers = clf.explain(top_window)

        # Generate nudge
        month = datetime.now().month
        season = nudge._get_season(month)
        nudge_result = nudge.generate_nudge(
            window=top_window,
            drivers=drivers,
            activity=activity,
            season=season,
            location=location_name,
            model_name=ollama_model if ollama_model else None,
        )

        # Prepare 7-day best windows
        ranked_df["day_name"] = pd.to_datetime(ranked_df["window_start"]).dt.strftime("%a")
        ranked_df["date_str"] = pd.to_datetime(ranked_df["window_start"]).dt.strftime("%b %d")
        daily_best_df = ranked_df.groupby("day_name", sort=False).first().reset_index()

        daily_best = []
        for _, r in daily_best_df.iterrows():
            daily_best.append({
                "day_name": str(r["day_name"]),
                "date_str": str(r["date_str"]),
                "window_start": str(r["window_start"]),
                "window_end": str(r["window_end"]),
                "score": float(r["predicted"]),
                "temperature": float(r.get("temperature_2m", 20.0)),
                "cloud_cover": float(r.get("cloud_cover", 0.0)),
                "precipitation": float(r.get("precipitation", 0.0)),
                "pm2_5": float(r.get("pm2_5", 15.0)),
            })

        # Calculate confidence metric
        uncertainty = float(top_window.get("uncertainty", 1.0))
        confidence = round(max(0.1, 1.0 - (uncertainty / 4.0)), 2)

        return {
            "top_window": top_window,
            "drivers": drivers,
            "nudge": nudge_result,
            "daily_best": daily_best,
            "confidence": confidence,
            "train_count": train_count,
            "is_cached": is_cached,
            "location": location_name,
            "season": season,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Prediction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class OutingPayload(BaseModel):
    latitude: float
    longitude: float
    outing_date: str
    outing_time: str
    activity: str
    rating: float
    notes: Optional[str] = None


@app.post("/api/outings")
def log_outing(payload: OutingPayload):
    try:
        data.log_outing(
            lat=payload.latitude,
            lon=payload.longitude,
            outing_date=payload.outing_date,
            outing_time=payload.outing_time,
            activity=payload.activity,
            rating=payload.rating,
            notes=payload.notes if payload.notes else None,
        )
        # Clear model cache so next prediction incorporates new outing
        global _cached_model_key, _cached_clf
        _cached_model_key = ""
        _cached_clf = None

        X_train, _ = model.load_training_data()
        return {"success": True, "train_count": len(X_train)}
    except Exception as e:
        logger.exception("Logging outing failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/field-card")
def get_field_card(
    lat: float = 40.7128,
    lon: float = -74.0060,
    location_name: str = "Central Park",
    activity: str = "Walk",
    ollama_model: str = "qwen3",
):
    try:
        pred = get_prediction(lat=lat, lon=lon, location_name=location_name, activity=activity, ollama_model=ollama_model)
        pdf_bytes = pdf_card.generate_field_card(
            window=pred["top_window"],
            nudge_data=pred["nudge"],
            location=location_name,
            date_str=datetime.now().strftime("%a, %b %d"),
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=grassday-{datetime.now().strftime('%Y%m%d')}.pdf"},
        )
    except Exception as e:
        logger.exception("PDF generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reset")
def reset_database():
    try:
        conn = data.get_db_connection()
        with conn:
            conn.execute("DELETE FROM outings")
            conn.execute("DELETE FROM weather_cache")
        global _cached_model_key, _cached_clf
        _cached_model_key = ""
        _cached_clf = None
        return {"success": True, "message": "Outings and weather cache cleared"}
    except Exception as e:
        logger.exception("Reset failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
