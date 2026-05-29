"""P73 Pin 连接恢复测试"""
from uasset_read.serializers.graph import _is_abnormal_pin_count, _recover_pin_count


def test_abnormal_pin_count_detection():
    """异常 Pin 计数值应该被检测"""
    assert _is_abnormal_pin_count(0xFF0000) == True
    assert _is_abnormal_pin_count(1001) == True
    assert _is_abnormal_pin_count(0x0100) == True
    assert _is_abnormal_pin_count(0) == False
    assert _is_abnormal_pin_count(5) == False


def test_pin_count_recovery():
    """异常 Pin 计数值应该被恢复"""
    assert _recover_pin_count(0xFF0000) == 0
    assert _recover_pin_count(0x0100) == 1
    assert _recover_pin_count(5) == 5
