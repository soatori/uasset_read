"""Core 安全与日志测试 — 合并自 test_error_and_safety.py 和 test_logging.py。

覆盖：错误处理、内存安全、文件句柄、日志系统、project logging session。
"""
from __future__ import annotations

import ast
import gc
import importlib
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.exceptions import (
    UAssetError,
    DecompressionError,
    LinkerError,
    ParseError,
    VersionError,
)
from uasset_read.memory_safety import (
    MemoryLimitExceeded,
    MemoryMonitor,
    MemoryPolicy,
    ResourceLimits,
    cleanup_after_parse,
)


# ---------------------------------------------------------------------------
# 辅助类
# ---------------------------------------------------------------------------

class MockResult:
    def __init__(self):
        self.errors = []


class _FakeResult:
    """轻量 Mock，模拟 BaseResult/ParseResult 的必要字段。"""

    def __init__(self):
        self.errors: list[str] = []
        self.is_success: bool = True
        self.summary = None
        self.diagnostics: list = []
        self.graphs: list = []
        self._error_keys: set = set()


class _FakeArchive:
    """模拟 FArchive，为 _record_parse_stage_error 提供必要接口。"""

    def __init__(self, size: int = 1024, pos: int = 0):
        self._size = size
        self._pos = pos

    def total_size(self) -> int:
        return self._size

    def tell(self) -> int:
        return self._pos


# ===========================================================================
# 1. tolerant_parse — 基础行为
# ===========================================================================

def test_tolerant_parse_no_error():
    from uasset_read.core.error_handling import tolerant_parse
    result = MockResult()
    with tolerant_parse(result, "test"):
        pass
    assert result.errors == []


def test_tolerant_parse_with_error():
    from uasset_read.core.error_handling import tolerant_parse
    result = MockResult()
    with pytest.raises(ParseError):
        with tolerant_parse(result, "test"):
            raise ParseError("test error")
    assert len(result.errors) == 1
    assert "test error" in result.errors[0]


# ===========================================================================
# 2. tolerant_parse — 去重
# ===========================================================================

def test_tolerant_parse_dedup():
    """同一 ParseError 不会重复添加到 result.errors。"""
    from uasset_read.core.error_handling import tolerant_parse

    class _R:
        def __init__(self):
            self.errors: list[str] = []

    result = _R()
    with pytest.raises(ParseError):
        with tolerant_parse(result, "stage"):
            raise ParseError("dup error")

    assert len(result.errors) == 1, f"期望 1 条错误，实际 {len(result.errors)}: {result.errors}"

    with pytest.raises(ParseError):
        with tolerant_parse(result, "stage"):
            raise ParseError("dup error")

    assert len(result.errors) == 1, f"去重失败，期望仍为 1 条，实际 {len(result.errors)}"


# ===========================================================================
# 3. 异常类层次与行为
# ===========================================================================

@pytest.mark.parametrize("exc_cls", [DecompressionError, LinkerError])
class TestExceptionHierarchy:
    """DecompressionError / LinkerError 继承自 UAssetError，可 raise 和 catch。"""

    def test_inherits_from_uasset_error(self, exc_cls):
        assert issubclass(exc_cls, UAssetError)

    def test_is_exception(self, exc_cls):
        assert issubclass(exc_cls, Exception)

    def test_raise_and_catch(self, exc_cls):
        with pytest.raises(UAssetError):
            raise exc_cls("test message")

    def test_catch_as_exception(self, exc_cls):
        """也能被基类 Exception 捕获。"""
        with pytest.raises(Exception):
            raise exc_cls("test message")


def test_exceptions_importable_from_package():
    """异常类可直接从 uasset_read.exceptions 顶层导入。"""
    import uasset_read.exceptions as mod

    assert hasattr(mod, "DecompressionError")
    assert hasattr(mod, "LinkerError")
    assert hasattr(mod, "ParseError")
    assert hasattr(mod, "VersionError")
    assert hasattr(mod, "UAssetError")


# ===========================================================================
# 4. _handle_parse_error — 各异常分支
# ===========================================================================

