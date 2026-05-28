"""PropertyTag flags 解析测试。"""
import pytest

from uasset_read.serializers.property_tags import parse_ctrl_flags


class TestParseCtrlFlags:
    """parse_ctrl_flags 工具函数测试。"""

    def test_zero_flags(self):
        flags = parse_ctrl_flags(0x00)
        assert all(v is False for v in flags.values())

    def test_has_array_index(self):
        flags = parse_ctrl_flags(0x01)
        assert flags["has_array_index"] is True
        assert flags["has_property_guid"] is False

    def test_has_property_guid(self):
        flags = parse_ctrl_flags(0x02)
        assert flags["has_property_guid"] is True
        assert flags["has_array_index"] is False

    def test_has_extensions(self):
        flags = parse_ctrl_flags(0x04)
        assert flags["has_extensions"] is True

    def test_has_binary_or_native(self):
        flags = parse_ctrl_flags(0x08)
        assert flags["has_binary_or_native"] is True

    def test_bool_true(self):
        flags = parse_ctrl_flags(0x10)
        assert flags["bool_true"] is True

    def test_skipped_serialize(self):
        flags = parse_ctrl_flags(0x20)
        assert flags["skipped_serialize"] is True

    def test_combined_flags(self):
        # 0x01 | 0x04 | 0x10 = 0x15
        flags = parse_ctrl_flags(0x15)
        assert flags["has_array_index"] is True
        assert flags["has_property_guid"] is False
        assert flags["has_extensions"] is True
        assert flags["has_binary_or_native"] is False
        assert flags["bool_true"] is True
        assert flags["skipped_serialize"] is False

    def test_all_flags(self):
        flags = parse_ctrl_flags(0x3F)
        assert all(v is True for v in flags.values())

    def test_upper_bits_ignored(self):
        # 0x80 不应影响低 6 位
        flags = parse_ctrl_flags(0x80)
        assert all(v is False for v in flags.values())
