"""project_logging 模块测试 — 日志禁用场景。"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.config import LogConfig
from uasset_read.project_logging import (
    current_log_run_id,
    project_logging_session,
)


class TestDisabledLogSession:
    """project_logging_session() 在日志禁用时应返回无操作会话。"""

    def test_level_off_does_not_raise(self):
        """level='off' 和 enabled=False 均正常返回。"""
        session = project_logging_session(enabled=False, level="off")
        assert session is not None
        session.close()
        session2 = project_logging_session(enabled=False)
        assert session2 is not None
        session2.close()

    def test_disabled_session_no_run_id(self):
        """禁用会话 run_id=None；支持 with 语句。"""
        session = project_logging_session(enabled=False, level="off")
        assert current_log_run_id() is None
        session.close()
        with project_logging_session(enabled=False, level="off") as s:
            assert s is not None and current_log_run_id() is None

    def test_disabled_session_no_log_file(self, tmp_path: Path):
        """禁用会话不创建日志文件；释放锁允许后续会话。"""
        log_dir = tmp_path / "log"
        session = project_logging_session(enabled=False, level="off", log_dir=str(log_dir))
        session.close()
        assert not log_dir.exists() or not list(log_dir.glob("*.log"))
        s1 = project_logging_session(enabled=False, level="off"); s1.close()
        s2 = project_logging_session(enabled=False, level="off"); s2.close()

    def test_logconfig_level_off_via_scoped(self, tmp_path: Path):
        """LogConfig level='off'/enabled=False 不应抛出日志禁用异常。"""
        from uasset_read.core import parse_single
        parse_single(str(tmp_path / "nonexistent.uasset"), log_config=LogConfig(level="off"))
        parse_single(str(tmp_path / "nonexistent.uasset"), log_config=LogConfig(enabled=False))
