"""
目录生成器模块
负责生成 EPUB 的目录结构
"""

from typing import List, Tuple
from ebooklib import epub

from src.config import ContentSource
from src.fetchers.base import Article
from src.utils.logger import get_logger


class TOCGenerator:
    """目录生成器"""

    def __init__(self):
        """初始化目录生成器"""
        self.logger = get_logger()

    def generate(
        self,
        sections: List[Tuple[ContentSource, List[Article]]]
    ) -> List[Tuple[epub.Section, List[epub.Link]]]:
        """
        生成目录结构

        Args:
            sections: 章节列表 (ContentSource, Articles)

        Returns:
            List[Tuple[epub.Section, List[epub.Link]]]: 目录结构
        """
        toc = []
        chapter_counter = 0  # 与 generator.py 中的 chapter_id 保持一致

        for source, articles in sections:
            if not articles:
                continue

            # 一级章节标题
            section_title = self._get_section_title(source, articles)

            # 创建章节
            section = epub.Section(section_title)

            # 二级章节（文章列表）
            links = []
            for article in articles:
                # 生成章节文件名（必须与 generator.py._add_chapters 一致）
                chapter_filename = f"chapter_{chapter_counter}.xhtml"
                chapter_id = f"chapter_{chapter_counter}"
                chapter_title = article.title

                # 创建链接
                link = epub.Link(chapter_filename, chapter_title, chapter_id)
                links.append(link)
                chapter_counter += 1

            toc.append((section, links))

        self.logger.info(f"Generated TOC with {len(toc)} sections")
        return toc

    def _get_section_title(self, source: ContentSource, articles: List[Article]) -> str:
        """
        获取章节标题

        Args:
            source: 内容源配置
            articles: 文章列表

        Returns:
            str: 章节标题
        """
        # 优先使用自定义标题
        if source.title:
            return source.title

        # 根据类型生成默认标题
        if source.type == "mail":
            return f"邮件订阅: {source.src}"
        elif source.type == "rss":
            return f"RSS: {source.src}"
        elif source.type == "web":
            return f"网页: {source.src}"
        elif source.type == "trending":
            return f"热点分析: {source.src}"
        else:
            return f"内容源: {source.src}"

    def generate_flat_toc(
        self,
        sections: List[Tuple[ContentSource, List[Article]]]
    ) -> List[epub.Link]:
        """
        生成扁平化目录（所有文章在同一层级）

        Args:
            sections: 章节列表

        Returns:
            List[epub.Link]: 扁平化目录
        """
        toc = []
        chapter_counter = 0

        for source, articles in sections:
            for article in articles:
                chapter_filename = f"chapter_{chapter_counter}.xhtml"
                chapter_id = f"chapter_{chapter_counter}"
                chapter_title = f"[{source.title or source.type}] {article.title}"

                link = epub.Link(chapter_filename, chapter_title, chapter_id)
                toc.append(link)
                chapter_counter += 1

        return toc
