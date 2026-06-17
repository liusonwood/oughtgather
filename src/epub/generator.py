"""
EPUB 生成器模块
负责生成完整的 EPUB 电子书
"""

import os
from typing import List, Tuple, Dict, Optional, Union
from ebooklib import epub
from bs4 import BeautifulSoup

from src.config import Config, ContentSource
from src.fetchers.base import Article, FetchResult
from src.epub.cover import CoverGenerator
from src.epub.toc import TOCGenerator
from src.processors.image_processor import ImageProcessor
from src.utils.logger import get_logger
from src.utils.helpers import get_now

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
        生成 EPUB 文件 (EPUB 3.0 格式，符合规范)
        """
        # 1. 创建 EPUB 书籍对象
        book = epub.EpubBook()

        # 2. 设置元数据
        self._set_metadata(book)

        # 3. 添加封面
        self._add_cover(book)

        # 4. 添加 NCX (EPUB 2.0 兼容)
        ncx = epub.EpubNcx()
        book.add_item(ncx)

        # 5. 准备章节数据
        sections = self._prepare_sections(results)

        # 6. 生成目录数据
        toc = self.toc_generator.generate(sections)
        book.toc = toc

        # 初始化 spine (包含 cover)
        book.spine = ['cover']

        # 7. 添加章节 (必须在添加导航文件之前，因为需要其生成 chapter_id)
        # _add_chapters 会将章节追加到 book.spine
        self._add_chapters(book, sections)

        # 8. 添加错误日志章节（如果有）
        if error_log:
            self._add_error_log_chapter(book, error_log)

        # 9. 手动生成并添加 nav.xhtml (EPUB 3.0 必需)
        # 使用 EpubHtml 而不是 EpubNav，并手动设置 'nav' 属性，
        # 这样可以防止 ebooklib 在 write_epub 时用其默认生成的模板覆盖我们的自定义内容。
        nav = epub.EpubHtml(title=book.title, file_name='nav.xhtml', uid='nav')
        nav.properties = ['nav']
        nav.content = self._generate_nav_content(book.title, book.toc)
        book.add_item(nav)

        # 10. 将 nav 插入到 spine 中。
        # 我们希望首次打开电子书时直接进入目录 (nav.xhtml)，因此把 nav 排在最前面，
        # 随后是封面 (cover) 以及各个章节。确保阅读顺序合理且首次打开即为目录。
        if isinstance(book.spine, list):
            book.spine.insert(0, nav)
        else:
            book.spine = [nav, 'cover']

        # 11. 添加样式
        self._add_style(book)

        # 12. 设置 Guide 元素，明确指定启动页面为目录 (增加老旧设备兼容性)
        book.guide = [
            {'href': 'nav.xhtml', 'title': 'Table of Contents', 'type': 'toc'},
            {'href': 'cover.xhtml', 'title': 'Cover', 'type': 'cover'},
            {'href': 'divider_0.xhtml', 'title': 'Start Reading', 'type': 'text'}
        ]

        # 13. 保存文件
        output_path = self._save_book(book)

        self.logger.info(f"EPUB 3.0 (compliant) generated: {output_path}")
        return output_path

    def _set_metadata(self, book: epub.EpubBook):
        """设置书籍元数据"""
        # 使用标准的 UUID，并确保每次生成的 ID 唯一
        import uuid
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(self.config.title.get_plain_text())
        # 使用 zh (匹配成功文件)
        book.set_language('zh')
        book.add_author('Ought Gather')

    def _add_cover(self, book: epub.EpubBook):
        """添加封面 (EPUB 3.0 格式)"""
        try:
            cover_filename, cover_data = self.cover_generator.generate()

            # 1. 设置封面图片 (使用 set_cover 确保 properties="cover-image" 被正确设置)
            # ebooklib 会自动处理 manifest 中的 properties
            # 设置 create_page=False，因为我们要手动创建自定义样式的封面页
            book.set_cover(cover_filename, cover_data, create_page=False)

            # 2. 创建封面 XHTML 页面 (EPUB 3.0 使用 HTML5)
            # 使用更好的 CSS 确保图片在 Kindle 等设备上充满屏幕，背景为黑色避免白边
            cover_html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh" xml:lang="zh">
<head>
    <title>Cover</title>
    <style type="text/css">
        @page {{ margin: 0; padding: 0; }}
        html, body {{ 
            margin: 0; 
            padding: 0; 
            width: 100%; 
            height: 100%; 
        }}
        body {{ 
            display: table; 
            text-align: center; 
            background-color: #000000; 
        }}
        .cover {{ 
            display: table-cell; 
            vertical-align: middle; 
            width: 100%; 
            height: 100%; 
        }}
        img {{ 
            max-width: 100%; 
            max-height: 100%; 
            display: block; 
            margin: 0 auto;
            object-fit: contain;
        }}
    </style>
</head>
<body>
    <div class="cover">
        <img src="{cover_filename}" alt="Cover"/>
    </div>
</body>
</html>"""

            cover_page = epub.EpubHtml(
                title='Cover',
                file_name='cover.xhtml',
                uid='cover'
            )
            cover_page.content = cover_html
            book.add_item(cover_page)

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
        添加章节 (EPUB 3.0 格式)

        在每个不同数据源（大目录）的第一篇文章前插入一个章节分隔页，
        让阅读时能清楚地感知进入了新的栏目/分组。
        """
        chapter_id = 0
        divider_id = 0

        # 使用 book.spine 的当前值（ebooklib 会自动包含 cover 和 nav）
        # 如果 book.spine 未初始化，先设置 cover
        if not book.spine:
            book.spine = ['cover']
        spine = book.spine

        for source, articles, source_title in sections:
            # 在该分组的第一篇文章前插入章节分隔页，显示所属栏目标题
            section_title = self.toc_generator._get_source_title(
                source, articles, source_title
            )
            divider = epub.EpubHtml(
                title=section_title,
                file_name=f"divider_{divider_id}.xhtml"
            )
            divider.content = self._generate_section_divider_content(section_title, divider_id)
            book.add_item(divider)
            spine.append(divider)
            divider_id += 1

            for article in articles:
                # 生成章节内容
                chapter_content = self._generate_chapter_content(article, chapter_id)

                # 创建章节
                chapter = epub.EpubHtml(
                    title=article.title,
                    file_name=f"chapter_{chapter_id}.xhtml"
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

    def _generate_chapter_content(self, article: Article, chapter_id: int) -> str:
        """
        生成章节 HTML 内容 (EPUB 3.0 格式，返回目录链接在标题下方)

        Args:
            article: 文章对象
            chapter_id: 章节 ID

        Returns:
            str: HTML 内容
        """
        import html

        # 对标题和作者进行 HTML 转义，防止 & 等字符导致 XML 解析失败
        safe_title = html.escape(article.title)
        safe_author = html.escape(article.author) if article.author else ""

        # EPUB 3.0 使用 HTML5 DOCTYPE
        content_html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="zh" xml:lang="zh">
<head>
    <title>{safe_title}</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>{safe_title}</h1>
    <p class="toc-link"><a href="nav.xhtml#toc_chapter_{chapter_id}">返回目录</a></p>
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

    def _generate_section_divider_content(self, section_title: str, divider_id: int) -> str:
        """
        生成章节分隔页 HTML 内容 (EPUB 3.0 格式，返回目录链接在标题下方)

        在两个不同"大目录"之间插入，视觉上提示读者进入了新的栏目/分组。

        Args:
            section_title: 章节/栏目标题
            divider_id: 分隔页 ID

        Returns:
            str: HTML 内容
        """
        safe_title = html_module.escape(section_title)
        return f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="zh" xml:lang="zh">
<head>
    <title>{safe_title}</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>{safe_title}</h1>
    <p class="toc-link"><a href="nav.xhtml#toc_section_{divider_id}">返回目录</a></p>
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
            
            # 记录所有可能包含远程 URL 的属性，以便清理
            remote_attrs = ['data-src', 'data-original', 'data-actualsrc', 'data-lazy-src', 'srcset', 'data-srcset', 'file', 'zoom-target', 'original']
            
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
                for attr in remote_attrs:
                    val = img.get(attr)
                    if val and not any(ext in val.lower() for ext in ['.gif', '.svg']):
                        src = val
                        break
            
            if not src:
                src = img.get('src')
            
            # 彻底移除所有干扰属性，防止残留远程链接
            for attr in remote_attrs:
                if img.has_attr(attr):
                    del img[attr]

            if not src or src.startswith('data:'):
                if not src:
                    img.decompose()
                continue

            # 如果已经处理过这个 URL
            if src in url_to_filename:
                img['src'] = f"images/{url_to_filename[src]}"
                continue

            # 处理图片
            result = self.image_processor.download_and_process(src, article.url)

            if result:
                filename, img_data = result
                url_to_filename[src] = filename

                # 检查是否已经添加过这个 item
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

                # 更新图片 URL
                img['src'] = f"images/{filename}"
            else:
                # 处理失败：彻底移除标签，绝不保留 http 引用
                self.logger.debug(f"Removing image tag (processing failed or skipped): {src}")
                img.decompose()

        # 将修改后的 HTML 写回 chapter.content (Bug 2)
        # BeautifulSoup 会生成完整的 HTML 结构并正确处理转义字符
        chapter.content = str(soup)

    def _add_error_log_chapter(self, book: epub.EpubBook, error_log: List[str]):
        """
        添加错误日志章节 (EPUB 3.0 格式，返回目录链接在标题下方)

        Args:
            book: EPUB 书籍对象
            error_log: 错误日志列表
        """
        import html

        # EPUB 3.0 使用 HTML5 DOCTYPE
        content_html = """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="zh" xml:lang="zh">
