"""Tests for reproducible historical-data downloads."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from src.download_historical import download_resource, select_resources


class HistoricalDownloadTest(unittest.TestCase):
    def test_select_resources_supports_all_and_specific_months(self) -> None:
        config = {
            "resources": {
                "2023-02": {"url": "two", "filename": "two.csv"},
                "2023-01": {"url": "one", "filename": "one.csv"},
            }
        }

        self.assertEqual(
            [month for month, _ in select_resources(config, ["all"])],
            ["2023-01", "2023-02"],
        )
        self.assertEqual(
            [month for month, _ in select_resources(config, ["2023-02"])],
            ["2023-02"],
        )

    @patch("src.download_historical.requests.get")
    def test_download_streams_to_final_path(self, mock_get: Mock) -> None:
        response = Mock()
        response.iter_content.return_value = [b"header\n", b"value\n"]
        mock_get.return_value = response

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "history.csv"
            result = download_resource("https://example.test/history.csv", output_path)

            self.assertEqual(result.read_bytes(), b"header\nvalue\n")
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])
            response.raise_for_status.assert_called_once()

    @patch("src.download_historical.requests.get")
    def test_failed_download_removes_temporary_file(self, mock_get: Mock) -> None:
        response = Mock()
        response.iter_content.side_effect = requests.ConnectionError("interrupted")
        mock_get.return_value = response

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "history.csv"
            with self.assertRaises(requests.ConnectionError):
                download_resource("https://example.test/history.csv", output_path)

            self.assertFalse(output_path.exists())
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
