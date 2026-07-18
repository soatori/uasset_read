"""#424 验证：启发式过滤真实样本回归"""
import pytest

from uasset_read.kismet.bytecode_extractor import _has_false_positive_pattern


class TestFalsePositivePattern:
    """_has_false_positive_pattern 单元测试"""

    def test_consecutive_intconst_rejected(self):
        """连续 IntConst (0x1D) 后跟 4 字节整数 > 3 次应被识别为伪数据"""
        data = b""
        for i in range(4):
            data += bytes([0x1D]) + (i).to_bytes(4, "little")
        assert _has_false_positive_pattern(data) is True

    def test_repeated_byte_rejected(self):
        """超过 50% 字节相同应被识别为伪数据"""
        data = bytes([0x00] * 20 + [0x01] * 5)  # 80% 是 0x00
        assert _has_false_positive_pattern(data) is True

    def test_short_data_not_false_positive(self):
        """短数据（<4 字节）不应被判定为伪数据"""
        data = bytes([0x03, 0x05, 0x08])
        assert _has_false_positive_pattern(data) is False

    def test_valid_bytecode_preserved(self):
        """有效字节码不应被过滤"""
        data = bytes([
            0x1B, 0x00, 0x01, 0x02,
            0x03, 0x04, 0x05, 0x06,
            0x07, 0x08, 0x09, 0x0A,
            0x0B, 0x0C, 0x0D, 0x0E,
        ])
        assert _has_false_positive_pattern(data) is False

    def test_single_intconst_not_rejected(self):
        """单个 IntConst 不应被识别为伪数据"""
        data = bytes([0x1D, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
        assert _has_false_positive_pattern(data) is False

    def test_mixed_data_not_false_positive(self):
        """混合数据（无明显模式）不应被过滤"""
        data = bytes(range(32))  # 0x00 到 0x1F
        assert _has_false_positive_pattern(data) is False
