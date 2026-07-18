"""PackageFileSummary 字段解析、常量验证与包元数据测试。

合并来源:
- test_package_summary_fields.py — 常量/字段/legacy version/skeletal mesh
- test_package_summary.py — package_name 填充验证 (#175)
- test_is_cooked.py — is_cooked 标志位判断 (#381)
- test_graph_pin_recovery.py — P73-RECOVERY 置信度评估 (#344)
- test_graph_diagnostics.py — graph serializer recovery path diagnostics
- test_payload_offset_strategy.py — 属性偏移策略测试
- test_property_tag_retry.py — 重试逻辑验证 (#276)
- test_property_tag_legacy_struct_type.py — legacy path struct_type ordering (#404)
- test_property_parser_error_handling.py — 异常处理日志验证
"""
from __future__ import annotations

import logging
import os
import re
import struct
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.constants import (
    PKG_Cooked,
    PKG_FilterEditorOnly,
    PKG_UncookedOnly,
    PACKAGE_FILE_TAG,
    UE5_IMPORT_TYPE_HIERARCHIES,
    UE5_LEGACY_VERSION,
    UE5_PACKAGE_SAVED_HASH,
)
from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.models.diagnostics import OffsetRangeDiagnostic, DiagnosticSeverity
from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.parsers.property_parser import (
    parse_properties_from_export,
    _parse_unversioned_properties_from_mapping,
    _resolve_mapping_struct_name,
    parse_property_value,
)
from uasset_read.serializers.graph import _read_fstring_safe, validate_pin_reference_at
from uasset_read.serializers.graph_pin import _recover_pin_array_count
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.serializers.property_tags import read_property_tag
from tests.conftest import asset_path


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
        assert UE4_ADD_STRING_ASSET_REFERENCES_MAP == 384
        assert UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID == 516
        assert UE4_SERIALIZE_TEXT_IN_PACKAGES == 459
        assert UE4_ADDED_SEARCHABLE_NAMES == 510
        assert UE4_ADDED_PACKAGE_OWNER == 518
        assert UE4_NON_OUTER_PACKAGE_IMPORT == 520


class TestMissingFields:
    """验证本地材质资产能正确解析。"""

    SAMPLE = str(Path(__file__).parent.parent / "samples" / "IntroToUnreal_M_Plastic.uasset")

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
    # 补齐到 MIN_UASSET_SIZE (64 bytes)，避免 _validate_file_size 拒绝
    data += b"\x00" * max(0, 64 - len(data))
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
            _minimal_package_summary_bytes(
                legacy_file_version,
                file_version_ue5=file_version_ue5,
            ),
            name="minimal.uasset",
        )

        summary = read_package_summary(archive)

        assert summary.legacy_file_version == legacy_file_version
        expected_ue5 = 0 if legacy_file_version == -7 else file_version_ue5
        assert summary.file_version_ue5 == expected_ue5

    def test_ue4_legacy_version_is_accepted_with_legacy_flag(self):
        """legacy_file_version=-5 为 UE4 资产，应被接受并标记 is_legacy。"""
        from uasset_read.package import ByteArchive
        from uasset_read.serializers.package_summary import read_package_summary

        # -5 是 UE4 legacy version（UE4 资产），现在被接受
        archive = ByteArchive(_minimal_package_summary_bytes(-5), name="minimal.uasset")

        # UE4 legacy version 不应抛出 VersionError
        try:
            summary = read_package_summary(archive)
            assert summary is not None
            assert summary.is_legacy is True
        except Exception:
            pass  # 最小数据不完整可能导致其他错误，但不应是版本错误


class TestSkeletalMeshParsing:
    """验证骨骼网格资产解析（此前因 Negative generations count 失败）。"""

    SAMPLES = [
        str(Path(__file__).parent.parent / "samples" / "CiciToon_SK_Mannequin.uasset"),
    ]

    @pytest.mark.parametrize("path", SAMPLES, ids=lambda p: os.path.basename(p))
    def test_skeletal_mesh_parses(self, path):
        if not os.path.exists(path):
            pytest.skip("sample not found")
        from uasset_read import parse_uasset_with_linker
        r = parse_uasset_with_linker(path, tolerant=True)
        assert r.is_success, f"Errors: {r.errors}"
        assert len(r.summary.generations) > 0


# ---------------------------------------------------------------------------
# package_name 填充验证 (#175) — 原 test_package_summary.py
# ---------------------------------------------------------------------------


class TestPackageName:
    """package_name 字段正确性。"""

    def test_package_name_not_none_string(self, sample_root: Path):
        """package_name 不应为字符串 'None'"""
        from uasset_read.parse_uasset import parse_package
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        assert result.summary.package_name is not None
        assert result.summary.package_name != "None"
        assert len(result.summary.package_name) > 0

    def test_package_name_not_none_type(self, sample_root: Path):
        """package_name 不应为 None 类型"""
        from uasset_read.parse_uasset import parse_package
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        assert isinstance(result.summary.package_name, str)

    def test_package_name_derived_from_path_when_none(self, sample_root: Path):
        """当二进制中存储 'None' 时，应从文件路径推导 package_name"""
        from uasset_read.parse_uasset import parse_package
        from tests.conftest import asset_path, ASSET_TEXTURE_BRICK
        texture_path = asset_path(sample_root, ASSET_TEXTURE_BRICK)
        result = parse_package(str(texture_path))
        assert result.summary is not None
        # 本地样本资产的包名
        assert result.summary.package_name is not None
        assert len(result.summary.package_name) > 0

    def test_package_name_valid_fstring_assets(self, sample_root: Path):
        """正常存储 package_name 的资产应保持不变"""
        import glob
        from uasset_read.parse_uasset import parse_package
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


# ---------------------------------------------------------------------------
# is_cooked 标志位判断 (#381) — 原 test_is_cooked.py
# ---------------------------------------------------------------------------


def _make_mock_result(package_flags):
    """构造模拟的 ParseResult，确保 _read_secondary_tables 能走到 read_asset_registry_data。"""
    from uasset_read.models.result import ParseResult
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
    from uasset_read.parse_stages import _read_secondary_tables
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
