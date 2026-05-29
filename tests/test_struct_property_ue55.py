"""UE5.5 StructProperty 扩展测试"""
from __future__ import annotations

import struct
from pathlib import Path
from uasset_read.archive import FArchive
from uasset_read.parsers.property_types import parse_struct_property
from uasset_read.models.properties import PropertyTag, StructValue


def _make_archive(tmp_path: Path, data: bytes) -> FArchive:
    path = tmp_path / "test.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=True)


def test_toplevel_asset_path(tmp_path):
    """TopLevelAssetPath: 2x FName (package + asset name)"""
    name_map = [
        "",  # 0
        "/Game/FirstPerson/Blueprints/BP_FirstPerson",  # 1
        "BP_FirstPerson",  # 2
    ]
    # FName 格式: i32 index + i32 number
    data = struct.pack('<ii', 1, 0) + struct.pack('<ii', 2, 0)
    archive = _make_archive(tmp_path, data)
    try:
        tag = PropertyTag(
            name="TestPath",
            type="StructProperty",
            size=len(data),
            struct_type="TopLevelAssetPath"
        )

        result = parse_struct_property(tag, archive, name_map, [], None)

        assert result.struct_type == "TopLevelAssetPath"
        assert "PackageName" in result.fields
        assert "AssetName" in result.fields
        assert result.fields["PackageName"] == "/Game/FirstPerson/Blueprints/BP_FirstPerson"
        assert result.fields["AssetName"] == "BP_FirstPerson"
        assert archive.tell() == 16  # 2 x 8-byte FName
        assert result.parse_status == "parsed"
    finally:
        archive.close()


def test_tagged_fallback_schemas_extended():
    """验证 _TAGGED_FALLBACK_STRUCT_SCHEMAS 已扩展"""
    from uasset_read.parsers.property_types import _TAGGED_FALLBACK_STRUCT_SCHEMAS

    assert "NewVariables" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
    assert "ImplementedInterfaces" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
    assert "LastEditedDocuments" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
    assert "CategorySorting" in _TAGGED_FALLBACK_STRUCT_SCHEMAS


def test_pointer_to_uber_graph_frame(tmp_path):
    """PointerToUberGraphFrame: 8 bytes (FPackageIndex)"""
    data = struct.pack('<q', 42)  # 64-bit index=42
    archive = _make_archive(tmp_path, data)

    tag = PropertyTag(
        name="UberGraphFrame",
        type="StructProperty",
        size=8,
        struct_type="PointerToUberGraphFrame"
    )

    try:
        result = parse_struct_property(tag, archive, name_map=[], export_map=[], summary=None)

        assert result.struct_type == "PointerToUberGraphFrame"
        assert "FrameIndex" in result.fields
        assert result.fields["FrameIndex"] == 42
        assert result.parse_status == "parsed"
        assert archive.tell() == 8
    finally:
        archive.close()


def test_box_sphere_bounds_114_bytes(tmp_path):
    """BoxSphereBounds 114 bytes: UE5.5 扩展格式"""
    # 28 floats = 112 bytes + 2 bytes padding = 114 bytes
    data = struct.pack('<28f', *range(28)) + b'\x00\x00'
    archive = _make_archive(tmp_path, data)

    tag = PropertyTag(
        name="TestBounds",
        type="StructProperty",
        size=114,
        struct_type="BoxSphereBounds"
    )

    try:
        result = parse_struct_property(tag, archive, name_map=[], export_map=[], summary=None)

        assert result.struct_type == "BoxSphereBounds"
        assert "Origin" in result.fields
        assert "BoxExtent" in result.fields
        assert "SphereRadius" in result.fields
        assert result.parse_status == "parsed"
        assert archive.tell() == 114  # 消费全部字节
    finally:
        archive.close()


def test_vector4_double_precision(tmp_path):
    """Vector4 32 bytes: double 精度版本 (UE5.5 LWC)"""
    data = struct.pack('<dddd', 1.0, 2.0, 3.0, 4.0)
    archive = _make_archive(tmp_path, data)

    tag = PropertyTag(
        name="TestVec4",
        type="StructProperty",
        size=32,
        struct_type="Vector4"
    )

    try:
        result = parse_struct_property(tag, archive, name_map=[], export_map=[], summary=None)

        assert result.struct_type == "Vector4"
        assert result.fields["X"] == 1.0
        assert result.fields["Y"] == 2.0
        assert result.fields["Z"] == 3.0
        assert result.fields["W"] == 4.0
        assert result.parse_status == "parsed"
        assert archive.tell() == 32
    finally:
        archive.close()
