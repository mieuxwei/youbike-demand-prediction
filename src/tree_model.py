"""Tree-model helpers for hourly transfer-demand experiments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

try:
    from .baseline_model import CALENDAR_FEATURES, HISTORY_FEATURES, WEATHER_COLUMNS
except ImportError:
    from baseline_model import CALENDAR_FEATURES, HISTORY_FEATURES, WEATHER_COLUMNS


def load_tree_config(config_path: Path) -> dict[str, Any]:
    """Load and validate tree candidates and rolling-origin folds."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    required = {"candidates", "rolling_origin_folds", "random_state", "loss"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"Tree config is missing: {', '.join(sorted(missing))}")
    if not config["candidates"] or not config["rolling_origin_folds"]:
        raise ValueError("Tree candidates and rolling-origin folds cannot be empty.")
    return config


def tree_feature_columns(include_weather: bool) -> list[str]:
    """Return station, calendar, history, and optional weather inputs."""
    columns = ["station_name", *CALENDAR_FEATURES, *HISTORY_FEATURES]
    if include_weather:
        columns.extend(WEATHER_COLUMNS)
    return columns


def build_tree_pipeline(
    include_weather: bool,
    candidate: dict[str, Any],
    loss: str = "poisson",
    random_state: int = 42,
) -> Pipeline:
    """Create an efficient histogram gradient-boosting pipeline."""
    numeric_features = [*CALENDAR_FEATURES, *HISTORY_FEATURES]
    if include_weather:
        numeric_features.extend(WEATHER_COLUMNS)
    preprocessor = ColumnTransformer(
        [
            (
                "station",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value", unknown_value=-1
                ),
                ["station_name"],
            ),
            ("numeric", "passthrough", numeric_features),
        ]
    )
    categorical_mask = [True, *([False] * len(numeric_features))]
    model = HistGradientBoostingRegressor(
        loss=loss,
        learning_rate=float(candidate["learning_rate"]),
        max_iter=int(candidate["max_iter"]),
        max_leaf_nodes=int(candidate["max_leaf_nodes"]),
        min_samples_leaf=int(candidate["min_samples_leaf"]),
        l2_regularization=float(candidate["l2_regularization"]),
        categorical_features=categorical_mask,
        random_state=random_state,
    )
    return Pipeline([("preprocessor", preprocessor), ("model", model)])


def build_rolling_origin_splits(
    model_data: pd.DataFrame, folds: list[dict[str, str]]
) -> list[tuple[str, pd.DataFrame, pd.DataFrame]]:
    """Build expanding training windows followed by non-overlapping validations."""
    outputs: list[tuple[str, pd.DataFrame, pd.DataFrame]] = []
    previous_validation_end: pd.Timestamp | None = None
    for fold in folds:
        train_end = pd.Timestamp(fold["train_end"]).tz_convert("Asia/Taipei")
        validation_end = pd.Timestamp(fold["validation_end"]).tz_convert(
            "Asia/Taipei"
        )
        if train_end >= validation_end:
            raise ValueError("Each rolling fold must train before it validates.")
        if previous_validation_end is not None and train_end != previous_validation_end:
            raise ValueError("Rolling folds must connect without overlap or gaps.")
        training = model_data.loc[model_data["event_time"].le(train_end)].copy()
        validation = model_data.loc[
            model_data["event_time"].gt(train_end)
            & model_data["event_time"].le(validation_end)
        ].copy()
        if training.empty or validation.empty:
            raise ValueError("Every rolling fold must contain train and validation rows.")
        outputs.append((fold["fold"], training, validation))
        previous_validation_end = validation_end
    return outputs
