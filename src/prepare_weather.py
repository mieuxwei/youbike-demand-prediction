"""Prepare hourly weather and merge it with historical transfer demand."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

try:
    from .weather_pipeline import (
        build_rain_hour_profile,
        build_weather_demand_summary,
        build_weather_quality_summary,
        clean_weather,
        load_weather_json,
        merge_weather_with_demand,
    )
except ImportError:
    from weather_pipeline import (
        build_rain_hour_profile,
        build_weather_demand_summary,
        build_weather_quality_summary,
        clean_weather,
        load_weather_json,
        merge_weather_with_demand,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare and join historical weather.")
    parser.add_argument(
        "--weather-input",
        type=Path,
        default=Path("data/raw/weather/taipei_weather_2023.json"),
    )
    parser.add_argument(
        "--demand-input",
        type=Path,
        default=Path("data/processed/historical_station_hour_demand.csv"),
    )
    parser.add_argument(
        "--weather-output",
        type=Path,
        default=Path("data/processed/taipei_weather_hourly.csv"),
    )
    parser.add_argument(
        "--merged-output",
        type=Path,
        default=Path("data/processed/historical_demand_with_weather.csv"),
    )
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_weather, metadata = load_weather_json(args.weather_input)
    weather = clean_weather(raw_weather)
    demand = pd.read_csv(args.demand_input)
    merged = merge_weather_with_demand(demand, weather)

    args.weather_output.parent.mkdir(parents=True, exist_ok=True)
    args.merged_output.parent.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    weather.to_csv(args.weather_output, index=False)
    merged.to_csv(args.merged_output, index=False)
    build_weather_quality_summary(weather, merged, metadata).to_csv(
        args.results_dir / "weather_quality_summary.csv", index=False
    )
    build_weather_demand_summary(merged).to_csv(
        args.results_dir / "weather_demand_summary.csv", index=False
    )
    build_rain_hour_profile(merged).to_csv(
        args.results_dir / "weather_rain_hour_profile.csv", index=False
    )
    print(f"Prepared {len(weather):,} hourly weather rows")
    print(f"Weather matched {merged['weather_matched'].mean() * 100:.2f}% of demand rows")


if __name__ == "__main__":
    main()
