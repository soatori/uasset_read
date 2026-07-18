"""FString/FText 安全与容错测试

合并测试文件：
- test_fstring_limit.py — FString 超长声明长度诊断增强测试 (#413)
- test_fstring_corruption.py — FString 全空损坏检测测试 (#330)
- test_ftext_args.py — FText args 数量限制测试
- test_ftext_safety.py — FTEXT-SAFETY 恢复位置测试
"""
import struct
import pytest
from unittest.mock import MagicMock, patch
from uasset_read.archive import ByteArchive, MAX_FSTRING_LENGTH
from uasset_read.exceptions import ParseError
from uasset_read.serializers.graph import read_ftext_with_history


# --- UTF-8 超长 ---

def test_fstring_utf8_exceeds_limit_tolerant_returns_empty():
    """UTF-8 FString 长度超过 MAX_FSTRING_LENGTH 时 tolerant 返回空字符串。"""
    # length=100_000_000 (远超 10MB 限制)
    length_val = 100_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_utf8_exceeds_limit_tolerant_records_diagnostic():
    """UTF-8 FString 超长时 tolerant 模式记录诊断信息。"""
    length_val = 100_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    archive.read_fstring()

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    d = diags[0]
    assert d.module == "archive"
    assert d.field == "fstring"
    assert d.source == "read_fstring"
    assert d.target_offset == 0  # pos_before
    assert d.read_size == length_val
    assert "exceeds MAX_FSTRING_LENGTH" in d.error


def test_fstring_utf8_exceeds_limit_strict_raises():
    """UTF-8 FString 长度超过 MAX_FSTRING_LENGTH 时 strict 抛出 ParseError。"""
    length_val = 100_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError, match="exceeds"):
        archive.read_fstring()


# --- UTF-16 超长 ---

def test_fstring_utf16_exceeds_limit_tolerant_returns_empty():
    """UTF-16 FString 长度超过 MAX_FSTRING_LENGTH 时 tolerant 返回空字符串。"""
    # length=-50_000_000 → utf16_len = 100_000_000
    length_val = -50_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_utf16_exceeds_limit_tolerant_records_diagnostic():
    """UTF-16 FString 超长时 tolerant 模式记录诊断信息。"""
    length_val = -50_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    archive.read_fstring()

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    d = diags[0]
    assert d.module == "archive"
    assert d.field == "fstring"
    assert d.source == "read_fstring"
    assert d.target_offset == 0
    assert d.read_size == 100_000_000  # utf16_len = -length * 2
    assert "exceeds MAX_FSTRING_LENGTH" in d.error


def test_fstring_utf16_exceeds_limit_strict_raises():
    """UTF-16 FString 长度超过 MAX_FSTRING_LENGTH 时 strict 抛出 ParseError。"""
    length_val = -50_000_000
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError, match="exceeds"):
        archive.read_fstring()


# --- 边界条件 ---

def test_fstring_exactly_at_limit_succeeds():
    """长度恰好等于 MAX_FSTRING_LENGTH 时应正常读取（不触发超长检测）。"""
    # 构造长度恰好等于 MAX_FSTRING_LENGTH 的 UTF-8 FString
    # 需要提供足够的数据
    length_val = MAX_FSTRING_LENGTH
    data = struct.pack('<i', length_val) + b'\x00' * length_val
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""  # 全 null 数据


def test_fstring_just_above_limit_tolerant():
    """长度刚好超过 MAX_FSTRING_LENGTH 时 tolerant 返回空字符串。"""
    length_val = MAX_FSTRING_LENGTH + 1
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    assert diags[0].read_size == length_val


