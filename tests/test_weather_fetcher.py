import pytest
import os
from unittest.mock import MagicMock, patch
from src.config import ContentSource
from src.fetchers.weather_fetcher import WeatherFetcher


class TestWeatherFetcher:
    """WeatherFetcher unit tests"""

    @pytest.fixture
    def weather_source(self):
        return ContentSource(
            type="weather",
            src="Shanghai",
            metadata={"date": "tomorrow"}
        )

    @patch.dict(os.environ, {"QWEATHER_KEY": "test_key", "QWEATHER_HOST": "test_host"})
    @patch.object(WeatherFetcher, "_make_request")
    def test_fetch_success(self, mock_make_request, weather_source):
        # Mock responses
        # 1st response: Geo lookup
        geo_response = MagicMock()
        geo_response.json.return_value = {
            "code": "200",
            "location": [{"id": "101020100", "name": "上海"}]
        }
        
        # 2nd response: Weather 3d forecast
        weather_response = MagicMock()
        weather_response.json.return_value = {
            "code": "200",
            "daily": [
                {
                    "fxDate": "2026-06-30",
                    "tempMax": "30",
                    "tempMin": "22",
                    "textDay": "晴",
                    "textNight": "多云"
                },
                {
                    "fxDate": "2026-07-01",
                    "tempMax": "31",
                    "tempMin": "23",
                    "textDay": "多云",
                    "textNight": "阴",
                    "sunrise": "04:50",
                    "sunset": "19:00",
                    "humidity": "60",
                    "precip": "0.0",
                    "uvIndex": "5"
                }
            ]
        }

        mock_make_request.side_effect = [geo_response, weather_response]

        fetcher = WeatherFetcher(weather_source)
        result = fetcher.fetch()

        assert result.success is True
        assert len(result.articles) == 1
        article = result.articles[0]
        assert "上海" in article.title
        assert "2026-07-01" in article.title
        assert "多云" in article.title
        assert "23°C 至 31°C" in article.content
        assert "04:50" in article.content

    @patch.dict(os.environ, {"QWEATHER_KEY": "test_key", "QWEATHER_HOST": "test_host"})
    @patch.object(WeatherFetcher, "_make_request")
    def test_fetch_resolve_failure(self, mock_make_request, weather_source):
        # Mock geo response failure
        geo_response = MagicMock()
        geo_response.json.return_value = {
            "code": "404",
            "msg": "Not Found"
        }
        mock_make_request.return_value = geo_response

        fetcher = WeatherFetcher(weather_source)
        result = fetcher.fetch()

        assert result.success is False
        assert "Error from API (geo lookup)" in result.error
