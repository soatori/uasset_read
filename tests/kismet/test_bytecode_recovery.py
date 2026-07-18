"""Bytecode recovery 测试 — #424 serial_scan_recovery 伪 EExprToken 修复"""
import pytest


def test_scan_recovery_rejects_false_positive_tokens():
    """验证 _PLAUSIBLE_SCRIPT_START_TOKENS 不包含易误报的 token。"""
    from uasset_read.kismet.bytecode_extractor import _PLAUSIBLE_SCRIPT_START_TOKENS

    # 这些 token 在数据区域频繁出现，不应作为合法脚本起始 token
    false_positives = {
        0x1D,  # EX_IntConst — 裸整数常量，内嵌数据中极常见
        0x5A,  # EX_WireTracepoint — 调试标记，生产资产中不存在
        0x5E,  # EX_Tracepoint — 同上
    }

    for token in false_positives:
        assert token not in _PLAUSIBLE_SCRIPT_START_TOKENS, \
            f"Token 0x{token:02X} should not be in _PLAUSIBLE_SCRIPT_START_TOKENS"


def test_has_false_positive_pattern_int_const_heavy():
    """过多连续 0x1D (EX_IntConst) 字节应被判定为伪数据。"""
    from uasset_read.kismet.bytecode_extractor import _has_false_positive_pattern

    # 构造含大量 0x1D 的字节流：模拟内嵌整数表
    data = b"\x1D\x00\x00\x00\x00" * 8  # 8 个 IntConst + 4 字节值
    assert _has_false_positive_pattern(data) is True


def test_has_false_positive_pattern_repeated_byte():
    """超过 50% 相同字节的流应被判定为伪数据。"""
    from uasset_read.kismet.bytecode_extractor import _has_false_positive_pattern

    # 80% 都是 0x00
    data = b"\x00" * 80 + b"\x01" * 20
    assert _has_false_positive_pattern(data) is True


def test_has_false_positive_pattern_clean_bytecode():
    """正常字节流不应被误判为伪数据。"""
    from uasset_read.kismet.bytecode_extractor import _has_false_positive_pattern

    # 模拟简短的正常表达式序列（Return + FinalFunction + EndOfScript）
    data = bytes([0x04, 0x1C, 0x01, 0x02, 0x03, 0x04, 0x53])
    assert _has_false_positive_pattern(data) is False


def test_has_false_positive_pattern_short_data():
    """长度 < 4 的数据永远返回 False。"""
    from uasset_read.kismet.bytecode_extractor import _has_false_positive_pattern

    assert _has_false_positive_pattern(b"\x1D\x1D\x1D") is False
    assert _has_false_positive_pattern(b"") is False
