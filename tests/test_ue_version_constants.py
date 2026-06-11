"""验证 CustomVersion GUID 与 UE 源码一致。"""
import pytest
from uasset_read.constants import (
    FCORE_OBJECT_VERSION_GUID,
    FEDITOR_OBJECT_VERSION_GUID,
    FANIM_OBJECT_VERSION_GUID,
    FPHYSICS_OBJECT_VERSION_GUID,
    FRENDERING_OBJECT_VERSION_GUID,
    FBLUEPRINTS_OBJECT_VERSION_GUID,
    FFRAMEWORK_OBJECT_VERSION_GUID,
    FRELEASE_OBJECT_VERSION_GUID,
    FUE5_MAINSTREAM_VERSION_GUID,
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
)


def _parse_guid(guid_str: str) -> tuple:
    """解析 GUID 字符串为 (A, B, C, D) 四元组。"""
    parts = guid_str.split("-")
    a = int(parts[0], 16)
    b = int(parts[1], 16)
    c = int(parts[2], 16)
    d = int(parts[3], 16)
    return (a, b, c, d)


class TestCustomVersionGUIDs:
    """验证 CustomVersion GUID 与 UE DevObjectVersion.cpp 一致。"""

    def test_fcore_object_version_guid(self):
        a, b, c, d = _parse_guid(FCORE_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0x375EC13C, 0x06E448FB, 0xB50084F0, 0x262A717E)

    def test_feditor_object_version_guid(self):
        a, b, c, d = _parse_guid(FEDITOR_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xE4B068ED, 0xF49442E9, 0xA231DA0B, 0x2E46BB41)

    def test_fanim_object_version_guid(self):
        a, b, c, d = _parse_guid(FANIM_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xAF43A65D, 0x7FD34947, 0x98733E8E, 0xD9C1BB05)

    def test_fphysics_object_version_guid(self):
        a, b, c, d = _parse_guid(FPHYSICS_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0x78F01B33, 0xEBEA4F98, 0xB9B484EA, 0xCCB95AA2)

    def test_frendering_object_version_guid(self):
        a, b, c, d = _parse_guid(FRENDERING_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0x12F88B9F, 0x88754AFC, 0xA67CD90C, 0x383ABD29)

    def test_fblueprints_object_version_guid(self):
        a, b, c, d = _parse_guid(FBLUEPRINTS_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xB0D832E4, 0x1F894F0D, 0xACCF7EB7, 0x36FD4AA2)

    def test_fframework_object_version_guid(self):
        a, b, c, d = _parse_guid(FFRAMEWORK_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xCFFC743F, 0x43B04480, 0x939114DF, 0x171D2073)

    def test_frelease_object_version_guid(self):
        a, b, c, d = _parse_guid(FRELEASE_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0x9C54D522, 0xA8264FBE, 0x94210746, 0x61B482D0)

    def test_fue5_mainstream_version_guid(self):
        a, b, c, d = _parse_guid(FUE5_MAINSTREAM_VERSION_GUID)
        assert (a, b, c, d) == (0x697DD581, 0xE64F41AB, 0xAA4A51EC, 0xBEB7B628)

    def test_fue5releasestream_object_version_guid(self):
        a, b, c, d = _parse_guid(FUE5RELEASESTREAM_OBJECT_VERSION_GUID)
        assert (a, b, c, d) == (0xD89B5E42, 0x24BD4D46, 0x8412ACA8, 0xDF641779)


