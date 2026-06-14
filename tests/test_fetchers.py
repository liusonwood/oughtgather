"""
抓取器测试（使用 mock 模拟 HTTP 请求）
测试 RSSFetcher、WebFetcher、MailFetcher、TrendingFetcher
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from urllib.parse import quote

from src.config import ContentSource
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.web_fetcher import WebFetcher
from src.fetchers.mail_fetcher import MailFetcher
from src.fetchers.trending_fetcher import TrendingFetcher


# =========================================================================
# Article / FetchResult 数据类测试
# =========================================================================

class TestArticle:
    """Article 数据类测试"""

    def test_article_creation(self):
        article = Article(
            title="Test",
            content="<p>Hello</p>",
            url="https://example.com",
        )
        assert article.title == "Test"
        assert article.content == "<p>Hello</p>"
        assert article.url == "https://example.com"
        assert article.author is None
        assert article.images == []
        assert article.metadata == {}

    def test_article_to_dict(self):
        article = Article(
            title="Test",
            content="<p>Hello</p>",
            url="https://example.com",
            author="Author",
        )
        d = article.to_dict()
        assert d["title"] == "Test"
        assert d["url"] == "https://example.com"
        assert d["author"] == "Author"


class TestFetchResult:
    """FetchResult 数据类测试"""

    def test_fetch_result_defaults(self):
        source = ContentSource(type="rss", src="https://example.com")
        result = FetchResult(source=source, articles=[])
        assert result.success is True
        assert result.error is None
        assert result.error_count == 0

    def test_add_error(self):
        source = ContentSource(type="rss", src="https://example.com")
        result = FetchResult(source=source, articles=[])
        result.add_error("Error 1")
        assert result.error == "Error 1"
        assert result.error_count == 1
        result.add_error("Error 2")
        assert "Error 1" in result.error
        assert "Error 2" in result.error
        assert result.error_count == 2


# =========================================================================
# BaseFetcher._should_delete 测试
# =========================================================================

class TestBaseFetcherShouldDelete:
    """BaseFetcher._should_delete 测试"""

    def _make_fetcher(self, source):
        """构造一个具体的 BaseFetcher 子类用于测试"""

        class DummyFetcher(BaseFetcher):
            def fetch(self):
                return FetchResult(source=self.source, articles=[])

        return DummyFetcher(source)

    def test_no_delete_config(self):
        source = ContentSource(type="rss", src="test")
        fetcher = self._make_fetcher(source)
        assert fetcher._should_delete("任何标题") is False

    def test_delete_matches(self):
        source = ContentSource(type="rss", src="test", delete="广告,推广")
        fetcher = self._make_fetcher(source)
        assert fetcher._should_delete("这是一条广告") is True
        assert fetcher._should_delete("推广内容") is True

    def test_delete_no_match(self):
        source = ContentSource(type="rss", src="test", delete="广告,推广")
        fetcher = self._make_fetcher(source)
        assert fetcher._should_delete("正常文章") is False


# =========================================================================
# RSSFetcher 测试
# =========================================================================

def _make_feedparser_dict(d):
    """模拟 feedparser 的 FeedParserDict，同时支持 dict 和属性访问"""
    class FeedParserDict(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)
    return FeedParserDict(d)


class TestRSSFetcher:
    """RSSFetcher 测试（mock feedparser）"""

    @patch("src.fetchers.rss_fetcher.feedparser.parse")
    def test_parse_entries(self, mock_parse, rss_source):
        """测试解析 RSS 条目"""
        # feedparser 返回的对象同时支持 dict 和属性访问
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "Test Feed"}
        mock_feed.entries = [
            _make_feedparser_dict({
                "title": "Entry 1",
                "link": "https://example.com/1",
                "author": "Author 1",
                "published": "2024-01-01",
                "content": [_make_feedparser_dict({"value": "<p>Content 1</p>"})],
                "tags": [{"term": "python"}],
            }),
            _make_feedparser_dict({
                "title": "Entry 2",
                "link": "https://example.com/2",
                "summary": "<p>Summary 2</p>",
                "tags": [],
            }),
        ]
        mock_parse.return_value = mock_feed

        fetcher = RSSFetcher(rss_source)
        result = fetcher.fetch()

        assert result.success is True
        assert len(result.articles) == 2
        assert result.articles[0].title == "Entry 1"
        assert result.articles[0].content == "<p>Content 1</p>"
        assert result.articles[1].content == "<p>Summary 2</p>"
        assert result.source_title == "Test Feed"

    @patch("src.fetchers.rss_fetcher.feedparser.parse")
    def test_bozo_with_no_entries(self, mock_parse, rss_source):
        """测试 bozo 且无条目时返回失败"""
        mock_parse.return_value = MagicMock(
            bozo=True,
            entries=[],
            bozo_exception="Parse error",
        )

        fetcher = RSSFetcher(rss_source)
        result = fetcher.fetch()

        assert result.success is False
        assert "Failed to parse" in result.error

    @patch("src.fetchers.rss_fetcher.feedparser.parse")
    def test_delete_filters_articles(self, mock_parse):
        """测试 delete 关键词过滤文章"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            delete="广告",
        )
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {}
        mock_feed.entries = [
            _make_feedparser_dict({
                "title": "正常文章",
                "content": [_make_feedparser_dict({"value": "<p>OK</p>"})],
                "tags": [],
            }),
            _make_feedparser_dict({
                "title": "这是广告",
                "content": [_make_feedparser_dict({"value": "<p>AD</p>"})],
                "tags": [],
            }),
        ]
        mock_parse.return_value = mock_feed

        fetcher = RSSFetcher(source)
        result = fetcher.fetch()

        assert len(result.articles) == 1
        assert result.articles[0].title == "正常文章"

    @patch("src.fetchers.rss_fetcher.feedparser.parse")
    def test_fallback_summary_fields(self, mock_parse, rss_source):
        """测试 content → summary → description 回退"""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {}
        mock_feed.entries = [
            _make_feedparser_dict({
                "title": "No Content",
                "description": "<p>Desc</p>",
                "tags": [],
            }),
        ]
        mock_parse.return_value = mock_feed

        fetcher = RSSFetcher(rss_source)
        result = fetcher.fetch()

        assert result.articles[0].content == "<p>Desc</p>"


