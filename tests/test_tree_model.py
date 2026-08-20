"""Tests for tree pipelines and rolling-origin evaluation windows."""

from __future__ import annotations

import unittest

import pandas as pd

from src.tree_model import build_rolling_origin_splits, build_tree_pipeline


CANDIDATE = {
    "learning_rate": 0.1,
    "max_iter": 10,
    "max_leaf_nodes": 7,
    "min_samples_leaf": 2,
    "l2_regularization": 1.0,
}


class TreeModelTest(unittest.TestCase):
    def test_tree_pipeline_fits_station_category_and_numeric_features(self) -> None:
        frame = pd.DataFrame(
            {
                "station_name": ["甲站", "甲站", "乙站", "乙站"] * 5,
                "hour_sin": [0.0, 1.0, 0.0, 1.0] * 5,
                "hour_cos": [1.0, 0.0, 1.0, 0.0] * 5,
                "weekday_sin": 0.0,
                "weekday_cos": 1.0,
                "month_sin": 0.0,
                "month_cos": 1.0,
                "is_weekend": False,
                "borrow_lag_1h": [0, 1, 2, 3] * 5,
                "return_lag_1h": [0, 1, 1, 2] * 5,
                "borrow_lag_24h": [0, 1, 2, 3] * 5,
                "borrow_lag_168h": [0, 1, 2, 3] * 5,
                "borrow_rolling_mean_24h": [0, 1, 2, 3] * 5,
            }
        )
        target = pd.Series([0, 1, 2, 3] * 5)
        pipeline = build_tree_pipeline(False, CANDIDATE)
        pipeline.fit(frame, target)
        self.assertEqual(len(pipeline.predict(frame)), len(frame))

    def test_rolling_origin_windows_expand_without_overlap(self) -> None:
        frame = pd.DataFrame(
            {
                "event_time": pd.date_range(
                    "2023-01-01", periods=8, freq="h", tz="Asia/Taipei"
                )
            }
        )
        folds = [
            {
                "fold": "one",
                "train_end": "2023-01-01T02:00:00+08:00",
                "validation_end": "2023-01-01T04:00:00+08:00",
            },
            {
                "fold": "two",
                "train_end": "2023-01-01T04:00:00+08:00",
                "validation_end": "2023-01-01T07:00:00+08:00",
            },
        ]
        outputs = build_rolling_origin_splits(frame, folds)
        self.assertEqual(len(outputs[0][1]), 3)
        self.assertEqual(len(outputs[0][2]), 2)
        self.assertEqual(len(outputs[1][1]), 5)
        self.assertEqual(len(outputs[1][2]), 3)


if __name__ == "__main__":
    unittest.main()
