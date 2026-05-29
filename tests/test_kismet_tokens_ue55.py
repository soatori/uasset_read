"""UE5.5 Kismet Token 扩展测试"""
from uasset_read.kismet.tokens import EExprToken


def test_ex_max_is_0xff():
    """验证 EX_Max 值为 0xFF"""
    assert EExprToken.EX_Max == 0xFF


def test_0xff_token_exists():
    """0xFF 应该能被识别为有效 token"""
    token = EExprToken(0xFF)
    assert token is not None
