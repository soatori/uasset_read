"""测试 pin_guid 格式统一 — Task 1

PinReference GUID 使用 _read_guid() 返回 8-4-4-4-12 带 dash 格式，
而 pin_id 使用 .hex().upper() 返回 32 字符纯 hex。
验证 _pin_ref_guid 归一化和 _is_valid_pin_guid 兼容两种格式。
"""
import pytest
from uasset_read.graph.flow_builder import _pin_ref_guid, _is_valid_pin_guid


class TestPinGuidFormat:
    """验证 PinReference GUID 与 pin_id 格式兼容。"""

    def test_pin_ref_guid_from_dict_with_dashes(self):
        """PinReference dict 返回归一化后的 GUID（无 dash，大写）。"""
        ref = {"pin_guid": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890", "owning_node": "TestNode"}
        result = _pin_ref_guid(ref)
        assert result == "A1B2C3D4E5F67890ABCDEF1234567890"

    def test_pin_ref_guid_from_dict_without_dashes(self):
        """纯 hex GUID 应转大写。"""
        ref = {"pin_guid": "a1b2c3d4e5f67890abcdef1234567890"}
        result = _pin_ref_guid(ref)
        assert result == "A1B2C3D4E5F67890ABCDEF1234567890"

    def test_pin_ref_guid_from_string(self):
        """字符串输入应归一化。"""
        result = _pin_ref_guid("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert result == "A1B2C3D4E5F67890ABCDEF1234567890"

    def test_pin_ref_guid_returns_none_for_empty(self):
        """空值返回 None。"""
        assert _pin_ref_guid({}) is None
        assert _pin_ref_guid("") is None
        assert _pin_ref_guid(None) is None

    def test_is_valid_pin_guid_accepts_32_char_hex(self):
        """接受 32 字符 hex GUID。"""
        assert _is_valid_pin_guid("A1B2C3D4E5F67890ABCDEF1234567890") is True

    def test_is_valid_pin_guid_accepts_36_char_dashed(self):
        """接受 36 字符带 dash GUID。"""
        assert _is_valid_pin_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890") is True

    def test_is_valid_pin_guid_accepts_lowercase_hex(self):
        """接受小写 hex GUID。"""
        assert _is_valid_pin_guid("a1b2c3d4e5f67890abcdef1234567890") is True

    def test_is_valid_pin_guid_accepts_zero_guid(self):
        """接受全零 GUID（ParentPin 空引用）。"""
        assert _is_valid_pin_guid("0" * 32) is True

    def test_is_valid_pin_guid_accepts_pin_prefix(self):
        """接受 pin- 前缀（测试 fixture）。"""
        assert _is_valid_pin_guid("pin-test-123") is True

    def test_is_valid_pin_guid_rejects_invalid(self):
        """拒绝非 hex 字符。"""
        assert _is_valid_pin_guid("not-a-valid-guid!!") is False
        assert _is_valid_pin_guid("") is False
        assert _is_valid_pin_guid(None) is False
        assert _is_valid_pin_guid("XYZ") is False

    def test_pin_ref_guid_normalized_matches_pin_lookup(self):
        """端到端测试：PinReference GUID 归一化后应匹配 pin_id。"""
        ref_guid = "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
        pin_id = "A1B2C3D4E5F67890ABCDEF1234567890"
        normalized = _pin_ref_guid(ref_guid)
        assert normalized == pin_id
        assert _is_valid_pin_guid(normalized) is True
