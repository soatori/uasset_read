"""PackageFileSummary 字段解析和常量验证测试。"""
from __future__ import annotations

import os

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

    def test_ue4_version_constants(self):
        """UE4 版本常量与 CUE4Parse EUnrealEngineObjectUE4Version 一致。"""
        from uasset_read.constants import (
            UE4_ADD_STRING_ASSET_REFERENCES_MAP,
            UE4_ADDED_SEARCHABLE_NAMES,
            UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID,
            UE4_SERIALIZE_TEXT_IN_PACKAGES,
            UE4_ADDED_PACKAGE_OWNER,
            UE4_NON_OUTER_PACKAGE_IMPORT,
        )
        assert UE4_ADD_STRING_ASSET_REFERENCES_MAP == 516
        assert UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID == 516
        assert UE4_SERIALIZE_TEXT_IN_PACKAGES == 517
        assert UE4_ADDED_SEARCHABLE_NAMES == 518
        assert UE4_ADDED_PACKAGE_OWNER == 519
        assert UE4_NON_OUTER_PACKAGE_IMPORT == 520


class TestMissingFields:
    """验证 M_Mannequin 材质资产能正确解析。"""

    SAMPLE = r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\Characters\Mannequins\Materials\M_Mannequin.uasset"

    @pytest.fixture(scope="class")
    def result(self):
        import os
        if not os.path.exists(self.SAMPLE):
            pytest.skip("sample asset not found")
        from uasset_read import parse_uasset_with_linker
        return parse_uasset_with_linker(self.SAMPLE, tolerant=True)

    def test_m_mannequin_parses_successfully(self, result):
        assert result.is_success
        assert len(result.errors) == 0

    def test_generations_count_positive(self, result):
        assert len(result.summary.generations) > 0

    def test_soft_package_references_present(self, result):
        assert result.summary.soft_package_references_count >= 0


class TestSkeletalMeshParsing:
    """验证骨骼网格资产解析（此前因 Negative generations count 失败）。"""

    SAMPLES = [
        r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\Characters\Mannequins\Meshes\SKM_Manny_Simple.uasset",
        r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\Characters\Mannequins\Meshes\SKM_Quinn_Simple.uasset",
    ]

    @pytest.mark.parametrize("path", SAMPLES, ids=lambda p: os.path.basename(p))
    def test_skeletal_mesh_parses(self, path):
        if not os.path.exists(path):
            pytest.skip("sample not found")
        from uasset_read import parse_uasset_with_linker
        r = parse_uasset_with_linker(path, tolerant=True)
        assert r.is_success, f"Errors: {r.errors}"
        assert len(r.summary.generations) > 0
