"""
test_mmap_behavior.py - SAFE-03 mmap 测试

Phase 5 Wave 0: 测试脚手架
"""

import pytest
import os
import tempfile
from uasset_read import FArchive, ParseError

MMAP_THRESHOLD = 50 * 1024 * 1024  # 50MB per D-01


def create_synthetic_uasset(size_mb: int) -> str:
    """创建合成 .uasset 文件用于测试"""
    f = tempfile.NamedTemporaryFile(delete=False, suffix='.uasset')
    # 写入有效的 UE 魔术标签 + 填充数据
    f.write(b'\xC1\x83\x2A\x9E')  # PACKAGE_FILE_TAG
    f.write(b'\x00' * (size_mb * 1024 * 1024 - 4))
    f.close()
    return f.name


class TestMmapThreshold:
    """D-01: 50MB threshold tests"""

    def test_mmap_threshold_switch(self):
        """Files >= 50MB use mmap mode"""
        pytest.skip("Wave 0 stub - implement after FArchive mmap support")

    def test_below_threshold_normal_read(self):
        """Files < 50MB use normal file read"""
        pytest.skip("Wave 0 stub")


class TestMmapFallback:
    """D-03: mmap failure fallback tests"""

    def test_mmap_fallback_on_error(self):
        """mmap failure falls back to normal read with warning"""
        pytest.skip("Wave 0 stub")


class TestMmapReadWrite:
    """D-02: mmap read/write consistency tests"""

    def test_mmap_read_correctness(self):
        """mmap read returns same data as normal read"""
        pytest.skip("Wave 0 stub")

    def test_mmap_seek_validation(self):
        """mmap seek validates bounds per D-10"""
        pytest.skip("Wave 0 stub")


class TestMmapClose:
    """D-05: unified close tests"""

    def test_mmap_close_releases_resources(self):
        """close() releases both mmap and file"""
        pytest.skip("Wave 0 stub")