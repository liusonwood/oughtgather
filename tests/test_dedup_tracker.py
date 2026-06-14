"""
去重追踪器测试
测试 DedupTracker 的加载、标记、保存和统计行为
"""

import os
import pytest

from src.dedup.tracker import DedupTracker


# =========================================================================
# 基本功能测试
# =========================================================================

class TestDedupTrackerBasic:
    """DedupTracker 基本功能测试"""

    def test_new_tracker_empty(self, tmp_dir):
        """新建 tracker 时 fetched_ids 为空"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)
        assert tracker.fetched_ids == set()
        assert tracker.new_ids == set()

    def test_mark_as_fetched(self, tmp_dir):
        """标记为已抓取后 is_fetched 返回 True"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)

        assert tracker.is_fetched("https://example.com", "标题") is False

        tracker.mark_as_fetched("https://example.com", "标题")

        assert tracker.is_fetched("https://example.com", "标题") is True

    def test_mark_same_url_different_title(self, tmp_dir):
        """相同 URL 不同标题视为不同内容"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)

        tracker.mark_as_fetched("https://example.com", "标题A")
        assert tracker.is_fetched("https://example.com", "标题A") is True
        assert tracker.is_fetched("https://example.com", "标题B") is False

    def test_mark_same_url_no_title(self, tmp_dir):
        """URL 相同且都不带标题视为相同内容"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)

        tracker.mark_as_fetched("https://example.com")
        assert tracker.is_fetched("https://example.com") is True

    def test_new_ids_tracked(self, tmp_dir):
        """mark_as_fetched 同时记录到 new_ids"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)

        tracker.mark_as_fetched("https://example.com/a", "A")
        tracker.mark_as_fetched("https://example.com/b", "B")

        assert len(tracker.new_ids) == 2

    def test_mark_already_fetched_not_in_new_ids(self, tmp_dir):
        """重复标记已抓取的内容不会加入 new_ids"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)

        tracker.mark_as_fetched("https://example.com", "标题")
        tracker.mark_as_fetched("https://example.com", "标题")  # 重复

        assert len(tracker.new_ids) == 1


# =========================================================================
# 持久化测试
# =========================================================================

class TestDedupTrackerPersistence:
    """DedupTracker 持久化测试"""

    def test_save_and_reload(self, tmp_dir):
        """保存后重新加载能恢复记录"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")

        # 第一次：标记并保存
        tracker1 = DedupTracker(data_file)
        tracker1.mark_as_fetched("https://example.com/a", "A")
        tracker1.mark_as_fetched("https://example.com/b", "B")
        tracker1.save()

        # 第二次：重新加载
        tracker2 = DedupTracker(data_file)
        assert tracker2.is_fetched("https://example.com/a", "A") is True
        assert tracker2.is_fetched("https://example.com/b", "B") is True
        assert tracker2.is_fetched("https://example.com/c", "C") is False

    def test_save_appends_not_overwrites(self, tmp_dir):
        """save 是追加模式，不覆盖已有记录"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")

        # 第一次保存
        tracker1 = DedupTracker(data_file)
        tracker1.mark_as_fetched("https://example.com/a", "A")
        tracker1.save()

        # 第二次保存
        tracker2 = DedupTracker(data_file)
        tracker2.mark_as_fetched("https://example.com/b", "B")
        tracker2.save()

        # 验证两条记录都存在
        tracker3 = DedupTracker(data_file)
        assert tracker3.is_fetched("https://example.com/a", "A") is True
        assert tracker3.is_fetched("https://example.com/b", "B") is True

    def test_save_no_new_ids_is_noop(self, tmp_dir):
        """没有新记录时 save 不写入文件"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)
        tracker.save()
        assert not os.path.exists(data_file)

    def test_creates_directory_if_missing(self, tmp_dir):
        """保存时自动创建目录"""
        data_file = os.path.join(tmp_dir, "subdir", "fetched_urls.txt")
        tracker = DedupTracker(data_file)
        tracker.mark_as_fetched("https://example.com", "标题")
        tracker.save()
        assert os.path.exists(data_file)

    def test_load_missing_file(self, tmp_dir):
        """加载不存在的文件不报错"""
        data_file = os.path.join(tmp_dir, "nonexistent.txt")
        tracker = DedupTracker(data_file)
        assert len(tracker.fetched_ids) == 0


# =========================================================================
# 统计与清理测试
# =========================================================================

class TestDedupTrackerStats:
    """DedupTracker 统计与清理测试"""

    def test_get_stats(self, tmp_dir):
        """get_stats 返回正确统计"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)

        tracker.mark_as_fetched("https://example.com/a", "A")
        tracker.mark_as_fetched("https://example.com/b", "B")

        stats = tracker.get_stats()
        assert stats["total_fetched"] == 2
        assert stats["new_fetched"] == 2

    def test_get_stats_after_reload(self, tmp_dir):
        """重新加载后 new_fetched 为 0"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")

        tracker1 = DedupTracker(data_file)
        tracker1.mark_as_fetched("https://example.com", "标题")
        tracker1.save()

        tracker2 = DedupTracker(data_file)
        stats = tracker2.get_stats()
        assert stats["total_fetched"] == 1
        assert stats["new_fetched"] == 0

    def test_clear_new_ids(self, tmp_dir):
        """clear_new_ids 清空 new_ids 但保留 fetched_ids"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        tracker = DedupTracker(data_file)

        tracker.mark_as_fetched("https://example.com", "标题")
        assert len(tracker.new_ids) == 1

        tracker.clear_new_ids()
        assert len(tracker.new_ids) == 0
        assert len(tracker.fetched_ids) == 1  # fetched_ids 不受影响
