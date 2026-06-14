#!/usr/bin/env python3
"""
Ought Gather 主入口
自动化信息聚合工具
"""

import sys
import os
from typing import List

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import load_config, Config, ContentSource
from src.fetchers.base import BaseFetcher, FetchResult
from src.fetchers.mail_fetcher import MailFetcher
from src.fetchers.rss_fetcher import RSSFetcher
from src.fetchers.web_fetcher import WebFetcher
from src.fetchers.trending_fetcher import TrendingFetcher
from src.processors.content_processor import ContentProcessor
from src.dedup.tracker import DedupTracker
from src.epub.generator import EPUBGenerator
from src.mailer.smtp_sender import SMTPSender
from src.utils.logger import get_logger


def get_fetcher(source: ContentSource) -> BaseFetcher:
    """
    根据数据源类型获取对应的抓取器

    Args:
        source: 内容源配置

    Returns:
        BaseFetcher: 抓取器实例
    """
    fetcher_map = {
        "mail": MailFetcher,
        "rss": RSSFetcher,
        "web": WebFetcher,
        "trending": TrendingFetcher
    }

    fetcher_class = fetcher_map.get(source.type)
    if not fetcher_class:
        raise ValueError(f"Unknown source type: {source.type}")

    return fetcher_class(source)


def process_results(results: List[FetchResult], tracker: DedupTracker) -> List[FetchResult]:
    """
    处理抓取结果（去重、内容处理）

    Args:
        results: 抓取结果列表
        tracker: 去重追踪器

    Returns:
        List[FetchResult]: 处理后的结果列表
    """
    logger = get_logger()
    processed_results = []

    for result in results:
        if not result.success:
            logger.warning(f"Skipping failed source: {result.source.src}")
            processed_results.append(result)
            continue

        # 过滤已抓取的文章（trending/web 使用带日期的哈希，每日刷新）
        original_count = len(result.articles)
        new_articles = []
        for article in result.articles:
            if not tracker.is_fetched(article.url, article.title, article.published_date):
                # 只要读取就标记为已处理，无论后续处理是否成功
                tracker.mark_as_fetched(article.url, article.title, article.published_date)

                # 应用内容处理规则，处理失败则保留原文
                try:
                    processor = ContentProcessor(result.source)
                    article = processor.process(article)
                except Exception as e:
                    logger.error(
                        f"Failed to process article '{article.title}': {e}, "
                        f"keeping original content"
                    )
                new_articles.append(article)
            else:
                logger.debug(f"Skipping already fetched: {article.title}")

        # 更新结果
        result.articles = new_articles
        processed_results.append(result)

        logger.info(
            f"Processed {result.source.type}: {len(new_articles)}/{original_count} new articles"
        )

    return processed_results


def has_new_content(results: List[FetchResult]) -> bool:
    """
    检查是否有新内容

    Args:
        results: 抓取结果列表

    Returns:
        bool: 是否有新内容
    """
    return any(result.success and len(result.articles) > 0 for result in results)


def main():
    """主函数"""
    logger = get_logger()

    logger.info("=" * 60)
    logger.info("Ought Gather - Starting")
    logger.info("=" * 60)

    try:
        # 1. 加载配置
        logger.info("Loading configuration...")
        config = load_config()
        logger.info(f"Loaded {len(config.body)} content sources")

        # 2. 初始化去重追踪器
        logger.info("Initializing dedup tracker...")
        tracker = DedupTracker()

        # 3. 抓取内容
        logger.info("Fetching content...")
        results = []
        error_log = []

        for source in config.body:
            try:
                fetcher = get_fetcher(source)
                result = fetcher.fetch_with_retry()
                results.append(result)

                if not result.success:
                    error_log.append(f"[{source.type}] {source.src}: {result.error}")

            except Exception as e:
                logger.error(f"Failed to fetch {source.src}: {e}")
                error_log.append(f"[{source.type}] {source.src}: {str(e)}")

        # 4. 处理结果（去重、内容处理）
        logger.info("Processing results...")
        processed_results = process_results(results, tracker)

        # 5. 检查是否有新内容
        if not has_new_content(processed_results):
            logger.info("No new content found. Exiting without generating EPUB.")
            return

        # 6. 生成 EPUB
        logger.info("Generating EPUB...")
        epub_generator = EPUBGenerator(config)
        epub_path = epub_generator.generate(processed_results, error_log)

        # 7. 发送邮件
        logger.info("Sending EPUB to Kindle...")
        try:
            sender = SMTPSender()
            subject = config.title.get_plain_text()
            sender.send_epub(epub_path, subject)
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            error_log.append(f"Email sending failed: {str(e)}")

        # 8. 保存去重记录
        logger.info("Saving dedup records...")
        tracker.save()

        # 9. 输出统计信息
        stats = tracker.get_stats()
        logger.info("=" * 60)
        logger.info("Ought Gather - Completed")
        logger.info(f"Total fetched: {stats['total_fetched']}")
        logger.info(f"New content: {stats['new_fetched']}")
        logger.info(f"EPUB: {epub_path}")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
