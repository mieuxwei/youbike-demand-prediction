"""Download official Taipei transfer-related YouBike trip files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests


DEFAULT_CONFIG = Path("config/historical_sources.json")
DEFAULT_OUTPUT_DIRECTORY = Path("data/raw/historical")


def load_config(config_path: Path) -> dict[str, Any]:
    """Load and minimally validate the historical source registry."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if "resources" not in config or not isinstance(config["resources"], dict):
        raise ValueError("Historical source config must contain a resources object.")
    return config


def download_resource(
    url: str,
    output_path: Path,
    force: bool = False,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """Stream one large CSV to an atomic temporary file."""
    if output_path.exists() and not force:
        print(f"Using existing file: {output_path}")
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")

    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with temporary_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    file.write(chunk)
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return output_path


def parse_args() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(
        description="Download an official transfer-related YouBike trip file."
    )
    parser.add_argument("--month", required=True, help="Resource month, e.g. 2023-01")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--force", action="store_true", help="Replace an existing file")
    return parser.parse_args()


def main() -> None:
    """Download the selected registered resource."""
    args = parse_args()
    config = load_config(args.config)
    resource = config["resources"].get(args.month)
    if resource is None:
        available = ", ".join(sorted(config["resources"]))
        raise SystemExit(f"Month {args.month} is not registered. Available: {available}")

    output_path = args.output_dir / resource["filename"]
    try:
        download_resource(resource["url"], output_path, force=args.force)
    except (OSError, requests.RequestException, ValueError) as error:
        raise SystemExit(f"Historical download failed: {error}") from error
    print(f"Historical file ready: {output_path}")


if __name__ == "__main__":
    main()
