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


_registry = {}


def get_fetcher_class(type_name: str) -> Optional[Any]:
    """
    根据类型名称获取注册的抓取器类

    Args:
        type_name: 抓取器类型名称

    Returns:
        Type[BaseFetcher] | None: 对应的抓取器类，如果未找到则返回 None
    """
    return _registry.get(type_name)


class BaseFetcher(ABC):
    """基础抓取器抽象类"""

    type_name: str = ""
    src_placeholder: str = ""
    config_schema: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "type_name") and cls.type_name:
            _registry[cls.type_name] = cls


    def __init__(self, source: ContentSource, global_limit: int = 15, max_retries: int = 3):
        """
        初始化抓取器

        Args:
            source: 内容源配置
            global_limit: 全局抓取数量限制
            max_retries: 最大重试次数
        """
        self.source = source
        self.global_limit = global_limit
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
                # 自定义重试间隔：第1次失败后1s，第2次失败后10s
                retry_intervals = [1, 10]
                wait_time = retry_intervals[attempt] if attempt < len(retry_intervals) else 10
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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        if headers:
            default_headers.update(headers)

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.request(method, url, headers=default_headers)
            response.raise_for_status()
            response.read()  # 确保在客户端关闭前读取响应体
            return response

    def _resolve_url(self, url: str, base_url: Optional[str] = None) -> str:
        """
        解析 URL（处理相对路径）

        Args:
            url: 图片 URL
            base_url: 基础 URL

        Returns:
            str: 完整的 URL
        """
        from urllib.parse import urljoin
        if not base_url:
            if url.startswith('//'):
                return 'https:' + url
            return url
        return urljoin(base_url, url)

    def _extract_images(self, html: str, base_url: Optional[str] = None) -> List[str]:
        """
        从 HTML 中提取图片 URL

        Args:
            html: HTML 内容
            base_url: 基础 URL（用于解析相对路径）

        Returns:
            List[str]: 图片 URL 列表
        """
        if not html:
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        images = []
        
        # 排除关键词
        exclude_keywords = ['avatar', 'logo', 'icon', 'button', 'loading', 'spacer', 'ad_']

        for img in soup.find_all('img'):
            # 1. 尝试多个候选属性
            src = None
            
            # 检查 srcset
            srcset = img.get('data-srcset') or img.get('srcset')
            if srcset:
                # 解析 srcset: "url1 300w, url2 600w"
                candidates = []
                for part in srcset.split(','):
                    parts = part.strip().split()
                    if parts:
                        candidates.append(parts[0])
                if candidates:
                    src = candidates[-1] # 假设最后一个是最大的
            
            # 检查懒加载属性
            if not src:
                for attr in ['data-src', 'data-original', 'data-actualsrc', 'data-lazy-src', 'file', 'zoom-target', 'original']:
                    val = img.get(attr)
                    if val and not any(ext in val.lower() for ext in ['.gif', '.svg']):
                        src = val
                        break
            
            # 最后用 src
            if not src:
                src = img.get('src')
                
            if not src:
                continue
                
            # 2. 基础过滤
            if src.startswith('data:image'):
                continue
            
            # 排除明显的占位图/图标
            if any(kw in src.lower() for kw in exclude_keywords):
                # 除非它是唯一的图片或非常大，否则跳过
                pass 
                
            # 3. 解析为绝对路径
            full_url = self._resolve_url(src, base_url or self.source.src)
            if full_url not in images:
                images.append(full_url)

        return images

    @staticmethod
    def _restore_img_tags(html: str) -> str:
        """
        将 trafilatura 输出的 <graphic> 标签还原为 <img> 标签。

        trafilatura 在 output_format="html" 模式下会把 <img> 转换为
        <graphic>（EPUB/HTML5 标准元素），但下游的图片处理流程只识别 <img>。
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        for graphic in soup.find_all('graphic'):
            graphic.name = 'img'
        body = soup.body if soup.body else soup
        return body.decode_contents()

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
