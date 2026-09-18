"""Train the first leakage-aware Track B availability regressions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor

try:
    from .features import add_future_targets, add_lag_features, add_rolling_features
except ImportError:
    from features import add_future_targets, add_lag_features, add_rolling_features


TAIPEI_TIMEZONE = "Asia/Taipei"
REQUIRED_COLUMNS = {
    "snapshot_time",
    "station_id",
    "available_bikes",
    "available_return_bikes",
    "capacity",
    "latitude",
    "longitude",
    "is_active",
}
BASE_FEATURE_COLUMNS = [
    "available_bikes",
    "available_return_bikes",
    "capacity",
    "availability_fraction",
    "return_space_fraction",
    "latitude",
    "longitude",
    "hour_sin",
    "hour_cos",
    "day_of_week_sin",
    "day_of_week_cos",
    "is_weekend",
    "is_rush_hour",
]
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/track_b_28_days.csv"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/track_b_regression.json"),
    )
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "window_start",
        "train_end",
        "validation_end",
        "test_end",
        "horizons_minutes",
        "lag_minutes",
        "rolling_windows_minutes",
        "target_tolerance_minutes",
        "training_snapshot_stride",
        "random_state",
        "candidates",
    }
    missing = required - set(config)
    if missing:
        raise ValueError("Track B config is missing: " + ", ".join(sorted(missing)))
    if config["training_snapshot_stride"] < 1:
        raise ValueError("training_snapshot_stride must be positive.")
    if not config["candidates"]:
        raise ValueError("At least one model candidate is required.")
    return config


def parse_utc(value: str) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise ValueError("Track B boundaries must include an explicit timezone.")
    return parsed.tz_convert("UTC")


def split_boundaries(config: dict[str, Any]) -> dict[str, pd.Timestamp]:
    boundaries = {
        name: parse_utc(config[name])
        for name in ("window_start", "train_end", "validation_end", "test_end")
    }
    ordered = [
        boundaries["window_start"],
        boundaries["train_end"],
        boundaries["validation_end"],
        boundaries["test_end"],
    ]
    if ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
        raise ValueError("Track B chronological boundaries must be strictly ordered.")
    return boundaries


def load_track_b_model_data(path: Path) -> pd.DataFrame:
    """Load the fixed export with compact dtypes and strict validation."""
    header = pd.read_csv(path, nrows=0)
    missing = REQUIRED_COLUMNS - set(header.columns)
    if missing:
        raise ValueError(
            "Track B regression input is missing columns: "
            + ", ".join(sorted(missing))
        )
    data = pd.read_csv(
        path,
        usecols=sorted(REQUIRED_COLUMNS),
        dtype={
            "snapshot_time": "string",
            "station_id": "category",
            "available_bikes": "int16",
            "available_return_bikes": "int16",
            "capacity": "int16",
            "latitude": "float32",
            "longitude": "float32",
            "is_active": "int8",
        },
    )
    if data.empty:
        raise ValueError("Track B regression input is empty.")
    timestamp_text = data["snapshot_time"]
    if not timestamp_text.str.contains(r"(?:Z|[+-]\d\d:\d\d)$", regex=True).all():
        raise ValueError("snapshot_time must include an explicit timezone.")
    data["snapshot_time"] = pd.to_datetime(timestamp_text, utc=True, errors="coerce")
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Track B regression input contains missing or invalid values.")
    if not data["is_active"].isin([0, 1]).all():
        raise ValueError("is_active must contain only 0 or 1.")
    numeric = ["available_bikes", "available_return_bikes", "capacity"]
    if (data[numeric] < 0).any().any():
        raise ValueError("Bike and capacity values cannot be negative.")
    if (data["available_bikes"] > data["capacity"]).any():
        raise ValueError("available_bikes cannot exceed capacity.")
    if (data["available_return_bikes"] > data["capacity"]).any():
        raise ValueError("available_return_bikes cannot exceed capacity.")
    if data.duplicated(["station_id", "snapshot_time"]).any():
        raise ValueError("Track B regression input contains duplicate station snapshots.")
    data["is_active"] = data["is_active"].astype(bool)
    return data.sort_values(["station_id", "snapshot_time"]).reset_index(drop=True)


def feature_columns(config: dict[str, Any]) -> list[str]:
    columns = BASE_FEATURE_COLUMNS.copy()
    for minutes in config["lag_minutes"]:
        columns.extend(
            [
                f"available_bikes_lag_{minutes}m",
                f"available_bikes_delta_{minutes}m",
            ]
        )
    for minutes in config["rolling_windows_minutes"]:
        columns.extend(
            [
                f"available_bikes_mean_past_{minutes}m",
                f"observations_past_{minutes}m",
            ]
        )
    return columns


def build_track_b_features(
    data: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Build local-calendar, past-only history, and separate future labels."""
    featured = data.copy()
    local_time = featured["snapshot_time"].dt.tz_convert(TAIPEI_TIMEZONE)
    hour = local_time.dt.hour.astype("int8")
    weekday = local_time.dt.dayofweek.astype("int8")
    featured["hour_sin"] = np.sin(2 * np.pi * hour / 24).astype("float32")
    featured["hour_cos"] = np.cos(2 * np.pi * hour / 24).astype("float32")
    featured["day_of_week_sin"] = np.sin(2 * np.pi * weekday / 7).astype("float32")
    featured["day_of_week_cos"] = np.cos(2 * np.pi * weekday / 7).astype("float32")
    featured["is_weekend"] = weekday.ge(5).astype("int8")
    featured["is_rush_hour"] = (
        hour.between(7, 9) | hour.between(17, 19)
    ).astype("int8")
    safe_capacity = featured["capacity"].replace(0, np.nan)
    featured["availability_fraction"] = (
        featured["available_bikes"] / safe_capacity
    ).astype("float32")
    featured["return_space_fraction"] = (
        featured["available_return_bikes"] / safe_capacity
    ).astype("float32")

    featured = add_lag_features(
        featured,
        horizons_minutes=tuple(config["lag_minutes"]),
        tolerance_minutes=config["target_tolerance_minutes"],
    )
    for minutes in config["lag_minutes"]:
        featured[f"available_bikes_delta_{minutes}m"] = (
            featured["available_bikes"]
            - featured[f"available_bikes_lag_{minutes}m"]
        )
    featured = add_rolling_features(
        featured,
        windows_minutes=tuple(config["rolling_windows_minutes"]),
    )
    featured = add_future_targets(
        featured,
        horizons_minutes=tuple(config["horizons_minutes"]),
        tolerance_minutes=config["target_tolerance_minutes"],
    )
    return featured


