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
        # 1. 应用 exclude 规则（先于 chop，避免 chop 将 HTML 压扁为纯文本）
        if self.source.exclude:
            article.content = self._apply_exclude(article.content)

        # 2. 应用 chop 规则
        if self.source.chop:
            article.content = self._apply_chop(article.content)

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
        支持 Python 切片语法，如 "/[0:100]" 表示只保留前 100 个字符
        支持负数索引，如 "/[:-200]" 表示删除最后 200 个字符

        Args:
            html: HTML 内容

        Returns:
            str: 处理后的 HTML
        """
        if not self.source.chop:
            return html

        try:
            # 解析切片语法（支持负数索引，如 /[:-200]、/[-50:]）
            chop_pattern = r'/\[(-?\d*):(-?\d*)\]'
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
        应用 exclude 规则，在 HTML 源码上操作，保留标签结构

        支持三种模式：
          start  — 删除从开头到关键词（含）之间的全部内容
          end    — 删除从关键词（含）到结尾的全部内容
          exact  — 在 HTML 源码中精确匹配并删除（可包含 HTML 标签/链接）

        Args:
            html: HTML 内容

        Returns:
            str: 处理后的 HTML
        """
        if not self.source.exclude:
            return html

        rules = self.source.exclude
        if not isinstance(rules, list):
            self.logger.error(f"exclude must be a list of rules, got {type(rules).__name__}")
            return html

        for rule in rules:
            if not isinstance(rule, dict):
                self.logger.warning(f"Skipping non-dict exclude rule: {rule}")
                continue

            rule_type = rule.get("type", "").strip()
            value = rule.get("value", "")

            if not value:
                self.logger.warning(f"Skipping exclude rule with empty value: {rule}")
                continue

            try:
                if rule_type == "start":
                    html = self._delete_from_start(html, value)
                elif rule_type == "end":
                    html = self._delete_from_end(html, value)
                elif rule_type == "exact":
                    html = self._delete_exact(html, value)
                else:
                    self.logger.warning(f"Unknown exclude rule type: '{rule_type}'")
            except Exception as e:
                self.logger.error(f"Failed to apply exclude rule {rule}: {e}")

        # 清理空标签
        html = self._cleanup_empty_tags(html)

        return html

    # ------------------------------------------------------------------
    # exclude 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _iter_text_nodes(html: str):
        """
        解析 HTML 并返回 (soup, 文本节点列表)

        文本节点按文档顺序排列，每个元素是 BeautifulSoup 的 NavigableString，
        对其 .string 赋值会直接反映到 DOM 树上。
        """
        from bs4 import NavigableString
        soup = BeautifulSoup(html, 'lxml')
        body = soup.body if soup.body else soup
        text_nodes = [n for n in body.find_all(string=True) if isinstance(n, NavigableString)]
        return soup, text_nodes

    def _delete_from_start(self, html: str, keyword: str) -> str:
        """删除从文档开头到 keyword（含 keyword 本身）之间的全部内容"""
        soup = BeautifulSoup(html, 'lxml')
        
        # 1. 寻找第一个包含 keyword 的文本节点
        target_node = None
        for node in soup.find_all(string=True):
            if keyword in node:
                target_node = node
                break
        
        if target_node:
            # 找到关键词所在位置
            text = str(target_node)
            idx = text.find(keyword)
            
            # 保留关键词之后的内容
            remaining_text = text[idx + len(keyword):]
            
            # 向上递归处理：删除当前节点及其所有父节点之前的兄弟节点
            curr = target_node
            while curr and curr.name != '[document]':
                # 获取当前节点的所有前序兄弟节点（包括元素、文本等）
                # 必须转换为列表，因为 extract() 会改变迭代器
                for prev in list(curr.previous_siblings):
                    prev.extract()
                curr = curr.parent
            
            # 更新目标文本节点的内容
            if remaining_text:
                target_node.replace_with(remaining_text)
            else:
                target_node.extract()
                
            return str(soup.body if soup.body else soup)

        # 2. 如果单节点没找到，尝试跨节点检查（仅做文本层面的检查，但不建议破坏结构）
        full_text = soup.get_text()
        if keyword in full_text:
            self.logger.warning(
                f"exclude 'start' keyword '{keyword}' spans multiple nodes. "
                "Structure preservation might be imperfect."
            )
            # 这里的策略：如果跨节点，我们至少不再退回到纯文本
            # 而是尝试定位到大致的元素位置，或者直接报错不处理以保护图片
            # 目前采用更安全的做法：如果不确定如何精确切割 DOM，则不执行删除，以保护图片
            # 除非是极简单的文档，否则跨节点切割 DOM 非常容易出错
            return html

        self.logger.debug(f"exclude 'start' keyword not found: '{keyword}'")
        return html

    def _delete_from_end(self, html: str, keyword: str) -> str:
        """删除从 keyword（含 keyword 本身）到文档结尾的全部内容"""
        soup = BeautifulSoup(html, 'lxml')
        
        # 1. 寻找最后一个包含 keyword 的文本节点（从后往前找）
        text_nodes = soup.find_all(string=True)
        target_node = None
        for node in reversed(text_nodes):
            if keyword in node:
                target_node = node
                break
        
        if target_node:
            # 找到关键词最后一次出现的位置
            text = str(target_node)
            idx = text.rfind(keyword)
            
            # 保留关键词之前的内容
            remaining_text = text[:idx]
            
            # 向上递归处理：删除当前节点及其所有父节点之后的兄弟节点
            curr = target_node
            while curr and curr.name != '[document]':
                # 获取当前节点的所有后续兄弟节点
                for nxt in list(curr.next_siblings):
                    nxt.extract()
                curr = curr.parent
            
            # 更新目标文本节点的内容
            if remaining_text:
                target_node.replace_with(remaining_text)
            else:
                target_node.extract()
                
            return str(soup.body if soup.body else soup)

        # 2. 跨节点检查
        full_text = soup.get_text()
        if keyword in full_text:
            self.logger.warning(
                f"exclude 'end' keyword '{keyword}' spans multiple nodes. "
                "Deletion skipped to preserve HTML structure and images."
            )
            return html

        self.logger.debug(f"exclude 'end' keyword not found: '{keyword}'")
        return html

    @staticmethod
    def _delete_exact(html: str, keyword: str) -> str:
        """在 HTML 源码中精确匹配 keyword 并删除所有出现（keyword 可含 HTML 标签）"""
        if keyword not in html:
            return html
        return html.replace(keyword, "")

    @staticmethod
    def _cleanup_empty_tags(html: str) -> str:
        """移除没有文本内容且无子标签的空标签，但保留 img, br, hr 等自闭合标签"""
        soup = BeautifulSoup(html, 'lxml')
        body = soup.body if soup.body else soup

        # 允许不包含内容或子标签的标签列表（自闭合标签或特殊标签）
        allowed_empty_tags = {'img', 'br', 'hr', 'td', 'th', 'iframe', 'video', 'audio'}

        # 逆序遍历，避免删除父标签后子标签引用失效
        for tag in reversed(body.find_all(True)):
            if tag.name in ('html', 'body', 'head') or tag.name in allowed_empty_tags:
                continue
            
            # 没有任何文本内容且没有子标签 → 视为真正可以删除的空标签
            if not tag.get_text(strip=True) and not tag.find_all(True):
                tag.extract()

        return str(soup.body if soup.body else soup)

    def _remove_links(self, html: str) -> str:
        """
        移除所有超链接，保留内部标签（如图片）

        Args:
            html: HTML 内容

        Returns:
            str: 处理后的 HTML
        """
        soup = BeautifulSoup(html, 'lxml')

        # 使用 unwrap() 移除 <a> 标签本身，但保留其子节点
        for link in soup.find_all('a'):
            link.unwrap()

        return str(soup)

    def _clean_html(self, html: str) -> str:
        """
        清洗 HTML
        移除不需要的标签和属性，修复 EPUB 验证错误

        Args:
            html: HTML 内容

        Returns:
            str: 清洗后的 HTML 片段
        """
        soup = BeautifulSoup(html, 'lxml')

        # === EPUB 验证修复规则 ===

        # 1. 转换废弃/非法标签
        # <row> → <tr>（表格行）
        for row in soup.find_all('row'):
            row.name = 'tr'

        # <cell> → <td>（表格单元格）
        for cell in soup.find_all('cell'):
            cell.name = 'td'

        # <font> → <span>，保留样式属性
        for font in soup.find_all('font'):
            font.name = 'span'
            # 将 color/face/size 转换为 style
            style_parts = []
            if font.get('color'):
                style_parts.append(f"color:{font['color']}")
                del font['color']
            if font.get('face'):
                style_parts.append(f"font-family:{font['face']}")
                del font['face']
            if font.get('size'):
                # HTML font size 1-7 转换为 px
                sizes = {'1': '8', '2': '10', '3': '12', '4': '14', '5': '18', '6': '24', '7': '36'}
                px = sizes.get(font['size'], '12')
                style_parts.append(f"font-size:{px}px")
                del font['size']
            if style_parts:
                font['style'] = ';'.join(style_parts)

        # 2. 修复图片属性：width/height 必须是整数
        for img in soup.find_all('img'):
            # 处理 width 属性
            if 'width' in img.attrs:
                width_value = img.get('width', '')
                if isinstance(width_value, str):
                    width_str = width_value.strip()
                    if width_str:  # 非空字符串
                        try:
                            width = int(float(width_str))
                            img['width'] = str(width)
                        except (ValueError, TypeError):
                            del img['width']
                    else:  # 空字符串，删除属性
                        del img['width']

            # 处理 height 属性
            if 'height' in img.attrs:
                height_value = img.get('height', '')
                if isinstance(height_value, str):
                    height_str = height_value.strip()
                    if height_str:  # 非空字符串
                        try:
                            height = int(float(height_str))
                            img['height'] = str(height)
                        except (ValueError, TypeError):
                            del img['height']
                    else:  # 空字符串，删除属性
                        del img['height']

        # 3. 移除 SVG 和远程资源标签
        # SVG 缺少命名空间会导致 EPUB 验证失败
        # 视频/音频是远程资源，Kindle 不支持
        for tag in soup(['svg', 'video', 'source', 'audio', 'track']):
            tag.decompose()

        # 4. 修复嵌套结构：块级元素不能在 <p> 内
        self._fix_nested_blocks(soup)

        # === 原有安全规则 ===

        # 移除 script 和 style 标签
        for tag in soup(['script', 'style', 'iframe', 'form', 'input', 'button', 'noscript']):
            tag.decompose()

        # 移除不安全的属性
        # 保留基本属性和图片处理所需的属性，以及表格/样式属性
        allowed_attrs = [
            'href', 'src', 'alt', 'title', 'class', 'style',
            'srcset', 'data-srcset', 'data-src', 'data-original',
            'data-actualsrc', 'data-lazy-src', 'file', 'zoom-target', 'original',
            'width', 'height', 'colspan', 'rowspan', 'id'
        ]

        for tag in soup.find_all(True):
            attrs = dict(tag.attrs)
            for attr in attrs:
                if attr not in allowed_attrs:
                    del tag[attr]

        # 仅返回 body 内部的内容，避免产生嵌套的 html/body 标签
        if soup.body:
            return soup.body.decode_contents()
        return str(soup)

    def _fix_nested_blocks(self, soup: BeautifulSoup) -> None:
        """
        修复 HTML 嵌套结构问题
        将 <p> 内的块级元素移出，确保 EPUB 验证通过

        EPUB 3.3 不允许 <p> 内包含块级元素（section, div, p 等）

        Args:
            soup: BeautifulSoup 解析对象
        """
        block_elements = {
            'section', 'div', 'article', 'aside', 'header', 'footer',
            'nav', 'main', 'figure', 'blockquote', 'pre', 'ul', 'ol',
            'li', 'table', 'form', 'fieldset', 'h1', 'h2', 'h3',
            'h4', 'h5', 'h6', 'p', 'address', 'hr', 'dl', 'dt', 'dd'
        }

        # 多次遍历确保深度嵌套也被修复
        # 增加迭代次数到 5 次，确保多层嵌套都被处理
        for _ in range(5):
            fixed_count = 0
            for p_tag in soup.find_all('p'):
                children_to_move = []
                for child in p_tag.children:
                    if hasattr(child, 'name') and child.name in block_elements:
                        children_to_move.append(child)

                for child in children_to_move:
                    child.extract()
                    p_tag.insert_after(child)
                    fixed_count += 1

            # 如果没有修复任何问题，提前退出
            if fixed_count == 0:
                break

    def _ensure_valid_html(self, html: str) -> str:
        """
        确保 HTML 格式正确
        主要用于修复未闭合标签

        Args:
            html: HTML 内容

        Returns:
            str: 有效的 HTML 片段
        """
        # 使用 BeautifulSoup 的修复能力
        soup = BeautifulSoup(html, 'lxml')
        
        if soup.body:
            return soup.body.decode_contents()
        return str(soup)
