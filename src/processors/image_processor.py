"""
图片处理器模块
负责图片下载、压缩和嵌入
"""

import io
import os
from typing import List, Tuple, Optional
from urllib.parse import urlparse
import httpx
from PIL import Image

from src.utils.logger import get_logger


class ImageProcessor:
    """图片处理器"""

    MAX_SIZE_KB = 250  # 单张图片最大大小（KB）
    MAX_WIDTH = 640  # 最大宽度（EPUB 阅读器屏幕通常 600px 宽）
    MAX_HEIGHT = 960  # 最大高度
    JPEG_QUALITY = 75  # JPEG 质量
    MIN_WIDTH = 120  # 最小宽度（过滤头像、图标、表情等装饰性小图）
    MIN_HEIGHT = 120  # 最小高度

    def __init__(self):
        """初始化图片处理器"""
        self.logger = get_logger()
        self.processed_images: List[Tuple[str, bytes]] = []  # (filename, data)

    def download_and_process(self, url: str, base_url: Optional[str] = None) -> Optional[Tuple[str, bytes]]:
        """
        下载并处理图片

        Args:
            url: 图片 URL
            base_url: 基础 URL（用于处理相对路径和作为 Referer）

        Returns:
            Tuple[str, bytes]: (文件名, 图片数据)
        """
        try:
            # 处理相对 URL
            full_url = self._resolve_url(url, base_url)

            # 下载图片
            self.logger.debug(f"Downloading image: {full_url}")
            # 将 base_url 传给下载器作为 Referer
            response = self._download_image(full_url, referer=base_url)

            if not response:
                return None

            # 处理图片
            result = self._process_image(response, url)
            if not result:
                return None

            filename, image_data = result
            self.processed_images.append((filename, image_data))
            size_kb = len(image_data) / 1024
            self.logger.info(f"Successfully processed image: {filename} ({size_kb:.1f}KB) from {url}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to process image {url}: {e}")
            return None

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

    def _download_image(self, url: str, referer: Optional[str] = None) -> Optional[bytes]:
        """
        下载图片

        Args:
            url: 图片 URL
            referer: 引用页 URL（用于绕过防盗链）

        Returns:
            Optional[bytes]: 图片数据
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            if referer:
                headers["Referer"] = referer

            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response.content

        except Exception as e:
            self.logger.error(f"Failed to download image from {url}: {e}")
            return None

    def _process_image(self, image_data: bytes, original_url: str) -> Optional[Tuple[str, bytes]]:
        """
        处理图片（压缩、转换格式）

        Args:
            image_data: 原始图片数据
            original_url: 原始 URL

        Returns:
            Tuple[str, bytes]: (文件名, 处理后的图片数据)
        """
        try:
            # 打开图片
            img = Image.open(io.BytesIO(image_data))

            # 跳过过小的图片（头像、图标、表情等装饰性小图）
            width, height = img.size
            if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                self.logger.debug(f"Skipping small image ({width}x{height}): {original_url}")
                return None

            # 转换为 RGB（如果是 RGBA 或其他模式）
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # 调整尺寸
            img = self._resize_image(img)

            # 压缩并转换为 JPEG
            compressed_data = self._compress_image(img)

            # 生成文件名
            filename = self._generate_filename(original_url)

            return (filename, compressed_data)

        except Exception as e:
            self.logger.error(f"Failed to process image: {e}")
            return None

    def _resize_image(self, img: Image.Image) -> Image.Image:
        """
        调整图片尺寸

        Args:
            img: PIL Image 对象

        Returns:
            Image.Image: 调整后的图片
        """
        width, height = img.size

        # 如果尺寸在限制内，不调整
        if width <= self.MAX_WIDTH and height <= self.MAX_HEIGHT:
            return img

        # 计算缩放比例
        ratio = min(self.MAX_WIDTH / width, self.MAX_HEIGHT / height)
        new_size = (int(width * ratio), int(height * ratio))

        # 调整尺寸（使用高质量重采样）
        return img.resize(new_size, Image.Resampling.LANCZOS)

    def _compress_image(self, img: Image.Image) -> bytes:
        """
        压缩图片

        Args:
            img: PIL Image 对象

        Returns:
            bytes: 压缩后的图片数据
        """
        # 逐步降低质量，直到满足大小要求
        quality = self.JPEG_QUALITY

        while quality >= 20:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            data = buffer.getvalue()

            # 检查大小
            size_kb = len(data) / 1024
            if size_kb <= self.MAX_SIZE_KB:
                return data

            # 降低质量
            quality -= 5

        # 如果仍然太大，进一步降低尺寸
        self.logger.warning("Image still too large after quality reduction, resizing further")
        width, height = img.size
        new_size = (int(width * 0.7), int(height * 0.7))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=60, optimize=True)
        return buffer.getvalue()

    def _generate_filename(self, url: str) -> str:
        """
        生成文件名

        Args:
            url: 原始 URL

        Returns:
            str: 文件名
        """
        # 使用 URL 的哈希作为文件名
        import hashlib
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
        return f"image_{url_hash}.jpg"

    def get_total_size(self) -> int:
        """
        获取所有已处理图片的总大小

        Returns:
            int: 总大小（字节）
        """
        return sum(len(data) for _, data in self.processed_images)

    def get_total_size_mb(self) -> float:
        """
        获取所有已处理图片的总大小（MB）

        Returns:
            float: 总大小（MB）
        """
        return self.get_total_size() / (1024 * 1024)

    def clear(self):
        """清除已处理的图片"""
        self.processed_images.clear()
