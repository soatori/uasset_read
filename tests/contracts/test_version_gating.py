"""验证序列化器的版本门控行为。

测试 FEdGraphPinType 序列化器根据不同 CustomVersion 和 UE4 版本
进行字段读取门控的正确性。
"""
import pytest
from unittest.mock import MagicMock
from io import BytesIO


def _make_archive(data: bytes):
    """创建 mock FArchive。

    模拟 FArchive 的读取方法，用于测试序列化器。
    """
    buf = BytesIO(data)
    archive = MagicMock()

    # 基础读取方法
    archive.read = lambda n: buf.read(n)
    archive.read_bytes = lambda n: buf.read(n)
    archive.tell = lambda: buf.tell()
    archive.seek = lambda pos: buf.seek(pos)

    # 整数读取（小端序）
    archive.read_u8 = lambda: int.from_bytes(buf.read(1), 'little')
    archive.read_i8 = lambda: int.from_bytes(buf.read(1), 'little', signed=True)
    archive.read_i32 = lambda: int.from_bytes(buf.read(4), 'little', signed=True)
    archive.read_u32 = lambda: int.from_bytes(buf.read(4), 'little')

    # Bool 读取（UE 标准 4 字节）
    archive.read_bool = lambda: int.from_bytes(buf.read(4), 'little') != 0

    # Bool 读取（UE5 紧凑 1 字节）
    archive.read_bool_1byte = lambda: int.from_bytes(buf.read(1), 'little') != 0

    # FName 读取（索引 + 实例号，共 8 字节）
    def read_name(name_map=None):
        index = int.from_bytes(buf.read(4), 'little')
        number = int.from_bytes(buf.read(4), 'little')  # noqa: F841
        if name_map and 0 <= index < len(name_map):
            return name_map[index]
        return "None"
    archive.read_name = read_name

    # FString 读取
    def read_fstring():
        length = int.from_bytes(buf.read(4), 'little', signed=True)
        if length <= 0:
            return ""
        data = buf.read(length)
        return data.decode('utf-8', errors='replace').rstrip('\x00')
    archive.read_fstring = read_fstring

    # 文件大小（用于边界检查）
    archive._file_size = len(data)

    # validate_size（property_tags 使用）
    archive.validate_size = lambda size, name, tolerant=False: None

    return archive


def _make_summary(**custom_versions):
    """创建 mock PackageFileSummary。

    Args:
        **custom_versions: CustomVersion GUID -> 版本号映射
        ue4_version: 特殊参数，设置 file_version_ue4
    """
    summary = MagicMock()
    summary.file_version_ue4 = custom_versions.pop('ue4_version', 500)

    def get_custom_version(guid, default=0):
        return custom_versions.get(guid, default)

    summary.get_custom_version = get_custom_version
    return summary


