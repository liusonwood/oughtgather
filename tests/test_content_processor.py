"""
内容处理器测试
测试 exclude、chop、keep_link、delete 等规则的 HTML 处理行为
"""

import pytest
from bs4 import BeautifulSoup

from src.config import ContentSource
from src.fetchers.base import Article
from src.processors.content_processor import ContentProcessor


def _make_article(content: str, title: str = "Test") -> Article:
    """构造测试用 Article"""
    return Article(
        title=title,
        content=content,
        url="https://example.com/test",
    )


# =========================================================================
# exclude: start 规则测试
# =========================================================================

class TestExcludeStart:
    """exclude type=start 测试"""

    def test_delete_from_start(self, sample_html, source_with_exclude):
        """删除从开头到 '前言部分' 的内容"""
        processor = ContentProcessor(source_with_exclude)
        article = _make_article(sample_html)
        result = processor.process(article)
        # "前言部分" 及其之前内容应被删除
        assert "前言部分" not in result.content

    def test_start_keyword_not_found(self):
        """start 关键词不存在时 HTML 保持不变"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "start", "value": "不存在的关键词"}],
        )
        processor = ContentProcessor(source)
        html = "<p>内容A</p><p>内容B</p>"
        article = _make_article(html)
        result = processor.process(article)
        assert "内容A" in result.content
        assert "内容B" in result.content

    def test_start_with_html_tags(self):
        """start 关键词包含 HTML 标签的情况"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "start", "value": "阅读更多"}],
        )
        processor = ContentProcessor(source)
        html = '<p>摘要内容</p><a href="#">阅读更多</a><p>正文内容</p>'
        article = _make_article(html)
        result = processor.process(article)
        assert "阅读更多" not in result.content
        assert "正文内容" in result.content


# =========================================================================
# exclude: end 规则测试
# =========================================================================

class TestExcludeEnd:
    """exclude type=end 测试"""

    def test_delete_from_end(self, sample_html, source_with_exclude):
        """删除从 '— 完 —' 到结尾的内容"""
        processor = ContentProcessor(source_with_exclude)
        article = _make_article(sample_html)
        result = processor.process(article)
        assert "— 完 —" not in result.content
        assert "这段应该被删除" not in result.content

    def test_end_keyword_not_found(self):
        """end 关键词不存在时 HTML 保持不变"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "end", "value": "不存在的关键词"}],
        )
        processor = ContentProcessor(source)
        html = "<p>内容A</p><p>内容B</p>"
        article = _make_article(html)
        result = processor.process(article)
        assert "内容A" in result.content
        assert "内容B" in result.content

    def test_end_uses_rfind(self):
        """end 应使用 rfind（匹配最后一次出现）"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "end", "value": "分割线"}],
        )
        processor = ContentProcessor(source)
        html = "<p>前文</p><p>分割线</p><p>中间</p><p>分割线</p><p>结尾</p>"
        article = _make_article(html)
        result = processor.process(article)
        # "分割线" 最后一次出现之后的内容应被删除
        assert "结尾" not in result.content
        assert "前文" in result.content


# =========================================================================
# exclude: exact 规则测试
# =========================================================================

