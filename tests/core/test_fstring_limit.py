"""FString 超长声明长度诊断增强测试 (#413)

验证 read_fstring() 对声明长度超过 MAX_FSTRING_LENGTH 的检测和容错行为：
- UTF-8: length > MAX_FSTRING_LENGTH
- UTF-16: -length*2 > MAX_FSTRING_LENGTH
- strict/tolerant 两种模式的表现差异
- 诊断信息包含 position, length, max, ratio
"""
import struct
import pytest
from uasset_read.archive import ByteArchive, MAX_FSTRING_LENGTH
from uasset_read.exceptions import ParseError


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
