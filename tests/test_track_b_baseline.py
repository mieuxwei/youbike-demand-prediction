"""Tests for the preliminary Track B persistence baseline."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.track_b_baseline import (
    assign_chronological_splits,
    evaluate_persistence,
)


class TrackBBaselineTests(unittest.TestCase):
    def test_chronological_splits_are_ordered(self) -> None:
        data = pd.DataFrame(
            {
                "snapshot_time": pd.to_datetime(
                    [
                        "2026-08-21T00:00:00Z",
                        "2026-08-26T00:00:00Z",
                        "2026-08-27T00:00:00Z",
                        "2026-08-28T06:00:00Z",
                    ],
                    utc=True,
                )
            }
        )

        split, boundaries = assign_chronological_splits(data)

        self.assertEqual(split.tolist(), ["train", "validation", "test", "test"])
        self.assertEqual(
            boundaries["validation_end"],
            pd.Timestamp("2026-08-27T00:00:00Z"),
        )

    def test_evaluation_purges_target_crossing_validation_boundary(self) -> None:
        featured = pd.DataFrame(
            {
                "snapshot_time": pd.to_datetime(
                    [
                        "2026-08-26T22:30:00Z",
                        "2026-08-26T23:45:00Z",
                        "2026-08-27T00:00:00Z",
                    ],
                    utc=True,
                ),
                "available_bikes": [5, 10, 8],
                "target_available_bikes_30m": [3, 7, 8],
                "target_30m_actual_minutes": [30, 30, 30],
                "target_available_bikes_60m": [2, 6, 8],
                "target_60m_actual_minutes": [60, 60, 60],
            }
        )
        split = pd.Series(["validation", "validation", "test"], dtype="string")
        boundaries = {
            "validation_end": pd.Timestamp("2026-08-27T00:00:00Z"),
            "latest": pd.Timestamp("2026-08-27T01:00:00Z"),
        }

        metrics = evaluate_persistence(featured, split, boundaries)
        indexed = metrics.set_index(["horizon_minutes", "split"])

        self.assertEqual(indexed.loc[(30, "validation"), "rows"], 1)
        self.assertEqual(indexed.loc[(60, "validation"), "rows"], 1)

    def test_persistence_metrics_use_current_available_bikes(self) -> None:
        featured = pd.DataFrame(
            {
                "snapshot_time": pd.to_datetime(
                    [
                        "2026-08-26T22:00:00Z",
                        "2026-08-26T22:05:00Z",
                        "2026-08-27T00:00:00Z",
                        "2026-08-27T00:05:00Z",
                    ],
                    utc=True,
                ),
                "available_bikes": [1, 2, 5, 8],
                "target_available_bikes_30m": [1, 2, 3, 9],
                "target_30m_actual_minutes": [30, 30, 30, 30],
                "target_available_bikes_60m": [1, 2, 4, 6],
                "target_60m_actual_minutes": [60, 60, 60, 60],
            }
        )
        split = pd.Series(
            ["validation", "validation", "test", "test"], dtype="string"
        )
        boundaries = {
            "validation_end": pd.Timestamp("2026-08-27T00:00:00Z"),
            "latest": pd.Timestamp("2026-08-27T02:00:00Z"),
        }

        metrics = evaluate_persistence(featured, split, boundaries)
        test_30m = metrics.loc[
            (metrics["horizon_minutes"] == 30) & (metrics["split"] == "test")
        ].iloc[0]

        self.assertAlmostEqual(test_30m["mae"], 1.5)
        self.assertAlmostEqual(test_30m["rmse"], np.sqrt(2.5))


if __name__ == "__main__":
    unittest.main()
