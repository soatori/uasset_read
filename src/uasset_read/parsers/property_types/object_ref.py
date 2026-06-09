"""对象引用属性解析器：object, soft_object, weak_object, lazy_object, class, interface 等。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

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
) -> SoftObjectPathValue:
    """解析 SoftObjectProperty（FSoftObjectPath）。

    当 soft_object_path_list 存在时（UE5.7+），读取 int32 索引。
    否则读取 FString 对（传统格式）。
    """
    if soft_object_path_list is not None and len(soft_object_path_list) > 0:
        # UE5.7+ 索引格式
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
    else:
        # 传统 FString 格式
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
) -> SoftObjectPathValue:
    """解析 SoftClassProperty — 与 SoftObjectProperty 解析方式相同。"""
    return parse_soft_object_property(tag, archive, name_map or [], soft_object_path_list)


def parse_asset_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """解析 AssetObjectProperty"""
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=archive.read_fstring())


def parse_interface_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 InterfaceProperty"""
    return archive.read_i32()