class TestHandleParseError:
    """覆盖 _handle_parse_error 的六个分支。"""

    def _call(self, exc, result, tolerant=True):
        """在 except 上下文中调用 _handle_parse_error，模拟实际调用链。"""
        mod = importlib.import_module("uasset_read.parse_uasset")
        _handle_parse_error = mod._handle_parse_error
        archive = _FakeArchive()
        try:
            raise exc
        except Exception as caught:
            _handle_parse_error(caught, result, archive, "test.uasset", tolerant)

    def test_version_error_records_and_sets_failure(self):
        result = _FakeResult()
        self._call(VersionError("unsupported version"), result)

        assert result.is_success is False
        assert len(result.errors) > 0
        assert any("VersionError" in e for e in result.errors)

    def test_parse_error_extracts_partial_result(self):
        result = _FakeResult()
        partial = {"graphs": [{"name": "partial_graph"}]}
        exc = ParseError("parse failed", partial_result=partial)
        self._call(exc, result)

        assert result.is_success is False
        assert result.graphs == [{"name": "partial_graph"}]
        assert len(result.errors) > 0

    def test_parse_error_no_partial_result(self):
        result = _FakeResult()
        exc = ParseError("parse failed without partial")
        self._call(exc, result)

        assert result.is_success is False
        assert len(result.errors) > 0

    def test_memory_error_records_and_sets_failure(self):
        result = _FakeResult()
        self._call(MemoryError("out of memory"), result)

        assert result.is_success is False
        assert any("MemoryError" in e for e in result.errors)

    def test_unexpected_error_records_and_sets_failure(self):
        result = _FakeResult()
        self._call(RuntimeError("something broke"), result)

        assert result.is_success is False
        assert len(result.errors) > 0

    def test_memory_limit_exceeded_reraises(self):
        result = _FakeResult()
        exc = MemoryLimitExceeded(
            asset_path="test.uasset",
            stage="parse",
            current_rss_mb=2048.0,
            limit_mb=1024.0,
        )
        with pytest.raises(MemoryLimitExceeded):
            self._call(exc, result)
        assert result.errors == []
        assert result.is_success is True

    def test_not_tolerant_reraises(self):
        result = _FakeResult()
        exc = ParseError("fatal parse error")
        with pytest.raises(ParseError):
            self._call(exc, result, tolerant=False)
        assert result.is_success is False
        assert len(result.errors) > 0


# ===========================================================================
# 5. _record_parse_stage_error — 去重与诊断
# ===========================================================================

class TestRecordParseStageError:
    """覆盖 _record_parse_stage_error 的核心行为。"""

    def _call(self, result, archive=None, stage="parse", field="test", error=None):
        from uasset_read.parse_stages import _record_parse_stage_error
        if error is None:
            error = ValueError("test error")
        _record_parse_stage_error(result, archive, "test.uasset", stage, field, error)

    def test_first_error_adds_to_errors(self):
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, error=ValueError("first error"))

        assert len(result.errors) == 1
        assert "first error" in result.errors[0]
        assert result.is_success is False

    def test_duplicate_error_not_added(self):
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, error=ValueError("dup error"))
        self._call(result, archive, error=ValueError("dup error"))

        assert len(result.errors) == 1

    def test_different_errors_all_added(self):
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, error=ValueError("error A"))
        self._call(result, archive, error=ValueError("error B"))

        assert len(result.errors) == 2

    def test_always_appends_diagnostic(self):
        result = _FakeResult()
        archive = _FakeArchive(size=2048, pos=512)

        self._call(result, archive, error=ValueError("diagnostic test"))

        assert len(result.diagnostics) == 1
        diag = result.diagnostics[0]
        assert diag.kind == "parse_stage_error"
        assert diag.asset_path == "test.uasset"
        assert diag.module == "parse"
        assert diag.field == "test"
        assert diag.current_pos == 512
        assert diag.file_size == 2048
        assert diag.source == "_parse_package_core"
        assert "diagnostic test" in diag.error
        assert diag.fallback_used is True

    def test_diagnostic_added_even_for_duplicate_error(self):
        """去重不影响 diagnostic 记录——重复错误仍会产生新的 diagnostic。"""
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, error=ValueError("dup"))
        self._call(result, archive, error=ValueError("dup"))

        assert len(result.errors) == 1
        assert len(result.diagnostics) == 2

    def test_archive_none_handled(self):
        """archive 为 None 时不会崩溃。"""
        result = _FakeResult()
        self._call(result, archive=None, error=ValueError("no archive"))

        assert len(result.errors) == 1
        assert len(result.diagnostics) == 1

    def test_different_exception_types_same_message_not_filtered(self):
        """不同异常类型相同消息不应被误过滤（Issue #359 核心场景）。"""
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, stage="parse", error=ValueError("same message"))
        self._call(result, archive, stage="parse", error=ParseError("same message"))

        assert len(result.errors) == 2, (
            f"不同异常类型相同消息应保留两条，实际 {len(result.errors)}: {result.errors}"
        )

    def test_same_exception_different_stage_not_filtered(self):
        """相同异常类型和消息但不同阶段不应被误过滤。"""
        result = _FakeResult()
        archive = _FakeArchive()

        self._call(result, archive, stage="stage_a", error=ValueError("msg"))
        self._call(result, archive, stage="stage_b", error=ValueError("msg"))

        assert len(result.errors) == 2, (
            f"不同阶段相同错误应保留两条，实际 {len(result.errors)}: {result.errors}"
        )


# ===========================================================================
# 6. BaseResult._error_keys 正式字段
# ===========================================================================

