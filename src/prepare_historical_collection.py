"""Prepare every locally downloaded historical transfer-demand month."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .historical_collection import prepare_historical_collection
    from .historical_pipeline import load_current_station_names
except ImportError:
    from historical_collection import prepare_historical_collection
    from historical_pipeline import load_current_station_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Combine downloaded historical months.")
    parser.add_argument(
        "--input-dir", type=Path, default=Path("data/raw/historical")
    )
    parser.add_argument("--pattern", default="transfers_*.csv")
    parser.add_argument(
        "--station-reference",
        type=Path,
        default=Path("data/raw/youbike_immediate_sample.json"),
    )
    parser.add_argument(
        "--station-hour-output",
        type=Path,
        default=Path("data/processed/historical_station_hour_demand.csv"),
    )
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_paths = sorted(args.input_dir.glob(args.pattern))
    if not source_paths:
        raise SystemExit(f"No files matched {args.input_dir / args.pattern}")

    current_names = load_current_station_names(args.station_reference)
    outputs = prepare_historical_collection(source_paths, current_names)
    args.station_hour_output.parent.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    outputs["station_hour"].to_csv(args.station_hour_output, index=False)
    outputs["quality"].to_csv(
        args.results_dir / "historical_quality_summary.csv", index=False
    )
    outputs["daily"].to_csv(
        args.results_dir / "historical_daily_summary.csv", index=False
    )
    outputs["monthly"].to_csv(
        args.results_dir / "historical_monthly_summary.csv", index=False
    )
    outputs["hourly"].to_csv(
        args.results_dir / "historical_hourly_profile.csv", index=False
    )
    outputs["top_stations"].to_csv(
        args.results_dir / "historical_top_stations.csv", index=False
    )
    print(f"Processed {len(source_paths)} monthly files")
    print(f"Built {len(outputs['station_hour']):,} station-hour demand rows")


if __name__ == "__main__":
    main()
