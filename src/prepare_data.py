"""Build the cleaned YouBike snapshot dataset and quality reports."""

from __future__ import annotations

import argparse
from pathlib import Path

from data_pipeline import (
    add_change_features,
    build_quality_summary,
    build_snapshot_summary,
    clean_snapshots,
    discover_snapshot_files,
    load_snapshots,
)


def parse_args() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(
        description="Validate and combine raw YouBike JSON snapshots."
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/youbike_snapshots.csv"),
    )
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    return parser.parse_args()


def main() -> None:
    """Run the complete raw-to-processed pipeline."""
    args = parse_args()
    source_paths = discover_snapshot_files(args.raw_dir)
    raw_data = load_snapshots(source_paths)
    processed_data = add_change_features(clean_snapshots(raw_data))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)

    quality_path = args.results_dir / "data_quality_summary.csv"
    snapshot_path = args.results_dir / "snapshot_summary.csv"

    processed_data.to_csv(args.output, index=False)
    build_quality_summary(raw_data, processed_data, source_paths).to_csv(
        quality_path, index=False
    )
    build_snapshot_summary(processed_data).to_csv(snapshot_path, index=False)

    print(f"Loaded {len(source_paths)} snapshot files")
    print(f"Prepared {len(processed_data):,} station records")
    print(f"Saved processed data to {args.output}")
    print(f"Saved quality report to {quality_path}")
    print(f"Saved snapshot report to {snapshot_path}")


if __name__ == "__main__":
    main()
