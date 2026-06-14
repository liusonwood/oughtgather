"""
集成测试 - 测试完整流程，真正生成 EPUB 文件
运行：python -m pytest tests/test_integration.py -v -s
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.config import Config, TitleConfig, ContentSource, _parse_config
from src.fetchers.base import Article, FetchResult
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.web_fetcher import WebFetcher
from src.processors.content_processor import ContentProcessor
from src.dedup.tracker import DedupTracker
from src.epub.generator import EPUBGenerator


def _make_feedparser_dict(d):
    """模拟 feedparser 的 FeedParserDict"""
    class FeedParserDict(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)
    return FeedParserDict(d)


# =========================================================================
# 完整流程集成测试
# =========================================================================

class TestFullPipeline:
    """完整流程集成测试：从抓取到生成 EPUB"""

    def test_rss_to_epub(self, tmp_path):
        """测试 RSS 抓取 → 内容处理 → EPUB 生成"""
        # 1. 准备配置
        config_data = {
            "title": {
                "text": "集成测试 {time}",
                "img": ""
            },
            "body": [
                {
                    "type": "rss",
                    "src": "https://example.com/rss",
                    "title": "测试 RSS 源",
                    "priority": 10,
                    "keep_link": "Y",
                }
            ]
        }
        config = _parse_config(config_data)

        # 2. Mock RSS 数据
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.feed = {"title": "测试 Feed"}
        mock_feed.entries = [
            _make_feedparser_dict({
                "title": "文章一：Python 教程",
                "link": "https://example.com/1",
                "author": "作者 A",
                "published": "2024-01-01",
                "content": [_make_feedparser_dict({
                    "value": "<h2>Python 入门</h2><p>这是一篇关于 Python 的教程。</p><p>Python 是一门优秀的编程语言。</p>"
                })],
                "tags": [{"term": "python"}, {"term": "programming"}],
            }),
            _make_feedparser_dict({
                "title": "文章二：Web 开发",
                "link": "https://example.com/2",
                "author": "作者 B",
                "published": "2024-01-02",
                "content": [_make_feedparser_dict({
                    "value": "<h2>Web 开发基础</h2><p>本文介绍 Web 开发的基本概念。</p><p>包括 HTML、CSS、JavaScript。</p>"
                })],
                "tags": [{"term": "web"}],
            }),
        ]

        with patch("src.fetchers.rss_fetcher.feedparser.parse", return_value=mock_feed):
            # 3. 抓取 RSS
            source = config.body[0]
            fetcher = RSSFetcher(source)
            fetch_result = fetcher.fetch()

            assert fetch_result.success is True
            assert len(fetch_result.articles) == 2
            print(f"✓ 成功抓取 {len(fetch_result.articles)} 篇文章")

            # 4. 处理内容
            processor = ContentProcessor(source)
            processed_articles = []
            for article in fetch_result.articles:
                original_content = article.content
                processed = processor.process(article)
                processed_articles.append(processed)
                print(f"  文章 '{article.title}': 内容长度 {len(original_content)} -> {len(processed.content)}")

            fetch_result.articles = processed_articles
            assert len(fetch_result.articles) == 2
            assert "Python" in fetch_result.articles[0].content
            print(f"✓ 内容处理完成")

            # 5. 生成 EPUB（需要 FetchResult 列表，不是 Article 列表）
            generator = EPUBGenerator(config)
            epub_path = generator.generate([fetch_result])  # 返回实际路径

            # 6. 验证 EPUB 文件
            assert os.path.exists(epub_path), f"EPUB 文件应该存在: {epub_path}"
            assert os.path.getsize(epub_path) > 0, "EPUB 文件不应该为空"
            print(f"✓ EPUB 文件生成成功：{epub_path}")
            print(f"  文件大小：{os.path.getsize(epub_path)} 字节")

            # 7. 验证 EPUB 内容（可选：解压检查）
            import zipfile
            assert zipfile.is_zipfile(epub_path), "EPUB 应该是 ZIP 格式"

            with zipfile.ZipFile(epub_path, 'r') as zf:
                file_list = zf.namelist()
                assert 'mimetype' in file_list, "EPUB 应包含 mimetype 文件"
                # 目录文件可能在根目录或 EPUB/ 子目录
                has_toc = any('toc.ncx' in f or 'nav.xhtml' in f for f in file_list)
                assert has_toc, f"EPUB 应包含目录文件，实际文件：{file_list}"
                print(f"  EPUB 包含 {len(file_list)} 个文件")

            # 清理生成的文件
            os.remove(epub_path)

    def test_multiple_sources_to_epub(self, tmp_path):
        """测试多个数据源 → EPUB 生成"""
        # 1. 准备配置（多个数据源）
        config_data = {
            "title": {
                "text": "多源测试 {time}",
                "img": ""
            },
            "body": [
                {
                    "type": "rss",
                    "src": "https://example.com/rss1",
                    "title": "RSS 源 1",
                    "priority": 15,
                },
                {
                    "type": "rss",
                    "src": "https://example.com/rss2",
                    "title": "RSS 源 2",
                    "priority": 10,
                },
            ]
        }
        config = _parse_config(config_data)

        # 2. Mock 两个 RSS 源
        def mock_parse_factory(url):
            mock_feed = MagicMock()
            mock_feed.bozo = False

            if "rss1" in url:
                mock_feed.feed = {"title": "Feed 1"}
                mock_feed.entries = [
                    _make_feedparser_dict({
                        "title": "来自源 1 的文章",
                        "link": "https://example.com/1",
                        "content": [_make_feedparser_dict({
                            "value": "<p>这是第一个源的文章内容。</p>"
                        })],
                        "tags": [],
                    }),
                ]
            else:
                mock_feed.feed = {"title": "Feed 2"}
                mock_feed.entries = [
                    _make_feedparser_dict({
                        "title": "来自源 2 的文章",
                        "link": "https://example.com/2",
                        "content": [_make_feedparser_dict({
                            "value": "<p>这是第二个源的文章内容。</p>"
                        })],
                        "tags": [],
                    }),
                ]
            return mock_feed

        all_results = []

        with patch("src.fetchers.rss_fetcher.feedparser.parse", side_effect=mock_parse_factory):
            # 3. 抓取所有源
            for source in config.body:
                fetcher = RSSFetcher(source)
                result = fetcher.fetch()
                assert result.success is True

                processor = ContentProcessor(source)
                processed_articles = []
                for article in result.articles:
                    processed = processor.process(article)
                    processed_articles.append(processed)
                result.articles = processed_articles

                all_results.append(result)

            assert len(all_results) == 2
            total_articles = sum(len(r.articles) for r in all_results)
            assert total_articles == 2
            print(f"✓ 从 {len(config.body)} 个源抓取了 {total_articles} 篇文章")

            # 4. 生成 EPUB（传入 FetchResult 列表）
            generator = EPUBGenerator(config)
            epub_path = generator.generate(all_results)  # 返回实际路径

            # 5. 验证
            assert os.path.exists(epub_path)
            assert os.path.getsize(epub_path) > 0
            print(f"✓ EPUB 生成成功：{epub_path}")
            print(f"  文件大小：{os.path.getsize(epub_path)} 字节")

            # 清理
            os.remove(epub_path)


class TestDedupIntegration:
    """去重功能集成测试"""

    def test_dedup_across_runs(self, tmp_path):
        """测试跨多次运行的去重"""
        dedup_file = tmp_path / "fetched_urls.txt"

        # 第一次运行
        tracker1 = DedupTracker(str(dedup_file))
        tracker1.mark_as_fetched("https://example.com/1", "文章 1")
        tracker1.mark_as_fetched("https://example.com/2", "文章 2")
        tracker1.save()

        assert dedup_file.exists()
        print(f"✓ 第一次运行：标记了 2 篇文章")

        # 第二次运行（应该能加载之前的记录）
        tracker2 = DedupTracker(str(dedup_file))
        assert tracker2.is_fetched("https://example.com/1", "文章 1") is True
        assert tracker2.is_fetched("https://example.com/2", "文章 2") is True
        assert tracker2.is_fetched("https://example.com/3", "文章 3") is False

        tracker2.mark_as_fetched("https://example.com/3", "文章 3")
        tracker2.save()
        print(f"✓ 第二次运行：新增 1 篇文章，跳过 2 篇已抓取")

        # 第三次运行（应该能加载所有记录）
        tracker3 = DedupTracker(str(dedup_file))
        stats = tracker3.get_stats()
        assert stats["total_fetched"] == 3
        assert stats["new_fetched"] == 0  # 没有新标记
        print(f"✓ 第三次运行：总共 {stats['total_fetched']} 篇已抓取")


class TestContentProcessingIntegration:
    """内容处理集成测试"""

    def test_complex_content_rules(self):
        """测试复杂的内容处理规则组合"""
        source = ContentSource(
            type="rss",
            src="https://example.com/rss",
            title="测试",
            keep_link="N",
            exclude=[
                {"type": "start", "value": "阅读更多"},
                {"type": "end", "value": "— 完 —"},
                {"type": "exact", "value": '<span class="ad">广告</span>'},
            ],
        )

        html = """
        <div>
            <a href="#">阅读更多</a>
            <p>正文的第一段，包含重要内容。</p>
            <p>正文的第二段，<a href="https://example.com">链接</a>应该被移除。</p>
            <span class="ad">广告</span>
            <p>正文的第三段。</p>
            <p>— 完 —</p>
            <p>这段应该被删除。</p>
        </div>
        """

        article = Article(
            title="测试文章",
            content=html,
            url="https://example.com/test",
        )

        processor = ContentProcessor(source)
        result = processor.process(article)

        # 验证规则生效
        assert "阅读更多" not in result.content
        assert "这段应该被删除" not in result.content
        assert "广告" not in result.content
        assert "<a" not in result.content  # 链接被移除
        assert "正文的第一段" in result.content
        assert "链接" in result.content  # 链接文字保留
        print("✓ 复杂内容规则处理正确")


class TestEpubStructure:
    """EPUB 文件结构测试"""

    def test_epub_contains_required_files(self, tmp_path):
        """验证 EPUB 包含必需的文件"""
        config_data = {
            "title": {"text": "结构测试", "img": ""},
            "body": [
                {
                    "type": "rss",
                    "src": "https://example.com/rss",
                    "title": "测试源",
                    "priority": 10,
                }
            ]
        }
        config = _parse_config(config_data)

        # 创建一个 FetchResult
        source = config.body[0]
        articles = [
            Article(
                title="测试文章",
                content="<p>内容</p>",
                url="https://example.com",
            ),
        ]
        fetch_result = FetchResult(source=source, articles=articles)

        generator = EPUBGenerator(config)
        epub_path_str = generator.generate([fetch_result])  # 传入 FetchResult 列表，返回实际路径

        import zipfile
        with zipfile.ZipFile(epub_path_str, 'r') as zf:
            files = zf.namelist()

            # 检查必需文件
            assert 'mimetype' in files, "缺少 mimetype"
            assert 'META-INF/container.xml' in files, "缺少 container.xml"

            # 检查内容文件（可能在 EPUB/ 或 OEBPS/ 目录）
            content_files = [f for f in files if 'EPUB/' in f or 'OEBPS/' in f]
            assert len(content_files) > 0, f"应该包含内容文件，实际文件：{files}"

            print(f"✓ EPUB 结构正确，包含 {len(files)} 个文件：")
            for f in sorted(files):
                print(f"    - {f}")

        # 清理
        os.remove(epub_path_str)
