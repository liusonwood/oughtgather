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

- `text`: 书名，支持 `{time}` 占位符（自动替换为日期）
- `img`: 封面图片 URL（留空则使用 Bing 每日壁纸）

### 内容源配置 (body)

每个内容源支持以下字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✓ | 数据源类型：`mail` / `rss` / `web` / `trending` |
| `src` | string | ✓ | 数据源地址（RSS URL / 网页 URL / 邮箱 / 关键词） |
| `title` | string | | 自定义章节标题 |
| `priority` | number | | 优先级（数字越大越靠前，默认 0） |
| `keep_link` | string | | 是否保留链接：`Y` / `N`（默认 Y） |
| `full_text` | string | | RSS 是否抓取全文：`Y` / `N`（默认 N） |
| `chop` | string | | 内容裁剪：`/[start:end]` |
| `exclude` | array | | 内容过滤规则列表，支持三种模式（见下方说明） |
| `delete` | string | | 删除包含关键词的文章（逗号分隔） |
| `goal` | string | | trending 类型的分析目标 |
| `model` | string | | trending 使用的 LLM 模型 |
| `metadata` | object | | 数据源的额外参数（目前仅 mail 类型使用，用于 API 查询过滤） |

### 配置示例

#### RSS 订阅

```json
{
  "type": "rss",
  "title": "Hacker News",
  "src": "https://hnrss.org/frontpage",
  "priority": 10,
  "keep_link": "Y",
  "full_text": "Y"
}
```

#### 网页抓取

```json
{
  "type": "web",
  "title": "热门文章",
  "src": "https://example.com/article",
  "priority": 5
}
```

#### 邮件订阅（需要 TestMail.app）

```json
{
  "type": "mail",
  "title": "订阅邮件",
  "src": "mynamespace",
  "priority": 8
}
```

> `src` 的值是 testmail.app 的 **namespace**（不是邮箱地址）。testmail 的收件地址格式为 `{namespace}.{tag}@inbox.testmail.app`，
> `src` 中的 `.` 只是 namespace 的命名分隔符，代码会自动 URL 编码后传给 API。

带 metadata 查询参数的完整用法：

```json
{
  "type": "mail",
  "src": "mynamespace",
  "metadata": {
    "tag": "daily",
    "limit": 10,
    "timestamp_from": 1718300000000
  }
}
```

| metadata 字段 | 类型 | 默认值 | 说明 |
|--------------|------|--------|------|
| `tag` | string | 无 | 按标签精确过滤（对应 `{namespace}.{tag}@inbox.testmail.app` 中的 tag） |
| `tag_prefix` | string | 无 | 按标签前缀过滤 |
| `timestamp_from` | int | 无 | 起始时间戳（**毫秒**），只返回此时间之后收到的邮件 |
| `timestamp_to` | int | 无 | 结束时间戳（**毫秒**），只返回此时间之前收到的邮件 |
| `limit` | int | `10` | 返回邮件数量上限（最大 `100`） |
| `offset` | int | `0` | 偏移量，用于翻页 |

#### AI 热点分析（需要 OpenRouter API）

```json
{
  "type": "trending",
  "title": "AI 热点",
  "src": "人工智能最新发展",
  "priority": 15,
  "goal": "分析最新的 AI 技术突破和应用案例",
  "model": "openai/gpt-4"
}
```

#### 内容过滤规则 (exclude)

`exclude` 是一个数组，每条规则包含 `type` 和 `value` 两个字段，支持三种模式：

| type | 说明 |
|------|------|
| `start` | 删除从文档开头到 `value`（含）之间的内容 |
| `end` | 删除从 `value`（含）到文档结尾的内容 |
| `exact` | 在 HTML 源码中精确匹配 `value` 并删除（可包含 HTML 标签） |

示例：

```json
{
  "exclude": [
    { "type": "start", "value": "前言部分" },
    { "type": "end",   "value": "— 完 —" },
    { "type": "exact", "value": "<a href=\"https://spam.com\">推广链接</a>" }
  ]
}
```

**注意**：`exclude` 在 HTML 上操作，会保留原始标签结构。关键词可以包含冒号等特殊字符。

## 本地开发

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python src/main.py
```

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
├── config.template.json        # 配置模板
├── requirements.txt            # Python 依赖
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
