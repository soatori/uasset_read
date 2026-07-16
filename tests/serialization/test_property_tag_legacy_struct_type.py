"""PropertyTag legacy path struct_type ordering 测试 — 验证 #404 修复。

验证:
1. legacy path (file_version_ue5 < 1012) 中 validate_size 在 struct_type 赋值后调用
2. StructProperty 的 struct_type 正确传递给 validate_size 用于动态阈值
3. 非 StructProperty 类型不受影响
"""
from __future__ import annotations

import struct
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag
from uasset_read.serializers.property_tags import read_property_tag


def _make_archive(data: bytes, file_version_ue5: int = 1000) -> FArchive:
    """从原始字节创建 FArchive 实例（用于测试 legacy path）。"""
    archive = FArchive.__new__(FArchive)
    archive._stream = BytesIO(data)
    archive._file_size = len(data)
    archive._byte_swapping = False
    archive._use_mmap = False
    archive._mmap = None
    archive._tolerant = False
    archive._file = BytesIO(data)
    archive._hex_view_enabled = False
    archive._hex_view_entries = []
    archive._hex_view_context = ""
    archive._diagnostics = []
    archive._logger = __import__("logging").getLogger("test")
    archive._name_map = None
    archive._file_version_ue5 = file_version_ue5
    return archive


def _build_legacy_struct_property_tag(
    name_index: int = 0,
    type_index: int = 0,
    size: int = 100,
    struct_name: str = "TestStruct",
    name_map: list[str] | None = None,
) -> bytes:
    """构建 legacy path (file_version_ue5 < 1012) 的 StructProperty tag 二进制数据。

    Legacy 格式:
    - Name: FName (index=4 bytes + number=4 bytes)
    - Type: FName (index=4 bytes + number=4 bytes)
    - Size: int32
    - ArrayIndex: int32 (旧格式始终存在)
    - Type.number == 0 时的类型特定字段:
      - StructProperty: StructName (FName) + StructGuid (FGuid, 16 bytes)
    - HasPropertyGuid: uint8
    - (可选) PropertyGuid: 16 bytes
    """
    if name_map is None:
        name_map = ["TestProp", "StructProperty", struct_name]

    # Name: FName (index, number)
    name_bytes = struct.pack("<II", name_index, 0)
    # Type: FName (index, number) — StructProperty
    type_bytes = struct.pack("<II", type_index, 0)  # number=0 触发类型特定字段
    # Size
    size_bytes = struct.pack("<i", size)
    # ArrayIndex (旧格式始终存在)
    array_index_bytes = struct.pack("<i", 0)
    # StructName: FName (index, number)
    struct_name_index = 2  # name_map[2] = struct_name
    struct_name_bytes = struct.pack("<II", struct_name_index, 0)
    # StructGuid: FGuid (16 bytes)
    struct_guid_bytes = b"\x00" * 16
    # HasPropertyGuid: uint8 (0 = no)
    has_guid_bytes = b"\x00"

    return (
        name_bytes
        + type_bytes
        + size_bytes
        + array_index_bytes
        + struct_name_bytes
        + struct_guid_bytes
        + has_guid_bytes
    )


def _build_legacy_struct_property_tag_large_size(
    name_map: list[str] | None = None,
    size: int = 500 * 1024 * 1024,  # 500MB — 超过默认阈值
) -> tuple[bytes, list[str]]:
    """构建带有大 size 的 legacy StructProperty tag，用于测试动态阈值。

    Returns:
        (binary_data, name_map)
    """
    if name_map is None:
        name_map = ["MyProp", "StructProperty", "LargeStruct"]
    return _build_legacy_struct_property_tag(
        name_index=0,
        type_index=1,  # StructProperty
        size=size,
        struct_name="LargeStruct",
        name_map=name_map,
    ), name_map


