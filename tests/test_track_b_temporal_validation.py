"""Tests for frozen Track B independent temporal validation."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

from src.train_track_b_regression import file_sha256
from src.train_track_b_regression import feature_columns, load_config
from src.validate_track_b_temporal import (
    combine_with_stage_17,
    decision_from_evidence,
    independent_scope,
    load_frozen_model,
    load_validation_config,
    resolve_frozen_inputs,
    schedule_summary,
    validation_window,
)


FEATURES = ["available_bikes", "capacity"]


class TrackBTemporalValidationTests(unittest.TestCase):
    def test_repository_freeze_manifest_matches_real_artifacts(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config_path = root / "config/track_b_temporal_validation.json"
        validation_config = load_validation_config(config_path)
        repository_root, specifications = resolve_frozen_inputs(
            config_path, validation_config
        )
        training_config = load_config(
            repository_root / validation_config["training_config_path"]
        )
        expected_features = feature_columns(training_config)
        loaded_horizons = []
        for specification in specifications:
            model, metadata = load_frozen_model(
                repository_root, specification, expected_features
            )
            self.assertTrue(callable(model.predict))
            loaded_horizons.append(metadata["horizon_minutes"])
        self.assertEqual(sorted(loaded_horizons), [30, 60])

    def test_window_is_exactly_seven_days_with_explicit_timezones(self) -> None:
        config = {
            "history_start": "2026-09-18T17:30:00Z",
            "evaluation_start": "2026-09-18T18:30:00Z",
            "evaluation_end_exclusive": "2026-09-25T18:30:00Z",
        }
        history, start, end = validation_window(config)
        self.assertEqual(start - history, pd.Timedelta(hours=1))
        self.assertEqual(end - start, pd.Timedelta(days=7))
        config["evaluation_end_exclusive"] = "2026-09-25T18:30:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            validation_window(config)

    def test_frozen_artifact_and_metadata_hashes_are_checked_before_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "model.joblib"
            metadata_path = root / "model.metadata.json"
            model = DummyRegressor(strategy="mean").fit(
                pd.DataFrame([[1, 10], [2, 10]], columns=FEATURES),
                np.array([1, 2]),
            )
            joblib.dump(model, artifact)
            artifact_hash = file_sha256(artifact)
            metadata = {
                "artifact_sha256": artifact_hash,
                "horizon_minutes": 30,
                "target": "target_available_bikes_30m",
                "feature_columns": FEATURES,
            }
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            specification = {
                "horizon_minutes": 30,
                "artifact_path": artifact.name,
                "artifact_sha256": artifact_hash,
                "metadata_path": metadata_path.name,
                "metadata_sha256": file_sha256(metadata_path),
                "stage_17_holdout": {},
            }
            loaded, loaded_metadata = load_frozen_model(root, specification, FEATURES)
            self.assertTrue(callable(loaded.predict))
            self.assertEqual(loaded_metadata["horizon_minutes"], 30)
            artifact.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "artifact checksum"):
                load_frozen_model(root, specification, FEATURES)

    def test_scope_uses_complete_rows_and_purges_targets_crossing_end(self) -> None:
        start = pd.Timestamp("2026-09-18T18:30:00Z")
        end = pd.Timestamp("2026-09-18T20:00:00Z")
        featured = pd.DataFrame(
            {
                "snapshot_time": pd.to_datetime(
                    ["2026-09-18T18:30:00Z", "2026-09-18T19:15:00Z"], utc=True
                ),
                "is_active": [True, True],
                "available_bikes": [3.0, 4.0],
                "capacity": [10.0, np.nan],
                "target_available_bikes_60m": [5.0, 6.0],
                "target_60m_actual_minutes": [60.0, 60.0],
            }
        )
        scope, coverage = independent_scope(featured, start, end, 60, FEATURES)
        self.assertEqual(scope.tolist(), [True, False])
        self.assertEqual(coverage["usable_rows"], 1)

    def test_schedule_summary_counts_expected_slots_and_internal_gaps(self) -> None:
        times = pd.to_datetime(
            [
                "2026-09-18T18:30:00Z",
                "2026-09-18T18:35:00Z",
                "2026-09-18T18:45:00Z",
                "2026-09-18T18:50:00Z",
            ],
            utc=True,
        )
        data = pd.DataFrame(
            {
                "snapshot_time": times,
                "station_id": pd.Series(["A"] * 4, dtype="category"),
            }
        )
        summary, gaps = schedule_summary(
            data,
            times[0],
            pd.Timestamp("2026-09-18T18:55:00Z"),
            expected_interval_minutes=5,
            gap_threshold_minutes=5.5,
        )
        self.assertEqual(summary["expected_snapshots"], 5)
        self.assertEqual(summary["observed_snapshots"], 4)
        self.assertEqual(summary["estimated_missing_slots"], 1)
        self.assertEqual(len(gaps), 1)

    def test_pre_registered_decision_does_not_promote_mixed_evidence(self) -> None:
        config = {
            "minimum_mae_improvement_percent": 0.0,
            "minimum_rmse_improvement_percent": 0.0,
            "minimum_station_improvement_percent": 50.0,
        }
        passed = decision_from_evidence(
            True,
            {"mae": 1.8, "rmse": 2.8},
            {"mae": 2.0, "rmse": 3.0},
            55.0,
            config,
        )
        self.assertEqual(passed["status"], "frozen_learned_model_passes_temporal_gate")
        mixed = decision_from_evidence(
            True,
            {"mae": 1.8, "rmse": 3.1},
            {"mae": 2.0, "rmse": 3.0},
            55.0,
            config,
        )
        self.assertEqual(mixed["status"], "mixed_evidence_no_promotion")
        failed = decision_from_evidence(
            True,
            {"mae": 2.1, "rmse": 2.8},
            {"mae": 2.0, "rmse": 3.0},
            55.0,
            config,
        )
        self.assertEqual(failed["status"], "persistence_remains_primary_baseline")
        self.assertEqual(
            combine_with_stage_17(
                passed, {"primary_mae_gate_passed": False}
            ),
            "mixed_across_windows_keep_persistence_baseline",
        )
        self.assertEqual(
            combine_with_stage_17(
                passed, {"primary_mae_gate_passed": True}
            ),
            "learned_model_confirmed_across_both_windows",
        )
        data_failure = decision_from_evidence(
            False,
            {"mae": 1.8, "rmse": 2.8},
            {"mae": 2.0, "rmse": 3.0},
            55.0,
            config,
        )
        self.assertEqual(
            combine_with_stage_17(
                data_failure, {"primary_mae_gate_passed": True}
            ),
            "independent_data_quality_failed_no_model_decision",
        )


if __name__ == "__main__":
    unittest.main()
