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
