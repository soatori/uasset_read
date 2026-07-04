"""opaque_stub 工厂函数单元测试"""
from unittest.mock import MagicMock


def test_make_opaque_stub_returns_callable():
    """make_opaque_stub 应返回可调用对象"""
    from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub
    fn = make_opaque_stub("TestClass")
    assert callable(fn)


def test_make_opaque_stub_read_sample():
    """返回的函数应读取最多 256 字节样本"""
    from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub
    fn = make_opaque_stub("TestClass")
    archive = MagicMock()
    archive.tell.return_value = 100
    archive.total_size.return_value = 500
    archive.read.return_value = b"\x00" * 256
    result = fn(archive, [])
    assert result["raw_offset"] == 100
    assert result["sample_size"] == 256
    assert result["parse_status"] == "partial_metadata"


def test_make_opaque_stub_small_remainder():
    """剩余不足 256 字节时应读取全部剩余"""
    from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub
    fn = make_opaque_stub("TestClass")
    archive = MagicMock()
    archive.tell.return_value = 480
    archive.total_size.return_value = 500
    archive.read.return_value = b"\x00" * 20
    result = fn(archive, [])
    assert result["sample_size"] == 20


def test_make_opaque_stub_empty_archive():
    """archive 为空时应返回零样本"""
    from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub
    fn = make_opaque_stub("TestClass")
    archive = MagicMock()
    archive.tell.return_value = 100
    archive.total_size.return_value = 100
    archive.read.return_value = b""
    result = fn(archive, [])
    assert result["sample_size"] == 0
    assert result["parse_status"] == "partial_metadata"
