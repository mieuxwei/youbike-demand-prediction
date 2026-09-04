"""Tests for the fourteen-day Track B stability analysis."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.track_b_stability import (
    assign_periods,
    build_distribution_summary,
    build_stability_comparison,
    evaluate_period_persistence,
    load_stability_export,
    parse_utc_boundary,
)


def fourteen_day_sample() -> pd.DataFrame:
    times = pd.date_range("2026-08-21T09:45:02Z", periods=14 * 24 * 2, freq="30min")
    rows = []
    for station_id, offset in (("A", 0), ("B", 2)):
        for index, timestamp in enumerate(times):
            bikes = (index + offset) % 11
            rows.append(
                {
                    "snapshot_time": timestamp,
                    "station_id": station_id,
                    "available_bikes": bikes,
                    "available_return_bikes": 10 - bikes,
                    "capacity": 10,
                    "is_active": True,
                }
            )
    return pd.DataFrame(rows).sort_values(["station_id", "snapshot_time"]).reset_index(drop=True)


class TrackBStabilityTests(unittest.TestCase):
    def test_boundaries_require_timezone_and_assign_equal_weeks(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit timezone"):
            parse_utc_boundary("2026-08-21 09:45:02")
        data = fourteen_day_sample()
        start = parse_utc_boundary("2026-08-21T09:45:02Z")
        end = parse_utc_boundary("2026-09-04T09:45:02Z")
        period, midpoint = assign_periods(data, start, end)
        self.assertEqual(midpoint, pd.Timestamp("2026-08-28T09:45:02Z"))
        self.assertEqual(period.value_counts().to_dict(), {"week_1": 672, "week_2": 672})

    def test_day_type_uses_taipei_calendar(self) -> None:
        data = pd.DataFrame(
            {
                "snapshot_time": pd.to_datetime(
                    ["2026-08-21T15:30:00Z", "2026-08-21T16:30:00Z"], utc=True
                ),
                "station_id": ["A", "A"],
                "available_bikes": [4, 6],
                "available_return_bikes": [6, 4],
                "capacity": [10, 10],
                "is_active": [True, True],
            }
        )
        period = pd.Series(["week_1", "week_1"], dtype="string")
        summary = build_distribution_summary(data, period).set_index("day_type")
        self.assertEqual(summary.loc["weekday", "rows"], 1)
        self.assertEqual(summary.loc["weekend", "rows"], 1)

    def test_period_metrics_purge_targets_at_each_week_boundary(self) -> None:
        data = fourteen_day_sample()
        start = pd.Timestamp("2026-08-21T09:45:02Z")
        end = pd.Timestamp("2026-09-04T09:45:02Z")
        metrics, coverage = evaluate_period_persistence(data, start, end)
        indexed = metrics.set_index(["period", "horizon_minutes"])
        covered = coverage.set_index(["period", "horizon_minutes"])
        self.assertEqual(indexed.loc[("week_1", 30), "rows"], 670)
        self.assertEqual(indexed.loc[("week_2", 60), "rows"], 668)
        self.assertLess(covered.loc[("week_1", 60), "coverage_percent"], 100)
        comparison = build_stability_comparison(metrics).set_index("horizon_minutes")
        self.assertAlmostEqual(
            comparison.loc[30, "week_2_minus_week_1_mae"],
            indexed.loc[("week_2", 30), "mae"]
            - indexed.loc[("week_1", 30), "mae"],
        )

    def test_loader_rejects_duplicates_and_naive_timestamps(self) -> None:
        row = (
            "snapshot_time,station_id,available_bikes,available_return_bikes,capacity,is_active\n"
            "2026-08-21T09:45:02Z,A,3,7,10,1\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            duplicate_path = Path(directory) / "duplicate.csv"
            duplicate_path.write_text(row + row.split("\n", 1)[1], encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_stability_export(duplicate_path)

            naive_path = Path(directory) / "naive.csv"
            naive_path.write_text(row.replace("Z,A", ",A"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "explicit timezone"):
                load_stability_export(naive_path)


if __name__ == "__main__":
    unittest.main()
