import pytest
from unittest.mock import MagicMock, patch
import os
from src.uploader.webdav_uploader import WebDavUploader
from src.config import WebDavConfig

@patch("src.uploader.webdav_uploader.get_webdav_config")
@patch("httpx.put")
def test_webdav_uploader_success(mock_put, mock_get_config):
    # Mock config
    config = WebDavConfig(
        enabled=True,
        url="http://webdav.test",
        username="user",
        password="password",
        remote_path="/test"
    )
    mock_get_config.return_value = config
    
    # Mock response
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_put.return_value = mock_response
    
    uploader = WebDavUploader()
    
    # Create a dummy file
    epub_path = "test.epub"
    with open(epub_path, "w") as f:
        f.write("content")
    
    try:
        result = uploader.upload_epub(epub_path)
        assert result is True
        mock_put.assert_called_once()
    finally:
        if os.path.exists(epub_path):
            os.remove(epub_path)

@patch("src.uploader.webdav_uploader.get_webdav_config")
def test_webdav_uploader_disabled(mock_get_config):
    mock_get_config.return_value = WebDavConfig(enabled=False)
    uploader = WebDavUploader()
    result = uploader.upload_epub("test.epub")
    assert result is False
