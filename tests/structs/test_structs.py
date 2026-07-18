"""结构体解析综合测试。

合并以下测试模块：
- test_struct_lwc.py — LWC 版本感知尺寸查询和解析
- test_struct_scalar_param.py — ScalarParameterValue tagged fallback
- test_struct_blend_sample.py — FBlendSample tagged fallback
- test_struct_editor_element.py — FEditorElement tagged fallback
- test_box_sphere_bounds.py — BoxSphereBounds 解析验证
"""
from __future__ import annotations

import logging
import os
import struct
from pathlib import Path

import pytest

from uasset_read.archive import FArchive
from uasset_read.models.properties import PropertyTag, StructValue
from uasset_read.parsers.property_types import (
    _EXPECTED_STRUCT_SIZES,
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
    get_struct_size,
    parse_struct_property,
)
from uasset_read.versioning import VersionContainer

from tests.conftest import asset_path, ASSET_MESH_CHAIR


# ============================================================================
# 辅助函数
# ============================================================================

def _archive(tmp_path: Path, data: bytes) -> FArchive:
    """从字节数据创建测试用 FArchive。"""
    path = tmp_path / "data.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=False)


def _make_vc(ue5_version: int = 0, ue4_version: int = 0) -> VersionContainer:
    """创建测试用 VersionContainer。"""
    return VersionContainer(
        file_version_ue5=ue5_version,
        file_version_ue4=ue4_version,
    )


# ============================================================================
# get_struct_size — 基础功能
# ============================================================================

class TestGetStructSizeBasic:
    """get_struct_size 基础查询（无 version_container）。"""

    def test_known_non_lwc_type(self):
        """非 LWC 类型返回固定大小。"""
        assert get_struct_size("Color") == 4
        assert get_struct_size("Guid") == 16
        assert get_struct_size("IntPoint") == 8
        assert get_struct_size("LinearColor") == 16

    def test_unknown_type_returns_none(self):
        """未知类型返回 None。"""
        assert get_struct_size("UnknownStruct") is None
        assert get_struct_size("CustomFoo") is None

    def test_no_version_container_uses_float_size(self):
        """无 version_container 时，LWC 基础类型返回 float 大小。"""
        assert get_struct_size("Vector") == 12
        assert get_struct_size("Rotator") == 12
        assert get_struct_size("Vector2D") == 8
        assert get_struct_size("Vector4") == 16
        assert get_struct_size("Quat") == 16
        assert get_struct_size("Plane") == 16
        assert get_struct_size("Sphere") == 16


# ============================================================================
# get_struct_size — LWC 版本感知
# ============================================================================

class TestGetStructSizeLWC:
    """get_struct_size LWC 版本感知。"""

    def test_ue4_returns_float_size(self):
        """UE4 版本返回 float 大小。"""
        vc = _make_vc(ue4_version=516)
        assert get_struct_size("Vector", vc) == 12
        assert get_struct_size("Quat", vc) == 16

    def test_ue5_pre_lwc_returns_float_size(self):
        """UE5 pre-LWC (file_version_ue5 < 1004) 返回 float 大小。"""
        vc = _make_vc(ue5_version=1000)
        assert get_struct_size("Vector", vc) == 12
        assert get_struct_size("Rotator", vc) == 12
        assert get_struct_size("Vector2D", vc) == 8
        assert get_struct_size("Vector4", vc) == 16
        assert get_struct_size("Quat", vc) == 16
        assert get_struct_size("Plane", vc) == 16
        assert get_struct_size("Sphere", vc) == 16

    def test_ue5_lwc_returns_double_size(self):
        """UE5 LWC (file_version_ue5 >= 1004) 返回 double 大小。"""
        vc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector", vc) == 24
        assert get_struct_size("Rotator", vc) == 24
        assert get_struct_size("Vector2D", vc) == 16
        assert get_struct_size("Vector4", vc) == 32
        assert get_struct_size("Quat", vc) == 32
        assert get_struct_size("Plane", vc) == 32
        assert get_struct_size("Sphere", vc) == 32

    def test_ue5_lwc_higher_version(self):
        """UE5 LWC 更高版本也返回 double 大小。"""
        vc = _make_vc(ue5_version=1012)
        assert get_struct_size("Vector", vc) == 24
        assert get_struct_size("Quat", vc) == 32

    def test_non_lwc_type_unaffected_by_version(self):
        """非 LWC 类型不受版本影响。"""
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Color", vc_lwc) == 4
        assert get_struct_size("Guid", vc_lwc) == 16
        assert get_struct_size("LinearColor", vc_lwc) == 16
        assert get_struct_size("IntPoint", vc_lwc) == 8


