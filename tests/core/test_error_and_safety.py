"""错误处理与内存安全测试 — 合并自 test_error_handling.py 和 test_memory_safety_audit.py。

覆盖：tolerant_parse 基础行为与去重、异常类层次、_handle_parse_error 各分支、
_record_parse_stage_error 去重与诊断、BaseResult._error_keys 字段、
文件句柄泄漏、缓存重置、循环引用清理、上下文管理器、MemoryPolicy。
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
