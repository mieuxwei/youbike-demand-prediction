"""Tests for weather download configuration and atomic output."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.download_weather import build_weather_params, download_weather


CONFIG = {
    "endpoint": "https://example.test/weather",
    "latitude": 25.0,
    "longitude": 121.5,
    "start_date": "2023-01-01",
    "end_date": "2023-01-02",
    "timezone": "Asia/Taipei",
    "hourly_variables": ["temperature_2m", "precipitation"],
}


class WeatherDownloadTest(unittest.TestCase):
    def test_params_include_timezone_and_hourly_variables(self) -> None:
        params = build_weather_params(CONFIG)
        self.assertEqual(params["timezone"], "Asia/Taipei")
        self.assertEqual(params["hourly"], "temperature_2m,precipitation")

    @patch("src.download_weather.requests.get")
    def test_download_writes_valid_response(self, mock_get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"hourly": {"time": []}}
        mock_get.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "weather.json"
            download_weather(CONFIG, output)
            self.assertTrue(output.exists())
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
