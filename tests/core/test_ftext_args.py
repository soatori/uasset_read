"""FText args 数量限制测试。"""
import pytest
from uasset_read.archive import ByteArchive
from uasset_read.serializers.graph import read_ftext_with_history


def test_ftext_named_format_arg_overflow():
    """FText NamedFormat arg_count 超限时应容错而非崩溃。"""
    from uasset_read.constants import MAX_SAFE_COUNT

    # 构造一个畸形的 FText 数据
    # format_text 是一个完整的 FText（history_type = -1, None）
    # history_type = 1 (NamedFormat)
    # arg_count = MAX_SAFE_COUNT + 1 (超限)
    data = b'\x00\x00\x00\x00'  # format_text 的 flags
    data += b'\xFF'  # format_text 的 history_type = -1 (None)
    data += b'\x00\x00\x00\x00'  # format_text 的 bHasCultureInvariantString = False
    data += (MAX_SAFE_COUNT + 1).to_bytes(4, 'little', signed=True)  # arg_count

    archive = ByteArchive(data, tolerant=True)

    # 在 tolerant 模式下应返回空字符串而非崩溃
    value, consumed = read_ftext_with_history(archive, history_type=1, tolerant=True)
    assert isinstance(value, str)


def test_ftext_named_format_negative_arg_count():
    """FText NamedFormat 负 arg_count 应容错而非崩溃。"""
    # 构造一个畸形的 FText 数据
    # format_text 是一个完整的 FText（history_type = -1, None）
    # history_type = 1 (NamedFormat)
    # arg_count = -1 (负数)
    data = b'\x00\x00\x00\x00'  # format_text 的 flags
    data += b'\xFF'  # format_text 的 history_type = -1 (None)
    data += b'\x00\x00\x00\x00'  # format_text 的 bHasCultureInvariantString = False
    data += (-1).to_bytes(4, 'little', signed=True)  # -1

    archive = ByteArchive(data, tolerant=True)

    # 在 tolerant 模式下应返回空字符串而非崩溃
    value, consumed = read_ftext_with_history(archive, history_type=1, tolerant=True)
    assert isinstance(value, str)
