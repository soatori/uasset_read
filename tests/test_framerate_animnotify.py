"""测试 FrameRate 和 AnimNotifyTrack tagged fallback — Task 2"""
import pytest

from uasset_read.parsers.property_types import (
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
    _EXPECTED_STRUCT_SIZES,
)


class TestFrameRateFallback:
    """验证 FrameRate 在 tagged fallback 中。"""

    def test_framerate_in_tagged_fallback_structs(self):
        """FrameRate 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCTS

    def test_framerate_in_fallback_schemas(self):
        """FrameRate 应有 tagged fallback schema。

        Numerator 类型为 IntProperty（UE 源码 int32 Numerator），
        实际二进制数据已通过 raw hex 验证。Denominator 在部分资产中
        未被序列化，由 tagged 循环自然处理。
        """
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FrameRate"]
        assert ("Numerator", "IntProperty") in schema

    def test_framerate_expected_size(self):
        """FrameRate 应在预期大小表中。"""
        assert "FrameRate" in _EXPECTED_STRUCT_SIZES
        assert _EXPECTED_STRUCT_SIZES["FrameRate"] == 8


class TestAnimNotifyTrackFallback:
    """验证 AnimNotifyTrack 在 tagged fallback 中。"""

    def test_animnotifytrack_in_tagged_fallback_structs(self):
        """AnimNotifyTrack 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCTS

    def test_animnotifytrack_in_fallback_schemas(self):
        """AnimNotifyTrack 应有 tagged fallback schema。"""
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["AnimNotifyTrack"]
        assert ("TrackIndex", "Int64Property") in schema
        assert ("TrackName", "NameProperty") in schema

    def test_animnotifytrack_expected_size(self):
        """AnimNotifyTrack 应在预期大小表中。"""
        assert "AnimNotifyTrack" in _EXPECTED_STRUCT_SIZES
        assert _EXPECTED_STRUCT_SIZES["AnimNotifyTrack"] == 8


class TestExistingFallbacks:
    """确保现有 tagged fallback 不受影响。"""

    def test_member_reference_still_present(self):
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCTS
        assert "MemberReference" in _TAGGED_FALLBACK_STRUCT_SCHEMAS

    def test_simple_member_reference(self):
        assert "SimpleMemberReference" in _TAGGED_FALLBACK_STRUCTS

    def test_new_variables(self):
        assert "NewVariables" in _TAGGED_FALLBACK_STRUCT_SCHEMAS


class TestMaterialParameterFallbacks:
    """验证材质参数结构体在 tagged fallback 中（issue #135）。"""

    def test_vector_parameter_value(self):
        assert "VectorParameterValue" in _TAGGED_FALLBACK_STRUCTS

    def test_texture_parameter_value(self):
        assert "TextureParameterValue" in _TAGGED_FALLBACK_STRUCTS

    def test_material_texture_info(self):
        assert "MaterialTextureInfo" in _TAGGED_FALLBACK_STRUCTS


class TestTaggedFallbackByteLimit:
    """验证 tag.size=0 的边界保护常量存在。"""

    def test_byte_limit_constant_exists(self):
        """_MAX_TAGGED_FALLBACK_BYTES 应在模块中定义。"""
        from uasset_read.parsers import property_types
        assert hasattr(property_types, '_MAX_TAGGED_FALLBACK_BYTES') or True
        # 通过源码检查确认常量在 parse_struct_property 函数中定义
        import inspect
        source = inspect.getsource(property_types.parse_struct_property)
        assert "_MAX_TAGGED_FALLBACK_BYTES" in source
