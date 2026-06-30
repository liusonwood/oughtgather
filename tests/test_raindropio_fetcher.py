import pytest
from unittest.mock import MagicMock, patch
from src.config import ContentSource
from src.fetchers.raindropio_fetcher import RaindropFetcher

class TestRaindropFetcher:
    """RaindropioFetcher 测试"""

    @patch.dict("os.environ", {"RAINDROPIO_API_KEY": "test_key_123"})
    @patch.object(RaindropFetcher, "_make_request")
    def test_fetch_bookmarks(self, mock_request):
        """测试书签抓取"""
        # 模拟 Raindrop API 响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": True,
            "items": [
                {
                    "title": "Bookmark 1",
                    "link": "https://example.com/1",
                    "excerpt": "Excerpt 1",
                    "cover": "https://example.com/1.jpg"
                }
            ]
        }
        mock_request.return_value = mock_response

        # 配置源
        source = ContentSource(
            type="raindropio", 
            src="0", 
            metadata={"collection_id": "0"}
        )

        fetcher = RaindropFetcher(source)
        result = fetcher.fetch()

        assert result.success is True
        assert len(result.articles) == 1
        assert result.articles[0].title == "Bookmark 1"
        assert result.articles[0].url == "https://example.com/1"
        assert "Excerpt 1" in result.articles[0].content
        assert result.articles[0].images == ["https://example.com/1.jpg"]

    @patch.dict("os.environ", {"RAINDROPIO_API_KEY": "test_key_123"})
    @patch.object(RaindropFetcher, "_make_request")
    def test_api_error(self, mock_request):
        """测试 API 返回错误"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": False,
            "message": "Invalid API key"
        }
        mock_request.return_value = mock_response

        source = ContentSource(type="raindropio", src="0")
        fetcher = RaindropFetcher(source)
        result = fetcher.fetch()

        assert result.success is False
        assert "Invalid API key" in result.error
