"""read_name() 越界警告去重测试 (#411)

验证同一越界索引重复出现时，只记录一次警告/诊断。
"""
import pytest
from uasset_read.archive import ByteArchive


def test_read_name_duplicate_index_only_one_diagnostic():
    """重复的越界索引只应记录一次诊断。"""
    # index=5 (u32), number=0 (u32) — name_map 只有 3 个元素
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00' * 3  # 3 次读取同一越界索引
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    for _ in range(3):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    # 只有第一次出现时记录诊断
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1


def test_read_name_different_indices_each_recorded():
    """不同的越界索引应各自记录一次诊断。"""
    # index=3 (u32), number=0; index=5 (u32), number=0; index=7 (u32), number=0
    data = (
        b'\x03\x00\x00\x00\x00\x00\x00\x00'
        b'\x05\x00\x00\x00\x00\x00\x00\x00'
        b'\x07\x00\x00\x00\x00\x00\x00\x00'
    )
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]  # 只有 3 个元素

    archive.read_name(name_map)  # index=3, out of range
    archive.read_name(name_map)  # index=5, out of range
    archive.read_name(name_map)  # index=7, out of range

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 3


def test_read_name_mixed_valid_and_invalid():
    """有效和无效索引混合时，只记录无效索引的诊断。"""
    # index=1 (valid), index=5 (invalid), index=0 (valid)
    data = (
        b'\x01\x00\x00\x00\x00\x00\x00\x00'  # index=1, valid
        b'\x05\x00\x00\x00\x00\x00\x00\x00'  # index=5, invalid
        b'\x00\x00\x00\x00\x00\x00\x00\x00'  # index=0, valid
    )
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]

    archive.read_name(name_map)  # Name1
    archive.read_name(name_map)  # None (index=5 out of range)
    archive.read_name(name_map)  # Name0

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1
    assert "index 5" in out_of_range[0].error


def test_read_name_duplicate_invalid_then_valid():
    """先重复越界，再有效索引，诊断只记录一次。"""
    # index=10 (u32), number=0 — 重复 5 次
    data = b'\x0A\x00\x00\x00\x00\x00\x00\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    for _ in range(5):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1
    assert "index 10" in out_of_range[0].error


def test_read_name_negative_index_dedup():
    """负索引（0xFFFFFFFF）也应去重。"""
    # 0xFFFFFFFF as u32 = 4294967295, 越界
    data = b'\xff\xff\xff\xff\x00\x00\x00\x00' * 3
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0"]

    for _ in range(3):
        archive.read_name(name_map)

    diagnostics = archive.get_diagnostics()
    out_of_range = [d for d in diagnostics if d.field == "read_name"]
    assert len(out_of_range) == 1


def test_read_name_strict_mode_still_deduplicates():
    """strict 模式下，同一越界索引第二次也应被去重（不会触发第二次异常前的诊断）。"""
    # strict 模式第一次就越界直接抛异常，不会执行到第二次
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)
    name_map = ["Name0", "Name1", "Name2"]

    with pytest.raises(Exception):
        archive.read_name(name_map)


def test_read_name_fresh_archive_warnings_seen_empty():
    """新 archive 的 _name_warnings_seen 应为空集。"""
    data = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    assert len(archive._name_warnings_seen) == 0


def test_read_name_valid_index_does_not_populate_warnings_seen():
    """有效索引不应写入 _name_warnings_seen。"""
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    assert len(archive._name_warnings_seen) == 0


def test_read_name_invalid_index_populates_warnings_seen():
    """越界索引应写入 _name_warnings_seen。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    assert 5 in archive._name_warnings_seen


def test_read_name_all_returns_none_for_invalid():
    """去重不影响返回值——每次越界都应返回 'None'。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00' * 3
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0"]

    for _ in range(3):
        result = archive.read_name(name_map)
        assert result == "None"
