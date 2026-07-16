"""测试 is_cooked 标志位判断逻辑 (Issue #381)"""

import pytest
from unittest.mock import MagicMock, patch

from uasset_read.constants import PKG_Cooked, PKG_UncookedOnly
from uasset_read.parse_stages import _read_secondary_tables
from uasset_read.models.result import ParseResult


def _make_mock_result(package_flags):
    """构造模拟的 ParseResult，确保 _read_secondary_tables 能走到 read_asset_registry_data。"""
    mock_result = MagicMock(spec=ParseResult)
    mock_result.summary.package_flags = package_flags
    mock_result.summary.asset_registry_data_offset = 100
    mock_result.summary.file_version_ue4 = 510
    mock_result.name_map = []
    # MagicMock 的 hasattr 总是返回 True，所以必须设置这些属性为 0，
    # 让条件判断 `> 0` 返回 False，跳过不需要的读取步骤
    mock_result.summary.soft_package_references_count = 0
    mock_result.summary.soft_object_paths_count = 0
    # depends_offset 和 preload_dependency_count 不参与 > 0 比较，
    # hasattr 总是 True，但 read_depends_map / read_preload_dependencies 已被 patch，安全
    return mock_result


def _call_secondary_tables(mock_result):
    """调用 _read_secondary_tables，patch 中间依赖函数以隔离 is_cooked 逻辑。"""
    with patch('uasset_read.parse_stages.read_asset_registry_data') as mock_read, \
         patch('uasset_read.parse_stages.read_depends_map'), \
         patch('uasset_read.parse_stages.read_preload_dependencies'), \
         patch('uasset_read.parse_stages.read_soft_package_references'), \
         patch('uasset_read.parse_stages.read_soft_object_paths'):
        mock_read.return_value = None
        _read_secondary_tables(
            archive=MagicMock(),
            result=mock_result,
            tolerant=True,
            linker=MagicMock(),
            mappings_provider=MagicMock(),
            path="test.uasset",
            memory_monitor=MagicMock(),
        )
        return mock_read


class TestIsCookedFlag:
    """测试 is_cooked 标志位判断"""

    def test_is_cooked_uses_pkg_cooked_flag(self):
        """验证 is_cooked 使用 PKG_Cooked (0x200) 而非 PKG_UncookedOnly (0x100)"""
        mock_result = _make_mock_result(PKG_Cooked)  # 0x200
        mock_read = _call_secondary_tables(mock_result)

        assert mock_read.called, "read_asset_registry_data 应被调用"
        call_kwargs = mock_read.call_args[1]
        assert call_kwargs.get('is_cooked') is True, \
            "PKG_Cooked 设置时 is_cooked 应为 True"

    def test_not_cooked_when_no_flag(self):
        """验证无 PKG_Cooked 标志时 is_cooked=False"""
        mock_result = _make_mock_result(0)  # 无标志
        mock_read = _call_secondary_tables(mock_result)

        assert mock_read.called, "read_asset_registry_data 应被调用"
        call_kwargs = mock_read.call_args[1]
        assert call_kwargs.get('is_cooked') is False, \
            "无 PKG_Cooked 标志时 is_cooked 应为 False"

    def test_pkg_uncooked_only_does_not_affect_is_cooked(self):
        """验证 PKG_UncookedOnly (0x100) 不影响 is_cooked 判断"""
        mock_result = _make_mock_result(PKG_UncookedOnly)  # 0x100
        mock_read = _call_secondary_tables(mock_result)

        assert mock_read.called, "read_asset_registry_data 应被调用"
        call_kwargs = mock_read.call_args[1]
        assert call_kwargs.get('is_cooked') is False, \
            "PKG_UncookedOnly 不应影响 is_cooked（应为 False）"

    def test_both_flags_set(self):
        """验证同时设置 PKG_Cooked 和 PKG_UncookedOnly 时的行为"""
        mock_result = _make_mock_result(PKG_Cooked | PKG_UncookedOnly)
        mock_read = _call_secondary_tables(mock_result)

        assert mock_read.called, "read_asset_registry_data 应被调用"
        call_kwargs = mock_read.call_args[1]
        # PKG_Cooked 存在，所以 is_cooked 应为 True
        assert call_kwargs.get('is_cooked') is True, \
            "PKG_Cooked 存在时 is_cooked 应为 True"

    def test_constants_values(self):
        """验证常量值正确"""
        assert PKG_Cooked == 0x200, "PKG_Cooked 应为 0x200"
        assert PKG_UncookedOnly == 0x100, "PKG_UncookedOnly 应为 0x100"
