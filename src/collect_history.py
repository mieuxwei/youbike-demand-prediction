"""Collect multiple YouBike snapshots at a fixed interval."""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any, Callable

import requests

try:
    from .collect_youbike import fetch_snapshot, save_snapshot
except ImportError:
    from collect_youbike import fetch_snapshot, save_snapshot


RecordList = list[dict[str, Any]]


def positive_int(value: str) -> int:
    """Parse a positive integer for argparse."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def positive_float(value: str) -> float:
    """Parse a positive number for argparse."""
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def collect_history(
    count: int,
    interval_seconds: float,
    output_directory: Path,
    fetcher: Callable[[], RecordList] = fetch_snapshot,
    saver: Callable[[RecordList, Path], Path] = save_snapshot,
    sleep: Callable[[float], None] = time.sleep,
    report_error: Callable[[str], None] = print,
) -> list[Path]:
    """Collect a fixed number of snapshots and continue after recoverable errors."""
    if count < 1:
        raise ValueError("count must be at least 1")
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than 0")

    saved_paths: list[Path] = []
    recoverable_errors = (OSError, requests.RequestException, ValueError)

    for attempt in range(1, count + 1):
        if attempt > 1:
            sleep(interval_seconds)

        try:
            records = fetcher()
            output_path = saver(records, output_directory)
        except recoverable_errors as error:
            report_error(f"Attempt {attempt}/{count} failed: {error}")
            continue

        saved_paths.append(output_path)
        print(
            f"Attempt {attempt}/{count}: saved {len(records):,} stations "
            f"to {output_path}"
        )

    return saved_paths


def parse_args() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(
        description="Collect multiple official YouBike snapshots."
    )
    parser.add_argument(
        "--count",
        type=positive_int,
        required=True,
        help="Number of collection attempts.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=positive_float,
        default=5.0,
        help="Minutes between attempts (default: 5).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/snapshots"),
        help="Directory for timestamped JSON snapshots.",
    )
    return parser.parse_args()


def main() -> None:
    """Run repeated collection from the command line."""
    args = parse_args()
    try:
        saved_paths = collect_history(
            count=args.count,
            interval_seconds=args.interval_minutes * 60,
            output_directory=args.output_dir,
        )
    except KeyboardInterrupt:
        raise SystemExit("Collection stopped by user.") from None

    print(f"Collection finished: {len(saved_paths)}/{args.count} snapshots saved")
    if not saved_paths:
        raise SystemExit("No snapshots were saved.")


if __name__ == "__main__":
    main()
