"""Archive 核心测试（archive/core）。

合并自：
- test_archive_coverage.py — ByteArchive 读取器、安全方法、数组读取、HexView、PackageArchive
- test_archive_serialize_bits.py — 内联 import 检测、serialize_bits 行为验证
- test_diagnostics.py — OffsetRangeDiagnostic 数据模型、FArchive 偏移诊断、PackageIR/渲染器 diagnostics
"""
from __future__ import annotations

import ast
import inspect
import json
import struct
import sys
import pytest
from io import BytesIO
from pathlib import Path

from uasset_read.archive import FArchive, ByteArchive, _contains_binary_data
from uasset_read.constants import MMAP_THRESHOLD, MAX_FSTRING_LENGTH, MAX_ARRAY_COUNT
from uasset_read.exceptions import ParseError
from uasset_read.ir_builder import build_package_ir
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    LinkerSummaryIR,
)
from uasset_read.models.result import ParseResult
from uasset_read.package import PackageArchive
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions

ARCHIVE_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "uasset_read" / "archive.py"



# === ByteArchive 读取器测试 ===

class TestByteArchive:

    """ByteArchive 内存数据读取器单元测试。"""

    def test_basic_read(self):
        """基本读取 — 从内存缓冲区读取数据。"""
        data = b'\x01\x02\x03\x04\x05'
        ar = ByteArchive(data)
        assert ar.read(3) == b'\x01\x02\x03'
        assert ar.tell() == 3
        assert ar.total_size() == 5

    def test_read_beyond_end(self):
        """读取越界 — 应抛出 ParseError。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        with pytest.raises(ParseError, match="Cannot read"):
            ar.read(10)

    def test_seek_and_read(self):
        """定位后读取 — 验证 seek 和 read 配合。"""
        data = b'\x00\x01\x02\x03\x04\x05\x06\x07'
        ar = ByteArchive(data)
        ar.seek(4)
        assert ar.tell() == 4
        assert ar.read(4) == b'\x04\x05\x06\x07'

    def test_seek_negative(self):
        """负数偏移 — 应抛出 ParseError。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        with pytest.raises(ParseError, match="Invalid offset"):
            ar.seek(-1)

    def test_seek_beyond_end(self):
        """越界偏移 — 应抛出 ParseError。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        with pytest.raises(ParseError, match="exceeds file size"):
            ar.seek(100)

    def test_read_i32(self):
        """读取 32 位整数。"""
        data = struct.pack('<i', 12345)
        ar = ByteArchive(data)
        assert ar.read_i32() == 12345

    def test_read_i32_big_endian(self):
        """大端序读取 32 位整数。"""
        data = struct.pack('>i', 12345)
        ar = ByteArchive(data)
        ar.set_byte_swapping(True)
        assert ar.read_i32() == 12345

    def test_read_u32(self):
        """读取无符号 32 位整数。"""
        data = struct.pack('<I', 0xDEADBEEF)
        ar = ByteArchive(data)
        assert ar.read_u32() == 0xDEADBEEF

    def test_read_u16(self):
        """读取无符号 16 位整数。"""
        data = struct.pack('<H', 65535)
        ar = ByteArchive(data)
        assert ar.read_u16() == 65535

    def test_read_i16(self):
        """读取有符号 16 位整数。"""
        data = struct.pack('<h', -1234)
        ar = ByteArchive(data)
        assert ar.read_i16() == -1234

    def test_read_i64(self):
        """读取 64 位整数。"""
        data = struct.pack('<q', 123456789012345)
        ar = ByteArchive(data)
        assert ar.read_i64() == 123456789012345

    def test_read_u64(self):
        """读取无符号 64 位整数。"""
        data = struct.pack('<Q', 0x123456789ABCDEF0)
        ar = ByteArchive(data)
        assert ar.read_u64() == 0x123456789ABCDEF0

    def test_read_f32(self):
        """读取 32 位浮点数。"""
        data = struct.pack('<f', 3.14159)
        ar = ByteArchive(data)
        assert abs(ar.read_f32() - 3.14159) < 0.001

    def test_read_f64(self):
        """读取 64 位浮点数。"""
        data = struct.pack('<d', 3.141592653589793)
        ar = ByteArchive(data)
        assert ar.read_f64() == pytest.approx(3.141592653589793)

    def test_read_u8(self):
        """读取无符号 8 位整数。"""
        data = b'\xff'
        ar = ByteArchive(data)
        assert ar.read_u8() == 255

    def test_read_i8(self):
        """读取有符号 8 位整数。"""
        data = b'\x80'
        ar = ByteArchive(data)
        assert ar.read_i8() == -128

    def test_read_bytes(self):
        """读取原始字节。"""
        data = b'\x01\x02\x03\x04\x05'
        ar = ByteArchive(data)
        assert ar.read_bytes(5) == data

    def test_read_bool(self):
        """读取 UE bool（4 字节 uint32）。"""
        data = struct.pack('<I', 1)
        ar = ByteArchive(data)
        assert ar.read_bool() is True

    def test_read_bool_false(self):
        """读取 UE bool false。"""
        data = struct.pack('<I', 0)
        ar = ByteArchive(data)
        assert ar.read_bool() is False

    def test_read_bool_1byte(self):
        """读取 1 字节 bool。"""
        data = b'\x01'
        ar = ByteArchive(data)
        assert ar.read_bool_1byte() is True

    def test_read_bool_1byte_false(self):
        """读取 1 字节 bool false。"""
        data = b'\x00'
        ar = ByteArchive(data)
        assert ar.read_bool_1byte() is False

    def test_peek_i32(self):
        """预读 32 位整数 — 不移动位置。"""
        data = struct.pack('<ii', 111, 222)
        ar = ByteArchive(data)
        assert ar.peek_i32() == 111
        assert ar.tell() == 0  # 位置不变

    def test_close(self):
        """关闭缓冲区 — 释放引用。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        ar.close()
        assert ar.total_size() == 0

    def test_repr(self):
        """repr 输出 — 包含缓冲区大小。"""
        data = b'\x01\x02\x03\x04\x05'
        ar = ByteArchive(data)
        assert "ByteArchive" in repr(ar)
        assert "5" in repr(ar)

    def test_tolerant_mode(self):
        """容错模式 — read_safe 返回 None 而非抛异常。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data, tolerant=True)
        result = ar.read_safe(10)
        assert result is None

    def test_diagnostics_collected(self):
        """诊断收集 — 越界操作记录诊断信息。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        ar.read_safe(10)  # 越界，应记录诊断
        diags = ar.get_diagnostics()
        assert len(diags) > 0
        assert diags[0].field == "read"

    def test_read_fstring_empty(self):
        """读取空 FString。"""
        data = struct.pack('<i', 0)  # length = 0
        ar = ByteArchive(data)
        assert ar.read_fstring() == ""

    def test_read_fstring_utf8(self):
        """读取 UTF-8 FString。"""
        text = "Hello"
        length = len(text)
        data = struct.pack('<i', length) + text.encode('utf-8') + b'\x00'
        ar = ByteArchive(data)
        assert ar.read_fstring() == "Hello"

    def test_read_fstring_utf16(self):
        """读取 UTF-16 FString。"""
        text = "Hello"
        utf16_data = text.encode('utf-16-le')
        length = -len(text)  # 负数表示 UTF-16
        data = struct.pack('<i', length) + utf16_data + b'\x00\x00'
        ar = ByteArchive(data)
        assert ar.read_fstring() == "Hello"

    def test_read_name_with_map(self):
        """使用名称表读取 FName。"""
        name_map = ["First", "Second", "Third"]
        ar = ByteArchive(struct.pack('<II', 1, 0))  # index=1, number=0
        assert ar.read_name(name_map) == "Second"

    def test_read_name_with_number(self):
        """读取带编号的 FName。"""
        name_map = ["First", "Second"]
        ar = ByteArchive(struct.pack('<II', 0, 3))  # index=0, number=3
        assert ar.read_name(name_map) == "First_3"

    def test_read_name_out_of_range(self):
        """索引越界 — 容错模式返回 'None'。"""
        name_map = ["First"]
        ar = ByteArchive(struct.pack('<II', 5, 0), tolerant=True)  # index=5 越界
        assert ar.read_name(name_map) == "None"

    def test_read_name_no_map(self):
        """无名称表 — 应抛出 ParseError。"""
        ar = ByteArchive(struct.pack('<II', 0, 0))
        with pytest.raises(ParseError, match="read_name"):
            ar.read_name()

    def test_read_name_set_cache(self):
        """通过 set_name_map 缓存名称表。"""
        name_map = ["Cached"]
        ar = ByteArchive(struct.pack('<II', 0, 0))
        ar.set_name_map(name_map)
        assert ar.read_name() == "Cached"
        assert ar.get_name_map() == name_map

    def test_serialize_int(self):
        """序列化 32 位整数。"""
        ar = ByteArchive(b'')
        result = ar.serialize_int(12345)
        assert struct.unpack('<i', result)[0] == 12345

    def test_serialize_int_big_endian(self):
        """大端序序列化 32 位整数。"""
        ar = ByteArchive(b'')
        ar.set_byte_swapping(True)
        result = ar.serialize_int(12345)
        assert struct.unpack('>i', result)[0] == 12345

    def test_serialize_bits(self):
        """序列化指定位数的值。"""
        ar = ByteArchive(b'')
        result = ar.serialize_bits(255, 8)
        assert result == b'\xff'

    def test_serialize_bits_16(self):
        """序列化 16 位值（默认 LE 模式）。"""
        ar = ByteArchive(b'')
        result = ar.serialize_bits(0x1234, 16)
        assert struct.unpack('<H', result)[0] == 0x1234

    def test_read_array(self):
        """读取数组 — 使用 element_reader 回调。"""
        data = struct.pack('<iii', 10, 20, 30)
        ar = ByteArchive(data)
        result = ar.read_array(3, lambda a: a.read_i32())
        assert result == [10, 20, 30]

    def test_read_array_empty(self):
        """读取空数组。"""
        ar = ByteArchive(b'')
        result = ar.read_array(0, lambda a: a.read_i32())
        assert result == []

    def test_read_array_negative_count(self):
        """负数元素数量 — 应抛出 ParseError。"""
        ar = ByteArchive(b'')
        with pytest.raises(ParseError, match="负数元素数量"):
            ar.read_array(-1, lambda a: a.read_i32())

    def test_read_array_exceeds_limit(self):
        """超出最大限制 — 应抛出 ParseError。"""
        ar = ByteArchive(b'')
        with pytest.raises(ParseError, match="超过最大限制"):
            ar.read_array(MAX_ARRAY_COUNT + 1, lambda a: a.read_i32())

    def test_read_bulk_array(self):
        """读取 BulkArray。"""
        data = b'\x01\x02\x03\x04\x05\x06'
        ar = ByteArchive(data)
        result = ar.read_bulk_array(2, 3)  # 2 bytes * 3 elements
        assert result == data

    def test_read_bulk_array_size_mismatch(self):
        """BulkArray 大小不匹配 — 应抛出 ParseError。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        with pytest.raises(ParseError, match="Cannot read"):
            ar.read_bulk_array(4, 2)  # 4*2=8 但只有 3 字节

    def test_read_bulk_array_negative_element_size(self):
        """负数元素大小 — 应抛出 ParseError。"""
        ar = ByteArchive(b'')
        with pytest.raises(ParseError, match="element_size.*负数"):
            ar.read_bulk_array(-1, 10)

    def test_read_bulk_array_negative_element_count(self):
        """负数元素数量 — 应抛出 ParseError。"""
        ar = ByteArchive(b'')
        with pytest.raises(ParseError, match="element_count.*负数"):
            ar.read_bulk_array(4, -1)

    def test_read_bulk_array_zero_elements(self):
        """零元素 BulkArray — 返回空字节。"""
        data = b'\x00' * 10
        ar = ByteArchive(data)
        result = ar.read_bulk_array(element_size=4, element_count=0)
        assert len(result) == 0
        assert result == b''

    def test_read_bulk_array_single_element(self):
        """单元素 BulkArray。"""
        data = b'\xAB\xCD\xEF\x01'
        ar = ByteArchive(data)
        result = ar.read_bulk_array(element_size=4, element_count=1)
        assert len(result) == 4
        assert result == data

    def test_read_bulk_array_advances_position(self):
        """读取后文件位置正确推进。"""
        data = b'\x00' * 30
        ar = ByteArchive(data)
        assert ar.tell() == 0
        ar.read_bulk_array(element_size=4, element_count=5)
        assert ar.tell() == 20

    def test_read_bulk_array_element_size_one(self):
        """element_size=1 时等价于 read(count)。"""
        data = bytes(range(10))
        ar = ByteArchive(data)
        result = ar.read_bulk_array(element_size=1, element_count=10)
        assert result == data

    def test_validate_size_negative(self):
        """validate_size 负数大小 — 容错模式返回，严格模式抛异常。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        # 严格模式
        with pytest.raises(ParseError, match="Invalid size"):
            ar.validate_size(-1, "test")
        # 容错模式
        ar._tolerant = True
        ar.validate_size(-1, "test")  # 不应抛异常

    def test_validate_size_exceeds_remaining(self):
        """validate_size 超出剩余 — 容错模式返回，严格模式抛异常。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        # 严格模式
        with pytest.raises(ParseError, match="exceeds remaining"):
            ar.validate_size(100, "test")
        # 容错模式
        ar._tolerant = True
        ar.validate_size(100, "test")  # 不应抛异常

    def test_validate_size_exceeds_max_reasonable(self):
        """validate_size 超出最大合理值。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        # 容错模式
        ar._tolerant = True
        ar.validate_size(100 * 1024 * 1024 + 1, "test")  # 不应抛异常

    def test_check_remaining_sufficient(self):
        """check_remaining 剩余足够 — 返回 True。"""
        data = b'\x01\x02\x03\x04\x05'
        ar = ByteArchive(data)
        assert ar.check_remaining(3) is True

    def test_check_remaining_insufficient(self):
        """check_remaining 剩余不足 — 返回 False 并记录诊断。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        assert ar.check_remaining(10) is False
        diags = ar.get_diagnostics()
        assert len(diags) > 0
        assert diags[0].field == "check_remaining"

    def test_seek_safe_valid(self):
        """seek_safe 有效位置 — 返回 True。"""
        data = b'\x01\x02\x03\x04\x05'
        ar = ByteArchive(data)
        assert ar.seek_safe(3) is True
        assert ar.tell() == 3

    def test_seek_safe_negative(self):
        """seek_safe 负数位置 — 返回 False 并记录诊断。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        assert ar.seek_safe(-1) is False
        diags = ar.get_diagnostics()
        assert len(diags) > 0

    def test_seek_safe_beyond_end(self):
        """seek_safe 越界位置 — 返回 False 并记录诊断。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        assert ar.seek_safe(100) is False
        diags = ar.get_diagnostics()
        assert len(diags) > 0

    def test_read_safe_negative_size(self):
        """read_safe 负数大小 — 返回 None。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        result = ar.read_safe(-1)
        assert result is None

    def test_read_safe_exceeds_remaining(self):
        """read_safe 超出剩余 — 返回 None。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        result = ar.read_safe(100)
        assert result is None

    def test_read_safe_valid(self):
        """read_safe 有效读取 — 返回数据。"""
        data = b'\x01\x02\x03\x04\x05'
        ar = ByteArchive(data)
        result = ar.read_safe(3)
        assert result == b'\x01\x02\x03'

    def test_hex_view_enabled(self):
        """HexView 启用 — 记录读取操作。"""
        data = struct.pack('<i', 42)
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        ar.read_i32("test_key")
        entries = ar.get_hex_view_entries()
        assert len(entries) > 0
        assert entries[0].key == "test_key"
        assert entries[0].type == "i32"
        assert entries[0].value == 42

    def test_hex_view_disabled(self):
        """HexView 禁用 — 不记录读取操作。"""
        data = struct.pack('<i', 42)
        ar = ByteArchive(data)
        ar.enable_hex_view(False)
        ar.read_i32("test_key")
        assert len(ar.get_hex_view_entries()) == 0

    def test_hex_view_context(self):
        """HexView 上下文 — 自动添加前缀。"""
        data = struct.pack('<i', 42)
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        ar.set_hex_view_context("Summary.")
        ar.read_i32("field")
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "Summary.field"
        ar.clear_hex_view_context()
        assert ar.get_hex_view_context() == ""

    def test_get_diagnostics_returns_copy(self):
        """get_diagnostics 返回副本 — 修改不影响内部列表。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        ar.read_safe(100)  # 触发诊断
        diags = ar.get_diagnostics()
        diags.clear()  # 清空副本
        assert len(ar.get_diagnostics()) > 0  # 内部列表不受影响

    def test_get_mmap_info(self):
        """get_mmap_info — ByteArchive 始终不使用 mmap。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        info = ar.get_mmap_info()
        assert info["used"] is False
        assert info["warning"] is None

    def test_is_byte_swapping(self):
        """is_byte_swapping — 初始状态为 False。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        assert ar.is_byte_swapping is False
        ar.set_byte_swapping(True)
        assert ar.is_byte_swapping is True

    def test_total_size(self):
        """total_size — 返回缓冲区大小。"""
        data = b'\x01\x02\x03\x04\x05'
        ar = ByteArchive(data)
        assert ar.total_size() == 5

    def test_read_u8_with_key(self):
        """read_u8 带 hex_view key。"""
        data = b'\xff'
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        result = ar.read_u8("byte_key")
        assert result == 255
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "byte_key"
        assert entries[0].type == "u8"

    def test_read_i8_with_key(self):
        """read_i8 带 hex_view key。"""
        data = b'\x80'
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        result = ar.read_i8("signed_key")
        assert result == -128
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "signed_key"

    def test_read_bytes_with_key(self):
        """read_bytes 带 hex_view key。"""
        data = b'\x01\x02\x03'
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        result = ar.read_bytes(3, "raw_key")
        assert result == data
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "raw_key"
        assert entries[0].type == "bytes"

    def test_read_bool_with_key(self):
        """read_bool 带 hex_view key。"""
        data = struct.pack('<I', 1)
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        result = ar.read_bool("bool_key")
        assert result is True
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "bool_key"
        assert entries[0].type == "bool"

    def test_read_bool_1byte_with_key(self):
        """read_bool_1byte 带 hex_view key。"""
        data = b'\x01'
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        result = ar.read_bool_1byte("bool8_key")
        assert result is True
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "bool8_key"
        assert entries[0].type == "bool8"

    def test_read_fstring_with_key(self):
        """read_fstring 带 hex_view key。"""
        text = "Test"
        length = len(text)
        data = struct.pack('<i', length) + text.encode('utf-8') + b'\x00'
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        result = ar.read_fstring("str_key")
        assert result == "Test"
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "str_key"
        assert entries[0].type == "fstring"

    def test_read_name_with_key(self):
        """read_name 带 hex_view key。"""
        name_map = ["Name"]
        data = struct.pack('<II', 0, 0)
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        result = ar.read_name(name_map, "name_key")
        assert result == "Name"
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "name_key"
        assert entries[0].type == "fname"

    def test_read_array_with_key(self):
        """read_array 带 hex_view key。"""
        data = struct.pack('<ii', 10, 20)
        ar = ByteArchive(data)
        ar.enable_hex_view(True)
        result = ar.read_array(2, lambda a: a.read_i32(), "arr_key")
        assert result == [10, 20]
        entries = ar.get_hex_view_entries()
        assert entries[0].key == "arr_key"
        assert entries[0].type == "array[2]"

    def test_empty_data(self):
        """空数据创建。"""
        ar = ByteArchive(b'')
        assert ar.total_size() == 0
        assert ar.tell() == 0

    def test_seek_backward(self):
        """向后 seek 回退。"""
        ar = ByteArchive(b'\x00\x01\x02\x03\x04')
        ar.read(3)
        ar.seek(1)
        assert ar.tell() == 1
        assert ar.read(2) == b'\x01\x02'

    def test_seek_to_start(self):
        """seek 回起始位置。"""
        ar = ByteArchive(b'\x0a\x0b\x0c')
        ar.read(3)
        ar.seek(0)
        assert ar.tell() == 0
        assert ar.read(1) == b'\x0a'

    def test_seek_to_end(self):
        """seek 到末尾 — 读取应抛出 ParseError。"""
        ar = ByteArchive(b'\x0a\x0b\x0c')
        ar.seek(3)
        assert ar.tell() == 3
        with pytest.raises(ParseError):
            ar.read(1)

    def test_repeated_seek_read(self):
        """反复 seek + read 验证稳定性。"""
        data = bytes(range(256))
        ar = ByteArchive(data)
        for i in range(0, 256, 17):
            ar.seek(i)
            assert ar.tell() == i
            val = ar.read(1)
            assert val == bytes([i])