# =========================================================================
# WebFetcher 测试
# =========================================================================

class TestWebFetcher:
    """WebFetcher 测试（mock httpx）"""

    @patch("src.fetchers.web_fetcher.trafilatura.extract")
    @patch.object(WebFetcher, "_make_request")
    def test_extract_content(self, mock_request, mock_extract, web_source):
        """测试网页正文提取"""
        mock_response = MagicMock()
        mock_response.text = "<html><body><article><p>正文</p></article></body></html>"
        mock_request.return_value = mock_response
        mock_extract.return_value = "<p>正文</p>"

        fetcher = WebFetcher(web_source)
        result = fetcher.fetch()

        assert result.success is True
        assert len(result.articles) == 1
        assert result.articles[0].content == "<p>正文</p>"

    @patch("src.fetchers.web_fetcher.trafilatura.extract")
    @patch.object(WebFetcher, "_make_request")
    def test_trafilatura_fails_fallback(self, mock_request, mock_extract, web_source):
        """测试 trafilatura 失败时回退到 BeautifulSoup"""
        mock_response = MagicMock()
        mock_response.text = "<html><body><article><p>备用内容</p></article></body></html>"
        mock_request.return_value = mock_response
        mock_extract.return_value = None  # trafilatura 失败

        fetcher = WebFetcher(web_source)
        result = fetcher.fetch()

        assert result.success is True
        assert "备用内容" in result.articles[0].content

    @patch.object(WebFetcher, "_make_request")
    def test_extract_title_from_h1(self, mock_request):
        """测试从 <h1> 提取标题"""
        source = ContentSource(type="web", src="https://example.com")
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>文章标题</h1><article><p>内容</p></article></body></html>"
        mock_request.return_value = mock_response

        with patch("src.fetchers.web_fetcher.trafilatura.extract", return_value="<p>内容</p>"):
            fetcher = WebFetcher(source)
            result = fetcher.fetch()
            assert result.articles[0].title == "文章标题"

    @patch.object(WebFetcher, "_make_request")
    def test_title_fallback_to_config(self, mock_request):
        """测试标题回退到配置中的 title"""
        source = ContentSource(type="web", src="https://example.com", title="自定义标题")
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>无标题的页面</p></body></html>"
        mock_request.return_value = mock_response

        with patch("src.fetchers.web_fetcher.trafilatura.extract", return_value="<p>内容</p>"):
            fetcher = WebFetcher(source)
            result = fetcher.fetch()
            # 没有 <title>/<h1>/og:title 时回退到 source.title
            assert result.articles[0].title == "自定义标题"


# =========================================================================
# MailFetcher 测试
# =========================================================================

