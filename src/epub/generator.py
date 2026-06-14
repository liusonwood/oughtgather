"""
EPUB 生成器模块
负责生成完整的 EPUB 电子书
"""

import os
from typing import List, Tuple, Dict, Optional
from ebooklib import epub
from bs4 import BeautifulSoup

from src.config import Config, ContentSource
from src.fetchers.base import Article, FetchResult
from src.epub.cover import CoverGenerator
from src.epub.toc import TOCGenerator
from src.processors.image_processor import ImageProcessor
from src.utils.logger import get_logger


class EPUBGenerator:
    """EPUB 生成器"""

    def __init__(self, config: Config):
        """
        初始化 EPUB 生成器

        Args:
            config: 全局配置
        """
        self.config = config
        self.logger = get_logger()
        self.image_processor = ImageProcessor()
        self.toc_generator = TOCGenerator()
        self.cover_generator = CoverGenerator(config.title)

    def generate(
        self,
        results: List[FetchResult],
        error_log: List[str] = None
    ) -> str:
        """
        生成 EPUB 文件（符合 Amazon Send to Kindle 要求）

        Args:
            results: 抓取结果列表
            error_log: 错误日志

        Returns:
            str: EPUB 文件路径
        """
        # 1. 创建 EPUB 书籍对象
        book = epub.EpubBook()

        # 2. 设置元数据
        self._set_metadata(book)

        # 3. 添加封面
        self._add_cover(book)

        # 4. 准备章节数据
        sections = self._prepare_sections(results)

        # 5. 添加目录章节
        self._add_toc_chapter(book, sections)

        # 6. 生成目录结构（符合 Amazon 要求）
        toc = self.toc_generator.generate(sections)

        # 6.1 添加目录项到 toc 开头
        toc_with_nav = [epub.Link("toc.xhtml", "目录", "toc")] + toc
        book.toc = toc_with_nav

        # 7. 添加正文章节
        self._add_chapters(book, sections)

        # 8. 添加错误日志章节（如果有）
        if error_log:
            self._add_error_log_chapter(book, error_log)

        # 9. 添加样式
        self._add_style(book)

        # 10. 添加导航文件（必须在保存之前，放在最后）
        book.add_item(epub.EpubNcx())  # EPUB 2 兼容
        book.add_item(epub.EpubNav())  # EPUB 3 标准

        # 11. 保存文件
        output_path = self._save_book(book)

        self.logger.info(f"EPUB generated: {output_path}")
        return output_path

    def _set_metadata(self, book: epub.EpubBook):
        """设置书籍元数据（符合 Amazon Send to Kindle 要求）"""
        book.set_identifier('ought-gather-epub')
        book.set_title(self.config.title.get_plain_text())
        book.set_language('zh-CN')
        book.add_author('Ought Gather')

        # 添加 publisher 元数据（Amazon 要求）
        book.add_metadata('DC', 'publisher', 'Ought Gather')

        # 添加 date 元数据（Amazon 要求）
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d')
        book.add_metadata('DC', 'date', now)

    def _add_cover(self, book: epub.EpubBook):
        """添加封面"""
        try:
            cover_filename, cover_data = self.cover_generator.generate()
            book.set_cover(cover_filename, cover_data)
            self.logger.info("Cover added to EPUB")
        except Exception as e:
            self.logger.error(f"Failed to add cover: {e}")

    def _prepare_sections(
        self,
        results: List[FetchResult]
    ) -> List[Tuple[ContentSource, List[Article], Optional[str]]]:
        """
        准备章节数据（按优先级排序）

        Args:
            results: 抓取结果列表

        Returns:
            List[Tuple[ContentSource, List[Article], Optional[str]]]: 章节数据
            第三个元素为数据源的显示名称（如 RSS feed 标题）
        """
        # 每个数据源最多保留 50 篇文章
        MAX_ARTICLES_PER_SOURCE = 50

        # 按优先级排序（降序）
        sorted_results = sorted(
            results,
            key=lambda r: r.source.priority,
            reverse=True
        )

        sections = []
        for result in sorted_results:
            if result.success and result.articles:
                # 限制每个数据源的文章数量
                limited_articles = result.articles[:MAX_ARTICLES_PER_SOURCE]
                sections.append((result.source, limited_articles, result.source_title))

        return sections

    def _add_toc_chapter(
        self,
        book: epub.EpubBook,
        sections: List[Tuple[ContentSource, List[Article], Optional[str]]]
    ):
        """添加目录章节到 EPUB 中"""
        book_title = self.config.title.get_title_without_date()

        html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head>
    <title>目录</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>{book_title}</h1>
    <h2>目录</h2>
    <ul>
