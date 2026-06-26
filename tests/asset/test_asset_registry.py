"""AssetRegistryData 解析器测试。"""
from __future__ import annotations

import struct
from io import BytesIO

import pytest

from uasset_read.parsers.asset_registry_parser import (
    AssetRegistryData,
    AssetRegistryObjectData,
    AssetRegistryTag,
    read_asset_registry_data,
)


class FakeArchive:
    """用于测试的简易 archive 模拟类。"""

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def seek(self, offset: int):
        self._pos = offset

    def tell(self) -> int:
        return self._pos

    def total_size(self) -> int:
        return len(self._data)

    def read(self, n: int) -> bytes:
        result = self._data[self._pos:self._pos + n]
        self._pos += n
        return result

    def read_i32(self) -> int:
        data = self.read(4)
        return struct.unpack("<i", data)[0]

    def read_fstring(self) -> str:
        """模拟 FArchive::read_fstring（UE FString 序列化格式）。"""
        length = self.read_i32()
        if length == 0:
            return ""
        if length > 0:
            raw = self.read(length)
            return raw[:-1].decode("utf-8", errors="replace") if raw.endswith(b"\x00") else raw.decode("utf-8", errors="replace")
        else:
            byte_count = -length * 2
            raw = self.read(byte_count)
            return raw[:-2].decode("utf-16-le", errors="replace") if raw.endswith(b"\x00\x00") else raw.decode("utf-16-le", errors="replace")


_DATA_OFFSET = 16  # 模拟数据在文件中的偏移


def _build_fstring(s: str) -> bytes:
    """构建 UE FString 序列化字节（ANSI，带 null 终止符）。"""
    encoded = s.encode("utf-8") + b"\x00"
    return struct.pack("<i", len(encoded)) + encoded


def _build_archive_with_registry(
    dep_offset: int,
    objects: list[tuple[str, str, list[tuple[str, str]]]],
    include_dep_offset: bool = True,
) -> FakeArchive:
    """构建包含 AssetRegistryData 的 FakeArchive。"""
    buf = BytesIO()
    # 填充前置空间
    buf.write(b"\x00" * _DATA_OFFSET)
    # 写入 AssetRegistryData
    if include_dep_offset:
        buf.write(struct.pack("<i", dep_offset))
    buf.write(struct.pack("<i", len(objects)))
    for obj_path, class_name, tags in objects:
        buf.write(_build_fstring(obj_path))
        buf.write(_build_fstring(class_name))
        buf.write(struct.pack("<i", len(tags)))
        for key, value in tags:
            buf.write(_build_fstring(key))
            buf.write(_build_fstring(value))
    return FakeArchive(buf.getvalue())


class TestAssetRegistryDataStructures:
    """测试数据结构。"""

    def test_tag_as_dict(self):
        tag = AssetRegistryTag(key="Hello", value="World")
        assert tag.key == "Hello"
        assert tag.value == "World"

    def test_object_data_tags_as_dict(self):
        obj = AssetRegistryObjectData(
            object_path="MyAsset",
            object_class_name="Texture2D",
            tags=[
                AssetRegistryTag(key="Key1", value="Val1"),
                AssetRegistryTag(key="Key2", value="Val2"),
            ],
        )
        d = obj.tags_as_dict()
        assert d == {"Key1": "Val1", "Key2": "Val2"}

    def test_asset_registry_data_to_dict(self):
        data = AssetRegistryData(
            dependency_data_offset=100,
            objects=[
                AssetRegistryObjectData(
                    object_path="MyObj",
                    object_class_name="MyClass",
                    tags=[AssetRegistryTag(key="K", value="V")],
                ),
            ],
        )
        d = data.to_dict()
        assert d["dependency_data_offset"] == 100
        assert d["object_count"] == 1
        assert d["objects"][0]["object_path"] == "MyObj"
        assert d["objects"][0]["tags"] == {"K": "V"}

    def test_asset_registry_data_empty(self):
        data = AssetRegistryData()
        assert data.object_count == 0
        d = data.to_dict()
        assert d["object_count"] == 0
        assert d["objects"] == []


