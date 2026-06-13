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
    简单的实现，去除 HTML 标签
    """
    if not html:
        return ""

    # 移除 script 和 style 标签及其内容
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)

    # 解码 HTML 实体
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")

    # 移除多余的空白
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
