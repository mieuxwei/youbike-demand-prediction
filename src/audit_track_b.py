"""Audit an exported Track B live dataset before availability modeling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

try:
    from .features import add_future_targets
except ImportError:
    from features import add_future_targets


REQUIRED_COLUMNS = {
    "snapshot_time",
    "station_id",
    "available_bikes",
    "capacity",
    "is_active",
}


def load_track_b_export(path: Path) -> pd.DataFrame:
    """Load and validate the columns needed for a Track B coverage audit."""
    header = pd.read_csv(path, nrows=0)
    missing = REQUIRED_COLUMNS - set(header.columns)
    if missing:
        raise ValueError(
            "Track B export is missing required columns: "
            + ", ".join(sorted(missing))
        )

    data = pd.read_csv(
        path,
        usecols=sorted(REQUIRED_COLUMNS),
        dtype={"station_id": "string"},
    )
    data["snapshot_time"] = pd.to_datetime(
        data["snapshot_time"], utc=True, errors="coerce"
    )
    if data.empty:
        raise ValueError("Track B export contains no station rows.")
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Track B export contains missing or invalid required values.")

    for column in ("available_bikes", "capacity", "is_active"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if data[["available_bikes", "capacity", "is_active"]].isna().any().any():
        raise ValueError("Track B export contains invalid numeric values.")
    if not data["is_active"].isin([0, 1]).all():
        raise ValueError("is_active must contain only 0 or 1.")

    data["is_active"] = data["is_active"].astype(bool)
    return data.sort_values(["station_id", "snapshot_time"]).reset_index(drop=True)


def build_schedule_audit(
    data: pd.DataFrame,
    expected_interval_minutes: int = 5,
    gap_threshold_minutes: float = 5.5,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Summarize snapshot coverage and list gaps above the allowed jitter."""
    times = pd.Series(data["snapshot_time"].drop_duplicates().sort_values())
    gaps = times.diff().dt.total_seconds().div(60)
    gap_rows = pd.DataFrame(
        {
            "previous_snapshot_time": times.shift(),
            "snapshot_time": times,
            "gap_minutes": gaps,
        }
    )
    gap_rows = gap_rows.loc[gap_rows["gap_minutes"].gt(gap_threshold_minutes)].copy()
    gap_rows["estimated_missing_slots"] = (
        (gap_rows["gap_minutes"] / expected_interval_minutes).round().astype(int) - 1
    ).clip(lower=0)

    first_time = times.iloc[0]
    latest_time = times.iloc[-1]
    span_hours = (latest_time - first_time).total_seconds() / 3600
    rows_by_snapshot = data.groupby("snapshot_time", observed=True).size()
    summary: dict[str, object] = {
        "row_count": int(len(data)),
        "snapshot_count": int(len(times)),
        "station_count": int(data["station_id"].nunique()),
        "first_snapshot_utc": first_time.isoformat(),
        "latest_snapshot_utc": latest_time.isoformat(),
        "coverage_hours": round(span_hours, 3),
        "coverage_days": round(span_hours / 24, 3),
        "duplicate_station_snapshot_rows": int(
            data.duplicated(["station_id", "snapshot_time"]).sum()
        ),
        "min_rows_per_snapshot": int(rows_by_snapshot.min()),
        "max_rows_per_snapshot": int(rows_by_snapshot.max()),
        "mean_rows_per_snapshot": round(float(rows_by_snapshot.mean()), 3),
        "gaps_over_threshold": int(len(gap_rows)),
        "estimated_missing_slots": int(gap_rows["estimated_missing_slots"].sum()),
        "max_gap_minutes": round(float(gaps.max()), 3),
    }
    return summary, gap_rows.reset_index(drop=True)


def build_target_coverage(
    data: pd.DataFrame,
    horizons_minutes: tuple[int, ...] = (30, 60),
    tolerance_minutes: float = 2,
) -> pd.DataFrame:
    """Measure exact active-station future-target coverage using approved logic."""
    if not data["is_active"].isin([0, 1, True, False]).all():
        raise ValueError("is_active must contain only active/inactive values.")
    prepared = data.copy()
    prepared["is_active"] = prepared["is_active"].astype(bool)
    featured = add_future_targets(
        prepared,
        horizons_minutes=horizons_minutes,
        tolerance_minutes=tolerance_minutes,
    )
    rows = []
    for horizon in horizons_minutes:
        target_column = f"target_available_bikes_{horizon}m"
        actual_column = f"target_{horizon}m_actual_minutes"
        usable = int(featured[target_column].notna().sum())
        rows.append(
            {
                "horizon_minutes": horizon,
                "total_rows": int(len(featured)),
                "usable_target_rows": usable,
                "coverage_percent": round(100 * usable / len(featured), 3),
                "min_actual_minutes": (
                    round(float(featured[actual_column].min()), 3)
                    if usable
                    else None
                ),
                "max_actual_minutes": (
                    round(float(featured[actual_column].max()), 3)
                    if usable
                    else None
                ),
            }
        )
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("results/track_b_live_audit.json"),
    )
    parser.add_argument(
        "--gaps-output",
        type=Path,
        default=Path("results/track_b_live_gaps.csv"),
    )
    parser.add_argument(
        "--targets-output",
        type=Path,
        default=Path("results/track_b_target_coverage.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_track_b_export(args.input)
    summary, gaps = build_schedule_audit(data)
    targets = build_target_coverage(data)

    for output in (args.summary_output, args.gaps_output, args.targets_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    gaps.to_csv(args.gaps_output, index=False)
    targets.to_csv(args.targets_output, index=False)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nFuture-target coverage")
    print(targets.to_string(index=False))


if __name__ == "__main__":
    main()