class TestReadAssetRegistryData:
    """测试解析逻辑。"""

    def test_offset_zero_returns_none(self):
        archive = FakeArchive(b"\x00" * 100)
        result = read_asset_registry_data(archive, 0)
        assert result is None

    def test_negative_offset_returns_none(self):
        archive = FakeArchive(b"\x00" * 100)
        result = read_asset_registry_data(archive, -1)
        assert result is None

    def test_empty_object_list(self):
        archive = _build_archive_with_registry(dep_offset=50, objects=[])
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.dependency_data_offset == 50
        assert result.object_count == 0

    def test_single_object_no_tags(self):
        archive = _build_archive_with_registry(
            dep_offset=100,
            objects=[("MyAsset", "Texture2D", [])],
        )
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.object_count == 1
        assert result.objects[0].object_path == "MyAsset"
        assert result.objects[0].object_class_name == "Texture2D"
        assert result.objects[0].tags == []

    def test_single_object_with_tags(self):
        archive = _build_archive_with_registry(
            dep_offset=100,
            objects=[
                ("MyAsset", "Material", [
                    ("NativeIdentifier", "Material'/Game/MyMaterial'"),
                    ("ImportedPath", "C:/Projects/MyMaterial.uasset"),
                ]),
            ],
        )
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.object_count == 1
        obj = result.objects[0]
        assert obj.object_path == "MyAsset"
        assert obj.object_class_name == "Material"
        assert len(obj.tags) == 2
        assert obj.tags[0].key == "NativeIdentifier"
        assert obj.tags[0].value == "Material'/Game/MyMaterial'"
        assert obj.tags_as_dict()["ImportedPath"] == "C:/Projects/MyMaterial.uasset"

    def test_multiple_objects(self):
        archive = _build_archive_with_registry(
            dep_offset=200,
            objects=[
                ("Obj1", "Class1", [("K1", "V1")]),
                ("Obj2", "Class2", [("K2", "V2"), ("K3", "V3")]),
            ],
        )
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.object_count == 2
        assert result.objects[0].object_path == "Obj1"
        assert result.objects[1].object_path == "Obj2"
        assert len(result.objects[1].tags) == 2

    def test_pre_dependency_format_no_dep_offset(self):
        """版本 < 510 时不读取 DependencyDataOffset。"""
        archive = _build_archive_with_registry(
            dep_offset=0,
            objects=[("Asset", "Class", [("K", "V")])],
            include_dep_offset=False,
        )
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=500)
        assert result is not None
        assert result.dependency_data_offset == -1
        assert result.object_count == 1
        assert result.objects[0].tags_as_dict() == {"K": "V"}

    def test_negative_object_count_returns_empty(self):
        """ObjectCount 为负数时返回空结果。"""
        buf = BytesIO()
        buf.write(b"\x00" * _DATA_OFFSET)
        buf.write(struct.pack("<i", 100))  # DependencyDataOffset
        buf.write(struct.pack("<i", -1))  # ObjectCount = -1
        archive = FakeArchive(buf.getvalue())
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.object_count == 0

    def test_negative_tag_count_skips_object(self):
        """TagCount 为负数时跳过该对象。"""
        buf = BytesIO()
        buf.write(b"\x00" * _DATA_OFFSET)
        buf.write(struct.pack("<i", 100))  # DependencyDataOffset
        buf.write(struct.pack("<i", 1))  # ObjectCount
        buf.write(_build_fstring("Obj"))
        buf.write(_build_fstring("Class"))
        buf.write(struct.pack("<i", -5))  # TagCount = -5
        archive = FakeArchive(buf.getvalue())
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.object_count == 0  # 对象被跳过

    def test_cooked_package_no_dep_offset(self):
        """Cooked 包不读取 DependencyDataOffset。"""
        archive = _build_archive_with_registry(
            dep_offset=0,
            objects=[("Asset", "Class", [])],
            include_dep_offset=False,
        )
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522, is_cooked=True)
        assert result is not None
        assert result.dependency_data_offset == -1
        assert result.object_count == 1

    def test_to_dict_roundtrip(self):
        """to_dict 输出可正确反映原始数据。"""
        archive = _build_archive_with_registry(
            dep_offset=500,
            objects=[
                ("/Game/Test", "Blueprint", [
                    ("GeneratedClass", "/Script/Engine.BlueprintGeneratedClass"),
                ]),
            ],
        )
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        d = result.to_dict()
        assert d["dependency_data_offset"] == 500
        assert d["object_count"] == 1
        assert d["objects"][0]["object_path"] == "/Game/Test"
        assert d["objects"][0]["tags"]["GeneratedClass"] == "/Script/Engine.BlueprintGeneratedClass"


class TestAssetRegistryIntegration:
    """集成测试 — 使用真实 .uasset 文件。"""

    SAMPLE_TEXTURE = "E:/Develop/lib/Samples/StarterContent/Content/StarterContent/Textures/T_Brick_Clay_New_D.uasset"

    def test_parse_returns_asset_registry_data(self):
        from uasset_read.parse_uasset import parse_package
        result = parse_package(self.SAMPLE_TEXTURE, tolerant=True)
        assert result.asset_registry_data is not None
        assert isinstance(result.asset_registry_data, AssetRegistryData)

    def test_parse_asset_registry_in_ir(self):
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        result = parse_package(self.SAMPLE_TEXTURE, tolerant=True)
        ir = build_package_ir(result)
        assert ir.asset_registry_data is not None
        assert "object_count" in ir.asset_registry_data

    def test_parse_json_output_includes_asset_registry(self):
        from uasset_read.core import parse_single
        import json
        output = parse_single(self.SAMPLE_TEXTURE, format="json")
        data = json.loads(output)
        assert "asset_registry_data" in data
        assert "object_count" in data["asset_registry_data"]

    def test_parse_markdown_output_includes_asset_registry(self):
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions
        from uasset_read.models.ir import PackageIR, PackageHeaderIR
        ir = PackageIR(
            header=PackageHeaderIR(
                package_name="/Test/Asset",
                package_class="Texture2D",
                package_flags=0,
                total_export_count=1,
                total_import_count=0,
                ue_version="5.x",
            ),
            name_map=[],
            imports=[],
            exports=[],
            linker=None,
            asset_registry_data={
                "dependency_data_offset": 0,
                "object_count": 1,
                "objects": [{
                    "object_path": "/Test/Asset",
                    "object_class_name": "Texture2D",
                    "tags": {"bIsCooked": "True", "AssetImportData": "test"},
                }],
            },
        )
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions())
        assert "Asset Registry Data" in output
        assert "Texture2D" in output
        assert "bIsCooked" in output
