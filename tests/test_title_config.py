"""
TitleConfig 模块的专门测试
测试 get_display_text() 和 get_plain_text() 方法
"""

from datetime import datetime
import pytest
from src.config import TitleConfig


class TestTitleConfig:
    """TitleConfig 数据类测试"""

    def test_simple_time_placeholder(self):
        """测试独立的 {time} 占位符"""
        config = TitleConfig(text="每日新闻 {time}")
        result = config.get_display_text()
        today = datetime.now().strftime("%Y-%m-%d")
        assert result == f"每日新闻 {today}"

    def test_nested_time_placeholder(self):
        """测试嵌套的 {前缀 {time}} 占位符"""
        config = TitleConfig(text="{Daily News {time}}")
        result = config.get_display_text()
        today = datetime.now().strftime("%Y-%m-%d")
        assert result == f"Daily News {today}"

    def test_no_time_placeholder(self):
        """测试不含占位符的纯文本"""
        config = TitleConfig(text="固定书名")
        assert config.get_display_text() == "固定书名"

    def test_multiple_time_placeholders(self):
        """测试多个 {time} 占位符"""
        config = TitleConfig(text="{time} - 新闻 - {time}")
        result = config.get_display_text()
        today = datetime.now().strftime("%Y-%m-%d")
        assert result == f"{today} - 新闻 - {today}"

    def test_img_optional(self):
        """测试 img 可选参数"""
        config = TitleConfig(text="Test")
        assert config.img is None

        config_with_img = TitleConfig(text="Test", img="https://example.com/img.jpg")
        assert config_with_img.img == "https://example.com/img.jpg"

    def test_get_plain_text_removes_br_tags(self):
        """测试 get_plain_text() 移除 </br> 标签"""
        config = TitleConfig(text="每日新闻</br>{time}")
        plain_text = config.get_plain_text()
        today = datetime.now().strftime("%Y-%m-%d")
        # 纯文本应该用空格替换</br>标签
        assert plain_text == f"每日新闻 {today}"
        # 原始显示文本应该保留换行标签
        assert config.get_display_text() == f"每日新闻</br>{today}"

    def test_get_plain_text_removes_br_tags_without_space(self):
        """测试 get_plain_text() 移除 <br> 标签（没有斜杠）"""
        config = TitleConfig(text="Daily News<br>{time}")
        plain_text = config.get_plain_text()
        today = datetime.now().strftime("%Y-%m-%d")
        assert plain_text == f"Daily News {today}"

    def test_get_plain_text_compresses_multiple_spaces(self):
        """测试 get_plain_text() 压缩多个连续空格"""
        config = TitleConfig(text="测试  多个    空格</br>{time}")
        plain_text = config.get_plain_text()
        today = datetime.now().strftime("%Y-%m-%d")
        assert plain_text == f"测试 多个 空格 {today}"

    def test_get_plain_text_handles_time_placeholder(self):
        """测试 get_plain_text() 正确处理时间占位符"""
        config = TitleConfig(text="{Daily News {time}}")
        plain_text = config.get_plain_text()
        today = datetime.now().strftime("%Y-%m-%d")
        assert plain_text == f"Daily News {today}"

    def test_get_plain_text_with_complex_formatting(self):
        """测试 get_plain_text() 处理复杂格式化的文本"""
        config = TitleConfig(text="AI Trends</br>{Daily Summary {time}}")
        plain_text = config.get_plain_text()
        today = datetime.now().strftime("%Y-%m-%d")
        assert plain_text == f"AI Trends Daily Summary {today}"
        # 验证显示文本保留换行标签
        assert config.get_display_text() == f"AI Trends</br>Daily Summary {today}"