class TestErrorKeysField:
    """验证 _error_keys 是 BaseResult 的正式字段而非动态属性。"""

    def test_error_keys_exists_on_base_result(self):
        from uasset_read.models.result import BaseResult

        result = BaseResult()
        assert hasattr(result, "_error_keys")
        assert isinstance(result._error_keys, set)
        assert len(result._error_keys) == 0

    def test_error_keys_exists_on_parse_result(self):
        from uasset_read.models.result import ParseResult

        result = ParseResult()
        assert hasattr(result, "_error_keys")
        assert isinstance(result._error_keys, set)

    def test_error_keys_tracks_unique_errors(self):
        from uasset_read.models.result import BaseResult

        result = BaseResult()
        key = ("ValueError", "read_header", "ValueError: invalid")
        result._error_keys.add(key)
        result._error_keys.add(key)

        assert len(result._error_keys) == 1

    def test_error_keys_different_types_not_filtered(self):
        from uasset_read.models.result import BaseResult

        result = BaseResult()
        key1 = ("ValueError", "stage", "ValueError: msg")
        key2 = ("TypeError", "stage", "TypeError: msg")

        result._error_keys.add(key1)
        result._error_keys.add(key2)

        assert len(result._error_keys) == 2


# ===========================================================================
# 文件句柄安全网
# ===========================================================================

class TestFileHandleSafetyNet:
    """验证文件处理类的 __del__ 安全网。"""

    def test_farchive_has_del_method(self):
        from uasset_read.archive import FArchive
        assert hasattr(FArchive, "__del__"), "FArchive 应有 __del__ 方法"

    def test_farchive_del_is_callable(self):
        from uasset_read.archive import FArchive
        assert callable(getattr(FArchive, "__del__", None)), "FArchive.__del__ 应是可调用的"

    def test_iostore_reader_has_del_method(self):
        from uasset_read.iostore.reader import IoStoreReader
        assert hasattr(IoStoreReader, "__del__"), "IoStoreReader 应有 __del__ 方法"

    def test_pak_file_reader_has_del_method(self):
        from uasset_read.pak.reader import PakFileReader
        assert hasattr(PakFileReader, "__del__"), "PakFileReader 应有 __del__ 方法"

    def test_del_method_implementation_pattern(self):
        """验证 __del__ 方法遵循正确的实现模式。"""
        archive_path = Path(__file__).parent.parent / "src" / "uasset_read" / "archive.py"
        source = archive_path.read_text(encoding="utf-8")

        assert "def __del__(self)" in source, "archive.py 应有 __del__ 方法"
        assert "self.close()" in source, "archive.py __del__ 应调用 self.close()"

        iostore_path = Path(__file__).parent.parent / "src" / "uasset_read" / "iostore" / "reader.py"
        source = iostore_path.read_text(encoding="utf-8")
        assert "def __del__(self)" in source, "iostore/reader.py 应有 __del__ 方法"

        pak_path = Path(__file__).parent.parent / "src" / "uasset_read" / "pak" / "reader.py"
        source = pak_path.read_text(encoding="utf-8")
        assert "def __del__(self)" in source, "pak/reader.py 应有 __del__ 方法"


# ===========================================================================
# 缓存重置
# ===========================================================================

class TestCacheResetMethods:
    """验证缓存重置方法。"""

    def test_class_handler_registry_reset_cache(self):
        from uasset_read.parsers.class_registry import ClassHandlerRegistry

        registry = ClassHandlerRegistry()

        mock_handler = MagicMock()
        mock_handler.can_handle.return_value = True
        mock_handler.handler_name = "TestHandler"

        registry.register(mock_handler)

        registry._cache["TestClass"] = mock_handler
        registry._cache["AnotherClass"] = None

        registry.reset_cache()

        assert len(registry._cache) == 0
        assert len(registry._handlers) == 1
        assert registry._handlers[0] is mock_handler


# ===========================================================================
# 循环引用清理
# ===========================================================================

class TestCircularReferenceCleanup:
    """验证循环引用清理逻辑。"""

    def test_parse_package_cleans_circular_references(self):
        """parse_package 应在 finally 块中清理循环引用。"""
        parse_uasset_path = Path(__file__).parent.parent / "src" / "uasset_read" / "parse_uasset.py"
        source = parse_uasset_path.read_text(encoding="utf-8")

        assert "obj.linker = None" in source, "parse_uasset.py 应在 finally 块中清理 linker 引用"
        assert "_export_objects.clear()" in source, "parse_uasset.py 应在 finally 块中清空 _export_objects"
        assert "_import_objects.clear()" in source, "parse_uasset.py 应在 finally 块中清空 _import_objects"


# ===========================================================================
# 大对象释放
# ===========================================================================

class TestLargeObjectCleanup:
    """验证大对象释放逻辑。"""

    def test_parse_single_releases_temp_attributes(self):
        """parse_single 应在 build_package_ir 后释放临时大对象。"""
        core_init_path = Path(__file__).parent.parent / "src" / "uasset_read" / "core" / "__init__.py"
        source = core_init_path.read_text(encoding="utf-8")

        assert "_asset_type_data" in source, "core/__init__.py 应释放 _asset_type_data"
        assert "_uclass_native_fields" in source, "core/__init__.py 应释放 _uclass_native_fields"
        assert "delattr" in source, "core/__init__.py 应使用 delattr 释放属性"


