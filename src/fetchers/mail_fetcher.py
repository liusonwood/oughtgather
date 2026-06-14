"""
邮件抓取器模块
通过 testmail.app API 抓取订阅邮件
"""

from typing import List, Optional
from urllib.parse import quote
from bs4 import BeautifulSoup

from src.config import ContentSource, get_testmail_config
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.utils.logger import get_logger


class MailFetcher(BaseFetcher):
    """邮件抓取器"""

    def __init__(self, source: ContentSource):
        """
        初始化邮件抓取器

        Args:
            source: 内容源配置
        """
        super().__init__(source)
        self.config = get_testmail_config()

        if not self.config:
            self.logger.warning(
                "TESTMAIL_APP_API_KEY not configured. Mail fetching will be skipped."
            )

    def fetch(self) -> FetchResult:
        """
        执行邮件抓取

        Returns:
            FetchResult: 抓取结果
        """
        result = FetchResult(source=self.source, articles=[])

        # 检查配置
        if not self.config:
            result.success = False
            result.error = "TESTMAIL_APP_API_KEY not configured"
            return result

        try:
            # 调用 testmail.app API
            # API 文档: https://testmail.app/docs/#using-cypress-json-api
            # namespace 使用 source.src 属性，需要 URL 编码
            namespace_encoded = quote(self.source.src.replace(' ', ''), safe='')
            api_url = (
                f"https://api.testmail.app/api/json"
                f"?apikey={self.config['api_key']}"
                f"&namespace={namespace_encoded}"
            )

            # 添加可选的查询参数
            api_url += self._build_query_params()

            response = self._make_request(api_url)
            data = response.json()

            # 检查 API 响应
            if data.get("result") != "success":
                error_msg = data.get("message", "Unknown API error")
                result.success = False
                result.error = f"API error: {error_msg}"
                return result

            # 解析邮件列表
            emails = data.get("emails", [])
            self.logger.info(f"Found {len(emails)} emails in namespace '{self.source.src}'")

            for email in emails:
                try:
                    article = self._parse_email(email)
                    if article and not self._should_delete(article.title):
                        result.articles.append(article)
                except Exception as e:
                    self.logger.error(f"Failed to parse email: {e}")
                    result.add_error(f"Failed to parse email: {e}")

            return result

        except Exception as e:
            self.logger.error(f"Mail fetch failed: {e}")
            result.success = False
            result.error = str(e)
            return result

    def _parse_email(self, email: dict) -> Article:
        """
        解析单个邮件

        Args:
            email: 邮件数据（JSON 格式）

        Returns:
            Article: 文章对象
        """
        # 提取邮件信息
        subject = email.get("subject", "No Subject")
        from_addr = email.get("from", "")
        timestamp = email.get("timestamp", "")

        # 提取 HTML 内容
        html_content = email.get("html", "")

        # 如果没有 HTML，使用纯文本
        if not html_content:
            text_content = email.get("text", "")
            html_content = f"<p>{text_content}</p>"

        # 提取图片
        images = self._extract_images(html_content)

        # 应用内容处理规则
        html_content = self._apply_content_rules(html_content)

        return Article(
            title=subject,
            content=html_content,
            url=f"mailto:{from_addr}",
            author=from_addr,
            published_date=timestamp,
            images=images,
            metadata={
                "to": email.get("to", ""),
                "attachments": email.get("attachments", [])
            }
        )

    def _extract_images(self, html: str) -> List[str]:
        """
        从 HTML 中提取图片 URL

        Args:
            html: HTML 内容

        Returns:
            List[str]: 图片 URL 列表
        """
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')
        images = []

        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                images.append(src)

        return images

    def _apply_content_rules(self, html: str) -> str:
        """
        应用内容处理规则（chop、exclude）

        Args:
            html: HTML 内容

        Returns:
            str: 处理后的 HTML
        """
        if not html:
            return html

        # TODO: 实现 chop 和 exclude 规则
        # 这些规则将在 content_processor 中统一处理

        return html

    def _build_query_params(self) -> str:
        """
        构建可选的查询参数

        支持通过 source.metadata 配置以下参数：
        - tag: 按标签过滤
        - tag_prefix: 按标签前缀过滤
        - timestamp_from: 起始时间戳（毫秒）
        - timestamp_to: 结束时间戳（毫秒）
        - limit: 返回邮件数量限制（默认 10，最大 100）
        - offset: 偏移量（默认 0，最大 9899）

        Returns:
            str: 查询参数字符串
        """
        params = []

        # 从 metadata 中读取可选参数
        metadata = self.source.metadata if hasattr(self.source, 'metadata') else {}

        if not metadata:
            # 默认只返回最新的 10 封邮件
            params.append("limit=10")
            return "&" + "&".join(params) if params else ""

        # 标签过滤
        if "tag" in metadata:
            params.append(f"tag={quote(str(metadata['tag']), safe='')}")

        if "tag_prefix" in metadata:
            params.append(f"tag_prefix={quote(str(metadata['tag_prefix']), safe='')}")

        # 时间范围过滤
        if "timestamp_from" in metadata:
            params.append(f"timestamp_from={metadata['timestamp_from']}")

        if "timestamp_to" in metadata:
            params.append(f"timestamp_to={metadata['timestamp_to']}")

        # 数量和偏移
        limit = min(metadata.get("limit", 10), 100)  # 最大 100
        params.append(f"limit={limit}")

        if "offset" in metadata:
            params.append(f"offset={metadata['offset']}")

        return "&" + "&".join(params) if params else ""
