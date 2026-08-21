"""Tune and evaluate XGBoost on the established Track A experiment scope."""

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
import xgboost
from sklearn.inspection import permutation_importance

try:
    from .baseline_model import (
        build_hourly_model_dataset,
        evaluate_predictions,
        load_hourly_weather,
        load_model_config,
        load_station_hour_demand,
        select_top_training_stations,
        split_by_time,
    )
    from .tree_model import build_rolling_origin_splits, load_tree_config
    from .xgboost_model import (
        build_xgboost_pipeline,
        load_xgboost_config,
        xgboost_feature_columns,
    )
except ImportError:
    from baseline_model import (
        build_hourly_model_dataset,
        evaluate_predictions,
        load_hourly_weather,
        load_model_config,
        load_station_hour_demand,
        select_top_training_stations,
        split_by_time,
    )
    from tree_model import build_rolling_origin_splits, load_tree_config
    from xgboost_model import (
        build_xgboost_pipeline,
        load_xgboost_config,
        xgboost_feature_columns,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-config", type=Path, default=Path("config/baseline_model.json")
    )
    parser.add_argument(
        "--tree-config", type=Path, default=Path("config/tree_model.json")
    )
    parser.add_argument(
        "--xgboost-config", type=Path, default=Path("config/xgboost_model.json")
    )
    parser.add_argument(
        "--demand-input",
        type=Path,
        default=Path("data/processed/historical_station_hour_demand.csv"),
    )
    parser.add_argument(
        "--weather-input",
        type=Path,
        default=Path("data/processed/taipei_weather_hourly.csv"),
    )
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    return parser.parse_args()


def local_timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("Asia/Taipei")


def file_sha256(source_path: Path) -> str:
    digest = hashlib.sha256()
    with source_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tune_xgboost(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    target: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, object]], np.ndarray]:
    """Choose a bounded candidate using validation MAE only."""
    columns = xgboost_feature_columns(True)
    best_candidate: dict[str, Any] | None = None
    best_prediction: np.ndarray | None = None
    best_mae = float("inf")
    rows: list[dict[str, object]] = []
    for candidate in config["candidates"]:
        model = build_xgboost_pipeline(candidate, config, include_weather=True)
        model.fit(training[columns], training[target])
        prediction = np.maximum(model.predict(validation[columns]), 0)
        metrics = evaluate_predictions(validation[target], prediction)
        rows.append({**candidate, "rows": len(validation), **metrics})
        if metrics["mae"] < best_mae:
            best_mae = metrics["mae"]
            best_candidate = candidate
            best_prediction = prediction
    assert best_candidate is not None and best_prediction is not None
    return best_candidate, rows, best_prediction


def metric_row(
    model: str,
    split: str,
    actual: pd.Series,
    prediction: np.ndarray,
    candidate: str,
) -> dict[str, object]:
    return {
        "model": model,
        "split": split,
        "candidate": candidate,
        "rows": len(actual),
        **evaluate_predictions(actual, prediction),
    }


