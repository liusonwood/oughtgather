"""
网页抓取器模块
抓取单个网页并提取正文
"""

from datetime import datetime
from typing import List
from bs4 import BeautifulSoup
import trafilatura

from src.config import ContentSource
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.utils.logger import get_logger
from src.utils.helpers import generate_content_id


class WebFetcher(BaseFetcher):
    """网页抓取器"""

    def fetch(self) -> FetchResult:
        """
        执行网页抓取

        Returns:
            FetchResult: 抓取结果
        """
        result = FetchResult(source=self.source, articles=[])

        try:
            # 下载网页
            response = self._make_request(self.source.src)
            html = response.text

            # 提取标题
            title = self._extract_title(html)

            # 提取正文
            content = self._extract_content(html)

            if not content:
                result.success = False
                result.error = "Failed to extract content from webpage"
                return result

            # Bug 1 & 2: 提取图片并处理 Trafilatura 剥离问题
            images = self._extract_images(content)
            
            # 如果正文内容太短，或者虽然有图片但 content 里一个 <img> 都没有，说明 trafilatura 过于激进
            if len(images) == 0 or len(content) < 300:
                raw_images = self._extract_images(html)
                if len(raw_images) > len(images) or len(content) < 300:
                    self.logger.warning(f"trafilatura might have been too aggressive for {self.source.src}, falling back to BeautifulSoup")
                    fallback_content = self._fallback_extract(html)
                    if len(fallback_content) > len(content):
                        content = fallback_content
                        images = self._extract_images(content)

            # 创建文章对象（带当日时间戳，用于去重哈希计算）
            today = datetime.now().strftime("%Y-%m-%d")
            article = Article(
                title=title,
                content=content,
                url=self.source.src,
                images=images,
                published_date=today
            )

            # 记录带时间戳的去重哈希
            content_id = generate_content_id(article.url, article.title, today)
            self.logger.info(f"Web dedup hash [{today}]: url={self.source.src}, hash={content_id}")

            # 检查是否应该删除
            if not self._should_delete(article.title):
                result.articles.append(article)

            return result

        except Exception as e:
            self.logger.error(f"Web fetch failed: {e}")
            result.success = False
            result.error = str(e)
            return result

    def _extract_title(self, html: str) -> str:
        """
        从 HTML 中提取标题

        Args:
            html: HTML 内容

        Returns:
            str: 标题
        """
        soup = BeautifulSoup(html, 'lxml')

        # 尝试多个可能的标题位置
        title = None

        # 1. <title> 标签
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        # 2. <h1> 标签
        if not title:
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)

        # 3. Open Graph 标题
        if not title:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content', '')

        # 4. 使用自定义标题或 URL
        if not title:
            title = self.source.title or self.source.src

        return title

    def _extract_content(self, html: str) -> str:
        """
        从 HTML 中提取正文

        Args:
            html: HTML 内容

        Returns:
            str: 正文 HTML
        """
        # 使用 trafilatura 提取正文
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_images=True,
            include_links=True,
            output_format="html"
        )

        if content:
            return content

        # 回退到备用方法
        self.logger.warning("trafilatura failed, using fallback extraction")
        return self._fallback_extract(html)

    def _fallback_extract(self, html: str) -> str:
        """
        备用的内容提取方法

        Args:
            html: HTML 内容

        Returns:
            str: 提取的内容
        """
        soup = BeautifulSoup(html, 'lxml')

        # 移除不需要的元素
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()

        # 尝试找到主要内容区域
        main_content = (
            soup.find('article') or
            soup.find('main') or
            soup.find('div', class_='content') or
            soup.find('div', class_='post') or
            soup.find('div', class_='article') or
            soup.body
        )

        if main_content:
            return str(main_content)

        return ""