class TestExcludeExact:
    """exclude type=exact 测试"""

    def test_delete_exact_match(self, sample_html, source_with_exclude):
        """精确匹配删除 HTML 片段"""
        processor = ContentProcessor(source_with_exclude)
        article = _make_article(sample_html)
        result = processor.process(article)
        assert '<span class="ad">广告</span>' not in result.content

    def test_exact_multiple_occurrences(self):
        """exact 删除所有出现"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "exact", "value": "[AD]"}],
        )
        processor = ContentProcessor(source)
        html = "<p>[AD]正文[AD]内容[AD]</p>"
        article = _make_article(html)
        result = processor.process(article)
        assert "[AD]" not in result.content

    def test_exact_with_html_tags(self):
        """exact 可以匹配包含 HTML 标签的字符串"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "exact", "value": '<a href="https://spam.com">推广</a>'}],
        )
        processor = ContentProcessor(source)
        html = '<p>正文</p><a href="https://spam.com">推广</a><p>结尾</p>'
        article = _make_article(html)
        result = processor.process(article)
        assert "推广" not in result.content
        assert "正文" in result.content

    def test_exact_no_match(self):
        """exact 关键词不存在时不修改"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "exact", "value": "不存在的内容"}],
        )
        processor = ContentProcessor(source)
        html = "<p>原始内容</p>"
        article = _make_article(html)
        result = processor.process(article)
        assert "原始内容" in result.content


# =========================================================================
# exclude 组合规则测试
# =========================================================================

class TestExcludeCombined:
    """多条 exclude 规则组合测试"""

    def test_start_then_end(self, sample_html, source_with_exclude):
        """start 和 end 组合使用"""
        processor = ContentProcessor(source_with_exclude)
        article = _make_article(sample_html)
        result = processor.process(article)
        # 两个关键词之间的内容应保留
        assert "正文的第一段" in result.content
        assert "正文的第二段" in result.content
        # 边界之外的应被删除
        assert "前言部分" not in result.content
        assert "这段应该被删除" not in result.content

    def test_invalid_exclude_rule_type_logged(self):
        """无效 exclude type 不崩溃"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "unknown_type", "value": "test"}],
        )
        processor = ContentProcessor(source)
        html = "<p>内容</p>"
        article = _make_article(html)
        result = processor.process(article)
        # 不应该崩溃，内容应保留
        assert "内容" in result.content

    def test_exclude_empty_value_skipped(self):
        """exclude 中 value 为空的规则应被跳过"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            exclude=[{"type": "exact", "value": ""}],
        )
        processor = ContentProcessor(source)
        html = "<p>内容</p>"
        article = _make_article(html)
        result = processor.process(article)
        assert "内容" in result.content


# =========================================================================
# chop 规则测试
# =========================================================================

class TestChop:
    """chop 内容裁剪测试"""

    def test_chop_start_only(self, source_with_chop):
        """chop /[0:100] 只保留前 100 个字符"""
        processor = ContentProcessor(source_with_chop)
        html = "<p>" + "A" * 200 + "</p>"
        article = _make_article(html)
        result = processor.process(article)
        text = BeautifulSoup(result.content, "lxml").get_text()
        assert len(text) == 100

    def test_chop_from_offset(self):
        """chop /[50:] 删除前 50 个字符"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            chop="/[50:]",
        )
        processor = ContentProcessor(source)
        html = "<p>" + "A" * 100 + "</p>"
        article = _make_article(html)
        result = processor.process(article)
        text = BeautifulSoup(result.content, "lxml").get_text()
        assert len(text) == 50
        assert text == "A" * 50

    def test_chop_negative_end(self):
        """chop /[:-200] 删除最后 200 个字符"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            chop="/[:-200]",
        )
        processor = ContentProcessor(source)
        html = "<p>" + "B" * 500 + "</p>"
        article = _make_article(html)
        result = processor.process(article)
        text = BeautifulSoup(result.content, "lxml").get_text()
        assert len(text) == 300
        assert text == "B" * 300

    def test_chop_negative_start(self):
        """chop /[-50:] 保留最后 50 个字符"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            chop="/[-50:]",
        )
        processor = ContentProcessor(source)
        html = "<p>" + "C" * 200 + "</p>"
        article = _make_article(html)
        result = processor.process(article)
        text = BeautifulSoup(result.content, "lxml").get_text()
        assert len(text) == 50
        assert text == "C" * 50

    def test_chop_negative_start_and_end(self):
        """chop /[-150:-50] 保留倒数第150到倒数第50之间的字符"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            chop="/[-150:-50]",
        )
        processor = ContentProcessor(source)
        html = "<p>" + "D" * 300 + "</p>"
        article = _make_article(html)
        result = processor.process(article)
        text = BeautifulSoup(result.content, "lxml").get_text()
        assert len(text) == 100
        assert text == "D" * 100

    def test_chop_negative_end_exceeds_length(self):
        """chop /[:-1000] 当内容不足1000字符时返回空"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            chop="/[:-1000]",
        )
        processor = ContentProcessor(source)
        html = "<p>" + "E" * 200 + "</p>"
        article = _make_article(html)
        result = processor.process(article)
        text = BeautifulSoup(result.content, "lxml").get_text()
        assert text == ""

    def test_chop_empty(self):
        """chop 为空时不裁剪"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            chop=None,
        )
        processor = ContentProcessor(source)
        html = "<p>Hello</p>"
        article = _make_article(html)
        result = processor.process(article)
        assert "Hello" in result.content


# =========================================================================
# keep_link 规则测试
# =========================================================================

class TestKeepLink:
    """keep_link 规则测试"""

    def test_keep_link_yes(self):
        """keep_link=Y 保留 <a> 标签"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            keep_link="Y",
        )
        processor = ContentProcessor(source)
        html = '<p>请 <a href="https://example.com">点击这里</a> 查看详情</p>'
        article = _make_article(html)
        result = processor.process(article)
        assert "<a" in result.content
        assert "href" in result.content

    def test_keep_link_no(self):
        """keep_link=N 移除 <a> 标签，保留文字"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            keep_link="N",
        )
        processor = ContentProcessor(source)
        html = '<p>请 <a href="https://example.com">点击这里</a> 查看详情</p>'
        article = _make_article(html)
        result = processor.process(article)
        assert "<a" not in result.content
        assert "点击这里" in result.content
        assert "查看详情" in result.content


# =========================================================================
# _should_delete（delete 规则）测试
# =========================================================================

class TestDelete:
    """delete 关键词过滤测试"""

    def test_delete_matching_title(self, source_with_delete):
        """标题包含关键词时 _should_delete 返回 True"""
        from src.fetchers.base import BaseFetcher
        # 用 ContentSource 直接调用 _should_delete 逻辑
        keywords = source_with_delete.delete.split(",")
        assert any(k.strip() in "这是一条广告文章" for k in keywords)

    def test_delete_no_match(self, source_with_delete):
        """标题不含关键词时 _should_delete 返回 False"""
        keywords = source_with_delete.delete.split(",")
        assert not any(k.strip() in "正常文章标题" for k in keywords)

    def test_delete_empty(self):
        """delete 为空时不过滤任何文章"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        assert source.delete is None

    def test_delete_multiple_keywords(self):
        """多个 delete 关键词任意匹配"""
        source = ContentSource(
            type="rss", src="https://example.com/rss",
            delete="广告,推广,赞助",
        )
        keywords = [k.strip() for k in source.delete.split(",")]
        # 分别测试每个关键词
        assert any(k in "这是一个广告" for k in keywords)
        assert any(k in "推广内容" for k in keywords)
        assert any(k in "赞助文章" for k in keywords)
        assert not any(k in "普通文章" for k in keywords)