class TestByteArchiveFromMemoryview:
    """从 memoryview 创建 ByteArchive 的测试。"""

    def test_basic_read(self):
        """从 memoryview 创建并读取数据。"""
        raw = bytearray(b'\x0a\x0b\x0c\x0d')
        mv = memoryview(raw)
        ar = ByteArchive(mv)
        assert ar.total_size() == 4
        assert ar.read(2) == b'\x0a\x0b'
        assert ar.read(2) == b'\x0c\x0d'


# ===========================================================================
# archive.py 代码质量验证测试
# ===========================================================================

class TestArchiveQuality:
    """验证 archive.py 代码质量改进。"""

    def test_archive_has_type_annotations(self):
        """FArchive 方法应有类型注解。"""
        sig = inspect.signature(FArchive.read_u32)
        assert sig.return_annotation != inspect.Parameter.empty

    def test_farchive_repr(self, tmp_path):
        """FArchive 应有可读的 repr，包含路径和文件大小。"""
        test_file = tmp_path / "test.uasset"
        test_file.write_bytes(b'\x00' * 256)
        ar = FArchive(str(test_file))
        try:
            r = repr(ar)
            assert 'FArchive' in r
            assert str(test_file) in r
            assert '256' in r
        finally:
            ar.close()


# ===========================================================================
# _contains_binary_data 函数测试
# ===========================================================================

