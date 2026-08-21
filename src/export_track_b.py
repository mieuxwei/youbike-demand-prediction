"""Export a UTC Track B D1 time range through the protected Worker endpoint."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="Inclusive date or ISO timestamp")
    parser.add_argument("--end", required=True, help="Inclusive date or exclusive ISO timestamp")
    parser.add_argument("--station-id", help="Optional exact station ID")
    parser.add_argument(
        "--url",
        default=os.environ.get("TRACK_B_EXPORT_URL"),
        help="Worker export URL; defaults to TRACK_B_EXPORT_URL",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/track_b_live_export.csv"),
    )
    return parser.parse_args()


def export_csv(
    url: str,
    token: str,
    start: str,
    end: str,
    output_path: Path,
    station_id: str | None = None,
    session: requests.Session | None = None,
) -> tuple[int, int]:
    """Download all cursor-paginated CSV pages to one atomic local file."""
    if not url:
        raise ValueError("Worker export URL is required.")
    if not token:
        raise ValueError("TRACK_B_EXPORT_TOKEN is required.")

    owns_session = session is None
    client = session or requests.Session()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    cursor: str | None = None
    page_count = 0
    row_count = 0
    try:
        with temporary_path.open("w", encoding="utf-8", newline="") as output:
            while True:
                params = {"start": start, "end": end}
                if station_id:
                    params["station_id"] = station_id
                if cursor:
                    params["cursor"] = cursor
                response = client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=60,
                )
                response.raise_for_status()
                lines = response.text.splitlines()
                if not lines:
                    raise ValueError("Export endpoint returned an empty CSV response.")
                if page_count == 0:
                    output.write(lines[0] + "\n")
                for line in lines[1:]:
                    if line:
                        output.write(line + "\n")
                        row_count += 1
                page_count += 1
                cursor = response.headers.get("x-next-cursor")
                if not cursor:
                    break
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    finally:
        if owns_session:
            client.close()
    return row_count, page_count


def main() -> None:
    args = parse_args()
    token = os.environ.get("TRACK_B_EXPORT_TOKEN", "")
    try:
        rows, pages = export_csv(
            url=args.url,
            token=token,
            start=args.start,
            end=args.end,
            output_path=args.output,
            station_id=args.station_id,
        )
    except (OSError, ValueError, requests.RequestException) as error:
        raise SystemExit(f"Track B export failed: {error}") from error
    print(f"Exported {rows:,} Track B rows across {pages} page(s) to {args.output}")


if __name__ == "__main__":
    main()
