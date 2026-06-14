# Ought Gather 测试指南

本文档教你如何运行、编写和维护本项目的测试。

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

需要额外安装测试依赖：
- `pytest` — 测试框架
- `pytest-mock` — mock 辅助工具

### 运行测试

```bash
# 运行所有测试
python -m pytest tests/

# 显示详细信息
python -m pytest tests/ -v

# 只运行某个文件
python -m pytest tests/test_config.py -v

# 只运行某个测试类
python -m pytest tests/test_config.py::TestTitleConfig -v

# 只运行某个测试方法
python -m pytest tests/test_config.py::TestTitleConfig::test_simple_time_placeholder -v

# 遇到失败时立即停止
python -m pytest tests/ -x

# 显示 print 输出（默认被捕获）
python -m pytest tests/ -s
```

### 测试文件结构

```
tests/
├── __init__.py
├── conftest.py              # 共享 fixtures
├── test_config.py           # 配置加载和验证
├── test_helpers.py          # 工具函数
├── test_content_processor.py # 内容处理规则
├── test_dedup_tracker.py    # 去重追踪
├── test_fetchers.py         # 各种抓取器（mock HTTP）
└── test_image_processor.py  # 图片处理
```

## 核心概念

### 1. pytest 基础

每个测试是一个函数，名字以 `test_` 开头：

```python
def test_something():
    assert 1 + 1 == 2
```

用类组织相关测试：

```python
class TestMyFeature:
    def test_case_a(self):
        assert True

    def test_case_b(self):
        assert True
```

### 2. Fixtures（测试夹具）

Fixtures 是 pytest 的核心，用于提供测试所需的依赖。在 `conftest.py` 中定义：

```python
import pytest
from src.config import ContentSource

@pytest.fixture
def rss_source():
    """提供一个 RSS 类型的 ContentSource"""
    return ContentSource(
        type="rss",
        src="https://example.com/rss",
        title="测试源",
        priority=10,
    )
```

在测试中使用（按名字注入）：

```python
def test_rss_fetch(rss_source):  # pytest 自动注入 fixture
    assert rss_source.type == "rss"
    assert rss_source.src == "https://example.com/rss"
```

### 3. Mock（模拟外部依赖）

本项目涉及大量外部依赖（HTTP 请求、API 调用、文件系统），必须用 mock 隔离。

#### 3.1 模拟 HTTP 请求

**场景**：测试 RSSFetcher，但不想真的请求网络。

```python
from unittest.mock import patch, MagicMock

@patch("src.fetchers.rss_fetcher.feedparser.parse")
def test_rss_fetch(mock_parse, rss_source):
    # 1. 设置 mock 返回值
    mock_parse.return_value = MagicMock(
        bozo=False,
        entries=[{"title": "文章1", "content": [{"value": "<p>内容</p>"}]}],
        feed={"title": "Test Feed"},
    )

    # 2. 执行被测代码
    from src.fetchers.rss_fetcher import RSSFetcher
    fetcher = RSSFetcher(rss_source)
    result = fetcher.fetch()

    # 3. 验证结果
    assert result.success is True
    assert len(result.articles) == 1
```

**关键点**：
- `@patch("模块路径.函数名")` 告诉 pytest 在测试期间替换该函数
- `mock_parse.return_value` 设置被替换函数的返回值
- mock 对象自动支持任意属性访问和方法调用

#### 3.2 模拟 feedparser 的特殊行为

feedparser 返回的对象**同时支持 dict 和属性访问**：

```python
entry["title"]  # ✓
entry.title     # ✓
```

普通 dict 只支持第一种。测试时需要模拟这种行为：

```python
def _make_feedparser_dict(d):
    """模拟 feedparser 的 FeedParserDict"""
    class FeedParserDict(dict):
        def __getattr__(self, name):
            try:
                return self[name]
            except KeyError:
                raise AttributeError(name)
    return FeedParserDict(d)

# 使用
entry = _make_feedparser_dict({
    "title": "文章",
    "content": [_make_feedparser_dict({"value": "<p>内容</p>"})],
})

assert entry["title"] == "文章"  # ✓
assert entry.title == "文章"     # ✓
```

