"""TopLevelAssetPath 结构体大小和解析测试。"""
from uasset_read.parsers.property_types import (
    _EXPECTED_STRUCT_SIZES,
    _TAGGED_FALLBACK_STRUCTS,
)


class TestTopLevelAssetPath:
    def test_expected_size_is_none(self):
        """TopLevelAssetPath 应为 None（可变大小，由 fast-path 直接处理）。"""
        size = _EXPECTED_STRUCT_SIZES.get("TopLevelAssetPath")
        assert size is None

    def test_not_in_tagged_fallback_structs(self):
        """TopLevelAssetPath 不应在 _TAGGED_FALLBACK_STRUCTS 中（expected_size=None 时 size-mismatch 块被跳过）。"""
        assert "TopLevelAssetPath" not in _TAGGED_FALLBACK_STRUCTS
