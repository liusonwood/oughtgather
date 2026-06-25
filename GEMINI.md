# Ought Gather — Developer Guide (GEMINI.md)

This guide provides compact developer instructions, architecture decisions, and strict compliance guidelines for working on the Ought Gather codebase.

## Common Commands

- **Install**: `pip install -r requirements.txt`
- **Run**: `python3.11 src/main.py [--config path/to/config.json]`
- **Test**: `python3.11 -m pytest tests/` (use `-v` for detail, `--tb=short` for brief failures, or target a specific file like `tests/test_config.py`)

## Tooling & Automation

- **Config Editor**: Open `config-editor.html` in browser for a visual configuration builder.
- **GitHub Actions**: Runs daily at UTC 00:00 (08:00 Beijing time). Explicitly sets `TZ=Asia/Shanghai`. Automatically uploads logs and EPUB artifacts.

## Architecture & Core Rules

- **Flow**: `config.json` → `Fetchers` → `Processors` → `Dedup` → `EPUB Generator` → `SMTP Sender`
- **Timezone**: All timestamping and datetime calculations must use Beijing Time (UTC+8) via `src/utils/helpers.py:get_now()`.
- **Fetchers (`src/fetchers/`)**:
  - `MailFetcher`: Uses testmail.app API. `src` supports `"namespace"` or `"namespace.tag"` (dot-split). `metadata` enables tags, limits, and date range filters.
  - `RSSFetcher`: feedparser. Supports `full_text=Y/N` for full article retrieval via trafilatura.
  - `WebFetcher`: Trafilatura with BeautifulSoup fallback.
  - `TrendingFetcher`: LLM generation via OpenRouter API.
- **Processors (`src/processors/`)**:
  - `content_processor`: Applies `keep_link`, `chop`, `exclude`, and `delete` rules.
  - `image_processor`: Downloads/compresses images (≤250KB, max 640×960, JPEG Q75). Filters out small decorative assets (< 120×120).
- **Dedup Tracker (`src/dedup/tracker.py`)**: File-based tracker (`data/fetched_urls.txt`) storing URL/title hashes. Automatically prunes old records when exceeding `MAX_RECORDS = 5000`.
- **EPUB Generator (`src/epub/`)**:
  - Cover: Custom (`title.img`) or Bing Daily wallpaper with text/date overlays.
  - TOC: Flat layout (source → articles).
  - Compliance: Standard `FOLDER_NAME='EPUB'` must be used (avoids OCF RSC-026). OPF version must be `3.0`. EPUB 3.0 requires both EpubNcx and EpubNav items (avoids RSC-005). XHTML covers must not be empty. Escape f-string CSS curly braces as `{{}}`. EPUBCheck validates against EPUB 3.3 rules (`java -jar epubcheck.jar <file.epub>`).

## Configuration

Required credentials (environment or GitHub Secrets): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `KINDLE_EMAIL`.
Optional variables: `CONFIG_JSON` (overrides file), `TESTMAIL_APP_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_API_ENDPOINT`.

### config.json Schema
```json
{
  "title": {
    "text": "{Daily News {time}}", // supports {time} and </br> placeholders
    "img": "" // Custom cover image URL, fallback to Bing daily image if empty
  },
  "body": [
    {
      "type": "rss|mail|web|trending",
      "src": "URL, namespace[.tag], or keyword query",
      "priority": 10, // Higher priority items appear earlier in book (stable sorted)
      "keep_link": "Y|N",
      "full_text": "Y|N", // RSS only
      "chop": "/[start:end]",
      "exclude": [{"type": "start|end|exact", "value": "keyword"}],
      "delete": "keyword1,keyword2",
      "metadata": {} // Fetcher-specific options
    }
  ]
}
```
