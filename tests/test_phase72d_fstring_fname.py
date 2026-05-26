"""Phase 72-D: FString/FName 区分验证测试。

测试 read_fstring() null-termination 验证逻辑替换 null_ratio 启发式，
以及 FName vs FString 读取路径正确性。
"""

import io
import pytest
import struct
import tempfile
from unittest.mock import MagicMock

from uasset_read.archive import FArchive, _contains_binary_data
from uasset_read.serializers.graph import read_ed_graph_pin_type


def _write_fstring_to_file(text: str, utf16: bool = False) -> str:
    """Write a FString binary to a temp file and return the path."""
    buf = io.BytesIO()
    if utf16:
        encoded = text.encode('utf-16-le')
        # Add null terminator (UTF-16 = 2 bytes)
        data = encoded + b'\x00\x00'
        char_count = len(text) + 1
        buf.write(struct.pack('<i', -char_count))
        buf.write(data)
    else:
        encoded = text.encode('utf-8')
        length = len(encoded) + 1  # + null terminator
        buf.write(struct.pack('<i', length))
        buf.write(encoded)
        buf.write(b'\x00')

    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
        f.write(buf.getvalue())
        return f.name


# ============================================================================
# Test 1: Short FString Not Rejected
# ============================================================================

class TestShortFStringNotRejected:
    """单字符短字符串不应被 null_ratio 启发式误杀。"""

    def test_single_char_A(self):
        path = _write_fstring_to_file("A")
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "A"
        finally:
            arch.close()

    def test_single_char_B(self):
        path = _write_fstring_to_file("B")
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "B"
        finally:
            arch.close()

    def test_single_char_C(self):
        path = _write_fstring_to_file("C")
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "C"
        finally:
            arch.close()

    def test_short_enum_value(self):
        """类似枚举名 "Byte" 这种短字符串。"""
        path = _write_fstring_to_file("Byte")
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "Byte"
        finally:
            arch.close()

    def test_empty_string(self):
        buf = struct.pack('<i', 0)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(buf)
            path = f.name
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == ""
        finally:
            arch.close()


# ============================================================================
# Test 2: Internal Null Detected
# ============================================================================

class TestInternalNullDetected:
    """包含内部 null 字节的字符串应截断返回前缀。

    Phase 72-I Wave 3: 改为截断而非返回空字符串，保留有效数据。
    """

    def test_internal_null_returns_truncated(self):
        text = "hello\x00world"
        encoded = text.encode('utf-8')
        length = len(encoded)
        buf = struct.pack('<i', length) + encoded
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(buf)
            path = f.name
        arch = FArchive(path)
        try:
            result = arch.read_fstring()
            # Phase 72-I Wave 3: 返回截断后的字符串而非空
            assert result == "hello"
        finally:
            arch.close()

    def test_internal_null_logs_warning(self, caplog):
        import logging
        text = "hello\x00world"
        encoded = text.encode('utf-8')
        length = len(encoded)
        buf = struct.pack('<i', length) + encoded
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(buf)
            path = f.name
        arch = FArchive(path)
        try:
            with caplog.at_level(logging.WARNING, logger='uasset_read.archive'):
                arch.read_fstring()
            # Phase 72-I Wave 3: 日志包含 "truncated at null"
            assert "truncated at null" in caplog.text
        finally:
            arch.close()


# ============================================================================
# Test 3: Trailing Null Stripped
# ============================================================================

class TestTrailingNullStripped:
    """末尾 null 字节应被正确 strip。"""

    def test_trailing_null_stripped(self):
        path = _write_fstring_to_file("Hello")
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "Hello"
        finally:
            arch.close()

    def test_trailing_null_stripped_long(self):
        path = _write_fstring_to_file("BP_FirstPersonCharacter_C")
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "BP_FirstPersonCharacter_C"
        finally:
            arch.close()

    def test_utf16_trailing_null_stripped(self):
        """UTF-16 路径：length < 0, data 以 b'\\x00\\x00' 结尾。"""
        path = _write_fstring_to_file("Test", utf16=True)
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "Test"
        finally:
            arch.close()


