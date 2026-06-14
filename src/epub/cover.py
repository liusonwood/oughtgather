"""
封面生成器模块
负责生成 EPUB 封面图片
"""

import io
import platform
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import httpx

from src.config import TitleConfig
from src.utils.logger import get_logger


class CoverGenerator:
    """封面生成器"""

    # 封面尺寸（Kindle 推荐）
    WIDTH = 1600
    HEIGHT = 2560

    def __init__(self, title_config: TitleConfig):
        """
        初始化封面生成器

        Args:
            title_config: 标题配置
        """
        self.title_config = title_config
        self.logger = get_logger()

    def generate(self) -> Tuple[str, bytes]:
        """
        生成封面

        Returns:
            Tuple[str, bytes]: (文件名, 图片数据)
        """
        # 1. 获取背景图片
        background = self._get_background()

        # 2. 叠加文字
        cover = self._add_text_overlay(background)

        # 3. 转换为字节
        image_data = self._image_to_bytes(cover)

        return ("cover.jpg", image_data)

    def _get_background(self) -> Image.Image:
        """
        获取背景图片
        优先使用自定义图片，否则使用 Bing 壁纸

        Returns:
            Image.Image: 背景图片
        """
        # 1. 尝试使用自定义图片
        if self.title_config.img:
            self.logger.info(f"Using custom cover image: {self.title_config.img}")
            img = self._download_image(self.title_config.img)
            if img:
                return img

        # 2. 使用 Bing 壁纸
        self.logger.info("Fetching Bing daily wallpaper as cover")
        img = self._fetch_bing_wallpaper()
        if img:
            return img

        # 3. 创建纯色背景
        self.logger.warning("Failed to get cover image, using solid color background")
        return self._create_solid_background()

    def _fetch_bing_wallpaper(self) -> Optional[Image.Image]:
        """
        获取 Bing 每日壁纸

        Returns:
            Optional[Image.Image]: 壁纸图片
        """
        try:
            # Bing API
            api_url = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=zh-CN"

            with httpx.Client(timeout=30, follow_redirects=True) as client:
                # 获取 JSON 数据
                response = client.get(api_url)
                response.raise_for_status()
                data = response.json()

                # 提取图片 URL
                if "images" in data and len(data["images"]) > 0:
                    relative_path = data["images"][0]["url"]
                    full_url = f"https://www.bing.com{relative_path}"

                    # 下载图片
                    return self._download_image(full_url)

        except Exception as e:
            self.logger.error(f"Failed to fetch Bing wallpaper: {e}")

        return None

    def _download_image(self, url: str) -> Optional[Image.Image]:
        """
        下载图片

        Args:
            url: 图片 URL

        Returns:
            Optional[Image.Image]: 图片对象
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; OughtGather/1.0)"
            }

            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()

                # 打开图片
                img = Image.open(io.BytesIO(response.content))

                # 转换为 RGB
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # 调整尺寸
                img = img.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)

                return img

        except Exception as e:
            self.logger.error(f"Failed to download image from {url}: {e}")
            return None

    def _create_solid_background(self) -> Image.Image:
        """
        创建纯色背景

        Returns:
            Image.Image: 纯色背景图片
        """
        # 使用深蓝色背景
        img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(30, 60, 120))
        return img

    def _add_text_overlay(self, background: Image.Image) -> Image.Image:
        """
        在背景上叠加文字

        Args:
            background: 背景图片

        Returns:
            Image.Image: 带文字的封面
        """
        # 创建可编辑的对象
        draw = ImageDraw.Draw(background)

        # 获取标题文本
        title_text = self.title_config.get_display_text()

        # 加载支持中文的字体
        title_font = self._load_font(120, bold=True)
        subtitle_font = self._load_font(60, bold=False)

        # 计算文字位置（居中）
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]

        x = (self.WIDTH - title_width) // 2
        y = (self.HEIGHT - title_height) // 2

        # 绘制文字阴影
        shadow_offset = 4
        draw.text((x + shadow_offset, y + shadow_offset), title_text, font=title_font, fill=(0, 0, 0))

        # 绘制文字
        draw.text((x, y), title_text, font=title_font, fill=(255, 255, 255))

        return background

    def _get_cjk_font_candidates(self) -> List[str]:
        """
        获取支持中文的字体候选路径列表（按优先级排序）。
        按平台（macOS / Linux）提供不同候选。
        """
        system = platform.system()

        # 通用 Linux 候选（GitHub Actions / Ubuntu）
        linux_candidates = [
            # Noto Sans CJK（需安装 fonts-noto-cjk-extra 或 fonts-noto-cjk）
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            # WenQuanYi
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            # Droid
            "/usr/share/fonts/truetype/droid/DroidSansFallback.ttf",
        ]

        # macOS 候选
        macos_candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]

        # Windows 候选（本地开发）
        windows_candidates = [
            "C:/Windows/Fonts/msyh.ttc",   # 微软雅黑
            "C:/Windows/Fonts/msyhbd.ttc",  # 微软雅黑 Bold
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
        ]

        if system == "Darwin":
            return macos_candidates + linux_candidates
        elif system == "Windows":
            return windows_candidates + linux_candidates
        else:
            return linux_candidates

    def _load_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """
        加载支持中文的字体。依次尝试候选路径，首个可用即返回；
        全部失败则回退到 DejaVu（拉丁）→ Pillow 默认字体。
        """
        candidates = self._get_cjk_font_candidates()

        # bold 变体：在 Noto CJK 里 Bold/Regular 是不同文件，优先 Bold
        if not bold:
            candidates = [
                p.replace("-Bold.ttc", "-Regular.ttc").replace("-Bold.ttf", "-Regular.ttf")
                for p in candidates
            ]

        # 追加 DejaVu 作为非中文兜底（保持与原行为兼容）
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue

        # 最终回退
        self.logger.warning(
            "No CJK-capable font found; Chinese characters may render as boxes. "
            "Install fonts-noto-cjk-extra on Ubuntu or ensure a CJK font is available."
        )
        return ImageFont.load_default()

    def _image_to_bytes(self, img: Image.Image) -> bytes:
        """
        将图片转换为字节

        Args:
            img: PIL Image 对象

        Returns:
            bytes: 图片数据
        """
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=90, optimize=True)
        return buffer.getvalue()
