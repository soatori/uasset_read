"""read_name() 索引越界增强测试 (#334) + 越界警告去重测试 (#411) + archive skip 测试"""
import pytest
from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


def test_read_name_index_out_of_range():
    """read_name() 索引越界时应返回 'None' 而非崩溃。"""
    # 构造一个只包含索引数据的 archive
    # index=5 (u32), number=0 (u32)
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1", "Name2"]  # 只有 3 个名称

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_index_out_of_range_strict():
    """read_name() 索引越界在 strict 模式应抛出异常。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)
    name_map = ["Name0", "Name1", "Name2"]

    with pytest.raises(ParseError):
        archive.read_name(name_map)


def test_read_name_index_negative():
    """read_name() 负索引应返回 'None'。"""
    # index=0xFFFFFFFF (-1 as signed), number=0
    data = b'\xff\xff\xff\xff\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_valid_index():
    """read_name() 正常索引应正确返回名称。"""
    # index=1, number=0
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data)
    name_map = ["Name0", "Name1", "Name2"]

    result = archive.read_name(name_map)
    assert result == "Name1"


def test_read_name_with_number():
    """read_name() 带 number 后缀应正确格式化。"""
    # index=0, number=5
    data = b'\x00\x00\x00\x00\x05\x00\x00\x00'
    archive = ByteArchive(data)
    name_map = ["MyName"]

    result = archive.read_name(name_map)
    assert result == "MyName_5"


def test_read_name_large_index_recovery():
    """read_name() 检测到异常大索引时应尝试恢复。"""
    # 模拟 SerializationControlExtensions 导致的偏移错位
    # 构造数据：2字节偏移 + 正常 FName (index=0, number=0)
    # 前面填充垃圾字节模拟错位，垃圾字节 + 后续数据组合产生 > 1000 的 u32
    garbage = b'\x00\x10\x00\x00\x00\x00'  # 6字节垃圾数据
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'  # index=0, number=0
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    # 应该能够恢复并读取到正确的名称
    result = archive.read_name(name_map)
    assert result == "TestName"


def test_read_name_large_index_recovery_with_number():
    """read_name() 恢复时保留 number 后缀。"""
    garbage = b'\x5B\x00'  # 2字节垃圾数据
    valid_name = b'\x01\x00\x00\x00\x03\x00\x00\x00'  # index=1, number=3
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "Name1_3"


def test_read_name_recovery_disabled_in_strict_mode():
    """strict 模式下不触发恢复，直接抛异常。"""
    garbage = b'\x5B\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=False)
    name_map = ["TestName"]

    with pytest.raises(ParseError):
        archive.read_name(name_map)


def test_read_name_recovery_no_valid_offset():
    """所有偏移调整均无效时，应返回 'None'。"""
    # 构造数据使得所有偏移调整后的索引均无效
    # 垃圾字节 + 异常数据，name_map 为空
    garbage = b'\xE9\x03\x00\x00'
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = []  # 空 name_map，任何索引均越界

    result = archive.read_name(name_map)
    assert result == "None"


def test_read_name_recovery_1byte_offset():
    """1字节偏移也能恢复。"""
    garbage = b'\x00\x10\x00\x00'  # 4字节垃圾数据（u32 读取产生大索引）
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'  # index=0, number=0
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    result = archive.read_name(name_map)
    assert result == "TestName"


def test_read_name_recovery_threshold():
    """read_name() 只在索引超过阈值时尝试恢复。"""
    # 索引刚好在阈值以下（999 < 1000），不应触发恢复
    data = b'\xE7\x03\x00\x00\x00\x00\x00\x00'  # index=999, number=0
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name"] * 1000

    result = archive.read_name(name_map)
    assert result == "Name"  # number=0 时不带后缀，正常读取不恢复


def test_read_name_recovery_with_number():
    """read_name() 恢复后应正确处理 number 后缀。"""
    # 模拟偏移错位：2字节垃圾 + 有效 FName (index=0, number=5)
    # garbage 须产生 > 1000 的 u32 以触发恢复（b'\xE9\x03' = 1001）
    garbage = b'\xE9\x03'
    valid_name = b'\x00\x00\x00\x00\x05\x00\x00\x00'  # index=0, number=5
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    result = archive.read_name(name_map)
    assert result == "TestName_5"


def test_read_name_recovery_failure():
    """read_name() 恢复失败时应返回 'None'。"""
    # 所有位置都是无效索引
    data = b'\xFF\x00\x00\x00\x00\x00\x00\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    result = archive.read_name(name_map)
    assert result == "None"


# --- 恢复统计诊断测试 ---

def test_recovery_stats_initial_zero():
    """新 archive 的恢复统计应为零。"""
    data = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 0
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 0


def test_recovery_stats_success():
    """恢复成功时应正确计数。"""
    garbage = b'\xE9\x03'  # 产生大索引，触发恢复
    valid_name = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    data = garbage + valid_name
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 1
    assert stats["recovery_successes"] == 1
    assert stats["recovery_failures"] == 0


def test_recovery_stats_failure():
    """恢复失败时应正确计数。"""
    # index=1001 (> threshold) 触发恢复，name_map 为空使所有恢复偏移均无效
    data = b'\xE9\x03\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = []  # 空 name_map → 恢复必失败

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 1
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 1


def test_recovery_stats_multiple_attempts():
    """多次调用应累积统计。"""
    # 第一次：恢复成功（2字节垃圾 + 有效 FName）
    garbage1 = b'\xE9\x03'
    valid1 = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    # 第二次：恢复失败（index=1001, 空 name_map）
    fail_data = b'\xE9\x03\x00\x00\x00\x00\x00\x00'
    data = garbage1 + valid1 + fail_data
    archive = ByteArchive(data, tolerant=True)
    name_map = ["TestName"]

    archive.read_name(name_map)  # 恢复成功
    # 第二次读取位置在 10，fail_data 从索引 10 开始，index=1001 触发恢复
    archive.read_name(name_map)  # 恢复失败（name_map 只有 1 个元素，恢复偏移产生的 index 不在范围内）

    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 2
    assert stats["recovery_successes"] == 1
    assert stats["recovery_failures"] == 1


def test_recovery_stats_no_recovery_for_valid_index():
    """正常索引不触发恢复，统计应为零。"""
    data = b'\x01\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)
    name_map = ["Name0", "Name1"]

    archive.read_name(name_map)
    stats = archive.get_read_name_recovery_stats()
    assert stats["recovery_attempts"] == 0
    assert stats["recovery_successes"] == 0
    assert stats["recovery_failures"] == 0


# --- archive skip 测试 ---


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


# --- read_name() 越界警告去重测试 (#411) ---


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
