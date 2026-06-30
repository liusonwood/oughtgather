"""
RSS 抓取器模块
解析 RSS/Atom 订阅源
"""

from typing import List, Optional
import feedparser
import trafilatura

from src.config import ContentSource
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.utils.logger import get_logger
from src.utils.helpers import format_date


class RSSFetcher(BaseFetcher):
    """RSS 抓取器"""

    type_name = "rss"
    src_placeholder = "RSS/Atom URL, 例如: https://hnrss.org/frontpage"
    config_schema = {
        "full_text": {
            "type": "select",
            "label": "全文提取",
            "options": ["", "N", "Y"],
            "hint": "仅 RSS 有效"
        },
        "metadata.limit": {
            "type": "number",
            "label": "限制条目数 (limit)",
            "placeholder": "留空使用全局限制"
        }
    }
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
            # 改进：即使有格式错误，只要有条目就继续处理
            if feed.bozo:
                self.logger.warning(
                    f"RSS feed has format issues (bozo): {feed.bozo_exception}"
                )
            
            # 如果没有任何条目且有严重错误，则失败
            if not feed.entries:
                result.success = False
                error_msg = str(feed.bozo_exception) if feed.bozo else "No entries found"
                result.error = f"Failed to parse RSS feed: {error_msg}"
                self.logger.error(result.error)
                return result

            # 提取 feed 标题作为章节显示名称
            result.source_title = feed.feed.get("title", "")

            self.logger.info(f"Found {len(feed.entries)} entries in RSS feed")

            # 限制条目数量（默认使用全局限制，可通过 metadata.limit 覆盖）
            metadata = self.source.metadata or {}
            limit = min(int(metadata.get("limit", self.global_limit)), len(feed.entries))
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

            # 只要成功解析了至少一些条目，就认为抓取成功
            if result.articles:
                result.success = True
            
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
            # 抓取完整正文（使用 trafilatura）
            content, raw_html = self._fetch_full_text(link)
            # 从原始 HTML 提取图片 URL（trafilatura 通常会剥离 <img>）
            body_images = self._extract_images(raw_html, base_url=link)
            # 额外从 og:image / twitter:image / <link rel="image_src"> 提取封面图，
            # 置于列表首位（SPA 类网站如 Scientific American 的 lead image
            # 可能不在 trafilatura 识别的正文区域内，依赖 meta 标签才能捕获）
            og_images = self._extract_og_image(raw_html, base_url=link)
            # 合并：og_images 在前，body_images 追加（去重）
            seen = set(og_images)
            images = og_images + [u for u in body_images if u not in seen]
        else:
            # 使用 RSS 摘要
            content = self._get_summary(entry)
            images = self._extract_images(content, base_url=link)

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
        抓取完整正文

        Args:
            url: 文章 URL

        Returns:
            tuple: (正文 HTML, 原始页面 HTML)。trafilatura 失败时正文为空字符串。
        """
        if not url:
            return "", ""

        try:
            # 下载网页
            response = self._make_request(url)
            raw_html = response.text

            # 使用 trafilatura 提取正文
            content = trafilatura.extract(
                raw_html,
                include_comments=False,
                include_tables=True,
                include_images=True,
                include_links=True,
                output_format="html"
            )

            if content:
                # trafilatura 在 output_format="html" 时会将 <img> 转换为
                # <graphic>（HTML5 元素），导致下游的 ContentProcessor 和
                # EPUBGenerator 找不到 <img> 标签而丢失所有图片。
                # 这里将 <graphic src="..."> 转换回 <img src="...">。
                content = self._restore_img_tags(content)

            if not content:
                self.logger.warning(f"trafilatura failed to extract content from {url}")

            return content or "", raw_html

        except Exception as e:
            self.logger.error(f"Failed to fetch full text from {url}: {e}")
            return "", ""
