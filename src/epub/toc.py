"""
目录生成器模块
负责生成 EPUB 的目录结构
"""

from typing import List, Tuple, Optional, Union
from ebooklib import epub

from src.config import ContentSource
from src.fetchers.base import Article
from src.utils.logger import get_logger


# TOC 条目类型：可以是两级结构 (Section, [Link]) 或扁平 Link
TOCEntry = Union[Tuple[epub.Section, List[epub.Link]], epub.Link]


class TOCGenerator:
    """目录生成器"""

    def __init__(self):
        """初始化目录生成器"""
        self.logger = get_logger()

    def generate(
        self,
        sections: List[Tuple[ContentSource, List[Article], Optional[str]]]
    ) -> List[TOCEntry]:
        """
        生成目录结构

        Args:
            sections: 章节列表 (ContentSource, Articles, source_title)
                      source_title 为数据源的显示名称（如 RSS feed 标题）

        Returns:
            List[TOCEntry]: 目录结构
            - mail/rss: (Section, [Link, ...]) 两级结构
            - web/trending: epub.Link 扁平结构（无小标题）
        """
        toc: List[TOCEntry] = []
        chapter_counter = 0  # 与 generator.py 中的 chapter_id 保持一致

        for source, articles, source_title in sections:
            if not articles:
                continue

            # web/trending：无小标题，直接生成扁平链接
            if source.type in ("web", "trending"):
                chapter_filename = f"chapter_{chapter_counter}.xhtml"
                chapter_id = f"chapter_{chapter_counter}"
                link_title = self._get_source_title(source, articles, source_title)

                link = epub.Link(chapter_filename, link_title, chapter_id)
                toc.append(link)
                chapter_counter += 1
                continue

            # mail/rss：两级结构（章节 → 文章列表）
            section_title = self._get_source_title(source, articles, source_title)
            section = epub.Section(section_title)

            links = []
            for article in articles:
                chapter_filename = f"chapter_{chapter_counter}.xhtml"
                chapter_id = f"chapter_{chapter_counter}"

                link = epub.Link(chapter_filename, article.title, chapter_id)
                links.append(link)
                chapter_counter += 1

            toc.append((section, links))

        self.logger.info(f"Generated TOC with {len(toc)} entries")
        return toc

    def _get_source_title(
        self,
        source: ContentSource,
        articles: List[Article],
        source_title: Optional[str] = None
    ) -> str:
        """
        获取数据源的显示名称

        优先级：
        1. 用户自定义 title（config 中的 title 字段）
        2. 数据源特定名称：
           - rss: feed 标题（从 feedparser 提取）
           - web: 页面标题（第一篇文章的标题）
           - mail: namespace（source.src）
           - trending: 关键词/主题（source.src）

        Args:
            source: 内容源配置
            articles: 文章列表
            source_title: 数据源显示名称（如 RSS feed 标题）

        Returns:
            str: 章节显示名称
        """
        # 1. 优先使用用户自定义标题
        if source.title:
            return source.title

        # 2. 根据类型获取默认名称
        if source.type == "rss":
            return source_title or source.src

        if source.type == "web":
            # 使用页面标题（第一篇文章的标题）
            if articles:
                return articles[0].title
            return source.src

        # mail / trending：直接使用 source.src（namespace / 关键词）
        return source.src
