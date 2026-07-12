import pytest
from uasset_read.archive import ByteArchive


def test_farchive_skip():
    """FArchive 应支持 skip() 方法跳过指定字节数。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    initial_pos = archive.tell()
    archive.skip(10)
    assert archive.tell() == initial_pos + 10


def test_farchive_skip_to_end():
    """skip() 应支持跳转到文件末尾。"""
    data = b'\x00' * 50
    archive = ByteArchive(data)

    archive.skip(50)
    assert archive.tell() == 50


def test_farchive_skip_zero():
    """skip(0) 应保持位置不变。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    archive.skip(0)
    assert archive.tell() == 0


def test_farchive_skip_negative_raises():
    """skip() 负数应抛出异常（seek 会验证）。"""
    data = b'\x00' * 100
    archive = ByteArchive(data)

    with pytest.raises(Exception):  # ParseError from seek validation
        archive.skip(-5)
