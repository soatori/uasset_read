"""P2 内存安全测试 (#108)。"""
from __future__ import annotations

import pytest


class TestCacheCleanup:
    """#108 P1: 缓存应有清理机制。"""

    def test_function_ref_resolver_has_reset(self):
        """FunctionRefResolver 应有 reset() 方法。"""
        from uasset_read.kismet.function_resolver import FunctionRefResolver
        assert hasattr(FunctionRefResolver, 'reset')

    def test_class_registry_has_reset_cache(self):
        """ClassHandlerRegistry 应有 reset_cache() 方法。"""
        from uasset_read.parsers.class_registry import ClassHandlerRegistry
        registry = ClassHandlerRegistry()
        assert hasattr(registry, 'reset_cache')

    def test_class_registry_global_reset(self):
        """全局 registry 的 reset_default_registry_cache() 应清空缓存。"""
        from uasset_read.parsers.class_registry import (
            get_class_registry, reset_default_registry_cache,
        )
        registry = get_class_registry()
        registry._cache["test"] = None
        reset_default_registry_cache()
        assert len(registry._cache) == 0


class TestFileHandleSafety:
    """#108 P0: 文件处理类应有 __del__ 安全网。"""

    def test_farchive_has_del(self):
        """FArchive 应有 __del__ 方法。"""
        from uasset_read.archive import FArchive
        assert hasattr(FArchive, '__del__')

    def test_iostore_reader_has_del(self):
        """IoStoreReader 应有 __del__ 方法。"""
        from uasset_read.iostore.reader import IoStoreReader
        assert hasattr(IoStoreReader, '__del__')

    def test_pak_reader_has_del(self):
        """PakFileReader 应有 __del__ 方法。"""
        from uasset_read.pak.reader import PakFileReader
        assert hasattr(PakFileReader, '__del__')

    def test_farchive_del_closes_safely(self):
        """FArchive.__del__ 不应抛异常。"""
        from uasset_read.archive import FArchive
        import tempfile
        import os

        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 100)
            tmp_path = f.name

        try:
            archive = FArchive(tmp_path)
            archive.close()
            # __del__ 在已关闭的 archive 上不应抛异常
            archive.__del__()
        finally:
            os.unlink(tmp_path)
