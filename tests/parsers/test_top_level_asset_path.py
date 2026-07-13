"""TopLevelAssetPath 结构体大小和解析测试。"""
import pytest
from uasset_read.parsers.property_types import (
    _EXPECTED_STRUCT_SIZES,
    _TAGGED_FALLBACK_STRUCTS,
)


class TestTopLevelAssetPath:
    def test_expected_size_is_not_16(self):
        """TopLevelAssetPath 的期望大小不应是 16。"""
        size = _EXPECTED_STRUCT_SIZES.get("TopLevelAssetPath")
        assert size != 16, "TopLevelAssetPath 大小已修正，不应再是 16"

    def test_expected_size_is_none(self):
        """TopLevelAssetPath 应为 None（可变大小，走 tagged fallback）。"""
        size = _EXPECTED_STRUCT_SIZES.get("TopLevelAssetPath")
        assert size is None

    def test_in_tagged_fallback_structs(self):
        """TopLevelAssetPath 应在 _TAGGED_FALLBACK_STRUCTS 中。"""
        assert "TopLevelAssetPath" in _TAGGED_FALLBACK_STRUCTS
