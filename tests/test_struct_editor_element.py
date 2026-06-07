"""测试 FEditorElement / EditorElement tagged fallback。

FEditorElement 是 UE5 蓝图编辑器中用于组合框（ComboBox）选项的结构体，
定义于 Runtime/Engine/Classes/Engine/BlueprintGeneratedClass.h：
  - DisplayName (FText) — 选项显示文本
  - Value (FString) — 选项值
  - bIsDefault (bool) — 是否为默认选项

当该结构体在蓝图资产中使用 tagged 格式（PropertyTag 含类型信息）时，
通过 tagged fallback 解析路径处理。
"""
import pytest

from uasset_read.parsers.property_types import (
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
)


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

    def test_new_variables_still_present(self):
        assert "NewVariables" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
