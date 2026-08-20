"""Tests for snapshot validation, cleaning, and change features."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.data_pipeline import (
    add_change_features,
    clean_snapshots,
    load_snapshot,
)


def make_record(
    snapshot_time: str,
    available_bikes: int,
    station_id: str = "500101001",
) -> dict[str, object]:
    """Create one minimal valid API record for a test."""
    return {
        "srcUpdateTime": snapshot_time,
        "mday": snapshot_time,
        "sno": station_id,
        "sna": "YouBike2.0_Test Station",
        "sarea": "Test District",
        "ar": "Test Address",
        "latitude": 25.0,
        "longitude": 121.5,
        "Quantity": 20,
        "available_rent_bikes": available_bikes,
        "available_return_bikes": 18 - available_bikes,
        "act": "1",
    }


class DataPipelineTest(unittest.TestCase):
    def test_load_snapshot_rejects_missing_required_field(self) -> None:
        record = make_record("2026-08-20 10:00:00", 10)
        del record["sno"]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps([record]), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing required fields: sno"):
                load_snapshot(path)

    def test_clean_snapshots_normalizes_and_derives_fields(self) -> None:
        raw = pd.DataFrame([make_record("2026-08-20 10:00:00", 10)])
        raw["source_file"] = "test.json"

        clean = clean_snapshots(raw)

        self.assertEqual(clean.loc[0, "station_id"], "500101001")
        self.assertEqual(clean.loc[0, "unavailable_docks"], 2)
        self.assertAlmostEqual(clean.loc[0, "availability_rate"], 0.5)
        self.assertTrue(clean.loc[0, "is_active"])
        self.assertEqual(str(clean.loc[0, "snapshot_time"].tz), "Asia/Taipei")

    def test_change_features_use_consecutive_active_snapshots(self) -> None:
        raw = pd.DataFrame(
            [
                make_record("2026-08-20 10:00:00", 10),
                make_record("2026-08-20 10:15:00", 7),
            ]
        )
        raw["source_file"] = ["first.json", "second.json"]

        featured = add_change_features(clean_snapshots(raw))

        self.assertTrue(pd.isna(featured.loc[0, "bike_net_change"]))
        self.assertEqual(featured.loc[1, "elapsed_minutes"], 15)
        self.assertEqual(featured.loc[1, "bike_net_change"], -3)
        self.assertEqual(featured.loc[1, "estimated_net_outflow"], 3)


if __name__ == "__main__":
    unittest.main()
