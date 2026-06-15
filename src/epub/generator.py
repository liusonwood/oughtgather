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

import html as html_module


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
        生成 EPUB 文件

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

        # 5. 生成目录
        toc = self.toc_generator.generate(sections)
        # 在目录最前面添加"目录"条目，方便快速跳转到导航页
        toc.insert(0, epub.Link("nav.xhtml", "目录", "nav"))
        book.toc = toc

        # 6. 添加章节
        self._add_chapters(book, sections)

        # 7. 添加错误日志章节（如果有）
        if error_log:
            self._add_error_log_chapter(book, error_log)

        # 8. 添加样式
        self._add_style(book)

        # 9. 添加导航文件
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # 10. 保存文件
        output_path = self._save_book(book)

        self.logger.info(f"EPUB generated: {output_path}")
        return output_path

    def _set_metadata(self, book: epub.EpubBook):
        """设置书籍元数据"""
        book.set_identifier('ought-gather-epub')
        book.set_title(self.config.title.get_plain_text())
        book.set_language('zh-CN')
        book.add_author('Ought Gather')

    def _add_cover(self, book: epub.EpubBook):
        """添加封面"""
        try:
            cover_filename, cover_data = self.cover_generator.generate()
            book.set_cover(cover_filename, cover_data)
            # ebooklib 默认将 cover.xhtml 标记为非线性内容（is_linear=False），
            # 会导致 epubcheck 报 OPF-096 错误（非线性内容必须可从其他内容超链接到达）。
            # 将其设为线性，使封面成为正文阅读顺序的第一页。
            for item in book.items:
                if getattr(item, 'file_name', '') == 'cover.xhtml':
                    item.is_linear = True
                    break
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
        # 按优先级排序（降序）
        sorted_results = sorted(
            results,
            key=lambda r: r.source.priority,
            reverse=True
        )

        sections = []
        for result in sorted_results:
            if result.success and result.articles:
                sections.append((result.source, result.articles, result.source_title))

        return sections

    def _add_chapters(
        self,
        book: epub.EpubBook,
        sections: List[Tuple[ContentSource, List[Article], Optional[str]]]
    ):
        """
        添加章节

        在每个不同数据源（大目录）的第一篇文章前插入一个章节分隔页，
        让阅读时能清楚地感知进入了新的栏目/分组。
        """
        chapter_id = 0
        divider_id = 0
        # 把 cover 放在最前面，确保封面在第一页显示；
        # 否则 cover.xhtml 不在 spine 中，阅读器会把它追加到末尾。
        spine = ['cover', 'nav']

        for source, articles, source_title in sections:
            # 在该分组的第一篇文章前插入章节分隔页，显示所属栏目标题
            section_title = self.toc_generator._get_source_title(
                source, articles, source_title
            )
            divider = epub.EpubHtml(
                title=section_title,
                file_name=f"divider_{divider_id}.xhtml",
                lang='zh-CN'
            )
            divider.content = self._generate_section_divider_content(section_title)
            book.add_item(divider)
            spine.append(divider)
            divider_id += 1

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

        # 设置书籍的阅读顺序
        book.spine = spine

        self.logger.info(
            f"Added {chapter_id} chapters and {divider_id} section dividers to EPUB"
        )

    def _generate_chapter_content(self, article: Article) -> str:
        """
        生成章节 HTML 内容

        Args:
            article: 文章对象

        Returns:
            str: HTML 内容
        """
        import html
        
        # 对标题和作者进行 HTML 转义，防止 & 等字符导致 XML 解析失败
        safe_title = html.escape(article.title)
        safe_author = html.escape(article.author) if article.author else ""
        
        # 注意：不能包含 <?xml ...?> 声明，否则 ebooklib 无法正确解析
        # 使用 XHTML 命名空间
        content_html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head>
    <title>{safe_title}</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>{safe_title}</h1>
    <p><a href='nav.xhtml'>返回目录</a></p>
"""

        # 添加元信息
        if safe_author:
            content_html += f"<p class='author'>作者: {safe_author}</p>"
        if article.published_date:
            content_html += f"<p class='date'>日期: {article.published_date}</p>"

        # 添加正文（正文已经由 ContentProcessor 处理过，应该是安全的 HTML 片段）
        content_html += f"<div class='content'>{article.content}</div>"

        # 添加原文链接
        if article.url and not article.url.startswith('mailto:'):
            safe_url = html.escape(article.url)
            content_html += f"<p class='link'>原文链接: <a href='{safe_url}'>{safe_url}</a></p>"

        content_html += """
