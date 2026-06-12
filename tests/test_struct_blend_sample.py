"""测试 FBlendSample / BlendSample tagged fallback。

FBlendSample 是 UE5 动画混合空间（UBlendSpace）中的采样点结构体，
定义于 Engine/Classes/Animation/BlendSpace.h：
  - SampleValue (FVector) — 混合空间采样点坐标
  - Time (float) — 动画时间值
  - RateScale (int32) — 播放速率缩放
  - bIsValid (bool) — 采样点是否有效

当该结构体在资产中使用 tagged 格式（PropertyTag 含类型信息）时，
通过 tagged fallback 解析路径处理。
"""
import pytest

from uasset_read.parsers.property_types import (
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
)


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


class TestExistingFallbacksUnaffected:
    """确保现有 tagged fallback 不受影响。"""

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
