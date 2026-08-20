"""Download reproducible hourly historical weather for the Taipei reference point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests


DEFAULT_CONFIG = Path("config/weather_source.json")
DEFAULT_OUTPUT = Path("data/raw/weather/taipei_weather_2023.json")


def load_weather_config(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    required = {
        "endpoint",
        "latitude",
        "longitude",
        "timezone",
        "start_date",
        "end_date",
        "hourly_variables",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(f"Weather config is missing: {', '.join(sorted(missing))}")
    return config


def build_weather_params(config: dict[str, Any]) -> dict[str, object]:
    """Build documented API parameters without an API key."""
    return {
        "latitude": config["latitude"],
        "longitude": config["longitude"],
        "start_date": config["start_date"],
        "end_date": config["end_date"],
        "hourly": ",".join(config["hourly_variables"]),
        "timezone": config["timezone"],
    }


def download_weather(
    config: dict[str, Any], output_path: Path, force: bool = False
) -> Path:
    """Save the raw API response atomically and preserve its metadata."""
    if output_path.exists() and not force:
        print(f"Using existing file: {output_path}")
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        response = requests.get(
            config["endpoint"], params=build_weather_params(config), timeout=120
        )
        response.raise_for_status()
        payload = response.json()
        if "hourly" not in payload:
            raise ValueError("Weather response does not contain hourly data.")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Taipei historical weather.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        config = load_weather_config(args.config)
        output = download_weather(config, args.output, force=args.force)
    except (OSError, ValueError, requests.RequestException) as error:
        raise SystemExit(f"Weather download failed: {error}") from error
    print(f"Weather file ready: {output}")


if __name__ == "__main__":
    main()
