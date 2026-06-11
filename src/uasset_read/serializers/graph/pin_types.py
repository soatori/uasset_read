"""FEdGraphPinType 序列化器 — Pin 类型结构读取（UE4/UE5 兼容）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    FRELEASE_OBJECT_VERSION_GUID,
    FFRAMEWORK_OBJECT_VERSION_GUID,
    FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER,
    FFRAMEWORK_VERSION_PINS_STORE_FNAME,
    FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE,
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
    FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION,
    VER_UE4_MEMBERREFERENCE_IN_PINTYPE,
    VER_UE4_SERIALIZE_PINTYPE_CONST,
)
from uasset_read.models.core import FEdGraphPinType, FEdGraphTerminalType
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.serializers.graph._common import _rcn


def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    import_map: Optional[List[ObjectImport]] = None,
    export_map: Optional[List[ObjectExport]] = None,
    linker: Optional["PackageLinker"] = None,
) -> FEdGraphPinType:
    """解析 FEdGraphPinType（UE4/UE5 兼容 — 带版本门控）。

    参考 UE 源码：Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp
    FEdGraphPinType::Serialize()
    """
    pin_type = FEdGraphPinType()

    # 获取版本信息
    framework_version = summary.get_custom_version(FFRAMEWORK_OBJECT_VERSION_GUID, 0)
    release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)
    ue5release_version = summary.get_custom_version(FUE5RELEASESTREAM_OBJECT_VERSION_GUID, 0)
    ue4_version = summary.file_version_ue4 if hasattr(summary, 'file_version_ue4') else 0

    # =========================================================================
    # 1. PinCategory / PinSubCategory
    #    >= FFrameworkObjectVersion::PinsStoreFName (19): FName
    #    < 19: FString (UE4 旧格式)
    # =========================================================================
    if framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME:
        pin_type.pin_category = archive.read_name(name_map)
        pin_type.pin_subcategory = archive.read_name(name_map)
    else:
        # UE4 旧格式：使用 FString
        pin_type.pin_category = archive.read_fstring()
        pin_type.pin_subcategory = archive.read_fstring()

    # =========================================================================
    # 2. PinSubCategoryObject (FPackageIndex)
    # =========================================================================
    pin_type.pin_subcategory_object = archive.read_i32()
    if pin_type.pin_subcategory_object:
        pkg_idx = PackageIndex(pin_type.pin_subcategory_object)
        try:
            if linker is not None:
                pin_type.pin_subcategory_object_ref = linker.resolve_package_index(pkg_idx)
                if pin_type.pin_subcategory_object_ref is not None:
                    pin_type.pin_subcategory_object_name = getattr(
                        pin_type.pin_subcategory_object_ref, "object_name", None
                    )
            elif import_map is not None and export_map is not None:
                pin_type.pin_subcategory_object_name = _rcn(
                    pkg_idx, import_map, export_map, linker
                )
        except Exception:
            pin_type.pin_subcategory_object_ref = None
            pin_type.pin_subcategory_object_name = None

    # =========================================================================
    # 3. ContainerType / PinValueType
    #    >= FFrameworkObjectVersion::EdGraphPinContainerType (15): uint8 + Map 时读 FEdGraphTerminalType
    #    < 15: 3 个 bool (bIsMap, bIsSet, bIsArray) + Map 时读 FEdGraphTerminalType
    # =========================================================================
    if framework_version >= FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE:
        # 现代格式：uint8 enum
        pin_type.container_type = archive.read_u8()
        if pin_type.container_type == 3:  # Map
            # 读取 FEdGraphTerminalType (PinValueType)
            pin_type.pin_value_type = FEdGraphTerminalType(
                pin_category=archive.read_name(name_map),
                pin_subcategory=archive.read_name(name_map),
                pin_subcategory_object=archive.read_i32(),
            )
    else:
        # UE4 旧格式：3 个 bool
        bIsMap = archive.read_bool()
        bIsSet = archive.read_bool()
        if bIsMap:
            # 读取 FEdGraphTerminalType (PinValueType)
            pin_type.pin_value_type = FEdGraphTerminalType(
                pin_category=archive.read_name(name_map),
                pin_subcategory=archive.read_name(name_map),
                pin_subcategory_object=archive.read_i32(),
            )
        # bIsArray 在 bIsSet 之后读取
        bIsArray = archive.read_bool()

        # 计算 container_type
        if bIsArray:
            pin_type.container_type = 1  # Array
        elif bIsSet:
            pin_type.container_type = 2  # Set
        elif bIsMap:
            pin_type.container_type = 3  # Map
        else:
            pin_type.container_type = 0  # None

    # =========================================================================
    # 4. bIsReference / bIsWeakPointer (始终存在，FArchive bool = uint32)
    # =========================================================================
    pin_type.is_reference = archive.read_bool()
    pin_type.is_weak_pointer = archive.read_bool()

    # =========================================================================
    # 5. PinSubCategoryMemberReference (FSimpleMemberReference)
    #    >= VER_UE4_MEMBERREFERENCE_IN_PINTYPE (354): 存在
    #    < 354: 不存在
    # =========================================================================
    if ue4_version >= VER_UE4_MEMBERREFERENCE_IN_PINTYPE:
        archive.read_i32()              # MemberParent
        archive.read_name(name_map)     # MemberName
        archive.read_bytes(16)          # MemberGuid

    # =========================================================================
    # 6. bIsConst
    #    >= VER_UE4_SERIALIZE_PINTYPE_CONST (455): 存在
    #    < 455: 不存在
    # =========================================================================
    if ue4_version >= VER_UE4_SERIALIZE_PINTYPE_CONST:
        pin_type.is_const = archive.read_bool()

    # =========================================================================
    # 7. bIsUObjectWrapper
    #    >= FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag (10): 存在
    #    < 10: 不存在
    # =========================================================================
    if release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER:
        pin_type.is_uobject_wrapper = archive.read_bool()

    # =========================================================================
    # 8. bSerializeAsSinglePrecisionFloat
    #    >= FUE5ReleaseStreamObjectVersion::SerializeFloatPinDefaultsAsSinglePrecision (36): 存在
    #    < 36: 不存在
    # =========================================================================
    if ue5release_version >= FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION:
        pin_type.b_serialize_as_single_precision_float = archive.read_bool()

    return pin_type
