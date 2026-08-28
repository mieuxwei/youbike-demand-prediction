"""Export a UTC Track B D1 time range through the protected Worker endpoint."""

from __future__ import annotations

import argparse
import os
import re
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


TAIPEI_TIMEZONE = timezone(timedelta(hours=8))


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
    parser.add_argument(
        "--window-hours",
        type=int,
        default=6,
        help="Reset cursor within fixed UTC windows to keep D1 queries bounded.",
    )
    return parser.parse_args()


def _parse_boundary(value: str, end_exclusive: bool) -> datetime:
    """Mirror the Worker's date-only Taipei and timezone-aware ISO semantics."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(
            tzinfo=TAIPEI_TIMEZONE
        )
        if end_exclusive:
            parsed += timedelta(days=1)
        return parsed.astimezone(timezone.utc)

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"Invalid export boundary: {value}") from error
    if parsed.tzinfo is None:
        raise ValueError("ISO export boundaries must include Z or a UTC offset.")
    return parsed.astimezone(timezone.utc)


def build_export_windows(
    start: str,
    end: str,
    window_hours: int | None,
) -> list[tuple[str, str]]:
    """Split a range into bounded UTC windows without gaps or overlap."""
    if window_hours is None:
        return [(start, end)]
    if window_hours < 1:
        raise ValueError("window_hours must be positive.")

    start_time = _parse_boundary(start, end_exclusive=False)
    end_time = _parse_boundary(end, end_exclusive=True)
    if start_time >= end_time:
        raise ValueError("start must be before end.")

    windows = []
    current = start_time
    window_size = timedelta(hours=window_hours)
    while current < end_time:
        next_time = min(current + window_size, end_time)
        windows.append(
            (
                current.isoformat().replace("+00:00", "Z"),
                next_time.isoformat().replace("+00:00", "Z"),
            )
        )
        current = next_time
    return windows


def export_csv(
    url: str,
    token: str,
    start: str,
    end: str,
    output_path: Path,
    station_id: str | None = None,
    session: requests.Session | None = None,
    max_page_attempts: int = 5,
    sleep: Callable[[float], None] = time.sleep,
    window_hours: int | None = None,
) -> tuple[int, int]:
    """Download all cursor-paginated CSV pages to one atomic local file."""
    if not url:
        raise ValueError("Worker export URL is required.")
    if not token:
        raise ValueError("TRACK_B_EXPORT_TOKEN is required.")
    if max_page_attempts < 1:
        raise ValueError("max_page_attempts must be positive.")

    owns_session = session is None
    client = session or requests.Session()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    page_count = 0
    row_count = 0
    windows = build_export_windows(start, end, window_hours)
    try:
        with temporary_path.open("w", encoding="utf-8", newline="") as output:
            for window_start, window_end in windows:
                cursor: str | None = None
                while True:
                    params = {"start": window_start, "end": window_end}
                    if station_id:
                        params["station_id"] = station_id
                    if cursor:
                        params["cursor"] = cursor
                    response = None
                    for attempt in range(1, max_page_attempts + 1):
                        try:
                            response = client.get(
                                url,
                                params=params,
                                headers={"Authorization": f"Bearer {token}"},
                                timeout=60,
                            )
                            response.raise_for_status()
                            break
                        except requests.RequestException as error:
                            status = getattr(error.response, "status_code", None)
                            retryable = (
                                status is None or status == 429 or status >= 500
                            )
                            if not retryable or attempt == max_page_attempts:
                                raise
                            delay = min(2 ** (attempt - 1), 8)
                            print(
                                f"Export page {page_count + 1:,} failed "
                                f"(HTTP {status or 'network'}, attempt {attempt}/"
                                f"{max_page_attempts}); retrying in {delay}s."
                            )
                            sleep(delay)
                    if response is None:  # pragma: no cover - defensive invariant
                        raise RuntimeError("Export page request produced no response.")
                    lines = response.text.splitlines()
                    if not lines:
                        raise ValueError(
                            "Export endpoint returned an empty CSV response."
                        )
                    if page_count == 0:
                        output.write(lines[0] + "\n")
                    for line in lines[1:]:
                        if line:
                            output.write(line + "\n")
                            row_count += 1
                    page_count += 1
                    if page_count % 25 == 0:
                        print(
                            f"Downloaded {row_count:,} rows across "
                            f"{page_count:,} page(s)..."
                        )
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
            window_hours=args.window_hours,
        )
    except (OSError, ValueError, requests.RequestException) as error:
        raise SystemExit(f"Track B export failed: {error}") from error
    print(f"Exported {rows:,} Track B rows across {pages} page(s) to {args.output}")


if __name__ == "__main__":
    main()
