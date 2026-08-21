"""Tests for Track A feature ablation and contextual error analysis."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.track_a_analysis import (
    OFFICIAL_DAY_FEATURE,
    add_error_contexts,
    add_official_calendar_features,
    assign_station_demand_tiers,
    build_ablation_pipeline,
    build_feature_variants,
    load_analysis_config,
    summarize_errors,
)


CONFIG_PATH = Path("config/track_a_analysis.json")
CANDIDATE = {
    "learning_rate": 0.1,
    "max_iter": 10,
    "max_leaf_nodes": 7,
    "min_samples_leaf": 2,
    "l2_regularization": 1.0,
}


class TrackAAnalysisTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_analysis_config(CONFIG_PATH)

    def test_official_calendar_distinguishes_holiday_and_makeup_workday(self) -> None:
        frame = pd.DataFrame(
            {
                "event_time": pd.to_datetime(
                    [
                        "2023-01-02T08:00:00+08:00",
                        "2023-01-07T08:00:00+08:00",
                        "2023-01-08T08:00:00+08:00",
                        "2023-01-09T08:00:00+08:00",
                    ],
                    utc=True,
                ).tz_convert("Asia/Taipei")
            }
        )
        output = add_official_calendar_features(
            frame, self.config["official_calendar"]
        )
        self.assertEqual(
            output[OFFICIAL_DAY_FEATURE].tolist(), [True, False, True, False]
        )
        self.assertEqual(
            output["official_day_type"].tolist(),
            [
                "weekday_day_off",
                "weekend_makeup_workday",
                "weekend_day_off",
                "regular_workday",
            ],
        )

    def test_feature_variants_remove_exactly_one_configured_group(self) -> None:
        variants = build_feature_variants(self.config)
        full = set(variants["full"])
        for name, features in self.config["feature_groups"].items():
            self.assertEqual(
                set(variants[f"without_{name}"]), full - set(features)
            )
        self.assertIn(
            OFFICIAL_DAY_FEATURE, variants["full_plus_official_day_off"]
        )
        self.assertNotIn("borrow_count", set().union(*map(set, variants.values())))

    def test_pipeline_can_fit_without_station_identity(self) -> None:
        frame = pd.DataFrame(
            {
                "borrow_lag_1h": [0, 1, 2, 3] * 5,
                "borrow_lag_168h": [0, 1, 2, 3] * 5,
            }
        )
        target = pd.Series([0, 1, 2, 3] * 5)
        pipeline = build_ablation_pipeline(
            ["borrow_lag_1h", "borrow_lag_168h"], CANDIDATE
        )
        pipeline.fit(frame, target)
        self.assertEqual(len(pipeline.predict(frame)), len(frame))

    def test_station_tiers_use_training_activity(self) -> None:
        training = pd.DataFrame(
            {
                "station_name": ["low", "mid", "high"] * 2,
                "borrow_count": [0, 1, 5, 0, 2, 7],
            }
        )
        test = pd.DataFrame({"station_name": ["high", "low", "mid"]})
        output, station_table = assign_station_demand_tiers(
            training, test, "borrow_count"
        )
        tier_by_station = station_table.set_index("station_name")[
            "station_demand_tier"
        ].to_dict()
        self.assertEqual(tier_by_station, {"low": "low", "mid": "medium", "high": "high"})
        self.assertEqual(output.iloc[0]["station_demand_tier"], "high")

    def test_context_thresholds_and_error_summary_are_deterministic(self) -> None:
        training = pd.DataFrame(
            {
                "precipitation_mm": [0.0, 1.0, 3.0, 5.0],
                "temperature_c": [10.0, 20.0, 30.0, 40.0],
            }
        )
        test = pd.DataFrame(
            {
                "event_time": pd.to_datetime(
                    ["2023-12-01T08:00:00+08:00", "2023-12-01T12:00:00+08:00"],
                    utc=True,
                ).tz_convert("Asia/Taipei"),
                "borrow_count": [4.0, 0.0],
                "prediction": [2.0, 1.0],
                "signed_error": [2.0, -1.0],
                "absolute_error": [2.0, 1.0],
                "precipitation_mm": [0.0, 4.0],
                "temperature_c": [15.0, 35.0],
            }
        )
        output, thresholds = add_error_contexts(
            training, test, "borrow_count", {"morning_peak": [7, 8, 9]}
        )
        self.assertEqual(thresholds["rainy_hour_training_median_mm"], 3.0)
        summary = summarize_errors(output, "borrow_count", ["peak_period"])
        overall_squared_error = np.square(test["signed_error"]).sum()
        reconstructed = sum(
            row.rows * row.rmse**2 for row in summary.itertuples(index=False)
        )
        self.assertAlmostEqual(reconstructed, overall_squared_error)


if __name__ == "__main__":
    unittest.main()
