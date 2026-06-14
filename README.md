# Ought Gather

自动化信息聚合工具，将邮件订阅、RSS、网页内容整合为 EPUB 电子书，并推送到 Kindle 设备。

## 功能特性

- **多数据源支持**：邮件订阅、RSS、网页、AI 热点分析
- **智能去重**：自动记录已抓取内容，避免重复；超过 5000 条时自动清理旧记录
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
    "text": "{Daily News {time}}",  // 支持 {time} 占位符和 </br> 换行符（如 "{Daily News</br>{time}}"）
    "img": ""  // 自定义封面 URL，留空则使用 Bing 每日壁纸
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

详细配置说明见 [配置指南](docs/CONFIG.md)。

### 4. 运行

- **自动运行**：每天 UTC 00:00（北京时间 08:00）自动执行
- **手动运行**：在 GitHub Actions 页面手动触发 "Daily Gather" 工作流

## 配置

详见 [配置指南](docs/CONFIG.md)，涵盖：

- 标题与封面配置（`title`）
- 四种数据源类型（`rss` / `web` / `mail` / `trending`）的专属字段
- 内容过滤（`exclude` / `chop` / `delete`）
- 完整示例与可视化配置编辑器（`config-editor.html`）

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
- **工具函数**（`test_helpers.py`）— 40 个测试
- **内容处理**（`test_content_processor.py`）— 30 个测试
- **去重追踪**（`test_dedup_tracker.py`）— 19 个测试
- **数据抓取**（`test_fetchers.py`）— 26 个测试（mock HTTP）
- **图片处理**（`test_image_processor.py`）— 25 个测试

**共 171 个测试。**

详细测试指南见 [TESTING.md](docs/TESTING.md)。

### 项目结构

```
ought-gather/
├── config-editor.html        # 可视化配置编辑器（浏览器打开）
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
├── docs/
│   ├── CONFIG.md               # 配置指南（config.json 详细说明）
│   └── TESTING.md              # 测试指南
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
