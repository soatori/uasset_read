"""日志系统集成测试。"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest


class TestLoggingIntegration:
    """端到端日志系统测试。"""

    def test_full_logging_workflow(self, tmp_path):
        """完整的日志工作流：配置 -> 写入 -> 轮转 -> 清理。"""
        from uasset_read.project_logging import (
            configure_project_logging,
            _reset_logging_state_for_tests,
        )

        _reset_logging_state_for_tests()

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        # 创建多个旧日志文件
        for i in range(10):
            old_log = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            old_log.write_text(f"old log content {i}")

        # 配置日志，启用自动清理（使用 cleanup + keep_latest 参数）
        _log_path = configure_project_logging(
            project_root=tmp_path,
            log_dir=log_dir,
            max_bytes=1024,  # 1KB 触发轮转
            backup_count=2,
            cleanup=True,
            keep_latest=3,
        )

        # 验证旧日志被清理（保留最新 3 个 + 新日志）
        log_files = list(log_dir.glob("uasset_read-*.log*"))
        assert len(log_files) <= 4  # 3 个旧日志 + 1 个新日志

        # 写入足够多的日志触发轮转
        logger = logging.getLogger("uasset_read")
        for _ in range(100):
            logger.info("test message " * 50)

        # 验证轮转发生
        log_files = list(log_dir.glob("uasset_read-*.log*"))
        assert len(log_files) >= 2  # 至少有主日志 + 1 个备份

        _reset_logging_state_for_tests()

    def test_log_level_override(self, tmp_path):
        """验证日志级别正确传递。"""
        from uasset_read.project_logging import configure_project_logging, _reset_logging_state_for_tests

        _reset_logging_state_for_tests()

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        configure_project_logging(
            project_root=tmp_path,
            log_dir=log_dir,
            level="WARNING",
        )

        logger = logging.getLogger("uasset_read")
        handler = logger.handlers[0]
        assert handler.level == logging.WARNING

        _reset_logging_state_for_tests()

    def test_cleanup_project_logs_function(self, tmp_path):
        """验证 cleanup_project_logs 函数工作正常。"""
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        # 创建不同时间的日志文件
        for i in range(5):
            log_file = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            log_file.write_text(f"log content {i}")
            # 设置不同的修改时间
            mtime = datetime.now() - timedelta(days=i)
            os.utime(log_file, (mtime.timestamp(), mtime.timestamp()))

        # 测试 keep_latest
        planned = cleanup_project_logs(
            log_dir=log_dir,
            keep_latest=2,
            dry_run=True,
        )
        assert len(planned) == 3  # 应该保留最新 2 个

        # 测试 older_than_days
        planned = cleanup_project_logs(
            log_dir=log_dir,
            older_than_days=2,
            dry_run=True,
        )
        assert len(planned) >= 2  # 应该删除超过 2 天的文件

    def test_cleanup_dry_run_no_deletion(self, tmp_path):
        """验证 dry_run 模式不会删除任何文件。"""
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        for i in range(3):
            log_file = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            log_file.write_text(f"log content {i}")

        planned = cleanup_project_logs(
            log_dir=log_dir,
            keep_latest=0,  # 标记全部删除
            dry_run=True,
        )
        assert len(planned) == 2

        # 文件应仍然存在
        remaining = list(log_dir.glob("uasset_read-*.log*"))
        assert len(remaining) == 3

    def test_cleanup_real_deletion(self, tmp_path):
        """验证 dry_run=False 确实删除文件。"""
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        for i in range(3):
            log_file = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            log_file.write_text(f"log content {i}")

        cleanup_project_logs(
            log_dir=log_dir,
            keep_latest=1,  # 只保留最新 1 个
            dry_run=False,
        )

        remaining = list(log_dir.glob("uasset_read-*.log*"))
        assert len(remaining) == 1

    def test_cleanup_nonexistent_dir(self, tmp_path):
        """验证清理不存在的目录不会报错。"""
        from uasset_read.project_logging import cleanup_project_logs

        result = cleanup_project_logs(
            log_dir=tmp_path / "nonexistent",
            keep_latest=1,
            dry_run=True,
        )
        assert result == []

    def test_cleanup_keeps_or_deletes_complete_run_families(self, tmp_path):
        from uasset_read.project_logging import cleanup_project_logs

        log_dir = tmp_path / "log"
        log_dir.mkdir()
        old_base = log_dir / "uasset_read-20260101-000000-000000-pid1-old.log"
        old_backup = log_dir / f"{old_base.name}.1"
        new_base = log_dir / "uasset_read-20260102-000000-000000-pid1-new.log"
        old_base.write_text("old")
        old_backup.write_text("old backup")
        new_base.write_text("new")
        old_time = (datetime.now() - timedelta(days=2)).timestamp()
        new_time = (datetime.now() - timedelta(days=1)).timestamp()
        os.utime(old_base, (old_time, old_time))
        newest_time = datetime.now().timestamp()
        os.utime(old_backup, (newest_time, newest_time))
        os.utime(new_base, (new_time, new_time))

        planned = cleanup_project_logs(
            log_dir=log_dir,
            keep_latest=1,
            dry_run=True,
        )

        assert set(planned) == {new_base}

    def test_cleanup_never_selects_active_run_family(self, tmp_path):
        from uasset_read.project_logging import (
            _reset_logging_state_for_tests,
            cleanup_project_logs,
            configure_project_logging,
        )

        log_dir = tmp_path / "log"
        active = configure_project_logging(log_dir=log_dir, run_id="active")
        try:
            planned = cleanup_project_logs(
                log_dir=log_dir,
                keep_latest=0,
                max_total_bytes=0,
                dry_run=True,
            )
            assert active not in planned
        finally:
            _reset_logging_state_for_tests()
