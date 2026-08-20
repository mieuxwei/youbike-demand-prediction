"""Tune and evaluate histogram gradient-boosting demand models."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
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
    from .tree_model import (
        build_rolling_origin_splits,
        build_tree_pipeline,
        load_tree_config,
        tree_feature_columns,
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
    from tree_model import (
        build_rolling_origin_splits,
        build_tree_pipeline,
        load_tree_config,
        tree_feature_columns,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and evaluate hourly tree-based demand models."
    )
    parser.add_argument(
        "--baseline-config", type=Path, default=Path("config/baseline_model.json")
    )
    parser.add_argument(
        "--tree-config", type=Path, default=Path("config/tree_model.json")
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


def tune_tree(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    target: str,
    include_weather: bool,
    tree_config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, object]], np.ndarray]:
    """Select one tree candidate using validation MAE only."""
    columns = tree_feature_columns(include_weather)
    rows: list[dict[str, object]] = []
    best_candidate: dict[str, Any] | None = None
    best_prediction: np.ndarray | None = None
    best_mae = float("inf")
    for candidate in tree_config["candidates"]:
        pipeline = build_tree_pipeline(
            include_weather,
            candidate,
            loss=tree_config["loss"],
            random_state=tree_config["random_state"],
        )
        pipeline.fit(training[columns], training[target])
        prediction = np.maximum(pipeline.predict(validation[columns]), 0)
        metrics = evaluate_predictions(validation[target], prediction)
        rows.append(
            {
                "include_weather": include_weather,
                **candidate,
                **metrics,
            }
        )
        if metrics["mae"] < best_mae:
            best_mae = metrics["mae"]
            best_candidate = candidate
            best_prediction = prediction
    assert best_candidate is not None and best_prediction is not None
    return best_candidate, rows, best_prediction


def main() -> None:
    args = parse_args()
    baseline_config = load_model_config(args.baseline_config)
    tree_config = load_tree_config(args.tree_config)
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

    tuning_rows: list[dict[str, object]] = []
    tree_metric_rows: list[dict[str, object]] = []
    best_candidates: dict[str, dict[str, Any]] = {}
    final_models: dict[str, object] = {}
    test_predictions: dict[str, np.ndarray] = {}
    for model_name, include_weather in [
        ("hist_gradient_boosting", False),
        ("hist_gradient_boosting_weather", True),
    ]:
        best, tuning, validation_prediction = tune_tree(
            splits["train"],
            splits["validation"],
            target,
            include_weather,
            tree_config,
        )
        tuning_rows.extend(tuning)
        tree_metric_rows.append(
            metric_row(
                model_name,
                "validation",
                splits["validation"][target],
                validation_prediction,
                best["candidate"],
            )
        )
        train_validation = pd.concat(
            [splits["train"], splits["validation"]], ignore_index=True
        )
        pipeline = build_tree_pipeline(
            include_weather,
            best,
            loss=tree_config["loss"],
            random_state=tree_config["random_state"],
        )
        columns = tree_feature_columns(include_weather)
        pipeline.fit(train_validation[columns], train_validation[target])
        prediction = np.maximum(pipeline.predict(splits["test"][columns]), 0)
        tree_metric_rows.append(
            metric_row(
                model_name,
                "test",
                splits["test"][target],
                prediction,
                best["candidate"],
            )
        )
        best_candidates[model_name] = best
        final_models[model_name] = pipeline
        test_predictions[model_name] = prediction

    best_name = "hist_gradient_boosting_weather"
    best_model = final_models[best_name]
    best_columns = tree_feature_columns(True)
    rolling_rows: list[dict[str, object]] = []
    for fold_name, training, validation in build_rolling_origin_splits(
        model_data, tree_config["rolling_origin_folds"]
    ):
        rolling_model = build_tree_pipeline(
            True,
            best_candidates[best_name],
            loss=tree_config["loss"],
            random_state=tree_config["random_state"],
        )
        rolling_model.fit(training[best_columns], training[target])
        prediction = np.maximum(
            rolling_model.predict(validation[best_columns]), 0
        )
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

    sample_size = min(tree_config["permutation_sample_rows"], len(splits["test"]))
    sample = splits["test"].sample(
        sample_size, random_state=tree_config["random_state"]
    )
    importance = permutation_importance(
        best_model,
        sample[best_columns],
        sample[target],
        scoring="neg_mean_absolute_error",
        n_repeats=tree_config["permutation_repeats"],
        random_state=tree_config["random_state"],
        # Single-process execution is slower but works in restricted environments
        # and avoids platform-dependent worker allocation.
        n_jobs=1,
    )
    importance_report = pd.DataFrame(
        {
            "feature": best_columns,
            "mae_increase_mean": importance.importances_mean,
            "mae_increase_std": importance.importances_std,
        }
    ).sort_values("mae_increase_mean", ascending=False)

    test = splits["test"][
        ["event_time", "station_name", target]
    ].copy()
    test["prediction"] = test_predictions[best_name]
    test["absolute_error"] = (test[target] - test["prediction"]).abs()
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

    args.results_dir.mkdir(parents=True, exist_ok=True)
    args.models_dir.mkdir(parents=True, exist_ok=True)
    tree_metrics = pd.DataFrame(tree_metric_rows)
    tree_metrics.to_csv(args.results_dir / "tree_model_metrics.csv", index=False)
    pd.DataFrame(tuning_rows).to_csv(
        args.results_dir / "tree_model_tuning.csv", index=False
    )
    pd.DataFrame(rolling_rows).to_csv(
        args.results_dir / "tree_rolling_origin_metrics.csv", index=False
    )
    importance_report.to_csv(
        args.results_dir / "tree_permutation_importance.csv", index=False
    )
    station_errors.to_csv(
        args.results_dir / "tree_station_errors.csv", index=False
    )
    hour_errors.to_csv(args.results_dir / "tree_hour_errors.csv", index=False)

    baseline_metrics = pd.read_csv(args.results_dir / "baseline_metrics.csv")
    baseline_metrics["candidate"] = ""
    tree_metrics["alpha"] = np.nan
    comparison = pd.concat(
        [baseline_metrics, tree_metrics],
        ignore_index=True,
    )
    comparison.to_csv(args.results_dir / "model_comparison_metrics.csv", index=False)
    for name, pipeline in final_models.items():
        joblib.dump(pipeline, args.models_dir / f"{name}.joblib")

    best_test = tree_metrics.loc[
        tree_metrics["model"].eq(best_name) & tree_metrics["split"].eq("test")
    ].iloc[0]
    print(
        f"Weather HGB test: MAE={best_test['mae']:.3f}, "
        f"RMSE={best_test['rmse']:.3f}, R2={best_test['r2']:.3f}"
    )
    print(f"Rolling-origin folds completed: {len(rolling_rows)}")


if __name__ == "__main__":
    main()
