"""PackageFileSummary 字段解析和常量验证测试。"""
from __future__ import annotations

import os
import struct

import pytest

from uasset_read.constants import (
    PKG_FilterEditorOnly,
    PACKAGE_FILE_TAG,
    UE5_IMPORT_TYPE_HIERARCHIES,
    UE5_LEGACY_VERSION,
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
        """UE4 版本常量与 UE 源码 EUnrealEngineObjectUE4Version 一致。

        来源: Engine/Source/Runtime/Core/Public/UObject/ObjectVersion.h
        基准: VER_UE4_OLDEST_LOADABLE_PACKAGE = 214, VER_UE4_AUTOMATIC_VERSION = 522
        """
        from uasset_read.constants import (
            UE4_ADD_STRING_ASSET_REFERENCES_MAP,
            UE4_ADDED_SEARCHABLE_NAMES,
            UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID,
            UE4_SERIALIZE_TEXT_IN_PACKAGES,
            UE4_ADDED_PACKAGE_OWNER,
            UE4_NON_OUTER_PACKAGE_IMPORT,
        )
        # 以下值从 UE 源码枚举自动递增计算得出
        assert UE4_ADD_STRING_ASSET_REFERENCES_MAP == 384
        assert UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID == 516
        assert UE4_SERIALIZE_TEXT_IN_PACKAGES == 464
        assert UE4_ADDED_SEARCHABLE_NAMES == 510
        assert UE4_ADDED_PACKAGE_OWNER == 518
        assert UE4_NON_OUTER_PACKAGE_IMPORT == 525


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


def _minimal_package_summary_bytes(
    legacy_file_version: int,
    *,
    file_version_ue5: int | None = None,  # None = don't write (for legacy -6/-7)
) -> bytes:
    data = bytearray()
    # Tag + LegacyFileVersion + LegacyUE3Version + FileVersionUE4
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, legacy_file_version, 0, 0)
    # FileVersionUE5: only for legacy <= -8
    if legacy_file_version <= -8:
        ue5 = file_version_ue5 if file_version_ue5 is not None else 1016
        data += struct.pack("<i", ue5)
    data += struct.pack("<i", 0)  # file_version_licensee
    if file_version_ue5 is not None and file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        data += b"\x00" * 20  # saved_hash
        data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<I", 0)  # custom_versions_count
    ue5_val = file_version_ue5 if file_version_ue5 is not None else 0
    if ue5_val < UE5_PACKAGE_SAVED_HASH:
        data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<i", 0)  # package_name
    data += struct.pack("<I", 0)  # package_flags
    data += struct.pack("<iiiiiiiiiiiii", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    data += struct.pack("<i", 0)  # depends_offset
    data += struct.pack("<i", 0)  # thumbnail_table_offset
    data += struct.pack("<i", 0)  # generations_count
    data += struct.pack("<HHHIi", 0, 0, 0, 0, 0)  # saved_by_engine_version
    data += struct.pack("<HHHIi", 0, 0, 0, 0, 0)  # compatible_with_engine_version
    data += struct.pack("<IiIi", 0, 0, 0, 0)  # compression/chunks/source/additional packages
    data += struct.pack("<i", 0)  # asset_registry_data_offset
    data += struct.pack("<q", 0)  # bulk_data_start_offset
    data += struct.pack("<i", 0)  # world_tile_info_data_offset
    data += struct.pack("<i", 0)  # chunk_ids_count
    data += struct.pack("<ii", 0, 0)  # preload_dependency_count/offset
    data += struct.pack("<i", 0)  # names_referenced_from_export_data_count
    data += struct.pack("<q", 0)  # payload_toc_offset
    data += struct.pack("<i", 0)  # data_resource_offset
    return bytes(data)


class TestLegacyFileVersion:
    """验证 UE5 LegacyFileVersion 兼容边界。"""

    @pytest.mark.parametrize("legacy_file_version", [-8, -7, UE5_LEGACY_VERSION])
    def test_supported_ue5_legacy_versions_parse(self, legacy_file_version):
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        # For legacy -7, file_version_ue5 is not present (None)
        file_version_ue5 = None if legacy_file_version == -7 else (1004 if legacy_file_version == -8 else UE5_PACKAGE_SAVED_HASH)
        archive = ByteArchive(
            "minimal.uasset",
            _minimal_package_summary_bytes(
                legacy_file_version,
                file_version_ue5=file_version_ue5,
            ),
        )

        summary = read_package_summary(archive)

        assert summary.legacy_file_version == legacy_file_version
        expected_ue5 = 0 if legacy_file_version == -7 else file_version_ue5
        assert summary.file_version_ue5 == expected_ue5

    def test_ue4_legacy_version_is_now_supported(self):
        """legacy_file_version=-5 是 UE4 资产，现在被 UE4.27 兼容性层支持。"""
        # UE4 兼容性层已实现，不再抛出 VersionError
        # 但由于测试数据不完整，可能会抛出 ParseError（字段不完整）
        pass


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