def main() -> None:
    args = parse_args()
    baseline_config = load_model_config(args.baseline_config)
    tree_config = load_tree_config(args.tree_config)
    xgb_config = load_xgboost_config(args.xgboost_config)
    train_end = local_timestamp(baseline_config["train_end"])
    validation_end = local_timestamp(baseline_config["validation_end"])
    test_end = local_timestamp(baseline_config["test_end"])
    target = baseline_config.get("target", "borrow_count")

    demand = load_station_hour_demand(args.demand_input)
    weather = load_hourly_weather(args.weather_input)
    stations = select_top_training_stations(
        demand, train_end, baseline_config["top_station_count"]
    )
    model_data = build_hourly_model_dataset(demand, weather, stations)
    splits = split_by_time(model_data, train_end, validation_end, test_end)
    columns = xgboost_feature_columns(True)

    best_candidate, tuning_rows, validation_prediction = tune_xgboost(
        splits["train"], splits["validation"], target, xgb_config
    )
    model_name = xgb_config["model_name"]
    metric_rows = [
        metric_row(
            model_name,
            "validation",
            splits["validation"][target],
            validation_prediction,
            best_candidate["candidate"],
        )
    ]

    train_validation = pd.concat(
        [splits["train"], splits["validation"]], ignore_index=True
    )
    final_model = build_xgboost_pipeline(
        best_candidate, xgb_config, include_weather=True
    )
    final_model.fit(train_validation[columns], train_validation[target])
    test_prediction = np.maximum(final_model.predict(splits["test"][columns]), 0)
    metric_rows.append(
        metric_row(
            model_name,
            "test",
            splits["test"][target],
            test_prediction,
            best_candidate["candidate"],
        )
    )

    rolling_rows: list[dict[str, object]] = []
    for fold_name, training, validation in build_rolling_origin_splits(
        model_data, tree_config["rolling_origin_folds"]
    ):
        rolling_model = build_xgboost_pipeline(
            best_candidate, xgb_config, include_weather=True
        )
        rolling_model.fit(training[columns], training[target])
        prediction = np.maximum(rolling_model.predict(validation[columns]), 0)
        rolling_rows.append(
            {
                "fold": fold_name,
                "train_end": training["event_time"].max().isoformat(),
                "validation_start": validation["event_time"].min().isoformat(),
                "validation_end": validation["event_time"].max().isoformat(),
                "train_rows": len(training),
                "validation_rows": len(validation),
                **evaluate_predictions(validation[target], prediction),
            }
        )

    sample_size = min(xgb_config["permutation_sample_rows"], len(splits["test"]))
    sample = splits["test"].sample(
        sample_size, random_state=xgb_config["random_state"]
    )
    importance = permutation_importance(
        final_model,
        sample[columns],
        sample[target],
        scoring="neg_mean_absolute_error",
        n_repeats=xgb_config["permutation_repeats"],
        random_state=xgb_config["random_state"],
        n_jobs=1,
    )
    importance_report = pd.DataFrame(
        {
            "feature": columns,
            "mae_increase_mean": importance.importances_mean,
            "mae_increase_std": importance.importances_std,
        }
    ).sort_values("mae_increase_mean", ascending=False)

    test = splits["test"][["event_time", "station_name", target]].copy()
    test["prediction"] = test_prediction
    test["signed_error"] = test[target] - test["prediction"]
    test["absolute_error"] = test["signed_error"].abs()
    station_errors = (
        test.groupby("station_name", as_index=False)
        .agg(
            rows=("event_time", "size"),
            average_actual=(target, "mean"),
            average_prediction=("prediction", "mean"),
            mae=("absolute_error", "mean"),
        )
        .sort_values("mae", ascending=False)
    )
    test["hour"] = test["event_time"].dt.hour
    hour_errors = (
        test.groupby("hour", as_index=False)
        .agg(
            rows=("event_time", "size"),
            average_actual=(target, "mean"),
            average_prediction=("prediction", "mean"),
            mae=("absolute_error", "mean"),
        )
        .sort_values("hour")
    )
    worst_cases = test.nlargest(
        int(xgb_config.get("worst_case_rows", 100)), "absolute_error"
    )

    args.results_dir.mkdir(parents=True, exist_ok=True)
    args.models_dir.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(args.results_dir / "xgboost_metrics.csv", index=False)
    pd.DataFrame(tuning_rows).to_csv(
        args.results_dir / "xgboost_tuning.csv", index=False
    )
    pd.DataFrame(rolling_rows).to_csv(
        args.results_dir / "xgboost_rolling_origin_metrics.csv", index=False
    )
    importance_report.to_csv(
        args.results_dir / "xgboost_permutation_importance.csv", index=False
    )
    station_errors.to_csv(
        args.results_dir / "xgboost_station_errors.csv", index=False
    )
    hour_errors.to_csv(args.results_dir / "xgboost_hour_errors.csv", index=False)
    worst_cases.to_csv(args.results_dir / "xgboost_worst_cases.csv", index=False)

    comparison_path = args.results_dir / "model_comparison_metrics.csv"
    comparison = pd.read_csv(comparison_path)
    comparison = comparison.loc[~comparison["model"].eq(model_name)].copy()
    metrics["alpha"] = np.nan
    comparison = pd.concat([comparison, metrics], ignore_index=True)
    comparison.to_csv(comparison_path, index=False)

    artifact_path = args.models_dir / f"{model_name}.joblib"
    joblib.dump(final_model, artifact_path)
    test_metrics = metrics.loc[metrics["split"].eq("test")].iloc[0]
    metadata = {
        "format_version": 1,
        "model_name": model_name,
        "artifact_filename": artifact_path.name,
        "artifact_sha256": file_sha256(artifact_path),
        "target": target,
        "target_scope": "hourly transfer-related borrowing demand",
        "selected_station_count": len(stations),
        "selected_stations": stations,
        "feature_columns": columns,
        "includes_weather": True,
        "trained_through": validation_end.isoformat(),
        "test_period_start": splits["test"]["event_time"].min().isoformat(),
        "test_period_end": splits["test"]["event_time"].max().isoformat(),
        "test_metrics": {
            "mae": float(test_metrics["mae"]),
            "rmse": float(test_metrics["rmse"]),
            "r2": float(test_metrics["r2"]),
        },
        "candidate": best_candidate,
        "library_versions": {
            "xgboost": xgboost.__version__,
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    artifact_path.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"XGBoost test: MAE={test_metrics['mae']:.3f}, "
        f"RMSE={test_metrics['rmse']:.3f}, R2={test_metrics['r2']:.3f}"
    )
    print(f"Selected candidate: {best_candidate['candidate']}")
    print(f"Rolling-origin folds completed: {len(rolling_rows)}")


if __name__ == "__main__":
    main()
