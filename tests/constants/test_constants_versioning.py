"""constants 和 versioning 模块单元测试。

覆盖范围：
- constants: 版本常量存在性、值正确性、边界常量、decode_package_flags、
  公式组合标志、节点集合、图类型映射、Framework 版本阈值
- versioning: EUEVersion 枚举、VersionStream、VersionContainer、
  FPackageFileVersion 比较运算、build_version_container
"""
from __future__ import annotations

import pytest

from uasset_read import constants
from uasset_read.versioning import (
    EUEVersion,
    FPackageFileVersion,
    STREAM_MAP,
    STREAM_FRAMEWORK,
    VersionContainer,
    VersionStream,
    build_version_container,
)


# ============================================================================
# Constants — 版本常量
# ============================================================================


class TestVersionConstantsExist:
    """关键版本常量应存在。"""

    def test_ue4_added_package_owner(self):
        assert hasattr(constants, "UE4_ADDED_PACKAGE_OWNER")
        assert constants.UE4_ADDED_PACKAGE_OWNER == 518

    def test_ue4_added_package_summary_localization_id(self):
        assert constants.UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID == 516

    def test_ue4_non_outer_package_import(self):
        assert constants.UE4_NON_OUTER_PACKAGE_IMPORT == 520

    def test_ue4_name_hashes_serialized(self):
        assert constants.UE4_NAME_HASHES_SERIALIZED == 504

    def test_ue5_script_serialization_offset(self):
        assert constants.UE5_SCRIPT_SERIALIZATION_OFFSET == 1010

    def test_ue5_property_tag_extension(self):
        assert constants.UE5_PROPERTY_TAG_EXTENSION == 1011

    def test_ue5_import_type_hierarchies(self):
        assert constants.UE5_IMPORT_TYPE_HIERARCHIES == 1018

    def test_ue5_legacy_versions_is_frozenset(self):
        assert isinstance(constants.UE5_LEGACY_VERSIONS, frozenset)
        assert -9 in constants.UE5_LEGACY_VERSIONS
        assert -8 in constants.UE5_LEGACY_VERSIONS


class TestPackageFileTags:
    """Package 文件标签值应正确。"""

    def test_file_tag(self):
        assert constants.PACKAGE_FILE_TAG == 0x9E2A83C1

    def test_swapped_file_tag(self):
        assert constants.PACKAGE_FILE_TAG_SWAPPED == 0xC1832A9E

    def test_tags_are_distinct(self):
        assert constants.PACKAGE_FILE_TAG != constants.PACKAGE_FILE_TAG_SWAPPED


# ============================================================================
# Constants — 边界验证常量
# ============================================================================


class TestBoundaryConstants:
    """边界验证常量值应合理。"""

    def test_max_name_count(self):
        assert constants.MAX_NAME_COUNT == 10_000_000

    def test_max_import_count(self):
        assert constants.MAX_IMPORT_COUNT == 1_000_000

    def test_max_export_count(self):
        assert constants.MAX_EXPORT_COUNT == 1_000_000

    def test_max_custom_versions(self):
        assert constants.MAX_CUSTOM_VERSIONS == 10_000

    def test_min_uasset_size(self):
        assert constants.MIN_UASSET_SIZE == 64

    def test_max_array_count(self):
        assert constants.MAX_ARRAY_COUNT == 1_000_000

    def test_max_fstring_length(self):
        assert constants.MAX_FSTRING_LENGTH == 10_000_000

    def test_max_recursion_depth(self):
        assert constants.MAX_RECURSION_DEPTH == 50

    def test_max_property_count(self):
        assert constants.MAX_PROPERTY_COUNT == 10_000


# ============================================================================
# Constants — Package Flags
# ============================================================================


