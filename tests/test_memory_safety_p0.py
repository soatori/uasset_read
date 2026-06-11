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


class TestXferStringLimits:
    """Issue #107-1: xfer_string/xfer_unicode_string 读取整个剩余流。"""

    def test_xfer_string_respects_max_len(self):
        """xfer_string 应在达到 max_len 时停止读取。"""
        from uasset_read.kismet.archive import FKismetArchive

        # 创建一个包含超长字符串的 archive（无 null terminator）
        data = b"A" * 100000  # 100KB 无 null 终止符
        archive = FKismetArchive(data, "test", [], tolerant=True)

        # 应该抛出 ParseError 而不是读取全部数据
        with pytest.raises(ParseError, match="no null terminator"):
            archive.xfer_string()

    def test_xfer_string_normal_case(self):
        """xfer_string 正常读取 null 终止字符串。"""
        from uasset_read.kismet.archive import FKismetArchive

        data = b"Hello\x00World\x00"
        archive = FKismetArchive(data, "test", [], tolerant=True)

        result = archive.xfer_string()
        assert result == "Hello"

    def test_xfer_unicode_string_respects_max_len(self):
        """xfer_unicode_string 应在达到 max_len 时停止读取。"""
        from uasset_read.kismet.archive import FKismetArchive

        # 创建一个包含超长 UTF-16 字符串的 archive（无 null terminator）
        data = ("A" * 50000).encode("utf-16-le")  # 100KB
        archive = FKismetArchive(data, "test", [], tolerant=True)

        with pytest.raises(ParseError, match="no null terminator"):
            archive.xfer_unicode_string()

    def test_xfer_unicode_string_normal_case(self):
        """xfer_unicode_string 正常读取双 null 终止字符串。"""
        from uasset_read.kismet.archive import FKismetArchive

        data = "Hello".encode("utf-16-le") + b"\x00\x00"
        archive = FKismetArchive(data, "test", [], tolerant=True)

        result = archive.xfer_unicode_string()
        assert result == "Hello"


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
