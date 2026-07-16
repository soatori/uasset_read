"""UsmapData 文件读取 budget 预留。"""
import os
import struct
import tempfile
from uasset_read.parsers.usmap import UsmapData


class RecordingBudget:
    """记录 reserve 调用。"""
    def __init__(self):
        self.calls = []
    def reserve(self, amount, label=""):
        self.calls.append((amount, label))
    def check(self, amount, label=""):
        pass


def _make_minimal_usmap() -> bytes:
    """创建最小有效 usmap 文件内容。

    格式:
      - 2 bytes: magic (0x30C4, little-endian)
      - 1 byte: version (0)
      - 1 byte: compression method (0 = none)
      - 4 bytes: comp_size (little-endian uint32)
      - 4 bytes: decomp_size (little-endian uint32)
      - payload (comp_size bytes)
    """
    magic = struct.pack('<H', 0x30C4)
    version = struct.pack('B', 0)
    compression = struct.pack('B', 0)  # 无压缩

    # 构建解压后的内容：name_count=1, name="Test"
    # version 0: name length 是 u8 (1 字节)
    name_payload = struct.pack('<I', 1)     # name_count
    name_payload += struct.pack('B', 4)     # name 长度 (u8)
    name_payload += b'Test'                 # name 内容
    name_payload += struct.pack('<I', 0)  # enum_count
    name_payload += struct.pack('<I', 0)  # schema_count

    decomp_size = len(name_payload)
    comp_size = decomp_size  # 无压缩时 comp_size == decomp_size
    comp_size_bytes = struct.pack('<I', comp_size)
    decomp_size_bytes = struct.pack('<I', decomp_size)

    return magic + version + compression + comp_size_bytes + decomp_size_bytes + name_payload


def test_usmap_file_read_reserves_budget():
    """UsmapData 从文件加载时应调用 budget.reserve。"""
    budget = RecordingBudget()
    data = _make_minimal_usmap()
    with tempfile.NamedTemporaryFile(suffix=".usmap", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        UsmapData(path, budget=budget)
        reserve_calls = [c for c in budget.calls if c[1] == "usmap_file_read"]
        assert len(reserve_calls) == 1, f"应有 1 次 usmap_file_read reserve, 实际: {reserve_calls}"
        assert reserve_calls[0][0] == os.path.getsize(path)
    finally:
        os.unlink(path)
