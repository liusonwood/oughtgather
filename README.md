# Ought Gather

自动化信息聚合工具，将邮件订阅、RSS、网页内容整合为 EPUB 电子书，并推送到 Kindle 设备。

## 功能特性

- **多数据源支持**：邮件订阅、RSS、网页、AI 热点分析
- **智能去重**：自动记录已抓取内容，避免重复
- **EPUB 生成**：自动生成带封面、目录的电子书
- **Kindle 推送**：通过邮件自动发送到 Kindle
- **定时运行**：GitHub Actions 每天自动执行
- **内容过滤**：支持关键词过滤、内容裁剪等规则

## 快速开始

### 1. Fork 本仓库

点击 GitHub 页面右上角的 "Fork" 按钮。

### 2. 配置 Secrets

在仓库的 **Settings → Secrets and variables → Actions** 中添加以下 Secrets：

注意：仓库 Settings → Actions → General 里 "Workflow permissions" 需要改成 "Read and write permissions"

#### 必需配置（邮件发送）

| Secret 名称 | 说明 | 示例 |
|------------|------|------|
| `SMTP_HOST` | SMTP 服务器地址 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 端口 | `587` 或 `465` |
| `SMTP_USERNAME` | 发送邮箱账号 | `your-email@gmail.com` |
| `SMTP_PASSWORD` | 邮箱授权码（非登录密码） | `xxxx xxxx xxxx xxxx` |
| `KINDLE_EMAIL` | Kindle 接收邮箱 | `your-name@kindle.com` |

**注意**：需要在亚马逊后台将发送邮箱添加到 Kindle 的"已认可的发件人电子邮箱列表"中。

#### 可选配置

| Secret 名称 | 说明 |
|------------|------|
| `CONFIG_JSON` | 完整的 config.json 内容（推荐，可保护隐私） |
| `TESTMAIL_APP_API_KEY` | TestMail.app API Key（邮件订阅抓取） |
| `OPENROUTER_API_KEY` | OpenRouter API Key（AI 热点分析） |
| `OPENROUTER_API_ENDPOINT` | 自定义 LLM API 端点 |
| `OPENROUTER_MODEL` | 全局默认模型 ID。优先级低于 config.json 中每个源的 `model` 字段。示例：`anthropic/claude-3.5-sonnet`、`openai/gpt-4o` |

### 3. 配置数据源

创建 `config.json` 文件（或通过 `CONFIG_JSON` Secret 配置）：

```json
{
  "title": {
    "text": "{Daily News {time}}",
    "img": ""
  },
  "body": [
    {
      "type": "rss",
      "title": "科技新闻",
      "src": "https://example.com/rss",
      "priority": 10,
      "keep_link": "Y",
      "full_text": "Y"
    }
  ]
}
```

详细配置说明见下文。

### 4. 运行

- **自动运行**：每天 UTC 00:00（北京时间 08:00）自动执行
- **手动运行**：在 GitHub Actions 页面手动触发 "Daily Gather" 工作流

## 配置详解

### 标题配置 (title)

