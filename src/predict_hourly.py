"""Command-line prediction interface for hourly transfer-related demand."""

from __future__ import annotations

import argparse
from pathlib import Path

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict top-100 station transfer-related borrowing demand."
    )
    parser.add_argument("--target-time", required=True)
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
        "--output",
        type=Path,
        default=Path("results/hourly_predictions.csv"),
    )
    parser.add_argument(
        "--include-actual",
        action="store_true",
        help="Attach actual demand only for a covered historical target hour.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = load_model_metadata(args.metadata)
    if not metadata["includes_weather"]:
        raise SystemExit("This prediction command requires a weather-enabled model.")
    model = load_verified_model(args.model, metadata)
    demand = load_station_hour_demand(args.demand_input)
    weather = load_hourly_weather(args.weather_input)
    features = build_prediction_features(
        demand, weather, metadata["selected_stations"], args.target_time
    )
    if features.columns.tolist() != metadata["feature_columns"]:
        raise SystemExit("Generated features do not match the model metadata schema.")
    predictions = predict_hourly_demand(model, features, args.target_time)
    if args.include_actual:
        predictions = attach_historical_actuals(
            predictions, demand, args.target_time
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output, index=False)
    print(f"Predicted {len(predictions)} stations for {args.target_time}")
    print(f"Saved ranked predictions to {args.output}")


if __name__ == "__main__":
    main()
