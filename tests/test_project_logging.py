"""project_logging 模块回归测试 — 日志禁用场景。"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.config import LogConfig
from uasset_read.project_logging import (
    current_log_run_id,
    project_logging_session,
)


class TestDisabledLogSession:
    """project_logging_session() 在日志禁用时应返回无操作会话而非抛异常。"""

    def test_level_off_does_not_raise(self):
        """level='off' 时 project_logging_session() 应正常返回。"""
        session = project_logging_session(enabled=False, level="off")
        assert session is not None
        session.close()

    def test_enabled_false_does_not_raise(self):
        """enabled=False 时 project_logging_session() 应正常返回。"""
        session = project_logging_session(enabled=False)
        assert session is not None
        session.close()

    def test_disabled_session_no_run_id(self):
        """禁用会话期间 current_log_run_id() 应保持 None。"""
        session = project_logging_session(enabled=False, level="off")
        assert current_log_run_id() is None
        session.close()

    def test_disabled_session_no_log_file(self, tmp_path: Path):
        """禁用会话不应创建项目日志文件。"""
        log_dir = tmp_path / "log"
        session = project_logging_session(
            enabled=False, level="off", log_dir=str(log_dir)
        )
        session.close()
        assert not log_dir.exists() or not list(log_dir.glob("*.log"))

    def test_disabled_session_context_manager(self):
        """禁用会话应支持 with 语句。"""
        with project_logging_session(enabled=False, level="off") as session:
            assert session is not None
            assert current_log_run_id() is None

    def test_disabled_session_releases_lock(self):
        """禁用会话退出后 _scope_lock 应被释放，允许后续正常会话。"""
        session1 = project_logging_session(enabled=False, level="off")
        session1.close()
        # 第二次调用不应抛出"A project logging session is already active"
        session2 = project_logging_session(enabled=False, level="off")
        session2.close()

    def test_logconfig_level_off_via_scoped(self, tmp_path: Path):
        """LogConfig(level='off') 经 scoped_project_logging 包装不应抛出日志禁用异常。"""
        from uasset_read.core import parse_single

        config = LogConfig(level="off")
        # 关键：不抛出 RuntimeError("Project logging is disabled")
        parse_single(str(tmp_path / "nonexistent.uasset"), log_config=config)

    def test_logconfig_enabled_false_via_scoped(self, tmp_path: Path):
        """LogConfig(enabled=False) 经 scoped_project_logging 包装不应抛出日志禁用异常。"""
        from uasset_read.core import parse_single

        config = LogConfig(enabled=False)
        parse_single(str(tmp_path / "nonexistent.uasset"), log_config=config)
