"""Bulk Data 结构测试"""
import struct
from io import BytesIO

def test_bulk_data_header_creation():
    """测试 BulkDataHeader 创建"""
    from uasset_read.bulk.structures import FBulkDataHeader

    header = FBulkDataHeader(
        flags=0x01,
        element_count=100,
        element_size=4,
        offset_in_file=4096
    )
    assert header.flags == 0x01
    assert header.element_count == 100
    assert header.element_size == 4

def test_bulk_data_header_is_data_stored_inline():
    """测试内联数据标志"""
    from uasset_read.bulk.structures import FBulkDataHeader, BulkDataFlags

    header = FBulkDataHeader(flags=BulkDataFlags.DATA_IN_INLINE)
    assert header.is_data_stored_inline == True

def test_bulk_data_header_is_data_stored_separate_file():
    """测试分离文件存储标志"""
    from uasset_read.bulk.structures import FBulkDataHeader, BulkDataFlags

    header = FBulkDataHeader(flags=BulkDataFlags.DATA_SEPARATE_FILE)
    assert header.is_data_in_separate_file == True