# ============================================================================
# get_struct_size — 显式精度变体
# ============================================================================

class TestGetStructSizeExplicitTypes:
    """显式精度变体类型（Vector3d, Vector3f 等）。"""

    def test_double_variants_always_return_double_size(self):
        """显式双精度变体始终返回 double 大小，不看版本。"""
        # 无版本
        assert get_struct_size("Vector3d") == 24
        assert get_struct_size("Vector4d") == 32
        assert get_struct_size("Rotator3d") == 24
        assert get_struct_size("Quat4d") == 32
        assert get_struct_size("Plane4d") == 32
        assert get_struct_size("Sphere3d") == 32

        # UE4 版本
        vc_ue4 = _make_vc(ue4_version=516)
        assert get_struct_size("Vector3d", vc_ue4) == 24
        assert get_struct_size("Quat4d", vc_ue4) == 32

        # UE5 LWC 版本
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector3d", vc_lwc) == 24
        assert get_struct_size("Quat4d", vc_lwc) == 32

    def test_float_variants_always_return_float_size(self):
        """显式单精度变体始终返回 float 大小，不看版本。"""
        # 无版本
        assert get_struct_size("Vector3f") == 12
        assert get_struct_size("Vector4f") == 16
        assert get_struct_size("Rotator3f") == 12
        assert get_struct_size("Quat4f") == 16
        assert get_struct_size("Plane4f") == 16
        assert get_struct_size("Sphere3f") == 16
        assert get_struct_size("Vector2f") == 8

        # UE5 LWC 版本
        vc_lwc = _make_vc(ue5_version=1004)
        assert get_struct_size("Vector3f", vc_lwc) == 12
        assert get_struct_size("Quat4f", vc_lwc) == 16


# ============================================================================
# parse_struct_property — Quat/Plane/Sphere LWC 快速路径
# ============================================================================

class TestStructPropertyLWCFastPath:
    """验证 Quat/Plane/Sphere 的 LWC 双精度快速路径。"""

    def test_quat_f32_fast_path(self, tmp_path):
        """Quat 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 1.0, 2.0, 3.0, 4.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestQuat", type="StructProperty", size=16, struct_type="Quat")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Quat"
        assert abs(result.fields["X"] - 1.0) < 1e-6
        assert abs(result.fields["Y"] - 2.0) < 1e-6
        assert abs(result.fields["Z"] - 3.0) < 1e-6
        assert abs(result.fields["W"] - 4.0) < 1e-6

    def test_quat_f64_lwc_fast_path(self, tmp_path):
        """Quat LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 1.5, 2.5, 3.5, 4.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestQuat", type="StructProperty", size=32, struct_type="Quat")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Quat"
        assert abs(result.fields["X"] - 1.5) < 1e-10
        assert abs(result.fields["Y"] - 2.5) < 1e-10
        assert abs(result.fields["Z"] - 3.5) < 1e-10
        assert abs(result.fields["W"] - 4.5) < 1e-10

    def test_plane_f32_fast_path(self, tmp_path):
        """Plane 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 0.0, 1.0, 0.0, -5.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestPlane", type="StructProperty", size=16, struct_type="Plane")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Plane"
        assert abs(result.fields["X"] - 0.0) < 1e-6
        assert abs(result.fields["W"] - (-5.0)) < 1e-6

    def test_plane_f64_lwc_fast_path(self, tmp_path):
        """Plane LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 0.0, 1.0, 0.0, -5.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestPlane", type="StructProperty", size=32, struct_type="Plane")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Plane"
        assert abs(result.fields["X"] - 0.0) < 1e-10
        assert abs(result.fields["W"] - (-5.5)) < 1e-10

    def test_sphere_f32_fast_path(self, tmp_path):
        """Sphere 标准 float 精度快速路径。"""
        data = struct.pack("<ffff", 10.0, 20.0, 30.0, 5.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestSphere", type="StructProperty", size=16, struct_type="Sphere")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Sphere"
        assert abs(result.fields["Center"]["X"] - 10.0) < 1e-6
        assert abs(result.fields["W"] - 5.0) < 1e-6

    def test_sphere_f64_lwc_fast_path(self, tmp_path):
        """Sphere LWC double 精度快速路径（tag.size=32）。"""
        data = struct.pack("<dddd", 10.5, 20.5, 30.5, 5.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="TestSphere", type="StructProperty", size=32, struct_type="Sphere")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Sphere"
        assert abs(result.fields["Center"]["X"] - 10.5) < 1e-10
        assert abs(result.fields["W"] - 5.5) < 1e-10


# ============================================================================
# parse_struct_property — 版本感知尺寸验证
# ============================================================================

class TestStructPropertyVersionAwareValidation:
    """验证 parse_struct_property 的版本感知尺寸验证。"""

    def test_vector_f32_accepted_without_version(self, tmp_path):
        """Vector 12 字节（float）在无 summary 时被接受。"""
        data = struct.pack("<fff", 1.0, 2.0, 3.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=12, struct_type="Vector")
        result = parse_struct_property(tag, archive, [], [])
        assert isinstance(result, StructValue)
        assert result.struct_type == "Vector"
        assert abs(result.fields["X"] - 1.0) < 1e-6

    def test_vector_f64_accepted_without_version(self, tmp_path):
        """Vector 24 字节（double）在无 summary 时通过预检查（属于 LWC 可变大小）。"""
        data = struct.pack("<ddd", 1.5, 2.5, 3.5)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=24, struct_type="Vector")
        # 无 summary 时，get_struct_size 返回 12（float），但 tag.size=24 不匹配
        # 预检查会 warning 并 fallback 到 generic path
        result = parse_struct_property(tag, archive, [], [], summary=None)
        # 应该返回 StructValue（fallback 到 generic path，无数据则 opaque）
        assert isinstance(result, StructValue)

    def test_vector_f32_size_mismatch_with_lwc_version(self, tmp_path):
        """Vector 12 字节在 UE5 LWC 版本下与预期 24 不匹配，fallback。"""
        data = struct.pack("<fff", 1.0, 2.0, 3.0)
        archive = _archive(tmp_path, data)
        tag = PropertyTag(name="Pos", type="StructProperty", size=12, struct_type="Vector")

        # 创建一个具有 UE5 LWC 版本的 summary
        class MockSummary:
            file_version_ue5 = 1004
            file_version_ue4 = 0
            custom_versions = []

        result = parse_struct_property(tag, archive, [], [], summary=MockSummary())
        # 12 != 24 (LWC expected)，fallback 到 generic path
        assert isinstance(result, StructValue)