class TestUE4VersionConstants:
    """验证 UE4 版本常量与 UE ObjectVersion.h enum 一致。"""

    def test_ver_ue4_struct_guid_in_property_tag(self):
        """VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG = 446"""
        from uasset_read.constants import VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG
        assert VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG == 446

    def test_ver_ue4_property_guid_in_property_tag(self):
        """VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG = 508"""
        from uasset_read.constants import VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG
        assert VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG == 508

    def test_ver_ue4_property_tag_set_map_support(self):
        """VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT = 514"""
        from uasset_read.constants import VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT
        assert VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT == 514

    def test_var_ue4_array_property_inner_tags(self):
        """VAR_UE4_ARRAY_PROPERTY_INNER_TAGS = 253"""
        from uasset_read.constants import VAR_UE4_ARRAY_PROPERTY_INNER_TAGS
        assert VAR_UE4_ARRAY_PROPERTY_INNER_TAGS == 253

    def test_ue4_name_hashes_serialized(self):
        """UE4_NAME_HASHES_SERIALIZED = 509"""
        from uasset_read.constants import UE4_NAME_HASHES_SERIALIZED
        assert UE4_NAME_HASHES_SERIALIZED == 509

    def test_ue4_preload_dependencies_in_cooked_exports(self):
        """UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 512"""
        from uasset_read.constants import UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS
        assert UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS == 512

    def test_ue4_templateindex_in_cooked_exports(self):
        """UE4_TemplateIndex_IN_COOKED_EXPORTS = 513"""
        from uasset_read.constants import UE4_TemplateIndex_IN_COOKED_EXPORTS
        assert UE4_TemplateIndex_IN_COOKED_EXPORTS == 513

    def test_ue4_64bit_exportmap_serialsizes(self):
        """UE4_64BIT_EXPORTMAP_SERIALSIZES = 516"""
        from uasset_read.constants import UE4_64BIT_EXPORTMAP_SERIALSIZES
        assert UE4_64BIT_EXPORTMAP_SERIALSIZES == 516

    def test_ue4_non_outer_package_import(self):
        """UE4_NON_OUTER_PACKAGE_IMPORT = 525"""
        from uasset_read.constants import UE4_NON_OUTER_PACKAGE_IMPORT
        assert UE4_NON_OUTER_PACKAGE_IMPORT == 525

    def test_ue4_serialize_text_in_packages(self):
        """UE4_SERIALIZE_TEXT_IN_PACKAGES = 464"""
        from uasset_read.constants import UE4_SERIALIZE_TEXT_IN_PACKAGES
        assert UE4_SERIALIZE_TEXT_IN_PACKAGES == 464


class TestFEdGraphPinTypeVersionConstants:
    """验证 FEdGraphPinType 序列化版本常量。"""

    def test_ver_ue4_memberreference_in_pintype(self):
        """VER_UE4_MEMBERREFERENCE_IN_PINTYPE = 355

        PinSubCategoryMemberReference 字段加入。
        """
        from uasset_read.constants import VER_UE4_MEMBERREFERENCE_IN_PINTYPE
        assert VER_UE4_MEMBERREFERENCE_IN_PINTYPE == 355

    def test_ver_ue4_serialize_pintype_const(self):
        """VER_UE4_SERIALIZE_PINTYPE_CONST = 456

        bIsConst 字段加入。
        """
        from uasset_read.constants import VER_UE4_SERIALIZE_PINTYPE_CONST
        assert VER_UE4_SERIALIZE_PINTYPE_CONST == 456


class TestFTextVersionConstants:
    """验证 FText 序列化版本常量。"""

    def test_ver_ue4_ftext_history(self):
        """VER_UE4_FTEXT_HISTORY = 428"""
        from uasset_read.constants import VER_UE4_FTEXT_HISTORY
        assert VER_UE4_FTEXT_HISTORY == 428

    def test_ver_ue4_added_currency_code_to_ftext(self):
        """VER_UE4_ADDED_CURRENCY_CODE_TO_FTEXT = 470"""
        from uasset_read.constants import VER_UE4_ADDED_CURRENCY_CODE_TO_FTEXT
        assert VER_UE4_ADDED_CURRENCY_CODE_TO_FTEXT == 470

    def test_ver_ue4_added_namespace_and_key_data_to_ftext(self):
        """VER_UE4_ADDED_NAMESPACE_AND_KEY_DATA_TO_FTEXT = 139"""
        from uasset_read.constants import VER_UE4_ADDED_NAMESPACE_AND_KEY_DATA_TO_FTEXT
        assert VER_UE4_ADDED_NAMESPACE_AND_KEY_DATA_TO_FTEXT == 139

    def test_ver_ue4_ftext_history_date_timezone(self):
        """VER_UE4_FTEXT_HISTORY_DATE_TIMEZONE = 539"""
        from uasset_read.constants import VER_UE4_FTEXT_HISTORY_DATE_TIMEZONE
        assert VER_UE4_FTEXT_HISTORY_DATE_TIMEZONE == 539
