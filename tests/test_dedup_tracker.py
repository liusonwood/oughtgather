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


# =========================================================================
# 自动清理测试
# =========================================================================

class TestDedupTrackerCleanup:
    """DedupTracker 超过上限自动清理测试"""

    def test_no_cleanup_when_under_max(self, tmp_dir, monkeypatch):
        """未达到上限时不触发清理"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        monkeypatch.setattr(DedupTracker, 'MAX_RECORDS', 5)

        tracker = DedupTracker(data_file)
        for i in range(3):
            tracker.mark_as_fetched(f"https://example.com/{i}", f"T{i}")
        tracker.save()

        with open(data_file) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 3

    def test_no_cleanup_at_exact_max(self, tmp_dir, monkeypatch):
        """恰好等于上限时不触发清理"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        monkeypatch.setattr(DedupTracker, 'MAX_RECORDS', 3)

        tracker = DedupTracker(data_file)
        for i in range(3):
            tracker.mark_as_fetched(f"https://example.com/{i}", f"T{i}")
        tracker.save()

        with open(data_file) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 3

    def test_cleanup_when_exceeds_max(self, tmp_dir, monkeypatch):
        """超过上限时自动清理，保留最新的记录"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        monkeypatch.setattr(DedupTracker, 'MAX_RECORDS', 5)

        # 预先写入 5 条旧记录（直接写文件，模拟历史数据）
        with open(data_file, 'w') as f:
            for i in range(5):
                f.write(f"old_{i}\n")

        tracker = DedupTracker(data_file)
        assert len(tracker.fetched_ids) == 5

        # 新增 3 条，总数 8 > 5，应触发清理
        for i in range(3):
            tracker.mark_as_fetched(f"https://example.com/new_{i}", f"N{i}")
        tracker.save()

        # 文件应只保留 5 条：最旧的 3 条被清理，留下 old_3、old_4 和 3 条新记录
        with open(data_file) as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 5
        assert "old_0" not in lines
        assert "old_1" not in lines
        assert "old_2" not in lines
        assert "old_3" in lines
        assert "old_4" in lines

        # 内存中的 set 同步更新
        assert len(tracker.fetched_ids) == 5
        assert "old_0" not in tracker.fetched_ids
        assert "old_3" in tracker.fetched_ids

    def test_cleanup_keeps_newest_in_order(self, tmp_dir, monkeypatch):
        """清理后文件中记录保持原有顺序（最新记录在末尾）"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        monkeypatch.setattr(DedupTracker, 'MAX_RECORDS', 3)

        # 写入 3 条历史数据
        with open(data_file, 'w') as f:
            f.write("aaa\nbbb\nccc\n")

        tracker = DedupTracker(data_file)
        tracker.mark_as_fetched("https://example.com/x", "X")
        tracker.mark_as_fetched("https://example.com/y", "Y")
        tracker.save()

        with open(data_file) as f:
            lines = [l.strip() for l in f if l.strip()]

        # 追加后为 [aaa, bbb, ccc, new1, new2]，保留末尾 3 条
        # 所以第一条是 ccc（旧记录中保留下来最晚的一条）
        assert lines[0] == "ccc"
        # 新追加的 2 条都在
        assert len(lines) == 3
        assert all(line not in ("aaa", "bbb") for line in lines)

    def test_cleanup_after_reload(self, tmp_dir, monkeypatch):
        """清理后重新加载，记录保持一致"""
        data_file = os.path.join(tmp_dir, "fetched_urls.txt")
        monkeypatch.setattr(DedupTracker, 'MAX_RECORDS', 3)

        # 第一次：写入 5 条，触发清理
        tracker1 = DedupTracker(data_file)
        for i in range(5):
            tracker1.mark_as_fetched(f"https://example.com/{i}", f"T{i}")
        tracker1.save()

        # 第二次：重新加载，应该只有 3 条
        tracker2 = DedupTracker(data_file)
        assert len(tracker2.fetched_ids) == 3
