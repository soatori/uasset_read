"""
archive.py 覆盖率补充测试

覆盖以下关键路径：
- ByteArchive 内存读取器
- seek_safe / read_safe 安全方法
- check_remaining 截断检测
- read_array / read_bulk_array 数组读取
- serialize_int / serialize_bits 序列化
- read_bool / read_bool_1byte 布尔读取
- validate_size 容错模式
- read_name 名称表缓存
- _contains_binary_data 二进制检测
"""
from __future__ import annotations

import inspect
import struct
import pytest
from io import BytesIO

from uasset_read.archive import FArchive, ByteArchive, _contains_binary_data
from uasset_read.constants import MMAP_THRESHOLD, MAX_FSTRING_LENGTH, MAX_ARRAY_COUNT
from uasset_read.exceptions import ParseError
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.package import PackageArchive


# ===========================================================================
# ByteArchive 内存读取器测试
# ===========================================================================

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
