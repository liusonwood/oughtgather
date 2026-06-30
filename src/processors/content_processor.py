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
        # 1. 应用 exclude 规则
        if self.source.exclude:
            article.content = self._apply_exclude(article.content)

        # 2. 应用 keep_link 规则
        if self.source.keep_link == "N":
            article.content = self._remove_links(article.content)

        # 3. 清洗 HTML
        article.content = self._clean_html(article.content)

        # 4. 确保 HTML 格式正确
        article.content = self._ensure_valid_html(article.content)

        # 5. 包裹 Emoji
        article.content = self.wrap_emojis(article.content)

        return article

    @staticmethod
    def wrap_emojis(html: str) -> str:
        """
        使用正则表达式找出文本中的常见表情符号，并用 <span class="emoji"> 包裹。
        """
        # 匹配常见 Emoji 的 Unicode 范围（包含杂项符号、表情、交通、补充符号等）
        # 注意：对于超过 4 位的 Unicode 码点，必须使用 \U0001Fxxx 格式
        emoji_pattern = re.compile(
            r'('
            r'[\u2600-\u27BF]|'      # 杂项符号、装饰符号、丁坝符
            r'[\U0001F300-\U0001F5FF]|'    # 杂项符号和象形文字
            r'[\U0001F600-\U0001F64F]|'    # 表情 (Emoticons)
            r'[\U0001F680-\U0001F6FF]|'    # 交通和地图符号
            r'[\U0001F900-\U0001F9FF]|'    # 补充符号和象形文字
            r'[\U0001F1E6-\U0001F1FF]+'    # 国家/地区旗帜符号
            r')'
        )
        
        # 使用 BeautifulSoup 避免破坏标签结构
        soup = BeautifulSoup(html, 'lxml')
        
        # 只处理文本节点
        for text_node in soup.find_all(string=True):
            # 跳过已经在 span.emoji 中的节点
            if text_node.parent.name == 'span' and text_node.parent.get('class') == ['emoji']:
                continue
                
            if emoji_pattern.search(text_node):
                new_text = emoji_pattern.sub(r'<span class="emoji">\1</span>', str(text_node))
                # 重新解析含有 span 的字符串片段
                new_node = BeautifulSoup(new_text, 'lxml').body.contents[0]
                text_node.replace_with(new_node)
                
        if soup.body:
            return soup.body.decode_contents()
        return str(soup)

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

    def _is_small_rendered_image(self, img_tag: BeautifulSoup) -> bool:
        """检查图片是否为包含在 <a> 中的渲染尺寸较小的图片"""
        if not img_tag.find_parent('a'):
            return False

        # 检查 width/height 属性
        for attr in ['width', 'height']:
            val = img_tag.get(attr)
            if val and val.isdigit() and int(val) <= 32:
                return True

        # 检查 style 属性
        style = img_tag.get('style', '').lower()
        if 'max-width' in style or 'width' in style:
            matches = re.findall(r'(\d+)px', style)
            for val in matches:
                if int(val) <= 32:
                    return True
        return False

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

        # === 布局清洗：将复杂的、嵌套的邮件/网页模版表格拆解为普通文本流 ===
        self._unwrap_layout_tables(soup)

        # === 预过滤：移除被包含在 <a> 中的社交小图标 ===
        for img in soup.find_all('img'):
            if self._is_small_rendered_image(img):
                parent_a = img.find_parent('a')
                if parent_a:
                    parent_a.decompose()

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
            # 将 face/size 转换为 style
            style_parts = []
            # 忽略 color 属性以避免在 Kindle 上显示为灰色
            if font.get('color'):
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

        # 清洗所有标签的 style 属性，移除颜色设置以及对非 img 标签的布局约束
        layout_properties_to_remove = {
            'width', 'height', 'min-width', 'max-width', 'min-height', 'max-height',
            'margin', 'margin-top', 'margin-bottom', 'margin-left', 'margin-right',
            'padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right',
            'position', 'top', 'bottom', 'left', 'right', 'float', 'clear',
            'display', 'flex', 'grid', 'border', 'background', 'background-image'
        }

        for tag in soup.find_all(True):
            if 'style' in tag.attrs:
                style_str = tag['style']
                # 移除 color 和 background-color 属性
                new_style = re.sub(r'(?i)\b(background-)?color\s*:[^;]+(;|$)', '', style_str)
                
                # 如果不是 img 标签，进一步移除布局和尺寸相关限制属性
                if tag.name != 'img':
                    parts = new_style.split(';')
                    filtered_parts = []
                    for part in parts:
                        part_strip = part.strip()
                        if not part_strip or ':' not in part_strip:
                            continue
                        prop, val = part_strip.split(':', 1)
                        prop_name = prop.strip().lower()
                        if prop_name in layout_properties_to_remove or 'background' in prop_name:
                            continue
                        filtered_parts.append(f"{prop_name}:{val.strip()}")
                    new_style = ';'.join(filtered_parts)

                # 移除多余的空格和分号
                new_style = new_style.strip().strip(';')
                if new_style:
                    tag['style'] = new_style
                else:
                    del tag['style']

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
                # 限制 width/height 属性只能在 img 标签上保留，防止复杂的表格固定宽度导致挤压
                elif attr in ('width', 'height') and tag.name != 'img':
                    del tag[attr]

        # 仅返回 body 内部的内容，避免产生嵌套 of html/body 标签
        if soup.body:
            return soup.body.decode_contents()
        return str(soup)

    def _unwrap_layout_tables(self, soup: BeautifulSoup) -> None:
        """
        拆解用于定位、边距和邮件模版布局的表格标签。
        若表格带有 role="presentation" 或 role="none"，或每行最多只有一个单元格（单列包装），
        或包含嵌套的表格，则将其子项（tr/td/tbody等）以及 table 标签自身全部拆开，使其流式排版，
        能自适应 Kindle 等电子书阅读器的屏幕尺寸。
        """
        # 采用自下而上的逆序遍历，确保嵌套表格能从小到大依次正确拆解
        for table in reversed(soup.find_all('table')):
            is_layout = False
            
            # 1. 显式指定的布局角色
            role = table.get('role')
            if role in ('presentation', 'none'):
                is_layout = True
            else:
                # 2. 判断是否是单列包裹表格或多层嵌套包裹表格
                max_cols = 0
                for tr in table.find_all('tr', recursive=False):
                    cells = tr.find_all(['td', 'th'], recursive=False)
                    max_cols = max(max_cols, len(cells))
                
                has_nested_table = bool(table.find('table'))
                
                if max_cols <= 1 or has_nested_table:
                    is_layout = True

            if is_layout:
                # 找到该 table 内的所有布局辅助标签（按深度倒序，防止父子标签拆解时影响树结构）
                tags_to_unwrap = table.find_all(['tbody', 'thead', 'tfoot', 'tr', 'td', 'th'])
                for tag in reversed(tags_to_unwrap):
                    tag.unwrap()
                table.unwrap()

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