class TestPackageFlags:
    """PKG_* 标志位值应与 UE 源码对齐。"""

    def test_pkg_none(self):
        assert constants.PKG_None == 0x00000000

    def test_pkg_cooked(self):
        assert constants.PKG_Cooked == 0x00000200

    def test_pkg_editor_only(self):
        assert constants.PKG_EditorOnly == 0x00000040

    def test_pkg_filter_editor_only(self):
        assert constants.PKG_FilterEditorOnly == 0x80000000

    def test_pkg_transient_flags_compound(self):
        assert (
            constants.PKG_TransientFlags
            == constants.PKG_NewlyCreated | constants.PKG_IsSaving | constants.PKG_ReloadingForCooker
        )

    def test_pkg_in_memory_only_compound(self):
        assert (
            constants.PKG_InMemoryOnly
            == constants.PKG_CompiledIn | constants.PKG_NewlyCreated
        )


# ============================================================================
# Constants — decode_package_flags
# ============================================================================


class TestDecodePackageFlags:
    """decode_package_flags 应正确解码标志位。"""

    def test_zero_returns_pkg_none(self):
        result = constants.decode_package_flags(0)
        assert result == ["PKG_None"]

    def test_single_flag(self):
        result = constants.decode_package_flags(constants.PKG_Cooked)
        assert "PKG_Cooked" in result

    def test_multiple_flags(self):
        flags = constants.PKG_Cooked | constants.PKG_EditorOnly
        result = constants.decode_package_flags(flags)
        assert "PKG_Cooked" in result
        assert "PKG_EditorOnly" in result

    def test_unknown_bits(self):
        flags = 0x04000000  # 未定义的位
        result = constants.decode_package_flags(flags)
        assert any("Unknown_" in name for name in result)


# ============================================================================
# Constants — PropertyTag 标志
# ============================================================================


class TestPropertyTagFlags:
    """PropertyTag 标志位值应正确。"""

    def test_prop_tag_none(self):
        assert constants.PROP_TAG_NONE == 0x00

    def test_prop_tag_has_array_index(self):
        assert constants.PROP_TAG_HAS_ARRAY_INDEX == 0x01

    def test_prop_tag_has_property_guid(self):
        assert constants.PROP_TAG_HAS_PROPERTY_GUID == 0x02

    def test_prop_tag_has_extensions(self):
        assert constants.PROP_TAG_HAS_EXTENSIONS == 0x04

    def test_prop_tag_has_binary_or_native(self):
        assert constants.PROP_TAG_HAS_BINARY_OR_NATIVE == 0x08

    def test_prop_tag_bool_true(self):
        assert constants.PROP_TAG_BOOL_TRUE == 0x10


# ============================================================================
# Constants — Framework 版本阈值
# ============================================================================


class TestFrameworkVersionThresholds:
    """Framework 版本阈值应正确。"""

    def test_ed_graph_pin_container_type(self):
        assert constants.FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE == 15

    def test_pins_store_fname(self):
        assert constants.FFRAMEWORK_VERSION_PINS_STORE_FNAME == 19

    def test_ue5_pin_source_index(self):
        assert constants.FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX == 50

    def test_release_pin_type_uobject_wrapper(self):
        assert constants.FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER == 10

    def test_float_pin_defaults_single_precision(self):
        """FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION 已移除，验证不存在。"""
        assert not hasattr(constants, "FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION")


# ============================================================================
# Constants — 节点集合 & 图常量
# ============================================================================