class TestLegacyPathStructTypeOrdering:
    """验证 legacy path 中 validate_size 在 struct_type 赋值后调用。"""

    def test_struct_type_available_for_validate_size(self):
        """legacy path 的 StructProperty 应在 validate_size 调用前设置 struct_type。"""
        # 使用 tolerant 模式避免 size 超过 remaining 的异常，专注测试 struct_type 传递
        data, name_map = _build_legacy_struct_property_tag_large_size(size=1000)
        archive = _make_archive(data, file_version_ue5=1000)
        archive._tolerant = True  # 容错模式，size 超限不会抛异常

        # Mock validate_size 来验证调用参数
        with patch.object(archive, 'validate_size', wraps=archive.validate_size) as mock_validate:
            tag = read_property_tag(archive, name_map, tolerant=True)

            # 验证 validate_size 被调用
            assert mock_validate.called
            # 验证 property_type 参数是 struct_type 而非 tag.type
            call_kwargs = mock_validate.call_args
            property_type = call_kwargs.kwargs.get('property_type') or call_kwargs[1].get('property_type')
            # 在修复后，property_type 应该是 "LargeStruct" (struct_type)
            # 在修复前，property_type 会是 "None" 或 tag.type
            assert property_type == "LargeStruct", (
                f"Expected property_type='LargeStruct', got '{property_type}'. "
                "validate_size was called before struct_type was assigned."
            )

    def test_struct_type_set_before_validate_size(self):
        """验证 tag.struct_type 在 validate_size 被调用前已设置。"""
        data, name_map = _build_legacy_struct_property_tag_large_size(size=100)
        archive = _make_archive(data, file_version_ue5=1000)
        archive._tolerant = True  # 容错模式，size 超限不会抛异常

        # 使用 side_effect 来捕获 validate_size 调用时的 tag 状态
        validate_size_called = []
        original_validate_size = archive.validate_size

        def capture_validate_size(*args, **kwargs):
            # 捕获调用时的 archive 位置和参数
            validate_size_called.append({
                'args': args,
                'kwargs': kwargs,
                'pos': archive.tell(),
            })
            return original_validate_size(*args, **kwargs)

        with patch.object(archive, 'validate_size', side_effect=capture_validate_size):
            tag = read_property_tag(archive, name_map, tolerant=True)

            # 验证 tag.struct_type 已设置
            assert tag.struct_type == "LargeStruct", (
                f"Expected tag.struct_type='LargeStruct', got '{tag.struct_type}'"
            )

            # 验证 validate_size 被调用
            assert len(validate_size_called) == 1

    def test_non_struct_property_unchanged(self):
        """非 StructProperty 类型在 legacy path 中行为不变。"""
        name_map = ["BoolProp", "BoolProperty"]
        # BoolProperty: FName (name) + FName (type) + Size + ArrayIndex + BoolVal + HasPropertyGuid
        name_bytes = struct.pack("<II", 0, 0)  # BoolProp
        type_bytes = struct.pack("<II", 1, 0)  # BoolProperty
        size_bytes = struct.pack("<i", 1)
        array_index_bytes = struct.pack("<i", 0)
        bool_val_bytes = b"\x01"  # BoolVal = true
        has_guid_bytes = b"\x00"

        data = (
            name_bytes
            + type_bytes
            + size_bytes
            + array_index_bytes
            + bool_val_bytes
            + has_guid_bytes
        )
        archive = _make_archive(data, file_version_ue5=1000)

        with patch.object(archive, 'validate_size', wraps=archive.validate_size) as mock_validate:
            tag = read_property_tag(archive, name_map, tolerant=False)

            assert tag.type == "BoolProperty"
            assert tag.bool_val == 1
            # 验证 validate_size 被调用，property_type 是 tag.type
            call_kwargs = mock_validate.call_args
            property_type = call_kwargs.kwargs.get('property_type') or call_kwargs[1].get('property_type')
            assert property_type == "BoolProperty"


class TestLegacyPathStructPropertyLargeSize:
    """验证 legacy path 中大 StructProperty 的动态阈值生效。"""

    def test_large_struct_property_with_correct_struct_type(self):
        """大 StructProperty 应使用 struct_type 作为 property_type。"""
        # 构建 500MB size 的 StructProperty
        data, name_map = _build_legacy_struct_property_tag_large_size(
            size=500 * 1024 * 1024  # 500MB
        )
        archive = _make_archive(data, file_version_ue5=1000)

        # Mock validate_size 来验证参数，不实际执行验证
        with patch.object(archive, 'validate_size') as mock_validate:
            tag = read_property_tag(archive, name_map, tolerant=False)

            # 验证 tag 结构正确
            assert tag.type == "StructProperty"
            assert tag.struct_type == "LargeStruct"
            assert tag.size == 500 * 1024 * 1024

            # 验证 validate_size 被调用，且 property_type 是 struct_type
            mock_validate.assert_called_once()
            call_kwargs = mock_validate.call_args
            property_type = call_kwargs.kwargs.get('property_type') or call_kwargs[1].get('property_type')
            assert property_type == "LargeStruct"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