def assign_splits(
    data: pd.DataFrame,
    boundaries: dict[str, pd.Timestamp],
) -> pd.Series:
    """Assign current observations to the fixed 18/5/5-day split."""
    if data["snapshot_time"].min() < boundaries["window_start"]:
        raise ValueError("Rows occur before the configured Track B window.")
    if data["snapshot_time"].max() >= boundaries["test_end"]:
        raise ValueError("Rows occur at or after the exclusive Track B end.")
    split = pd.Series("test", index=data.index, dtype="string")
    split.loc[data["snapshot_time"].lt(boundaries["validation_end"])] = "validation"
    split.loc[data["snapshot_time"].lt(boundaries["train_end"])] = "train"
    return split.astype("category")


def eligible_mask(
    featured: pd.DataFrame,
    split: pd.Series,
    split_name: str,
    horizon_minutes: int,
    boundaries: dict[str, pd.Timestamp],
    columns: list[str],
    complete_features: pd.Series | None = None,
    target_time: pd.Series | None = None,
) -> pd.Series:
    """Return a complete-case scope whose labels stay inside its time block."""
    target = f"target_available_bikes_{horizon_minutes}m"
    actual_minutes = f"target_{horizon_minutes}m_actual_minutes"
    if target_time is None:
        target_time = featured["snapshot_time"] + pd.to_timedelta(
            featured[actual_minutes], unit="m"
        )
    end_by_split = {
        "train": boundaries["train_end"],
        "validation": boundaries["validation_end"],
        "test": boundaries["test_end"],
    }
    if complete_features is None:
        complete_features = featured[columns].notna().all(axis=1)
    return (
        split.eq(split_name)
        & featured["is_active"]
        & featured[target].notna()
        & target_time.lt(end_by_split[split_name])
        & complete_features
    )


