"""
辅助函数模块
提供通用的工具函数
"""

import re
import hashlib
from typing import Optional
from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    """
    标准化 URL
    移除末尾斜杠、统一协议等
    """
    if not url:
        return ""

    # 移除片段和查询参数（用于去重）
    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    # 移除末尾斜杠
    normalized = normalized.rstrip('/')

    return normalized


def generate_content_id(url: str, title: Optional[str] = None) -> str:
    """
    生成内容唯一标识符
    用于去重追踪
    """
    # 使用 URL 和标题的组合作为标识
    content = normalize_url(url)
    if title:
        content += f"|{title}"

    return hashlib.md5(content.encode('utf-8')).hexdigest()


def extract_text_from_html(html: str) -> str:
    """
    从 HTML 中提取纯文本
    保留段落间的换行和基本的文本格式标签（b, strong, i, em, u）
    """
    if not html:
        return ""

    # 移除 script 和 style 标签及其内容
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 将块级元素（如 p, div, br, li）替换为换行符，保留段落结构
    text = re.sub(r'</?(p|div|h[1-6]|li|tr|table|blockquote|pre|ul|ol)[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)

    # 保留文本格式标签：粗体（b, strong）、斜体（i, em）、下划线（u）
    # 将其他 HTML 标签替换为空字符串
    def replace_tag(match):
        tag = match.group(1).lower()
        # 保留这些标签的标签名（包括闭合标签）
        if tag in ['b', 'strong', 'i', 'em', 'u']:
            return match.group(0)  # 保留原始标签
        return ''  # 移除其他标签

    # 使用正则表达式保留特定标签，移除其他标签
    text = re.sub(r'<(/?)([a-z][a-z0-9]*)[^>]*>', replace_tag, text, flags=re.IGNORECASE)

    # 解码 HTML 实体
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")

    # 合并多个连续的换行符为两个（保留段落间隔）
    text = re.sub(r'\n\s*\n', '\n\n', text)

    # 移除行首尾的空白字符，但保留段落间的换行
    text = re.sub(r'[ \t]+(?=\n)', '', text)  # 移除换行前的空格
    text = re.sub(r'\n[ \t]+', '\n', text)  # 移除换行后的空格

    # 移除行内的多余空白，包括换行
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def truncate_text(text: str, max_length: int = 200) -> str:
    """
    截断文本
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length] + "..."


def is_valid_url(url: str) -> bool:
    """
    验证 URL 是否有效
    """
    if not url:
        return False

    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """
    清理文件名
    移除非法字符
    """
    # 移除文件系统不允许的字符
    illegal_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(illegal_chars, '_', filename)

    # 限制长度
    if len(sanitized) > 200:
        sanitized = sanitized[:200]

    return sanitized.strip()


def format_date(date_str: str) -> str:
    """
    统一日期格式化

    支持的输入格式：
    - RFC 822 (如: "Mon, 14 Jun 2026 10:30:00 GMT")
    - ISO 8601 (如: "2026-06-14T10:30:00")
    - Unix 时间戳（秒或毫秒，如: "1718343000" 或 "1718343000000"）
    - 任意字符串（原样返回）

    输出格式：YYYY-MM-DD HH:MM

    Args:
        date_str: 日期字符串

    Returns:
        str: 格式化后的日期
    """
    if not date_str:
        return ""

    # 尝试解析为 datetime 对象
    from datetime import datetime

    # 首先检查是否是纯数字（时间戳）
    if isinstance(date_str, str) and date_str.isdigit():
        try:
            timestamp = int(date_str)
            # 判断是秒还是毫秒（毫秒 > 1e12）
            if timestamp > 1_000_000_000_000:
                timestamp = timestamp / 1000  # 毫秒转秒
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError, OverflowError):
            pass  # 继续尝试其他格式

    # 尝试常见的日期格式
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",  # RFC 822: "Mon, 14 Jun 2026 10:30:00 GMT"
        "%a, %d %b %Y %H:%M:%S %z",  # RFC 822 with timezone offset
        "%Y-%m-%dT%H:%M:%S",  # ISO 8601: "2026-06-14T10:30:00"
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO 8601 with microseconds
        "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601 with timezone
        "%Y-%m-%d %H:%M:%S",  # Standard format
        "%Y/%m/%d %H:%M:%S",  # Alternative separator
        "%Y-%m-%d",  # Date only
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            continue

    # 如果都解析失败，尝试使用 dateutil（如果有安装）
    try:
        from dateutil import parser
        dt = parser.parse(date_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ImportError, ValueError, TypeError, OverflowError):
        # 最后手段：返回原始字符串
        return date_str
