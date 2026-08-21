"""XGBoost helpers for the Track A hourly demand comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

try:
    from .baseline_model import CALENDAR_FEATURES, HISTORY_FEATURES, WEATHER_COLUMNS
except ImportError:
    from baseline_model import CALENDAR_FEATURES, HISTORY_FEATURES, WEATHER_COLUMNS


def load_xgboost_config(config_path: Path) -> dict[str, Any]:
    """Load and validate the bounded XGBoost candidate configuration."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    required = {
        "model_name",
        "objective",
        "eval_metric",
        "tree_method",
        "random_state",
        "n_jobs",
        "candidates",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(f"XGBoost config is missing: {', '.join(sorted(missing))}")
    if not config["candidates"]:
        raise ValueError("At least one XGBoost candidate is required.")
    candidate_fields = {
        "candidate",
        "n_estimators",
        "learning_rate",
        "max_depth",
        "min_child_weight",
        "subsample",
        "colsample_bytree",
        "reg_alpha",
        "reg_lambda",
    }
    for candidate in config["candidates"]:
        missing_candidate = candidate_fields - set(candidate)
        if missing_candidate:
            raise ValueError(
                "XGBoost candidate is missing: "
                + ", ".join(sorted(missing_candidate))
            )
    return config


def xgboost_feature_columns(include_weather: bool = True) -> list[str]:
    """Return the same station, calendar, history, and weather inputs as HGB."""
    columns = ["station_name", *CALENDAR_FEATURES, *HISTORY_FEATURES]
    if include_weather:
        columns.extend(WEATHER_COLUMNS)
    return columns


def build_xgboost_pipeline(
    candidate: dict[str, Any],
    config: dict[str, Any],
    include_weather: bool = True,
) -> Pipeline:
    """Build a station-aware, sparse one-hot XGBoost count model."""
    numeric_features = [*CALENDAR_FEATURES, *HISTORY_FEATURES]
    if include_weather:
        numeric_features.extend(WEATHER_COLUMNS)
    preprocessor = ColumnTransformer(
        [
            (
                "station",
                OneHotEncoder(handle_unknown="ignore", sparse_output=True),
                ["station_name"],
            ),
            ("numeric", "passthrough", numeric_features),
        ]
    )
    model = XGBRegressor(
        objective=config["objective"],
        eval_metric=config["eval_metric"],
        tree_method=config["tree_method"],
        random_state=int(config["random_state"]),
        n_jobs=int(config["n_jobs"]),
        n_estimators=int(candidate["n_estimators"]),
        learning_rate=float(candidate["learning_rate"]),
        max_depth=int(candidate["max_depth"]),
        min_child_weight=float(candidate["min_child_weight"]),
        subsample=float(candidate["subsample"]),
        colsample_bytree=float(candidate["colsample_bytree"]),
        reg_alpha=float(candidate["reg_alpha"]),
        reg_lambda=float(candidate["reg_lambda"]),
    )
    return Pipeline([("preprocessor", preprocessor), ("model", model)])
