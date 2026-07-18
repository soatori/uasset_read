"""Asset 文本与注册表测试（asset/text）。

合并自：
- test_lazy_and_text.py — 懒加载导出、GatherableTextData IR 结构
- test_asset_registry.py — AssetRegistryData 解析器
"""
from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

import pytest

from uasset_read.models.ir import ExportIR, ExportRawIR, PackageIR, PackageHeaderIR
from uasset_read.models.result import ParseResult
from uasset_read.parsers.asset_registry_parser import (
    AssetRegistryData,
    AssetRegistryObjectData,
    AssetRegistryTag,
    read_asset_registry_data,
)



# === 懒加载 + GatherableTextData 测试 ===

class TestExportIRLazyFields:

    """测试 ExportIR 懒加载字段。"""

    def _make_export(self):
        return ExportIR(
            index=0,
            object_name="Test",
            object_class="StaticMesh",
            serial_size=1000,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
        )

    def test_export_ir_has_is_loaded(self):
        """ExportIR 包含 is_loaded 标记，默认 False"""
        export = self._make_export()
        assert hasattr(export, "is_loaded")
        assert export.is_loaded is False

    def test_export_ir_has_lazy_load_archive(self):
        """ExportIR 包含 lazy_load_archive 字段，默认 None"""
        export = self._make_export()
        assert hasattr(export, "lazy_load_archive")
        assert export.lazy_load_archive is None

    def test_export_ir_lazy_fields_can_be_set(self):
        """懒加载字段可被设置"""
        export = self._make_export()
        export.is_loaded = True
        export.lazy_load_archive = b"\x00\x01\x02"
        assert export.is_loaded is True
        assert export.lazy_load_archive == b"\x00\x01\x02"


class TestParsePackageLazy:
    """测试 parse_package_lazy 函数。"""

    def _get_test_asset(self):
        """获取一个可用的测试 .uasset 文件路径"""
        samples = Path(__file__).parent / "samples"
        if not samples.exists():
            pytest.skip("测试样本目录不存在")
        assets = list(samples.glob("*.uasset"))
        if not assets:
            pytest.skip("无可用 .uasset 测试文件")
        return str(assets[0])

    def test_parse_lazy_returns_result(self):
        """parse_package_lazy 返回 ParseResult"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(path, tolerant=True)
        assert isinstance(result, ParseResult)
        assert result.summary is not None
        assert result.name_map is not None

    def test_parse_lazy_no_indices_all_unloaded(self):
        """未指定 export_indices 时所有 export 标记为未加载"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(path, export_indices=None, tolerant=True)
        for export in result.export_map:
            assert export.is_loaded is False

    def test_parse_lazy_with_indices(self):
        """指定 export_indices 时对应 export 被加载"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(path, tolerant=True)
        if not result.export_map:
            pytest.skip("测试文件无 export")

        # 只加载第一个 export
        result2 = parse_package_lazy(path, export_indices=[0], tolerant=True)
        assert result2.export_map[0].is_loaded is True
        for i in range(1, len(result2.export_map)):
            assert result2.export_map[i].is_loaded is False

    def test_parse_lazy_store_raw_bytes(self):
        """store_raw_bytes=True 时 export 包含原始字节"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[], store_raw_bytes=True, tolerant=True,
        )
        for export in result.export_map:
            if export.serial_size > 0:
                assert export.lazy_load_archive is not None
                assert isinstance(export.lazy_load_archive, bytes)

    def test_parse_lazy_no_raw_bytes(self):
        """store_raw_bytes=False 时 export 不包含原始字节"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[], store_raw_bytes=False, tolerant=True,
        )
        for export in result.export_map:
            assert getattr(export, "lazy_load_archive", None) is None

    def test_parse_lazy_metadata(self):
        """parse_package_lazy 设置正确的 metadata"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[0], tolerant=True,
        )
        assert result.metadata.get("lazy_loading") is True
        assert 0 in result.metadata.get("loaded_exports", [])
        assert "total_exports" in result.metadata

    def test_parse_lazy_nonexistent_index(self):
        """指定不存在的 export_indices 不会崩溃"""
        from uasset_read.parse_uasset import parse_package_lazy
        path = self._get_test_asset()
        result = parse_package_lazy(
            path, export_indices=[9999], tolerant=True,
        )
        # 所有 export 仍应标记为未加载
        for export in result.export_map:
            assert export.is_loaded is False


# ===========================================================================
# GatherableTextData IR 结构测试
# 参照 UE 源码 GatherableTextData.h:
# - FGatherableTextData: NamespaceName, SourceData, SourceSiteContexts
# - FTextSourceSiteContext: KeyName, SiteDescription, IsEditorOnly, IsOptional
# ===========================================================================


from uasset_read.models.ir import GatherableTextDataIR, SourceSiteContextIR


class TestSourceSiteContextIR:
    """测试 SourceSiteContextIR 数据结构。"""

    def test_basic_construction(self) -> None:
        """基本构造与字段访问。"""
        ctx = SourceSiteContextIR(
            key_name="UI.Button.OK",
            site_description="OK button text",
            is_editor_only=False,
            is_optional=False,
        )
        assert ctx.key_name == "UI.Button.OK"
        assert ctx.site_description == "OK button text"
        assert ctx.is_editor_only is False
        assert ctx.is_optional is False

    def test_editor_only_context(self) -> None:
        """编辑器专用上下文。"""
        ctx = SourceSiteContextIR(
            key_name="Editor.Tooltip",
            site_description="Tooltip for editor widget",
            is_editor_only=True,
            is_optional=True,
        )
        assert ctx.is_editor_only is True
        assert ctx.is_optional is True

    def test_equality(self) -> None:
        """相等性判断。"""
        ctx1 = SourceSiteContextIR("K", "D", False, False)
        ctx2 = SourceSiteContextIR("K", "D", False, False)
        assert ctx1 == ctx2

    def test_inequality(self) -> None:
        """不等性判断。"""
        ctx1 = SourceSiteContextIR("K1", "D", False, False)
        ctx2 = SourceSiteContextIR("K2", "D", False, False)
        assert ctx1 != ctx2


