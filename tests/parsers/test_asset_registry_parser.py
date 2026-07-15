"""AssetRegistryData 容错测试。"""
import pytest
from uasset_read.parsers.asset_registry_parser import read_asset_registry_data
from uasset_read.exceptions import ParseError


class FailingArchive:
    """在 read_fstring 时抛 ParseError 的 mock。"""
    def seek(self, offset):
        pass
    def tell(self):
        return 0
    def total_size(self):
        return 1000
    def read_fstring(self):
        raise ParseError("short read from asset registry")
    def read_i32(self):
        return 1
    def read_i64(self):
        return 0


def test_asset_registry_data_parse_error_returns_partial():
    """ParseError 应被捕获，返回部分结果而非崩溃。"""
    archive = FailingArchive()
    # 不应抛异常
    result = read_asset_registry_data(archive, asset_registry_data_offset=100, file_version_ue4=510, is_cooked=True)
    assert result is not None  # 返回部分结果
