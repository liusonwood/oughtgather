"""
图片处理器测试
测试 ImageProcessor 的图片下载、压缩、尺寸调整和 URL 解析
"""

import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from src.processors.image_processor import ImageProcessor


def _make_image_bytes(
    width: int = 100,
    height: int = 100,
    mode: str = "RGB",
    color=(255, 0, 0),
    fmt: str = "JPEG",
) -> bytes:
    """生成测试用图片字节数据"""
    img = Image.new(mode, (width, height), color)
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    return buffer.getvalue()


# =========================================================================
# URL 解析测试
# =========================================================================

class TestResolveUrl:
    """ImageProcessor._resolve_url 测试"""

    def setup_method(self):
        self.processor = ImageProcessor()

    def test_absolute_https_url(self):
        url = "https://example.com/image.jpg"
        assert self.processor._resolve_url(url) == url

    def test_absolute_http_url(self):
        url = "http://example.com/image.jpg"
        assert self.processor._resolve_url(url) == url

    def test_protocol_relative_url(self):
        url = "//cdn.example.com/image.jpg"
        assert self.processor._resolve_url(url) == "https://cdn.example.com/image.jpg"

    def test_relative_url_with_base(self):
        url = "/images/photo.jpg"
        base = "https://example.com/article/page"
        assert self.processor._resolve_url(url, base) == "https://example.com/images/photo.jpg"

    def test_relative_path_with_base(self):
        url = "photo.jpg"
        base = "https://example.com/articles/"
        assert self.processor._resolve_url(url, base) == "https://example.com/articles/photo.jpg"

    def test_relative_url_no_base(self):
        url = "image.jpg"
        # 无 base_url 时原样返回
        assert self.processor._resolve_url(url) == "image.jpg"


# =========================================================================
# 图片尺寸调整测试
# =========================================================================

class TestResizeImage:
    """ImageProcessor._resize_image 测试"""

    def setup_method(self):
        self.processor = ImageProcessor()

    def test_small_image_unchanged(self):
        """小于限制的图片不调整"""
        img = Image.new("RGB", (400, 600))
        result = self.processor._resize_image(img)
        assert result.size == (400, 600)

    def test_width_exceeds_limit(self):
        """宽度超限等比缩放"""
        img = Image.new("RGB", (1280, 800))
        result = self.processor._resize_image(img)
        assert result.size[0] == 640  # MAX_WIDTH
        # 高度按比例：800 * (640/1280) = 400
        assert result.size[1] == 400

    def test_height_exceeds_limit(self):
        """高度超限等比缩放"""
        img = Image.new("RGB", (400, 1920))
        result = self.processor._resize_image(img)
        assert result.size[1] == 960  # MAX_HEIGHT
        # 宽度按比例：400 * (960/1920) = 200
        assert result.size[0] == 200

    def test_both_exceed_limit(self):
        """宽高都超限按较大比例缩放"""
        img = Image.new("RGB", (1280, 1920))
        result = self.processor._resize_image(img)
        # 宽度比例：640/1280 = 0.5
        # 高度比例：960/1920 = 0.5
        assert result.size == (640, 960)

    def test_exact_limit_unchanged(self):
        """恰好等于限制尺寸不调整"""
        img = Image.new("RGB", (640, 960))
        result = self.processor._resize_image(img)
        assert result.size == (640, 960)


# =========================================================================
# 过小图片过滤测试
# =========================================================================

class TestSmallImageFilter:
    """装饰性小图（头像、图标、表情等）应被过滤，不参与 EPUB 生成"""

    def setup_method(self):
        self.processor = ImageProcessor()

    @patch.object(ImageProcessor, "_download_image")
    def test_tiny_icon_skipped(self, mock_download):
        """极小图标（如 32x32 表情）被跳过"""
        mock_download.return_value = _make_image_bytes(32, 32)
        result = self.processor.download_and_process("https://example.com/icon.png")
        assert result is None

    @patch.object(ImageProcessor, "_download_image")
    def test_avatar_skipped(self, mock_download):
        """头像类小图（如 64x64）被跳过"""
        mock_download.return_value = _make_image_bytes(64, 64)
        result = self.processor.download_and_process("https://example.com/avatar.jpg")
        assert result is None

    @patch.object(ImageProcessor, "_download_image")
    def test_narrow_separator_skipped(self, mock_download):
        """窄长条分隔图（宽度过小）被跳过"""
        mock_download.return_value = _make_image_bytes(50, 400)
        result = self.processor.download_and_process("https://example.com/separator.png")
        assert result is None

    @patch.object(ImageProcessor, "_download_image")
    def test_short_banner_skipped(self, mock_download):
        """矮横幅（高度过小）被跳过"""
        mock_download.return_value = _make_image_bytes(400, 50)
        result = self.processor.download_and_process("https://example.com/banner.png")
        assert result is None

    @patch.object(ImageProcessor, "_download_image")
    def test_exact_min_size_kept(self, mock_download):
        """恰好等于最小尺寸的图片保留（边界不丢弃）"""
        mock_download.return_value = _make_image_bytes(120, 120)
        result = self.processor.download_and_process("https://example.com/min.jpg")
        assert result is not None

    @patch.object(ImageProcessor, "_download_image")
    def test_normal_image_kept(self, mock_download):
        """正常正文配图（大于最小尺寸）保留"""
        mock_download.return_value = _make_image_bytes(300, 200)
        result = self.processor.download_and_process("https://example.com/content.jpg")
        assert result is not None

    @patch.object(ImageProcessor, "_download_image")
    def test_skipped_image_not_tracked(self, mock_download):
        """被跳过的小图不进入 processed_images 列表"""
        mock_download.return_value = _make_image_bytes(48, 48)
        self.processor.download_and_process("https://example.com/tiny.png")
        assert len(self.processor.processed_images) == 0