def sample_by_snapshot_stride(
    data: pd.DataFrame,
    mask: pd.Series,
    stride: int,
) -> pd.Series:
    """Sample full station cross-sections at a deterministic time cadence."""
    times = data.loc[mask, "snapshot_time"].drop_duplicates().sort_values()
    selected = set(times.iloc[::stride])
    return mask & data["snapshot_time"].isin(selected)


def build_model(candidate: dict[str, Any], random_state: int) -> object:
    model_type = candidate["model_type"]
    if model_type == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(
            learning_rate=float(candidate["learning_rate"]),
            max_iter=int(candidate["max_iter"]),
            max_leaf_nodes=int(candidate["max_leaf_nodes"]),
            min_samples_leaf=int(candidate["min_samples_leaf"]),
            l2_regularization=float(candidate["l2_regularization"]),
            loss="squared_error",
            random_state=random_state,
        )
    raise ValueError(f"Unsupported Track B model type: {model_type}")


def capacity_clip(prediction: np.ndarray, capacity: pd.Series) -> np.ndarray:
    values = np.asarray(prediction, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Track B model produced non-finite predictions.")
    return np.minimum(np.maximum(values, 0), capacity.to_numpy(dtype=float))


def regression_metrics(actual: pd.Series, prediction: np.ndarray) -> dict[str, float]:
    actual_values = actual.to_numpy(dtype=float)
    prediction_values = np.asarray(prediction, dtype=float)
    error = prediction_values - actual_values
    squared = np.square(error)
    denominator = np.square(actual_values - actual_values.mean()).sum()
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(squared.mean())),
        "r2": float(1 - squared.sum() / denominator) if denominator > 0 else np.nan,
        "mean_error_prediction_minus_actual": float(error.mean()),
    }


def select_best_candidate(tuning: pd.DataFrame) -> str:
    if tuning.empty:
        raise ValueError("Track B tuning results are empty.")
    ordered = tuning.sort_values(["mae", "candidate"], kind="stable")
    return str(ordered.iloc[0]["candidate"])


def split_summary(data: pd.DataFrame, split: pd.Series) -> pd.DataFrame:
    frame = data[["snapshot_time", "station_id"]].copy()
    frame["split"] = split
    return (
        frame.groupby("split", observed=True)
        .agg(
            rows=("station_id", "size"),
            snapshots=("snapshot_time", "nunique"),
            stations=("station_id", "nunique"),
            first_snapshot=("snapshot_time", "min"),
            latest_snapshot=("snapshot_time", "max"),
        )
        .reindex(["train", "validation", "test"])
        .reset_index()
    )


