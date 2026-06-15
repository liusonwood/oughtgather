"""
热点分析抓取器模块
调用 LLM API 生成热点分析内容
"""

import json
import markdown
from datetime import datetime
from typing import Optional, Dict, Any

from src.config import ContentSource, get_openrouter_config
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.utils.logger import get_logger
from src.utils.helpers import generate_content_id, get_now


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

            # 创建文章对象（带当日时间戳，用于去重哈希计算）
            title = self.source.title or f"热点分析: {self.source.src}"
            today = get_now().strftime("%Y-%m-%d")
            article = Article(
                title=title,
                content=analysis,
                url=self.source.src,
                author="AI Analysis",
                published_date=today,
                metadata={
                    "goal": self.source.goal,
                    "model": self.source.model or "default"
                }
            )

            # 记录带时间戳的去重哈希
            content_id = generate_content_id(article.url, article.title, today)
            self.logger.info(f"Trending dedup hash [{today}]: src={self.source.src}, hash={content_id}")

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
                    "content": (
                        "你是一位资深行业分析师，专注于捕捉前沿信息、识别关键趋势并提炼可行动的洞察。"
                        "你的分析风格：深度优于广度，数据支撑观点，避免套话与泛泛而谈，语言简练有力。\n\n"
                        "输出规范：\n"
                        "- 严格使用 Markdown 格式，层级清晰（H2/H3/列表/加粗）\n"
                        "- 每个要点须包含具体事实或数据，禁止空洞描述\n"
                        "- 若涉及不确定信息，明确标注「待验证」\n"
                        "- 不要输出 ```markdown``` 代码块包裹符"
                    )
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
        today = get_now().strftime("%Y年%m月%d日")
        return f"""## 分析任务

**当前日期**: {today}
**分析主题**: {self.source.src}
**核心目标**: {self.source.goal}

## 输出要求

请围绕上述主题，提供一份结构化的深度分析报告，涵盖以下维度：

### 1. 近期热点动态（3-5 条）
- 列举近期最值得关注的具体事件或进展
- 每条须有时间线索或具体来源（如有）

### 2. 关键趋势与信号
- 识别 2-3 个正在形成的中长期趋势
- 说明每个趋势的驱动因素

### 3. 核心洞察与行动建议
- 提炼 1-2 个最值得关注的核心洞察
- 给出对目标用户有实际价值的建议或启示

## 质量标准
- 内容基于事实，避免猜测；不确定信息标注「待验证」
- 语言精炼，每条要点不超过 60 字
- 避免陈词滥调，突出差异化视角
"""

    def _format_as_html(self, text: str) -> str:
        """
        将 Markdown 文本转换为 HTML

        Args:
            text: Markdown 文本

        Returns:
            str: HTML 格式文本
        """
        # 清理 LLM 可能返回的代码块标记（如 ```markdown...``` 或 '''markdown...'''）
        text = self._remove_code_block_markers(text)

        # 使用 markdown 库转换为 HTML
        html = markdown.markdown(
            text,
            extensions=[
                'extra',  # 支持表格、代码块等扩展
                'codehilite',  # 代码高亮（虽然这里不用，但保持完整）
                'tables',  # 表格支持
                'fenced_code',  # 围栏代码块
            ],
            output_format='html5'
        )

        return html

    @staticmethod
    def _remove_code_block_markers(text: str) -> str:
        """
        移除代码块标记（如 ```html...``` 或 '''html...'''）

        Args:
            text: 原始文本

        Returns:
            str: 清理后的文本
        """
        # 处理 ```html ... ``` 格式
        if text.strip().startswith('```'):
            lines = text.split('\n')
            # 移除第一行的 ```html 或 ```
            if lines[0].strip().startswith('```'):
                lines = lines[1:]
            # 移除最后一行的 ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            text = '\n'.join(lines)

        # 处理 '''html ... ''' 格式
        if text.strip().startswith("'''"):
            lines = text.split('\n')
            # 移除第一行的 '''html 或 '''
            if lines[0].strip().startswith("'''"):
                lines = lines[1:]
            # 移除最后一行的 '''
            if lines and lines[-1].strip() == "'''":
                lines = lines[:-1]
            text = '\n'.join(lines)

        return text.strip()
