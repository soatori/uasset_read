# tests/test_pak_encoded.py
"""Pak v10+ 编码条目测试"""
import struct
from io import BytesIO

def test_decode_encoded_entry():
    """测试解码 v10+ 编码条目"""
    from uasset_read.pak.structures import decode_encoded_pak_entry
    
    # 构造测试数据：压缩方法索引=1, 加密标志=0, 压缩块数=2
    # 位域布局: bits 0-5=压缩方法索引, bit 6=加密, bit 7=压缩, bits 8-17=压缩块数
    test_value = (1 << 0) | (0 << 6) | (0 << 7) | (2 << 8) | (0 << 22)
    data = struct.pack('<I', test_value)
    
    result = decode_encoded_pak_entry(data, is_enabled=True)
    assert result is not None
    assert result['compression_method_index'] == 1
    assert result['is_encrypted'] == False
    assert result['compression_block_count'] == 2

def test_decode_encoded_entry_with_size():
    """测试解码带大小的编码条目"""
    from uasset_read.pak.structures import decode_encoded_pak_entry
    
    # 64 位大小模式：bit 22 置 1
    data = struct.pack('<I', 0x00400000)  # 64 位大小标志 (bit 22)
    
    result = decode_encoded_pak_entry(data, is_enabled=True)
    assert result is not None
    assert result['has_64bit_size'] == True
