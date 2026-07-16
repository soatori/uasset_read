"""mappings.py _decompress 一致性测试。"""
import pytest
from uasset_read.mappings import UsmapParser


class TestMappingsDecompress:
    def test_uncompressed_passthrough(self):
        """未压缩数据应直接返回。"""
        parser = UsmapParser.__new__(UsmapParser)
        data = b'\x00' * 10 + b'test payload'
        result = parser._decompress(data, method=0, comp_size=len(data), decomp_size=len(data))
        assert result == data

    def test_uncompressed_size_mismatch_raises(self):
        """未压缩但大小不一致应抛出 ParseError。"""
        parser = UsmapParser.__new__(UsmapParser)
        data = b'\x00' * 10
        with pytest.raises(Exception, match="大小不一致"):
            parser._decompress(data, method=0, comp_size=10, decomp_size=20)

    def test_unsupported_method_raises(self):
        """不支持的压缩方式应抛出 ParseError。"""
        parser = UsmapParser.__new__(UsmapParser)
        with pytest.raises(Exception, match="不支持"):
            parser._decompress(b'', method=99, comp_size=0, decomp_size=0)
