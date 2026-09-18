"""Evaluate frozen Track B models on a pre-registered future time window."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    from .train_track_b_regression import (
        TAIPEI_TIMEZONE,
        build_track_b_features,
        capacity_clip,
        feature_columns,
        file_sha256,
        load_config,
        load_track_b_model_data,
        regression_metrics,
    )
except ImportError:
    from train_track_b_regression import (
        TAIPEI_TIMEZONE,
        build_track_b_features,
        capacity_clip,
        feature_columns,
        file_sha256,
        load_config,
        load_track_b_model_data,
        regression_metrics,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/track_b_independent_7d.csv"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/track_b_temporal_validation.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify the freeze manifest and model artifacts without evaluation data.",
    )
    return parser.parse_args()


def parse_utc(value: str, field: str) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include an explicit timezone.")
    return parsed.tz_convert("UTC")


def load_validation_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "format_version",
        "status",
        "history_start",
        "evaluation_start",
        "evaluation_end_exclusive",
        "expected_interval_minutes",
        "gap_threshold_minutes",
        "minimum_snapshot_coverage_percent",
        "minimum_usable_target_coverage_percent",
        "minimum_station_improvement_percent",
        "minimum_mae_improvement_percent",
        "minimum_rmse_improvement_percent",
        "training_config_path",
        "training_config_sha256",
        "models",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(
            "Temporal validation config is missing: " + ", ".join(sorted(missing))
        )
    if config["format_version"] != 1:
        raise ValueError("Unsupported temporal validation config format.")
    if config["status"] != "pre_registered_before_independent_export":
        raise ValueError("Temporal validation config is not marked pre-registered.")
    if not config["models"]:
        raise ValueError("At least one frozen model is required.")
    for field in (
        "expected_interval_minutes",
        "gap_threshold_minutes",
        "minimum_snapshot_coverage_percent",
        "minimum_usable_target_coverage_percent",
        "minimum_station_improvement_percent",
    ):
        if float(config[field]) <= 0:
            raise ValueError(f"{field} must be positive.")
    return config


def validation_window(
    config: dict[str, Any],
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    history_start = parse_utc(config["history_start"], "history_start")
    start = parse_utc(config["evaluation_start"], "evaluation_start")
    end = parse_utc(config["evaluation_end_exclusive"], "evaluation_end_exclusive")
    if not history_start < start < end:
        raise ValueError("Temporal validation boundaries must be strictly ordered.")
    if end - start != pd.Timedelta(days=7):
        raise ValueError("Independent temporal validation must cover exactly seven days.")
    return history_start, start, end


def resolve_frozen_inputs(
    config_path: Path,
    config: dict[str, Any],
) -> tuple[Path, list[dict[str, Any]]]:
    repository_root = config_path.resolve().parent.parent
    training_config_path = repository_root / config["training_config_path"]
    if file_sha256(training_config_path) != config["training_config_sha256"]:
        raise ValueError("Frozen Track B training config checksum does not match.")
    return repository_root, config["models"]


def load_frozen_model(
    repository_root: Path,
    specification: dict[str, Any],
    expected_features: list[str],
) -> tuple[object, dict[str, Any]]:
    required = {
        "horizon_minutes",
        "artifact_path",
        "artifact_sha256",
        "metadata_path",
        "metadata_sha256",
        "stage_17_holdout",
    }
    missing = required - set(specification)
    if missing:
        raise ValueError("Frozen model specification is missing: " + ", ".join(sorted(missing)))
    artifact_path = repository_root / specification["artifact_path"]
    metadata_path = repository_root / specification["metadata_path"]
    if file_sha256(metadata_path) != specification["metadata_sha256"]:
        raise ValueError("Frozen model metadata checksum does not match.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if file_sha256(artifact_path) != specification["artifact_sha256"]:
        raise ValueError("Frozen model artifact checksum does not match.")
    if metadata.get("artifact_sha256") != specification["artifact_sha256"]:
        raise ValueError("Model metadata and freeze manifest disagree on artifact checksum.")
    horizon = int(specification["horizon_minutes"])
    if metadata.get("horizon_minutes") != horizon:
        raise ValueError("Model metadata and freeze manifest disagree on horizon.")
    if metadata.get("target") != f"target_available_bikes_{horizon}m":
        raise ValueError("Frozen model target is incompatible with its horizon.")
    if metadata.get("feature_columns") != expected_features:
        raise ValueError("Frozen model feature schema does not match the training config.")
    model = joblib.load(artifact_path)
    if not callable(getattr(model, "predict", None)):
        raise ValueError("Frozen model does not provide predict().")
    model_features = list(getattr(model, "feature_names_in_", expected_features))
    if model_features != expected_features:
        raise ValueError("Frozen model feature names do not match metadata.")
    return model, metadata


def validate_input_bounds(
    data: pd.DataFrame,
    history_start: pd.Timestamp,
    evaluation_start: pd.Timestamp,
    evaluation_end: pd.Timestamp,
    maximum_history_minutes: int,
    expected_interval_minutes: int,
) -> None:
    if evaluation_start - history_start < pd.Timedelta(minutes=maximum_history_minutes):
        raise ValueError("Input history does not cover the longest frozen feature window.")
    if data["snapshot_time"].min() < history_start:
        raise ValueError("Independent export contains rows before history_start.")
    if data["snapshot_time"].max() >= evaluation_end:
        raise ValueError("Independent export contains rows at or after the exclusive end.")
    allowed_edge_delay = pd.Timedelta(minutes=expected_interval_minutes + 2)
    if data["snapshot_time"].min() > history_start + allowed_edge_delay:
        raise ValueError("Independent export is missing the required history boundary.")
    if data["snapshot_time"].max() < evaluation_end - allowed_edge_delay:
        raise ValueError("Independent export ends too early for the fixed window.")


def schedule_summary(
    data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    expected_interval_minutes: int,
    gap_threshold_minutes: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    times = pd.Series(
        data.loc[
            data["snapshot_time"].ge(start) & data["snapshot_time"].lt(end),
            "snapshot_time",
        ]
        .drop_duplicates()
        .sort_values()
        .to_numpy()
    )
    if times.empty:
        raise ValueError("Independent evaluation window contains no snapshots.")
    gaps = times.diff().dt.total_seconds().div(60)
    gap_rows = pd.DataFrame(
        {
            "previous_snapshot_time": times.shift(),
            "snapshot_time": times,
            "gap_minutes": gaps,
        }
    )
    gap_rows = gap_rows.loc[gap_rows["gap_minutes"].gt(gap_threshold_minutes)].copy()
    gap_rows["estimated_missing_slots"] = (
        (gap_rows["gap_minutes"] / expected_interval_minutes).round().astype(int) - 1
    ).clip(lower=0)
    expected_snapshots = int((end - start) / pd.Timedelta(minutes=expected_interval_minutes))
    snapshot_count = int(len(times))
    summary = {
        "expected_snapshots": expected_snapshots,
        "observed_snapshots": snapshot_count,
        "snapshot_coverage_percent": 100 * snapshot_count / expected_snapshots,
        "first_snapshot_utc": times.iloc[0].isoformat(),
        "latest_snapshot_utc": times.iloc[-1].isoformat(),
        "gaps_over_threshold": int(len(gap_rows)),
        "estimated_missing_slots": int(gap_rows["estimated_missing_slots"].sum()),
        "max_gap_minutes": float(gaps.max()) if gaps.notna().any() else 0.0,
        "duplicate_station_snapshot_rows": int(
            data.duplicated(["station_id", "snapshot_time"]).sum()
        ),
    }
    return summary, gap_rows.reset_index(drop=True)


def independent_scope(
    featured: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    horizon_minutes: int,
    columns: list[str],
) -> tuple[pd.Series, dict[str, float | int]]:
    target = f"target_available_bikes_{horizon_minutes}m"
    actual_minutes = f"target_{horizon_minutes}m_actual_minutes"
    in_window = featured["snapshot_time"].ge(start) & featured["snapshot_time"].lt(end)
    active = in_window & featured["is_active"]
    complete_features = featured[columns].notna().all(axis=1)
    target_time = featured["snapshot_time"] + pd.to_timedelta(
        featured[actual_minutes], unit="m"
    )
    valid_target = featured[target].notna() & target_time.lt(end)
    scope = active & complete_features & valid_target
    active_rows = int(active.sum())
    coverage = {
        "horizon_minutes": int(horizon_minutes),
        "active_current_rows": active_rows,
        "complete_feature_rows": int((active & complete_features).sum()),
        "usable_rows": int(scope.sum()),
        "complete_feature_coverage_percent": (
            100 * int((active & complete_features).sum()) / active_rows
            if active_rows
            else 0.0
        ),
        "usable_target_coverage_percent": (
            100 * int(scope.sum()) / active_rows if active_rows else 0.0
        ),
    }
    return scope, coverage


def error_summaries(
    frame: pd.DataFrame,
    horizon_minutes: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    station = (
        frame.groupby("station_id", observed=True)
        .agg(
            rows=("actual", "size"),
            mean_actual=("actual", "mean"),
            mean_prediction=("prediction", "mean"),
            learned_mae=("absolute_error", "mean"),
            persistence_mae=("persistence_absolute_error", "mean"),
        )
        .reset_index()
    )
    station["learned_minus_persistence_mae"] = (
        station["learned_mae"] - station["persistence_mae"]
    )
    station["learned_improvement_percent"] = np.where(
        station["persistence_mae"].gt(0),
        100
        * (station["persistence_mae"] - station["learned_mae"])
        / station["persistence_mae"],
        np.nan,
    )
    station.insert(0, "horizon_minutes", horizon_minutes)

    hour = (
        frame.groupby("local_hour", observed=True)
        .agg(
            rows=("actual", "size"),
            mean_actual=("actual", "mean"),
            mean_prediction=("prediction", "mean"),
            learned_mae=("absolute_error", "mean"),
            persistence_mae=("persistence_absolute_error", "mean"),
        )
        .reset_index()
    )
    hour["learned_minus_persistence_mae"] = hour["learned_mae"] - hour["persistence_mae"]
    hour["learned_improvement_percent"] = np.where(
        hour["persistence_mae"].gt(0),
        100 * (hour["persistence_mae"] - hour["learned_mae"]) / hour["persistence_mae"],
        np.nan,
    )
    hour.insert(0, "horizon_minutes", horizon_minutes)
    return station, hour


def decision_from_evidence(
    data_quality_passed: bool,
    learned_metrics: dict[str, float],
    persistence_metrics: dict[str, float],
    stations_improved_percent: float,
    config: dict[str, Any],
) -> dict[str, Any]:
    mae_improvement = 100 * (
        persistence_metrics["mae"] - learned_metrics["mae"]
    ) / persistence_metrics["mae"]
    rmse_improvement = 100 * (
        persistence_metrics["rmse"] - learned_metrics["rmse"]
    ) / persistence_metrics["rmse"]
    gates = {
        "data_quality_passed": bool(data_quality_passed),
        "mae_improvement_passed": bool(
            mae_improvement > float(config["minimum_mae_improvement_percent"])
        ),
        "rmse_improvement_passed": bool(
            rmse_improvement > float(config["minimum_rmse_improvement_percent"])
        ),
        "station_majority_passed": bool(
            stations_improved_percent
            >= float(config["minimum_station_improvement_percent"])
        ),
    }
    if not gates["data_quality_passed"]:
        status = "data_quality_gate_failed"
    elif not gates["mae_improvement_passed"]:
        status = "persistence_remains_primary_baseline"
    elif all(gates.values()):
        status = "frozen_learned_model_passes_temporal_gate"
    else:
        status = "mixed_evidence_no_promotion"
    return {
        "status": status,
        "mae_improvement_percent": mae_improvement,
        "rmse_improvement_percent": rmse_improvement,
        "stations_improved_percent": stations_improved_percent,
        "gates": gates,
    }


def combine_with_stage_17(
    independent_decision: dict[str, Any],
    stage_17_holdout: dict[str, Any],
) -> str:
    """Require primary-MAE support in both frozen evaluation windows."""
    if independent_decision["status"] == "data_quality_gate_failed":
        return "independent_data_quality_failed_no_model_decision"
    stage_17_passed = bool(stage_17_holdout.get("primary_mae_gate_passed"))
    independent_passed = (
        independent_decision["status"]
        == "frozen_learned_model_passes_temporal_gate"
    )
    if stage_17_passed and independent_passed:
        return "learned_model_confirmed_across_both_windows"
    if not stage_17_passed and independent_passed:
        return "mixed_across_windows_keep_persistence_baseline"
    if stage_17_passed:
        return "independent_window_did_not_confirm_learned_model"
    return "persistence_baseline_supported_across_current_evidence"


def main() -> None:
    args = parse_args()
    validation_config = load_validation_config(args.config)
    history_start, evaluation_start, evaluation_end = validation_window(validation_config)
    repository_root, specifications = resolve_frozen_inputs(args.config, validation_config)
    training_config_path = repository_root / validation_config["training_config_path"]
    training_config = load_config(training_config_path)
    columns = feature_columns(training_config)
    configured_horizons = sorted(int(value) for value in training_config["horizons_minutes"])
    frozen_horizons = sorted(int(value["horizon_minutes"]) for value in specifications)
    if frozen_horizons != configured_horizons:
        raise ValueError("Freeze manifest horizons do not match the training config.")

    frozen_models: dict[int, tuple[object, dict[str, Any]]] = {}
    for specification in specifications:
        horizon = int(specification["horizon_minutes"])
        model, metadata = load_frozen_model(repository_root, specification, columns)
        metadata_end = parse_utc(
            metadata["test_end_exclusive"],
            "model test_end_exclusive",
        )
        if evaluation_start < metadata_end:
            raise ValueError("Independent evaluation window overlaps model evaluation history.")
        frozen_models[horizon] = (model, metadata)
    if args.check_only:
        print(
            "Freeze manifest verified for horizons: "
            + ", ".join(f"{horizon}m" for horizon in sorted(frozen_models))
        )
        return

    data = load_track_b_model_data(args.input)
    maximum_history = max(
        [*training_config["lag_minutes"], *training_config["rolling_windows_minutes"]]
    )
    validate_input_bounds(
        data,
        history_start,
        evaluation_start,
        evaluation_end,
        maximum_history,
        int(validation_config["expected_interval_minutes"]),
    )
    featured = build_track_b_features(data, training_config)
    schedule, gaps = schedule_summary(
        data,
        evaluation_start,
        evaluation_end,
        int(validation_config["expected_interval_minutes"]),
        float(validation_config["gap_threshold_minutes"]),
    )
    schedule_gate = (
        schedule["snapshot_coverage_percent"]
        >= float(validation_config["minimum_snapshot_coverage_percent"])
        and schedule["duplicate_station_snapshot_rows"] == 0
    )

    metric_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    station_frames: list[pd.DataFrame] = []
    hour_frames: list[pd.DataFrame] = []
    decisions: dict[str, Any] = {}
    model_evidence: dict[str, Any] = {}

    for specification in specifications:
        horizon = int(specification["horizon_minutes"])
        model, metadata = frozen_models[horizon]
        scope, coverage = independent_scope(
            featured, evaluation_start, evaluation_end, horizon, columns
        )
        if not scope.any():
            raise ValueError(f"No eligible independent rows for the {horizon}-minute model.")
        coverage_rows.append(coverage)
        target = f"target_available_bikes_{horizon}m"
        actual = featured.loc[scope, target]
        persistence = featured.loc[scope, "available_bikes"].to_numpy(dtype=float)
        learned = capacity_clip(
            model.predict(featured.loc[scope, columns]),
            featured.loc[scope, "capacity"],
        )
        persistence_result = regression_metrics(actual, persistence)
        learned_result = regression_metrics(actual, learned)
        for name, metrics in (
            ("current_availability_persistence", persistence_result),
            (metadata["model_name"], learned_result),
        ):
            metric_rows.append(
                {
                    "horizon_minutes": horizon,
                    "model": name,
                    "rows": int(scope.sum()),
                    **metrics,
                }
            )

        error_frame = featured.loc[
            scope, ["snapshot_time", "station_id", "available_bikes"]
        ].copy()
        error_frame["actual"] = actual.to_numpy(dtype=float)
        error_frame["prediction"] = learned
        error_frame["absolute_error"] = np.abs(learned - error_frame["actual"])
        error_frame["persistence_absolute_error"] = np.abs(
            error_frame["available_bikes"] - error_frame["actual"]
        )
        error_frame["local_hour"] = (
            error_frame["snapshot_time"].dt.tz_convert(TAIPEI_TIMEZONE).dt.hour
        )
        station, hour = error_summaries(error_frame, horizon)
        station_frames.append(station)
        hour_frames.append(hour)
        stations_improved_percent = 100 * float(
            station["learned_mae"].lt(station["persistence_mae"]).mean()
        )
        target_gate = (
            coverage["usable_target_coverage_percent"]
            >= float(validation_config["minimum_usable_target_coverage_percent"])
        )
        independent_decision = decision_from_evidence(
            schedule_gate and target_gate,
            learned_result,
            persistence_result,
            stations_improved_percent,
            validation_config,
        )
        independent_decision["combined_with_stage_17"] = combine_with_stage_17(
            independent_decision, specification["stage_17_holdout"]
        )
        decisions[f"{horizon}m"] = independent_decision
        model_evidence[f"{horizon}m"] = {
            "artifact_sha256": specification["artifact_sha256"],
            "metadata_sha256": specification["metadata_sha256"],
            "stage_17_holdout": specification["stage_17_holdout"],
        }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame(metric_rows)
    coverage = pd.DataFrame(coverage_rows)
    metrics.to_csv(args.output_dir / "track_b_independent_metrics.csv", index=False)
    coverage.to_csv(args.output_dir / "track_b_independent_coverage.csv", index=False)
    pd.concat(station_frames, ignore_index=True).to_csv(
        args.output_dir / "track_b_independent_station_errors.csv", index=False
    )
    pd.concat(hour_frames, ignore_index=True).to_csv(
        args.output_dir / "track_b_independent_hour_errors.csv", index=False
    )
    gaps.to_csv(args.output_dir / "track_b_independent_gaps.csv", index=False)
    summary = {
        "status": "independent_temporal_validation_complete",
        "window_utc": {
            "history_start": history_start.isoformat(),
            "evaluation_start": evaluation_start.isoformat(),
            "evaluation_end_exclusive": evaluation_end.isoformat(),
        },
        "schedule": schedule,
        "coverage": coverage.to_dict(orient="records"),
        "pre_registered_thresholds": {
            key: validation_config[key]
            for key in (
                "minimum_snapshot_coverage_percent",
                "minimum_usable_target_coverage_percent",
                "minimum_station_improvement_percent",
                "minimum_mae_improvement_percent",
                "minimum_rmse_improvement_percent",
            )
        },
        "frozen_models": model_evidence,
        "decisions": decisions,
        "limitations": [
            "This is a fixed independent temporal evaluation, not model retraining.",
            "Future inventory is not rental demand and does not define shortage risk.",
            "A passing temporal gate is not a production deployment guarantee.",
        ],
    }
    (args.output_dir / "track_b_independent_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Track B independent temporal metrics")
    print(metrics.to_string(index=False))
    print("\nPre-registered decisions")
    print(json.dumps(decisions, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
