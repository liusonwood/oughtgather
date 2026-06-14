"""
基础抓取器模块
定义统一的抓取接口和基础功能
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import httpx

from src.config import ContentSource
from src.utils.logger import get_logger


@dataclass
class Article:
    """文章数据结构"""
    title: str
    content: str  # HTML 格式
    url: str
    author: Optional[str] = None
    published_date: Optional[str] = None
    images: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "author": self.author,
            "published_date": self.published_date,
            "images": self.images,
            "metadata": self.metadata
        }


@dataclass
class FetchResult:
    """抓取结果数据结构"""
    source: ContentSource
    articles: List[Article]
    success: bool = True
    error: Optional[str] = None
    error_count: int = 0
    source_title: Optional[str] = None  # 数据源的显示名称（如 RSS feed 标题）

    def add_error(self, error_msg: str):
        """添加错误信息"""
        if self.error:
            self.error += f"; {error_msg}"
        else:
            self.error = error_msg
        self.error_count += 1


class BaseFetcher(ABC):
    """基础抓取器抽象类"""

    def __init__(self, source: ContentSource, max_retries: int = 3):
        """
        初始化抓取器

        Args:
            source: 内容源配置
            max_retries: 最大重试次数
        """
        self.source = source
        self.max_retries = max_retries
        self.logger = get_logger()

    @abstractmethod
    def fetch(self) -> FetchResult:
        """
        执行抓取

        Returns:
            FetchResult: 抓取结果
        """
        pass

    def fetch_with_retry(self) -> FetchResult:
        """
        带重试机制的抓取
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                self.logger.info(
                    f"Fetching {self.source.type} (attempt {attempt + 1}/{self.max_retries}): "
                    f"{self.source.src}"
                )

                result = self.fetch()

                if result.success:
                    self.logger.info(
                        f"Successfully fetched {len(result.articles)} articles from {self.source.src}"
                    )
                    return result
                else:
                    last_error = result.error
                    self.logger.warning(
                        f"Attempt {attempt + 1} failed: {last_error}"
                    )

            except Exception as e:
                last_error = str(e)
                self.logger.error(
                    f"Attempt {attempt + 1} failed with exception: {e}"
                )

            # 如果不是最后一次尝试，等待后重试
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避：1s, 2s, 4s
                self.logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        # 所有重试都失败
        self.logger.error(
            f"All {self.max_retries} attempts failed for {self.source.src}"
        )

        return FetchResult(
            source=self.source,
            articles=[],
            success=False,
            error=f"Failed after {self.max_retries} attempts: {last_error}"
        )

    def _make_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30
    ) -> httpx.Response:
        """
        发送 HTTP 请求

        Args:
            url: 请求 URL
            method: HTTP 方法
            headers: 请求头
            timeout: 超时时间（秒）

        Returns:
            httpx.Response: 响应对象
        """
        default_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; OughtGather/1.0)"
        }

        if headers:
            default_headers.update(headers)

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.request(method, url, headers=default_headers)
            response.raise_for_status()
            response.read()  # 确保在客户端关闭前读取响应体
            return response

    def _should_delete(self, title: str) -> bool:
        """
        检查是否应该删除该文章（基于 delete 配置）

        Args:
            title: 文章标题

        Returns:
            bool: 是否应该删除
        """
        if not self.source.delete:
            return False

        # 检查标题是否包含删除关键词
        keywords = self.source.delete.split(',')
        return any(keyword.strip() in title for keyword in keywords)
