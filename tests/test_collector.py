"""Tests for the YouBike API snapshot collector."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.collect_youbike import fetch_snapshot, save_snapshot


def valid_record() -> dict[str, object]:
    """Return the minimal confirmed schema used by the collector."""
    return {
        "sno": "500101001",
        "sna": "YouBike2.0_Test Station",
        "sarea": "Test District",
        "mday": "2026-08-20 10:00:00",
        "Quantity": 20,
        "available_rent_bikes": 10,
        "available_return_bikes": 8,
    }


class CollectorTest(unittest.TestCase):
    @patch("src.collect_youbike.requests.get")
    def test_fetch_snapshot_validates_all_records(self, mock_get: Mock) -> None:
        invalid_record = valid_record()
        del invalid_record["sno"]
        response = Mock()
        response.json.return_value = [valid_record(), invalid_record]
        mock_get.return_value = response

        with self.assertRaisesRegex(ValueError, "Station record 1"):
            fetch_snapshot()

    @patch("src.collect_youbike.requests.get")
    def test_fetch_snapshot_returns_valid_records(self, mock_get: Mock) -> None:
        response = Mock()
        response.json.return_value = [valid_record()]
        mock_get.return_value = response

        records = fetch_snapshot()

        response.raise_for_status.assert_called_once()
        self.assertEqual(records[0]["sno"], "500101001")

    def test_save_snapshot_uses_atomic_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_directory = Path(directory)
            output_path = save_snapshot([valid_record()], output_directory)

            self.assertTrue(output_path.exists())
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8"))[0]["sno"],
                "500101001",
            )
            self.assertEqual(list(output_directory.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
