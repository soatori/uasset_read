"""P3 内存安全测试 - 低风险防御性限制"""
import pytest
from io import BytesIO
from unittest.mock import Mock, patch
from uasset_read.pak.index import parse_primary_index
from uasset_read.pak.structures import FPakInfo
from uasset_read.exceptions import ParseError


def test_pak_num_entries_limit():
    """测试 PAK 索引条目数上限"""
    # 构造测试数据：mount_point (空字符串) + num_entries (超大值)
    test_data = BytesIO(
        b'\x00\x00\x00\x00'  # mount_point length = 0
        b'\xff\xff\xff\x7f'  # num_entries = 2147483647 (超过 10M 限制)
    )

    mock_pak_info = Mock(spec=FPakInfo)
    mock_pak_info.index_offset = 0
    mock_pak_info.index_size = len(test_data.getvalue())
    mock_pak_info.version = 11  # v11 > PathHashIndex
    mock_pak_info.encrypted_index = False
    mock_pak_info.index_hash = b'\x00' * 20

    # Mock validate_index_hash 返回 True（跳过哈希验证）
    with patch('uasset_read.pak.crypto.validate_index_hash', return_value=True):
        with pytest.raises(ParseError, match="PAK entry count.*exceeds limit"):
            parse_primary_index(test_data, mock_pak_info)
