"""
配置管理模块
负责加载、验证和提供配置访问接口
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from src.utils.helpers import get_now


@dataclass
class TitleConfig:
    """标题配置"""
    text: str
    img: Optional[str] = None

    def get_display_text(self) -> str:
        """获取显示文本，处理时间占位符"""
        now = get_now()
        result = self.text
        date_str = now.strftime("%Y-%m-%d")

        # 先处理 {xxx {time}} 格式（必须在简单替换之前，否则 {time} 会被提前替换掉）
        import re
        pattern = r'\{([^{}]+)\{time\}\}'
        def _replace_complex(m):
            prefix = m.group(1).strip()
            return f"{prefix} {date_str}"
        result = re.sub(pattern, _replace_complex, result)

        # 再替换剩余的独立 {time}
        if "{time}" in result:
            result = result.replace("{time}", date_str)

        return result

    def get_plain_text(self) -> str:
        """获取纯文本标题，去除所有 HTML 标签（如 </br>、<a> 等）"""
        import re
        text = self.get_display_text()
        # 移除所有 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()


@dataclass
class ContentSource:
    """内容源配置"""
    type: str  # mail / rss / web / trending
    src: str
    priority: int = 0
    title: Optional[str] = None
    keep_link: str = "Y"
    full_text: str = "N"
    chop: Optional[str] = None
    exclude: Optional[List[Dict[str, str]]] = None
    delete: Optional[str] = None
    goal: Optional[str] = None
    model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # 额外的配置参数

    def __post_init__(self):
        """验证配置"""
        valid_types = {"mail", "rss", "web", "trending"}
        if self.type not in valid_types:
            raise ValueError(f"Invalid type: {self.type}. Must be one of {valid_types}")

        if not self.src:
            raise ValueError("src is required")

        # 验证 trending 类型的特殊要求
        if self.type == "trending" and not self.goal:
            self.goal = "分析并总结相关热点信息"


@dataclass
class Config:
    """全局配置"""
    title: TitleConfig
    body: List[ContentSource]
    limit: int = 15  # 全局每源抓取上限

    def get_sorted_sources(self) -> List[ContentSource]:
        """获取按优先级排序的内容源（降序，稳定排序）"""
        return sorted(self.body, key=lambda x: x.priority, reverse=True)


def load_config(config_path: str = "config.json") -> Config:
    """
    加载配置

    优先级：
    1. CONFIG_JSON 环境变量
    2. config.json 文件
    """
    config_data = None

    # 1. 尝试从环境变量加载
    config_json_env = os.getenv("CONFIG_JSON")
    if config_json_env:
        try:
            config_data = json.loads(config_json_env)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse CONFIG_JSON: {e}")
    else:
        # 2. 从文件加载
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Please create config.json or set CONFIG_JSON environment variable"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

    # 验证和解析配置
    return _parse_config(config_data)


def _parse_config(data: Dict[str, Any]) -> Config:
    """解析配置数据"""
    # 解析标题配置
    if "title" not in data:
        raise ValueError("title is required in config")

    title_data = data["title"]
    title_config = TitleConfig(
        text=title_data.get("text", "Daily News"),
        img=title_data.get("img")
    )

    # 解析内容源配置
    if "body" not in data or not isinstance(data["body"], list):
        raise ValueError("body must be a non-empty array in config")

    sources = []
    for idx, source_data in enumerate(data["body"]):
        try:
            source = ContentSource(
                type=source_data.get("type"),
                src=source_data.get("src"),
                priority=source_data.get("priority", 0),
                title=source_data.get("title"),
                keep_link=source_data.get("keep_link", "Y"),
                full_text=source_data.get("full_text", "N"),
                chop=source_data.get("chop"),
                exclude=source_data.get("exclude"),
                delete=source_data.get("delete"),
                goal=source_data.get("goal"),
                model=source_data.get("model"),
                metadata=source_data.get("metadata")
            )
            sources.append(source)
        except Exception as e:
            raise ValueError(f"Error parsing body[{idx}]: {e}")

    return Config(
        title=title_config,
        body=sources,
        limit=data.get("limit", 15)
    )


def get_secret(secret_name: str, required: bool = True) -> Optional[str]:
    """
    获取 Secret 值

    Args:
        secret_name: Secret 名称
        required: 是否必需

    Returns:
        Secret 值

    Raises:
        ValueError: 如果必需的 Secret 不存在
    """
    value = os.getenv(secret_name)

    if required and not value:
        raise ValueError(
            f"Required secret '{secret_name}' is not set. "
            f"Please add it to GitHub Secrets or environment variables."
        )

    return value


def get_smtp_config() -> Dict[str, str]:
    """获取 SMTP 配置"""
    return {
        "host": get_secret("SMTP_HOST"),
        "port": int(get_secret("SMTP_PORT")),
        "username": get_secret("SMTP_USERNAME"),
        "password": get_secret("SMTP_PASSWORD"),
        "kindle_email": get_secret("KINDLE_EMAIL")
    }


def get_testmail_config() -> Optional[Dict[str, str]]:
    """获取 TestMail 配置（可选）"""
    api_key = get_secret("TESTMAIL_APP_API_KEY", required=False)
    if api_key:
        return {"api_key": api_key}
    return None


def get_openrouter_config() -> Optional[Dict[str, str]]:
    """获取 OpenRouter 配置（可选）"""
    api_key = get_secret("OPENROUTER_API_KEY", required=False)
    endpoint = get_secret("OPENROUTER_API_ENDPOINT", required=False)
    model = get_secret("OPENROUTER_MODEL", required=False)

    if api_key:
        return {
            "api_key": api_key,
            "endpoint": endpoint or "https://openrouter.ai/api/v1/chat/completions",
            "model": model,  # None if not set; caller falls back to its own default
        }
    return None
