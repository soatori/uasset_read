"""parsers 属性边界测试 — 合并自 test_property_size_validation / test_max_reasonable。

验证：
1. validate_size 在 size > remaining / 负值 / max_reasonable 超限时的行为
2. read_property_tag 的 size_exceeded 标志
3. parse_properties_from_export 处理 size_exceeded tag
4. get_max_reasonable 动态阈值（UE5 大型属性类型）
"""
from __future__ import annotations

import struct
import tempfile
import os
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.serializers.property_tags import read_property_tag
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.constants import (
    get_max_reasonable,
    MAX_REASONABLE_CAP,
    UE5_LARGE_PROPERTY_MAX_REASONABLE,
)


# ============================================================================
# 辅助工厂
# ============================================================================

def _make_archive(data: bytes, tolerant: bool = False) -> FArchive:
    """从原始字节创建 FArchive 实例（用于测试）。"""
    archive = FArchive.__new__(FArchive)
    archive._stream = BytesIO(data)
    archive._file_size = len(data)
    archive._byte_swapping = False
    archive._use_mmap = False
    archive._mmap = None
    archive._tolerant = tolerant
    archive._file = BytesIO(data)
    archive._hex_view_enabled = False
    archive._hex_view_entries = []
    archive._hex_view_context = ""
    archive._diagnostics = []
    archive._logger = __import__("logging").getLogger("test")
    archive._name_map = None
    return archive


def _make_export(serial_offset: int = 0, serial_size: int = 1024) -> ObjectExport:
    """创建测试用 ObjectExport。"""
    return ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(-1),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=serial_size,
        serial_offset=serial_offset,
    )


# ============================================================================
# validate_size 记录诊断测试
# ============================================================================

class TestValidateSizeRecordsDiagnostic:
    """validate_size 在 size > remaining 时应记录诊断。"""

    def test_tolerant_records_diagnostic_on_size_exceeded(self):
        """tolerant 模式: size > remaining 时应记录诊断并返回 False。"""
        # 仅 4 字节数据，但 validate_size 检查 size=100 > remaining=4
        data = b"\x00" * 4
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        result = archive.validate_size(100, "TestProp", tolerant=True)

        assert result is False
        assert len(archive._diagnostics) >= 1
        diag = archive._diagnostics[-1]
        assert "exceeds remaining" in diag.error
        assert "TestProp" in diag.error

    def test_tolerant_records_diagnostic_on_negative_size(self):
        """tolerant 模式: 负数 size 时应记录诊断并返回 False。"""
        data = b"\x00" * 4
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        result = archive.validate_size(-1, "TestProp", tolerant=True)

        assert result is False
        assert len(archive._diagnostics) >= 1
        diag = archive._diagnostics[-1]
        assert "negative" in diag.error

    def test_tolerant_records_diagnostic_on_max_reasonable_exceeded(self):
        """tolerant 模式: size > max_reasonable 时应记录诊断并返回 False。"""
        # 1MB 文件，size=200KB 超过 max_reasonable (file_size // 10 = 100KB)
        # 但 size < remaining (1MB)，所以会到达 max_reasonable 检查
        data = b"\x00" * (1024 * 1024)
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 0

        result = archive.validate_size(200 * 1024, "TestProp", tolerant=True)

        assert result is False
        assert len(archive._diagnostics) >= 1
        diag = archive._diagnostics[-1]
        assert "max_reasonable" in diag.error

    def test_valid_size_returns_true(self):
        """有效 size 应返回 True 且不记录诊断。"""
        data = b"\x00" * 1024
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 0

        result = archive.validate_size(100, "TestProp", tolerant=True)

        assert result is True
        assert len(archive._diagnostics) == 0


# ============================================================================
# validate_size strict 模式测试
# ============================================================================

class TestValidateSizeStrictRaises:
    """strict 模式下 size 验证失败应抛出 ParseError。"""

    def test_strict_raises_on_size_exceeded(self):
        """strict 模式: size > remaining 时应抛出 ParseError。"""
        data = b"\x00" * 4
        archive = _make_archive(data, tolerant=False)
        archive._file_version_ue5 = 1012

        with pytest.raises(ParseError, match="exceeds remaining"):
            archive.validate_size(100, "TestProp", tolerant=False)

    def test_strict_raises_on_negative_size(self):
        """strict 模式: 负数 size 时应抛出 ParseError。"""
        data = b"\x00" * 4
        archive = _make_archive(data, tolerant=False)
        archive._file_version_ue5 = 1012

        with pytest.raises(ParseError, match="negative"):
            archive.validate_size(-1, "TestProp", tolerant=False)


# ============================================================================
# read_property_tag size_exceeded 测试
# ============================================================================

