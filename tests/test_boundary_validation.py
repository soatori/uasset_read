"""
test_boundary_validation.py - SAFE-01/SAFE-02 边界验证测试

Phase 5 Wave 2: 测试脚手架
"""

import pytest
import tempfile
import os
from uasset_read import FArchive, ParseError, PackageIndex

class TestOffsetValidation:
    """D-10: 全偏移验证测试"""

    def test_negative_offset_rejected(self):
        """负数偏移被拒绝"""
        pytest.skip("Wave 2 stub - implement after FArchive.validate_offset()")

    def test_offset_exceeds_file_size_rejected(self):
        """超出文件大小的偏移被拒绝"""
        pytest.skip("Wave 2 stub")


class TestSizeValidation:
    """D-11/D-16: PropertyTag.Size 完整验证测试"""

    def test_negative_size_rejected(self):
        """负数 Size 被拒绝"""
        pytest.skip("Wave 2 stub")

    def test_size_exceeds_max_reasonable_rejected(self):
        """Size 超过 max_reasonable 被拒绝（D-16）"""
        pytest.skip("Wave 2 stub")


class TestPackageIndexValidation:
    """D-12/D-17: PackageIndex 完整验证测试"""

    def test_package_index_import_out_of_range(self):
        """导入索引超出范围"""
        pytest.skip("Wave 2 stub")

    def test_package_index_export_out_of_range(self):
        """导出索引超出范围"""
        pytest.skip("Wave 2 stub")