"""Feature-group ablation and contextual error-analysis helpers for Track A."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

try:
    from .baseline_model import (
        CALENDAR_FEATURES,
        HISTORY_FEATURES,
        WEATHER_COLUMNS,
        evaluate_predictions,
    )
except ImportError:
    from baseline_model import (
        CALENDAR_FEATURES,
        HISTORY_FEATURES,
        WEATHER_COLUMNS,
        evaluate_predictions,
    )


OFFICIAL_DAY_FEATURE = "is_official_day_off"
BASE_FEATURE_COLUMNS = [
    "station_name",
    *CALENDAR_FEATURES,
    *HISTORY_FEATURES,
    *WEATHER_COLUMNS,
]


def load_analysis_config(config_path: Path) -> dict[str, Any]:
    """Load and validate the analysis and official-calendar definitions."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    required = {
        "model_candidate",
        "worst_case_rows",
        "feature_groups",
        "peak_periods",
        "official_calendar",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(f"Analysis config is missing: {', '.join(sorted(missing))}")
    calendar = config["official_calendar"]
    calendar_required = {
        "provider",
        "dataset_page",
        "source_url",
        "source_sha256",
        "source_rows",
        "weekday_days_off",
        "weekend_workdays",
    }
    calendar_missing = calendar_required - set(calendar)
    if calendar_missing:
        raise ValueError(
            "Official calendar config is missing: "
            + ", ".join(sorted(calendar_missing))
        )
    configured_features = [
        feature
        for features in config["feature_groups"].values()
        for feature in features
    ]
    if len(configured_features) != len(set(configured_features)):
        raise ValueError("Feature groups must not overlap.")
    if set(configured_features) != set(BASE_FEATURE_COLUMNS):
        raise ValueError("Feature groups must partition the full HGB feature set.")
    return config


def add_official_calendar_features(
    frame: pd.DataFrame, calendar: dict[str, Any]
) -> pd.DataFrame:
    """Add the DGPA office-calendar day-off flag and an audit-friendly day type."""
    if "event_time" not in frame:
        raise ValueError("event_time is required for official calendar features.")
    output = frame.copy()
    local_time = output["event_time"]
    if not isinstance(local_time.dtype, pd.DatetimeTZDtype):
        raise ValueError("event_time must be timezone-aware.")
    local_time = local_time.dt.tz_convert("Asia/Taipei")
    date_key = local_time.dt.strftime("%Y-%m-%d")
    is_weekend = local_time.dt.dayofweek.ge(5)
    weekday_days_off = set(calendar["weekday_days_off"])
    weekend_workdays = set(calendar["weekend_workdays"])
    official_day_off = is_weekend.copy()
    official_day_off |= date_key.isin(weekday_days_off)
    official_day_off &= ~date_key.isin(weekend_workdays)
    output[OFFICIAL_DAY_FEATURE] = official_day_off.astype(bool)
    output["official_day_type"] = np.select(
        [
            ~is_weekend & official_day_off,
            is_weekend & ~official_day_off,
            is_weekend & official_day_off,
        ],
        ["weekday_day_off", "weekend_makeup_workday", "weekend_day_off"],
        default="regular_workday",
    )
    return output


def build_feature_variants(config: dict[str, Any]) -> dict[str, list[str]]:
    """Build full, leave-one-group-out, and holiday-augmented feature sets."""
    variants = {"full": list(BASE_FEATURE_COLUMNS)}
    for group_name, removed_features in config["feature_groups"].items():
        removed = set(removed_features)
        variants[f"without_{group_name}"] = [
            feature for feature in BASE_FEATURE_COLUMNS if feature not in removed
        ]
    variants["full_plus_official_day_off"] = [
        *BASE_FEATURE_COLUMNS,
        OFFICIAL_DAY_FEATURE,
    ]
    return variants


def build_ablation_pipeline(
    feature_columns: list[str],
    candidate: dict[str, Any],
    *,
    loss: str = "poisson",
    random_state: int = 42,
) -> Pipeline:
    """Build an HGB pipeline for an arbitrary validated feature subset."""
    if not feature_columns:
        raise ValueError("Ablation feature columns cannot be empty.")
    unknown = set(feature_columns) - {*BASE_FEATURE_COLUMNS, OFFICIAL_DAY_FEATURE}
    if unknown:
        raise ValueError(f"Unknown ablation features: {', '.join(sorted(unknown))}")
    include_station = "station_name" in feature_columns
    numeric_features = [
        feature for feature in feature_columns if feature != "station_name"
    ]
    transformers: list[tuple[str, Any, list[str]]] = []
    categorical_mask: list[bool] = []
    if include_station:
        transformers.append(
            (
                "station",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                ["station_name"],
            )
        )
        categorical_mask.append(True)
    if numeric_features:
        transformers.append(("numeric", "passthrough", numeric_features))
        categorical_mask.extend([False] * len(numeric_features))
    preprocessor = ColumnTransformer(transformers)
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


