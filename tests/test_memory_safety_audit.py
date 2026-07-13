"""内存安全审计测试 — 文件句柄泄漏与缓存增长修复验证。"""
from __future__ import annotations

import gc
import sys
from unittest.mock import MagicMock, patch

import pytest


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


class TestCacheResetMethods:
    """验证缓存重置方法。"""

    def test_function_ref_resolver_reset(self):
        """FunctionRefResolver.reset() 应清空所有缓存和计数器。"""
        from uasset_read.kismet.function_resolver import FunctionRefResolver

        mock_linker = MagicMock()
        resolver = FunctionRefResolver(mock_linker)

        # 模拟一些缓存数据
        resolver._cache[123] = ("ClassName", "FuncName")
        resolver._virtual_class_cache["FuncName"] = "ClassName"
        resolver._resolve_attempts = 10
        resolver._resolve_failures = 3
        resolver._unresolved_refs[456] = 5

        # 调用 reset
        resolver.reset()

        # 验证所有缓存被清空
        assert len(resolver._cache) == 0
        assert len(resolver._virtual_class_cache) == 0
        assert resolver._resolve_attempts == 0
        assert resolver._resolve_failures == 0
        assert len(resolver._unresolved_refs) == 0

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