class TestReadPropertyTagSizeExceeded:
    """read_property_tag 在 size 超过剩余字节时应标记 size_exceeded。"""

    def test_tolerant_sets_size_exceeded_flag(self):
        """tolerant 模式: size > remaining 时 tag.size_exceeded 应为 True。"""
        # UE5 >= 1012 格式:
        # Name: FName (8 bytes: index=0, number=0)
        # Type: FPropertyTypeName = FName (8 bytes) + inner_count (4 bytes) = 12 bytes
        # Size: i32 (4 bytes)
        # Total: 24 bytes
        name_bytes = struct.pack("<II", 0, 0)  # FName: index=0, number=0
        type_bytes = struct.pack("<II", 0, 0)  # FName: index=0, number=0
        inner_count = struct.pack("<i", 0)      # inner_count = 0 (no children)
        size_bytes = struct.pack("<i", 1000)    # size = 1000 (远大于剩余 0 字节)
        data = name_bytes + type_bytes + inner_count + size_bytes
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        tag = read_property_tag(archive, ["TestProp"], tolerant=True)

        assert tag.size_exceeded is True
        assert tag.size == 1000
        # 不应尝试读取 flags（否则会失败）
        assert tag.serialize_type == "Property"

    def test_tolerant_skips_flags_reading(self):
        """tolerant 模式: size 超过后不应读取 flags/array_index 等字段。"""
        name_bytes = struct.pack("<II", 0, 0)  # FName: index=0, number=0
        type_bytes = struct.pack("<II", 0, 0)  # FName: index=0, number=0
        inner_count = struct.pack("<i", 0)      # inner_count = 0
        size_bytes = struct.pack("<i", 1000)    # size = 1000
        data = name_bytes + type_bytes + inner_count + size_bytes
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        tag = read_property_tag(archive, ["TestProp"], tolerant=True)

        # archive 位置不应超过 name(8) + type(8+4) + size(4) = 24
        assert archive.tell() == 24

    def test_valid_size_sets_size_exceeded_false(self):
        """有效 size 时 tag.size_exceeded 应为 False。"""
        name_bytes = struct.pack("<II", 0, 0)  # FName: index=0, number=0
        type_bytes = struct.pack("<II", 0, 0)  # FName: index=0, number=0
        inner_count = struct.pack("<i", 0)      # inner_count = 0
        size_bytes = struct.pack("<i", 4)       # size = 4
        flags_bytes = b"\x00"                   # flags = 0
        value_bytes = b"\x00" * 4               # 4 字节 value 数据
        data = name_bytes + type_bytes + inner_count + size_bytes + flags_bytes + value_bytes
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        tag = read_property_tag(archive, ["TestProp"], tolerant=True)

        assert tag.size_exceeded is False
        assert tag.size == 4


# ============================================================================
# parse_properties_from_export size_exceeded 测试
# ============================================================================

class TestParsePropertiesSizeExceeded:
    """parse_properties_from_export 正确处理 size_exceeded tag。"""

    def test_tolerant_creates_fallback_for_size_exceeded(self):
        """tolerant 模式: size 超过时应创建 PropertyFallback。"""
        # 构造一个小文件，属性 tag 声明的 size 超过文件剩余字节
        # parse_properties_from_export 会先读取 1 字节 SerializationControl (UE5 >= 1011)
        # 然后读取 PropertyTag: Name(8) + Type(12) + Size(4)
        serialization_control = b"\x00"           # 1 byte: SerializationControl
        name_bytes = struct.pack("<II", 0, 0)     # FName: index=0, number=0
        type_bytes = struct.pack("<II", 0, 0)     # FName: index=0, number=0
        inner_count = struct.pack("<i", 0)         # inner_count = 0
        size_bytes = struct.pack("<i", 1000)       # size = 1000 (远大于剩余字节)
        data = serialization_control + name_bytes + type_bytes + inner_count + size_bytes
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012

        export = _make_export(serial_offset=0, serial_size=100)

        result = parse_properties_from_export(
            export, archive, summary,
            name_map=["TestProp"],
            export_map=[],
            tolerant=True,
        )

        assert isinstance(result, list)
        assert len(result) >= 1
        prop = result[0]
        assert isinstance(prop, PropertyValue)
        assert prop.name == "TestProp"
        assert isinstance(prop.value, PropertyFallback)
        assert prop.value.reason == FallbackReason.SIZE_EXCEEDED
        assert "exceeds remaining" in prop.value.error_message

    def test_strict_raises_on_size_exceeded(self):
        """strict 模式: size 超过时应抛出 ParseError。"""
        serialization_control = b"\x00"           # 1 byte: SerializationControl
        name_bytes = struct.pack("<II", 0, 0)     # FName: index=0, number=0
        type_bytes = struct.pack("<II", 0, 0)     # FName: index=0, number=0
        inner_count = struct.pack("<i", 0)         # inner_count = 0
        size_bytes = struct.pack("<i", 1000)       # size = 1000
        data = serialization_control + name_bytes + type_bytes + inner_count + size_bytes
        archive = _make_archive(data, tolerant=False)
        archive._file_version_ue5 = 1012

        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012

        export = _make_export(serial_offset=0, serial_size=100)

        with pytest.raises(ParseError, match="exceeds remaining"):
            parse_properties_from_export(
                export, archive, summary,
                name_map=["TestProp"],
                export_map=[],
                tolerant=False,
            )