# ===========================================================================
# 上下文管理器
# ===========================================================================

class TestArchiveContextManager:
    """验证 Archive 类支持上下文管理器协议。"""

    def test_iostore_reader_has_context_manager(self):
        from uasset_read.iostore.reader import IoStoreReader

        assert hasattr(IoStoreReader, "__enter__"), "IoStoreReader 应有 __enter__ 方法"
        assert hasattr(IoStoreReader, "__exit__"), "IoStoreReader 应有 __exit__ 方法"

    def test_pak_file_reader_has_context_manager(self):
        from uasset_read.pak.reader import PakFileReader

        assert hasattr(PakFileReader, "__enter__"), "PakFileReader 应有 __enter__ 方法"
        assert hasattr(PakFileReader, "__exit__"), "PakFileReader 应有 __exit__ 方法"


# ===========================================================================
# Memory policy and monitoring
# ===========================================================================

@pytest.mark.parametrize(
    ("size_bytes", "rss_limit_mb", "timeout_seconds"),
    [
        (20 * 1024 * 1024, 1024, 120.0),
        (20 * 1024 * 1024 + 1, 2048, 180.0),
        (100 * 1024 * 1024, 2048, 180.0),
        (100 * 1024 * 1024 + 1, 4096, 300.0),
    ],
)
def test_default_policy_uses_file_size_tiers(
    size_bytes: int,
    rss_limit_mb: int,
    timeout_seconds: float,
) -> None:
    limits = MemoryPolicy().limits_for_size(size_bytes)
    assert limits == ResourceLimits(rss_limit_mb, timeout_seconds)


def test_policy_supports_custom_limits() -> None:
    policy = MemoryPolicy(
        small_limits=ResourceLimits(128, 10),
        medium_limits=ResourceLimits(256, 20),
        large_limits=ResourceLimits(512, 30),
        system_usage_limit=0.7,
        poll_interval_seconds=0.25,
    )

    assert policy.limits_for_size(1) == ResourceLimits(128, 10)
    assert policy.limits_for_size(50 * 1024 * 1024) == ResourceLimits(256, 20)
    assert policy.limits_for_size(200 * 1024 * 1024) == ResourceLimits(512, 30)
    assert policy.system_usage_limit == 0.7
    assert policy.poll_interval_seconds == 0.25


def test_memory_policy_types_are_public() -> None:
    from uasset_read import MemoryLimitExceeded as PublicError
    from uasset_read import MemoryPolicy as PublicPolicy
    from uasset_read import ResourceLimits as PublicLimits

    assert PublicPolicy is MemoryPolicy
    assert PublicLimits is ResourceLimits
    assert PublicError is MemoryLimitExceeded


def test_monitor_checkpoint_reports_stage_and_limit() -> None:
    monitor = MemoryMonitor(
        asset_path=Path("Content/Test.uasset"),
        limits=ResourceLimits(64, 30),
        rss_reader=lambda _pid=None: 65.5,
    )

    with pytest.raises(MemoryLimitExceeded) as exc_info:
        monitor.checkpoint("export_map")

    error = exc_info.value
    assert error.stage == "export_map"
    assert error.current_rss_mb == 65.5
    assert error.limit_mb == 64
    assert error.asset_path == "Content\\Test.uasset" or error.asset_path == "Content/Test.uasset"


def test_cleanup_after_parse_runs_one_gc_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr("uasset_read.memory_safety.gc.collect", lambda: calls.append(1))

    cleanup_after_parse()

    assert calls == [1]


def test_pytest_teardown_runs_one_gc_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests import conftest

    calls = []
    monkeypatch.setattr(conftest.gc, "collect", lambda: calls.append(1))

    conftest.pytest_runtest_teardown(None)

    assert calls == [1]


# ===========================================================================
# Resource safety — file handle leaks and stderr
# ===========================================================================

def _src_path(relative: str) -> Path:
    return Path(__file__).resolve().parent.parent / "src" / "uasset_read" / relative


