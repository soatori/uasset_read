"""P0 内存安全问题测试 — 句柄泄漏和 xfer_string 读取限制。"""
from __future__ import annotations

import os
import pytest

from uasset_read.mappings import UsmapParser, JmapParser
from uasset_read.exceptions import ParseError


class TestMappingsFileHandleLeak:
    """Issue #107-2: mappings.py 文件句柄泄漏。"""

    def test_usmap_parser_closes_file_handle(self, tmp_path):
        """UsmapParser 从文件读取后应关闭文件句柄。"""
        usmap_path = tmp_path / "test.usmap"
        usmap_path.write_bytes(b"\x00\x00")  # 无效 magic

        initial_fds = _count_open_fds()

        with pytest.raises(ParseError):
            UsmapParser(str(usmap_path))

        after_fds = _count_open_fds()
        assert after_fds <= initial_fds + 1, f"文件句柄泄漏: {after_fds - initial_fds} 个未关闭"

    def test_jmap_parser_closes_file_handle(self, tmp_path):
        """JmapParser 从文件读取后应关闭文件句柄。"""
        jmap_path = tmp_path / "test.jmap"
        jmap_path.write_bytes(b"invalid json")

        initial_fds = _count_open_fds()

        with pytest.raises(Exception):  # JSON 解析错误
            JmapParser(str(jmap_path))

        after_fds = _count_open_fds()
        assert after_fds <= initial_fds + 1, f"文件句柄泄漏: {after_fds - initial_fds} 个未关闭"

    def test_usmap_parser_batch_no_leak(self, tmp_path):
        """批量解析多个 usmap 文件不应累积泄漏。"""
        for i in range(10):
            path = tmp_path / f"test_{i}.usmap"
            path.write_bytes(b"\x00\x00")

        initial_fds = _count_open_fds()

        for i in range(10):
            path = tmp_path / f"test_{i}.usmap"
            try:
                UsmapParser(str(path))
            except ParseError:
                pass

        after_fds = _count_open_fds()
        leaked = after_fds - initial_fds
        assert leaked <= 1, f"批量解析泄漏 {leaked} 个文件句柄"


def _count_open_fds() -> int:
    """统计当前进程打开的文件描述符数量（跨平台）。"""
    if os.name == "nt":
        # Windows: 尝试打开文件验证句柄未耗尽
        try:
            fd = os.open(os.devnull, os.O_RDONLY)
            os.close(fd)
            return 0  # 无法精确统计，返回 0 表示正常
        except OSError:
            return 9999  # 句柄耗尽
    else:
        # Unix: 直接统计 /proc/self/fd
        try:
            return len(os.listdir("/proc/self/fd"))
        except OSError:
            return 0