class TestNodeCollections:
    """蓝图图解析相关集合常量应正确。"""

    def test_control_flow_nodes_is_frozenset(self):
        assert isinstance(constants.CONTROL_FLOW_NODES, frozenset)

    def test_start_event_types_is_frozenset(self):
        assert isinstance(constants.START_EVENT_TYPES, frozenset)

    def test_data_boundary_nodes_is_frozenset(self):
        assert isinstance(constants.DATA_BOUNDARY_NODES, frozenset)

    def test_blueprint_metadata_keys_is_frozenset(self):
        assert isinstance(constants.BLUEPRINT_METADATA_KEYS, frozenset)

    def test_control_flow_nodes_contains_if_then_else(self):
        assert "K2Node_IfThenElse" in constants.CONTROL_FLOW_NODES

    def test_start_event_types_contains_event(self):
        assert "K2Node_Event" in constants.START_EVENT_TYPES

    def test_branch_type_map_values_are_strings(self):
        for val in constants.BRANCH_TYPE_MAP.values():
            assert isinstance(val, str)

    def test_graph_type_map(self):
        assert constants.GRAPH_TYPE_MAP["EdGraph"] == "event"
        assert constants.GRAPH_TYPE_MAP["UberEdGraph"] == "uber"

    def test_etrigger_event_pin_map(self):
        assert constants.ETRIGGER_EVENT_PIN_MAP["Started"] == "Started"
        assert constants.ETRIGGER_EVENT_PIN_MAP["Triggered"] == "Triggered"


# ============================================================================
# Constants — CustomVersion GUID 格式
# ============================================================================


class TestCustomVersionGUIDs:
    """CustomVersion GUID 应为合法格式。"""

    @pytest.mark.parametrize(
        "guid_name",
        [
            "FFRAMEWORK_OBJECT_VERSION_GUID",
            "FUE5_MAINSTREAM_VERSION_GUID",
            "FRELEASE_OBJECT_VERSION_GUID",
            "FUE5RELEASESTREAM_OBJECT_VERSION_GUID",
            "FBLUEPRINTS_OBJECT_VERSION_GUID",
            "FCORE_OBJECT_VERSION_GUID",
            "FEDITOR_OBJECT_VERSION_GUID",
            "FANIM_OBJECT_VERSION_GUID",
            "FPHYSICS_OBJECT_VERSION_GUID",
            "FRENDERING_OBJECT_VERSION_GUID",
            "FSEQUENCER_OBJECT_VERSION_GUID",
        ],
    )
    def test_guid_format(self, guid_name):
        guid = getattr(constants, guid_name)
        assert isinstance(guid, str)
        # UE GUID 格式: XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX (35 chars, 3 dashes)
        assert len(guid) == 35
        assert guid.count("-") == 3


# ============================================================================
# Versioning — EUEVersion 枚举
# ============================================================================


class TestEUEVersion:
    """EUEVersion 枚举值应正确。"""

    def test_ue4_23(self):
        assert EUEVersion.UE4_23 == 516

    def test_ue5_0(self):
        assert EUEVersion.UE5_0 == 1000

    def test_ue5_2(self):
        assert EUEVersion.UE5_2 == 1005

    def test_ue5_5(self):
        assert EUEVersion.UE5_5 == 1012

    def test_ue5_8(self):
        assert EUEVersion.UE5_8 == 1018

    def test_is_int_enum(self):
        assert isinstance(EUEVersion.UE5_0, int)

    def test_ordering(self):
        assert EUEVersion.UE4_23 < EUEVersion.UE5_0
        assert EUEVersion.UE5_0 < EUEVersion.UE5_8


# ============================================================================
# Versioning — VersionStream
# ============================================================================


class TestVersionStream:
    """VersionStream 应正确创建和比较。"""

    def test_stream_framework(self):
        assert STREAM_FRAMEWORK.guid == constants.FFRAMEWORK_OBJECT_VERSION_GUID
        assert STREAM_FRAMEWORK.name == "framework"

    def test_stream_map_count(self):
        assert len(STREAM_MAP) >= 27

    def test_stream_frozen(self):
        with pytest.raises(AttributeError):
            STREAM_FRAMEWORK.name = "changed"

    def test_all_streams_have_guid_and_name(self):
        for key, stream in STREAM_MAP.items():
            assert isinstance(stream.guid, str)
            assert isinstance(stream.name, str)
            assert len(stream.guid) > 0


# ============================================================================
# Versioning — VersionContainer
# ============================================================================