class TestNoFileHandleLeak:
    """验证无 open() 无 with 的文件句柄泄漏。"""

    @staticmethod
    def _find_bare_open(filepath: Path) -> list[int]:
        """检测裸 open() 调用（不在 with 语句中的）的行号。"""
        tree = ast.parse(filepath.read_text(encoding="utf-8"))

        with_open_lines: set[int] = set()

        class WithVisitor(ast.NodeVisitor):
            def visit_With(self, node: ast.With) -> None:
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call):
                        call = item.context_expr
                        if isinstance(call.func, ast.Name) and call.func.id == "open":
                            with_open_lines.add(call.lineno)
                self.generic_visit(node)

        WithVisitor().visit(tree)

        bare_lines: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "open":
                    if node.lineno not in with_open_lines:
                        bare_lines.append(node.lineno)
        return sorted(bare_lines)

    def test_mappings_no_handle_leak(self):
        """mappings.py 不应存在裸 open() 调用。"""
        filepath = _src_path("mappings.py")
        bare = self._find_bare_open(filepath)
        assert not bare, (
            f"mappings.py 存在 {len(bare)} 处裸 open() 调用 "
            f"(行 {bare})，应使用 with 语句"
        )

    def test_batch_worker_no_handle_leak(self):
        """batch_worker.py 不应存在裸 open() 调用。"""
        filepath = _src_path("batch_worker.py")
        bare = self._find_bare_open(filepath)
        assert not bare, (
            f"batch_worker.py 存在 {len(bare)} 处裸 open() 调用 "
            f"(行 {bare})，应使用 with 语句"
        )


class TestStderrNotSwallowed:
    """验证 batch_worker 子进程 stderr 不被吞没。"""

    def test_stderr_not_devnull(self):
        """batch_worker.py 中 Popen 不应将 stderr 重定向到 DEVNULL。"""
        filepath = _src_path("batch_worker.py")
        tree = ast.parse(filepath.read_text(encoding="utf-8"))

        devnull_stderr: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                is_popen = (
                    isinstance(func, ast.Attribute)
                    and func.attr == "Popen"
                )
                if not is_popen:
                    continue
                for kw in node.keywords:
                    if kw.arg == "stderr":
                        if isinstance(kw.value, ast.Attribute):
                            if kw.value.attr == "DEVNULL":
                                devnull_stderr.append(node.lineno)
                        elif isinstance(kw.value, ast.Name):
                            if kw.value.id == "DEVNULL":
                                devnull_stderr.append(node.lineno)

        assert not devnull_stderr, (
            f"batch_worker.py 行 {devnull_stderr}: "
            f"stderr 被重定向到 DEVNULL，应保留 stderr 用于调试"
        )

    def test_stderr_visible_on_subprocess_failure(self):
        """子进程失败时 stderr 应可通过日志获取。"""
        filepath = _src_path("batch_worker.py")
        source = filepath.read_text(encoding="utf-8")
        has_stderr_logging = (
            "result.stderr" in source
            or "stderr" in source
            and "logger" in source
        )
        assert has_stderr_logging or "DEVNULL" not in source, (
            "batch_worker.py 既不记录 stderr 也不保留 stderr，"
            "子进程错误信息将完全丢失"
        )


# ==============================================================================
# 以下来自 test_logging.py
# ==============================================================================

"""日志系统综合测试 — 合并自 logging_config, logging_ownership, cli_logging_args,
cli_logging_ownership, project_logging, project_logging_session。

覆盖：日志级别配置、handler 拥有权、CLI 参数解析、project logging 集成、
session 状态管理、cleanup、轮转、debug 聚合。
"""

import importlib
import io
import logging
import logging.handlers
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import uasset_read
from uasset_read import cli, core
from uasset_read.config import LogConfig
from uasset_read.core import _configure_logging
from uasset_read import project_logging
from uasset_read.project_logging import (
    _build_log_path,
    _reset_logging_state_for_tests,
    configure_project_logging,
    setup_logging,
)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_project_logging():
    _reset_logging_state_for_tests()
    yield
    _reset_logging_state_for_tests()


def _owned_handlers():
    return [
        handler
        for handler in logging.getLogger("uasset_read").handlers
        if getattr(handler, "_uasset_read_project_log_handler", False)
    ]


def _run_cli_help():
    """运行 `python -m uasset_read --help` 并返回 stdout。"""
    src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )
    return result


def project_logging_config(**kwargs):
    return LogConfig(**kwargs)


# ===========================================================================
# 1. 日志级别规范 (#342)
# ===========================================================================

class TestLoggingLevelSpec:
    """#342: 日志级别规范测试。"""

    def test_logger_has_expected_handlers(self):
        """验证项目 logger 有正确的 handler 配置。"""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(
                log_dir=Path(tmp),
                level="DEBUG",
            )
            logger = logging.getLogger("uasset_read")
            assert len(logger.handlers) > 0
            _reset_logging_state_for_tests()

    def test_log_level_can_be_configured(self):
        """验证日志级别可通过参数配置。"""
        _reset_logging_state_for_tests()
        with tempfile.TemporaryDirectory() as tmp:
            configure_project_logging(
                log_dir=Path(tmp),
                level="WARNING",
            )
            logger = logging.getLogger("uasset_read")
            assert logger.level <= logging.WARNING
            _reset_logging_state_for_tests()


# ===========================================================================
# 2. Handler 拥有权
# ===========================================================================

def test_core_logging_default_does_not_install_file_handler():
    assert _configure_logging() is None
    assert _owned_handlers() == []