def assign_station_demand_tiers(
    training: pd.DataFrame, frame: pd.DataFrame, target: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign low/medium/high station tiers using training-period activity only."""
    station_activity = (
        training.groupby("station_name", as_index=False)[target]
        .mean()
        .rename(columns={target: "training_average_demand"})
        .sort_values(["training_average_demand", "station_name"])
        .reset_index(drop=True)
    )
    station_activity["station_demand_tier"] = pd.qcut(
        station_activity.index,
        q=3,
        labels=["low", "medium", "high"],
    ).astype(str)
    output = frame.merge(
        station_activity, how="left", on="station_name", validate="many_to_one"
    )
    if output["station_demand_tier"].isna().any():
        raise ValueError("Every analyzed station must have a training demand tier.")
    return output, station_activity


def add_error_contexts(
    training: pd.DataFrame,
    test: pd.DataFrame,
    target: str,
    peak_periods: dict[str, list[int]],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Add leakage-safe context labels used only to summarize test errors."""
    output = test.copy()
    hour = output["event_time"].dt.tz_convert("Asia/Taipei").dt.hour
    output["hour"] = hour
    output["weekday"] = output["event_time"].dt.tz_convert(
        "Asia/Taipei"
    ).dt.day_name()
    output["peak_period"] = "off_peak"
    for name, hours in peak_periods.items():
        output.loc[hour.isin(hours), "peak_period"] = name

    rainy_training = training.loc[training["precipitation_mm"].gt(0), "precipitation_mm"]
    rain_median = float(rainy_training.median()) if not rainy_training.empty else 0.0
    output["rain_intensity"] = np.select(
        [
            output["precipitation_mm"].le(0),
            output["precipitation_mm"].lt(rain_median),
        ],
        ["dry", "rain_below_training_median"],
        default="rain_at_or_above_training_median",
    )
    temperature_q25 = float(training["temperature_c"].quantile(0.25))
    temperature_q75 = float(training["temperature_c"].quantile(0.75))
    output["temperature_band"] = np.select(
        [
            output["temperature_c"].le(temperature_q25),
            output["temperature_c"].ge(temperature_q75),
        ],
        ["cool_training_quartile", "warm_training_quartile"],
        default="middle_temperature_range",
    )
    output["actual_demand_band"] = pd.cut(
        output[target],
        bins=[-np.inf, 0, 3, 9, np.inf],
        labels=["zero", "one_to_three", "four_to_nine", "ten_or_more"],
    ).astype(str)
    return output, {
        "rainy_hour_training_median_mm": rain_median,
        "training_temperature_q25_c": temperature_q25,
        "training_temperature_q75_c": temperature_q75,
    }


def summarize_errors(
    frame: pd.DataFrame, target: str, group_columns: Iterable[str]
) -> pd.DataFrame:
    """Return consistent MAE/RMSE/bias/tail-error summaries for many contexts."""
    required = {target, "prediction", "signed_error", "absolute_error"}
    missing = required - set(frame)
    if missing:
        raise ValueError(f"Error frame is missing: {', '.join(sorted(missing))}")
    rows: list[dict[str, Any]] = []
    for group_column in group_columns:
        if group_column not in frame:
            raise ValueError(f"Unknown error context: {group_column}")
        for group_value, group in frame.groupby(group_column, observed=True):
            rows.append(
                {
                    "context": group_column,
                    "segment": str(group_value),
                    "rows": len(group),
                    "average_actual": float(group[target].mean()),
                    "average_prediction": float(group["prediction"].mean()),
                    "mae": float(group["absolute_error"].mean()),
                    "rmse": float(np.sqrt(np.mean(np.square(group["signed_error"])))),
                    "bias_actual_minus_prediction": float(group["signed_error"].mean()),
                    "p90_absolute_error": float(group["absolute_error"].quantile(0.9)),
                    "underprediction_rate": float(group["signed_error"].gt(0).mean()),
                    "overprediction_rate": float(group["signed_error"].lt(0).mean()),
                }
            )
    return pd.DataFrame(rows)


def ablation_metric_row(
    variant: str,
    split: str,
    actual: pd.Series,
    prediction: np.ndarray,
    feature_columns: list[str],
) -> dict[str, Any]:
    """Build one auditable ablation metric row."""
    return {
        "variant": variant,
        "split": split,
        "rows": len(actual),
        "feature_count": len(feature_columns),
        "feature_columns": "|".join(feature_columns),
        **evaluate_predictions(actual, prediction),
    }
