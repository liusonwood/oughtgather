"""
内容处理器模块
负责内容清洗、格式化和规则应用
"""

import re
from typing import Optional
from bs4 import BeautifulSoup

from src.config import ContentSource
from src.fetchers.base import Article
from src.utils.logger import get_logger


class ContentProcessor:
    """内容处理器"""

    def __init__(self, source: ContentSource):
        """
        初始化内容处理器

        Args:
            source: 内容源配置
        """
        self.source = source
        self.logger = get_logger()

    def process(self, article: Article) -> Article:
        """
        处理文章内容

        Args:
            article: 原始文章

        Returns:
            Article: 处理后的文章
        """
        # 1. 应用 chop 规则
        if self.source.chop:
            article.content = self._apply_chop(article.content)

        # 2. 应用 exclude 规则
        if self.source.exclude:
            article.content = self._apply_exclude(article.content)

        # 3. 应用 keep_link 规则
        if self.source.keep_link == "N":
            article.content = self._remove_links(article.content)

        # 4. 清洗 HTML
        article.content = self._clean_html(article.content)

        # 5. 确保 HTML 格式正确
        article.content = self._ensure_valid_html(article.content)

        return article

    def _apply_chop(self, html: str) -> str:
        """
        应用 chop 规则
        支持 Python 切片语法，如 "/[0:100]" 表示删除前 100 个字符

        Args:
            html: HTML 内容

        Returns:
            str: 处理后的 HTML
        """
        if not self.source.chop:
            return html

        try:
            # 解析切片语法
            chop_pattern = r'/\[(\d*):(\d*)\]'
            match = re.match(chop_pattern, self.source.chop)

            if match:
                start = int(match.group(1)) if match.group(1) else None
                end = int(match.group(2)) if match.group(2) else None

                # 提取纯文本进行切片
                soup = BeautifulSoup(html, 'lxml')
                text = soup.get_text()

                # 应用切片
                sliced_text = text[start:end]

                # 重新构建 HTML（简化处理）
                return f"<p>{sliced_text}</p>"

        except Exception as e:
            self.logger.error(f"Failed to apply chop rule: {e}")

        return html

    def _apply_exclude(self, html: str) -> str:
        """
        应用 exclude 规则
        删除指定开头或结尾的内容块

        Args:
            html: HTML 内容

        Returns:
            str: 处理后的 HTML
        """
        if not self.source.exclude:
            return html

        try:
            # 解析 exclude 配置
            # 格式：start:关键词 或 end:关键词
            exclude_parts = self.source.exclude.split(':')

            if len(exclude_parts) == 2:
                position = exclude_parts[0].strip()
                keyword = exclude_parts[1].strip()

                soup = BeautifulSoup(html, 'lxml')
                text = soup.get_text()

                if position == "start":
                    # 删除开头的指定内容
                    idx = text.find(keyword)
                    if idx != -1:
                        text = text[idx + len(keyword):]
                elif position == "end":
                    # 删除结尾的指定内容
                    idx = text.rfind(keyword)
                    if idx != -1:
                        text = text[:idx]

                return f"<p>{text}</p>"

        except Exception as e:
            self.logger.error(f"Failed to apply exclude rule: {e}")

        return html

    def _remove_links(self, html: str) -> str:
        """
        移除所有超链接

        Args:
            html: HTML 内容

        Returns:
            str: 处理后的 HTML
        """
        soup = BeautifulSoup(html, 'lxml')

        # 将所有 <a> 标签替换为纯文本
        for link in soup.find_all('a'):
            link.replace_with(link.get_text())

        return str(soup)

    def _clean_html(self, html: str) -> str:
        """
        清洗 HTML
        移除不需要的标签和属性

        Args:
            html: HTML 内容

        Returns:
            str: 清洗后的 HTML
        """
        soup = BeautifulSoup(html, 'lxml')

        # 移除 script 和 style 标签
        for tag in soup(['script', 'style', 'iframe', 'form', 'input', 'button']):
            tag.decompose()

        # 移除不安全的属性
        for tag in soup.find_all(True):
            # 保留基本属性
            allowed_attrs = ['href', 'src', 'alt', 'title', 'class']
            attrs = dict(tag.attrs)
            for attr in attrs:
                if attr not in allowed_attrs:
                    del tag[attr]

        return str(soup)

    def _ensure_valid_html(self, html: str) -> str:
        """
        确保 HTML 格式正确
        添加必要的包装标签

        Args:
            html: HTML 内容

        Returns:
            str: 有效的 HTML
        """
        # 检查是否有根标签
        soup = BeautifulSoup(html, 'lxml')

        # 如果没有 body，添加一个
        if not soup.body:
            html = f"<body>{html}</body>"

        return html
