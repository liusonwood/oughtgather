# Ought Gather

[![Daily Gather](https://github.com/liusonwood/oughtgather/actions/workflows/daily-gather.yml/badge.svg)](https://github.com/liusonwood/oughtgather/actions/workflows/daily-gather.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![EPUB 3.0](https://img.shields.io/badge/EPUB-3.0-6f42c1)](docs/EPUB_COMPLIANCE.md)
[![Kindle Delivery](https://img.shields.io/badge/Kindle-Email%20Delivery-orange)](#github-actions)

Ought Gather 是一个 Python 自动化信息聚合工具。它从 RSS、网页、TestMail.app 邮件和 LLM 热点分析源收集内容，去重和清洗后生成 EPUB，并通过 SMTP 邮件发送到 Kindle 接收邮箱。

项目内置 GitHub Actions 工作流：每天 UTC 00:00 运行一次，也可以手动触发。工作流会安装依赖、准备 `config.json`、执行 `python src/main.py`、提交去重记录，并把生成的 EPUB 作为 artifact 保留 7 天。

## 功能

- 支持四类内容源：`rss`、`web`、`mail`、`trending`
- 生成 EPUB 3.0 文件，包含封面、目录、正文和推送汇总章节
- 封面可使用自定义图片；未配置时尝试使用 Bing 每日壁纸，失败后使用纯色背景
- 支持标题日期占位符 `{time}` 和封面标题换行标记 `</br>`
- 支持按源设置优先级、链接保留、全文抓取、内容裁剪、HTML 过滤和标题关键词删除
- 使用 `data/fetched_urls.txt` 记录已处理内容；记录超过 50000 条时保留最新记录
- 支持通过 `CONFIG_JSON` 环境变量提供完整配置，避免把私有源写入仓库

## 环境要求

- Python 3.11+
- 依赖见 `requirements.txt`
- Kindle 推送需要可用的 SMTP 邮箱
- `mail` 源需要 `TESTMAIL_APP_API_KEY`
- `trending` 源需要 `OPENROUTER_API_KEY`

## 新手简单使用教程

这条路线不需要在本地安装 Python，适合只想每天自动收到 Kindle 推送的用户。

### 1. Fork 仓库

在 GitHub 页面点击 `Fork`，把项目复制到自己的账号下。后续配置都在你自己的仓库里完成。

### 2. 开启 Actions 写入权限

进入你的仓库：

```text
Settings -> Actions -> General -> Workflow permissions
```

选择 `Read and write permissions`，然后保存。这个权限用于让工作流更新 `data/fetched_urls.txt`，避免每天重复推送同一批文章。

### 3. 准备 Kindle 和发件邮箱

你需要两个邮箱地址：

| 项目 | 说明 |
| --- | --- |
| 发件邮箱 | 用来通过 SMTP 发送 EPUB 附件 |
| Kindle 接收邮箱 | Kindle 的 `@kindle.com` 收件地址 |

在亚马逊 Kindle 设置里，把发件邮箱加入“已认可的发件人电子邮箱列表”。否则邮件发送成功后，Kindle 也可能不会接收附件。

### 4. 添加 GitHub Secrets

进入你的仓库：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

先添加这 5 个必需 Secret：

| Secret | 示例 | 说明 |
| --- | --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` | 发件邮箱的 SMTP 服务器 |
| `SMTP_PORT` | `587` | 常见值是 `587` 或 `465` |
| `SMTP_USERNAME` | `sender@example.com` | 发件邮箱账号 |
| `SMTP_PASSWORD` | `xxxx xxxx xxxx xxxx` | 邮箱授权码或应用密码 |
| `KINDLE_EMAIL` | `name@kindle.com` | Kindle 接收邮箱 |

如果只使用 RSS 和网页源，可以先不配置 `TESTMAIL_APP_API_KEY`、`OPENROUTER_API_KEY`。

### 5. 添加配置 Secret

继续新建一个名为 `CONFIG_JSON` 的 Secret，值填完整配置。可以先使用下面这个最小配置：

```json
{
  "title": {
    "text": "{每日新闻 {time}}",
    "img": ""
  },
  "limit": 10,
  "body": [
    {
      "type": "rss",
      "src": "https://hnrss.org/frontpage",
      "title": "Hacker News",
      "priority": 10,
      "keep_link": "Y",
      "full_text": "N"
    }
  ]
}
```

确认能跑通后，可以下载 `config-editor.html` 在浏览器中打开，配置订阅源。

### 6. 手动运行一次

进入：

```text
Actions -> Daily Gather -> Run workflow
```

点击运行后，等待任务完成。成功时通常会发生三件事：

- `output/` 中生成 EPUB，并作为 Actions artifact 上传
- EPUB 通过邮件发送到 `KINDLE_EMAIL`
- `data/fetched_urls.txt` 被提交更新，用于下次去重

### 7. 检查失败原因

如果没有收到 Kindle 推送，先在 Actions 运行记录里看失败步骤：

| 现象 | 常见原因 |
| --- | --- |
| 配置准备失败 | `CONFIG_JSON` 不是合法 JSON |
| SMTP 登录失败 | `SMTP_USERNAME`、`SMTP_PASSWORD`、端口或授权码错误 |
| 邮件发出但 Kindle 没收到 | 发件邮箱没有加入 Kindle 认可列表 |
| 没生成 EPUB | 所有内容都已抓取过，或内容源没有新文章 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备配置

复制模板并修改：

```bash
cp config.template.json config.json
```

最小示例：

```json
{
  "title": {
    "text": "{每日新闻 {time}}",
    "img": ""
  },
  "limit": 15,
  "body": [
    {
      "type": "rss",
      "src": "https://hnrss.org/frontpage",
      "title": "Hacker News",
      "priority": 10,
      "keep_link": "Y",
      "full_text": "N"
    }
  ]
}
```

也可以直接在浏览器中打开 `config-editor.html` 编辑配置。完整字段说明见 [docs/CONFIG.md](docs/CONFIG.md)。

### 3. 设置环境变量

本地运行至少需要 SMTP 和 Kindle 接收邮箱配置：

```bash
export SMTP_HOST="smtp.example.com"
export SMTP_PORT="587"
export SMTP_USERNAME="sender@example.com"
export SMTP_PASSWORD="app-password"
export KINDLE_EMAIL="name@kindle.com"
```

可选变量：

| 变量 | 用途 |
| --- | --- |
| `CONFIG_JSON` | 完整 `config.json` 字符串；优先级高于本地 `config.json` |
| `TESTMAIL_APP_API_KEY` | 读取 TestMail.app 邮件 |
| `OPENROUTER_API_KEY` | 调用 LLM 生成热点分析 |
| `OPENROUTER_API_ENDPOINT` | 自定义 OpenRouter 兼容接口，默认 `https://openrouter.ai/api/v1/chat/completions` |
| `OPENROUTER_MODEL` | `trending` 源的全局默认模型；低于单个源的 `model` 字段 |

Kindle 侧还需要把发送邮箱加入“已认可的发件人电子邮箱列表”。

### 4. 运行

```bash
python src/main.py
```

有新内容时，程序会在 `output/` 下生成 EPUB，并尝试发送到 `KINDLE_EMAIL`。日志写入 `logs/`。

## GitHub Actions

工作流文件是 [.github/workflows/daily-gather.yml](.github/workflows/daily-gather.yml)。

Fork 或部署到自己的仓库后，在 `Settings -> Secrets and variables -> Actions` 中配置：

| Secret | 必需 | 说明 |
| --- | --- | --- |
| `SMTP_HOST` | 是 | SMTP 服务器地址 |
| `SMTP_PORT` | 是 | SMTP 端口；`465` 使用 SSL，其他端口使用 STARTTLS |
| `SMTP_USERNAME` | 是 | 发件邮箱账号 |
| `SMTP_PASSWORD` | 是 | 发件邮箱密码或应用授权码 |
| `KINDLE_EMAIL` | 是 | Kindle 接收邮箱 |
| `CONFIG_JSON` | 否 | 完整配置；未设置时工作流读取仓库中的 `config.json` |
| `TESTMAIL_APP_API_KEY` | 否 | `mail` 源所需 |
| `OPENROUTER_API_KEY` | 否 | `trending` 源所需 |
| `OPENROUTER_API_ENDPOINT` | 否 | OpenRouter 兼容接口地址 |
| `OPENROUTER_MODEL` | 否 | `trending` 源默认模型 |

工作流会把 `data/fetched_urls.txt` 提交回仓库，因此仓库 Actions 权限需要允许写入内容。

### 修改运行时间

定时触发由 [.github/workflows/daily-gather.yml](.github/workflows/daily-gather.yml) 的 `on.schedule` 控制：

```yaml
on:
  schedule:
    # 当前仓库实测约在北京时间 12:00 运行
    - cron: '0 0 * * *'
  workflow_dispatch:
```

要修改自动运行时间，只需要改 `cron` 这一行。GitHub Actions 的 cron 使用 UTC，不使用北京时间；工作流里的 `TZ: Asia/Shanghai` 只影响程序运行时的日期、日志和内容生成，不影响触发时间。

按 UTC 换算，`cron: '0 0 * * *'` 对应北京时间 08:00；但当前仓库的实际运行记录显示，这个配置约在北京时间 12:00 触发。也就是说，下面的表格是 cron 语义上的换算，实际触发时间仍应以 GitHub Actions 运行记录为准。

如果你希望按当前仓库的实际表现调整时间，可以用现有配置作为参照：`'0 0 * * *'` 实测约为北京时间 12:00。比如想提前 1 小时到北京时间 11:00，可以改为：

```yaml
schedule:
  - cron: '0 23 * * *'
```

也可以保留 `workflow_dispatch`，这样即使改了定时规则，仍能在 GitHub Actions 页面手动运行。

## 配置要点

>项目提供了一个可视化 HTML 配置编辑器，浏览器打开 `config-editor.html` 即可使用。

顶层字段：

| 字段 | 说明 |
| --- | --- |
| `title` | EPUB 标题和封面配置 |
| `limit` | 每个内容源的默认抓取上限，默认 `15` |
| `body` | 内容源数组 |

内容源通用字段：

| 字段 | 说明 |
| --- | --- |
| `type` | `rss`、`web`、`mail`、`trending` |
| `src` | 内容源地址或主题；所有类型必填 |
| `title` | EPUB 中显示的章节标题 |
| `priority` | 章节排序值，数值越大越靠前 |
| `keep_link` | `Y` 保留链接，`N` 移除链接标签但保留文字 |
| `full_text` | RSS 是否抓取原文；`Y` 启用 |
| `chop` | 使用 `"/[start:end]"` 形式裁剪纯文本 |
| `exclude` | 按 `start`、`end`、`exact` 规则过滤 HTML 内容 |
| `delete` | 标题包含指定关键词时跳过整篇文章 |
| `goal` | `trending` 源的分析目标 |
| `model` | `trending` 源使用的模型 |
| `metadata` | 类型专属扩展配置，如邮件 tag、limit、时间范围 |

## 测试

```bash
python -m pytest tests/
python -m pytest tests/ -v
```

常用定向测试：

```bash
python -m pytest tests/test_config.py -v
python -m pytest tests/test_fetchers.py -v
python -m pytest tests/test_epub_compliance.py -v
```

集成测试支持 [epubcheck](https://github.com/w3c/epubcheck) 。若要启用 W3C EPUB 校验，把 `epubcheck.jar` 放在：

```text
epubcheck/epubcheck.jar
```

然后运行：

```bash
python -m pytest tests/test_integration.py::TestEpubcheckValidation -v
```

更多说明见 [docs/TESTING.md](docs/TESTING.md) 和 [docs/EPUB_COMPLIANCE.md](docs/EPUB_COMPLIANCE.md)。

## 项目结构
```
ought-gather/
├── config-editor.html          # 可视化配置编辑器（浏览器打开）
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
│   ├── conftest.py             # 共享 fixtures
│   ├── test_config.py          # 配置测试
│   ├── test_helpers.py         # 工具函数测试
│   ├── test_content_processor.py # 内容处理测试
│   ├── test_dedup_tracker.py   # 去重测试
│   ├── test_fetchers.py        # 抓取器测试
│   ├── test_image_processor.py # 图片处理测试
│   ├── test_epub_compliance.py # EPUB合规性测试（21个测试）
│   └── test_integration.py     # 集成测试（含epubcheck验证）
├── config.template.json        # 配置模板
├── docs/
│   ├── CONFIG.md               # 配置指南（config.json 详细说明）
│   ├── TESTING.md              # 测试指南
│   ├── EPUB_COMPLIANCE.md      # EPUB合规指南（常见错误与解决方案）
│   ├── design.md               # Ought Gather 项目设计文档
│   └── testmail-api.md         # TestMail.app API 文档
└── .github/workflows/          # GitHub Actions
    └── daily-gather.yml
```
## 许可证

Apache 2.0，见 [LICENSE](LICENSE)。
