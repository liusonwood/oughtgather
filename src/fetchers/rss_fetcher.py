"""
RSS 抓取器模块
解析 RSS/Atom 订阅源
"""

from typing import List, Optional
import feedparser
from bs4 import BeautifulSoup
import trafilatura

from src.config import ContentSource
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.utils.logger import get_logger
from src.utils.helpers import format_date, extract_image_urls


class RSSFetcher(BaseFetcher):
    """RSS 抓取器"""

    MAX_ENTRIES = 50  # 每个 RSS 源最多抓取的条目数，可通过 metadata.limit 覆盖

    def fetch(self) -> FetchResult:
        """
        执行 RSS 抓取

        Returns:
            FetchResult: 抓取结果
        """
        result = FetchResult(source=self.source, articles=[])

        try:
            # 解析 RSS/Atom feed
            feed = feedparser.parse(self.source.src)

            # 检查解析结果
            if feed.bozo and not feed.entries:
                result.success = False
                result.error = f"Failed to parse RSS feed: {feed.bozo_exception}"
                return result

            # 提取 feed 标题作为章节显示名称
            result.source_title = feed.feed.get("title", "")

            self.logger.info(f"Found {len(feed.entries)} entries in RSS feed")

            # 限制条目数量（默认最多 50 条，可通过 metadata.limit 覆盖）
            metadata = self.source.metadata or {}
            limit = min(int(metadata.get("limit", self.MAX_ENTRIES)), len(feed.entries))
            entries = feed.entries[:limit]

            if limit < len(feed.entries):
                self.logger.info(f"Limiting RSS entries to {limit} (feed has {len(feed.entries)})")

            # 遍历所有条目
            for entry in entries:
                try:
                    article = self._parse_entry(entry)
                    if article and not self._should_delete(article.title):
                        result.articles.append(article)
                except Exception as e:
                    self.logger.error(f"Failed to parse entry: {e}")
                    result.add_error(f"Failed to parse entry: {e}")

            return result

        except Exception as e:
            self.logger.error(f"RSS fetch failed: {e}")
            result.success = False
            result.error = str(e)
            return result

    def _parse_entry(self, entry: dict) -> Optional[Article]:
        """
        解析单个 RSS 条目

        Args:
            entry: RSS 条目（feedparser 解析结果）

        Returns:
            Article: 文章对象
        """
        # 提取基本信息
        title = entry.get("title", "No Title")
        link = entry.get("link", "")
        author = entry.get("author", "")
        published = format_date(entry.get("published", ""))

        # 提取内容
        if self.source.full_text == "Y":
            # 抓取完整正文（同时从原始 HTML 中提取图片，因为 trafilatura 会移除 <img> 标签）
            content, images = self._fetch_full_text(link)
        else:
            # 使用 RSS 摘要
            content = self._get_summary(entry)
            images = self._extract_images(content)

        if not content:
            self.logger.warning(f"No content for entry: {title}")
            return None

        return Article(
            title=title,
            content=content,
            url=link,
            author=author,
            published_date=published,
            images=images,
            metadata={
                "categories": entry.get("tags", []),
            }
        )

    def _get_summary(self, entry: dict) -> str:
        """
        从 RSS 条目中获取摘要

        Args:
            entry: RSS 条目

        Returns:
            str: 摘要 HTML
        """
        # 尝试多个可能的内容字段
        if "content" in entry and len(entry.content) > 0:
            return entry.content[0].get("value", "")

        if "summary" in entry:
            return entry.get("summary", "")

        if "description" in entry:
            return entry.get("description", "")

        return ""

    def _fetch_full_text(self, url: str) -> tuple:
        """
        抓取完整正文，同时从原始 HTML 中提取图片。

        trafilatura 会移除 <img> 标签，因此必须在调用 trafilatura 之前
        从原始 HTML 中提取图片 URL。

        Args:
            url: 文章 URL

        Returns:
            tuple: (正文 HTML, 图片 URL 列表)
        """
        if not url:
            return "", []

        try:
            # 下载网页
            response = self._make_request(url)
            raw_html = response.text

            # 从原始 HTML 中提取图片（必须在 trafilatura 之前）
            images = extract_image_urls(raw_html, url)

            # 使用 trafilatura 提取正文
            content = trafilatura.extract(
                raw_html,
                include_comments=False,
                include_tables=True,
                include_images=True,
                include_links=True,
                output_format="html"
            )

            if not content:
                self.logger.warning(f"trafilatura failed to extract content from {url}")
                # 回退到使用 BeautifulSoup 提取
                content = self._fallback_extract(raw_html)

            return content, images

        except Exception as e:
            self.logger.error(f"Failed to fetch full text from {url}: {e}")
            return "", []

    def _fallback_extract(self, html: str) -> str:
        """
        备用的内容提取方法

        Args:
            html: HTML 内容

        Returns:
            str: 提取的内容
        """
        soup = BeautifulSoup(html, 'lxml')

        # 移除 script 和 style
        for script in soup(["script", "style"]):
            script.decompose()

        # 尝试找到主要内容区域
        main_content = (
            soup.find('article') or
            soup.find('main') or
            soup.find('div', class_='content') or
            soup.find('div', class_='post') or
            soup.body
        )

        if main_content:
            return str(main_content)

        return str(soup.body) if soup.body else ""

    def _extract_images(self, html: str) -> List[str]:
        """
        从 HTML 中提取图片 URL。

        使用共享的 extract_image_urls 辅助函数，支持懒加载和相对 URL 解析。

        Args:
            html: HTML 内容

        Returns:
            List[str]: 图片 URL 列表
        """
        return extract_image_urls(html)