class TestVersionContainer:
    """VersionContainer 版本查询应正确工作。"""

    def test_empty_container_get_version_returns_default(self):
        vc = VersionContainer()
        assert vc.get_version("any-guid") == 0

    def test_empty_container_get_version_custom_default(self):
        vc = VersionContainer()
        assert vc.get_version("any-guid", default=42) == 42

    def test_container_with_custom_versions(self):
        class FakeVersion:
            def __init__(self, guid, version):
                self.guid = guid
                self.version = version

        vc = VersionContainer(
            custom_versions=[
                FakeVersion("FFC743F-43B04480-939114DF-171D2073", 7),
            ],
        )
        # 有横杠
        assert vc.get_version("FFC743F-43B04480-939114DF-171D2073") == 7
        # 无横杠
        assert vc.get_version("FFC743F43B04480939114DF171D2073") == 7
        # 大小写不敏感
        assert vc.get_version("ffc743f43b04480939114df171d2073") == 7

    def test_container_is_ue5(self):
        vc = VersionContainer(file_version_ue5=1012)
        assert vc.is_ue5 is True

    def test_container_ue4_only(self):
        """file_version_ue5=0 时 is_ue5 仍为 True（UE5_VERSION_MIN=0），
        这是 UE 设计行为：is_ue5 仅判断 file_version_ue5 >= 0。"""
        vc = VersionContainer(file_version_ue5=0, file_version_ue4=520)
        # UE5_VERSION_MIN=0，所以 0 >= 0 → True
        assert vc.is_ue5 is True

    def test_file_version_property(self):
        vc = VersionContainer(file_version_ue4=520, file_version_ue5=1012)
        fv = vc.file_version
        assert isinstance(fv, FPackageFileVersion)
        assert fv.file_version_ue4 == 520
        assert fv.file_version_ue5 == 1012


# ============================================================================
# Versioning — FPackageFileVersion
# ============================================================================


class TestFPackageFileVersion:
    """FPackageFileVersion 应正确比较。"""

    def test_to_value_ue5_priority(self):
        fv = FPackageFileVersion(file_version_ue4=520, file_version_ue5=1012)
        assert fv.to_value() == 1012

    def test_to_value_ue4_fallback(self):
        fv = FPackageFileVersion(file_version_ue4=520, file_version_ue5=0)
        assert fv.to_value() == 520

    def test_ge(self):
        fv = FPackageFileVersion(file_version_ue5=1012)
        assert fv >= 1012
        assert fv >= 1000
        assert not fv >= 1013

    def test_gt(self):
        fv = FPackageFileVersion(file_version_ue5=1012)
        assert fv > 1011
        assert not fv > 1012

    def test_le(self):
        fv = FPackageFileVersion(file_version_ue5=1012)
        assert fv <= 1012
        assert fv <= 1013
        assert not fv <= 1011

    def test_lt(self):
        fv = FPackageFileVersion(file_version_ue5=1012)
        assert fv < 1013
        assert not fv < 1012


# ============================================================================
# Versioning — build_version_container
# ============================================================================


class TestBuildVersionContainer:
    """build_version_container 应从 summary 构建 VersionContainer。"""

    def test_build_from_summary(self):
        class FakeCustomVersion:
            def __init__(self, guid, version):
                self.guid = guid
                self.version = version

        class FakeSummary:
            custom_versions = [
                FakeCustomVersion("FFC743F-43B04480-939114DF-171D2073", 7),
            ]
            file_version_ue5 = 1012
            file_version_ue4 = 520

        vc = build_version_container(FakeSummary())
        assert vc.file_version_ue5 == 1012
        assert vc.file_version_ue4 == 520
        assert vc.get_version("FFC743F-43B04480-939114DF-171D2073") == 7

    def test_build_from_summary_no_ue4(self):
        class FakeSummary:
            custom_versions = []
            file_version_ue5 = 0

        vc = build_version_container(FakeSummary())
        assert vc.file_version_ue4 == 0
        # is_ue5 始终为 True（UE5_VERSION_MIN=0）
        assert vc.is_ue5 is True