#### 3.3 模拟 httpx.Client

**场景**：测试 MailFetcher，需要 mock HTTP POST 请求。

```python
@patch.object(MailFetcher, "_make_request")
def test_mail_fetch(mock_request, mail_source):
    # 1. 构造 mock 响应
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": "success",
        "emails": [{"subject": "测试邮件", "html": "<p>内容</p>"}]
    }
    mock_request.return_value = mock_response

    # 2. 执行
    fetcher = MailFetcher(mail_source)
    result = fetcher.fetch()

    # 3. 验证
    assert result.success is True
    assert len(result.articles) == 1
```

**注意**：如果源码在函数内部局部导入模块（如 `import httpx`），需要 patch 全局模块：

```python
# ❌ 错误：源码在函数内 import httpx，不是模块属性
@patch("src.fetchers.trending_fetcher.httpx.Client")

# ✅ 正确：直接 patch httpx 模块
@patch("httpx.Client")
```

#### 3.4 模拟环境变量

很多配置通过环境变量读取，测试时需要临时设置：

```python
@patch.dict("os.environ", {"TESTMAIL_APP_API_KEY": "test_key_123"})
def test_with_api_key(mail_source):
    # 测试期间环境变量已设置
    from src.config import get_testmail_config
    config = get_testmail_config()
    assert config["api_key"] == "test_key_123"

@patch.dict("os.environ", {}, clear=True)
def test_without_api_key(mail_source, monkeypatch):
    # 清空所有环境变量
    monkeypatch.delenv("TESTMAIL_APP_API_KEY", raising=False)
    # 现在 API key 不存在
```

#### 3.5 模拟文件系统

测试文件读写操作时，用 `tmp_path` 或 `tmp_dir` fixture：

```python
def test_save_and_reload(tmp_dir):
    """使用临时目录，测试后自动清理"""
    data_file = os.path.join(tmp_dir, "fetched_urls.txt")

    # 第一次：写入
    tracker1 = DedupTracker(data_file)
    tracker1.mark_as_fetched("https://example.com", "标题")
    tracker1.save()

    # 第二次：读取
    tracker2 = DedupTracker(data_file)
    assert tracker2.is_fetched("https://example.com", "标题") is True
```

`tmp_dir` fixture 在 `conftest.py` 中定义，使用 `tempfile.mkdtemp()` 创建临时目录。

### 4. 测试组织原则

#### 4.1 每个测试只测一件事

```python
# ❌ 不好：一个测试验证太多东西
def test_rss_fetcher():
    result = fetcher.fetch()
    assert result.success
    assert len(result.articles) == 2
    assert result.articles[0].title == "A"
    assert result.articles[1].title == "B"
    assert result.source_title == "Feed"

# ✅ 好：拆分成多个独立测试
def test_rss_fetch_success():
    result = fetcher.fetch()
    assert result.success is True

def test_rss_fetch_article_count():
    result = fetcher.fetch()
    assert len(result.articles) == 2

def test_rss_fetch_article_titles():
    result = fetcher.fetch()
    assert result.articles[0].title == "A"
    assert result.articles[1].title == "B"
```

#### 4.2 测试命名要清晰

```python
# ❌ 不好
def test_1():
    ...

def test_config():
    ...

# ✅ 好
def test_load_config_from_file():
    ...

def test_load_config_from_env_takes_precedence():
    ...

def test_invalid_type_raises_value_error():
    ...
```

#### 4.3 使用 Arrange-Act-Assert 模式

```python
def test_chop_truncates_content():
    # Arrange（准备）
    source = ContentSource(type="rss", src="test", chop="/[0:100]")
    processor = ContentProcessor(source)
    html = "<p>" + "A" * 200 + "</p>"
    article = Article(title="Test", content=html, url="test")

    # Act（执行）
    result = processor.process(article)

    # Assert（断言）
    text = BeautifulSoup(result.content, "lxml").get_text()
    assert len(text) == 100
```

## 常见陷阱

### 1. Mock 对象的行为不符合预期

**问题**：MagicMock 默认返回另一个 MagicMock，不是你想要的值。

