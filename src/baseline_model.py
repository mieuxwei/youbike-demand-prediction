"""Build and evaluate leakage-aware hourly transfer-demand baselines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


DEMAND_COLUMNS = {"event_time", "station_name", "borrow_count", "return_count"}
WEATHER_COLUMNS = [
    "temperature_c",
    "relative_humidity_percent",
    "precipitation_mm",
    "wind_speed_kmh",
    "is_raining",
]
HISTORY_FEATURES = [
    "borrow_lag_1h",
    "return_lag_1h",
    "borrow_lag_24h",
    "borrow_lag_168h",
    "borrow_rolling_mean_24h",
]
CALENDAR_FEATURES = [
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "month_sin",
    "month_cos",
    "is_weekend",
]


def load_model_config(config_path: Path) -> dict[str, Any]:
    """Load and minimally validate the baseline experiment configuration."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    required = {
        "top_station_count",
        "train_end",
        "validation_end",
        "test_end",
        "ridge_alphas",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(f"Baseline config is missing: {', '.join(sorted(missing))}")
    if not config["ridge_alphas"]:
        raise ValueError("At least one Ridge alpha is required.")
    return config


def load_station_hour_demand(source_path: Path) -> pd.DataFrame:
    """Load only model-required demand columns from the large generated CSV."""
    header = pd.read_csv(source_path, nrows=0)
    missing = DEMAND_COLUMNS - set(header)
    if missing:
        raise ValueError(f"Demand data is missing: {', '.join(sorted(missing))}")
    demand = pd.read_csv(source_path, usecols=sorted(DEMAND_COLUMNS))
    demand["event_time"] = pd.to_datetime(demand["event_time"], utc=True).dt.tz_convert(
        "Asia/Taipei"
    )
    demand[["borrow_count", "return_count"]] = demand[
        ["borrow_count", "return_count"]
    ].apply(pd.to_numeric, errors="raise")
    return demand


def load_hourly_weather(source_path: Path) -> pd.DataFrame:
    """Load the cleaned one-row-per-hour weather table."""
    required = {"event_time", *WEATHER_COLUMNS}
    header = pd.read_csv(source_path, nrows=0)
    missing = required - set(header)
    if missing:
        raise ValueError(f"Weather data is missing: {', '.join(sorted(missing))}")
    weather = pd.read_csv(source_path, usecols=["event_time", *WEATHER_COLUMNS])
    weather["event_time"] = pd.to_datetime(
        weather["event_time"], utc=True
    ).dt.tz_convert("Asia/Taipei")
    if weather["event_time"].duplicated().any():
        raise ValueError("Weather data must contain one row per hour.")
    weather["is_raining"] = weather["is_raining"].astype(bool)
    return weather


def select_top_training_stations(
    demand: pd.DataFrame, train_end: pd.Timestamp, station_count: int
) -> list[str]:
    """Rank stations using training-period borrowing only."""
    training = demand.loc[demand["event_time"].le(train_end)]
    activity = training.groupby("station_name")["borrow_count"].sum()
    if len(activity) < station_count:
        raise ValueError(
            f"Requested {station_count} stations, but training data has {len(activity)}."
        )
    return activity.nlargest(station_count).index.tolist()


def complete_station_hours(
    demand: pd.DataFrame, stations: list[str]
) -> pd.DataFrame:
    """Fill zero-demand hours only between each selected station's first/last event."""
    selected = demand.loc[demand["station_name"].isin(stations)].copy()
    completed: list[pd.DataFrame] = []
    for station_name, group in selected.groupby("station_name", sort=False):
        group = group.set_index("event_time").sort_index()
        hours = pd.date_range(group.index.min(), group.index.max(), freq="h")
        group = group.reindex(hours)
        group.index.name = "event_time"
        group["station_name"] = station_name
        group[["borrow_count", "return_count"]] = group[
            ["borrow_count", "return_count"]
        ].fillna(0)
        completed.append(group.reset_index())
    if len(completed) != len(stations):
        raise ValueError("One or more selected stations had no demand rows.")
    return pd.concat(completed, ignore_index=True).sort_values(
        ["station_name", "event_time"]
    )