</body>
</html>"""

        return content_html

    def _generate_section_divider_content(self, section_title: str) -> str:
        """
        生成章节分隔页 HTML 内容

        在两个不同"大目录"之间插入，视觉上提示读者进入了新的栏目/分组。

        Args:
            section_title: 章节/栏目标题

        Returns:
            str: HTML 内容
        """
        safe_title = html_module.escape(section_title)
        return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head>
    <title>{safe_title}</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>{safe_title}</h1>
    <p><a href='nav.xhtml'>返回目录</a></p>
</body>
</html>"""

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
        if not chapter.content:
            return

        soup = BeautifulSoup(chapter.content, 'lxml')
        img_tags = soup.find_all('img')

        if not img_tags:
            return

        # 用于存储已处理的图片 URL，避免在同一章节中重复处理
        url_to_filename = {}

        for img in img_tags:
            # 优先检查懒加载属性 (Bug 3) 和 srcset
            src = None
            
            # 检查 srcset (Bug 4)
            srcset = img.get('data-srcset') or img.get('srcset')
            if srcset:
                candidates = []
                for part in srcset.split(','):
                    parts = part.strip().split()
                    if parts:
                        candidates.append(parts[0])
                if candidates:
                    src = candidates[-1]
            
            # 检查懒加载属性
            if not src:
                for attr in ['data-src', 'data-original', 'data-actualsrc', 'data-lazy-src', 'file', 'zoom-target', 'original']:
                    val = img.get(attr)
                    if val and not any(ext in val.lower() for ext in ['.gif', '.svg']):
                        src = val
                        break
            
            if not src:
                src = img.get('src')
            
            if not src:
                continue

            # 如果已经处理过这个 URL
            if src in url_to_filename:
                img['src'] = f"images/{url_to_filename[src]}"
                # 移除干扰属性
                for attr in ['data-src', 'data-original', 'data-actualsrc', 'data-lazy-src', 'srcset', 'data-srcset']:
                    if img.has_attr(attr):
                        del img[attr]
                continue

            # 处理图片
            # image_processor.download_and_process 会处理相对 URL
            result = self.image_processor.download_and_process(src, article.url)

            if result:
                filename, img_data = result
                url_to_filename[src] = filename

                # 检查是否已经添加过这个 item（避免跨章节重复添加）
                image_uid = f"image_{filename}"
                is_already_added = False
                for item in book.items:
                    if item.id == image_uid:
                        is_already_added = True
                        break

                if not is_already_added:
                    epub_image = epub.EpubItem(
                        uid=image_uid,
                        file_name=f"images/{filename}",
                        media_type="image/jpeg",
                        content=img_data
                    )
                    book.add_item(epub_image)

                # 在章节内容中更新图片 URL
                img['src'] = f"images/{filename}"
                # 移除干扰属性 (Bug 3)
                for attr in ['data-src', 'data-original', 'data-actualsrc', 'data-lazy-src', 'srcset', 'data-srcset']:
                    if img.has_attr(attr):
                        del img[attr]
            else:
                # 图片下载/处理失败或被跳过（如小图片）：移除 img 标签以避免在 EPUB 中留下外部 URL。
                # EPUB 3 标准不允许引用 EPUB 容器之外的资源（RSC-006），
                # 否则 epubcheck 会报 RSC-006 和 OPF-014 错误。
                # 注：真正的下载/处理错误已在 ImageProcessor 中用 error 级别记录，
                # 小图片跳过也已用 debug 级别记录，此处仅记录移除标签的操作。
                self.logger.debug(f"Removing image tag (processing failed or skipped): {src}")
                img.decompose()

        # 将修改后的 HTML 写回 chapter.content (Bug 2)
        # BeautifulSoup 会生成完整的 HTML 结构并正确处理转义字符
        chapter.content = str(soup)

    def _add_error_log_chapter(self, book: epub.EpubBook, error_log: List[str]):
        """
        添加错误日志章节

        Args:
            book: EPUB 书籍对象
            error_log: 错误日志列表
        """
        import html
        
        # 注意：不能包含 <?xml ...?> 声明，否则 ebooklib 无法正确解析
        content_html = """<!DOCTYPE html>
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
            safe_error = html.escape(error)
            content_html += f"        <li>{safe_error}</li>\n"

        content_html += """    </ul>
</body>
</html>"""

        chapter = epub.EpubHtml(
            title="错误日志",
            file_name="error_log.xhtml",
            lang='zh-CN'
        )
        chapter.content = content_html

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
    font-size: 1.5em;
    font-weight: bold;
    margin-bottom: 0.5em;
    color: #333;
}
.author, .date {
    font-size: 0.9em;
    color: #666;
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
    color: #999;
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
nav ol {
    line-height: 2.2;
}
nav li {
    margin: 0.3em 0;
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
