"""Generate time-series features from validated raw YouBike snapshots."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .data_pipeline import (
        add_change_features,
        clean_snapshots,
        discover_snapshot_files,
        load_snapshots,
    )
    from .features import build_feature_coverage, build_features
except ImportError:
    from data_pipeline import (
        add_change_features,
        clean_snapshots,
        discover_snapshot_files,
        load_snapshots,
    )
    from features import build_feature_coverage, build_features


def parse_args() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(
        description="Build leakage-aware YouBike time-series features."
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/youbike_features.csv"),
    )
    parser.add_argument(
        "--coverage-output",
        type=Path,
        default=Path("results/feature_coverage.csv"),
    )
    return parser.parse_args()


def main() -> None:
    """Run the raw-to-feature pipeline."""
    args = parse_args()
    source_paths = discover_snapshot_files(args.raw_dir)
    raw_data = load_snapshots(source_paths)
    cleaned_data = add_change_features(clean_snapshots(raw_data))
    featured_data = build_features(cleaned_data)
    coverage = build_feature_coverage(featured_data)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.coverage_output.parent.mkdir(parents=True, exist_ok=True)
    featured_data.to_csv(args.output, index=False)
    coverage.to_csv(args.coverage_output, index=False)

    target_columns = [
        column
        for column in featured_data.columns
        if column.startswith("target_available_bikes_")
    ]
    usable_targets = int(featured_data[target_columns].notna().any(axis=1).sum())

    print(f"Loaded {len(source_paths)} snapshot files")
    print(f"Built features for {len(featured_data):,} station records")
    print(f"Rows with at least one future target: {usable_targets:,}")
    print(f"Saved feature data to {args.output}")
    print(f"Saved coverage report to {args.coverage_output}")


if __name__ == "__main__":
    main()
