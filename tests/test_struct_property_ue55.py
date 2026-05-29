"""UE5.5 StructProperty 扩展测试"""
import struct
import pytest
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
