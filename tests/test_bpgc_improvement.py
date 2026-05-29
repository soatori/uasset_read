"""BPGC 字节码回退改进测试"""
import struct
from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer


def test_parse_with_trailing_garbage():
    """应该能处理尾部垃圾数据"""
    func1 = bytes([0x00, 0x01, 0x04, 0x53])
    garbage = b'\xFF\xFF\xFF\xFF'

    data = struct.pack('<I', len(func1)) + func1 + garbage
    buffers = _parse_cooked_bytecode_buffer(data)

    assert len(buffers) == 1
    assert buffers[0].endswith(b'\x53')


def test_parse_multiple_functions():
    """应该能正确解析多个函数"""
    func1 = bytes([0x00, 0x53])
    func2 = bytes([0x01, 0x53])
    func3 = bytes([0x04, 0x53])

    data = (
        struct.pack('<I', len(func1)) + func1 +
        struct.pack('<I', len(func2)) + func2 +
        struct.pack('<I', len(func3)) + func3
    )

    buffers = _parse_cooked_bytecode_buffer(data)
    assert len(buffers) == 3
