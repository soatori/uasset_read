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
        """FrameRate 应有 tagged fallback schema。"""
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FrameRate"]
        assert ("Numerator", "FloatProperty") in schema
        assert ("Denominator", "IntProperty") in schema

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