# ============================================================================
# max_reasonable 动态阈值测试
# ============================================================================

class TestGetMaxReasonable:
    """get_max_reasonable 动态阈值函数测试。"""

    def test_default_property_returns_standard_cap(self):
        """普通属性类型返回默认阈值。"""
        result = get_max_reasonable("IntProperty", engine_version=5)
        assert result == MAX_REASONABLE_CAP

    def test_struct_property_returns_standard_cap(self):
        """StructProperty 返回默认阈值（非已知大型类型）。"""
        result = get_max_reasonable("StructProperty", engine_version=5)
        assert result == MAX_REASONABLE_CAP

    def test_bone_animation_tracks_allows_large_size(self):
        """UE5 BoneAnimationTracks 应允许更大的属性大小。"""
        result = get_max_reasonable("BoneAnimationTracks", engine_version=5)
        assert result == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_pose_container_allows_large_size(self):
        """UE5 PoseContainer 应允许更大的属性大小。"""
        result = get_max_reasonable("PoseContainer", engine_version=5)
        assert result == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_array_connection_map_allows_large_size(self):
        """UE5 ArrayConnectionMap 应允许更大的属性大小。"""
        result = get_max_reasonable("ArrayConnectionMap", engine_version=5)
        assert result == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_rigvm_allows_large_size(self):
        """UE5 RigVM 应允许更大的属性大小。"""
        result = get_max_reasonable("RigVM", engine_version=5)
        assert result == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_ue4_large_type_still_uses_standard_cap(self):
        """UE4 版本即使类型在大型列表中，也应使用标准阈值。"""
        result = get_max_reasonable("BoneAnimationTracks", engine_version=4)
        assert result == MAX_REASONABLE_CAP

    def test_ue5_non_large_type_uses_standard_cap(self):
        """UE5 版本但非大型类型，应使用标准阈值。"""
        result = get_max_reasonable("SomeOtherType", engine_version=5)
        assert result == MAX_REASONABLE_CAP

    def test_engine_version_zero_uses_standard_cap(self):
        """engine_version=0 时使用标准阈值。"""
        result = get_max_reasonable("BoneAnimationTracks", engine_version=0)
        assert result == MAX_REASONABLE_CAP

    def test_large_property_max_is_500mb(self):
        """大型属性阈值应为 500MB。"""
        assert UE5_LARGE_PROPERTY_MAX_REASONABLE == 500 * 1024 * 1024

    def test_standard_cap_is_100mb(self):
        """标准阈值应为 100MB。"""
        assert MAX_REASONABLE_CAP == 100 * 1024 * 1024


class TestValidateSizeWithPropertyType:
    """validate_size 带属性类型的动态阈值测试。"""

    def test_validate_size_accepts_large_struct(self):
        """validate_size 对已知大型属性类型应接受超过标准阈值的大小。"""
        # 创建临时文件模拟大文件
        file_size = 600 * 1024 * 1024  # 600MB
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * min(file_size, 1024))  # 实际写入少量数据
            temp_path = f.name

        try:
            archive = FArchive(temp_path, tolerant=False)
            # 手动设置文件大小以模拟大文件
            archive._file_size = file_size
            # 设置引擎版本为 UE5
            archive._file_version_ue5 = 5

            # 对于大型属性类型，500MB 应该通过验证
            # 注意：剩余空间检查会先于 max_reasonable 检查，所以需要模拟剩余空间足够大
            archive.validate_size(
                500 * 1024 * 1024,  # 500MB
                context="TestProp",
                tolerant=False,
                property_type="BoneAnimationTracks",
            )
            # 不应抛出异常
        finally:
            archive.close()
            os.unlink(temp_path)

    def test_validate_size_rejects_large_normal_property(self):
        """validate_size 对普通属性类型应拒绝超过标准阈值的大小。"""
        # 创建临时文件模拟大文件
        file_size = 600 * 1024 * 1024  # 600MB
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * min(file_size, 1024))
            temp_path = f.name

        try:
            archive = FArchive(temp_path, tolerant=False)
            archive._file_size = file_size
            # 设置引擎版本为 UE5
            archive._file_version_ue5 = 5

            # 对于普通属性类型，500MB 应该超过标准阈值
            # 注意：剩余空间检查会先于 max_reasonable 检查，所以需要模拟剩余空间足够大
            try:
                archive.validate_size(
                    500 * 1024 * 1024,  # 500MB
                    context="TestProp",
                    tolerant=False,
                    property_type="IntProperty",
                )
                # 应该抛出异常
                assert False, "应抛出 ParseError"
            except ParseError as e:
                assert "max_reasonable" in str(e)
        finally:
            archive.close()
            os.unlink(temp_path)