"""

        chapter_id = 0
        for source, articles, source_title in sections:
            if not articles:
                continue

            # web/trending: 扁平结构
            if source.type in ("web", "trending"):
                link_title = self.toc_generator._get_source_title(source, articles, source_title)
                html += f'<li><a href="chapter_{chapter_id}.xhtml">{link_title}</a></li>\n'
                chapter_id += 1
                continue

            # mail/rss: 两级结构
            section_title = self.toc_generator._get_source_title(source, articles, source_title)
            html += f'<li><a href="chapter_{chapter_id}.xhtml">{section_title}</a></li>\n'
            chapter_id += len(articles)

        html += """</ul>
</body>
</html>"""

        toc_chapter = epub.EpubHtml(
            title="目录",
            file_name="toc.xhtml",
            lang='zh-CN'
        )
        toc_chapter.content = html

        book.add_item(toc_chapter)
        self.logger.info("TOC chapter added to EPUB")

    def _add_chapters(
        self,
        book: epub.EpubBook,
        sections: List[Tuple[ContentSource, List[Article], Optional[str]]]
    ):
        """添加章节"""
        chapter_id = 0
        # Kindle 打开 EPUB 时会显示 spine 的第一个页面
        # 阅读顺序：目录 → 正文章节（封面在最后，避免打开时首先看到封面）
        spine = []

        # 先添加封面到 spine（但实际内容在最后，这样 Kindle 不会在打开时首先显示封面）
        spine.append('cover')

        # 添加目录章节到 spine
        # 需要先获取 toc 章节对象
        toc_chapter = None
        for item in book.items:
            if hasattr(item, 'file_name') and item.file_name == 'toc.xhtml':
                toc_chapter = item
                break

        if toc_chapter:
            spine.append(toc_chapter)
        else:
            spine.append('nav')  # 如果没有 toc，使用 nav

        for source, articles, _source_title in sections:
            for article in articles:
                # 生成章节内容
                chapter_content = self._generate_chapter_content(article)

                # 创建章节
                chapter = epub.EpubHtml(
                    title=article.title,
                    file_name=f"chapter_{chapter_id}.xhtml",
                    lang='zh-CN'
                )
                chapter.content = chapter_content

                # 添加图片
                self._add_images_to_chapter(book, chapter, article)

                book.add_item(chapter)
                spine.append(chapter)  # 添加到 spine（阅读顺序）
                chapter_id += 1

        # 设置书籍的阅读顺序：封面 → 目录 → 正文章节
        book.spine = spine

        self.logger.info(f"Added {chapter_id} chapters to EPUB")

    def _generate_chapter_content(self, article: Article) -> str:
        """
        生成章节 HTML 内容

        Args:
            article: 文章对象

        Returns:
            str: HTML 内容
        """
        # 注意：不能包含 <?xml ...?> 声明，否则 ebooklib 无法正确解析
        html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head>
    <title>{article.title}</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>{article.title}</h1>
    <p class="back-to-toc">
        <a href="nav.xhtml">返回目录</a>
    </p>
"""

        # 添加元信息
        if article.author:
            html += f"<p class='author'>作者: {article.author}</p>"
        if article.published_date:
            html += f"<p class='date'>日期: {article.published_date}</p>"

        # 添加正文
        html += f"<div class='content'>{article.content}</div>"

        # 添加原文链接
        if article.url and not article.url.startswith('mailto:'):
            html += f"<p class='link'>原文链接: <a href='{article.url}'>{article.url}</a></p>"

        html += """
</body>
</html>"""

        return html

    def _add_images_to_chapter(
        self,
        book: epub.EpubBook,
        chapter: epub.EpubHtml,
        article: Article
    ):
        """
        添加图片到章节

        Args:
            book: EPUB 书籍对象
            chapter: 章节对象
            article: 文章对象
        """
        # 处理文章中的图片
        for img_url in article.images:
            result = self.image_processor.download_and_process(img_url, article.url)

            if result:
                filename, img_data = result

                # 添加图片到书籍
                epub_image = epub.EpubItem(
                    uid=f"image_{filename}",
                    file_name=f"images/{filename}",
                    media_type="image/jpeg",
                    content=img_data
                )
                book.add_item(epub_image)

                # 在章节内容中替换图片 URL
                chapter.content = chapter.content.replace(img_url, f"images/{filename}")

    def _add_error_log_chapter(self, book: epub.EpubBook, error_log: List[str]):
        """
        添加错误日志章节

        Args:
            book: EPUB 书籍对象
            error_log: 错误日志列表
        """
        # 注意：不能包含 <?xml ...?> 声明，否则 ebooklib 无法正确解析
        html = """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head>
    <title>错误日志</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>错误日志</h1>
    <p>以下是在抓取过程中发生的错误：</p>
    <ul>
"""

        for error in error_log:
            html += f"        <li>{error}</li>\n"

        html += """    </ul>
</body>
</html>"""

        chapter = epub.EpubHtml(
            title="错误日志",
            file_name="error_log.xhtml",
            lang='zh-CN'
        )
        chapter.content = html

        book.add_item(chapter)

        # 添加到目录
        book.toc.append(epub.Link("error_log.xhtml", "错误日志", "error_log"))

        # 添加到 spine（阅读顺序）
        if isinstance(book.spine, list):
            book.spine.append(chapter)

        self.logger.info("Error log chapter added to EPUB")

    def _add_style(self, book: epub.EpubBook):
        """添加样式"""
        css = epub.EpubItem(
            uid="style",
            file_name="style/default.css",
            media_type="text/css",
            content="""
body {
    font-family: serif;
    line-height: 1.6;
    margin: 1em;
}
h1 {
    font-size: 1.8em;
    font-weight: bold;
    margin-bottom: 0.8em;
    color: #000000;
    padding-bottom: 0.3em;
    border-bottom: 2px solid #666666;
}
h2 {
    font-size: 1.4em;
    font-weight: bold;
    margin-bottom: 0.5em;
    color: #333333;
}
h3 {
    font-size: 1.2em;
    font-weight: bold;
    margin-bottom: 0.5em;
    color: #555555;
}
.author, .date {
    font-size: 0.9em;
    color: #666666;
    margin: 0.2em 0;
}
.content {
    margin-top: 1em;
    text-align: justify;
}
.content img {
    max-width: 100%;
    height: auto;
}
.link {
    margin-top: 2em;
    font-size: 0.8em;
    color: #999999;
}
a {
    color: #0066cc;
    text-decoration: none;
}
ul {
    margin: 1em 0;
    padding-left: 2em;
}
li {
    margin: 0.5em 0;
}
.back-to-toc {
    text-align: center;
    margin-top: 1em;
    margin-bottom: 1em;
    font-size: 0.9em;
}
.back-to-toc a {
    color: #0066cc;
    text-decoration: none;
}
"""
        )
        book.add_item(css)

    def _save_book(self, book: epub.EpubBook) -> str:
        """
        保存 EPUB 文件

        Args:
            book: EPUB 书籍对象

        Returns:
            str: 文件路径
        """
        # 生成文件名
        from src.utils.helpers import sanitize_filename
        title = self.config.title.get_plain_text()
        filename = sanitize_filename(title) + ".epub"

        # 确保输出目录存在
        os.makedirs("output", exist_ok=True)

        output_path = os.path.join("output", filename)

        # 保存
        epub.write_epub(output_path, book, {})

        # 检查文件大小
        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)

        self.logger.info(f"EPUB file size: {file_size_mb:.2f} MB")

        if file_size_mb > 50:
            self.logger.warning("EPUB file exceeds 50MB limit!")

        return output_path
