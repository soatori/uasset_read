# tests/test_iostore_api.py
"""IoStore 公共 API 测试"""
def test_iostore_import():
    """测试 IoStore 模块可导入"""
    from uasset_read import IoStoreReader
    assert IoStoreReader is not None

def test_iostore_structures_import():
    """测试 IoStore 结构可导入"""
    from uasset_read import FIoChunkId, FIoOffsetAndSize
    assert FIoChunkId is not None
    assert FIoOffsetAndSize is not None