```python
# ❌ 错误
mock_response = MagicMock()
data = mock_response.json()  # 返回 MagicMock，不是 dict

# ✅ 正确
mock_response = MagicMock()
mock_response.json.return_value = {"result": "success"}  # 显式设置返回值
data = mock_response.json()  # 现在返回 dict
```

### 2. 忘记设置 mock 的上下文管理器行为

**问题**：`with httpx.Client() as client:` 需要 mock 支持 `__enter__` 和 `__exit__`。

```python
# ❌ 错误
@patch("httpx.Client")
def test_api(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    # with 语句会失败，因为 mock_client 没有正确实现上下文管理器

# ✅ 正确
@patch("httpx.Client")
def test_api(mock_client_cls):
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = mock_client
```

### 3. 环境变量污染

**问题**：测试修改了环境变量，影响其他测试。

```python
# ❌ 错误
def test_with_env():
    os.environ["API_KEY"] = "test"  # 永久修改，影响其他测试

# ✅ 正确
@patch.dict("os.environ", {"API_KEY": "test"})
def test_with_env():
    # 测试结束后自动恢复
    pass
```

### 4. 测试依赖外部网络

**问题**：测试真的发起 HTTP 请求，慢且不稳定。

```python
# ❌ 错误
def test_fetch():
    fetcher = RSSFetcher(source)
    result = fetcher.fetch()  # 真的请求网络！

# ✅ 正确
@patch("src.fetchers.rss_fetcher.feedparser.parse")
def test_fetch(mock_parse):
    mock_parse.return_value = ...  # 模拟返回
    fetcher = RSSFetcher(source)
    result = fetcher.fetch()  # 不会发起网络请求
```

## 如何添加新测试

### 步骤 1：确定测试目标

问自己：
- 测试哪个模块/函数？
- 有哪些输入情况？
- 期望的输出是什么？
- 有哪些边界情况？

### 步骤 2：选择测试文件

按模块对应关系：
- `src/config.py` → `tests/test_config.py`
- `src/processors/content_processor.py` → `tests/test_content_processor.py`
- `src/fetchers/*.py` → `tests/test_fetchers.py`
- ...

### 步骤 3：编写测试

```python
# tests/test_my_feature.py

import pytest
from src.my_module import my_function

class TestMyFeature:
    """我的功能测试"""

    def test_normal_case(self):
        """测试正常情况"""
        result = my_function("input")
        assert result == "expected"

    def test_edge_case_empty_input(self):
        """测试边界情况：空输入"""
        result = my_function("")
        assert result is None

    def test_error_case(self):
        """测试错误情况"""
        with pytest.raises(ValueError, match="error message"):
            my_function("invalid")
```

### 步骤 4：运行测试

```bash
python -m pytest tests/test_my_feature.py -v
```

### 步骤 5：检查覆盖率（可选）

```bash
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## 调试测试

### 1. 查看详细输出

```bash
python -m pytest tests/ -v -s  # -s 显示 print 输出
```

### 2. 在测试中打断点

```python
def test_something():
    result = my_function()
    breakpoint()  # Python 3.7+ 内置调试器
    assert result == "expected"
```

运行 pytest 时会进入交互式调试：
```bash
python -m pytest tests/test_file.py -s
```

### 3. 只显示失败测试的详细信息

```bash
python -m pytest tests/ --tb=short  # 简短回溯
python -m pytest tests/ --tb=long   # 完整回溯
python -m pytest tests/ --tb=line   # 只显示失败行
```

## 最佳实践

1. **测试要快**：避免真的网络请求、文件 I/O，用 mock 隔离
2. **测试要独立**：每个测试不依赖其他测试的执行顺序或状态
3. **测试要可重复**：相同输入总是得到相同输出
4. **测试要清晰**：命名说明意图，注释解释为什么
5. **测试要全面**：覆盖正常情况、边界情况、错误情况
6. **不要测试实现细节**：测试行为，不测试内部实现

## 参考资源

- [pytest 官方文档](https://docs.pytest.org/)
- [unittest.mock 文档](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-mock 文档](https://pytest-mock.readthedocs.io/)
