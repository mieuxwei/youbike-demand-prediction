"""Tests for leakage-aware feature engineering."""

from __future__ import annotations

import unittest

import pandas as pd

from src.features import (
    add_calendar_features,
    add_future_targets,
    add_lag_features,
    add_rolling_features,
    build_feature_coverage,
)


def example_data() -> pd.DataFrame:
    """Create an irregular station history for time-aware alignment tests."""
    timestamps = pd.to_datetime(
        [
            "2026-08-20 08:00:00",
            "2026-08-20 08:14:00",
            "2026-08-20 08:30:00",
            "2026-08-20 09:00:00",
        ]
    ).tz_localize("Asia/Taipei")
    return pd.DataFrame(
        {
            "snapshot_time": timestamps,
            "station_id": ["A"] * 4,
            "available_bikes": [10, 8, 100, 6],
            "capacity": [120] * 4,
            "is_active": pd.Series([True] * 4, dtype="boolean"),
        }
    )


class FeatureTest(unittest.TestCase):
    def test_calendar_features_use_local_timestamp(self) -> None:
        featured = add_calendar_features(example_data())

        self.assertEqual(featured.loc[0, "hour"], 8)
        self.assertEqual(featured.loc[0, "day_of_week"], 3)
        self.assertFalse(featured.loc[0, "is_weekend"])
        self.assertTrue(featured.loc[0, "is_rush_hour"])

    def test_lag_alignment_only_looks_backward(self) -> None:
        featured = add_lag_features(
            example_data(), horizons_minutes=(15,), tolerance_minutes=2
        )

        # At 08:30, the desired lag is 08:15. Backward alignment selects 08:14,
        # never the current 08:30 value of 100.
        self.assertEqual(featured.loc[2, "available_bikes_lag_15m"], 8)
        self.assertEqual(featured.loc[2, "lag_15m_actual_minutes"], 16)
        self.assertTrue(pd.isna(featured.loc[1, "available_bikes_lag_15m"]))

    def test_rolling_average_excludes_current_observation(self) -> None:
        featured = add_rolling_features(example_data(), windows_minutes=(30,))

        # The 08:30 result uses 08:00 and 08:14, not the current value of 100.
        self.assertEqual(featured.loc[2, "available_bikes_mean_past_30m"], 9)
        self.assertEqual(featured.loc[2, "observations_past_30m"], 2)

    def test_future_target_uses_forward_match_only(self) -> None:
        featured = add_future_targets(
            example_data(), horizons_minutes=(30,), tolerance_minutes=2
        )

        self.assertEqual(featured.loc[0, "target_available_bikes_30m"], 100)
        self.assertEqual(featured.loc[0, "target_30m_actual_minutes"], 30)
        self.assertTrue(pd.isna(featured.loc[3, "target_available_bikes_30m"]))

    def test_coverage_requires_positive_rolling_observation_count(self) -> None:
        featured = add_rolling_features(example_data(), windows_minutes=(30,))
        coverage = build_feature_coverage(featured).set_index("column")

        self.assertEqual(
            coverage.loc["observations_past_30m", "usable_rows"], 3
        )


if __name__ == "__main__":
    unittest.main()
