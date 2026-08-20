"""Train, validate, and evaluate hourly transfer-demand baselines."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:
    from .baseline_model import (
        build_hourly_model_dataset,
        build_ridge_pipeline,
        evaluate_predictions,
        feature_columns,
        load_hourly_weather,
        load_model_config,
        load_station_hour_demand,
        select_top_training_stations,
        split_by_time,
    )
except ImportError:
    from baseline_model import (
        build_hourly_model_dataset,
        build_ridge_pipeline,
        evaluate_predictions,
        feature_columns,
        load_hourly_weather,
        load_model_config,
        load_station_hour_demand,
        select_top_training_stations,
        split_by_time,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train hourly transfer-demand baselines."
    )
    parser.add_argument(
        "--config", type=Path, default=Path("config/baseline_model.json")
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


def timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("Asia/Taipei")


def add_metrics(
    rows: list[dict[str, object]],
    model_name: str,
    split_name: str,
    actual: pd.Series,
    predicted: np.ndarray | pd.Series,
    alpha: float | None = None,
) -> None:
    metrics = evaluate_predictions(actual, predicted)
    rows.append(
        {
            "model": model_name,
            "split": split_name,
            "alpha": alpha,
            "rows": len(actual),
            **metrics,
        }
    )


def main() -> None:
    args = parse_args()
    config = load_model_config(args.config)
    train_end = timestamp(config["train_end"])
    validation_end = timestamp(config["validation_end"])
    test_end = timestamp(config["test_end"])

    demand = load_station_hour_demand(args.demand_input)
    weather = load_hourly_weather(args.weather_input)
    stations = select_top_training_stations(
        demand, train_end, config["top_station_count"]
    )
    model_data = build_hourly_model_dataset(demand, weather, stations)
    splits = split_by_time(model_data, train_end, validation_end, test_end)
    target = config.get("target", "borrow_count")
    floor = float(config.get("prediction_floor", 0))

    metric_rows: list[dict[str, object]] = []
    for split_name in ["validation", "test"]:
        frame = splits[split_name]
        add_metrics(
            metric_rows,
            "persistence_1h",
            split_name,
            frame[target],
            frame["borrow_lag_1h"],
        )
        add_metrics(
            metric_rows,
            "seasonal_168h",
            split_name,
            frame[target],
            frame["borrow_lag_168h"],
        )

    tuning_rows: list[dict[str, object]] = []
    trained_models: dict[str, object] = {}
    test_predictions: dict[str, np.ndarray] = {}
    for model_name, include_weather in [
        ("ridge_time_history", False),
        ("ridge_time_history_weather", True),
    ]:
        columns = feature_columns(include_weather)
        best_alpha: float | None = None
        best_mae = float("inf")
        best_validation_prediction: np.ndarray | None = None
        for alpha in config["ridge_alphas"]:
            pipeline = build_ridge_pipeline(include_weather, float(alpha))
            pipeline.fit(splits["train"][columns], splits["train"][target])
            prediction = np.maximum(
                pipeline.predict(splits["validation"][columns]), floor
            )
            validation_metrics = evaluate_predictions(
                splits["validation"][target], prediction
            )
            tuning_rows.append(
                {"model": model_name, "alpha": alpha, **validation_metrics}
            )
            if validation_metrics["mae"] < best_mae:
                best_alpha = float(alpha)
                best_mae = validation_metrics["mae"]
                best_validation_prediction = prediction

        assert best_alpha is not None and best_validation_prediction is not None
        add_metrics(
            metric_rows,
            model_name,
            "validation",
            splits["validation"][target],
            best_validation_prediction,
            best_alpha,
        )
        train_validation = pd.concat(
            [splits["train"], splits["validation"]], ignore_index=True
        )
        final_pipeline = build_ridge_pipeline(include_weather, best_alpha)
        final_pipeline.fit(train_validation[columns], train_validation[target])
        prediction = np.maximum(
            final_pipeline.predict(splits["test"][columns]), floor
        )
        add_metrics(
            metric_rows,
            model_name,
            "test",
            splits["test"][target],
            prediction,
            best_alpha,
        )
        trained_models[model_name] = final_pipeline
        test_predictions[model_name] = prediction

    args.results_dir.mkdir(parents=True, exist_ok=True)
    args.models_dir.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(args.results_dir / "baseline_metrics.csv", index=False)
    pd.DataFrame(tuning_rows).to_csv(
        args.results_dir / "baseline_ridge_tuning.csv", index=False
    )

    split_summary = pd.DataFrame(
        [
            {
                "split": name,
                "rows": len(frame),
                "stations": frame["station_name"].nunique(),
                "start": frame["event_time"].min().isoformat(),
                "end": frame["event_time"].max().isoformat(),
                "average_target": frame[target].mean(),
                "zero_target_percent": frame[target].eq(0).mean() * 100,
            }
            for name, frame in splits.items()
        ]
    )
    split_summary.to_csv(args.results_dir / "baseline_split_summary.csv", index=False)

    best_name = "ridge_time_history_weather"
    test = splits["test"][
        ["event_time", "station_name", "borrow_count"]
    ].copy()
    test["prediction"] = test_predictions[best_name]
    test["absolute_error"] = (test["borrow_count"] - test["prediction"]).abs()
    station_error = (
        test.groupby("station_name", as_index=False)
        .agg(
            rows=("event_time", "size"),
            average_actual=("borrow_count", "mean"),
            average_prediction=("prediction", "mean"),
            mae=("absolute_error", "mean"),
        )
        .sort_values("mae", ascending=False)
    )
    station_error.to_csv(args.results_dir / "baseline_station_errors.csv", index=False)
    test["hour"] = test["event_time"].dt.hour
    hour_error = (
        test.groupby("hour", as_index=False)
        .agg(
            rows=("event_time", "size"),
            average_actual=("borrow_count", "mean"),
            average_prediction=("prediction", "mean"),
            mae=("absolute_error", "mean"),
        )
        .sort_values("hour")
    )
    hour_error.to_csv(args.results_dir / "baseline_hour_errors.csv", index=False)

    for name, pipeline in trained_models.items():
        joblib.dump(pipeline, args.models_dir / f"{name}.joblib")

    weather_test = metrics.loc[
        metrics["model"].eq("ridge_time_history_weather")
        & metrics["split"].eq("test")
    ].iloc[0]
    print(f"Model rows: {len(model_data):,}; stations: {len(stations)}")
    print(
        "Weather Ridge test: "
        f"MAE={weather_test['mae']:.3f}, RMSE={weather_test['rmse']:.3f}, "
        f"R2={weather_test['r2']:.3f}"
    )


if __name__ == "__main__":
    main()