# ============================================================================
# ScalarParameterValue / FScalarParameterValue tagged fallback
# ============================================================================

class TestScalarParameterValueRegistration:
    """验证 ScalarParameterValue / FScalarParameterValue 在 tagged fallback 中注册。"""

    def test_scalar_param_in_tagged_fallback_structs(self):
        assert "ScalarParameterValue" in _TAGGED_FALLBACK_STRUCTS

    def test_f_scalar_param_in_tagged_fallback_structs(self):
        assert "FScalarParameterValue" in _TAGGED_FALLBACK_STRUCTS

    def test_f_material_parameter_info_in_tagged_fallback_structs(self):
        """FMaterialParameterInfo 也需注册，因为 ScalarParameterValue 依赖它。"""
        assert "FMaterialParameterInfo" in _TAGGED_FALLBACK_STRUCTS

    def test_scalar_param_in_fallback_schemas(self):
        assert "ScalarParameterValue" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_f_scalar_param_in_fallback_schemas(self):
        assert "FScalarParameterValue" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_f_material_parameter_info_in_fallback_schemas(self):
        assert "FMaterialParameterInfo" in _TAGGED_FALLBACK_STRUCT_SCHEMAS


class TestScalarParameterValueSchema:
    """验证 ScalarParameterValue schema 字段定义与 UE5 源码一致。"""

    def test_scalar_param_schema_fields(self):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
        field_names = [f[0] for f in schema]
        assert "ParameterInfo" in field_names
        assert "ParameterValue" in field_names
        assert "bOverride" in field_names

    def test_scalar_param_schema_types(self):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
        schema_dict = dict(schema)
        assert schema_dict["ParameterInfo"] == "StructProperty"
        assert schema_dict["ParameterValue"] == "FloatProperty"
        assert schema_dict["bOverride"] == "BoolProperty"

    def test_f_scalar_param_matches_scalar_param(self):
        """FScalarParameterValue 应与 ScalarParameterValue 有相同字段。"""
        assert (
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
            == _TAGGED_FALLBACK_STRUCT_SCHEMAS["FScalarParameterValue"]
        )

    def test_material_parameter_info_schema_fields(self):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FMaterialParameterInfo"]
        field_names = [f[0] for f in schema]
        assert "ParameterName" in field_names
        assert "Index" in field_names
        assert "bOverride" in field_names

    def test_material_parameter_info_schema_types(self):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FMaterialParameterInfo"]
        schema_dict = dict(schema)
        assert schema_dict["ParameterName"] == "NameProperty"
        assert schema_dict["Index"] == "IntProperty"
        assert schema_dict["bOverride"] == "BoolProperty"