def test_fstring_negative_just_above_limit_tolerant():
    """UTF-16 长度刚好超过 MAX_FSTRING_LENGTH 时 tolerant 返回空字符串。"""
    # utf16_len = MAX_FSTRING_LENGTH + 2 → -length = (MAX_FSTRING_LENGTH + 2) / 2
    utf16_len = MAX_FSTRING_LENGTH + 2
    length_val = -(utf16_len // 2)
    data = struct.pack('<i', length_val)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    assert diags[0].read_size == utf16_len


# --- 异常值（来自 issue #413 的实际案例）---

def test_fstring_issue413_value_956301312():
    """Issue #413: 长度值 956301312 超过限制，tolerant 应返回空字符串。"""
    data = struct.pack('<i', 956301312)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    assert diags[0].read_size == 956301312


def test_fstring_issue413_value_419430400():
    """Issue #413: 长度值 419430400 超过限制，tolerant 应返回空字符串。"""
    data = struct.pack('<i', 419430400)
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""

    diags = archive.get_diagnostics()
    assert len(diags) == 1
    assert diags[0].read_size == 419430400


# --- FString 全空损坏检测 (#330) ---

def test_fstring_all_nulls_utf8_tolerant():
    """UTF-8 FString 全空在 tolerant 模式应返回空字符串。"""
    # length=5 (u32 LE), 5 个 null 字节
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_all_nulls_utf16_tolerant():
    """UTF-16 FString 全空在 tolerant 模式应返回空字符串。"""
    # length=-3 (i32 LE) → utf16_len=6, 6 个 null 字节
    data = b'\xfd\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_all_nulls_utf8_strict():
    """UTF-8 FString 全空在 strict 模式应抛出 ParseError。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError):
        archive.read_fstring()


def test_fstring_all_nulls_utf16_strict():
    """UTF-16 FString 全空在 strict 模式应抛出 ParseError。"""
    data = b'\xfd\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError):
        archive.read_fstring()


# --- FText args 数量限制 ---

def test_ftext_named_format_arg_overflow():
    """FText NamedFormat arg_count 超限时应容错而非崩溃。"""
    from uasset_read.constants import MAX_SAFE_COUNT

    # 构造一个畸形的 FText 数据
    # format_text 是一个完整的 FText（history_type = -1, None）
    # history_type = 1 (NamedFormat)
    # arg_count = MAX_SAFE_COUNT + 1 (超限)
    data = b'\x00\x00\x00\x00'  # format_text 的 flags
    data += b'\xFF'  # format_text 的 history_type = -1 (None)
    data += b'\x00\x00\x00\x00'  # format_text 的 bHasCultureInvariantString = False
    data += (MAX_SAFE_COUNT + 1).to_bytes(4, 'little', signed=True)  # arg_count

    archive = ByteArchive(data, tolerant=True)

    # 在 tolerant 模式下应返回空字符串而非崩溃
    value, consumed = read_ftext_with_history(archive, history_type=1, tolerant=True)
    assert isinstance(value, str)


def test_ftext_named_format_negative_arg_count():
    """FText NamedFormat 负 arg_count 应容错而非崩溃。"""
    # 构造一个畸形的 FText 数据
    # format_text 是一个完整的 FText（history_type = -1, None）
    # history_type = 1 (NamedFormat)
    # arg_count = -1 (负数)
    data = b'\x00\x00\x00\x00'  # format_text 的 flags
    data += b'\xFF'  # format_text 的 history_type = -1 (None)
    data += b'\x00\x00\x00\x00'  # format_text 的 bHasCultureInvariantString = False
    data += (-1).to_bytes(4, 'little', signed=True)  # -1

    archive = ByteArchive(data, tolerant=True)

    # 在 tolerant 模式下应返回空字符串而非崩溃
    value, consumed = read_ftext_with_history(archive, history_type=1, tolerant=True)
    assert isinstance(value, str)


# --- FTEXT-SAFETY 恢复位置 ---

def test_ftext_safety_recovery_position():
    """FTEXT-SAFETY 消耗超限时应回退到字段起始位置。"""
    from uasset_read.serializers.graph_pin import _read_pin_ftext_field
    from uasset_read.constants import MAX_FTEXT_CONSUMPTION

    mock_archive = MagicMock()
    # tell() 首次返回 0（字段起始），_read_ftext_value 后返回超限值
    mock_archive.tell.side_effect = [0, MAX_FTEXT_CONSUMPTION + 100]

    # 模拟一个消耗大量字节的 FText
    def mock_read_ftext_value(archive, tolerant=True):
        return ("value", 0, 0, MAX_FTEXT_CONSUMPTION + 100)

    with patch('uasset_read.serializers.graph_pin._read_ftext_value', mock_read_ftext_value):
        trace_fields = {}
        value, success = _read_pin_ftext_field(
            mock_archive, "TestField", False, trace_fields
        )

        # 应回退到 _start（字段起始位置），而非 _start + 5
        # 验证 seek 被调用且参数为 0（_start）
        mock_archive.seek.assert_called_with(0)
