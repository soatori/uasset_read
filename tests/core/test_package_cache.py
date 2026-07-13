"""测试 FileSystemPackageProvider 缓存失效机制。

验证缓存基于目录修改时间自动失效，而非仅依赖手动 refresh_file_cache()。
"""

import pytest
import tempfile
import time
from pathlib import Path


def test_list_files_cache_returns_same_object():
    """验证缓存返回相同的列表对象。"""
    from uasset_read.package import FileSystemPackageProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        result2 = provider.list_files()

        # 应该返回同一个对象（缓存命中）
        assert result1 is result2


def test_list_files_cache_invalidated_on_file_change():
    """验证文件变化后缓存自动失效。"""
    from uasset_read.package import FileSystemPackageProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test1.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        assert len(result1) == 1

        # 添加新文件——目录 mtime 变化
        time.sleep(0.1)
        (Path(tmpdir) / "test2.uasset").touch()

        # 缓存应该自动失效
        result2 = provider.list_files()
        assert len(result2) == 2


def test_refresh_file_cache_forces_refresh():
    """验证 refresh_file_cache() 强制刷新缓存。"""
    from uasset_read.package import FileSystemPackageProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test1.uasset").touch()

        provider = FileSystemPackageProvider(tmpdir)
        result1 = provider.list_files()
        assert len(result1) == 1

        # 添加新文件并手动刷新
        (Path(tmpdir) / "test2.uasset").touch()
        provider.refresh_file_cache()

        result2 = provider.list_files()
        assert len(result2) == 2
