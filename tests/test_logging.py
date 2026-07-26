"""project_logging 模块测试 — 日志禁用场景。"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.config import LogConfig
from uasset_read.project_logging import (
    current_log_run_id,
    project_logging_session,
)

# Relative path to a known-good sample asset for integration-style tests.
_SAMPLE_ASSET = Path(__file__).resolve().parent / "samples" / "StackOBot_Enum_CameraState.uasset"


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


class TestDirectPackageLogConfig:
    """#448: parse_package() and parse_uasset_with_linker() must consume log_config."""

    def test_parse_package_level_off_no_log_file(self, tmp_path: Path):
        """LogConfig(level='off') must not create any log files."""
        from uasset_read.parse_uasset import parse_package

        log_dir = tmp_path / "logs_disabled"
        log_dir.mkdir()
        parse_package(
            str(_SAMPLE_ASSET),
            log_config=LogConfig(level="off", dir=str(log_dir)),
        )
        assert not list(log_dir.glob("*.log")), (
            "LogConfig(level='off') should not produce log files"
        )

    def test_parse_package_custom_dir_creates_log(self, tmp_path: Path):
        """LogConfig(dir=...) must route logs to the specified directory."""
        from uasset_read.parse_uasset import parse_package

        custom_dir = tmp_path / "my_logs"
        custom_dir.mkdir()
        parse_package(
            str(_SAMPLE_ASSET),
            log_config=LogConfig(dir=str(custom_dir)),
        )
        log_files = list(custom_dir.glob("*.log"))
        assert log_files, "LogConfig(dir=...) should create at least one log file"

    def test_parse_uasset_with_linker_level_off_no_log_file(self, tmp_path: Path):
        """LogConfig(level='off') must not create any log files."""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        log_dir = tmp_path / "logs_disabled"
        log_dir.mkdir()
        parse_uasset_with_linker(
            str(_SAMPLE_ASSET),
            log_config=LogConfig(level="off", dir=str(log_dir)),
        )
        assert not list(log_dir.glob("*.log")), (
            "LogConfig(level='off') should not produce log files"
        )

    def test_parse_uasset_with_linker_custom_dir_creates_log(self, tmp_path: Path):
        """LogConfig(dir=...) must route logs to the specified directory."""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        custom_dir = tmp_path / "my_logs"
        custom_dir.mkdir()
        parse_uasset_with_linker(
            str(_SAMPLE_ASSET),
            log_config=LogConfig(dir=str(custom_dir)),
        )
        log_files = list(custom_dir.glob("*.log"))
        assert log_files, "LogConfig(dir=...) should create at least one log file"


# ---------------------------------------------------------------------------
# Finding 1: Tests for logging features added in Task #421
# ---------------------------------------------------------------------------


class _FakeExport:
    """Minimal mock export with a parse_status and optional fallback_reason."""

    def __init__(self, status: str, fallback_reason: str | None = None):
        self.parse_status = status
        if fallback_reason is not None:
            self.fallback_reason = fallback_reason


class _FakeResult:
    """Minimal mock result with export_map, errors, warnings, diagnostics."""

    def __init__(
        self,
        *,
        status: str = "success",
        export_map=None,
        errors=None,
        warnings=None,
        diagnostics=None,
        diagnostics_dropped_count: int = 0,
    ):
        self._status = status
        self.export_map = export_map or []
        self.errors = errors or []
        self.warnings = warnings or []
        self.diagnostics = diagnostics or []
        self.diagnostics_dropped_count = diagnostics_dropped_count

    @property
    def status(self):
        return self._status


