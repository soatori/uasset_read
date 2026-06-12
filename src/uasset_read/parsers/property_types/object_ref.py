"""对象引用属性解析器：object, soft_object, weak_object, lazy_object, class, interface 等。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.models.properties import PropertyTag, SoftObjectPathValue


def parse_object_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 ObjectProperty（PROP-07）。返回原始 FPackageIndex。"""
    return archive.read_i32()


def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    soft_object_path_list: Optional[List[Dict]] = None,
    file_version_ue4: int = 0,
    file_version_ue5: int = 0,
) -> SoftObjectPathValue:
    """解析 SoftObjectProperty（FSoftObjectPath）— 三阶段版本门控。

    序列化格式随引擎版本演变（参考 UE 源码 FSoftObjectPath operator<<）：
    - Phase 4 (UE5 >= 1008): SoftObjectPathList 索引格式
    - Phase 3 (UE5 >= 1007): FUtf8String + FUtf8String (REMOVE_ASSET_PATH_FNAMES)
    - Phase 2 (UE4 >= 514 或 UE5 < 1007): FName(AssetPath) + WideString(SubPath)
    - Phase 1 (Legacy UE4 < 514): 单一 FString
    - Fallback (版本未知 0,0): FString + FString（向后兼容默认格式）
    """
    # Phase 4: UE5 >= 1008 — SoftObjectPathList 索引格式（最高优先级）
    if soft_object_path_list is not None and len(soft_object_path_list) > 0:
        index = archive.read_i32()
        if 0 <= index < len(soft_object_path_list):
            entry = soft_object_path_list[index]
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path=entry.get('asset_path', ''),
                sub_path=entry.get('sub_path', ''),
                index=index,
            )
        else:
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path='',
                sub_path='',
                index=index,
                error=f"SoftObjectPath index {index} out of bounds (list size {len(soft_object_path_list)})",
            )

    # Phase 3: UE5 >= 1007 — FUtf8String + FUtf8String
    if file_version_ue5 >= 1007:
        asset_path = archive.read_fstring()
        sub_path = archive.read_fstring()
        return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)

    # Phase 2: FName(AssetPath) + WideString(SubPath)
    # 适用条件：UE4 >= 514 或 UE5 (0 < ue5 < 1007)
    if file_version_ue4 >= 514 or file_version_ue5 > 0:
        # FName: int32 index into name map + int32 number
        asset_path_index = archive.read_i32()
        _asset_path_number = archive.read_i32()  # number 分量，通常未使用
        if 0 <= asset_path_index < len(name_map):
            asset_path = name_map[asset_path_index]
        else:
            asset_path = ""
        sub_path = archive.read_fstring()
        return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)

    # Phase 1: Legacy UE4 (1 <= ue4 < 514) — 单一 FString
    if file_version_ue4 > 0:
        asset_path = archive.read_fstring()
        return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path)

    # Fallback: 版本未知 (0, 0) — 向后兼容默认格式 (FString + FString)
    # 未传递版本参数时保留原始行为，确保现有调用方正常工作
    asset_path = archive.read_fstring()
    sub_path = archive.read_fstring()
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)


def parse_weak_object_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 WeakObjectProperty"""
    return archive.read_i32()


def parse_lazy_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """解析 LazyObjectProperty"""
    read_size = tag.size if tag.size > 0 else 16
    raw = archive.read_bytes(read_size)
    return SoftObjectPathValue(raw_kind=tag.type, guid=raw.hex())


def parse_class_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 ClassProperty"""
    return archive.read_i32()


def parse_soft_class_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str] = None,
    soft_object_path_list: Optional[List[Dict]] = None,
    file_version_ue4: int = 0,
    file_version_ue5: int = 0,
) -> SoftObjectPathValue:
    """解析 SoftClassProperty — 与 SoftObjectProperty 解析方式相同，版本参数透传。"""
    return parse_soft_object_property(
        tag, archive, name_map or [], soft_object_path_list,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
    )


def parse_asset_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """解析 AssetObjectProperty"""
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=archive.read_fstring())


def parse_interface_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 InterfaceProperty"""
    return archive.read_i32()
