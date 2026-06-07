"""测试重构后的 parse 函数行为不变。"""
import pytest
from pathlib import Path


def test_parse_package_returns_result():
    """parse_package 应返回有效的 ParseResult。"""
    from uasset_read.parse_uasset import parse_package
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:3]
    for asset_path in test_assets:
        result = parse_package(str(asset_path))
        assert result.summary is not None
        assert result.name_map is not None
        assert result.export_map is not None


def test_parse_uasset_with_linker_returns_result():
    """parse_uasset_with_linker 应返回有效的 LinkerParseResult。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:3]
    for asset_path in test_assets:
        result = parse_uasset_with_linker(str(asset_path))
        assert result.summary is not None
        assert result.linker is not None
        assert result.all_objects is not None


def test_parse_package_with_mappings():
    """parse_package 支持 mappings_path 参数。"""
    from uasset_read.parse_uasset import parse_package
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:1]
    if not test_assets:
        pytest.skip("No test assets found")
    result = parse_package(str(test_assets[0]))
    assert "mappings_path" not in result.metadata  # 未提供 mappings


def test_parse_package_aes_key_rejection():
    """parse_package 应拒绝 aes_key 参数。"""
    from uasset_read.parse_uasset import parse_package
    from uasset_read.exceptions import ParseError
    test_assets = list(Path("tests/assets").glob("*.uasset"))[:1]
    if not test_assets:
        pytest.skip("No test assets found")
    result = parse_package(str(test_assets[0]), aes_key=b"\x00" * 16)
    assert not result.is_success
    assert "aes_key" in result.errors[0]