class TestCountExportCategories:
    """_count_export_categories correctly tallies export parse statuses."""

    def test_empty_export_map(self):
        from uasset_read.project_logging import _count_export_categories

        result = _FakeResult(export_map=[])
        cats = _count_export_categories(result)
        assert cats == {"fallback": 0, "opaque": 0, "recovery": 0}

    def test_all_success(self):
        from uasset_read.project_logging import _count_export_categories

        result = _FakeResult(
            export_map=[_FakeExport("success"), _FakeExport("success")]
        )
        cats = _count_export_categories(result)
        assert cats == {"fallback": 0, "opaque": 0, "recovery": 0}

    def test_mixed_statuses(self):
        from uasset_read.project_logging import _count_export_categories

        result = _FakeResult(
            export_map=[
                _FakeExport("success"),
                _FakeExport("partial", fallback_reason="unsupported_type"),
                _FakeExport("partial", fallback_reason="serial_scan_recovery"),
                _FakeExport("opaque"),
                _FakeExport("success"),
                _FakeExport("partial"),
            ]
        )
        cats = _count_export_categories(result)
        assert cats["fallback"] == 2  # two exports with fallback_reason set
        assert cats["opaque"] == 1    # one export with parse_status="opaque"
        assert cats["recovery"] == 1  # one of the fallbacks has "serial_scan" in reason

    def test_no_export_map(self):
        from uasset_read.project_logging import _count_export_categories

        class _NoExportMap:
            pass

        result = _NoExportMap()
        cats = _count_export_categories(result)
        assert cats == {"fallback": 0, "opaque": 0, "recovery": 0}


class TestLastParseResultLifecycle:
    """_last_parse_result ContextVar is set and read correctly."""

    def test_set_and_get(self):
        from uasset_read.project_logging import (
            set_last_parse_result,
            get_last_parse_result,
        )

        set_last_parse_result(None)
        assert get_last_parse_result() is None

        sentinel = _FakeResult(status="success")
        set_last_parse_result(sentinel)
        assert get_last_parse_result() is sentinel

        set_last_parse_result(None)
        assert get_last_parse_result() is None

    def test_default_is_none(self):
        from uasset_read.project_logging import get_last_parse_result

        assert get_last_parse_result() is None

    def test_set_with_various_types(self):
        from uasset_read.project_logging import (
            set_last_parse_result,
            get_last_parse_result,
        )

        for value in [42, "string", {"key": "val"}, [1, 2, 3]]:
            set_last_parse_result(value)
            assert get_last_parse_result() is value

        set_last_parse_result(None)


class TestAssetEndFormat:
    """asset_end log line includes parse_status and diagnostic counts."""

    def test_asset_end_contains_expected_fields(self, tmp_path: Path):
        """Verify scoped_project_logging emits asset_end with full diagnostic fields."""
        import logging
        from uasset_read.project_logging import (
            scoped_project_logging,
            set_last_parse_result,
            _reset_logging_state_for_tests,
        )

        _reset_logging_state_for_tests()
        captured: list[str] = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        pkg_logger = logging.getLogger("uasset_read")
        handler = _CaptureHandler()
        pkg_logger.addHandler(handler)
        pkg_logger.setLevel(logging.DEBUG)

        try:
            set_last_parse_result(None)

            @scoped_project_logging
            def _fake_parse(log_config=None, file_path="dummy.uasset", path=None):
                result = _FakeResult(
                    status="partial",
                    export_map=[
                        _FakeExport("success"),
                        _FakeExport("partial", fallback_reason="unsupported_type"),
                        _FakeExport("opaque"),
                    ],
                    errors=["err1"],
                    warnings=["warn1"],
                    diagnostics_dropped_count=0,
                )
                set_last_parse_result(result)
                return "output"

            _fake_parse(
                log_config=LogConfig(level="DEBUG", dir=str(tmp_path)),
                path="dummy.uasset",
            )

            asset_end_lines = [l for l in captured if "asset_end" in l]
            assert asset_end_lines, "No asset_end line found in logs"
            line = asset_end_lines[-1]
            assert "parse_status=partial" in line
            assert "exports=3" in line
            assert "fallback=1" in line
            assert "opaque=1" in line
            assert "errors=1" in line
            assert "warnings=1" in line
            assert "duration_ms=" in line
        finally:
            pkg_logger.removeHandler(handler)
            set_last_parse_result(None)