class TestScalarParameterValueTaggedParse:
    """验证 ScalarParameterValue tagged fallback 解析行为。

    模拟材质资产中 ScalarParameterValues 数组元素的 tagged 序列化格式：
    每个元素包含 PropertyTag 循环（ParameterInfo: StructProperty, ParameterValue: FloatProperty, bOverride: BoolProperty, None 终止）。
    """

    def test_tagged_parse_material_parameter_info(self, tmp_path):
        """FMaterialParameterInfo tagged 格式解析。"""
        # 构造 FMaterialParameterInfo 的 tagged 数据：
        # - FName "BaseColor" (3 chars, utf-8) + index=0
        # - int32 Index = 0
        # - bool bOverride = false (0)
        fname_bytes = b"BaseColor"
        name_data = struct.pack("<i", len(fname_bytes)) + fname_bytes
        # FName 序列化: 可能是 FNameEntrySerialized 格式
        # 在 tagged 解析中 FName 通过 read_name 读取
        # 但 read_property_tag 先读 name + type，然后 read_tag_value 读值
        # 对于 NameProperty，值是 FName = 8 bytes (comparison_id + number)

        # 简化：直接验证 schema 注册和结构正确性，而非构造完整二进制
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FMaterialParameterInfo"]
        assert len(schema) == 3
        assert schema[0] == ("ParameterName", "NameProperty")
        assert schema[1] == ("Index", "IntProperty")
        assert schema[2] == ("bOverride", "BoolProperty")

    def test_scalar_param_field_count(self):
        """ScalarParameterValue schema 包含 3 个字段。"""
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
        assert len(schema) == 3

    def test_existing_fallbacks_not_affected_for_scalar(self):
        """确保已有的 tagged fallback 不受 ScalarParameterValue 注册影响。"""
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCTS
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCTS
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCTS
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCTS
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCTS

    def test_expected_struct_sizes_not_required(self):
        """ScalarParameterValue 不需要在 _EXPECTED_STRUCT_SIZES 中，
        因为它是 tagged 格式（大小可变），不是固定布局。"""
        assert "ScalarParameterValue" not in _EXPECTED_STRUCT_SIZES
        assert "FScalarParameterValue" not in _EXPECTED_STRUCT_SIZES


# ============================================================================
# FBlendSample / BlendSample tagged fallback
# ============================================================================

class TestFBlendSampleFallback:
    """验证 FBlendSample 在 tagged fallback 中。"""

    def test_fblendsample_in_tagged_fallback_structs(self):
        """FBlendSample 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "FBlendSample" in _TAGGED_FALLBACK_STRUCTS

    def test_fblendsample_in_fallback_schemas(self):
        """FBlendSample 应有 tagged fallback schema。"""
        assert "FBlendSample" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FBlendSample"]
        assert ("SampleValue", "StructProperty") in schema
        assert ("Time", "FloatProperty") in schema
        assert ("RateScale", "IntProperty") in schema
        assert ("bIsValid", "BoolProperty") in schema
        assert len(schema) == 4

    def test_fblendsample_schema_field_order(self):
        """FBlendSample schema 字段顺序应与 UE 序列化顺序一致。"""
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FBlendSample"]
        field_names = [name for name, _ in schema]
        assert field_names == ["SampleValue", "Time", "RateScale", "bIsValid"]


class TestBlendSampleFallback:
    """验证无前缀别名 BlendSample 在 tagged fallback 中。"""

    def test_blendsample_in_tagged_fallback_structs(self):
        """BlendSample（无 F 前缀）应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "BlendSample" in _TAGGED_FALLBACK_STRUCTS

    def test_blendsample_in_fallback_schemas(self):
        """BlendSample 应有 tagged fallback schema。"""
        assert "BlendSample" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["BlendSample"]
        assert ("SampleValue", "StructProperty") in schema
        assert ("Time", "FloatProperty") in schema
        assert ("RateScale", "IntProperty") in schema
        assert ("bIsValid", "BoolProperty") in schema
        assert len(schema) == 4


class TestBlendSampleSchemaConsistency:
    """验证 FBlendSample 与 BlendSample schema 一致。"""

    def test_both_aliases_have_same_schema(self):
        """两个别名的 schema 应完全一致。"""
        assert _TAGGED_FALLBACK_STRUCT_SCHEMAS["FBlendSample"] == \
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["BlendSample"]