<head>
    <title>错误日志</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>错误日志</h1>
    <p class="toc-link"><a href="nav.xhtml#toc_error_log">返回目录</a></p>
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
            file_name="error_log.xhtml"
        )
        chapter.content = content_html

        book.add_item(chapter)

        # 添加到目录
        book.toc.append(epub.Link("error_log.xhtml", "错误日志", "error_log"))

        # 添加到 spine（阅读顺序）
        if isinstance(book.spine, list):
            book.spine.append(chapter)

        self.logger.info("Error log chapter added to EPUB")

    def _generate_nav_content(self, book_title: str, toc: List[Union[epub.Link, Tuple[epub.Link, List[epub.Link]]]]) -> str:
        """
        手动生成 EPUB 3.0 的 nav.xhtml 内容，包含目录和地标 (landmarks)。
        为每个条目添加 ID 以便回跳。
        """
        import html
        from ebooklib import epub as epub_lib
        safe_title = html.escape(book_title)
        
        content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh" xml:lang="zh">
<head>
    <title>{safe_title}</title>
    <style type="text/css">
        body {{ font-family: sans-serif; padding: 1em; }}
        h1 {{ text-align: center; font-size: 1.6em; margin-bottom: 1.2em; border-bottom: 2px solid #333; padding-bottom: 0.5em; }}
        nav ol {{ list-style-type: none; margin: 0; padding: 0; }}
        nav li {{ margin: 0.8em 0; }}
        
        /* 大章节样式 (Section/Divider) */
        .section-link {{ 
            font-weight: bold; 
            font-size: 1.15em; 
            color: #222; 
            display: block;
            margin-bottom: 0.3em;
        }}
        
        /* 小章节/文章样式 (Article) */
        .article-link {{ 
            font-weight: normal; 
            font-size: 1.0em; 
            color: #0066cc; 
        }}
        
        nav li ol {{ 
            margin-left: 1.2em; 
            list-style-type: none; 
            border-left: 2px solid #eee;
            padding-left: 0.8em;
        }}
        
        nav li ol li {{ margin: 0.4em 0; }}
        
        a {{ text-decoration: none; }}
        .landmarks {{ margin-top: 2em; border-top: 1px solid #ccc; padding-top: 1em; display: none; }}
    </style>
</head>
<body>
    <nav epub:type="toc" id="toc">
        <h1>{safe_title}</h1>
        <ol>
"""
        for item in toc:
            if isinstance(item, epub_lib.Link):
                # 扁平链接（如 web/trending 或 error_log）
                # 这里的 web/trending 其实是该源的唯一入口，也使用大章节样式
                content += f'            <li id="toc_{item.uid}"><a class="section-link" href="{item.href}">{html.escape(item.title)}</a></li>\n'
            elif isinstance(item, tuple) and len(item) == 2:
                # 两级结构（如 mail/rss）
                section_link, links = item
                content += f'            <li id="toc_{section_link.uid}">\n'
                content += f'                <a class="section-link" href="{section_link.href}">{html.escape(section_link.title)}</a>\n'
                content += f'                <ol>\n'
                for link in links:
                    content += f'                    <li id="toc_{link.uid}"><a class="article-link" href="{link.href}">{html.escape(link.title)}</a></li>\n'
                content += f'                </ol>\n'
                content += f'            </li>\n'
        
        content += """        </ol>
    </nav>
    <nav epub:type="landmarks" class="landmarks">
        <h2>Landmarks</h2>
        <ol>
            <li><a epub:type="toc" href="nav.xhtml#toc">Table of Contents</a></li>
            <li><a epub:type="cover" href="cover.xhtml">Cover</a></li>
            <li><a epub:type="bodymatter" href="divider_0.xhtml">Start Reading</a></li>
        </ol>
    </nav>
</body>
</html>"""
        return content

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
.toc-link {
    margin-top: 2em;
    font-size: 0.9em;
    text-align: center;
}
.toc-link a {
    color: #0066cc;
    text-decoration: none;
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
        # 建议：如果还是失败，尝试将文件名改为纯英文/数字
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
