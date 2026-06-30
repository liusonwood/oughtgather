"""
EPUB 辅助工具模块
提供统一的、可复用的 HTML 组件生成器（如返回目录超链接、章节分隔页等）
"""

import html as html_module
from ebooklib import epub


def generate_toc_link(target_id: str) -> str:
    """
    生成统一的 “返回目录” 超链接 HTML 片段

    Args:
        target_id (str): nav.xhtml 中的锚点 ID (例如 'toc_chapter_1', 'toc_section_0', 'toc_summary')

    Returns:
        str: HTML 片段
    """
    return f'<p class="toc-link"><a href="nav.xhtml#{target_id}">返回目录</a></p>'


def create_section_divider_page(section_title: str, file_name: str, target_toc_id: str) -> epub.EpubHtml:
    """
    创建统一的章节分隔页 (EpubHtml 对象)

    在两个不同 "大目录" 之间插入，视觉上提示读者进入了新的栏目/分组。

    Args:
        section_title (str): 章节/栏目标题
        file_name (str): 分隔页的文件名 (例如 'divider_0.xhtml')
        target_toc_id (str): 返回目录链接指向的 TOC 元素的 ID

    Returns:
        epub.EpubHtml: 分隔页对象
    """
    safe_title = html_module.escape(section_title)
    toc_link = generate_toc_link(target_toc_id)

    content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" lang="zh" xml:lang="zh">
<head>
    <title>{safe_title}</title>
    <link rel="stylesheet" type="text/css" href="style/default.css"/>
</head>
<body>
    <h1>{safe_title}</h1>
    {toc_link}
</body>
</html>"""

    divider = epub.EpubHtml(
        title=section_title,
        file_name=file_name
    )
    divider.content = content
    return divider
