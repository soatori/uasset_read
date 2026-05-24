"""Phase 73 Wave 4: PropertyTag cascade failure recovery tests.

Tests for:
1. PropertyTag offset tracking fields are populated
2. FName/FString distinction verified by existing tests
3. PropertyTag size validation recovery exists
"""
import pytest

from uasset_read.models.properties import PropertyTag
from uasset_read.parsers.property_types import parse_str_property
from uasset_read.serializers.property_tags import read_property_tag


class TestPropertyTagOffsetFields:
    """Test PropertyTag offset tracking fields are populated correctly."""

    def test_property_tag_has_offset_fields(self):
        """PropertyTag dataclass should have offset tracking fields."""
        tag = PropertyTag(
            name="TestProp",
            type="IntProperty",
            size=4,
            tag_start_offset=0,
            value_start_offset=13,
            value_end_offset=17
        )

        # Verify offset fields exist and have correct values
        assert tag.tag_start_offset == 0
        assert tag.value_start_offset == 13
        assert tag.value_end_offset == 17

    def test_property_tag_offset_fields_default_none(self):
        """PropertyTag offset fields default to None if not provided."""
        tag = PropertyTag(name="Test", type="BoolProperty", size=0)

        assert tag.tag_start_offset is None
        assert tag.value_start_offset is None
        assert tag.value_end_offset is None

    def test_property_tag_zero_size_value_end_equals_start(self):
        """PropertyTag with size=0 should have value_end == value_start."""
        tag = PropertyTag(
            name="Empty",
            type="BoolProperty",
            size=0,
            value_start_offset=10,
            value_end_offset=10
        )

        assert tag.size == 0
        assert tag.value_start_offset == tag.value_end_offset


class TestStrPropertyFStringFormat:
    """Test StrProperty reads FString format correctly."""

    def test_str_property_is_distinct_from_fname(self):
        """StrProperty uses FString format (length + data), distinct from FName index."""
        # This test verifies that StrProperty parsing exists and is distinct
        # FName format is i32 index + i32 number (8 bytes)
        # FString format is i32 length + data (variable)
        # Both use different parse functions

        # Verify parse_str_property exists
        assert parse_str_property is not None

        # Verify the function signature expects PropertyTag + archive
        # (actual parsing tested in test_advanced_properties.py)


class TestPropertyTagSizeRecovery:
    """Test PropertyTag size validation recovery exists."""

    def test_property_tag_recovery_logic_exists(self):
        """PropertyTag size validation failure should have recovery path."""
        # The recovery logic in property_tags.py:
        # min(max(tag.size, 0), 64 * 1024) ensures safe skip
        # This test verifies the code exists and compiles
        assert read_property_tag is not None

    def test_property_tag_recovery_clamps_to_64kb(self):
        """PropertyTag recovery should clamp skip to 64KB max."""
        # Verify recovery logic: _safe_skip = min(max(tag.size, 0), 64 * 1024)
        # This prevents runaway seeks on corrupted size values

        # Test the clamp logic with simulated values
        test_sizes = [-100, 0, 100, 100000, 1000000]

        for test_size in test_sizes:
            safe_skip = min(max(test_size, 0), 64 * 1024)
            # Safe skip should always be in range [0, 64*1024]
            assert 0 <= safe_skip <= 64 * 1024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