# ============================================================================
# Test 4: FName vs FString Distinction
# ============================================================================

class FArchiveMock:
    """Minimal FArchive-like wrapper around bytes for FName testing."""

    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)
        self._file_size = len(data)
        self._byte_swapping = False
        self._logger = MagicMock()

    def read(self, size: int) -> bytes:
        return self._buf.read(size)

    def seek(self, pos: int):
        self._buf.seek(pos)

    def tell(self) -> int:
        return self._buf.tell()

    def read_i32(self) -> int:
        return struct.unpack('<i', self.read(4))[0]

    def read_u32(self) -> int:
        return struct.unpack('<I', self.read(4))[0]

    def read_u8(self) -> int:
        return struct.unpack('<B', self.read(1))[0]

    def read_bool(self) -> bool:
        return self.read_u32() != 0

    def read_bytes(self, n: int) -> bytes:
        return self._buf.read(n)

    def read_name(self, name_map: list) -> str:
        index = self.read_u32()
        number = self.read_u32()
        if 0 <= index < len(name_map):
            base = name_map[index]
            if number > 0:
                return f"{base}_{number}"
            return base
        return "None"


class TestFNameVsFString:
    """FName 索引区域（小整数）不应被误读为 FString。"""

    def test_fname_reads_from_name_map(self):
        """FName 使用索引查表，不受 null_ratio 影响。"""
        name_map = ["FloatProperty", "IntProperty", "ByteProperty"]
        data = struct.pack('<II', 0, 0)
        arch = FArchiveMock(data)
        result = arch.read_name(name_map)
        assert result == "FloatProperty"

    def test_fname_index_with_instance_number(self):
        """FName index=1, number=2 -> IntProperty_2"""
        name_map = ["FloatProperty", "IntProperty"]
        data = struct.pack('<II', 1, 2)
        arch = FArchiveMock(data)
        result = arch.read_name(name_map)
        assert result == "IntProperty_2"

    def test_fname_invalid_index_returns_none(self):
        """index 超出范围 -> "None" """
        name_map = ["FloatProperty"]
        data = struct.pack('<II', 99, 0)
        arch = FArchiveMock(data)
        result = arch.read_name(name_map)
        assert result == "None"


# ============================================================================
# Test 5: PinCategory Uses read_name
# ============================================================================