def build_hourly_model_dataset(
    demand: pd.DataFrame, weather: pd.DataFrame, stations: list[str]
) -> pd.DataFrame:
    """Create calendar, past-only lag, rolling, and weather predictors."""
    model_data = complete_station_hours(demand, stations)
    model_data = model_data.merge(
        weather, how="left", on="event_time", validate="many_to_one"
    )
    if model_data[WEATHER_COLUMNS].isna().any().any():
        raise ValueError("Weather does not cover every selected station-hour.")

    timestamp = model_data["event_time"]
    hour = timestamp.dt.hour
    weekday = timestamp.dt.dayofweek
    month = timestamp.dt.month
    model_data["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    model_data["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    model_data["weekday_sin"] = np.sin(2 * np.pi * weekday / 7)
    model_data["weekday_cos"] = np.cos(2 * np.pi * weekday / 7)
    model_data["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12)
    model_data["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12)
    model_data["is_weekend"] = weekday.ge(5)

    grouped = model_data.groupby("station_name", sort=False)
    model_data["borrow_lag_1h"] = grouped["borrow_count"].shift(1)
    model_data["return_lag_1h"] = grouped["return_count"].shift(1)
    model_data["borrow_lag_24h"] = grouped["borrow_count"].shift(24)
    model_data["borrow_lag_168h"] = grouped["borrow_count"].shift(168)
    model_data["borrow_rolling_mean_24h"] = grouped["borrow_count"].transform(
        lambda values: values.shift(1).rolling(24, min_periods=24).mean()
    )
    return model_data.dropna(subset=HISTORY_FEATURES).reset_index(drop=True)


def split_by_time(
    model_data: pd.DataFrame,
    train_end: pd.Timestamp,
    validation_end: pd.Timestamp,
    test_end: pd.Timestamp,
) -> dict[str, pd.DataFrame]:
    """Create non-overlapping chronological train, validation, and test sets."""
    if not train_end < validation_end < test_end:
        raise ValueError("Split boundaries must be strictly increasing.")
    timestamp = model_data["event_time"]
    splits = {
        "train": model_data.loc[timestamp.le(train_end)].copy(),
        "validation": model_data.loc[
            timestamp.gt(train_end) & timestamp.le(validation_end)
        ].copy(),
        "test": model_data.loc[
            timestamp.gt(validation_end) & timestamp.le(test_end)
        ].copy(),
    }
    if any(frame.empty for frame in splits.values()):
        raise ValueError("Every chronological split must contain rows.")
    return splits


def build_ridge_pipeline(include_weather: bool, alpha: float) -> Pipeline:
    """Create a station-aware Ridge regression pipeline."""
    numeric_features = [*CALENDAR_FEATURES, *HISTORY_FEATURES]
    if include_weather:
        numeric_features.extend(WEATHER_COLUMNS)
    preprocessor = ColumnTransformer(
        [
            (
                "station",
                OneHotEncoder(handle_unknown="ignore"),
                ["station_name"],
            ),
            ("numeric", StandardScaler(), numeric_features),
        ]
    )
    return Pipeline(
        [("preprocessor", preprocessor), ("model", Ridge(alpha=alpha))]
    )


def evaluate_predictions(
    actual: pd.Series | np.ndarray, predicted: pd.Series | np.ndarray
) -> dict[str, float]:
    """Return the planned regression metrics after flooring negative demand."""
    clipped = np.maximum(np.asarray(predicted, dtype=float), 0)
    actual_array = np.asarray(actual, dtype=float)
    return {
        "mae": float(mean_absolute_error(actual_array, clipped)),
        "rmse": float(np.sqrt(mean_squared_error(actual_array, clipped))),
        "r2": float(r2_score(actual_array, clipped)),
    }


def feature_columns(include_weather: bool) -> list[str]:
    """Return model inputs in one stable order."""
    columns = ["station_name", *CALENDAR_FEATURES, *HISTORY_FEATURES]
    if include_weather:
        columns.extend(WEATHER_COLUMNS)
    return columns