class TestFEdGraphPinTypeVersionGating:
    """验证 FEdGraphPinType 版本门控。

    测试覆盖 6 个版本门控点：
    1. FFrameworkObjectVersion::PinsStoreFName (19)
    2. FFrameworkObjectVersion::EdGraphPinContainerType (15)
    3. VER_UE4_MEMBERREFERENCE_IN_PINTYPE (355)
    4. VER_UE4_SERIALIZE_PINTYPE_CONST (456)
    5. FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag (10)
    6. FUE5ReleaseStreamObjectVersion::SerializeFloatPinDefaultsAsSinglePrecision (36)
    """

    def test_pins_store_fname_modern_format(self):
        """>= FFrameworkObjectVersion::PinsStoreFName (19): 使用 FName 格式"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # framework_version = 20 >= 19，使用 FName
        name_map = ["object", "int"]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName: index=0, number=0)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName: index=1, number=0)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject (FPackageIndex)
            b'\x00'                               # ContainerType (None)
            b'\x00\x00\x00\x00'                   # bIsReference (4 bytes)
            b'\x00\x00\x00\x00'                   # bIsWeakPointer (4 bytes)
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 0,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        assert pin_type.pin_category == "object"
        assert pin_type.pin_subcategory == "int"
        assert pin_type.container_type == 0

    def test_pins_store_fstring_legacy_format(self):
        """< FFrameworkObjectVersion::PinsStoreFName (19): 使用 FString 格式"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # framework_version = 10 < 19，使用 FString
        # FString 格式: length (i32) + data (含 null terminator)
        # "object\0" = 7 bytes, "int\0" = 4 bytes
        data = (
            b'\x07\x00\x00\x00object\x00'      # PinCategory (FString, len=7)
            b'\x04\x00\x00\x00int\x00'          # PinSubCategory (FString, len=4)
            b'\x00\x00\x00\x00'                 # PinSubCategoryObject
            b'\x00\x00\x00\x00'                 # bIsMap (4 bytes bool)
            b'\x00\x00\x00\x00'                 # bIsSet (4 bytes bool)
            b'\x00\x00\x00\x00'                 # bIsArray (4 bytes bool)
            b'\x00\x00\x00\x00'                 # bIsReference (4 bytes)
            b'\x00\x00\x00\x00'                 # bIsWeakPointer (4 bytes)
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 10,
                FRELEASE_OBJECT_VERSION_GUID: 0,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, [], summary)

        assert pin_type.pin_category == "object"
        assert pin_type.pin_subcategory == "int"

    def test_container_type_modern_format(self):
        """>= FFrameworkObjectVersion::EdGraphPinContainerType (15): uint8 enum"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # framework_version = 20 >= 15，使用 uint8 ContainerType
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x01'                               # ContainerType = 1 (Array)
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 0,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        assert pin_type.container_type == 1  # Array

    def test_container_type_legacy_3bools(self):
        """< FFrameworkObjectVersion::EdGraphPinContainerType (15): 3 个 bool"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # framework_version = 10 < 15 且 < 19，使用 3 个 bool + FString 格式
        data = (
            b'\x07\x00\x00\x00object\x00'      # PinCategory (FString, len=7)
            b'\x04\x00\x00\x00int\x00'          # PinSubCategory (FString, len=4)
            b'\x00\x00\x00\x00'                 # PinSubCategoryObject
            b'\x00\x00\x00\x00'                 # bIsMap = false
            b'\x00\x00\x00\x00'                 # bIsSet = false
            b'\x01\x00\x00\x00'                 # bIsArray = true
            b'\x00\x00\x00\x00'                 # bIsReference
            b'\x00\x00\x00\x00'                 # bIsWeakPointer
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 10,
                FRELEASE_OBJECT_VERSION_GUID: 0,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, [], summary)

        assert pin_type.container_type == 1  # Array (bIsArray = true)

    def test_member_reference_gating_enabled(self):
        """>= VER_UE4_MEMBERREFERENCE_IN_PINTYPE (355): 读取 MemberReference"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # ue4_version = 500 >= 355，读取 MemberReference
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            # MemberReference (ue4_version >= 355)
            b'\x01\x00\x00\x00'                   # MemberParent (FPackageIndex)
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberName (FName)
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberGuid (16 bytes)
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 0,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        # 验证成功读取（不抛异常）
        assert pin_type.pin_category == "object"

    def test_member_reference_gating_disabled(self):
        """< VER_UE4_MEMBERREFERENCE_IN_PINTYPE (355): 跳过 MemberReference"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # ue4_version = 300 < 355，不读取 MemberReference
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            # 无 MemberReference（版本 < 355）
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 0,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=300,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        # 验证成功读取（不抛异常）
        assert pin_type.pin_category == "object"

    def test_serialize_pintype_const_enabled(self):
        """>= VER_UE4_SERIALIZE_PINTYPE_CONST (456): 读取 bIsConst"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # ue4_version = 500 >= 456，读取 bIsConst
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            b'\x01\x00\x00\x00'                   # MemberParent (ue4 >= 355)
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberName
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberGuid
            b'\x01\x00\x00\x00'                   # bIsConst = true (ue4 >= 456)
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 0,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        assert pin_type.is_const is True

    def test_serialize_pintype_const_disabled(self):
        """< VER_UE4_SERIALIZE_PINTYPE_CONST (456): 跳过 bIsConst"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # ue4_version = 400 < 456，不读取 bIsConst
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            b'\x01\x00\x00\x00'                   # MemberParent (ue4 >= 355)
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberName
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberGuid
            # 无 bIsConst（版本 < 456）
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 0,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=400,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        assert pin_type.is_const is False  # 默认值

    def test_uobject_wrapper_enabled(self):
        """>= FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag (10): 读取 bIsUObjectWrapper"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # release_version = 15 >= 10，读取 bIsUObjectWrapper
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            b'\x01\x00\x00\x00'                   # MemberParent
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberName
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberGuid
            b'\x01\x00\x00\x00'                   # bIsConst
            b'\x01\x00\x00\x00'                   # bIsUObjectWrapper = true (release >= 10)
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 15,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        assert pin_type.is_uobject_wrapper is True

    def test_uobject_wrapper_disabled(self):
        """< FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag (10): 跳过 bIsUObjectWrapper"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # release_version = 5 < 10，不读取 bIsUObjectWrapper
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            b'\x01\x00\x00\x00'                   # MemberParent
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberName
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberGuid
            b'\x01\x00\x00\x00'                   # bIsConst
            # 无 bIsUObjectWrapper（版本 < 10）
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 5,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 0,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        assert pin_type.is_uobject_wrapper is False  # 默认值

    def test_single_precision_float_enabled(self):
        """>= FUE5ReleaseStreamObjectVersion::SerializeFloatPinDefaultsAsSinglePrecision (36): 读取标志"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # ue5release_version = 40 >= 36，读取 bSerializeAsSinglePrecisionFloat
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            b'\x01\x00\x00\x00'                   # MemberParent
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberName
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberGuid
            b'\x01\x00\x00\x00'                   # bIsConst
            b'\x01\x00\x00\x00'                   # bIsUObjectWrapper
            b'\x01\x00\x00\x00'                   # bSerializeAsSinglePrecisionFloat = true
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 15,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 40,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        assert pin_type.b_serialize_as_single_precision_float is True

    def test_single_precision_float_disabled(self):
        """< FUE5ReleaseStreamObjectVersion::SerializeFloatPinDefaultsAsSinglePrecision (36): 跳过"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # ue5release_version = 30 < 36，不读取 bSerializeAsSinglePrecisionFloat
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            b'\x01\x00\x00\x00'                   # MemberParent
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberName
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberGuid
            b'\x01\x00\x00\x00'                   # bIsConst
            b'\x01\x00\x00\x00'                   # bIsUObjectWrapper
            # 无 bSerializeAsSinglePrecisionFloat（版本 < 36）
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 20,
                FRELEASE_OBJECT_VERSION_GUID: 15,
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 30,
            },
            ue4_version=500,
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        assert pin_type.b_serialize_as_single_precision_float is False  # 默认值

    def test_all_version_gating_combined(self):
        """测试所有版本门控同时启用的完整场景"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            FRELEASE_OBJECT_VERSION_GUID,
            FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        )

        # 所有版本门控都启用
        name_map = ["float", ""]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # PinCategory (FName, framework >= 19)
            b'\x01\x00\x00\x00\x00\x00\x00\x00'  # PinSubCategory (FName)
            b'\x00\x00\x00\x00'                   # PinSubCategoryObject
            b'\x00'                               # ContainerType (uint8, framework >= 15)
            b'\x00\x00\x00\x00'                   # bIsReference
            b'\x00\x00\x00\x00'                   # bIsWeakPointer
            b'\x00\x00\x00\x00'                   # MemberParent (ue4 >= 355)
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberName
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  # MemberGuid
            b'\x01\x00\x00\x00'                   # bIsConst = true (ue4 >= 456)
            b'\x00\x00\x00\x00'                   # bIsUObjectWrapper = false (release >= 10)
            b'\x01\x00\x00\x00'                   # bSerializeAsSinglePrecisionFloat = true (ue5 >= 36)
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{
                FFRAMEWORK_OBJECT_VERSION_GUID: 25,  # >= 19, >= 15
                FRELEASE_OBJECT_VERSION_GUID: 12,    # >= 10
                FUE5RELEASESTREAM_OBJECT_VERSION_GUID: 40,  # >= 36
            },
            ue4_version=517,  # >= 456, >= 355
        )

        pin_type = read_ed_graph_pin_type(archive, name_map, summary)

        # 验证所有字段
        assert pin_type.pin_category == "float"
        assert pin_type.container_type == 0
        assert pin_type.is_reference is False
        assert pin_type.is_weak_pointer is False
        assert pin_type.is_const is True
        assert pin_type.is_uobject_wrapper is False
        assert pin_type.b_serialize_as_single_precision_float is True


class TestPropertyTagVersionGating:
    """验证 PropertyTag UE4 路径版本门控。"""

    def test_struct_guid_in_property_tag_gating(self):
        """>= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG (446): 读取 StructGuid"""
        from uasset_read.serializers.property_tags import read_property_tag

        # legacy_file_version = -500 (UE4 version 500 >= 446)
        name_map = ["TestProp", "StructProperty", "Vector", "None"]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Name (FName index=0, number=0)
            + b'\x01\x00\x00\x00\x00\x00\x00\x00'  # Type (FName index=1 = "StructProperty")
            + b'\x02\x00\x00\x00\x00\x00\x00\x00'  # StructType (FName index=2 = "Vector")
            + b'\x01'              # has_struct_guid = true
            + b'\x00' * 16         # StructGuid (16 bytes)
            + b'\x0c\x00\x00\x00'  # Size (12)
            + b'\x00\x00\x00\x00'  # ArrayIndex
            + b'\x00'              # has_guid = false
        )
        archive = _make_archive(data)

        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-500,  # UE4 version 500
        )
        assert tag.name == "TestProp"
        assert tag.type == "StructProperty"
        assert tag.struct_type == "Vector"
        assert tag.struct_guid is not None

    def test_struct_guid_skipped_for_old_version(self):
        """< VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG (446): 跳过 StructGuid"""
        from uasset_read.serializers.property_tags import read_property_tag

        # legacy_file_version = -400 (UE4 version 400 < 446)
        name_map = ["TestProp", "StructProperty", "Vector", "None"]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Name
            + b'\x01\x00\x00\x00\x00\x00\x00\x00'  # Type = "StructProperty"
            + b'\x02\x00\x00\x00\x00\x00\x00\x00'  # StructType = "Vector"
            # 无 StructGuid（版本 < 446）
            + b'\x0c\x00\x00\x00'  # Size
            + b'\x00\x00\x00\x00'  # ArrayIndex
        )
        archive = _make_archive(data)

        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-400,  # UE4 version 400
        )
        assert tag.struct_guid is None

    def test_property_guid_in_property_tag_gating(self):
        """>= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG (508): 读取 PropertyGuid"""
        from uasset_read.serializers.property_tags import read_property_tag

        name_map = ["TestProp", "IntProperty", "None"]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Name
            + b'\x01\x00\x00\x00\x00\x00\x00\x00'  # Type = "IntProperty"
            + b'\x04\x00\x00\x00'  # Size (4)
            + b'\x00\x00\x00\x00'  # ArrayIndex
            + b'\x01'              # has_guid = true
            + b'\x00' * 16         # PropertyGuid
        )
        archive = _make_archive(data)

        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-520,  # UE4 version 520 >= 508
        )
        assert tag.property_guid is not None

    def test_set_map_support_gating(self):
        """>= VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT (514): 支持 MapProperty"""
        from uasset_read.serializers.property_tags import read_property_tag

        name_map = ["TestMap", "MapProperty", "StrProperty", "IntProperty", "None"]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Name
            + b'\x01\x00\x00\x00\x00\x00\x00\x00'  # Type = "MapProperty"
            + b'\x02\x00\x00\x00\x00\x00\x00\x00'  # KeyType = "StrProperty"
            + b'\x03\x00\x00\x00\x00\x00\x00\x00'  # ValueType = "IntProperty"
            + b'\x00\x00\x00\x00'  # Size
            + b'\x00\x00\x00\x00'  # ArrayIndex
        )
        archive = _make_archive(data)

        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-520,  # UE4 version 520 >= 514
        )
        assert tag.key_type == "StrProperty"
        assert tag.value_type == "IntProperty"

    def test_array_inner_tags_gating(self):
        """>= VAR_UE4_ARRAY_PROPERTY_INNER_TAGS (253): 读取 ArrayProperty InnerType"""
        from uasset_read.serializers.property_tags import read_property_tag

        name_map = ["TestArray", "ArrayProperty", "IntProperty", "None"]
        data = (
            b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Name
            + b'\x01\x00\x00\x00\x00\x00\x00\x00'  # Type = "ArrayProperty"
            + b'\x02\x00\x00\x00\x00\x00\x00\x00'  # InnerType = "IntProperty"
            + b'\x00\x00\x00\x00'  # Size
            + b'\x00\x00\x00\x00'  # ArrayIndex
        )
        archive = _make_archive(data)

        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-300,  # UE4 version 300 >= 253
        )
        assert tag.inner_type == "IntProperty"


class TestFTextVersionGating:
    """验证 FText 序列化版本门控。

    FText 序列化根据 UE4 版本决定是否读取 history_type 字段：
    - >= VER_UE4_FTEXT_HISTORY (428): 读取 history_type (i8)
    - < 428: 跳过 history_type，直接读取 Base 格式
    """

    def test_ftext_history_gating(self):
        """>= VER_UE4_FTEXT_HISTORY (428): 读取 history_type"""
        from uasset_read.blueprint._ftext import read_ftext

        # ue4_version = 500 >= 428，应读取 history_type
        data = (
            b'\x00\x00\x00\x00'          # flags
            b'\x00'                       # history_type = 0 (Base)
            b'\x00\x00\x00\x00'          # namespace (empty FString)
            b'\x00\x00\x00\x00'          # key (empty FString)
            b'\x06\x00\x00\x00Hello\x00'  # source_string (6 bytes including null)
        )
        archive = _make_archive(data)
        summary = _make_summary(ue4_version=500)

        result = read_ftext(archive, summary)
        assert result == "Hello"

    def test_ftext_no_history_for_old_version(self):
        """< VER_UE4_FTEXT_HISTORY (428): 跳过 history_type，直接读 Base 格式"""
        from uasset_read.blueprint._ftext import read_ftext

        # ue4_version = 400 < 428，无 history_type
        data = (
            b'\x00\x00\x00\x00'          # flags
            # 无 history_type（旧版本）
            b'\x00\x00\x00\x00'          # namespace
            b'\x00\x00\x00\x00'          # key
            b'\x06\x00\x00\x00World\x00'  # source_string
        )
        archive = _make_archive(data)
        summary = _make_summary(ue4_version=400)

        result = read_ftext(archive, summary)
        assert result == "World"

    def test_ftext_boundary_version_428(self):
        """ue4_version == 428 (VER_UE4_FTEXT_HISTORY): 应读取 history_type"""
        from uasset_read.blueprint._ftext import read_ftext

        data = (
            b'\x00\x00\x00\x00'          # flags
            b'\x00'                       # history_type = 0 (Base)
            b'\x00\x00\x00\x00'          # namespace
            b'\x00\x00\x00\x00'          # key
            b'\x04\x00\x00\x00test\x00'  # source_string
        )
        archive = _make_archive(data)
        summary = _make_summary(ue4_version=428)

        result = read_ftext(archive, summary)
        assert result == "test"

    def test_ftext_boundary_version_427(self):
        """ue4_version == 427 (< 428): 不读取 history_type"""
        from uasset_read.blueprint._ftext import read_ftext

        data = (
            b'\x00\x00\x00\x00'          # flags
            # 无 history_type
            b'\x00\x00\x00\x00'          # namespace
            b'\x00\x00\x00\x00'          # key
            b'\x04\x00\x00\x00test\x00'  # source_string
        )
        archive = _make_archive(data)
        summary = _make_summary(ue4_version=427)

        result = read_ftext(archive, summary)
        assert result == "test"

    def test_ftext_no_summary_defaults_to_modern(self):
        """summary=None 时默认 ue4_version=500 (现代格式)，读取 history_type"""
        from uasset_read.blueprint._ftext import read_ftext

        data = (
            b'\x00\x00\x00\x00'          # flags
            b'\x00'                       # history_type = 0 (Base)
            b'\x00\x00\x00\x00'          # namespace
            b'\x00\x00\x00\x00'          # key
            b'\x02\x00\x00\x00AB\x00'    # source_string
        )
        archive = _make_archive(data)

        result = read_ftext(archive, summary=None)
        assert result == "AB"