def feature_coverage(
    featured: pd.DataFrame,
    split: pd.Series,
    columns: list[str],
) -> pd.DataFrame:
    rows = []
    for split_name in ("train", "validation", "test"):
        mask = split.eq(split_name)
        denominator = int(mask.sum())
        for column in columns:
            usable = int(featured.loc[mask, column].notna().sum())
            rows.append(
                {
                    "split": split_name,
                    "feature": column,
                    "rows": denominator,
                    "non_null_rows": usable,
                    "coverage_percent": 100 * usable / denominator,
                }
            )
    return pd.DataFrame(rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    boundaries = split_boundaries(config)
    data = load_track_b_model_data(args.input)
    featured = build_track_b_features(data, config)
    split = assign_splits(featured, boundaries)
    columns = feature_columns(config)
    complete_features = featured[columns].notna().all(axis=1)
    stride = int(config["training_snapshot_stride"])
    random_state = int(config["random_state"])

    args.results_dir.mkdir(parents=True, exist_ok=True)
    args.models_dir.mkdir(parents=True, exist_ok=True)
    split_summary(featured, split).to_csv(
        args.results_dir / "track_b_28d_split_summary.csv", index=False
    )
    feature_coverage(featured, split, columns).to_csv(
        args.results_dir / "track_b_28d_feature_coverage.csv", index=False
    )

    tuning_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    station_error_frames: list[pd.DataFrame] = []
    hour_error_frames: list[pd.DataFrame] = []
    selected_models: dict[str, str] = {}
    artifact_metadata: dict[str, object] = {}

    for horizon in config["horizons_minutes"]:
        target = f"target_available_bikes_{horizon}m"
        actual_minutes = f"target_{horizon}m_actual_minutes"
        target_time = featured["snapshot_time"] + pd.to_timedelta(
            featured[actual_minutes], unit="m"
        )
        masks = {
            name: eligible_mask(
                featured,
                split,
                name,
                horizon,
                boundaries,
                columns,
                complete_features,
                target_time,
            )
            for name in ("train", "validation", "test")
        }
        sampled_train = sample_by_snapshot_stride(featured, masks["train"], stride)
        if not sampled_train.any() or not masks["validation"].any() or not masks["test"].any():
            raise ValueError(f"Horizon {horizon} has an empty modeling split.")

        validation_actual = featured.loc[masks["validation"], target]
        validation_capacity = featured.loc[masks["validation"], "capacity"]
        horizon_tuning = []
        for candidate in config["candidates"]:
            model = build_model(candidate, random_state)
            model.fit(
                featured.loc[sampled_train, columns],
                featured.loc[sampled_train, target],
            )
            prediction = capacity_clip(
                model.predict(featured.loc[masks["validation"], columns]),
                validation_capacity,
            )
            row = {
                "horizon_minutes": int(horizon),
                "candidate": candidate["name"],
                "model_type": candidate["model_type"],
                "training_rows": int(sampled_train.sum()),
                "validation_rows": int(masks["validation"].sum()),
                **regression_metrics(validation_actual, prediction),
            }
            tuning_rows.append(row)
            horizon_tuning.append(row)

        tuning = pd.DataFrame(horizon_tuning)
        best_name = select_best_candidate(tuning)
        selected_models[f"{horizon}m"] = best_name
        best_candidate = next(
            candidate for candidate in config["candidates"] if candidate["name"] == best_name
        )

        for split_name in ("validation", "test"):
            scope = masks[split_name]
            actual = featured.loc[scope, target]
            persistence = featured.loc[scope, "available_bikes"].to_numpy(dtype=float)
            metric_rows.append(
                {
                    "horizon_minutes": int(horizon),
                    "split": split_name,
                    "model": "current_availability_persistence",
                    "rows": int(scope.sum()),
                    **regression_metrics(actual, persistence),
                }
            )

        train_validation = masks["train"] | masks["validation"]
        sampled_train_validation = sample_by_snapshot_stride(
            featured, train_validation, stride
        )
        final_model = build_model(best_candidate, random_state)
        final_model.fit(
            featured.loc[sampled_train_validation, columns],
            featured.loc[sampled_train_validation, target],
        )
        test_scope = masks["test"]
        test_actual = featured.loc[test_scope, target]
        test_prediction = capacity_clip(
            final_model.predict(featured.loc[test_scope, columns]),
            featured.loc[test_scope, "capacity"],
        )
        test_metrics = regression_metrics(test_actual, test_prediction)
        validation_selected = tuning.loc[tuning["candidate"].eq(best_name)].iloc[0]
        metric_rows.append(
            {
                "horizon_minutes": int(horizon),
                "split": "validation",
                "model": best_name,
                "rows": int(masks["validation"].sum()),
                **{
                    key: float(validation_selected[key])
                    for key in (
                        "mae",
                        "rmse",
                        "r2",
                        "mean_error_prediction_minus_actual",
                    )
                },
            }
        )
        metric_rows.append(
            {
                "horizon_minutes": int(horizon),
                "split": "test",
                "model": best_name,
                "rows": int(test_scope.sum()),
                **test_metrics,
            }
        )

        test_frame = featured.loc[
            test_scope, ["snapshot_time", "station_id", "available_bikes"]
        ].copy()
        test_frame["actual"] = test_actual.to_numpy(dtype=float)
        test_frame["prediction"] = test_prediction
        test_frame["absolute_error"] = np.abs(
            test_frame["prediction"] - test_frame["actual"]
        )
        test_frame["persistence_absolute_error"] = np.abs(
            test_frame["available_bikes"] - test_frame["actual"]
        )
        test_frame["local_hour"] = (
            test_frame["snapshot_time"].dt.tz_convert(TAIPEI_TIMEZONE).dt.hour
        )
        station_errors = (
            test_frame.groupby("station_id", observed=True)
            .agg(
                rows=("actual", "size"),
                mean_actual=("actual", "mean"),
                mean_prediction=("prediction", "mean"),
                learned_mae=("absolute_error", "mean"),
                persistence_mae=("persistence_absolute_error", "mean"),
            )
            .reset_index()
        )
        station_errors["learned_minus_persistence_mae"] = (
            station_errors["learned_mae"] - station_errors["persistence_mae"]
        )
        station_errors["learned_improvement_percent"] = np.where(
            station_errors["persistence_mae"].gt(0),
            100
            * (
                station_errors["persistence_mae"] - station_errors["learned_mae"]
            )
            / station_errors["persistence_mae"],
            np.nan,
        )
        station_errors.insert(0, "horizon_minutes", int(horizon))
        station_error_frames.append(station_errors)
        hour_errors = (
            test_frame.groupby("local_hour", observed=True)
            .agg(
                rows=("actual", "size"),
                mean_actual=("actual", "mean"),
                mean_prediction=("prediction", "mean"),
                learned_mae=("absolute_error", "mean"),
                persistence_mae=("persistence_absolute_error", "mean"),
            )
            .reset_index()
        )
        hour_errors["learned_minus_persistence_mae"] = (
            hour_errors["learned_mae"] - hour_errors["persistence_mae"]
        )
        hour_errors["learned_improvement_percent"] = np.where(
            hour_errors["persistence_mae"].gt(0),
            100
            * (hour_errors["persistence_mae"] - hour_errors["learned_mae"])
            / hour_errors["persistence_mae"],
            np.nan,
        )
        hour_errors.insert(0, "horizon_minutes", int(horizon))
        hour_error_frames.append(hour_errors)

        artifact = args.models_dir / f"track_b_{horizon}m_regression.joblib"
        joblib.dump(final_model, artifact)
        metadata = {
            "format_version": 1,
            "model_name": best_name,
            "artifact_filename": artifact.name,
            "artifact_sha256": file_sha256(artifact),
            "target": target,
            "target_scope": "future station available bikes",
            "horizon_minutes": int(horizon),
            "feature_columns": columns,
            "calendar_timezone": TAIPEI_TIMEZONE,
            "storage_timezone": "UTC",
            "capacity_clipping": True,
            "training_snapshot_stride": stride,
            "trained_through": boundaries["validation_end"].isoformat(),
            "test_start": boundaries["validation_end"].isoformat(),
            "test_end_exclusive": boundaries["test_end"].isoformat(),
            "test_metrics": test_metrics,
            "candidate": best_candidate,
            "library_versions": {
                "scikit_learn": sklearn.__version__,
                "pandas": pd.__version__,
                "numpy": np.__version__,
            },
        }
        artifact.with_suffix(".metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        artifact_metadata[f"{horizon}m"] = metadata

    tuning = pd.DataFrame(tuning_rows)
    metrics = pd.DataFrame(metric_rows)
    tuning.to_csv(args.results_dir / "track_b_28d_model_tuning.csv", index=False)
    metrics.to_csv(args.results_dir / "track_b_28d_model_metrics.csv", index=False)
    pd.concat(station_error_frames, ignore_index=True).to_csv(
        args.results_dir / "track_b_28d_station_errors.csv", index=False
    )
    pd.concat(hour_error_frames, ignore_index=True).to_csv(
        args.results_dir / "track_b_28d_hour_errors.csv", index=False
    )
    summary = {
        "status": "track_b_28_day_first_learned_regression",
        "analysis_window": "[window_start, test_end)",
        "boundaries_utc": {
            name: value.isoformat() for name, value in boundaries.items()
        },
        "split_days": {"train": 18, "validation": 5, "test": 5},
        "selection_rule": "Lowest validation MAE independently for each horizon.",
        "comparison_rule": "Learned model and persistence use identical complete-case rows.",
        "selected_models": selected_models,
        "artifacts": artifact_metadata,
        "limitations": [
            "Targets are future station inventory, not rental demand.",
            "Snapshot changes may include rentals, returns, rebalancing, and corrections.",
            "This stage does not define shortage/full-station risk or optimization.",
        ],
    }
    (args.results_dir / "track_b_28d_training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Track B model metrics")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
