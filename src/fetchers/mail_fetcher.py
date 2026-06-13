"""
邮件抓取器模块
通过 testmail.app API 抓取订阅邮件
"""

from typing import List
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
            api_url = f"https://api.testmail.app/api/json?apikey={self.config['api_key']}&namespace=default&livequery"

            response = self._make_request(api_url)
            data = response.json()

            # 解析邮件列表
            emails = data.get("emails", [])
            self.logger.info(f"Found {len(emails)} emails")

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