# =========================================================================
# 图片压缩测试
# =========================================================================

class TestCompressImage:
    """ImageProcessor._compress_image 测试"""

    def setup_method(self):
        self.processor = ImageProcessor()

    def test_small_image_compressed(self):
        """小图片压缩后小于 MAX_SIZE_KB"""
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        data = self.processor._compress_image(img)
        assert len(data) / 1024 <= 250

    def test_returns_jpeg(self):
        """压缩后是 JPEG 格式"""
        img = Image.new("RGB", (200, 200))
        data = self.processor._compress_image(img)
        # JPEG 文件头是 FF D8 FF
        assert data[:3] == b"\xff\xd8\xff"

    def test_large_image_forced_smaller(self):
        """大图片压缩后满足大小限制"""
        # 创建一个复杂的图片（噪声），更难压缩
        import random
        img = Image.new("RGB", (640, 960))
        pixels = img.load()
        for x in range(640):
            for y in range(960):
                pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        data = self.processor._compress_image(img)
        # 即使质量降到最低也不满足，会进一步缩小尺寸
        # 最终应仍是一个有效的 JPEG
        assert data[:3] == b"\xff\xd8\xff"


# =========================================================================
# 文件名生成测试
# =========================================================================

class TestGenerateFilename:
    """ImageProcessor._generate_filename 测试"""

    def setup_method(self):
        self.processor = ImageProcessor()

    def test_filename_format(self):
        """文件名格式为 image_{hash}.jpg"""
        filename = self.processor._generate_filename("https://example.com/image.jpg")
        assert filename.startswith("image_")
        assert filename.endswith(".jpg")

    def test_same_url_same_filename(self):
        """相同 URL 生成相同文件名"""
        f1 = self.processor._generate_filename("https://example.com/a.jpg")
        f2 = self.processor._generate_filename("https://example.com/a.jpg")
        assert f1 == f2

    def test_different_url_different_filename(self):
        """不同 URL 生成不同文件名"""
        f1 = self.processor._generate_filename("https://example.com/a.jpg")
        f2 = self.processor._generate_filename("https://example.com/b.jpg")
        assert f1 != f2

    def test_hash_length(self):
        """哈希部分为 12 位"""
        filename = self.processor._generate_filename("https://example.com/img.jpg")
        # image_ (6) + hash (12) + .jpg (4) = 22
        assert len(filename) == 22


# =========================================================================
# 图片处理流程测试（mock 下载）
# =========================================================================

class TestDownloadAndProcess:
    """ImageProcessor.download_and_process 集成测试"""

    @patch.object(ImageProcessor, "_download_image")
    def test_successful_processing(self, mock_download):
        """完整处理流程：下载 → 调整 → 压缩"""
        mock_download.return_value = _make_image_bytes(200, 300)

        processor = ImageProcessor()
        result = processor.download_and_process("https://example.com/img.jpg")

        assert result is not None
        filename, data = result
        assert filename.startswith("image_")
        assert filename.endswith(".jpg")
        assert len(data) > 0

    @patch.object(ImageProcessor, "_download_image")
    def test_rgba_converted_to_rgb(self, mock_download):
        """RGBA 图片转换为 RGB"""
        mock_download.return_value = _make_image_bytes(200, 200, mode="RGBA", fmt="PNG")

        processor = ImageProcessor()
        result = processor.download_and_process("https://example.com/img.png")

        assert result is not None
        _, data = result
        # 应输出 JPEG（非 PNG）
        assert data[:3] == b"\xff\xd8\xff"

    @patch.object(ImageProcessor, "_download_image")
    def test_download_failure_returns_none(self, mock_download):
        """下载失败返回 None"""
        mock_download.return_value = None

        processor = ImageProcessor()
        result = processor.download_and_process("https://example.com/img.jpg")

        assert result is None

    @patch.object(ImageProcessor, "_download_image")
    def test_processed_images_tracked(self, mock_download):
        """处理过的图片记录到 processed_images 列表"""
        mock_download.return_value = _make_image_bytes(200, 200)

        processor = ImageProcessor()
        processor.download_and_process("https://example.com/a.jpg")
        processor.download_and_process("https://example.com/b.jpg")

        assert len(processor.processed_images) == 2

    @patch.object(ImageProcessor, "_download_image")
    def test_get_total_size(self, mock_download):
        """get_total_size 返回所有图片的总字节数"""
        mock_download.return_value = _make_image_bytes(200, 200)

        processor = ImageProcessor()
        processor.download_and_process("https://example.com/a.jpg")
        processor.download_and_process("https://example.com/b.jpg")

        total = processor.get_total_size()
        assert total > 0
        assert total == sum(len(d) for _, d in processor.processed_images)

    @patch.object(ImageProcessor, "_download_image")
    def test_get_total_size_mb(self, mock_download):
        """get_total_size_mb 返回 MB 单位"""
        mock_download.return_value = _make_image_bytes(200, 200)

        processor = ImageProcessor()
        processor.download_and_process("https://example.com/a.jpg")

        mb = processor.get_total_size_mb()
        assert mb > 0
        assert mb == processor.get_total_size() / (1024 * 1024)

    def test_clear(self):
        """clear 清空已处理图片"""
        processor = ImageProcessor()
        processor.processed_images = [("a.jpg", b"data1"), ("b.jpg", b"data2")]
        processor.clear()
        assert len(processor.processed_images) == 0
