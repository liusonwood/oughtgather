"""
WebDAV 上传器模块
"""
import os
import httpx
from src.config import get_webdav_config
from src.utils.logger import get_logger

class WebDavUploader:
    """WebDAV 上传器"""
    def __init__(self):
        self.logger = get_logger()
        self.config = get_webdav_config()

    def upload_epub(self, epub_path: str) -> bool:
        """上传 EPUB 文件"""
        if not self.config or not self.config.enabled:
            return False

        if not os.path.exists(epub_path):
            self.logger.error(f"EPUB file not found: {epub_path}")
            return False

        filename = os.path.basename(epub_path)
        # 简单拼接路径
        base_url = self.config.url.rstrip('/')
        remote_path = self.config.remote_path.lstrip('/')
        remote_url = f"{base_url}/{remote_path}/{filename}"
        
        try:
            self.logger.info(f"Uploading EPUB to {remote_url}...")
            with open(epub_path, 'rb') as f:
                # WebDAV PUT upload
                response = httpx.put(
                    remote_url,
                    content=f,
                    auth=(self.config.username, self.config.password),
                    timeout=30.0
                )
            response.raise_for_status()
            self.logger.info("EPUB uploaded successfully to WebDAV")
            return True
        except Exception as e:
            self.logger.error(f"Failed to upload EPUB to WebDAV: {e}")
            return False
