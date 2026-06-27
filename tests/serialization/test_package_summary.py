"""package_name 填充验证 — Issue #175。

验证 summary.package_name 不为字符串 'None'，且正确填充。
"""
from pathlib import Path

import pytest

from tests.conftest import asset_path, ASSET_TEXTURE_BRICK


class TestPackageName:
    """package_name 字段正确性。"""

    def test_package_name_not_none_string(self, sample_root: Path):
        """package_name 不应为字符串 'None'"""
        from uasset_read.parse_uasset import parse_package
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        assert result.summary.package_name is not None
        assert result.summary.package_name != "None"
        assert len(result.summary.package_name) > 0

    def test_package_name_not_none_type(self, sample_root: Path):
        """package_name 不应为 None 类型"""
        from uasset_read.parse_uasset import parse_package
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        assert isinstance(result.summary.package_name, str)

    def test_package_name_derived_from_path_when_none(self, sample_root: Path):
        """当二进制中存储 'None' 时，应从文件路径推导 package_name"""
        from uasset_read.parse_uasset import parse_package
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        # 对于 T_Brick_Clay_New_D.uasset，期望 package_name 包含资产名称
        assert "T_Brick_Clay_New_D" in result.summary.package_name

    def test_package_name_valid_fstring_assets(self, sample_root: Path):
        """正常存储 package_name 的资产应保持不变"""
        from uasset_read.parse_uasset import parse_package
        import glob
        samples = glob.glob(
            str(sample_root / "**/BP_*.uasset"), recursive=True
        )
        if not samples:
            pytest.skip("No BP_ samples found")
        # 只测试前 3 个
        for path in samples[:3]:
            result = parse_package(path)
            assert result.summary is not None
            assert result.summary.package_name != "None"
            assert len(result.summary.package_name) > 0
