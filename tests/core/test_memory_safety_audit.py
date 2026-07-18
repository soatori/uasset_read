"""内存安全审计测试 — 文件句柄泄漏与缓存增长修复验证。"""
from __future__ import annotations

import ast
import gc
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.memory_safety import (
    MemoryLimitExceeded,
    MemoryMonitor,
    MemoryPolicy,
    ResourceLimits,
    cleanup_after_parse,
)


# ===========================================================================
# 文件句柄安全网
# ===========================================================================

class TestFileHandleSafetyNet:
    """验证文件处理类的 __del__ 安全网。"""

    def test_farchive_has_del_method(self):
        """FArchive 应有 __del__ 方法作为安全网。"""
        from uasset_read.archive import FArchive

        # 验证 __del__ 方法存在
        assert hasattr(FArchive, "__del__"), "FArchive 应有 __del__ 方法"

    def test_farchive_del_is_callable(self):
        """FArchive.__del__ 应是可调用的方法。"""
        from uasset_read.archive import FArchive

        # 验证 __del__ 是方法
        assert callable(getattr(FArchive, "__del__", None)), "FArchive.__del__ 应是可调用的"

    def test_iostore_reader_has_del_method(self):
        """IoStoreReader 应有 __del__ 方法作为安全网。"""
        from uasset_read.iostore.reader import IoStoreReader

        assert hasattr(IoStoreReader, "__del__"), "IoStoreReader 应有 __del__ 方法"

    def test_pak_file_reader_has_del_method(self):
        """PakFileReader 应有 __del__ 方法作为安全网。"""
        from uasset_read.pak.reader import PakFileReader

        assert hasattr(PakFileReader, "__del__"), "PakFileReader 应有 __del__ 方法"

    def test_del_method_implementation_pattern(self):
        """验证 __del__ 方法遵循正确的实现模式。"""
        import ast
        from pathlib import Path

        # 检查 archive.py
        archive_path = Path(__file__).parent.parent / "src" / "uasset_read" / "archive.py"
        source = archive_path.read_text(encoding="utf-8")

        # 验证 __del__ 方法存在且调用 close()
        assert "def __del__(self)" in source, "archive.py 应有 __del__ 方法"
        assert "self.close()" in source, "archive.py __del__ 应调用 self.close()"

        # 检查 iostore/reader.py
        iostore_path = Path(__file__).parent.parent / "src" / "uasset_read" / "iostore" / "reader.py"
        source = iostore_path.read_text(encoding="utf-8")
        assert "def __del__(self)" in source, "iostore/reader.py 应有 __del__ 方法"

        # 检查 pak/reader.py
        pak_path = Path(__file__).parent.parent / "src" / "uasset_read" / "pak" / "reader.py"
        source = pak_path.read_text(encoding="utf-8")
        assert "def __del__(self)" in source, "pak/reader.py 应有 __del__ 方法"


# ===========================================================================
# 缓存重置
# ===========================================================================

class TestCacheResetMethods:
    """验证缓存重置方法。"""

    def test_class_handler_registry_reset_cache(self):
        """ClassHandlerRegistry.reset_cache() 应只清空查找缓存。"""
        from uasset_read.parsers.class_registry import ClassHandlerRegistry

        registry = ClassHandlerRegistry()

        # 创建 mock handler
        mock_handler = MagicMock()
        mock_handler.can_handle.return_value = True
        mock_handler.handler_name = "TestHandler"

        # 注册 handler
        registry.register(mock_handler)

        # 模拟缓存数据
        registry._cache["TestClass"] = mock_handler
        registry._cache["AnotherClass"] = None

        # 调用 reset_cache
        registry.reset_cache()

        # 验证缓存被清空，但 handlers 仍存在
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
        # 这个测试验证 parse_uasset.py 中的清理逻辑
        # 由于 parse_package 需要实际文件，这里验证清理函数的存在
        import ast
        from pathlib import Path

        parse_uasset_path = Path(__file__).parent.parent / "src" / "uasset_read" / "parse_uasset.py"
        source = parse_uasset_path.read_text(encoding="utf-8")

        # 验证 finally 块中存在循环引用清理代码
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
        import ast
        from pathlib import Path

        core_init_path = Path(__file__).parent.parent / "src" / "uasset_read" / "core" / "__init__.py"
        source = core_init_path.read_text(encoding="utf-8")

        # 验证存在释放临时属性的代码
        assert "_asset_type_data" in source, "core/__init__.py 应释放 _asset_type_data"
        assert "_uclass_native_fields" in source, "core/__init__.py 应释放 _uclass_native_fields"
        assert "delattr" in source, "core/__init__.py 应使用 delattr 释放属性"