class TestPinCategoryUsesReadName:
    """FEdGraphPinType 的 PinCategory/PinSubCategory 使用 FName 读取。"""

    def _build_pin_type_data(self, pin_category_idx: int, pin_sub_idx: int,
                              name_map: list, pin_object_index: int = 0) -> bytes:
        """Build minimal FEdGraphPinType binary (UE5 format)."""
        buf = io.BytesIO()
        # PinCategory (FName)
        buf.write(struct.pack('<II', pin_category_idx, 0))
        # PinSubCategory (FName)
        buf.write(struct.pack('<II', pin_sub_idx, 0))
        # PinSubCategoryObject (FPackageIndex, i32)
        buf.write(struct.pack('<i', pin_object_index))
        # ContainerType (u8)
        buf.write(struct.pack('<B', 0))
        # bIsReference (bool = u32)
        buf.write(struct.pack('<I', 0))
        # bIsWeakPointer (bool = u32)
        buf.write(struct.pack('<I', 0))
        # SimpleMemberReference: MemberParent(i32) + MemberName(FName 2*u32) + MemberGuid(16B)
        buf.write(struct.pack('<i', 0))
        buf.write(struct.pack('<II', 0, 0))
        buf.write(b'\x00' * 16)
        # bIsConst (bool = u32)
        buf.write(struct.pack('<I', 0))
        # bIsUObjectWrapper (bool = u32)
        buf.write(struct.pack('<I', 0))
        # bSerializeAsSinglePrecisionFloat (bool = u32)
        buf.write(struct.pack('<I', 0))
        return buf.getvalue()

    def test_pin_category_exec(self):
        name_map = ["exec", "int", "float", "String"]
        data = self._build_pin_type_data(0, 1, name_map)
        arch = FArchiveMock(data)
        pin_type = read_ed_graph_pin_type(arch, name_map, MagicMock(file_version_ue5=0))
        assert pin_type.pin_category == "exec"

    def test_pin_subcategory_int(self):
        name_map = ["exec", "int", "float", "String"]
        data = self._build_pin_type_data(0, 1, name_map)
        arch = FArchiveMock(data)
        pin_type = read_ed_graph_pin_type(arch, name_map, MagicMock(file_version_ue5=0))
        assert pin_type.pin_subcategory == "int"

    def test_pin_subcategory_string(self):
        name_map = ["exec", "int", "float", "String"]
        data = self._build_pin_type_data(0, 3, name_map)
        arch = FArchiveMock(data)
        pin_type = read_ed_graph_pin_type(arch, name_map, MagicMock(file_version_ue5=0))
        assert pin_type.pin_subcategory == "String"

    def test_pin_subcategory_object_zero_stays_empty(self):
        name_map = ["exec", "int", "float", "String"]
        data = self._build_pin_type_data(0, 1, name_map, pin_object_index=0)
        arch = FArchiveMock(data)

        pin_type = read_ed_graph_pin_type(arch, name_map, MagicMock(file_version_ue5=0))

        assert pin_type.pin_subcategory_object == 0
        assert pin_type.pin_subcategory_object_name is None
        assert pin_type.pin_subcategory_object_ref is None

    def test_pin_subcategory_object_preserves_positive_index(self):
        name_map = ["exec", "int", "float", "String"]
        data = self._build_pin_type_data(0, 1, name_map, pin_object_index=7)
        arch = FArchiveMock(data)

        pin_type = read_ed_graph_pin_type(arch, name_map, MagicMock(file_version_ue5=0))

        assert pin_type.pin_subcategory_object == 7
        assert pin_type.pin_subcategory_object_name is None

    def test_pin_subcategory_object_preserves_negative_index(self):
        name_map = ["exec", "int", "float", "String"]
        data = self._build_pin_type_data(0, 1, name_map, pin_object_index=-3)
        arch = FArchiveMock(data)

        pin_type = read_ed_graph_pin_type(arch, name_map, MagicMock(file_version_ue5=0))

        assert pin_type.pin_subcategory_object == -3

    def test_pin_subcategory_object_linker_resolution_is_additive(self):
        name_map = ["exec", "int", "float", "String"]
        data = self._build_pin_type_data(0, 1, name_map, pin_object_index=2)
        arch = FArchiveMock(data)
        obj = MagicMock()
        obj.object_name = "Character"
        linker = MagicMock()
        linker.resolve_package_index.return_value = obj

        pin_type = read_ed_graph_pin_type(
            arch, name_map, MagicMock(file_version_ue5=0), [], [], linker
        )

        assert pin_type.pin_subcategory_object == 2
        assert pin_type.pin_subcategory_object_name == "Character"
        assert pin_type.pin_subcategory_object_ref is obj


# ============================================================================
# Test 6: Regression
# ============================================================================

class TestRegression:
    """确保现有功能不被破坏。"""

    def test_normal_utf8_string(self):
        path = _write_fstring_to_file("Hello")
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "Hello"
        finally:
            arch.close()

    def test_utf16_string(self):
        path = _write_fstring_to_file("Test", utf16=True)
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == "Test"
        finally:
            arch.close()

    def test_contains_binary_data_still_works(self):
        """_contains_binary_data 输出检测函数保持可用。"""
        # 3 nulls in 13 chars = 0.23 < 0.3 → False
        assert _contains_binary_data("hello\x00world\x00\x00") is False
        # 5 nulls in 5 chars = 1.0 > 0.3 → True
        assert _contains_binary_data("\x00\x00\x00\x00\x00") is True
        assert _contains_binary_data("clean string") is False
        assert _contains_binary_data("") is False
        assert _contains_binary_data(None) is False

    def test_long_valid_string(self):
        text = "A" * 1000
        path = _write_fstring_to_file(text)
        arch = FArchive(path)
        try:
            assert arch.read_fstring() == text
        finally:
            arch.close()