def test_core_logging_explicit_config_installs_file_handler(tmp_path):
    path = _configure_logging(
        log_config=LogConfig(dir=str(tmp_path), run_id="explicit"),
    )

    assert path is not None
    assert path.parent == tmp_path.resolve()
    assert len(_owned_handlers()) == 1


def test_parse_single_explicit_log_config_is_scoped_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        core,
        "parse_uasset_with_linker",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse failed")),
    )

    with pytest.raises(RuntimeError, match="parse failed"):
        core.parse_single(
            "missing.uasset",
            log_config=LogConfig(dir=str(tmp_path), run_id="scoped-error"),
        )

    assert _owned_handlers() == []
    assert len(list(tmp_path.glob("uasset_read-*-scoped-error.log"))) == 1


@pytest.mark.parametrize("entrypoint", ["parse_package", "parse_uasset_with_linker"])
def test_low_level_parse_defaults_do_not_configure_file_logging(monkeypatch, entrypoint):
    parse_module = importlib.import_module("uasset_read.parse_uasset")
    monkeypatch.setattr(parse_module, "_parse_package_core", lambda *args, **kwargs: None)

    getattr(parse_module, entrypoint)("missing.uasset")

    assert _owned_handlers() == []


@pytest.mark.parametrize("entrypoint", ["parse_package", "parse_uasset_with_linker"])
def test_low_level_explicit_log_config_is_scoped(monkeypatch, tmp_path, entrypoint):
    parse_module = importlib.import_module("uasset_read.parse_uasset")
    monkeypatch.setattr(parse_module, "_parse_package_core", lambda *args, **kwargs: None)

    getattr(parse_module, entrypoint)(
        "missing.uasset",
        log_config=LogConfig(dir=str(tmp_path), run_id=f"low-{entrypoint}"),
    )

    assert _owned_handlers() == []
    assert len(list(tmp_path.glob(f"uasset_read-*-low-{entrypoint}.log"))) == 1


def test_public_package_exports_logging_session_api():
    assert uasset_read.ProjectLogSession is not None
    assert callable(uasset_read.project_logging_session)
    assert callable(uasset_read.shutdown_project_logging)


def test_batch_summary_reports_result_counts(caplog):
    result = core.BatchResult(
        total=4,
        success=["one"],
        skipped=[("two", "skip")],
        failed=[("three", "fail"), ("four", "fail")],
    )
    caplog.set_level(logging.INFO, logger="uasset_read.core")

    core._log_batch_summary(result)

    assert "batch_summary total=4 success=1 skipped=1 failed=2" in caplog.text


# ===========================================================================
# 3. CLI 日志参数
# ===========================================================================

class TestCLILoggingArgs:
    """验证日志 CLI 参数正确传递。"""

    def test_log_max_total_mb_argument(self):
        """--log-max-total-mb 参数应被接受。"""
        result = _run_cli_help()
        assert "--log-max-total-mb" in result.stdout

    def test_log_keep_latest_argument(self):
        """--log-keep-latest 参数应被接受。"""
        result = _run_cli_help()
        assert "--log-keep-latest" in result.stdout

    def test_log_max_total_mb_help_text(self):
        """--log-max-total-mb 帮助文本应包含描述。"""
        result = _run_cli_help()
        assert "cap total log storage" in result.stdout

    def test_log_keep_latest_help_text(self):
        """--log-keep-latest 帮助文本应包含描述。"""
        result = _run_cli_help()
        assert "keep only the newest" in result.stdout


# ===========================================================================
# 4. CLI 日志配置
# ===========================================================================

def test_cli_builds_enabled_debug_log_config_by_default(tmp_path):
    args = cli.create_parser().parse_args([
        str(tmp_path / "asset.uasset"),
        "--log-dir",
        str(tmp_path / "logs"),
    ])

    config = cli._log_config_from_args(args)

    assert config.level == "debug"
    assert config.enabled is True
    assert config.dir == str(tmp_path / "logs")
    assert config.repeat_limit == 5
    assert config.auto_cleanup is True
    assert config.keep_latest == 20
    assert config.max_total_bytes == 500 * 1024 * 1024


def test_cli_log_level_off_disables_file_logging(tmp_path):
    args = cli.create_parser().parse_args([
        str(tmp_path / "asset.uasset"),
        "--log-level",
        "off",
    ])

    config = cli._log_config_from_args(args)

    assert config.level == "off"
    assert config.enabled is False


def test_cli_can_disable_cleanup_and_debug_aggregation(tmp_path):
    args = cli.create_parser().parse_args([
        str(tmp_path / "asset.uasset"),
        "--no-log-cleanup",
        "--log-repeat-limit",
        "0",
    ])

    config = cli._log_config_from_args(args)

    assert config.auto_cleanup is False
    assert config.repeat_limit == 0


def test_python_log_config_does_not_auto_cleanup_by_default():
    config = LogConfig()

    assert config.auto_cleanup is False
    assert config.repeat_limit == 5