class TestGatherableTextDataIR:
    """测试 GatherableTextDataIR 数据结构。"""

    def test_basic_construction(self) -> None:
        """基本构造与字段访问。"""
        ir = GatherableTextDataIR(
            namespace_name="Game",
            source_string="Hello World",
            source_site_contexts=[],
        )
        assert ir.namespace_name == "Game"
        assert ir.source_string == "Hello World"
        assert ir.source_site_contexts == []

    def test_with_contexts(self) -> None:
        """包含多个上下文。"""
        ctx1 = SourceSiteContextIR("Key1", "Site1", False, False)
        ctx2 = SourceSiteContextIR("Key2", "Site2", True, True)
        ir = GatherableTextDataIR(
            namespace_name="MyGame.UI",
            source_string="Submit",
            source_site_contexts=[ctx1, ctx2],
        )
        assert len(ir.source_site_contexts) == 2
        assert ir.source_site_contexts[0].key_name == "Key1"
        assert ir.source_site_contexts[1].is_editor_only is True

    def test_empty_namespace(self) -> None:
        """空命名空间。"""
        ir = GatherableTextDataIR(
            namespace_name="",
            source_string="Some text",
            source_site_contexts=[],
        )
        assert ir.namespace_name == ""
        assert ir.source_string == "Some text"

    def test_equality(self) -> None:
        """相等性判断。"""
        ir1 = GatherableTextDataIR("NS", "Text", [])
        ir2 = GatherableTextDataIR("NS", "Text", [])
        assert ir1 == ir2

    def test_inequality(self) -> None:
        """不等性判断。"""
        ir1 = GatherableTextDataIR("NS1", "Text", [])
        ir2 = GatherableTextDataIR("NS2", "Text", [])
        assert ir1 != ir2

    def test_multiple_contexts_equality(self) -> None:
        """含上下文的相等性判断。"""
        ctx = SourceSiteContextIR("K", "D", False, False)
        ir1 = GatherableTextDataIR("NS", "Text", [ctx])
        ir2 = GatherableTextDataIR("NS", "Text", [ctx])
        assert ir1 == ir2


# === AssetRegistryData 解析器测试 ===

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

    def read_i64(self) -> int:
        data = self.read(8)
        return struct.unpack("<q", data)[0]

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
    file_version_ue4: int = 522,
) -> FakeArchive:
    """构建包含 AssetRegistryData 的 FakeArchive。"""
    buf = BytesIO()
    # 填充前置空间
    buf.write(b"\x00" * _DATA_OFFSET)
    # 写入 AssetRegistryData
    if include_dep_offset:
        # UE5 版本 >= 510 时使用 int64 写入 DependencyDataOffset
        if file_version_ue4 >= 510:
            buf.write(struct.pack("<q", dep_offset))
        else:
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
        archive = _build_archive_with_registry(dep_offset=0, objects=[])
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.dependency_data_offset == 0
        assert result.object_count == 0

    def test_single_object_no_tags(self):
        archive = _build_archive_with_registry(
            dep_offset=0,
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
            dep_offset=0,
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
            dep_offset=0,
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
        buf.write(struct.pack("<q", 100))  # DependencyDataOffset (int64 for UE5)
        buf.write(struct.pack("<i", -1))  # ObjectCount = -1
        archive = FakeArchive(buf.getvalue())
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        assert result.object_count == 0

    def test_negative_tag_count_skips_object(self):
        """TagCount 为负数时跳过该对象。"""
        buf = BytesIO()
        buf.write(b"\x00" * _DATA_OFFSET)
        buf.write(struct.pack("<q", 100))  # DependencyDataOffset (int64 for UE5)
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
            dep_offset=0,
            objects=[
                ("/Game/Test", "Blueprint", [
                    ("GeneratedClass", "/Script/Engine.BlueprintGeneratedClass"),
                ]),
            ],
        )
        result = read_asset_registry_data(archive, _DATA_OFFSET, file_version_ue4=522)
        assert result is not None
        d = result.to_dict()
        assert d["dependency_data_offset"] == 0
        assert d["object_count"] == 1
        assert d["objects"][0]["object_path"] == "/Game/Test"
        assert d["objects"][0]["tags"]["GeneratedClass"] == "/Script/Engine.BlueprintGeneratedClass"


class TestAssetRegistryIntegration:
    """集成测试 — 使用真实 .uasset 文件。"""

    def test_parse_returns_asset_registry_data(self, sample_root: Path):
        from uasset_read.parse_uasset import parse_package
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path), tolerant=True)
        assert result.asset_registry_data is not None
        assert isinstance(result.asset_registry_data, AssetRegistryData)

    def test_parse_asset_registry_in_ir(self, sample_root: Path):
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path), tolerant=True)
        ir = build_package_ir(result)
        assert ir.asset_registry_data is not None
        assert "object_count" in ir.asset_registry_data

    def test_parse_json_output_includes_asset_registry(self, sample_root: Path):
        from uasset_read.core import parse_single
        import json
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        output = parse_single(str(texture_path), format="json")
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
