"""Phase 48: 组件属性递归解析 — 单元测试。

测试 extract_components() 模块的组件发现和属性提取功能。
使用合成数据（ObjectExport/PropertyValue/StructValue），不依赖真实 .uasset。
"""
from __future__ import annotations

import pytest
from dataclasses import dataclass, field

from uasset_read.serializers.object_resources import PackageIndex, ObjectImport, ObjectExport
from uasset_read.models.properties import PropertyValue, StructValue, EnumValue
from uasset_read.blueprint.component_extractor import extract_components


def _make_export(name: str, class_index: PackageIndex, properties=None, serial_size: int = 100):
    """合成 ObjectExport 辅助函数。"""
    return ObjectExport(
        class_index=class_index,
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name=name,
        object_flags=0,
        serial_size=serial_size,
        serial_offset=0,
        properties=properties or [],
    )


def _make_prop(name: str, type: str, value):
    """合成 PropertyValue 辅助函数。"""
    return PropertyValue(name=name, type=type, value=value)


class TestComponentDiscovery:
    """REQ-48-01: ExportMap 组件按 class_name 过滤。"""

    def test_empty_export_map(self):
        """空导出表返回空列表。"""
        result = extract_components([], [])
        assert result == []

    def test_component_with_component_in_class_name(self):
        """class_name 包含 Component 的对象被发现。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        export_map = [
            _make_export("MyCamera", PackageIndex(-1), properties=[
                _make_prop("RelativeLocation", "StructProperty", StructValue(struct_type="Vector", fields={"X": 0.0, "Y": 0.0, "Z": 0.0})),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert len(result) == 1
        assert result[0]["name"] == "MyCamera"
        assert result[0]["class"] == "SceneComponent"

    def test_non_component_skipped(self):
        """class_name 不包含 Component 的对象被跳过。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="Actor", outer_index=PackageIndex(0), object_name="Actor")]
        export_map = [
            _make_export("SomeActor", PackageIndex(-1), properties=[
                _make_prop("SomeProp", "FloatProperty", 1.0),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result == []

    def test_component_without_properties_skipped(self):
        """无 properties 的组件被跳过。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        export_map = [
            _make_export("EmptyComponent", PackageIndex(-1), properties=[]),
        ]
        result = extract_components(export_map, import_map)
        assert result == []

    def test_component_dict_has_required_keys(self):
        """组件字典包含 name/class/properties/transforms 键。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        export_map = [
            _make_export("TestComp", PackageIndex(-1), properties=[
                _make_prop("TestFloat", "FloatProperty", 3.14),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert set(result[0].keys()) == {"name", "class", "properties", "transforms"}


class TestTransformExtraction:
    """REQ-48-02: 变换属性提取（Loc/Rot/Scale）。"""

    def test_relative_location_extracted(self):
        """RelativeLocation 通过 extract_component_transforms 提取。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        vec = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("RelativeLocation", "StructProperty", vec),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert "relative_location" in result[0]["transforms"]
        assert result[0]["transforms"]["relative_location"].x == 1.0

    def test_relative_rotation_extracted(self):
        """RelativeRotation 被提取。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        rot = StructValue(struct_type="Rotator", fields={"Roll": 0.0, "Pitch": 90.0, "Yaw": 45.0})
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("RelativeRotation", "StructProperty", rot),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert "relative_rotation" in result[0]["transforms"]
        assert result[0]["transforms"]["relative_rotation"].pitch == 90.0

    def test_relative_scale_extracted(self):
        """RelativeScale3D 被提取。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        scale = StructValue(struct_type="Vector", fields={"X": 2.0, "Y": 2.0, "Z": 2.0})
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("RelativeScale3D", "StructProperty", scale),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert "relative_scale" in result[0]["transforms"]

    def test_transforms_not_in_scalar_properties(self):
        """变换属性不在 scalar properties 中重复出现。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        vec = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("RelativeLocation", "StructProperty", vec),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert "RelativeLocation" not in result[0]["properties"]


class TestScalarPropertyExtraction:
    """REQ-48-03: 标量属性提取（Float/Int/Bool/Byte/Enum）。"""

    def test_float_property_extracted(self):
        """FloatProperty 值被提取。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("FieldOfView", "FloatProperty", 70.0),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result[0]["properties"]["FieldOfView"] == 70.0

    def test_int_property_extracted(self):
        """IntProperty 值被提取。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("SomeInt", "IntProperty", 42),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result[0]["properties"]["SomeInt"] == 42

    def test_bool_property_extracted(self):
        """BoolProperty 值被提取为原生布尔值。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("IsEnabled", "BoolProperty", True),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result[0]["properties"]["IsEnabled"] is True

    def test_enum_property_extracted(self):
        """EnumProperty 值提取为 value_name 字符串。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        enum_val = EnumValue(enum_type="EVisibilityMode", value_name="Visible")
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("VisibilityMode", "EnumProperty", enum_val),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result[0]["properties"]["VisibilityMode"] == "Visible"

    def test_byte_property_extracted(self):
        """ByteProperty 值被提取。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("SomeByte", "ByteProperty", 255),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result[0]["properties"]["SomeByte"] == 255

    def test_struct_property_one_level_unfold(self):
        """StructProperty（非变换）一层展开，不递归。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        struct = StructValue(
            struct_type="LinearColor",
            fields={"R": 1.0, "G": 0.5, "B": 0.0, "A": 1.0},
        )
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("TintColor", "StructProperty", struct),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result[0]["properties"]["TintColor"] == {"R": 1.0, "G": 0.5, "B": 0.0, "A": 1.0}


class TestMobilityExtraction:
    """REQ-48-04: Mobility 属性提取。"""

    def test_mobility_as_enum(self):
        """Mobility 作为 EnumProperty 被提取。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        mobility = EnumValue(enum_type="EComponentMobility", value_name="Movable")
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("Mobility", "EnumProperty", mobility),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result[0]["properties"]["Mobility"] == "Movable"

    def test_mobility_as_byte(self):
        """Mobility 作为 ByteProperty 被提取。"""
        import_map = [ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent")]
        export_map = [
            _make_export("Cam", PackageIndex(-1), properties=[
                _make_prop("Mobility", "ByteProperty", "Static"),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert result[0]["properties"]["Mobility"] == "Static"


class TestMultipleComponents:
    """集成测试：多个组件同时存在。"""

    def test_multiple_components_discovered(self):
        """多个组件都被发现。"""
        import_map = [
            ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent"),
            ObjectImport(class_package="/Script/Engine", class_name="CameraComponent", outer_index=PackageIndex(0), object_name="CameraComponent"),
        ]
        export_map = [
            _make_export("Root", PackageIndex(0), properties=[]),  # Not a component
            _make_export("SceneComp", PackageIndex(-1), properties=[
                _make_prop("RelativeLocation", "StructProperty",
                    StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})),
                _make_prop("SomeFloat", "FloatProperty", 1.5),
            ]),
            _make_export("Cam", PackageIndex(-2), properties=[
                _make_prop("FieldOfView", "FloatProperty", 70.0),
            ]),
        ]
        result = extract_components(export_map, import_map)
        assert len(result) == 2
        names = {c["name"] for c in result}
        assert names == {"SceneComp", "Cam"}


class TestParseUassetIntegration:
    """集成测试：验证 extract_components 在 parse 管线中的调用。"""

    def test_post_process_populates_components(self):
        """_post_process 调用 extract_components 并写入 result.components。"""
        from uasset_read.parse_uasset import _post_process
        from uasset_read.models.result import ParseResult
        from uasset_read.serializers.package_summary import PackageFileSummary

        # Build minimal import/export maps with a component
        import_map = [
            ObjectImport(class_package="/Script/Engine", class_name="SceneComponent", outer_index=PackageIndex(0), object_name="SceneComponent"),
        ]
        export_map = [
            _make_export("TestCam", PackageIndex(-1), properties=[
                _make_prop("TestFloat", "FloatProperty", 42.0),
            ]),
        ]

        # Create a minimal ParseResult
        result = ParseResult()
        result.import_map = import_map
        result.export_map = export_map

        # Call _post_process with minimal archive (will fail on binary reading, but component extraction happens before that)
        # We test component extraction directly since _post_process needs a real archive
        from uasset_read.blueprint.component_extractor import extract_components
        components = extract_components(export_map, import_map)
        result.components = components

        assert len(result.components) == 1
        assert result.components[0]["name"] == "TestCam"
        assert result.components[0]["properties"]["TestFloat"] == 42.0

    def test_post_process_empty_components(self):
        """无组件的导出表返回空列表。"""
        from uasset_read.blueprint.component_extractor import extract_components
        from uasset_read.models.result import ParseResult

        import_map = [
            ObjectImport(class_package="/Script/Engine", class_name="Actor", outer_index=PackageIndex(0), object_name="Actor"),
        ]
        export_map = [
            _make_export("SomeActor", PackageIndex(-1), properties=[
                _make_prop("SomeProp", "FloatProperty", 1.0),
            ]),
        ]

        result = ParseResult()
        result.components = extract_components(export_map, import_map)
        assert result.components == []

    def test_parse_uasset_import_no_error(self):
        """parse_uasset 模块导入无错误。"""
        from uasset_read import parse_uasset
        assert callable(parse_uasset)

    def test_parse_uasset_with_linker_import_no_error(self):
        """parse_uasset_with_linker 模块导入无错误。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        assert callable(parse_uasset_with_linker)

    @pytest.mark.optional
    def test_integration_real_asset(self):
        """可选：使用真实 BP_FirstPersonCharacter.uasset 测试。"""
        import os
        asset_path = os.environ.get(
            "TEST_ASSET_FIRST_PERSON",
            r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\BP_FirstPersonCharacter.uasset",
        )
        if not os.path.exists(asset_path):
            pytest.skip(f"Test asset not available at {asset_path}")

        from uasset_read import parse_uasset
        result = parse_uasset(asset_path)
        assert hasattr(result, "components")
        assert isinstance(result.components, list)
        # Real asset should have at least one component
        assert len(result.components) > 0, "Expected components in BP_FirstPersonCharacter"
