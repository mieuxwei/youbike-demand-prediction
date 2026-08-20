"""Download and save one Taipei YouBike 2.0 availability snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


API_URL = (
    "https://tcgbusfs.blob.core.windows.net/"
    "dotapp/youbike/v2/youbike_immediate.json"
)

# These fields were confirmed from the official API sample on 2026-08-20.
REQUIRED_FIELDS = {
    "sno",
    "sna",
    "sarea",
    "mday",
    "Quantity",
    "available_rent_bikes",
    "available_return_bikes",
}


def fetch_snapshot(url: str = API_URL) -> list[dict[str, Any]]:
    """Fetch one snapshot and validate its basic structure."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    records = response.json()

    if not isinstance(records, list) or not records:
        raise ValueError("Expected the API response to be a non-empty list.")

    if not isinstance(records[0], dict):
        raise ValueError("Expected each station record to be a JSON object.")

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Station record {index} is not a JSON object.")

        missing_fields = REQUIRED_FIELDS - record.keys()
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(
                f"Station record {index} is missing required API fields: {missing}"
            )

    return records


def save_snapshot(
    records: list[dict[str, Any]], output_directory: Path
) -> Path:
    """Save records as UTF-8 JSON using a timestamped filename."""
    output_directory.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now().astimezone()
    filename = f"youbike_{collected_at:%Y%m%d_%H%M%S_%f}.json"
    output_path = output_directory / filename

    temporary_path = output_path.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False)
    temporary_path.replace(output_path)

    return output_path


def parse_args() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(
        description="Save one official Taipei YouBike availability snapshot."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/snapshots"),
        help="Directory for timestamped JSON snapshots.",
    )
    return parser.parse_args()


def main() -> None:
    """Collect and save one snapshot."""
    args = parse_args()
    try:
        records = fetch_snapshot()
        output_path = save_snapshot(records, args.output_dir)
    except (OSError, requests.RequestException, ValueError) as error:
        raise SystemExit(f"Collection failed: {error}") from error
    print(f"Saved {len(records):,} stations to {output_path}")


if __name__ == "__main__":
    main()
