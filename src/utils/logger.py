"""
日志系统模块
提供统一的日志记录功能
"""

import logging
import os
from datetime import datetime
from typing import Optional


class Logger:
    """日志记录器"""

    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化日志系统"""
        # 创建日志目录
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)

        # 生成日志文件名
        log_file = os.path.join(
            log_dir,
            f"gather_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )

        # 配置日志格式
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

        # 创建日志记录器
        self._logger = logging.getLogger("ought_gather")
        self._logger.setLevel(logging.DEBUG)

        # 避免重复添加 handler
        if not self._logger.handlers:
            # 文件 handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(log_format, date_format)
            file_handler.setFormatter(file_formatter)
            self._logger.addHandler(file_handler)

            # 控制台 handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(log_format, date_format)
            console_handler.setFormatter(console_formatter)
            self._logger.addHandler(console_handler)

    def get_logger(self) -> logging.Logger:
        """获取日志记录器"""
        return self._logger


def get_logger() -> logging.Logger:
    """获取全局日志记录器"""
    return Logger().get_logger()


# 便捷函数
def debug(message: str):
    """记录 DEBUG 级别日志"""
    get_logger().debug(message)


def info(message: str):
    """记录 INFO 级别日志"""
    get_logger().info(message)


def warning(message: str):
    """记录 WARNING 级别日志"""
    get_logger().warning(message)


def error(message: str):
    """记录 ERROR 级别日志"""
    get_logger().error(message)


def critical(message: str):
    """记录 CRITICAL 级别日志"""
    get_logger().critical(message)


def exception(message: str):
    """记录异常日志"""
    get_logger().exception(message)
