import pytest
from unittest.mock import MagicMock, patch
import os
from src.mailer.smtp_sender import SMTPSender

@pytest.fixture
def smtp_config():
    return {
        "host": "smtp.example.com",
        "port": 587,
        "username": "user@example.com",
        "password": "password",
        "kindle_email": "kindle@example.com"
    }

@patch("src.mailer.smtp_sender.get_smtp_config")
def test_send_epub_success_tls(mock_get_config, smtp_config, tmp_path):
    mock_get_config.return_value = smtp_config
    
    # Create a dummy epub file
    epub_file = tmp_path / "test.epub"
    epub_file.write_text("dummy content")
    
    sender = SMTPSender()
    
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        result = sender.send_epub(str(epub_file))
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_with("user@example.com", "password")
        mock_server.send_message.assert_called_once()

@patch("src.mailer.smtp_sender.get_smtp_config")
def test_send_epub_success_ssl(mock_get_config, smtp_config, tmp_path):
    smtp_config["port"] = 465
    mock_get_config.return_value = smtp_config
    
    # Create a dummy epub file
    epub_file = tmp_path / "test.epub"
    epub_file.write_text("dummy content")
    
    sender = SMTPSender()
    
    with patch("smtplib.SMTP_SSL") as mock_smtp_ssl:
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server
        
        result = sender.send_epub(str(epub_file))
        
        assert result is True
        # SMTP_SSL handles SSL connection automatically
        mock_server.login.assert_called_with("user@example.com", "password")
        mock_server.send_message.assert_called_once()

@patch("src.mailer.smtp_sender.get_smtp_config")
def test_send_epub_file_not_found(mock_get_config, smtp_config):
    mock_get_config.return_value = smtp_config
    sender = SMTPSender()
    
    result = sender.send_epub("non_existent.epub")
    assert result is False

@patch("src.mailer.smtp_sender.get_smtp_config")
def test_send_epub_failure(mock_get_config, smtp_config, tmp_path):
    mock_get_config.return_value = smtp_config
    
    epub_file = tmp_path / "test.epub"
    epub_file.write_text("dummy content")
    
    sender = SMTPSender()
    
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = Exception("SMTP Connection Failed")
        
        result = sender.send_epub(str(epub_file))
        
        assert result is False