def test_cli_help_describes_run_cleanup_and_safe_dry_run():
    help_text = cli.create_parser().format_help()
    normalized = " ".join(help_text.split())

    assert "newest N complete runs" in normalized
    assert "Dry-run log cleanup plan" in normalized
    assert "pass --log-cleanup to delete" not in normalized


def test_clean_logs_dry_run_uses_cli_retention_defaults(monkeypatch, tmp_path):
    args = cli.create_parser().parse_args([
        "--clean-logs",
        "--log-dir",
        str(tmp_path),
    ])
    captured = {}

    def fake_cleanup(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(cli, "cleanup_project_logs", fake_cleanup)

    with pytest.raises(SystemExit) as exc_info:
        cli._handle_clean_logs(args)

    assert exc_info.value.code == 0
    assert captured["keep_latest"] == 20
    assert captured["max_total_bytes"] == 500 * 1024 * 1024
    assert captured["dry_run"] is True


def test_cli_single_parse_passes_structured_log_config(monkeypatch, tmp_path):
    asset_path = tmp_path / "asset.uasset"
    asset_path.write_bytes(b"")
    captured = {}

    def fake_parse_single(*args, **kwargs):
        captured.update(kwargs)
        return "{}"

    monkeypatch.setattr(cli, "parse_single", fake_parse_single)
    monkeypatch.setattr(sys, "argv", ["uasset_read", str(asset_path)])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 0
    assert isinstance(captured["log_config"], LogConfig)
    assert captured["log_config"].enabled is True
    assert "log_level" not in captured
    assert "log_dir" not in captured


# ===========================================================================
# 5. Project logging 集成
# ===========================================================================

class TestLoggingIntegration:
    """端到端日志系统测试。"""

    def test_full_logging_workflow(self, tmp_path):
        """完整的日志工作流：配置 -> 写入 -> 轮转 -> 清理。"""
        _reset_logging_state_for_tests()

        log_dir = tmp_path / "log"
        log_dir.mkdir()

        # 创建多个旧日志文件
        for i in range(10):
            old_log = log_dir / f"uasset_read-2025010{i}-000000-pid1234-test{i}.log"
            old_log.write_text(f"old log content {i}")

        # 配置日志，启用自动清理
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
        from uasset_read.project_logging import cleanup_project_logs

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


# ===========================================================================
# 6. Project logging session
# ===========================================================================

def test_project_logging_keeps_host_propagation_and_restores_logger_state(tmp_path):
    package_logger = logging.getLogger("uasset_read")
    original_level = logging.WARNING
    package_logger.setLevel(original_level)
    package_logger.propagate = True

    stream = io.StringIO()
    host_handler = logging.StreamHandler(stream)
    root_logger = logging.getLogger()
    root_logger.addHandler(host_handler)
    try:
        configure_project_logging(log_dir=tmp_path, level="DEBUG", run_id="host-test")
        logging.getLogger("uasset_read.session_test").warning("visible to host")
        project_logging.shutdown_project_logging()
    finally:
        root_logger.removeHandler(host_handler)
        host_handler.close()

    assert "visible to host" in stream.getvalue()
    assert package_logger.level == original_level
    assert package_logger.propagate is True
    assert not package_logger.handlers


def test_different_configuration_replaces_owned_handler(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first_path = configure_project_logging(
        log_dir=first_dir,
        level="ERROR",
        run_id="first-run",
    )
    second_path = configure_project_logging(
        log_dir=second_dir,
        level="DEBUG",
        run_id="second-run",
    )

    assert first_path != second_path
    assert second_path is not None
    assert second_path.parent == second_dir.resolve()
    owned_handlers = [
        handler
        for handler in logging.getLogger("uasset_read").handlers
        if getattr(handler, "_uasset_read_project_log_handler", False)
    ]
    assert len(owned_handlers) == 1
    assert owned_handlers[0].level == logging.DEBUG


def test_run_id_identifies_a_unique_run_file(tmp_path):
    first_path = configure_project_logging(log_dir=tmp_path, run_id="first")
    project_logging.shutdown_project_logging()
    second_path = configure_project_logging(log_dir=tmp_path, run_id="second")

    assert first_path is not None
    assert second_path is not None
    assert first_path != second_path
    assert "first" in first_path.name
    assert "second" in second_path.name
    assert first_path.exists()
    assert second_path.exists()


def test_same_configuration_is_idempotent(tmp_path):
    first_path = configure_project_logging(log_dir=tmp_path, run_id="same")
    second_path = configure_project_logging(log_dir=tmp_path, run_id="same")

    assert second_path == first_path
    owned_handlers = [
        handler
        for handler in logging.getLogger("uasset_read").handlers
        if getattr(handler, "_uasset_read_project_log_handler", False)
    ]
    assert len(owned_handlers) == 1


def test_project_logging_session_closes_owned_handler(tmp_path):
    log_path = None
    with project_logging.project_logging_session(
        log_dir=tmp_path,
        run_id="scoped",
    ) as session:
        log_path = session.log_path
        assert session.log_path.exists()
        assert session.run_id == "scoped"
        logging.getLogger("uasset_read.session_test").info("inside scope")

    owned_handlers = [
        handler
        for handler in logging.getLogger("uasset_read").handlers
        if getattr(handler, "_uasset_read_project_log_handler", False)
    ]
    assert owned_handlers == []
    output = log_path.read_text(encoding="utf-8")
    assert "session_start" in output
    assert "session_end" in output
    assert "duration_ms=" in output


def test_session_auto_cleanup_runs_after_close_and_preserves_current_run(tmp_path):
    old_one = tmp_path / "uasset_read-20260101-000000-000000-pid1-old1.log"
    old_two = tmp_path / "uasset_read-20260102-000000-000000-pid1-old2.log"
    old_one.write_text("old one")
    old_two.write_text("old two")

    with project_logging.project_logging_session(
        log_dir=tmp_path,
        run_id="current",
        cleanup_on_close=True,
        keep_latest=1,
        max_total_bytes=0,
    ) as session:
        current_path = session.log_path

    assert current_path.exists()
    assert list(tmp_path.glob("uasset_read-*.log")) == [current_path]


def test_nested_scoped_session_is_rejected_without_replacing_outer_handler(tmp_path):
    with project_logging.project_logging_session(
        log_dir=tmp_path / "outer",
        run_id="outer",
    ) as outer:
        with pytest.raises(RuntimeError, match="already active"):
            project_logging.project_logging_session(
                log_dir=tmp_path / "inner",
                run_id="inner",
            )
        logging.getLogger("uasset_read.session_test").warning("outer remains active")

    output = outer.log_path.read_text(encoding="utf-8")
    assert "outer remains active" in output
    assert not (tmp_path / "inner").exists()


def test_log_context_adds_run_process_asset_and_stage(tmp_path):
    path = configure_project_logging(
        log_dir=tmp_path,
        run_id="context-run",
    )
    assert path is not None

    with project_logging.log_context(asset="Asset.uasset", stage="parse"):
        logging.getLogger("uasset_read.session_test").warning("context detail")
    project_logging.shutdown_project_logging()

    output = path.read_text(encoding="utf-8")
    assert "run=context-run" in output
    assert "pid=" in output
    assert "asset=Asset.uasset" in output
    assert "stage=parse" in output


def test_repeated_debug_templates_are_summarized_without_suppressing_warnings(tmp_path):
    path = configure_project_logging(
        log_dir=tmp_path,
        run_id="repeat-run",
        repeat_limit=2,
    )
    assert path is not None
    logger = logging.getLogger("uasset_read.repeat_test")

    for index in range(5):
        logger.debug("repeated value %d", index)
    for index in range(3):
        logger.warning("warning value %d", index)
    project_logging.shutdown_project_logging()

    output = path.read_text(encoding="utf-8")
    assert output.count("repeated value") == 3
    assert "suppressed=3" in output
    assert output.count("warning value") == 3


def test_scoped_api_logs_asset_lifecycle_and_failure_status(tmp_path):
    @project_logging.scoped_project_logging
    def failing_api(path: str, *, log_config=None):
        raise ValueError("broken")

    with pytest.raises(ValueError, match="broken"):
        failing_api(
            "Asset.uasset",
            log_config=project_logging_config(
                dir=str(tmp_path),
                run_id="lifecycle",
            ),
        )

    path = next(tmp_path.glob("uasset_read-*-lifecycle.log"))
    output = path.read_text(encoding="utf-8")
    assert "asset_start" in output
    assert "asset_end status=error" in output
    assert "duration_ms=" in output


# ===========================================================================
# 7. 日志文件优化（合并自 test_log_file_optimization）
# ===========================================================================

class TestLogFileOptimization:
    def test_run_filename_contains_run_id(self):
        path = _build_log_path(Path(tempfile.mkdtemp()), "test-run")
        basename = os.path.basename(path)
        assert basename.startswith("uasset_read-")
        assert basename.endswith("-test-run.log")

    def test_rotating_handler_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            root_logger = logging.getLogger("uasset_read")
            rotating = [h for h in root_logger.handlers
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
            assert len(rotating) >= 1
            _reset_logging_state_for_tests()

    def test_rotation_configured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            root_logger = logging.getLogger("uasset_read")
            rotating = [h for h in root_logger.handlers
                        if isinstance(h, logging.handlers.RotatingFileHandler)]
            handler = rotating[0]
            assert handler.maxBytes >= 1024 * 1024
            assert handler.backupCount >= 1
            _reset_logging_state_for_tests()

    def test_log_file_created_in_specified_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            log_files = list(Path(tmpdir).glob("uasset_read-*.log"))
            assert len(log_files) == 1
            _reset_logging_state_for_tests()
