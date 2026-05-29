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
