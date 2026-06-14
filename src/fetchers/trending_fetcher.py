"""
热点分析抓取器模块
调用 LLM API 生成热点分析内容
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any

from src.config import ContentSource, get_openrouter_config
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.utils.logger import get_logger


class TrendingFetcher(BaseFetcher):
    """热点分析抓取器"""

    def __init__(self, source: ContentSource):
        """
        初始化热点分析抓取器

        Args:
            source: 内容源配置
        """
        super().__init__(source)
        self.config = get_openrouter_config()

        if not self.config:
            self.logger.warning(
                "OPENROUTER_API_KEY not configured. Trending analysis will be skipped."
            )

    def fetch(self) -> FetchResult:
        """
        执行热点分析抓取

        Returns:
            FetchResult: 抓取结果
        """
        result = FetchResult(source=self.source, articles=[])

        # 检查配置
        if not self.config:
            result.success = False
            result.error = "OPENROUTER_API_KEY not configured"
            return result

        # 检查是否有 goal 配置
        if not self.source.goal:
            result.success = False
            result.error = "goal is required for trending type"
            return result

        try:
            # 调用 LLM API
            analysis = self._call_llm_api()

            if not analysis:
                result.success = False
                result.error = "Failed to get analysis from LLM"
                return result

            # 创建文章对象
            title = self.source.title or f"热点分析: {self.source.src}"
            article = Article(
                title=title,
                content=analysis,
                url=self.source.src,
                author="AI Analysis",
                published_date=datetime.now().isoformat(),
                metadata={
                    "goal": self.source.goal,
                    "model": self.source.model or "default"
                }
            )

            result.articles.append(article)
            return result

        except Exception as e:
            self.logger.error(f"Trending fetch failed: {e}")
            result.success = False
            result.error = str(e)
            return result

    def _call_llm_api(self) -> Optional[str]:
        """
        调用 LLM API

        Returns:
            Optional[str]: 分析结果 HTML
        """
        # 构造 prompt
        prompt = self._build_prompt()

        # 构造请求
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }

        # 确定使用的模型：source.model > OPENROUTER_MODEL secret > 默认值
        model = (
            self.source.model
            or (self.config.get("model") if self.config else None)
            or "google/gemma-4-31b-it:free"
        )

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的信息分析师，擅长总结和分析热点信息。请用 HTML 格式输出分析结果，包含清晰的标题和段落。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        try:
            # 使用 httpx 发送 POST 请求
            import httpx
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    self.config['endpoint'],
                    headers=headers,
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()

            # 提取响应内容
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                return self._format_as_html(content)

            self.logger.error(f"Unexpected API response: {data}")
            return None

        except Exception as e:
            self.logger.error(f"LLM API call failed: {e}")
            return None

    def _build_prompt(self) -> str:
        """
        构造 prompt

        Returns:
            str: prompt 文本
        """
        return f"""
请根据以下要求，分析并总结相关热点信息：

主题/关键词: {self.source.src}
分析目标: {self.source.goal}

请提供：
1. 最新的热点动态（3-5 个要点）
2. 关键趋势分析
3. 值得关注的亮点

请用清晰的结构和简洁的语言输出，确保内容有价值且易于阅读。
"""

    def _format_as_html(self, text: str) -> str:
        """
        将文本格式化为 HTML

        Args:
            text: 原始文本

        Returns:
            str: HTML 格式文本
        """
        # 简单处理：将换行转换为段落
        paragraphs = text.split('\n\n')
        html_parts = []

        for para in paragraphs:
            para = para.strip()
            if para:
                # 处理标题（以 # 开头）
                if para.startswith('#'):
                    level = len(para.split(' ')[0])
                    title_text = para.lstrip('#').strip()
                    html_parts.append(f"<h{level}>{title_text}</h{level}>")
                # 处理列表（以 - 或 * 开头）
                elif para.startswith('-') or para.startswith('*'):
                    items = para.split('\n')
                    html_parts.append("<ul>")
                    for item in items:
                        item = item.strip('-* ').strip()
                        if item:
                            html_parts.append(f"<li>{item}</li>")
                    html_parts.append("</ul>")
                else:
                    # 普通段落
                    html_parts.append(f"<p>{para}</p>")

        return '\n'.join(html_parts)
