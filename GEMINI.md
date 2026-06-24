# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ought Gather is an elegant, automated content curation and delivery pipeline designed for deep-reading and E-ink enthusiasts. It helps readers reclaim their reading autonomy in an era of fragmented algorithms by fetching high-quality content from trusted RSS feeds, newsletters, web pages, and AI trend digests. The tool cleanses layouts, compresses images, intelligently deduplicates entries, and packages them into beautiful, EPUB 3.0-compliant ebooks, automatically dispatched to Kindle devices daily via GitHub Actions.

## Common Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running
```bash
# Main execution
python3.11 src/main.py

# With custom config path
python3.11 src/main.py --config path/to/config.json
```

### Testing
```bash
# 运行所有测试（171 个测试，约 1 秒）
python3.113.11 -m pytest tests/

# 详细输出
python3.113.11 -m pytest tests/ -v

# 只运行某个文件
python3.113.11 -m pytest tests/test_config.py -v

# 只运行某个测试类
python3.11 -m pytest tests/test_config.py::TestTitleConfig -v

# 只显示失败测试的详细信息
python3.11 -m pytest tests/ --tb=short
```

**测试覆盖**：配置加载、内容处理（exclude/chop/keep_link/delete）、去重追踪（含自动清理）、数据抓取（RSS/Web/Mail/Trending）、图片处理、工具函数。

详细测试指南见 [TESTING.md](docs/TESTING.md)。

### Configuration Editor
A visual HTML editor for `config.json` is available — open [config-editor.html](config-editor.html) in a browser.
- Supports all 4 source types (rss / mail / web / trending) with type-specific fields
- Import existing config.json, add/remove/reorder sources, manage exclude rules and metadata
- Export via download or copy to clipboard

### GitHub Actions
- Automated daily run: UTC 00:00 (Beijing 08:00)
- Manual trigger: via GitHub Actions UI "Daily Gather" workflow
- Logs and EPUB artifacts uploaded automatically
- **Timezone**: Uses `TZ=Asia/Shanghai` environment variable to ensure all timestamps are in Beijing time (UTC+8)

## Architecture

### Core Flow
```
config.json → Fetchers → Processors → Dedup → EPUB Generator → SMTP Sender
```

1. **Config Loading** (`src/config.py`): Loads from `CONFIG_JSON` env var or `config.json` file. Validates structure and provides typed access via `TitleConfig`, `ContentSource`, and `Config` dataclasses.

2. **Fetchers** (`src/fetchers/`): Strategy pattern with `BaseFetcher` abstract class. Four implementations:
   - `MailFetcher`: Uses testmail.app API. `src` field supports `"namespace"` or `"namespace.tag"` format — if a dot is present, it splits into namespace + tag. Spaces are stripped. Supports metadata for query params (tag overrides src tag, limit, timestamp range).
   - `RSSFetcher`: Uses feedparser. Supports `full_text=Y/N` to extract full article via trafilatura.
   - `WebFetcher`: Single page extraction via trafilatura with fallback to BeautifulSoup.
   - `TrendingFetcher`: LLM-based content generation via OpenRouter API.

3. **Content Processing** (`src/processors/`): Applies `keep_link`, `chop`, `exclude`, `delete` rules. `ImageProcessor` downloads and compresses images (≤250KB per image, max 640×960, JPEG quality 75). Skips images smaller than 120×120 (icons, avatars, emoji, other decorative graphics).

4. **Dedup Tracking** (`src/dedup/tracker.py`): File-based dedup using `data/fetched_urls.txt`. Tracks by URL+title hash. Auto-cleans old records when exceeding `MAX_RECORDS` (default 5000), keeping the newest entries. Persisted across runs via git commits in GitHub Actions.

5. **EPUB Generation** (`src/epub/`): 
   - `cover.py`: Custom image (from `title.img`) or Bing daily wallpaper. Overlays title and date.
   - `toc.py`: Flat hierarchy (source → articles). No nested chapters.
   - `generator.py`: Assembles EPUB with ebooklib. Sorts by priority (descending), stable sort.
   
   **EPUB Compliance Requirements** (Critical - learned from EPUBCheck validation failures):
   - **Directory Structure**: Must use standard `EPUB/` folder (default `FOLDER_NAME='EPUB'`). Setting `FOLDER_NAME=''` causes absolute paths like `/file.xhtml` which violate OCF spec (RSC-026 error).
   - **EPUB Version**: ebooklib 0.20 hardcodes `version="3.0"` in OPF. Cannot downgrade to EPUB 2.0 via `book.version='2.0'`. Must accept EPUB 3.0 format.
   - **Navigation**: EPUB 3.0 **requires** both `EpubNcx()` and `EpubNav()` items. Missing nav document causes RSC-005 error ("Exactly one manifest item must declare the 'nav' property").
   - **CSS in f-string**: When writing CSS in python3.11 f-string, must escape braces with `{{}}` (e.g., `body {{ margin: 0; }}`), otherwise python3.11 interprets `{}` as expression placeholders.
   - **Cover HTML**: Cover XHTML must have proper content, not empty. Use simple `<img src="cover.jpg"/>` structure for compatibility.
   - **Guide Element**: Keep `book.guide` for backward compatibility (EPUB 2.0 feature, optional in EPUB 3.0).
   - **Validation**: Always run EPUBCheck validation: `java -jar epubcheck.jar <file.epub>`. EPUBCheck validates against EPUB 3.3 rules by default.

6. **Email Delivery** (`src/mailer/smtp_sender.py`): Sends EPUB as attachment to Kindle email.

