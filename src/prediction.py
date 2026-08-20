"""Build safe one-hour-ahead feature rows and load trusted model bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    from .baseline_model import (
        CALENDAR_FEATURES,
        HISTORY_FEATURES,
        WEATHER_COLUMNS,
    )
except ImportError:
    from baseline_model import CALENDAR_FEATURES, HISTORY_FEATURES, WEATHER_COLUMNS


def local_hour(value: str | pd.Timestamp) -> pd.Timestamp:
    """Parse a timestamp, use Taipei for naive values, and require an exact hour."""
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("Asia/Taipei")
    else:
        parsed = parsed.tz_convert("Asia/Taipei")
    if any([parsed.minute, parsed.second, parsed.microsecond, parsed.nanosecond]):
        raise ValueError("Prediction target must be aligned to an exact hour.")
    return parsed


def file_sha256(source_path: Path) -> str:
    digest = hashlib.sha256()
    with source_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model_metadata(metadata_path: Path) -> dict[str, Any]:
    """Validate fields required to reproduce feature construction."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = {
        "format_version",
        "model_name",
        "artifact_sha256",
        "target",
        "selected_stations",
        "feature_columns",
        "includes_weather",
    }
    missing = required - set(metadata)
    if missing:
        raise ValueError(f"Model metadata is missing: {', '.join(sorted(missing))}")
    if metadata["format_version"] != 1:
        raise ValueError(f"Unsupported metadata format: {metadata['format_version']}")
    return metadata


def load_verified_model(model_path: Path, metadata: dict[str, Any]) -> object:
    """Check artifact integrity before loading the trusted local joblib file."""
    actual_checksum = file_sha256(model_path)
    if actual_checksum != metadata["artifact_sha256"]:
        raise ValueError("Model artifact checksum does not match its metadata.")
    return joblib.load(model_path)


