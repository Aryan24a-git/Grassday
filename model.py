"""model.py - Local-first TabPFN prediction, cold-start prior, and explanation engine.

Features:
- Heuristic comfort prior for cold start (N < 10 outings).
- TabPFNRegressor fitting and quantile forecasting (10th, 50th, 90th percentile).
- Uncertainty-aware window ranking.
- Permutation-based feature attribution (top 3 drivers).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tabpfn import TabPFNRegressor

import data

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
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
]

# Baseline neutral values for permutation/counterfactual explanations
NEUTRAL_FEATURE_DEFAULTS = {
    "temperature_2m": 15.0,
    "apparent_temperature": 15.0,
    "precipitation": 0.5,
    "wind_speed_10m": 18.0,
    "cloud_cover": 50.0,
    "relative_humidity_2m": 60.0,
    "uv_index": 4.0,
    "pm2_5": 20.0,
    "hour_of_day": 12.0,
    "day_of_week": 3.0,
    "daylight_fraction": 0.5,
    "sunset_proximity_hours": 3.0,
    "month_sin": 0.0,
    "month_cos": 0.0,
}


def compute_heuristic_prior(window_features: Dict[str, Any] | pd.Series) -> float:
    """
    Compute a transparent biometeorological outdoor comfort score in [1.0, 5.0].
    Penalizes extreme temps, rain, high wind, severe UV, bad AQI; rewards golden hour & daylight.
    """
    app_temp = float(window_features.get("apparent_temperature", 20.0))
    rain = float(window_features.get("precipitation", 0.0))
    wind = float(window_features.get("wind_speed_10m", 10.0))
    uv = float(window_features.get("uv_index", 2.0))
    pm25 = float(window_features.get("pm2_5", 12.0))
    daylight = float(window_features.get("daylight_fraction", 1.0))
    sunset_prox = float(window_features.get("sunset_proximity_hours", 4.0))

    score = 5.0

    # 1. Thermal comfort: ideal 19°C - 23°C (target 21°C)
    temp_diff = abs(app_temp - 21.0)
    if temp_diff > 2.0:
        score -= min(2.5, (temp_diff - 2.0) * 0.12)

    # 2. Rain penalty
    if rain > 0.0:
        score -= min(2.5, 0.8 + rain * 1.2)

    # 3. Wind penalty (uncomfortable above 20 km/h)
    if wind > 20.0:
        score -= min(1.5, (wind - 20.0) * 0.06)

    # 4. Air quality penalty (PM2.5 above 25 ug/m3)
    if pm25 > 25.0:
        score -= min(1.5, (pm25 - 25.0) * 0.04)

    # 5. UV penalty (harsh above 7)
    if uv > 7.0:
        score -= min(1.0, (uv - 7.0) * 0.15)

    # 6. Daylight & Sunset proximity bonus / night penalty
    if daylight < 0.2:
        score -= 0.6  # Nighttime / darkness penalty
    elif abs(sunset_prox) <= 1.5:
        score += 0.3  # Golden hour bonus

    return float(np.clip(score, 1.0, 5.0))


def load_training_data(db_path: str = data.DEFAULT_DB_PATH) -> Tuple[pd.DataFrame, pd.Series]:
    """Load logged outings from SQLite and assemble feature matrix X and rating target y."""
    conn = data.get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT features_json, rating FROM outings ORDER BY id ASC")
    rows = cur.fetchall()

    if not rows:
        return pd.DataFrame(columns=FEATURE_COLUMNS), pd.Series(dtype=float)

    x_list = []
    y_list = []
    for r in rows:
        try:
            feats = json.loads(r["features_json"])
            if all(col in feats for col in FEATURE_COLUMNS):
                x_list.append({col: float(feats[col]) for col in FEATURE_COLUMNS})
                y_list.append(float(r["rating"]))
        except Exception as e:
            logger.warning("Skipping malformed outing row: %s", e)

    if not x_list:
        return pd.DataFrame(columns=FEATURE_COLUMNS), pd.Series(dtype=float)

    return pd.DataFrame(x_list), pd.Series(y_list, name="rating")


class GrassdayModel:
    """Grassday predictor combining TabPFN regressor with cold-start comfort prior."""

    def __init__(self, model_checkpoint: str = "tabpfn-v2-regressor.ckpt", device: str = "cpu"):
        self.device = device
        self.model_checkpoint = model_checkpoint
        self.regressor: Optional[TabPFNRegressor] = None
        self.is_fitted: bool = False
        self.train_count: int = 0
        self.neutral_reference: Dict[str, float] = dict(NEUTRAL_FEATURE_DEFAULTS)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> GrassdayModel:
        """Fit TabPFNRegressor on training features and ratings."""
        self.train_count = len(X)
        if self.train_count < 2:
            self.is_fitted = False
            return self

        # Update neutral feature reference with sample means
        for col in FEATURE_COLUMNS:
            if col in X.columns:
                self.neutral_reference[col] = float(X[col].mean())

        try:
            self.regressor = TabPFNRegressor(model_path=self.model_checkpoint, device=self.device)
            self.regressor.fit(X[FEATURE_COLUMNS].values, y.values)
            self.is_fitted = True
        except Exception as err:
            logger.error("TabPFN fitting failed (%s). Falling back to heuristic prior.", err)
            self.is_fitted = False

        return self

    def predict_window(self, window_row: Dict[str, Any] | pd.Series) -> Dict[str, float]:
        """
        Predict point estimate and quantiles (q10, q50, q90) for a single window,
        blending TabPFN with the cold-start heuristic prior.
        """
        prior = compute_heuristic_prior(window_row)

        if not self.is_fitted or self.regressor is None:
            # Complete cold start (0 outings) or fit fallback
            return {
                "predicted": prior,
                "q10": max(1.0, prior - 0.7),
                "q50": prior,
                "q90": min(5.0, prior + 0.7),
                "uncertainty": 1.4,
                "prior": prior,
                "cold_start_weight": 1.0,
            }

        # Format input vector
        x_vec = np.array([[float(window_row.get(c, self.neutral_reference.get(c, 0.0))) for c in FEATURE_COLUMNS]])

        try:
            quantiles = self.regressor.predict(x_vec, output_type="quantiles", quantiles=[0.1, 0.5, 0.9])
            q10_raw = float(quantiles[0][0])
            q50_raw = float(quantiles[1][0])
            q90_raw = float(quantiles[2][0])
        except Exception as err:
            logger.warning("TabPFN quantile prediction failed (%s). Using prior.", err)
            q10_raw = prior - 0.5
            q50_raw = prior
            q90_raw = prior + 0.5

        # Clip raw outputs to valid rating range [1.0, 5.0]
        q10_raw = float(np.clip(q10_raw, 1.0, 5.0))
        q50_raw = float(np.clip(q50_raw, 1.0, 5.0))
        q90_raw = float(np.clip(q90_raw, 1.0, 5.0))

        # Dynamic cold-start blending:
        # N < 10: blend heuristic prior and TabPFN
        # N >= 10: pure TabPFN
        if self.train_count < 10:
            prior_weight = max(0.0, (10 - self.train_count) / 10.0)
            model_weight = 1.0 - prior_weight
        else:
            prior_weight = 0.0
            model_weight = 1.0

        q50_blended = prior_weight * prior + model_weight * q50_raw
        q10_blended = prior_weight * (prior - 0.4) + model_weight * q10_raw
        q90_blended = prior_weight * (prior + 0.4) + model_weight * q90_raw

        q10_blended = float(np.clip(q10_blended, 1.0, 5.0))
        q50_blended = float(np.clip(q50_blended, 1.0, 5.0))
        q90_blended = float(np.clip(q90_blended, 1.0, 5.0))
        uncertainty = float(max(0.0, q90_blended - q10_blended))

        return {
            "predicted": round(q50_blended, 2),
            "q10": round(q10_blended, 2),
            "q50": round(q50_blended, 2),
            "q90": round(q90_blended, 2),
            "uncertainty": round(uncertainty, 2),
            "prior": round(prior, 2),
            "cold_start_weight": round(prior_weight, 2),
        }

    def rank_windows(
        self,
        windows_df: pd.DataFrame,
        uncertainty_penalty: float = 0.1,
    ) -> pd.DataFrame:
        """
        Score and rank candidate windows, penalizing high uncertainty slightly.
        Ranking score = q50 - uncertainty_penalty * (q90 - q10).
        Uses vectorized batch prediction for speed.
        """
        if windows_df.empty:
            return windows_df

        if not self.is_fitted or self.regressor is None:
            results = []
            for _, row in windows_df.iterrows():
                pred_dict = self.predict_window(row)
                rank_score = pred_dict["q50"] - uncertainty_penalty * pred_dict["uncertainty"]
                record = row.to_dict()
                record.update(pred_dict)
                record["rank_score"] = round(float(rank_score), 3)
                results.append(record)
            ranked_df = pd.DataFrame(results)
            return ranked_df.sort_values(by="rank_score", ascending=False).reset_index(drop=True)

        # Batch prediction with TabPFN
        x_rows = []
        for _, row in windows_df.iterrows():
            x_rows.append([float(row.get(c, self.neutral_reference.get(c, 0.0))) for c in FEATURE_COLUMNS])
        x_mat = np.array(x_rows)

        try:
            quantiles = self.regressor.predict(x_mat, output_type="quantiles", quantiles=[0.1, 0.5, 0.9])
            q10_raw = np.clip(quantiles[0], 1.0, 5.0)
            q50_raw = np.clip(quantiles[1], 1.0, 5.0)
            q90_raw = np.clip(quantiles[2], 1.0, 5.0)
        except Exception as err:
            logger.warning("Batched TabPFN prediction failed (%s). Falling back.", err)
            results = []
            for _, row in windows_df.iterrows():
                pred_dict = self.predict_window(row)
                rank_score = pred_dict["q50"] - uncertainty_penalty * pred_dict["uncertainty"]
                record = row.to_dict()
                record.update(pred_dict)
                record["rank_score"] = round(float(rank_score), 3)
                results.append(record)
            ranked_df = pd.DataFrame(results)
            return ranked_df.sort_values(by="rank_score", ascending=False).reset_index(drop=True)

        priors = np.array([compute_heuristic_prior(row) for _, row in windows_df.iterrows()])

        if self.train_count < 10:
            prior_weight = max(0.0, (10 - self.train_count) / 10.0)
            model_weight = 1.0 - prior_weight
        else:
            prior_weight = 0.0
            model_weight = 1.0

        q50_blended = np.clip(prior_weight * priors + model_weight * q50_raw, 1.0, 5.0)
        q10_blended = np.clip(prior_weight * (priors - 0.4) + model_weight * q10_raw, 1.0, 5.0)
        q90_blended = np.clip(prior_weight * (priors + 0.4) + model_weight * q90_raw, 1.0, 5.0)
        uncertainty = np.maximum(0.0, q90_blended - q10_blended)
        rank_scores = q50_blended - uncertainty_penalty * uncertainty

        results = []
        for i, (_, row) in enumerate(windows_df.iterrows()):
            record = row.to_dict()
            record.update({
                "predicted": round(float(q50_blended[i]), 2),
                "q10": round(float(q10_blended[i]), 2),
                "q50": round(float(q50_blended[i]), 2),
                "q90": round(float(q90_blended[i]), 2),
                "uncertainty": round(float(uncertainty[i]), 2),
                "prior": round(float(priors[i]), 2),
                "cold_start_weight": round(float(prior_weight), 2),
                "rank_score": round(float(rank_scores[i]), 3),
            })
            results.append(record)

        ranked_df = pd.DataFrame(results)
        return ranked_df.sort_values(by="rank_score", ascending=False).reset_index(drop=True)

    def explain(self, window_row: Dict[str, Any] | pd.Series) -> List[Dict[str, Any]]:
        """
        Explain the prediction for a window using permutation/counterfactual sensitivity.
        Computes the delta in prediction when each feature is substituted with neutral reference.
        Returns the top 3 features by impact.
        """
        base_pred = self.predict_window(window_row)["predicted"]
        impacts = []

        feature_labels = {
            "temperature_2m": "Temperature",
            "apparent_temperature": "Thermal feel",
            "precipitation": "Precipitation",
            "wind_speed_10m": "Wind speed",
            "cloud_cover": "Cloud cover",
            "relative_humidity_2m": "Humidity",
            "uv_index": "UV Index",
            "pm2_5": "Air Quality (PM2.5)",
            "daylight_fraction": "Daylight",
            "sunset_proximity_hours": "Sunset timing",
            "hour_of_day": "Hour of day",
        }

        eval_features = [f for f in feature_labels.keys() if f in FEATURE_COLUMNS]

        for feat in eval_features:
            perturbed = dict(window_row)
            perturbed[feat] = self.neutral_reference.get(feat, NEUTRAL_FEATURE_DEFAULTS.get(feat, 0.0))
            perturbed_pred = self.predict_window(perturbed)["predicted"]
            delta = round(base_pred - perturbed_pred, 3)

            val = window_row.get(feat, 0.0)
            impacts.append({
                "feature": feat,
                "label": feature_labels.get(feat, feat),
                "value": val,
                "delta": delta,
                "abs_delta": abs(delta),
                "direction": "positive" if delta > 0 else "negative" if delta < 0 else "neutral",
            })

        # Sort by largest magnitude of delta
        impacts.sort(key=lambda x: x["abs_delta"], reverse=True)
        return impacts[:3]


def get_cold_start_status(train_count: int) -> Dict[str, Any]:
    """Return cold start progress details and prompt for the user."""
    needed = max(0, 10 - train_count)
    is_cold_start = train_count < 10
    pct = min(100, int((train_count / 10.0) * 100))
    message = (
        f"Cold start active: {train_count}/10 outings logged ({pct}%). "
        f"Log {needed} more to unlock 100% personalized predictions."
        if is_cold_start
        else f"Personalized mode active ({train_count} outings logged)."
    )
    return {
        "train_count": train_count,
        "needed": needed,
        "is_cold_start": is_cold_start,
        "percentage": pct,
        "message": message,
    }