# =========================================================================
# HTML 清洗测试
# =========================================================================

class TestCleanHtml:
    """HTML 清洗测试"""

    def test_removes_script(self):
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<p>内容</p><script>alert('xss')</script>"
        article = _make_article(html)
        result = processor.process(article)
        assert "<script" not in result.content
        assert "alert" not in result.content

    def test_removes_style(self):
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<style>body{color:red}</style><p>内容</p>"
        article = _make_article(html)
        result = processor.process(article)
        assert "<style" not in result.content

    def test_removes_iframe(self):
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = '<p>内容</p><iframe src="https://evil.com"></iframe>'
        article = _make_article(html)
        result = processor.process(article)
        assert "<iframe" not in result.content

    def test_removes_dangerous_attrs(self):
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = '<p onclick="alert(1)" class="test" data-x="1">内容</p>'
        article = _make_article(html)
        result = processor.process(article)
        assert "onclick" not in result.content
        assert "data-x" not in result.content
        # class 是允许保留的属性
        assert "class" in result.content


# =========================================================================
# EPUB 验证错误修复测试
# =========================================================================

class TestEpubValidationFixes:
    """EPUB 验证错误修复测试"""

    def test_row_to_tr_conversion(self):
        """<row> 应转换为 <tr>"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<table><row><td>单元格</td></row></table>"
        article = _make_article(html)
        result = processor.process(article)
        assert "<tr>" in result.content
        assert "<row>" not in result.content

    def test_font_to_span_with_color(self):
        """<font color='red'> 应转换为 <span style='color:red'>"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<font color='red'>红色文字</font>"
        article = _make_article(html)
        result = processor.process(article)
        assert "<span" in result.content
        assert "color:red" in result.content
        assert "<font" not in result.content

    def test_font_to_span_with_size(self):
        """<font size='5'> 应转换为带 font-size 的 <span>"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<font size='5'>大号文字</font>"
        article = _make_article(html)
        result = processor.process(article)
        assert "<span" in result.content
        assert "font-size:18px" in result.content  # size 5 → 18px
        assert "<font" not in result.content

    def test_font_to_span_with_multiple_attrs(self):
        """<font color='blue' face='Arial'> 应转换多个属性"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<font color='blue' face='Arial'>蓝色Arial</font>"
        article = _make_article(html)
        result = processor.process(article)
        assert "<span" in result.content
        assert "color:blue" in result.content
        assert "font-family:Arial" in result.content
        assert "<font" not in result.content

    def test_svg_removal(self):
        """SVG 元素应被移除"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<svg><circle cx='50' cy='50' r='40'/></svg>正文"
        article = _make_article(html)
        result = processor.process(article)
        assert "<svg" not in result.content
        assert "正文" in result.content

    def test_video_removal(self):
        """视频元素应被移除"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<video src='https://example.com/video.mp4'></video>正文"
        article = _make_article(html)
        result = processor.process(article)
        assert "<video" not in result.content
        assert "正文" in result.content

    def test_audio_removal(self):
        """音频元素应被移除"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<audio src='https://example.com/audio.mp3'></audio>正文"
        article = _make_article(html)
        result = processor.process(article)
        assert "<audio" not in result.content
        assert "正文" in result.content

    def test_nested_section_in_p_fixed(self):
        """<p> 内的 <section> 应移到外面"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<p>文本<section>块内容</section>更多文本</p>"
        article = _make_article(html)
        result = processor.process(article)
        # section 不应在 p 内
        soup = BeautifulSoup(result.content, 'lxml')
        for p in soup.find_all('p'):
            assert not p.find('section')

    def test_nested_div_in_p_fixed(self):
        """<p> 内的 <div> 应移到外面"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<p>文本<div>块内容</div>更多文本</p>"
        article = _make_article(html)
        result = processor.process(article)
        soup = BeautifulSoup(result.content, 'lxml')
        for p in soup.find_all('p'):
            assert not p.find('div')

    def test_nested_p_in_p_fixed(self):
        """嵌套 <p> 应被拆分"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<p>外层<p>内层</p>继续</p>"
        article = _make_article(html)
        result = processor.process(article)
        # 不应有嵌套的 p
        soup = BeautifulSoup(result.content, 'lxml')
        for p in soup.find_all('p'):
            assert not p.find('p')

    def test_nested_header_in_p_fixed(self):
        """<p> 内的 <h1> 应移到外面"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<p>文本<h1>标题</h1>更多文本</p>"
        article = _make_article(html)
        result = processor.process(article)
        soup = BeautifulSoup(result.content, 'lxml')
        for p in soup.find_all('p'):
            assert not p.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

    def test_complex_nested_structure(self):
        """复杂嵌套结构应被修复"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<p>文本1<section><p>文本2</p></section>文本3</p>"
        article = _make_article(html)
        result = processor.process(article)
        # 检查结构是否有效
        soup = BeautifulSoup(result.content, 'lxml')
        assert soup.find('section') is not None
        # 所有 p 内不应有嵌套的块级元素
        for p in soup.find_all('p'):
            assert not p.find(['section', 'div', 'p', 'article', 'aside'])

    def test_deep_nested_structure_fixed(self):
        """深度嵌套应被多次遍历修复"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<p>外<p>中<p>内</p></p></p>"
        article = _make_article(html)
        result = processor.process(article)
        soup = BeautifulSoup(result.content, 'lxml')
        # 确保没有嵌套的 p
        for p in soup.find_all('p'):
            assert not p.find('p')

    def test_text_preserved_after_fix(self):
        """修复嵌套结构后文本内容应保留"""
        source = ContentSource(type="rss", src="https://example.com/rss")
        processor = ContentProcessor(source)
        html = "<p>段落1<section>块内容</section>段落2</p>"
        article = _make_article(html)
        result = processor.process(article)
        assert "段落1" in result.content
        assert "块内容" in result.content
        assert "段落2" in result.content
