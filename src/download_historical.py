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


def select_resources(config: dict[str, Any], months: list[str]) -> list[tuple[str, dict[str, str]]]:
    """Resolve requested months, supporting the special value ``all``."""
    resources = config["resources"]
    selected_months = sorted(resources) if months == ["all"] else months
    missing = [month for month in selected_months if month not in resources]
    if missing:
        available = ", ".join(sorted(resources))
        raise ValueError(
            f"Months not registered: {', '.join(missing)}. Available: {available}"
        )
    return [(month, resources[month]) for month in selected_months]


def parse_args() -> argparse.Namespace:
    """Read command-line options."""
    parser = argparse.ArgumentParser(
        description="Download an official transfer-related YouBike trip file."
    )
    parser.add_argument(
        "--month",
        nargs="+",
        required=True,
        help="One or more resource months, or 'all', e.g. 2023-01 2023-02",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--force", action="store_true", help="Replace an existing file")
    return parser.parse_args()


def main() -> None:
    """Download the selected registered resource."""
    args = parse_args()
    config = load_config(args.config)
    try:
        resources = select_resources(config, args.month)
        for month, resource in resources:
            output_path = args.output_dir / resource["filename"]
            download_resource(resource["url"], output_path, force=args.force)
            print(f"Historical file ready ({month}): {output_path}")
    except (OSError, requests.RequestException, ValueError) as error:
        raise SystemExit(f"Historical download failed: {error}") from error


if __name__ == "__main__":
    main()