def build_prediction_features(
    demand: pd.DataFrame,
    weather: pd.DataFrame,
    stations: list[str],
    target_time: str | pd.Timestamp,
) -> pd.DataFrame:
    """Build target-hour features using demand no later than target minus one hour."""
    target = local_hour(target_time)
    required_demand = {"event_time", "station_name", "borrow_count", "return_count"}
    missing_demand = required_demand - set(demand)
    if missing_demand:
        raise ValueError(
            f"Demand data is missing: {', '.join(sorted(missing_demand))}"
        )
    required_weather = {"event_time", *WEATHER_COLUMNS}
    missing_weather = required_weather - set(weather)
    if missing_weather:
        raise ValueError(
            f"Weather data is missing: {', '.join(sorted(missing_weather))}"
        )

    demand = demand.copy()
    weather = weather.copy()
    demand["event_time"] = pd.to_datetime(
        demand["event_time"], utc=True
    ).dt.tz_convert("Asia/Taipei")
    weather["event_time"] = pd.to_datetime(
        weather["event_time"], utc=True
    ).dt.tz_convert("Asia/Taipei")
    history_start = target - pd.Timedelta(hours=168)
    history_end = target - pd.Timedelta(hours=1)
    if demand["event_time"].min() > history_start:
        raise ValueError("Demand history does not reach target minus 168 hours.")
    if demand["event_time"].max() < history_end:
        raise ValueError("Demand history is not current through target minus one hour.")
    if demand.duplicated(["station_name", "event_time"]).any():
        raise ValueError("Demand data contains duplicate station-hour rows.")

    known_stations = set(demand["station_name"])
    missing_stations = sorted(set(stations) - known_stations)
    if missing_stations:
        preview = ", ".join(missing_stations[:5])
        raise ValueError(f"Demand history is missing model stations: {preview}")

    hours = pd.date_range(history_start, history_end, freq="h")
    grid = pd.MultiIndex.from_product(
        [stations, hours], names=["station_name", "event_time"]
    )
    history = (
        demand.loc[
            demand["station_name"].isin(stations)
            & demand["event_time"].between(history_start, history_end),
            ["station_name", "event_time", "borrow_count", "return_count"],
        ]
        .set_index(["station_name", "event_time"])
        .reindex(grid, fill_value=0)
        .reset_index()
    )
    features = pd.DataFrame({"station_name": stations})
    lag_1h = history.loc[history["event_time"].eq(history_end)].set_index(
        "station_name"
    )
    lag_24h = history.loc[
        history["event_time"].eq(target - pd.Timedelta(hours=24))
    ].set_index("station_name")
    lag_168h = history.loc[history["event_time"].eq(history_start)].set_index(
        "station_name"
    )
    rolling_24h = (
        history.loc[history["event_time"].ge(target - pd.Timedelta(hours=24))]
        .groupby("station_name")["borrow_count"]
        .mean()
    )
    features["borrow_lag_1h"] = features["station_name"].map(
        lag_1h["borrow_count"]
    )
    features["return_lag_1h"] = features["station_name"].map(
        lag_1h["return_count"]
    )
    features["borrow_lag_24h"] = features["station_name"].map(
        lag_24h["borrow_count"]
    )
    features["borrow_lag_168h"] = features["station_name"].map(
        lag_168h["borrow_count"]
    )
    features["borrow_rolling_mean_24h"] = features["station_name"].map(
        rolling_24h
    )

    hour = target.hour
    weekday = target.dayofweek
    month = target.month
    features["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    features["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    features["weekday_sin"] = np.sin(2 * np.pi * weekday / 7)
    features["weekday_cos"] = np.cos(2 * np.pi * weekday / 7)
    features["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12)
    features["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12)
    features["is_weekend"] = weekday >= 5

    target_weather = weather.loc[weather["event_time"].eq(target)]
    if len(target_weather) != 1:
        raise ValueError("Weather data must contain exactly one target-hour row.")
    for column in WEATHER_COLUMNS:
        features[column] = target_weather.iloc[0][column]
    if features[[*HISTORY_FEATURES, *WEATHER_COLUMNS]].isna().any().any():
        raise ValueError("Prediction features contain missing values.")
    return features[
        ["station_name", *CALENDAR_FEATURES, *HISTORY_FEATURES, *WEATHER_COLUMNS]
    ]


def predict_hourly_demand(
    model: object,
    features: pd.DataFrame,
    target_time: str | pd.Timestamp,
) -> pd.DataFrame:
    """Predict non-negative demand and rank stations from highest to lowest."""
    prediction = np.maximum(np.asarray(model.predict(features), dtype=float), 0)
    output = pd.DataFrame(
        {
            "target_time": local_hour(target_time).isoformat(),
            "station_name": features["station_name"],
            "predicted_borrow_count": prediction,
        }
    ).sort_values("predicted_borrow_count", ascending=False)
    output.insert(0, "prediction_rank", range(1, len(output) + 1))
    return output.reset_index(drop=True)


def attach_historical_actuals(
    predictions: pd.DataFrame,
    demand: pd.DataFrame,
    target_time: str | pd.Timestamp,
) -> pd.DataFrame:
    """Attach held-out actuals for a covered historical hour after prediction."""
    target = local_hour(target_time)
    demand = demand.copy()
    demand["event_time"] = pd.to_datetime(
        demand["event_time"], utc=True
    ).dt.tz_convert("Asia/Taipei")
    if demand["event_time"].max() < target:
        raise ValueError("Historical actuals are unavailable for the target hour.")
    actual = (
        demand.loc[demand["event_time"].eq(target)]
        .set_index("station_name")["borrow_count"]
    )
    output = predictions.copy()
    output["actual_borrow_count"] = output["station_name"].map(actual).fillna(0)
    output["absolute_error"] = (
        output["actual_borrow_count"] - output["predicted_borrow_count"]
    ).abs()
    return output