```json
{
  "title": {
    "text": "{Daily News {time}}",
    "img": "https://example.com/cover.jpg"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | ✓ | 书名，显示在封面中央。支持两种占位符写法：<br>`{time}` → `2026-06-14`<br>`{前缀 {time}}` → `前缀 2026-06-14`（外层花括号仅用于嵌套，输出时被展开） |
| `img` | string | | 封面背景图片 URL。<br>留空 `""` 或未配置 → 自动使用 Bing 每日壁纸<br>Bing 也失败时 → 深蓝色纯色背景<br>有效 URL → 下载并缩放到 1600×2560（Kindle 推荐尺寸） |

### 内容源配置 (body)

`body` 是一个数组，每个元素定义一个数据源。EPUB 中的章节按 `priority` 降序排列（数值越大越靠前），相同优先级保持配置中的原始顺序（稳定排序）。

#### 通用属性（所有 type 共用）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✓ | 数据源类型：`rss` / `web` / `mail` / `trending` |
| `src` | string | ✓ | 数据源地址，含义因 `type` 而异（详见下方各类型说明） |
| `title` | string | | 自定义章节标题，显示在 EPUB 目录中。各类型的默认行为：<br>`rss` → 使用 RSS feed 自身的标题<br>`web` → 优先从网页 `<title>`/`<h1>`/`og:title` 提取<br>`mail` → 无默认，建议手动指定<br>`trending` → `"热点分析: {src}"` |
| `priority` | int | | 优先级，数字越大在 EPUB 中越靠前。默认 `0`。相同值保持配置顺序 |
| `keep_link` | string | | 是否保留文章中的超链接。`"Y"`（默认）保留 `<a>` 标签，Kindle 上可点击跳转；`"N"` 移除所有 `<a>` 标签，只保留链接文字 |
| `chop` | string | | 内容裁剪，使用 Python 切片语法 `"/[start:end]"`，作用于**纯文本**（先提取纯文本再切片，输出为 `<p>...</p>`）。<br>示例：<br>`"/[0:500]"` → 只保留前 500 个字符<br>`"/[100:]"` → 删除前 100 个字符<br>`"/[:-200]"` → 删除最后 200 个字符<br>留空或不配置 → 不裁剪 |
| `exclude` | array | | 内容过滤规则列表，在 **HTML 源码**上操作，保留标签结构。每条规则是一个 `{type, value}` 对象，按数组顺序依次执行（详见下方 exclude 说明） |
| `delete` | string | | 按标题关键词**删除整篇文章**（逗号分隔多个关键词）。文章标题中包含任意一个关键词就跳过不收录。<br>示例：`"广告,推广,赞助"` → 标题含其中任一词的文章不收录 |

#### exclude 规则详解

`exclude` 数组中每条规则包含 `type` 和 `value` 两个字段，支持三种模式：

| type | 说明 | 示例 |
|------|------|------|
| `start` | 删除从文档**开头**到 `value`（含 value 本身）之间的所有内容。在文本节点中顺序查找第一个匹配位置 | `{ "type": "start", "value": "前言部分" }` |
| `end` | 删除从 `value`（含）到文档**结尾**的所有内容。在文本节点中逆序查找最后一次出现（rfind 语义） | `{ "type": "end", "value": "— 完 —" }` |
| `exact` | 在 HTML **源码**中精确匹配 `value` 字符串并删除所有出现。`value` 可以包含 HTML 标签，适合精确移除特定链接或广告 | `{ "type": "exact", "value": "<a href=\"https://spam.com\">推广</a>" }` |

> **注意**：`exclude` 在 HTML 上操作，会保留原始标签结构。关键词可以包含冒号等特殊字符。多条规则按顺序依次执行，可组合使用。

#### 各 type 的 src 含义与专属属性

**`rss` — RSS/Atom 订阅**

| 专属字段 | 类型 | 必填 | 说明 |
|---------|------|------|------|
| `src` | string | ✓ | RSS/Atom feed 的完整 URL |
| `full_text` | string | | 是否抓取完整正文。`"N"`（默认）→ 使用 feed 提供的摘要；`"Y"` → 访问原始 URL，用 trafilatura 提取全文，失败时回退到 BeautifulSoup 提取 `<article>`/`<main>` 等区域 |

```json
{
  "type": "rss",
  "title": "Hacker News",
  "src": "https://hnrss.org/frontpage",
  "priority": 10,
  "keep_link": "Y",
  "full_text": "Y",
  "chop": "/[0:2000]",
  "exclude": [
    { "type": "start", "value": "阅读更多" },
    { "type": "end", "value": "— 完 —" }
  ],
  "delete": "广告,推广"
}
```

**`web` — 网页抓取**

| 专属字段 | 类型 | 必填 | 说明 |
|---------|------|------|------|
| `src` | string | ✓ | 目标网页的完整 URL |

`web` 类型没有专属属性，但 `chop`、`exclude`、`delete` 同样适用。

```json
{
  "type": "web",
  "title": "热门文章",
  "src": "https://example.com/article",
  "priority": 5,
  "keep_link": "N",
  "exclude": [
    { "type": "start", "value": "分享到：" }
  ]
}
```

**`mail` — 邮件订阅（需要 `TESTMAIL_APP_API_KEY`）**

| 专属字段 | 类型 | 必填 | 说明 |
|---------|------|------|------|
| `src` | string | ✓ | testmail.app 的 **namespace**（不是邮箱地址）。testmail 的收件地址格式为 `{namespace}.{tag}@inbox.testmail.app`，代码会自动 URL 编码后传给 API |
| `metadata` | object | | 邮件查询的可选过滤参数（见下表） |

`metadata` 字段详解：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tag` | string | 无 | 按标签精确过滤（对应 `{namespace}.{tag}@inbox.testmail.app` 中的 tag） |
| `tag_prefix` | string | 无 | 按标签前缀过滤，例如 `"news"` 匹配 tag 为 `"news"`/`"newsletter"`/`"news-daily"` 的邮件 |
| `timestamp_from` | int | 无 | 起始时间戳（**毫秒**级 Unix 时间戳），只返回此时间之后收到的邮件 |
| `timestamp_to` | int | 无 | 结束时间戳（**毫秒**级），只返回此时间之前收到的邮件 |
| `limit` | int | `50` | 返回邮件数量上限（最大 `100`） |
| `offset` | int | `0` | 分页偏移量，配合 limit 使用 |