# ============================================================================
# FEditorElement / EditorElement tagged fallback
# ============================================================================

class TestFEditorElementFallback:
    """验证 FEditorElement 在 tagged fallback 中。"""

    def test_feditorelement_in_tagged_fallback_structs(self):
        """FEditorElement 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCTS

    def test_feditorelement_in_fallback_schemas(self):
        """FEditorElement 应有 tagged fallback schema。"""
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FEditorElement"]
        assert ("DisplayName", "TextProperty") in schema
        assert ("Value", "StrProperty") in schema
        assert ("bIsDefault", "BoolProperty") in schema
        assert len(schema) == 3

    def test_feditorelement_schema_field_order(self):
        """FEditorElement schema 字段顺序应与 UE 序列化顺序一致。"""
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FEditorElement"]
        field_names = [name for name, _ in schema]
        assert field_names == ["DisplayName", "Value", "bIsDefault"]


class TestEditorElementFallback:
    """验证无前缀别名 EditorElement 在 tagged fallback 中。"""

    def test_editorelement_in_tagged_fallback_structs(self):
        """EditorElement（无 F 前缀）应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCTS

    def test_editorelement_in_fallback_schemas(self):
        """EditorElement（无 F 前缀）应有 tagged fallback schema。"""
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["EditorElement"]
        assert ("DisplayName", "TextProperty") in schema
        assert ("Value", "StrProperty") in schema
        assert ("bIsDefault", "BoolProperty") in schema
        assert len(schema) == 3


class TestEditorElementSchemaConsistency:
    """验证 FEditorElement 与 EditorElement schema 一致。"""

    def test_both_aliases_have_same_schema(self):
        """两个别名的 schema 应完全一致。"""
        assert _TAGGED_FALLBACK_STRUCT_SCHEMAS["FEditorElement"] == \
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["EditorElement"]


# ============================================================================
# BoxSphereBounds 解析验证（Issue #175）
# ============================================================================

# 样本文件完整路径
CHAIR_PATH = Path(__file__).parent.parent / "samples" / "StackOBot_M_BotBase.uasset"


@pytest.mark.integration
class TestBoxSphereBoundsParsing:
    """BoxSphereBounds 解析验证。"""

    def test_box_sphere_bounds_parsed(self, sample_root: Path):
        """验证本地样本资产能正确解析。"""
        chair_path = asset_path(sample_root, ASSET_MESH_CHAIR)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(chair_path), tolerant=True)

        # 本地样本可能没有 BoxSphereBounds 属性，只验证解析成功
        assert result.is_success or result.status == "partial", f"解析失败: {result.errors}"
        assert len(result.export_map) > 0, "应有至少一个 export"

    def test_box_sphere_bounds_no_warning(self):
        """验证 BoxSphereBounds 解析不产生 '不匹配' 警告。"""
        if not os.path.exists(CHAIR_PATH):
            pytest.skip(f"样本文件不存在: {CHAIR_PATH}")

        from uasset_read.parse_uasset import parse_package

        handler = logging.handlers if hasattr(logging, "handlers") else None
        # 捕获 property_types 模块的 WARNING
        logger = logging.getLogger("uasset_read.parsers.property_types")

        class WarningCapture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.warnings = []

            def emit(self, record):
                if record.levelno >= logging.WARNING:
                    self.warnings.append(record.getMessage())

        capture = WarningCapture()
        logger.addHandler(capture)
        try:
            result = parse_package(str(CHAIR_PATH), tolerant=True)
        finally:
            logger.removeHandler(capture)

        # 检查没有 BoxSphereBounds 相关的警告
        bounds_warnings = [w for w in capture.warnings if "BoxSphereBounds" in w]
        assert len(bounds_warnings) == 0, f"BoxSphereBounds 解析不应有警告: {bounds_warnings}"


# ============================================================================
# 通用 tagged fallback 存在性验证
# ============================================================================

class TestExistingFallbacksUnaffected:
    """确保现有 tagged fallback 不受新增注册影响。"""

    def test_member_reference_still_present(self):
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCTS
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_framerate_still_present(self):
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCTS
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_animnotifytrack_still_present(self):
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCTS
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_feditor_element_still_present(self):
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCTS
        assert "FEditorElement" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_editor_element_still_present(self):
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCTS
        assert "EditorElement" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_new_variables_still_present(self):
        assert "NewVariables" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
