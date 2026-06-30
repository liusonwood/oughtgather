import os
from typing import List, Optional
from bs4 import BeautifulSoup
import httpx

from src.config import ContentSource
from src.fetchers.base import BaseFetcher, FetchResult, Article
from src.utils.logger import get_logger

class RaindropFetcher(BaseFetcher):
    """Raindrop.io Fetcher"""
    
    type_name = "raindropio"
    src_placeholder = "Enter Raindropio collection ID (e.g., 1234567, or 0 for Unsorted)"
    config_schema = {
        "full_text": {
            "type": "select",
            "label": "全文提取",
            "options": ["", "N", "Y"],
            "hint": "Raindropio 有效"
        }
    }
    required_secrets = {
        "RAINDROPIO_API_KEY": "Raindrop.io 的 API 访问密钥。"
    }

    def __init__(self, source: ContentSource, global_limit: int = 15, max_retries: int = 3):
        super().__init__(source, global_limit=global_limit, max_retries=max_retries)
        api_key = os.environ.get("RAINDROPIO_API_KEY")
        if not api_key:
            raise ValueError(
                "Required secret 'RAINDROPIO_API_KEY' is not set. "
                "Please add it to GitHub Secrets or environment variables."
            )
        self.api_key = api_key

    def fetch(self) -> FetchResult:
        """
        Execute fetch operation from Raindrop.io.
        """
        result = FetchResult(source=self.source, articles=[])
        
        try:
            # Use source.src as collection ID
            collection_id = self.source.src
            
            # Raindrop API URL
            url = f"https://api.raindrop.io/rest/v1/raindrops/{collection_id}"
            
            # API Request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Using base fetcher's request method
            response = self._make_request(url, headers=headers)
            data = response.json()
            
            if not data.get("result"):
                raise Exception(f"Raindropio API error: {data.get('message', 'Unknown error')}")
                
            raindrops = data.get("items", [])
            
            # Process articles
            for item in raindrops[:self.global_limit]:
                title = item.get("title")
                url = item.get("link")
                excerpt = item.get("excerpt", "")
                
                # Check for full text if requested
                content = None
                if self.source.full_text == "Y":
                    content, _ = self._fetch_full_text(url)
                
                if not content:
                    # Fallback to excerpt
                    content = f"<p>{excerpt}</p>"
                
                # Check for images
                images = []
                if item.get("cover"):
                    images.append(item.get("cover"))
                    
                article = Article(
                    title=title,
                    content=content,
                    url=url,
                    images=images
                )
                
                if not self._should_delete(article.title):
                    result.articles.append(article)

            return result

        except Exception as e:
            self.logger.error(f"Raindropio fetch failed: {e}")
            result.success = False
            result.error = str(e)
            return result