```json
{
  "type": "mail",
  "title": "订阅邮件",
  "src": "mynamespace",
  "priority": 8,
  "metadata": {
    "tag": "daily",
    "timestamp_from": 1718300000000,
    "limit": 10
  }
}
```

**`trending` — AI 热点分析（需要 `OPENROUTER_API_KEY`）**

| 专属字段 | 类型 | 必填 | 说明 |
|---------|------|------|------|
| `src` | string | ✓ | 搜索关键词/主题，发送给 LLM 的主题文本 |
| `goal` | string | | 分析目标/指令，告诉 LLM 要做什么。LLM 会输出 3-5 个要点 + 趋势分析 + 亮点。留空或不配置 → 自动使用默认值 `"分析并总结相关热点信息"` |
| `model` | string | | OpenRouter 模型 ID。留空或不配置 → 默认使用 `"openai/gpt-3.5-turbo"`。常用示例：`"openai/gpt-4o"`、`"anthropic/claude-3.5-sonnet"`、`"google/gemini-pro-1.5"` |

```json
{
  "type": "trending",
  "title": "AI 热点",
  "src": "人工智能最新发展趋势",
  "priority": 15,
  "goal": "分析最新的 AI 技术突破和应用案例，重点关注大模型、Agent、多模态方向",
  "model": "openai/gpt-4o"
}
```

### 完整示例

下面是一个使用了所有属性的完整 `config.json`，包含四种数据源：

```json
{
  "title": {
    "text": "{每日新闻 {time}}",
    "img": ""
  },
  "body": [
    {
      "type": "rss",
      "src": "https://hnrss.org/frontpage",
      "title": "Hacker News 首页",
      "priority": 10,
      "keep_link": "Y",
      "full_text": "Y",
      "chop": "/[0:2000]",
      "exclude": [
        { "type": "start", "value": "阅读更多" },
        { "type": "end", "value": "— 完 —" },
        { "type": "exact", "value": "<a href=\"https://spam.com\">推广链接</a>" }
      ],
      "delete": "广告,推广,赞助"
    },
    {
      "type": "web",
      "src": "https://example.com/article/123",
      "title": "深度报道",
      "priority": 5,
      "keep_link": "N",
      "exclude": [
        { "type": "start", "value": "分享到：" }
      ]
    },
    {
      "type": "mail",
      "src": "mynamespace",
      "title": "每日精选邮件",
      "priority": 8,
      "keep_link": "Y",
      "metadata": {
        "tag": "daily",
        "timestamp_from": 1718300000000,
        "limit": 10
      }
    },
    {
      "type": "trending",
      "src": "人工智能最新发展趋势",
      "title": "AI 行业热点",
      "priority": 15,
      "goal": "分析最新的 AI 技术突破和应用案例，重点关注大模型、Agent、多模态方向",
      "model": "openai/gpt-4o"
    }
  ]
}
```