class TestContainsBinaryData:
    """_contains_binary_data 函数单元测试。"""

    def test_empty_string(self):
        """空字符串 — 返回 False。"""
        assert _contains_binary_data("") is False

    def test_normal_string(self):
        """正常字符串 — 返回 False。"""
        assert _contains_binary_data("Hello World") is False

    def test_binary_string(self):
        """包含大量 null 的字符串 — 返回 True。"""
        binary_str = "\x00" * 100 + "abc"
        assert _contains_binary_data(binary_str) is True

    def test_mixed_string(self):
        """混合字符串 — 低于阈值返回 False。"""
        mixed_str = "Hello\x00World"
        assert _contains_binary_data(mixed_str) is False

    def test_custom_threshold(self):
        """自定义阈值 — 低于阈值返回 False。"""
        binary_str = "\x00" * 30 + "a" * 70  # 30% null
        assert _contains_binary_data(binary_str, threshold=0.5) is False

    def test_max_check_length(self):
        """最大检查长度 — 只检查前 N 个字符。"""
        # 前 10 个字符都是 null，但超过 max_check_length 后有正常字符
        binary_str = "\x00" * 10 + "a" * 256
        assert _contains_binary_data(binary_str, max_check_length=10) is True


# ===========================================================================
# PackageArchive.read() 短读校验
# ===========================================================================