### Key Design Decisions

- **Timezone**: All datetime operations use `get_now()` from `src/utils/helpers.py` which returns Beijing time (UTC+8) via `zoneinfo.ZoneInfo("Asia/Shanghai")`. GitHub Actions workflow sets `TZ=Asia/Shanghai` for consistency.
- **Error Tolerance**: Failed sources are skipped and logged. Errors included in EPUB as a final chapter.
- **No livequery**: Mail fetcher queries existing emails, not waiting for new ones.
- **URL Encoding**: Namespace in MailFetcher is URL-encoded to handle special characters. Spaces are stripped. `src` supports `"namespace.tag"` format — splits on first dot into namespace + tag.
- **Dedup Auto-Cleanup**: `DedupTracker.MAX_RECORDS = 5000`. When `save()` causes the file to exceed this limit, old records (top of file) are trimmed, keeping only the newest. In-memory `fetched_ids` set is synced to match.
- **ContentSource.metadata**: Optional dict for fetcher-specific parameters (e.g., mail query filters).
- **Secrets Management**: All credentials via GitHub Secrets or environment variables. Never in code.

## Configuration

### Required Environment Variables (GitHub Secrets)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `KINDLE_EMAIL`

### Optional Environment Variables
- `CONFIG_JSON`: Full config.json content (recommended for privacy)
- `TESTMAIL_APP_API_KEY`: For mail fetching
- `OPENROUTER_API_KEY`, `OPENROUTER_API_ENDPOINT`: For AI trend analysis

### config.json Structure
```json
{
  "title": {
    "text": "{Daily News {time}}",  // 支持 {time} 占位符和 </br> 换行符（如 "{Daily News</br>{time}}"）。每行文字自动适配大小，并添加黑色边框增强可读性
    "img": ""  // 自定义封面 URL，留空则使用 Bing 每日壁纸
  },
  "body": [
    {
      "type": "rss|mail|web|trending",
      "src": "URL or namespace[.tag] or keyword",  // mail: "namespace" or "namespace.tag"
      "priority": 10,  // Higher = earlier in EPUB
      "keep_link": "Y|N",
      "full_text": "Y|N",  // RSS only
      "chop": "/[start:end]",
      "exclude": [{"type": "start|end|exact", "value": "keyword"}],
      "delete": "keyword1,keyword2",
      "metadata": {}  // Fetcher-specific params
    }
  ]
}
```

## Development Notes

- **python 3.11+** required (uses `zoneinfo` module for timezone support, available since python3.11 3.9)
- **Dependencies**: feedparser, trafilatura, ebooklib, Pillow, httpx, beautifulsoup4, lxml
- **Test dependencies**: pytest, pytest-mock
- **Logging**: Uses singleton logger (`src/utils/logger.py`). Logs to `logs/` directory.
- **Timezone**: All timestamps use Beijing time (UTC+8) via `zoneinfo.ZoneInfo("Asia/Shanghai")`.
- **Data Directory**: `data/fetched_urls.txt` for dedup. Gitignored except in GitHub Actions.
- **Output**: EPUB files written to `output/` directory.
- **Test Suite**: 171 tests in `tests/` directory. All tests use mocks to avoid network requests. See [TESTING.md](docs/TESTING.md) for details.

## File Structure

```
config-editor.html        # Visual config.json editor (open in browser)
src/
├── main.py                 # Entry point, orchestrates the pipeline
├── config.py               # Configuration loading and validation
├── fetchers/               # Data source implementations
│   ├── base.py            # BaseFetcher, Article, FetchResult
│   ├── mail_fetcher.py    # testmail.app API
│   ├── rss_fetcher.py     # RSS/Atom with feedparser
│   ├── web_fetcher.py     # Single page extraction
│   └── trending_fetcher.py # LLM-based generation
├── processors/            # Content transformation
│   ├── content_processor.py # HTML cleaning, rule application
│   └── image_processor.py  # Download, compress, embed
├── epub/                  # Ebook generation
│   ├── generator.py       # Main EPUB assembly
│   ├── cover.py           # Cover image generation
│   └── toc.py             # Table of contents
├── dedup/
│   └── tracker.py         # URL/title dedup tracking
├── mailer/
│   └── smtp_sender.py     # Email with attachment
└── utils/
    ├── logger.py          # Singleton logging
    └── helpers.py         # URL normalization, text extraction

tests/
├── __init__.py
├── conftest.py              # Shared fixtures (ContentSource, HTML samples, etc.)
├── test_config.py           # 26 tests - config loading and validation
├── test_helpers.py          # 40 tests - utility functions
├── test_content_processor.py # 30 tests - exclude/chop/keep_link/delete rules
├── test_dedup_tracker.py    # 19 tests - dedup tracking, persistence, and auto-cleanup
├── test_fetchers.py         # 26 tests - RSS/Web/Mail/Trending fetchers (mocked HTTP)
└── test_image_processor.py  # 32 tests - image download, resize, compress, small-image filtering

docs/
├── CONFIG.md                # Configuration guide (detailed config.json explanation)
├── TESTING.md               # Testing guide
├── EPUB_COMPLIANCE.md       # EPUB compliance guide (common errors and solutions)
├── design.md                # Project design documentation
└── testmail-api.md          # TestMail.app API documentation
```

## Documentation Maintenance

**Important**: When moving or renaming or editing files :
1. Update [README.md](README.md)
2. Update this [CLAUDE.md](CLAUDE.md) file
3. Keep documentation organized under the `docs/` directory
