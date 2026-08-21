"""Tests for the bounded Track A XGBoost configuration and pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.xgboost_model import (
    build_xgboost_pipeline,
    load_xgboost_config,
    xgboost_feature_columns,
)


CONFIG = {
    "model_name": "xgboost_weather",
    "objective": "count:poisson",
    "eval_metric": "mae",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": 1,
    "candidates": [
        {
            "candidate": "tiny",
            "n_estimators": 5,
            "learning_rate": 0.1,
            "max_depth": 2,
            "min_child_weight": 1.0,
            "subsample": 1.0,
            "colsample_bytree": 1.0,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
        }
    ],
}


class XGBoostModelTests(unittest.TestCase):
    def test_config_requires_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({**CONFIG, "candidates": []}))
            with self.assertRaisesRegex(ValueError, "At least one"):
                load_xgboost_config(path)

    def test_pipeline_fits_same_non_weather_feature_scope(self) -> None:
        rows = 20
        frame = pd.DataFrame(
            {
                "station_name": ["甲站", "乙站"] * (rows // 2),
                "hour_sin": [0.0, 1.0] * (rows // 2),
                "hour_cos": [1.0, 0.0] * (rows // 2),
                "weekday_sin": 0.0,
                "weekday_cos": 1.0,
                "month_sin": 0.0,
                "month_cos": 1.0,
                "is_weekend": False,
                "borrow_lag_1h": [0, 2] * (rows // 2),
                "return_lag_1h": [1, 2] * (rows // 2),
                "borrow_lag_24h": [0, 2] * (rows // 2),
                "borrow_lag_168h": [0, 2] * (rows // 2),
                "borrow_rolling_mean_24h": [0.5, 2.0] * (rows // 2),
            }
        )
        target = pd.Series([0, 3] * (rows // 2))
        pipeline = build_xgboost_pipeline(
            CONFIG["candidates"][0], CONFIG, include_weather=False
        )
        pipeline.fit(frame[xgboost_feature_columns(False)], target)
        prediction = pipeline.predict(frame[xgboost_feature_columns(False)])
        self.assertEqual(len(prediction), rows)
        self.assertTrue((prediction >= 0).all())


if __name__ == "__main__":
    unittest.main()