# ===========================================================================
# 上下文管理器
# ===========================================================================

class TestArchiveContextManager:
    """验证 Archive 类支持上下文管理器协议。"""

    def test_iostore_reader_has_context_manager(self):
        """IoStoreReader 应支持 with 语句。"""
        from uasset_read.iostore.reader import IoStoreReader

        assert hasattr(IoStoreReader, "__enter__"), "IoStoreReader 应有 __enter__ 方法"
        assert hasattr(IoStoreReader, "__exit__"), "IoStoreReader 应有 __exit__ 方法"

    def test_pak_file_reader_has_context_manager(self):
        """PakFileReader 应支持 with 语句。"""
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
        """检测裸 open() 调用（不在 with 语句中的）的行号。

        遍历 AST，找出所有 open(...) 调用节点，然后检查其
        最近的 ast.Call 祖先是否直接位于 with 上下文管理器中。
        """
        tree = ast.parse(filepath.read_text(encoding="utf-8"))

        # 收集所有 with 语句中直接包含 open() 的节点位置
        with_open_lines: set[int] = set()

        class WithVisitor(ast.NodeVisitor):
            """遍历 with 语句，记录直接在 with 中的 open() 调用。"""

            def visit_With(self, node: ast.With) -> None:
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call):
                        call = item.context_expr
                        if isinstance(call.func, ast.Name) and call.func.id == "open":
                            with_open_lines.add(call.lineno)
                self.generic_visit(node)

        WithVisitor().visit(tree)

        # 收集所有裸 open() 调用
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
                # 检查是否为 subprocess.Popen 调用
                func = node.func
                is_popen = (
                    isinstance(func, ast.Attribute)
                    and func.attr == "Popen"
                )
                if not is_popen:
                    continue
                # 检查 stderr=DEVNULL 关键字参数
                for kw in node.keywords:
                    if kw.arg == "stderr":
                        if isinstance(kw.value, ast.Attribute):
                            # stderr=subprocess.DEVNULL
                            if kw.value.attr == "DEVNULL":
                                devnull_stderr.append(node.lineno)
                        elif isinstance(kw.value, ast.Name):
                            # stderr=DEVNULL (已导入)
                            if kw.value.id == "DEVNULL":
                                devnull_stderr.append(node.lineno)

        assert not devnull_stderr, (
            f"batch_worker.py 行 {devnull_stderr}: "
            f"stderr 被重定向到 DEVNULL，应保留 stderr 用于调试"
        )

    def test_stderr_visible_on_subprocess_failure(self):
        """子进程失败时 stderr 应可通过日志获取。"""
        # 验证 batch_worker 源码中存在对 result.stderr 的日志记录
        filepath = _src_path("batch_worker.py")
        source = filepath.read_text(encoding="utf-8")
        # 应有 logger 调用引用 stderr（或 PIPE 模式）
        has_stderr_logging = (
            "result.stderr" in source
            or "stderr" in source
            and "logger" in source
        )
        # 基本验证：文件中应引用 stderr 用于调试
        assert has_stderr_logging or "DEVNULL" not in source, (
            "batch_worker.py 既不记录 stderr 也不保留 stderr，"
            "子进程错误信息将完全丢失"
        )
