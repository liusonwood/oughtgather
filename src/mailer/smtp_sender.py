"""
SMTP 发送器模块
负责将 EPUB 文件发送到 Kindle
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from src.config import get_smtp_config
from src.utils.logger import get_logger


class SMTPSender:
    """SMTP 发送器"""

    def __init__(self):
        """初始化 SMTP 发送器"""
        self.logger = get_logger()
        self.config = get_smtp_config()

    def send_epub(self, epub_path: str, subject: str = None) -> bool:
        """
        发送 EPUB 文件

        Args:
            epub_path: EPUB 文件路径
            subject: 邮件主题

        Returns:
            bool: 是否发送成功
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(epub_path):
                self.logger.error(f"EPUB file not found: {epub_path}")
                return False

            # 构造邮件主题
            if not subject:
                filename = os.path.basename(epub_path)
                subject = f"New EPUB: {filename}"

            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.config['username']
            msg['To'] = self.config['kindle_email']
            msg['Subject'] = subject

            # 添加邮件正文
            body = "Please find the attached EPUB file."
            msg.attach(MIMEText(body, 'plain'))

            # 添加附件
            self._attach_file(msg, epub_path)

            # 发送邮件
            self._send_mail(msg)

            self.logger.info(f"EPUB sent successfully to {self.config['kindle_email']}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send EPUB: {e}")
            return False

    def _attach_file(self, msg: MIMEMultipart, file_path: str):
        """
        添加附件

        Args:
            msg: 邮件对象
            file_path: 文件路径
        """
        filename = os.path.basename(file_path)

        # 创建附件
        with open(file_path, 'rb') as f:
            attachment = MIMEBase('application', 'octet-stream')
            attachment.set_payload(f.read())

        # 编码附件
        encoders.encode_base64(attachment)

        # 添加附件头（使用关键字参数以支持非 ASCII 文件名的 RFC 2231 编码）
        attachment.add_header(
            'Content-Disposition', 'attachment',
            filename=filename
        )

        msg.attach(attachment)

    def _send_mail(self, msg: MIMEMultipart):
        """
        发送邮件

        Args:
            msg: 邮件对象
        """
        host = self.config['host']
        port = self.config['port']
        username = self.config['username']
        password = self.config['password']

        # 根据端口选择连接方式
        if port == 465:
            # SSL
            self.logger.info(f"Connecting to SMTP server {host}:{port} (SSL)")
            with smtplib.SMTP_SSL(host, port) as server:
                server.login(username, password)
                server.send_message(msg)
        else:
            # TLS
            self.logger.info(f"Connecting to SMTP server {host}:{port} (TLS)")
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)

        self.logger.info("Email sent successfully")
