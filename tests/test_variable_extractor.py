"""Blueprint 变量提取器测试。"""
import pytest
from uasset_read.models.properties import StructValue
from uasset_read.blueprint.variable_extractor import _guid_from_description


class TestGuidFromDescription:
    """_guid_from_description 各种输入格式处理。"""

    def test_struct_value_guid(self):
        """StructValue(Guid, {A,B,C,D}) 应转换为十六进制字符串。"""
        sv = StructValue(
            struct_type="Guid",
            fields={"A": 0x01020304, "B": 0x05060708, "C": 0x090A0B0C, "D": 0x0D0E0F10}
        )
        result = _guid_from_description(sv)
        # 4个uint32按小端序字节排列
        assert result != "", "StructValue Guid 不应返回空字符串"
        assert "-" in result, "GUID 应包含连字符分隔符"

    def test_struct_value_zero_guid(self):
        """全零 Guid 也应返回有效字符串。"""
        sv = StructValue(struct_type="Guid", fields={"A": 0, "B": 0, "C": 0, "D": 0})
        result = _guid_from_description(sv)
        assert result != "", "全零 Guid 不应返回空字符串"

    def test_dict_binary_or_native_still_works(self):
        """原有 dict + binary_or_native_property 路径应保持兼容。"""
        d = {
            "kind": "binary_or_native_property",
            "raw_data": b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
        }
        result = _guid_from_description(d)
        assert result == "00010203-0405-0607-0809-0a0b0c0d0e0f"

    def test_bytes_input_still_works(self):
        """原始 bytes 输入应保持兼容。"""
        result = _guid_from_description(b'\xAA\xBB\xCC\xDD' * 4)
        assert result == "aabbccdd-aabb-ccdd-aabb-ccddaabbccdd"

    def test_string_input_passthrough(self):
        """字符串输入应直接返回。"""
        s = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert _guid_from_description(s) == s

    def test_none_returns_empty(self):
        """None 应返回空字符串。"""
        assert _guid_from_description(None) == ""

    def test_int_returns_empty(self):
        """非预期类型应返回空字符串。"""
        assert _guid_from_description(0) == ""
