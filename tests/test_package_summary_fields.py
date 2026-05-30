"""PackageFileSummary 字段解析和常量验证测试。"""
from __future__ import annotations

import pytest

from uasset_read.constants import (
    PKG_FilterEditorOnly,
    UE5_IMPORT_TYPE_HIERARCHIES,
    UE5_PACKAGE_SAVED_HASH,
)


class TestConstants:
    """验证常量与 CUE4Parse ObjectVersion.cs 一致。"""

    def test_pkg_filter_editor_only_value(self):
        """PKG_FilterEditorOnly 必须为 0x80000000（CUE4Parse EPackageFlags）。"""
        assert PKG_FilterEditorOnly == 0x80000000

    def test_import_type_hierarchies_version(self):
        """UE5_IMPORT_TYPE_HIERARCHIES 必须为 1018（CUE4Parse IMPORT_TYPE_HIERARCHIES）。"""
        assert UE5_IMPORT_TYPE_HIERARCHIES == 1018

    def test_package_saved_hash_version(self):
        """UE5_PACKAGE_SAVED_HASH 必须为 1016（CUE4Parse PACKAGE_SAVED_HASH）。"""
        assert UE5_PACKAGE_SAVED_HASH == 1016
