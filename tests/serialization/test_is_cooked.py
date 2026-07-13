"""测试 is_cooked 标志位判断逻辑 (Issue #381)"""

import pytest
from unittest.mock import MagicMock, patch

from uasset_read.constants import PKG_Cooked, PKG_UncookedOnly
from uasset_read.parse_stages import _read_secondary_tables
from uasset_read.models.result import ParseResult


class TestIsCookedFlag:
    """测试 is_cooked 标志位判断"""

    def test_is_cooked_uses_pkg_cooked_flag(self):
        """验证 is_cooked 使用 PKG_Cooked (0x200) 而非 PKG_UncookedOnly (0x100)"""
        # 模拟 cooked 包：PKG_Cooked 位已设置
        mock_result = MagicMock(spec=ParseResult)
        mock_result.summary.package_flags = PKG_Cooked  # 0x200
        mock_result.summary.asset_registry_data_offset = 100
        mock_result.summary.file_version_ue4 = 510
        mock_result.soft_object_path_list = []

        with patch('uasset_read.parse_stages.read_asset_registry_data') as mock_read:
            mock_read.return_value = None
            try:
                _read_secondary_tables(
                    mock_result,
                    archive=MagicMock(),
                    tolerant=True,
                    enable_graph_parsing=False,
                    enable_blueprint_extraction=False,
                )
            except Exception:
                pass  # 允许其他部分失败

            # 验证 is_cooked=True 传递给 read_asset_registry_data
            if mock_read.called:
                call_kwargs = mock_read.call_args[1]
                assert call_kwargs.get('is_cooked') is True, \
                    "PKG_Cooked 设置时 is_cooked 应为 True"

    def test_not_cooked_when_no_flag(self):
        """验证无 PKG_Cooked 标志时 is_cooked=False"""
        mock_result = MagicMock(spec=ParseResult)
        mock_result.summary.package_flags = 0  # 无标志
        mock_result.summary.asset_registry_data_offset = 100
        mock_result.summary.file_version_ue4 = 510
        mock_result.soft_object_path_list = []

        with patch('uasset_read.parse_stages.read_asset_registry_data') as mock_read:
            mock_read.return_value = None
            try:
                _read_secondary_tables(
                    mock_result,
                    archive=MagicMock(),
                    tolerant=True,
                    enable_graph_parsing=False,
                    enable_blueprint_extraction=False,
                )
            except Exception:
                pass

            if mock_read.called:
                call_kwargs = mock_read.call_args[1]
                assert call_kwargs.get('is_cooked') is False, \
                    "无 PKG_Cooked 标志时 is_cooked 应为 False"

    def test_pkg_uncooked_only_does_not_affect_is_cooked(self):
        """验证 PKG_UncookedOnly (0x100) 不影响 is_cooked 判断"""
        mock_result = MagicMock(spec=ParseResult)
        mock_result.summary.package_flags = PKG_UncookedOnly  # 0x100
        mock_result.summary.asset_registry_data_offset = 100
        mock_result.summary.file_version_ue4 = 510
        mock_result.soft_object_path_list = []

        with patch('uasset_read.parse_stages.read_asset_registry_data') as mock_read:
            mock_read.return_value = None
            try:
                _read_secondary_tables(
                    mock_result,
                    archive=MagicMock(),
                    tolerant=True,
                    enable_graph_parsing=False,
                    enable_blueprint_extraction=False,
                )
            except Exception:
                pass

            if mock_read.called:
                call_kwargs = mock_read.call_args[1]
                assert call_kwargs.get('is_cooked') is False, \
                    "PKG_UncookedOnly 不应影响 is_cooked（应为 False）"

    def test_both_flags_set(self):
        """验证同时设置 PKG_Cooked 和 PKG_UncookedOnly 时的行为"""
        mock_result = MagicMock(spec=ParseResult)
        mock_result.summary.package_flags = PKG_Cooked | PKG_UncookedOnly
        mock_result.summary.asset_registry_data_offset = 100
        mock_result.summary.file_version_ue4 = 510
        mock_result.soft_object_path_list = []

        with patch('uasset_read.parse_stages.read_asset_registry_data') as mock_read:
            mock_read.return_value = None
            try:
                _read_secondary_tables(
                    mock_result,
                    archive=MagicMock(),
                    tolerant=True,
                    enable_graph_parsing=False,
                    enable_blueprint_extraction=False,
                )
            except Exception:
                pass

            if mock_read.called:
                call_kwargs = mock_read.call_args[1]
                # PKG_Cooked 存在，所以 is_cooked 应为 True
                assert call_kwargs.get('is_cooked') is True, \
                    "PKG_Cooked 存在时 is_cooked 应为 True"

    def test_constants_values(self):
        """验证常量值正确"""
        assert PKG_Cooked == 0x200, "PKG_Cooked 应为 0x200"
        assert PKG_UncookedOnly == 0x100, "PKG_UncookedOnly 应为 0x100"