class ShortReadArchive:
    """模拟短读的底层 archive。"""
    def __init__(self):
        self.pos = 0
    def read(self, size):
        return b"X"  # 总是只返回 1 字节
    def seek(self, pos):
        self.pos = pos
    def tell(self):
        return self.pos
    def close(self):
        pass
    def total_size(self):
        return 4
    def set_byte_swapping(self, enabled):
        pass


def test_package_archive_short_read_raises():
    """短读应抛 ParseError 而非静默推进位置。"""
    archive = PackageArchive(ShortReadArchive())
    with pytest.raises(ParseError, match="short read"):
        archive.read(4)


def test_package_archive_normal_read_ok():
    """正常读取应正常工作。"""
    class GoodArchive:
        def __init__(self):
            self.pos = 0
        def read(self, size):
            return b"\x00" * size
        def seek(self, pos):
            self.pos = pos
        def tell(self):
            return self.pos
        def close(self):
            pass
        def total_size(self):
            return 4
        def set_byte_swapping(self, enabled):
            pass

    archive = PackageArchive(GoodArchive())
    data = archive.read(4)
    assert len(data) == 4


# === 内联 import 检测 + serialize_bits 验证 ===

class TestNoInlineImports:

    """验证 archive.py 不包含函数体内的内联 import。"""

    @pytest.fixture(autouse=True)
    def _parse_archive(self):
        self._source = ARCHIVE_PATH.read_text(encoding="utf-8")
        self._tree = ast.parse(self._source)

    def _function_body_imports(self, module: ast.Module) -> list[tuple[str, int]]:
        """收集所有函数/方法体内的 import 语句。"""
        results = []
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Import):
                        for alias in child.names:
                            results.append((alias.name, child.lineno))
                    elif isinstance(child, ast.ImportFrom):
                        if child.module:
                            results.append((child.module, child.lineno))
        return results

    def test_no_inline_import_struct(self):
        """函数体内不应有 `import struct`。"""
        body_imports = self._function_body_imports(self._tree)
        struct_imports = [(n, l) for n, l in body_imports if n == "struct"]
        assert not struct_imports, (
            f"发现内联 `import struct`（应移至模块顶部）: {struct_imports}"
        )

    def test_no_inline_import_math(self):
        """函数体内不应有 `import math`。"""
        body_imports = self._function_body_imports(self._tree)
        math_imports = [(n, l) for n, l in body_imports if n == "math"]
        assert not math_imports, (
            f"发现内联 `import math`（应移至模块顶部）: {math_imports}"
        )

    def test_no_inline_import_os(self):
        """函数体内不应有 `__import__('os')`。"""
        source = self._source
        assert "__import__('os')" not in source and '__import__("os")' not in source, (
            "发现内联 `__import__('os')`（应改为模块顶部 `import os`）"
        )

    def test_module_level_struct_import(self):
        """模块顶部应有 `import struct`。"""
        module_imports = []
        for node in ast.iter_child_nodes(self._tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_imports.append(alias.name)
        assert "struct" in module_imports, "模块顶部缺少 `import struct`"

    def test_module_level_os_import(self):
        """模块顶部应有 `import os`。"""
        module_imports = []
        for node in ast.iter_child_nodes(self._tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_imports.append(alias.name)
        assert "os" in module_imports, "模块顶部缺少 `import os`"


# ---------------------------------------------------------------------------
# 测试 2: serialize_bits 行为验证
# ---------------------------------------------------------------------------

class TestSerializeBits:
    """验证 serialize_bits 序列化行为与 UE FArchive::SerializeBits 一致。"""

    @pytest.fixture()
    def archive_le(self):
        """创建 LE 模式 ByteArchive。"""
        # 延迟导入，避免在模块加载时触发 inline import 问题
        from uasset_read.archive import ByteArchive
        return ByteArchive(b'\x00' * 256)

    @pytest.fixture()
    def archive_be(self):
        """创建 BE 模式 ByteArchive。"""
        from uasset_read.archive import ByteArchive
        ar = ByteArchive(b'\x00' * 256)
        ar.set_byte_swapping(True)
        return ar

    def test_byte_count_8_bits(self, archive_le):
        """8 bits → 1 byte。"""
        result = archive_le.serialize_bits(0xFF, 8)
        assert len(result) == 1

    def test_byte_count_9_bits(self, archive_le):
        """9 bits → 2 bytes（向上取整）。"""
        result = archive_le.serialize_bits(0x1FF, 9)
        assert len(result) == 2

    def test_byte_count_1_bit(self, archive_le):
        """1 bit → 1 byte。"""
        result = archive_le.serialize_bits(1, 1)
        assert len(result) == 1

    def test_byte_count_16_bits(self, archive_le):
        """16 bits → 2 bytes。"""
        result = archive_le.serialize_bits(0xFFFF, 16)
        assert len(result) == 2

    def test_byte_count_32_bits(self, archive_le):
        """32 bits → 4 bytes。"""
        result = archive_le.serialize_bits(0xFFFFFFFF, 32)
        assert len(result) == 4

    def test_value_correctness_le(self, archive_le):
        """LE 模式：值应以小端序编码。"""
        result = archive_le.serialize_bits(0x0102, 16)
        assert result == b'\x02\x01'

    def test_value_correctness_be(self, archive_be):
        """BE 模式：值应以大端序编码。"""
        result = archive_be.serialize_bits(0x0102, 16)
        assert result == b'\x01\x02'

    def test_value_truncation_non_aligned(self, archive_le):
        """非字节对齐位数：高位应被截断（UE bitmask 行为）。

        UE FArchive::SerializeBits 在加载时执行:
            ((uint8*)V)[LengthBits / 8] &= ((1 << (LengthBits & 7)) - 1)

        对于 3 bits，mask = (1 << 3) - 1 = 0x07。
        值 0xFF 应被截断为 0x07（仅保留低 3 位）。
        """
        result = archive_le.serialize_bits(0xFF, 3)
        # 1 byte, 值应为 0xFF & 0x07 = 0x07
        assert result == b'\x07'

    def test_value_5_bits(self, archive_le):
        """5 bits: mask = 0x1F。"""
        result = archive_le.serialize_bits(0xFF, 5)
        assert result == b'\x1F'

    def test_value_1_bit_true(self, archive_le):
        """1 bit 值为 1。"""
        result = archive_le.serialize_bits(1, 1)
        assert result == b'\x01'

    def test_value_1_bit_zero(self, archive_le):
        """1 bit 值为 0。"""
        result = archive_le.serialize_bits(0, 1)
        assert result == b'\x00'

    def test_value_zero(self, archive_le):
        """全零值。"""
        result = archive_le.serialize_bits(0, 8)
        assert result == b'\x00'

    def test_no_math_dependency(self):
        """serialize_bits 不应依赖 math 模块（用整数除法替代）。"""
        from uasset_read.archive import ByteArchive
        # 确保方法可正常调用（不抛 ImportError）
        ar = ByteArchive(b'\x00' * 16)
        result = ar.serialize_bits(42, 7)
        assert isinstance(result, bytes)


# === 诊断相关测试 ===

class TestOffsetRangeDiagnostic:

    """OffsetRangeDiagnostic 数据模型单元测试。"""

    def test_default_instance(self):
        """默认实例化 — 所有字段使用默认值。"""
        diag = OffsetRangeDiagnostic()
        assert diag.kind == "offset_range_diagnostic"
        assert diag.asset_path == ""
        assert diag.asset_type == ""
        assert diag.module == ""
        assert diag.object_name == ""
        assert diag.export_index is None
        assert diag.import_index is None
        assert diag.field == ""
        assert diag.current_pos == 0
        assert diag.target_offset == 0
        assert diag.read_size == 0
        assert diag.file_size == 0
        assert diag.range_start is None
        assert diag.range_end is None
        assert diag.source == ""
        assert diag.error == ""
        assert diag.fallback_used is False
        assert diag.fallback_result == ""

    def test_custom_instance(self):
        """自定义实例化 — 传入所有字段。"""
        diag = OffsetRangeDiagnostic(
            kind="custom_kind",
            asset_path="/Game/Test",
            asset_type="Blueprint",
            module="linker",
            object_name="MyObject",
            export_index=3,
            import_index=7,
            field="serial_offset",
            current_pos=1024,
            target_offset=2048,
            read_size=512,
            file_size=4096,
            range_start=512,
            range_end=3000,
            source="PackageLinker",
            error="offset out of range",
            fallback_used=True,
            fallback_result="partial",
        )
        assert diag.kind == "custom_kind"
        assert diag.asset_path == "/Game/Test"
        assert diag.asset_type == "Blueprint"
        assert diag.module == "linker"
        assert diag.object_name == "MyObject"
        assert diag.export_index == 3
        assert diag.import_index == 7
        assert diag.field == "serial_offset"
        assert diag.current_pos == 1024
        assert diag.target_offset == 2048
        assert diag.read_size == 512
        assert diag.file_size == 4096
        assert diag.range_start == 512
        assert diag.range_end == 3000
        assert diag.source == "PackageLinker"
        assert diag.error == "offset out of range"
        assert diag.fallback_used is True
        assert diag.fallback_result == "partial"

    def test_to_dict_default(self):
        """to_dict() 默认实例 — 仅含 kind 和整数零值字段。"""
        diag = OffsetRangeDiagnostic()
        d = diag.to_dict()
        assert isinstance(d, dict)
        assert d["kind"] == "offset_range_diagnostic"
        # 整数字段始终输出（含 0）
        assert d["current_pos"] == 0
        assert d["target_offset"] == 0
        assert d["read_size"] == 0
        assert d["file_size"] == 0
        # 空字符串字段不输出
        assert "asset_path" not in d
        assert "module" not in d
        assert "error" not in d
        # None 字段不输出
        assert "export_index" not in d
        assert "range_start" not in d
        # False 布尔不输出
        assert "fallback_used" not in d

    def test_to_dict_full(self):
        """to_dict() 完整实例 — 所有字段均输出。"""
        diag = OffsetRangeDiagnostic(
            asset_path="/Game/Test.uasset",
            asset_type="SkeletalMesh",
            module="property",
            object_name="SK_Mannequin",
            export_index=0,
            import_index=None,
            field="serial_offset",
            current_pos=512,
            target_offset=1024,
            read_size=256,
            file_size=8192,
            range_start=0,
            range_end=1024,
            source="PropertyParser",
            error="read past end of export data",
            fallback_used=True,
            fallback_result="failed",
        )
        d = diag.to_dict()
        assert d["kind"] == "offset_range_diagnostic"
        assert d["asset_path"] == "/Game/Test.uasset"
        assert d["asset_type"] == "SkeletalMesh"
        assert d["module"] == "property"
        assert d["object_name"] == "SK_Mannequin"
        assert d["export_index"] == 0
        assert "import_index" not in d  # None 不输出
        assert d["field"] == "serial_offset"
        assert d["current_pos"] == 512
        assert d["target_offset"] == 1024
        assert d["read_size"] == 256
        assert d["file_size"] == 8192
        assert d["range_start"] == 0
        assert d["range_end"] == 1024
        assert d["source"] == "PropertyParser"
        assert d["error"] == "read past end of export data"
        assert d["fallback_used"] is True
        assert d["fallback_result"] == "failed"

    def test_to_dict_json_serializable(self):
        """to_dict() 输出可被 json.dumps 序列化。"""
        diag = OffsetRangeDiagnostic(
            asset_path="/Game/Test",
            module="kismet",
            field="CodeOffset",
            current_pos=100,
            target_offset=200,
            read_size=50,
            file_size=4000,
            fallback_used=True,
            fallback_result="success",
        )
        d = diag.to_dict()
        # 不应抛出异常
        serialized = json.dumps(d, ensure_ascii=False)
        assert isinstance(serialized, str)
        assert "offset_range_diagnostic" in serialized

    def test_to_dict_zero_export_index(self):
        """export_index=0 应输出（非 None）。"""
        diag = OffsetRangeDiagnostic(export_index=0)
        d = diag.to_dict()
        assert d["export_index"] == 0

    def test_to_dict_none_export_index(self):
        """export_index=None 不应输出。"""
        diag = OffsetRangeDiagnostic(export_index=None)
        d = diag.to_dict()
        assert "export_index" not in d

    def test_to_dict_zero_range_boundaries(self):
        """range_start=0 应输出（非 None）。"""
        diag = OffsetRangeDiagnostic(range_start=0, range_end=0)
        d = diag.to_dict()
        assert d["range_start"] == 0
        assert d["range_end"] == 0

    def test_module_values(self):
        """验证各 module 值均可正确设置和输出。"""
        for mod in ("linker", "property", "graph", "pin", "kismet", "pak", "iostore"):
            diag = OffsetRangeDiagnostic(module=mod)
            d = diag.to_dict()
            assert d["module"] == mod

    def test_field_values(self):
        """验证各 field 值均可正确设置和输出。"""
        for fld in ("serial_offset", "script_serial_offset", "ValueEndOffset", "CodeOffset", "LinkedTo"):
            diag = OffsetRangeDiagnostic(field=fld)
            d = diag.to_dict()
            assert d["field"] == fld

    def test_fallback_result_values(self):
        """验证 fallback_result 各取值。"""
        for result in ("failed", "partial", "success"):
            diag = OffsetRangeDiagnostic(fallback_result=result)
            d = diag.to_dict()
            assert d["fallback_result"] == result


# ===========================================================================
# 第二部分：FArchive 偏移诊断测试
# ===========================================================================

@pytest.fixture
def sample_archive(tmp_path):
    """创建 16 字节测试文件并返回 FArchive 实例。"""
    data = bytes(range(16))  # 0x00..0x0F
    path = tmp_path / "test.bin"
    path.write_bytes(data)
    ar = FArchive(str(path), tolerant=True)
    yield ar
    ar.close()


class TestSeekSafe:
    """seek_safe() 越界诊断。"""

    def test_seek_within_bounds_returns_true(self, sample_archive):
        """正常 seek 返回 True，不产生诊断。"""
        result = sample_archive.seek_safe(8)
        assert result is True
        assert sample_archive.tell() == 8
        assert len(sample_archive.get_diagnostics()) == 0

    def test_seek_to_zero(self, sample_archive):
        """seek 到起始位置。"""
        assert sample_archive.seek_safe(0) is True

    def test_seek_to_eof(self, sample_archive):
        """seek 到文件末尾（合法）。"""
        assert sample_archive.seek_safe(16) is True

    def test_seek_beyond_eof_records_diagnostic(self, sample_archive):
        """seek 超出文件大小产生诊断。"""
        result = sample_archive.seek_safe(100)
        assert result is False
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        d = diags[0]
        assert d.field == "seek"
        assert d.target_offset == 100
        assert d.file_size == 16
        assert "超出文件范围" in d.error

    def test_seek_negative_records_diagnostic(self, sample_archive):
        """seek 负偏移产生诊断。"""
        result = sample_archive.seek_safe(-1)
        assert result is False
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        assert diags[0].target_offset == -1

    def test_seek_preserves_position_on_failure(self, sample_archive):
        """seek 失败后位置不变。"""
        sample_archive.seek_safe(4)
        sample_archive.seek_safe(100)
        assert sample_archive.tell() == 4

    def test_seek_context_recorded(self, sample_archive):
        """context 参数记录到诊断中。"""
        sample_archive.seek_safe(100, context="test_phase")
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "test_phase"

    def test_seek_default_context(self, sample_archive):
        """无 context 时使用默认值。"""
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "seek_safe"


class TestReadSafe:
    """read_safe() 越界诊断。"""

    def test_read_within_bounds_returns_data(self, sample_archive):
        """正常 read 返回数据，不产生诊断。"""
        data = sample_archive.read_safe(4)
        assert data is not None
        assert len(data) == 4
        assert len(sample_archive.get_diagnostics()) == 0

    def test_read_exact_remaining(self, sample_archive):
        """读取恰好剩余的字节数。"""
        sample_archive.seek_safe(12)
        data = sample_archive.read_safe(4)
        assert data is not None
        assert len(data) == 4

    def test_read_beyond_remaining_records_diagnostic(self, sample_archive):
        """请求超出剩余字节产生诊断并返回 None。"""
        sample_archive.seek_safe(12)
        data = sample_archive.read_safe(8)
        assert data is None
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 1
        d = diags[0]
        assert d.field == "read"
        assert d.read_size == 8
        assert "仅剩 4 字节" in d.error

    def test_read_negative_size_records_diagnostic(self, sample_archive):
        """负大小产生诊断。"""
        data = sample_archive.read_safe(-1)
        assert data is None
        d = sample_archive.get_diagnostics()[0]
        assert d.read_size == -1
        assert "负数" in d.error

    def test_read_at_eof_records_diagnostic(self, sample_archive):
        """在 EOF 处读取产生诊断。"""
        sample_archive.seek_safe(16)
        data = sample_archive.read_safe(1)
        assert data is None
        d = sample_archive.get_diagnostics()[0]
        assert d.read_size == 1
        assert d.current_pos == 16

    def test_read_context_recorded(self, sample_archive):
        """context 参数记录到诊断中。"""
        sample_archive.read_safe(100, context="export_parse")
        d = sample_archive.get_diagnostics()[0]
        assert d.source == "export_parse"


class TestDiagnosticAccumulation:
    """多次诊断累积。"""

    def test_multiple_diagnostics_accumulated(self, sample_archive):
        """多次越界操作累积诊断记录。"""
        sample_archive.seek_safe(100, context="s1")
        sample_archive.seek_safe(200, context="s2")
        sample_archive.read_safe(50, context="r1")
        diags = sample_archive.get_diagnostics()
        assert len(diags) == 3

    def test_diagnostics_returns_copy(self, sample_archive):
        """get_diagnostics() 返回副本。"""
        sample_archive.seek_safe(100)
        diags = sample_archive.get_diagnostics()
        diags.clear()
        assert len(sample_archive.get_diagnostics()) == 1

    def test_no_diagnostics_for_clean_session(self, sample_archive):
        """正常操作不产生任何诊断。"""
        sample_archive.seek_safe(0)
        sample_archive.read_safe(8)
        sample_archive.seek_safe(4)
        sample_archive.read_safe(4)
        assert len(sample_archive.get_diagnostics()) == 0


class TestDiagnosticFields:
    """诊断记录字段完整性。"""

    def test_seek_diagnostic_fields(self, sample_archive):
        """seek 诊断包含所有必要字段。"""
        sample_archive.seek_safe(4)
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        assert d.module == "archive"
        assert d.current_pos == 4
        assert d.target_offset == 100
        assert d.file_size == 16

    def test_read_diagnostic_fields(self, sample_archive):
        """read 诊断包含所有必要字段。"""
        sample_archive.seek_safe(14)
        sample_archive.read_safe(8)
        d = sample_archive.get_diagnostics()[0]
        assert d.module == "archive"
        assert d.current_pos == 14
        assert d.read_size == 8
        assert d.file_size == 16

    def test_diagnostic_to_dict(self, sample_archive):
        """诊断可序列化为字典。"""
        sample_archive.seek_safe(100)
        d = sample_archive.get_diagnostics()[0]
        d_dict = d.to_dict()
        assert isinstance(d_dict, dict)
        assert d_dict["kind"] == "offset_range_diagnostic"
        assert d_dict["field"] == "seek"


# ===========================================================================
# 辅助工厂（diagnostics 测试）
# ===========================================================================


def _make_header() -> PackageHeaderIR:
    """创建最小 PackageHeaderIR。"""
    return PackageHeaderIR(
        package_name="/Game/Test",
        package_class="Blueprint",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.1",
    )


def _make_package_ir(diagnostics: list | None = None) -> PackageIR:
    """创建最小 PackageIR，可选注入 diagnostics。"""
    return PackageIR(
        header=_make_header(),
        name_map=[],
        imports=[],
        exports=[],
        linker=None,
        diagnostics=diagnostics or [],
    )


def _make_diagnostic(**overrides) -> OffsetRangeDiagnostic:
    """创建一个 OffsetRangeDiagnostic 实例，支持部分字段覆盖。"""
    defaults = dict(
        kind="offset_range_diagnostic",
        asset_path="/Game/Test",
        asset_type="Blueprint",
        module="graph",
        object_name="TestGraph",
        field="script_serial_offset",
        current_pos=100,
        target_offset=200,
        read_size=50,
        file_size=1024,
        error="offset out of range",
    )
    defaults.update(overrides)
    return OffsetRangeDiagnostic(**defaults)


# ===========================================================================
# 第三部分：PackageIR.diagnostics 字段测试
# ===========================================================================

class TestPackageIRDiagnostics:
    """验证 PackageIR 拥有 diagnostics 字段且行为正确。"""

    def test_default_empty(self):
        """默认 diagnostics 应为空列表。"""
        ir = _make_package_ir()
        assert ir.diagnostics == []

    def test_accepts_list(self):
        """diagnostics 可以接受 OffsetRangeDiagnostic 列表。"""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        assert len(ir.diagnostics) == 1
        assert ir.diagnostics[0].kind == "offset_range_diagnostic"

    def test_field_independent(self):
        """不同实例的 diagnostics 互不影响（field default_factory 隔离）。"""
        ir1 = _make_package_ir()
        ir2 = _make_package_ir()
        ir1.diagnostics.append(_make_diagnostic())
        assert len(ir1.diagnostics) == 1
        assert len(ir2.diagnostics) == 0


class TestBuildPackageIRDiagnostics:
    """验证 build_package_ir 正确传递 diagnostics。"""

    def test_empty_diagnostics(self):
        """ParseResult.diagnostics 为空时，PackageIR.diagnostics 也为空。"""
        result = ParseResult(is_success=True)
        ir = build_package_ir(result)
        assert ir.diagnostics == []

    def test_passes_diagnostics(self):
        """ParseResult.diagnostics 非空时，PackageIR.diagnostics 包含相同元素。"""
        diag = _make_diagnostic()
        result = ParseResult(is_success=True, diagnostics=[diag])
        ir = build_package_ir(result)
        assert len(ir.diagnostics) == 1
        assert ir.diagnostics[0].kind == "offset_range_diagnostic"

    def test_none_diagnostics(self):
        """ParseResult.diagnostics 为 None 时，PackageIR.diagnostics 为空列表。"""
        result = ParseResult(is_success=True)
        result.diagnostics = None
        ir = build_package_ir(result)
        assert ir.diagnostics == []


# ===========================================================================
# 第四部分：渲染器 diagnostics 输出测试
# ===========================================================================

class TestJSONRendererDiagnostics:
    """验证 JSONRenderer 输出 diagnostics 数组。"""

    def _render(self, ir: PackageIR) -> dict:
        renderer = JSONRenderer()
        options = RenderOptions(output_level="debug")
        raw = renderer.render(ir, options)
        return json.loads(raw)

    def test_no_diagnostics_key_when_empty(self):
        """无诊断时 JSON 不包含 diagnostics 键。"""
        ir = _make_package_ir()
        data = self._render(ir)
        assert "diagnostics" not in data

    def test_diagnostics_array_present(self):
        """有诊断时 JSON 包含 diagnostics 数组。"""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        data = self._render(ir)
        assert "diagnostics" in data
        assert isinstance(data["diagnostics"], list)
        assert len(data["diagnostics"]) == 1

    def test_diagnostic_fields_serialized(self):
        """诊断条目应包含 kind、module、field、error 等关键字段。"""
        diag = _make_diagnostic(module="kismet", field="CodeOffset", error="overflow")
        ir = _make_package_ir(diagnostics=[diag])
        data = self._render(ir)
        entry = data["diagnostics"][0]
        assert entry["kind"] == "offset_range_diagnostic"
        assert entry["module"] == "kismet"
        assert entry["field"] == "CodeOffset"
        assert entry["error"] == "overflow"

    def test_multiple_diagnostics(self):
        """多条诊断应全部输出。"""
        d1 = _make_diagnostic(module="graph")
        d2 = _make_diagnostic(module="pin", object_name="PinA")
        ir = _make_package_ir(diagnostics=[d1, d2])
        data = self._render(ir)
        assert len(data["diagnostics"]) == 2
        assert data["diagnostics"][0]["module"] == "graph"
        assert data["diagnostics"][1]["module"] == "pin"


class TestMarkdownRendererDiagnostics:
    """验证 MarkdownRenderer 输出诊断信息表格。"""

    def _render(self, ir: PackageIR) -> str:
        renderer = MarkdownRenderer()
        options = RenderOptions()
        return renderer.render(ir, options)

    def test_no_diagnostics_section_when_empty(self):
        """无诊断时 Markdown 不包含诊断信息章节。"""
        ir = _make_package_ir()
        md = self._render(ir)
        assert "诊断信息" not in md

    def test_diagnostics_section_present(self):
        """有诊断时 Markdown 包含诊断信息章节。"""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        md = self._render(ir)
        assert "## 诊断信息" in md

    def test_diagnostics_table_header(self):
        """诊断信息章节包含表头行。"""
        diag = _make_diagnostic()
        ir = _make_package_ir(diagnostics=[diag])
        md = self._render(ir)
        assert "| 类型 | 模块 | 对象名 | 字段 | 错误信息 |" in md

    def test_diagnostics_table_row_content(self):
        """诊断表格行包含正确的字段值。"""
        diag = _make_diagnostic(module="linker", error="invalid index")
        ir = _make_package_ir(diagnostics=[diag])
        md = self._render(ir)
        assert "linker" in md
        assert "invalid index" in md
