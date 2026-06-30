# Ought Gather - Custom Fetcher LLM Developer Prompt

Copy and paste the template below to another LLM to guide it in automatically generating a new fetcher plugin for your Ought Gather codebase.

---

## 📋 New Fetcher Requirements Questionnaire
Before using the prompt below, please answer these questions and insert your answers into the **`[INSERT YOUR SPECIFIC FETCHING REQUIREMENTS OR SITE NAME HERE]`** placeholder at the very bottom:

1. **What is the target source?** (e.g., a specific website's pages, an RSS feed, a platform's JSON API, etc.)
2. **What configurations are needed in `config.json`?**
   - What should the `src` field contain? (e.g., API URL, webpage URL, User ID, tag, etc.)
   - Do you need any custom parameters under `metadata`? (e.g., `limit` limit, `category` filter, `format` selection, etc.)
3. **Does it require security credentials (API Keys / Secrets)?**
   - What environment variables need to be set? (e.g., `MY_API_KEY`)
4. **How is the article content located and parsed?**
   - Where are the title, content body, author, publication date, and images located in the HTML tags or JSON keys?
5. **Are there any special processing rules?**
   - Do you need specific content filtering, text replacement, or customized retry settings?

---

```markdown
You are an expert python coding assistant. Help me write a new fetcher plugin for Ought Gather, a news aggregation tool.

### 1. Architectural Rules & Requirements
- **Plugin Registry**: Every fetcher must inherit from `BaseFetcher` (from `src.fetchers.base`) and specify a unique class-level `type_name = "your_type"`. Subclasses are registered automatically upon module loading. Do not modify the main script or registry to register it.
- **File Placement**: Save the new fetcher in a file named `src/fetchers/<your_type>_fetcher.py`.
- **Return Type**: The fetcher must implement the `fetch(self) -> FetchResult` method, returning a `FetchResult` instance populated with `Article` objects.
- **Parent Helpers**:
  - Use `self._make_request(url, ...)` for HTTP requests.
  - Use `self._extract_images(html)` to parse image URLs from HTML pages.
  - Use `self._should_delete(article_title)` to check if a title matches configured deletion keywords.
  - Use `self._restore_img_tags(html)` if using tools that output non-standard image tags (like trafilatura).
- **Timezone**: All timestamping and datetime calculations must use Beijing Time (UTC+8) via `src.utils.helpers.get_now()`.

### 2. Base Classes & Dataclasses (For Reference)
```python
# Defined in src.fetchers.base
@dataclass
class Article:
    title: str
    content: str  # HTML format
    url: str
    author: Optional[str] = None
    published_date: Optional[str] = None
    images: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FetchResult:
    source: ContentSource
    articles: List[Article]
    success: bool = True
    error: Optional[str] = None
    error_count: int = 0
    source_title: Optional[str] = None
```

### 3. Fetcher Configuration & Secrets
- **Custom Config**: Access user configuration from `config.json` via `self.source.metadata` (e.g. `self.source.metadata.get("param_name")`).
- **Secrets**: If your fetcher needs API keys or secret tokens:
  1. Define a class-level variable `required_secrets = ["MY_API_KEY_1", "MY_API_KEY_2"]` in your fetcher class.
  2. Access them within your class using `os.environ.get("MY_API_KEY_1")`.

### 4. Fetcher Boilerplate Template
```python
from typing import List, Optional
import os
from bs4 import BeautifulSoup

from src.config import ContentSource
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.utils.logger import get_logger

class CustomFetcher(BaseFetcher):
    """Your Custom Fetcher Description"""
    
    # 1. Declare the plugin type name, source input placeholder, config editor schema, and required secrets
    type_name = "custom_type"
    src_placeholder = "placeholder text for the source field in config-editor"
    config_schema = {
        # Schema dictionary describing custom fields for config-editor.html.
        # Supported input types: 'text', 'number', 'select', 'textarea'.
        # Use dot notation (e.g. 'metadata.xyz') to place the field inside the metadata block.
        "metadata.custom_param": {
            "type": "text",
            "label": "Custom Parameter",
            "placeholder": "Enter value..."
        }
    }
    required_secrets = ["CUSTOM_API_KEY"]

    def __init__(self, source: ContentSource, global_limit: int = 15, max_retries: int = 3):
        super().__init__(source, global_limit=global_limit, max_retries=max_retries)
        self.api_key = os.environ.get("CUSTOM_API_KEY")

    def fetch(self) -> FetchResult:
        """
        Execute fetch operation.
        """
        result = FetchResult(source=self.source, articles=[])
        
        try:
            # 2. Get custom parameters from self.source.metadata
            metadata = self.source.metadata or {}
            custom_param = metadata.get("custom_param", "default_val")

            # 3. Call API or fetch page
            url = self.source.src
            # Use self.api_key for authentication if required
            response = self._make_request(url)
            html = response.text

            # 4. Parse content using BeautifulSoup/lxml
            soup = BeautifulSoup(html, "lxml")
            
            # Example parsing loop:
            # title = soup.find("h1").get_text()
            # content = str(soup.find("div", class_="content"))
            # images = self._extract_images(content)
            
            # 5. Populate and validate article
            article = Article(
                title="Example Article Title",
                content="<p>Example Article Body Content...</p>",
                url=url,
                images=[]
            )
            
            if not self._should_delete(article.title):
                result.articles.append(article)

            return result

        except Exception as e:
            self.logger.error(f"Custom fetch failed: {e}")
            result.success = False
            result.error = str(e)
            return result
```

### 5. Goal for the New Fetcher
Here are the specific requirements for the fetcher you need to write:
[INSERT YOUR SPECIFIC FETCHING REQUIREMENTS OR SITE NAME HERE]
```