class TestMailFetcher:
    """MailFetcher 测试（mock httpx + API key）"""

    @patch.dict("os.environ", {"TESTMAIL_APP_API_KEY": "test_key_123"})
    @patch.object(MailFetcher, "_make_request")
    def test_fetch_emails(self, mock_request, mail_source):
        """测试邮件抓取"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": "success",
            "emails": [
                {
                    "subject": "邮件 1",
                    "from": "sender@example.com",
                    "to": "test@testmail.app",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "html": "<p>邮件内容</p>",
                    "attachments": [],
                }
            ],
        }
        mock_request.return_value = mock_response

        fetcher = MailFetcher(mail_source)
        result = fetcher.fetch()

        assert result.success is True
        assert len(result.articles) == 1
        assert result.articles[0].title == "邮件 1"
        assert result.articles[0].author == "sender@example.com"

    @patch.dict("os.environ", {"TESTMAIL_APP_API_KEY": "test_key_123"})
    @patch.object(MailFetcher, "_make_request")
    def test_api_error(self, mock_request, mail_source):
        """测试 API 返回错误"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": "error",
            "message": "Invalid API key",
        }
        mock_request.return_value = mock_response

        fetcher = MailFetcher(mail_source)
        result = fetcher.fetch()

        assert result.success is False
        assert "Invalid API key" in result.error

    @patch.dict("os.environ", {}, clear=True)
    def test_no_api_key(self, mail_source, monkeypatch):
        """测试未配置 API key 时跳过"""
        monkeypatch.delenv("TESTMAIL_APP_API_KEY", raising=False)

        fetcher = MailFetcher(mail_source)
        result = fetcher.fetch()

        assert result.success is False
        assert "not configured" in result.error

    @patch.dict("os.environ", {"TESTMAIL_APP_API_KEY": "test_key_123"})
    @patch.object(MailFetcher, "_make_request")
    def test_namespace_url_encoded(self, mock_request):
        """测试 namespace.tag 格式被正确拆分"""
        source = ContentSource(
            type="mail", src="my.namespace",
            title="Test",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success", "emails": []}
        mock_request.return_value = mock_response

        fetcher = MailFetcher(source)
        result = fetcher.fetch()

        # 验证 namespace 和 tag 被正确拆分
        call_args = mock_request.call_args
        api_url = call_args[0][0]
        assert "namespace=my" in api_url
        assert "tag=namespace" in api_url

    @patch.dict("os.environ", {"TESTMAIL_APP_API_KEY": "test_key_123"})
    @patch.object(MailFetcher, "_make_request")
    def test_metadata_query_params(self, mock_request):
        """测试 metadata 参数正确构建到请求 URL 中"""
        source = ContentSource(
            type="mail", src="testns",
            metadata={"tag": "daily", "limit": 10, "timestamp_from": 1718300000000},
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success", "emails": []}
        mock_request.return_value = mock_response

        fetcher = MailFetcher(source)
        result = fetcher.fetch()

        api_url = mock_request.call_args[0][0]
        assert "tag=daily" in api_url
        assert "limit=10" in api_url
        assert "timestamp_from=1718300000000" in api_url


# =========================================================================
# TrendingFetcher 测试
# =========================================================================

class TestTrendingFetcher:
    """TrendingFetcher 测试（mock httpx + API key）"""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key_456"})
    @patch("httpx.Client")
    def test_fetch_analysis(self, mock_client_cls, trending_source):
        """测试 LLM 分析请求"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "# AI 趋势\n\n最新发展概述\n\n- 要点1\n- 要点2"
                    }
                }
            ]
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        fetcher = TrendingFetcher(trending_source)
        result = fetcher.fetch()

        assert result.success is True
        assert len(result.articles) == 1
        assert result.articles[0].title == "AI 热点"
        assert result.articles[0].author == "AI Analysis"
        assert "<h1>" in result.articles[0].content or "<p>" in result.articles[0].content

    @patch.dict("os.environ", {}, clear=True)
    def test_no_api_key(self, trending_source, monkeypatch):
        """测试未配置 API key"""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        fetcher = TrendingFetcher(trending_source)
        result = fetcher.fetch()

        assert result.success is False
        assert "not configured" in result.error

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key_456"})
    def test_title_default(self, monkeypatch):
        """测试 trending 默认标题"""
        source = ContentSource(
            type="trending", src="AI 趋势",
            goal="分析 AI",
        )
        with patch("src.fetchers.trending_fetcher.TrendingFetcher._call_llm_api", return_value="<p>内容</p>"):
            fetcher = TrendingFetcher(source)
            result = fetcher.fetch()
            assert result.articles[0].title == "热点分析: AI 趋势"

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key_456"})
    def test_format_as_html_paragraphs(self, trending_source):
        """测试文本转 HTML 的段落处理"""
        fetcher = TrendingFetcher(trending_source)
        text = "第一段内容\n\n第二段内容\n\n第三段内容"
        html = fetcher._format_as_html(text)
        assert "<p>第一段内容</p>" in html
        assert "<p>第二段内容</p>" in html
        assert "<p>第三段内容</p>" in html

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key_456"})
    def test_format_as_html_headings(self, trending_source):
        """测试文本转 HTML 的标题处理"""
        fetcher = TrendingFetcher(trending_source)
        text = "# 一级标题\n\n内容\n\n## 二级标题\n\n更多内容"
        html = fetcher._format_as_html(text)
        assert "<h1>一级标题</h1>" in html
        assert "<h2>二级标题</h2>" in html

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test_key_456"})
    def test_format_as_html_list(self, trending_source):
        """测试文本转 HTML 的列表处理"""
        fetcher = TrendingFetcher(trending_source)
        text = "- 项目一\n- 项目二\n- 项目三"
        html = fetcher._format_as_html(text)
        assert "<ul>" in html
        assert "<li>项目一</li>" in html
        assert "<li>项目二</li>" in html
        assert "</ul>" in html
