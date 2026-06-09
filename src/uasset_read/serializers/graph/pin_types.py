"""FEdGraphPinType 序列化器 — Pin 类型结构读取。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    FRELEASE_OBJECT_VERSION_GUID,
)
from uasset_read.models.core import FEdGraphPinType
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
    """解析 FEdGraphPinType（UE5.7 专用 — 自定义序列化路径）。"""
    pin_type = FEdGraphPinType()

    release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)

    # PinCategory / PinSubCategory (UE5 始终使用 FName 格式)
    pin_type.pin_category = archive.read_name(name_map)
    pin_type.pin_subcategory = archive.read_name(name_map)

    # PinSubCategoryObject (FPackageIndex)
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

    # ContainerType (UE5 始终使用现代 uint8 格式)
    pin_type.container_type = archive.read_u8()
    if pin_type.container_type == 3:  # Map
        archive.read_name(name_map)  # TerminalCategory
        archive.read_name(name_map)  # TerminalSubCategory
        archive.read_i32()           # TerminalSubCategoryObject

    # bIsReference / bIsWeakPointer (UE5 FArchive bool = uint32, 4B)
    pin_type.is_reference = archive.read_bool()
    pin_type.is_weak_pointer = archive.read_bool()

    # FSimpleMemberReference (UE5 始终存在)
    archive.read_i32()       # MemberParent
    archive.read_name(name_map)  # MemberName
    archive.read_bytes(16)   # MemberGuid

    # bIsConst (UE5 FArchive bool = uint32, 4B)
    pin_type.is_const = archive.read_bool()

    # bIsUObjectWrapper (UE5 FArchive bool = uint32, 4B)
    pin_type.is_uobject_wrapper = archive.read_bool()

    # bSerializeAsSinglePrecisionFloat (UE5 FArchive bool = uint32, 4B)
    pin_type.b_serialize_as_single_precision_float = archive.read_bool()

    return pin_type
