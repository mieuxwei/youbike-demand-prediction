"""Tests for the first learned Track B availability regression."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.train_track_b_regression import (
    assign_splits,
    build_track_b_features,
    capacity_clip,
    eligible_mask,
    feature_columns,
    select_best_candidate,
    split_boundaries,
)


def config() -> dict[str, object]:
    return {
        "window_start": "2026-08-21T09:45:02Z",
        "train_end": "2026-09-08T09:45:02Z",
        "validation_end": "2026-09-13T09:45:02Z",
        "test_end": "2026-09-18T09:45:02Z",
        "horizons_minutes": [30, 60],
        "lag_minutes": [30, 60],
        "rolling_windows_minutes": [30, 60],
        "target_tolerance_minutes": 2,
        "training_snapshot_stride": 1,
        "random_state": 42,
        "candidates": [
            {
                "name": "hgb_test",
                "model_type": "hist_gradient_boosting",
                "learning_rate": 0.1,
                "max_iter": 5,
                "max_leaf_nodes": 7,
                "min_samples_leaf": 2,
                "l2_regularization": 1.0,
            }
        ],
    }


def sample_data() -> pd.DataFrame:
    times = pd.date_range("2026-08-21T09:45:02Z", periods=28 * 24 + 1, freq="1h")
    bikes = np.arange(len(times)) % 11
    return pd.DataFrame(
        {
            "snapshot_time": times,
            "station_id": pd.Series(["A"] * len(times), dtype="category"),
            "available_bikes": bikes,
            "available_return_bikes": 10 - bikes,
            "capacity": 10,
            "latitude": 25.03,
            "longitude": 121.56,
            "is_active": True,
        }
    )


class TrackBRegressionTests(unittest.TestCase):
    def test_split_is_fixed_chronological_18_5_5(self) -> None:
        boundaries = split_boundaries(config())
        data = sample_data()
        data = data.loc[data["snapshot_time"].lt(boundaries["test_end"])]
        split = assign_splits(data, boundaries)
        self.assertEqual(split.iloc[0], "train")
        self.assertEqual(
            split.loc[data["snapshot_time"].eq(boundaries["train_end"])].iloc[0],
            "validation",
        )
        self.assertEqual(
            split.loc[data["snapshot_time"].eq(boundaries["validation_end"])].iloc[0],
            "test",
        )

    def test_calendar_uses_taipei_and_history_is_past_only(self) -> None:
        data = sample_data().iloc[:4].copy()
        data["snapshot_time"] = pd.to_datetime(
            [
                "2026-08-21T15:45:02Z",
                "2026-08-21T16:15:02Z",
                "2026-08-21T16:45:02Z",
                "2026-08-21T17:45:02Z",
            ],
            utc=True,
        )
        data["available_bikes"] = [2, 4, 8, 6]
        featured = build_track_b_features(data, config())
        self.assertEqual(featured.iloc[0]["is_weekend"], 0)
        self.assertEqual(featured.iloc[1]["is_weekend"], 1)
        self.assertEqual(featured.iloc[2]["available_bikes_lag_30m"], 4)
        self.assertEqual(featured.iloc[2]["available_bikes_mean_past_60m"], 3)
        self.assertEqual(featured.iloc[0]["target_available_bikes_60m"], 8)

    def test_eligible_mask_purges_target_crossing_split_boundary(self) -> None:
        cfg = config()
        boundaries = split_boundaries(cfg)
        columns = feature_columns(cfg)
        row_count = 2
        featured = pd.DataFrame(
            {
                "snapshot_time": pd.to_datetime(
                    ["2026-09-08T08:44:02Z", "2026-09-08T09:30:02Z"], utc=True
                ),
                "is_active": [True, True],
                "target_available_bikes_60m": [3.0, 4.0],
                "target_60m_actual_minutes": [60.0, 60.0],
            }
        )
        for column in columns:
            featured[column] = np.ones(row_count)
        split = pd.Series(["train", "train"], dtype="category")
        mask = eligible_mask(featured, split, "train", 60, boundaries, columns)
        self.assertEqual(mask.tolist(), [True, False])

    def test_capacity_clip_and_validation_selection(self) -> None:
        clipped = capacity_clip(np.array([-2.0, 5.0, 20.0]), pd.Series([10, 10, 10]))
        self.assertEqual(clipped.tolist(), [0.0, 5.0, 10.0])
        tuning = pd.DataFrame(
            {"candidate": ["worse", "better"], "mae": [2.0, 1.0]}
        )
        self.assertEqual(select_best_candidate(tuning), "better")



if __name__ == "__main__":
    unittest.main()