**EPUB 中章节的排列顺序**（按 priority 降序）：
1. AI 行业热点（priority: 15）
2. Hacker News 首页（priority: 10）
3. 每日精选邮件（priority: 8）
4. 深度报道（priority: 5）

## 本地开发

### 安装依赖

```bash
pip install -r requirements.txt
```

需要测试依赖：
```bash
pip install pytest pytest-mock
```

### 运行

```bash
python src/main.py
```

### 测试

```bash
# 运行所有测试
python -m pytest tests/

# 显示详细信息
python -m pytest tests/ -v

# 只运行某个测试文件
python -m pytest tests/test_config.py -v

# 只运行某个测试类
python -m pytest tests/test_config.py::TestTitleConfig -v
```

当前测试覆盖：
- **配置加载**（`test_config.py`）— 26 个测试
- **工具函数**（`test_helpers.py`）— 28 个测试
- **内容处理**（`test_content_processor.py`）— 20 个测试
- **去重追踪**（`test_dedup_tracker.py`）— 15 个测试
- **数据抓取**（`test_fetchers.py`）— 32 个测试（mock HTTP）
- **图片处理**（`test_image_processor.py`）— 37 个测试

**共 158 个测试，全部通过。**

详细测试指南见 [TESTING.md](TESTING.md)。

### 项目结构

```
ought-gather/
├── src/
│   ├── main.py                 # 主入口
│   ├── config.py               # 配置管理
│   ├── fetchers/               # 数据抓取模块
│   │   ├── mail_fetcher.py     # 邮件抓取
│   │   ├── rss_fetcher.py      # RSS 抓取
│   │   ├── web_fetcher.py      # 网页抓取
│   │   └── trending_fetcher.py # 热点分析
│   ├── processors/             # 内容处理
│   │   ├── content_processor.py
│   │   └── image_processor.py
│   ├── epub/                   # EPUB 生成
│   │   ├── generator.py
│   │   ├── cover.py
│   │   └── toc.py
│   ├── dedup/                  # 去重追踪
│   │   └── tracker.py
│   ├── mailer/                 # 邮件发送
│   │   └── smtp_sender.py
│   └── utils/                  # 工具模块
│       ├── logger.py
│       └── helpers.py
├── tests/                      # 测试套件
│   ├── conftest.py            # 共享 fixtures
│   ├── test_config.py         # 配置测试
│   ├── test_helpers.py        # 工具函数测试
│   ├── test_content_processor.py # 内容处理测试
│   ├── test_dedup_tracker.py  # 去重测试
│   ├── test_fetchers.py       # 抓取器测试
│   └── test_image_processor.py # 图片处理测试
├── config.template.json        # 配置模板
├── requirements.txt            # Python 依赖
├── TESTING.md                  # 测试指南
└── .github/workflows/          # GitHub Actions
    └── daily-gather.yml
```

## 常见问题

### Q: 如何测试配置是否正确？

A: 在本地创建 `config.json`，运行 `python src/main.py`，检查 `output/` 目录生成的 EPUB 文件。

### Q: Kindle 收不到邮件怎么办？

A: 
1. 检查发送邮箱是否已添加到 Kindle 的"已认可的发件人电子邮箱列表"
2. 检查 SMTP 配置是否正确（特别是授权码）
3. 查看 GitHub Actions 运行日志

### Q: 如何修改运行时间？

A: 编辑 `.github/workflows/daily-gather.yml`，修改 `cron` 表达式。

### Q: 支持哪些邮箱服务？

A: 支持所有提供 SMTP 服务的邮箱，如 Gmail、QQ 邮箱、163 邮箱等。注意需要使用授权码而非登录密码。

## 技术栈

- **Python 3.11+**
- **feedparser**: RSS/Atom 解析
- **trafilatura**: 网页正文提取
- **ebooklib**: EPUB 生成
- **Pillow**: 图片处理
- **httpx**: HTTP 请求

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
