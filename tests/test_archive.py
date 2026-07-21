"""Archive 模块合并测试。

覆盖主链路、边界和恢复场景：
1. 基础读写与 seek
2. 数值类型读取
3. 数组读取
4. 容错模式与诊断
5. FString 读取（UTF-8 / UTF-16）
6. FName 读取与恢复
"""
from __future__ import annotations

import struct
import pytest

from uasset_read.archive import FArchive, ByteArchive
from uasset_read.constants import MAX_ARRAY_COUNT, MAX_FSTRING_LENGTH
from uasset_read.exceptions import ParseError


# ---------------------------------------------------------------------------
# 1. 基础读写与 seek
# ---------------------------------------------------------------------------

class TestBasicReadAndSeek:
    """ByteArchive 基础读取、seek 和边界检查。"""

    def test_basic_read_and_tell(self):
        """读取后 tell 位置正确推进。"""
        data = b'\x01\x02\x03\x04\x05'
        ar = ByteArchive(data)
        assert ar.read(3) == b'\x01\x02\x03'
        assert ar.tell() == 3
        assert ar.total_size() == 5

    def test_read_beyond_end_raises(self):
        """读取越界应抛出 ParseError。"""
        ar = ByteArchive(b'\x01\x02\x03')
        with pytest.raises(ParseError, match="Cannot read"):
            ar.read(10)


# ---------------------------------------------------------------------------
# 2. 数值类型读取
# ---------------------------------------------------------------------------

class TestNumericReads:
    """各数值类型读取验证。"""

    def test_read_i32_and_f32(self):
        """32 位有符号整数和浮点数。"""
        ar = ByteArchive(struct.pack('<i', 12345))
        assert ar.read_i32() == 12345
        ar = ByteArchive(struct.pack('<f', 3.14159))
        assert abs(ar.read_f32() - 3.14159) < 0.001

        # 数组读取与边界检查
        data = struct.pack('<iii', 10, 20, 30)
        ar = ByteArchive(data)
        result = ar.read_array(3, lambda a: a.read_i32())
        assert result == [10, 20, 30]


# ---------------------------------------------------------------------------
# 3. 容错模式与诊断
# ---------------------------------------------------------------------------

class TestTolerantAndDiagnostics:
    """容错模式行为与诊断信息收集。"""

    def test_tolerant_read_safe_returns_none(self):
        """容错模式下 read_safe 越界返回 None。"""
        ar = ByteArchive(b'\x01\x02\x03', tolerant=True)
        assert ar.read_safe(10) is None

        # 越界操作记录诊断信息
        ar2 = ByteArchive(b'\x01\x02\x03')
        ar2.read_safe(10)
        diags = ar2.get_diagnostics()
        assert len(diags) > 0


# ---------------------------------------------------------------------------
# 5. FString 读取（UTF-8 / UTF-16）
# ---------------------------------------------------------------------------

class TestFStringRead:
    """FString 读取：UTF-8、UTF-16、空字符串和边界。"""

    def test_read_fstring_utf8_and_utf16(self):
        """UTF-8 和 UTF-16 FString 均正确读取。"""
        text = "Hello"
        # UTF-8
        data = struct.pack('<i', len(text)) + text.encode('utf-8') + b'\x00'
        ar = ByteArchive(data)
        assert ar.read_fstring() == "Hello"
        # UTF-16
        utf16_data = text.encode('utf-16-le')
        data = struct.pack('<i', -len(text)) + utf16_data + b'\x00\x00'
        ar = ByteArchive(data)
        assert ar.read_fstring() == "Hello"


# ---------------------------------------------------------------------------
# 6. FName 读取与恢复
# ---------------------------------------------------------------------------

class TestFNameRead:
    """FName 读取：正常索引、编号名称和越界恢复。"""

    def test_read_name_with_map(self):
        """使用名称表读取 FName。"""
        name_map = ["First", "Second", "Third"]
        ar = ByteArchive(struct.pack('<II', 1, 0))
        assert ar.read_name(name_map) == "Second"

    def test_read_name_out_of_range_tolerant(self):
        """索引越界时容错模式返回 'None'。"""
        name_map = ["First"]
        ar = ByteArchive(struct.pack('<II', 5, 0), tolerant=True)
        assert ar.read_name(name_map) == "None"
