"""Tests for the Track B live export coverage audit."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.audit_track_b import (
    build_schedule_audit,
    build_target_coverage,
    load_track_b_export,
)


def sample_export() -> pd.DataFrame:
    times = pd.to_datetime(
        [
            "2026-08-21T00:00:00Z",
            "2026-08-21T00:05:00Z",
            "2026-08-21T00:35:00Z",
            "2026-08-21T01:00:00Z",
        ],
        utc=True,
    )
    rows = []
    for station_id in ("A", "B"):
        for index, timestamp in enumerate(times):
            rows.append(
                {
                    "snapshot_time": timestamp,
                    "station_id": station_id,
                    "available_bikes": index,
                    "capacity": 20,
                    "is_active": 1,
                }
            )
    return pd.DataFrame(rows)


class AuditTrackBTests(unittest.TestCase):
    def test_schedule_audit_reports_gap_and_duplicates(self) -> None:
        data = sample_export()
        data = pd.concat([data, data.iloc[[0]]], ignore_index=True)

        summary, gaps = build_schedule_audit(data)

        self.assertEqual(summary["snapshot_count"], 4)
        self.assertEqual(summary["duplicate_station_snapshot_rows"], 1)
        self.assertEqual(summary["gaps_over_threshold"], 2)
        self.assertEqual(summary["estimated_missing_slots"], 9)
        self.assertEqual(gaps["gap_minutes"].tolist(), [30.0, 25.0])

    def test_target_coverage_uses_forward_horizon_and_active_rows(self) -> None:
        data = sample_export()
        data.loc[
            (data["station_id"] == "B")
            & (data["snapshot_time"] == pd.Timestamp("2026-08-21T00:35:00Z")),
            "is_active",
        ] = 0

        coverage = build_target_coverage(data)

        coverage_by_horizon = coverage.set_index("horizon_minutes")
        self.assertEqual(coverage_by_horizon.loc[30, "usable_target_rows"], 1)
        self.assertEqual(coverage_by_horizon.loc[60, "usable_target_rows"], 2)

    def test_loader_rejects_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("snapshot_time,station_id\n2026-08-21T00:00:00Z,A\n")
            with self.assertRaisesRegex(ValueError, "missing required columns"):
                load_track_b_export(path)


if __name__ == "__main__":
    unittest.main()
