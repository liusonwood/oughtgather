"""
抓取器模块的初始化文件
实现动态插件加载机制，自动扫描并注册所有抓取器
"""

import os
import importlib
import pkgutil

from src.fetchers.base import (
    BaseFetcher,
    FetchResult,
    Article,
    get_fetcher_class,
)

# 动态插件加载：自动导入当前包下的所有模块，触发 BaseFetcher.__init_subclass__ 注册机制
def _load_plugins():
    package_dir = os.path.dirname(__file__)
    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        if module_name not in ("base", "__init__"):
            importlib.import_module(f"src.fetchers.{module_name}")

_load_plugins()
