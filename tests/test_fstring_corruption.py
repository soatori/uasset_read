"""测试 FString corrupted 处理 — Task 3（确认性行为测试）"""
import pytest
import os

from uasset_read.archive import FArchive


def _make_archive(data: bytes) -> FArchive:
    """创建临时 FArchive 用于测试。"""
    path = os.path.join(os.path.dirname(__file__), "..", "temp", "_test_fstring.uasset")
    path = os.path.normpath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return FArchive(path)


class TestFStringCorruption:
    """验证 FString 在遇到损坏数据时的处理行为。"""

    def test_all_nulls_returns_empty(self):
        """全 null 数据返回空字符串，不崩溃。"""
        # length=5, 后面 5 个 null 字节
        data = b"\x05\x00\x00\x00\x00\x00\x00\x00\x00"
        archive = _make_archive(data)
        result = archive.read_fstring()
        assert result == ""

    def test_partial_content_before_null(self):
        """null 之前有内容时截断返回。"""
        # length=10, "hello\x00..." 在 null 处截断
        content = b"hello\x00\x00\x00\x00\x00"
        data = b"\x0a\x00\x00\x00" + content
        archive = _make_archive(data)
        result = archive.read_fstring()
        assert result == "hello"

    def test_empty_string(self):
        """length=0 返回空字符串。"""
        data = b"\x00\x00\x00\x00"
        archive = _make_archive(data)
        result = archive.read_fstring()
        assert result == ""

    def test_normal_string(self):
        """正常字符串正确读取。"""
        text = b"Hello World\x00"
        data = b"\x0b\x00\x00\x00" + text
        archive = _make_archive(data)
        result = archive.read_fstring()
        assert result == "Hello World"

    def test_position_restored_on_boundary_error(self):
        """长度异常时位置回退到入口。"""
        # length=999999 但后面没有足够数据
        data = b"\x3f\x42\x0f\x00"  # 大长度，无后续数据
        archive = _make_archive(data)
        pos_before = archive.tell()

        with pytest.raises(Exception):
            archive.read_fstring()

        # 位置应回退到入口
        assert archive.tell() == pos_before