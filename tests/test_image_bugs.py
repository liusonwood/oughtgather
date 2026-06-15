
import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup
from ebooklib import epub

from src.fetchers.web_fetcher import WebFetcher
from src.epub.generator import EPUBGenerator
from src.config import ContentSource, Config, _parse_config
from src.fetchers.base import Article, FetchResult

class TestImageBugs:
    """Specialized tests for image-related bugs."""

    def test_lazy_loading_extraction(self):
        """Test Bug 3: Lazy loading attributes extraction."""
        source = ContentSource(type="web", src="https://example.com", title="Test")
        fetcher = WebFetcher(source)
        
        html = """
        <html>
            <body>
                <img src="placeholder.gif" data-src="https://example.com/real-image.jpg">
                <img data-original="https://example.com/real-image-2.jpg">
                <img src="https://example.com/normal.jpg">
            </body>
        </html>
        """
        
        images = fetcher._extract_images(html)
        assert "https://example.com/real-image.jpg" in images
        assert "https://example.com/real-image-2.jpg" in images
        assert "https://example.com/normal.jpg" in images
        # placeholder.gif should be ignored if data-src is present
        assert "placeholder.gif" not in images

    def test_image_replacement_with_encoding(self):
        """Test Bug 2: URL encoding mismatch (& vs &amp;)."""
        config_data = {
            "title": {"text": "Test", "img": ""},
            "body": [{"type": "web", "src": "https://example.com", "title": "Test"}]
        }
        config = _parse_config(config_data)
        generator = EPUBGenerator(config)
        
        # HTML with encoded ampersand
        url_with_amp = "https://example.com/img?w=800&h=600"
        html_content = f'<div><img src="https://example.com/img?w=800&amp;h=600"></div>'
        
        article = Article(
            title="Test",
            content=html_content,
            url="https://example.com",
            images=[url_with_amp]
        )
        
        chapter = epub.EpubHtml(title="Test", file_name="test.xhtml")
        chapter.content = generator._generate_chapter_content(article)
        
        book = epub.EpubBook()
        
        with patch.object(generator.image_processor, "download_and_process", return_value=("processed.jpg", b"data")):
            generator._add_images_to_chapter(book, chapter, article)
            
        assert "images/processed.jpg" in chapter.content
        assert url_with_amp not in chapter.content
        assert "w=800&amp;h=600" not in chapter.content

    def test_trafilatura_images_from_raw_html(self):
        """Test Bug 1: trafilatura 剥离图片时，从原始 HTML 取回图片 URL。"""
        source = ContentSource(type="web", src="https://example.com", title="Test")
        fetcher = WebFetcher(source)

        raw_html = """
        <html>
            <body>
                <article>
                    <h1>Title</h1>
                    <img src="https://example.com/test.jpg">
                    <p>Content</p>
                </article>
            </body>
        </html>
        """

        # Mock trafilatura.extract 返回不含 <img> 的内容
        trafilatura_content = "<html><body><h1>Title</h1><p>Content</p></body></html>"
        with patch("src.fetchers.web_fetcher.trafilatura.extract", return_value=trafilatura_content):
            with patch.object(fetcher, "_make_request") as mock_req:
                mock_req.return_value.text = raw_html
                result = fetcher.fetch()

                assert result.success
                assert len(result.articles) == 1
                # 内容用 trafilatura 的
                assert result.articles[0].content == trafilatura_content
                # 图片从原始 HTML 取回
                assert "https://example.com/test.jpg" in result.articles[0].images

    def test_lazy_loading_removal_in_epub(self):
        """Test that lazy loading attributes are removed in the final EPUB content."""
        config_data = {
            "title": {"text": "Test", "img": ""},
            "body": [{"type": "web", "src": "https://example.com", "title": "Test"}]
        }
        config = _parse_config(config_data)
        generator = EPUBGenerator(config)
        
        html_content = '<img src="placeholder.jpg" data-src="https://example.com/real.jpg">'
        article = Article(
            title="Test",
            content=html_content,
            url="https://example.com",
            images=["https://example.com/real.jpg"]
        )
        
        chapter = epub.EpubHtml(title="Test", file_name="test.xhtml")
        chapter.content = html_content
        book = epub.EpubBook()
        
        with patch.object(generator.image_processor, "download_and_process", return_value=("real.jpg", b"data")):
            generator._add_images_to_chapter(book, chapter, article)
            
        assert "images/real.jpg" in chapter.content
        assert "data-src" not in chapter.content
        assert "placeholder.jpg" not in chapter.content
