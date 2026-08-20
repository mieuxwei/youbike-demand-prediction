"""Prepare official transfer-related YouBike historical demand data."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .historical_pipeline import (
        build_daily_summary,
        build_historical_quality_summary,
        build_hourly_profile,
        build_station_hour_demand,
        build_top_station_summary,
        clean_historical_trips,
        load_current_station_names,
        load_historical_trips,
    )
except ImportError:
    from historical_pipeline import (
        build_daily_summary,
        build_historical_quality_summary,
        build_hourly_profile,
        build_station_hour_demand,
        build_top_station_summary,
        clean_historical_trips,
        load_current_station_names,
        load_historical_trips,
    )


def parse_args() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(
        description="Clean and summarize a transfer-related YouBike trip CSV."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/historical/transfers_2023_01.csv"),
    )
    parser.add_argument(
        "--station-reference",
        type=Path,
        default=Path("data/raw/youbike_immediate_sample.json"),
    )
    parser.add_argument(
        "--processed-output",
        type=Path,
        default=Path("data/processed/historical_transfers_2023_01.csv"),
    )
    parser.add_argument(
        "--station-hour-output",
        type=Path,
        default=Path("data/processed/historical_station_hour_demand.csv"),
    )
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    return parser.parse_args()


def main() -> None:
    """Run the complete historical raw-to-analysis pipeline."""
    args = parse_args()
    raw_data = load_historical_trips(args.input)
    current_names = load_current_station_names(args.station_reference)
    clean_data = clean_historical_trips(raw_data, current_names)
    station_hour = build_station_hour_demand(clean_data)

    args.processed_output.parent.mkdir(parents=True, exist_ok=True)
    args.station_hour_output.parent.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    clean_data.to_csv(args.processed_output, index=False)
    station_hour.to_csv(args.station_hour_output, index=False)
    build_historical_quality_summary(raw_data, clean_data).to_csv(
        args.results_dir / "historical_quality_summary.csv", index=False
    )
    build_daily_summary(clean_data).to_csv(
        args.results_dir / "historical_daily_summary.csv", index=False
    )
    build_hourly_profile(clean_data).to_csv(
        args.results_dir / "historical_hourly_profile.csv", index=False
    )
    build_top_station_summary(clean_data).to_csv(
        args.results_dir / "historical_top_stations.csv", index=False
    )

    print(f"Prepared {len(clean_data):,} transfer-related trip records")
    print(f"Built {len(station_hour):,} station-hour demand rows")
    print(f"Saved processed trips to {args.processed_output}")
    print(f"Saved historical reports under {args.results_dir}")


if __name__ == "__main__":
    main()
