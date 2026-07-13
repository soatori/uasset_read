"""FTEXT-SAFETY 恢复位置测试。"""
import pytest
from unittest.mock import MagicMock, patch


def test_ftext_safety_recovery_position():
    """FTEXT-SAFETY 消耗超限时应回退到字段起始位置。"""
    from uasset_read.serializers.graph_pin import _read_pin_ftext_field
    from uasset_read.constants import MAX_FTEXT_CONSUMPTION

    mock_archive = MagicMock()
    # tell() 首次返回 0（字段起始），_read_ftext_value 后返回超限值
    mock_archive.tell.side_effect = [0, MAX_FTEXT_CONSUMPTION + 100]

    # 模拟一个消耗大量字节的 FText
    def mock_read_ftext_value(archive, tolerant=True):
        return ("value", 0, 0, MAX_FTEXT_CONSUMPTION + 100)

    with patch('uasset_read.serializers.graph_pin._read_ftext_value', mock_read_ftext_value):
        trace_fields = {}
        value, success = _read_pin_ftext_field(
            mock_archive, "TestField", False, trace_fields
        )

        # 应回退到 _start（字段起始位置），而非 _start + 5
        # 验证 seek 被调用且参数为 0（_start）
        mock_archive.seek.assert_called_with(0)
