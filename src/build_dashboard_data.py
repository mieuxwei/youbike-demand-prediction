"""Build a compact, reproducible data bundle for the historical dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .baseline_model import load_hourly_weather, load_station_hour_demand
    from .prediction import (
        attach_historical_actuals,
        build_prediction_features,
        load_model_metadata,
        load_verified_model,
        predict_hourly_demand,
    )
except ImportError:
    from baseline_model import load_hourly_weather, load_station_hour_demand
    from prediction import (
        attach_historical_actuals,
        build_prediction_features,
        load_model_metadata,
        load_verified_model,
        predict_hourly_demand,
    )


WEEKDAYS_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--targets", type=Path, default=Path("config/dashboard_targets.json")
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models/hist_gradient_boosting_weather.joblib"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("models/hist_gradient_boosting_weather.metadata.json"),
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
    parser.add_argument(
        "--model-comparison",
        type=Path,
        default=Path("results/model_comparison_metrics.csv"),
    )
    parser.add_argument(
        "--rolling-origin",
        type=Path,
        default=Path("results/tree_rolling_origin_metrics.csv"),
    )
    parser.add_argument(
        "--feature-importance",
        type=Path,
        default=Path("results/tree_permutation_importance.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dashboard/app/dashboard-data.json"),
    )
    return parser.parse_args()


def json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Return records after converting NumPy scalars and missing cells safely."""
    return json.loads(frame.to_json(orient="records"))


def build_target(
    target_time: str,
    model: object,
    metadata: dict[str, Any],
    demand: pd.DataFrame,
    weather: pd.DataFrame,
) -> dict[str, Any]:
    features = build_prediction_features(
        demand, weather, metadata["selected_stations"], target_time
    )
    if features.columns.tolist() != metadata["feature_columns"]:
        raise ValueError("Generated features do not match model metadata.")
    predictions = predict_hourly_demand(model, features, target_time)
    predictions = attach_historical_actuals(predictions, demand, target_time)

    target = pd.Timestamp(target_time)
    weather_row = weather.loc[weather["event_time"].eq(target)]
    if len(weather_row) != 1:
        raise ValueError(f"Expected one weather row for {target_time}.")
    observed = weather_row.iloc[0]

    station_rows = predictions[
        [
            "prediction_rank",
            "station_name",
            "predicted_borrow_count",
            "actual_borrow_count",
            "absolute_error",
        ]
    ].rename(
        columns={
            "prediction_rank": "rank",
            "station_name": "station",
            "predicted_borrow_count": "predicted",
            "actual_borrow_count": "actual",
            "absolute_error": "absoluteError",
        }
    )
    station_rows[["predicted", "actual", "absoluteError"]] = station_rows[
        ["predicted", "actual", "absoluteError"]
    ].round(2)

    return {
        "id": target.strftime("%Y%m%d-%H"),
        "targetTime": target.isoformat(),
        "dateLabel": f"{target.month} 月 {target.day} 日",
        "timeLabel": target.strftime("%H:%M"),
        "weekdayLabel": WEEKDAYS_ZH[target.dayofweek],
        "periodLabel": "週末" if target.dayofweek >= 5 else "平日",
        "weather": {
            "temperatureC": round(float(observed["temperature_c"]), 1),
            "humidityPercent": round(float(observed["relative_humidity_percent"])),
            "precipitationMm": round(float(observed["precipitation_mm"]), 1),
            "windSpeedKmh": round(float(observed["wind_speed_kmh"]), 1),
            "isRaining": bool(observed["is_raining"]),
        },
        "summary": {
            "totalPredicted": round(float(predictions["predicted_borrow_count"].sum())),
            "totalActual": round(float(predictions["actual_borrow_count"].sum())),
            "mae": round(float(predictions["absolute_error"].mean()), 2),
            "largestDemandStation": str(predictions.iloc[0]["station_name"]),
        },
        "stations": json_records(station_rows),
    }


def main() -> None:
    args = parse_args()
    target_config = json.loads(args.targets.read_text(encoding="utf-8"))
    target_times = target_config.get("targets", [])
    if not target_times:
        raise ValueError("Dashboard target configuration must not be empty.")

    metadata = load_model_metadata(args.metadata)
    model = load_verified_model(args.model, metadata)
    demand = load_station_hour_demand(args.demand_input)
    weather = load_hourly_weather(args.weather_input)

    targets = [
        build_target(target, model, metadata, demand, weather)
        for target in target_times
    ]
    comparison = pd.read_csv(args.model_comparison)
    comparison = comparison.loc[comparison["split"].eq("test")].copy()
    comparison["label"] = comparison["model"].map(
        {
            "persistence_1h": "前一小時",
            "seasonal_168h": "前一週同時段",
            "ridge_time_history": "Ridge",
            "ridge_time_history_weather": "Ridge + 天氣",
            "hist_gradient_boosting": "HGB",
            "hist_gradient_boosting_weather": "HGB + 天氣",
            "xgboost_weather": "XGBoost + 天氣",
        }
    )
    comparison = comparison[["model", "label", "mae", "rmse", "r2"]]
    comparison[["mae", "rmse", "r2"]] = comparison[
        ["mae", "rmse", "r2"]
    ].round(3)

    rolling = pd.read_csv(args.rolling_origin)
    rolling["period"] = (
        pd.to_datetime(rolling["validation_start"]).dt.strftime("%m/%d")
        + "–"
        + pd.to_datetime(rolling["validation_end"]).dt.strftime("%m/%d")
    )
    rolling = rolling[["fold", "period", "mae", "rmse", "r2"]].round(3)

    importance = pd.read_csv(args.feature_importance).head(8).copy()
    importance["label"] = importance["feature"].map(
        {
            "hour_cos": "小時週期（cos）",
            "borrow_lag_1h": "前一小時借車量",
            "hour_sin": "小時週期（sin）",
            "station_name": "站點",
            "borrow_lag_168h": "前一週同時段",
            "borrow_rolling_mean_24h": "前 24 小時平均",
            "borrow_lag_24h": "前一天同時段",
            "weekday_sin": "星期週期",
        }
    )
    importance["mae_increase_mean"] = importance["mae_increase_mean"].round(3)

    payload = {
        "meta": {
            "title": "YouBike 歷史需求觀測站",
            "model": "Histogram Gradient Boosting + 天氣",
            "scope": metadata["target_scope"],
            "stationCount": metadata["selected_station_count"],
            "testPeriod": "2023-12-01 至 2023-12-31",
            "trainedThrough": metadata["trained_through"],
            "targetCount": len(targets),
            "testMetrics": {
                key: round(float(value), 3)
                for key, value in metadata["test_metrics"].items()
            },
        },
        "targets": targets,
        "modelComparison": json_records(comparison),
        "rollingOrigin": json_records(rolling),
        "featureImportance": json_records(
            importance[["feature", "label", "mae_increase_mean"]]
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Built {len(targets)} dashboard targets at {args.output}")


if __name__ == "__main__":
    main()
