"""UE5/Verse 特定属性类型解析函数。

从 _all_types.py 拆分出的 Verse 语言相关解析器。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.models.properties import PropertyTag


def parse_verse_string_property(tag: PropertyTag, archive: "FArchive") -> str:
    """解析 VerseStringProperty"""
    return archive.read_fstring()


def parse_verse_class_property(tag: PropertyTag, archive: "FArchive") -> int:
    """解析 VerseClassProperty"""
    return archive.read_i32()


def parse_verse_function_property(tag: PropertyTag, archive: "FArchive") -> int:
    """解析 VerseFunctionProperty"""
    return archive.read_i32()


def parse_verse_dynamic_property(tag: PropertyTag, archive: "FArchive") -> int:
    """解析 VerseDynamicProperty"""
    return archive.read_i32()


def parse_verse_cell_property(tag: PropertyTag, archive: "FArchive") -> dict:
    """解析 VerseCellProperty（UE5.6+ Verse 脚本系统）。

    VerseCell 引用指向 Verse 文件中的单元格，序列化格式为 PackageIndex + 名称索引。
    当前返回原始引用值，完整解析需要 Verse 文件系统。
    """
    start = archive.tell()
    package_index = archive.read_i32() if tag.size >= 4 else 0
    name_index = archive.read_i32() if tag.size >= 8 else -1
    consumed = archive.tell() - start
    raw = archive.read_bytes(tag.size - consumed) if tag.size > consumed else b""
    return {
        "kind": "VerseCellProperty",
        "ref": {"package_index": package_index, "name_index": name_index},
        "raw": raw,
    }


def parse_verse_value_property(tag: PropertyTag, archive: "FArchive") -> dict:
    """解析 VerseValueProperty（UE5.6+ Verse 脚本系统）。

    VerseValue 是 Verse 类型系统的运行时值容器，序列化包含类型标签 + 值。
    当前读取类型标签和原始数据，完整解析需要 Verse 类型系统知识。
    """
    start = archive.tell()
    type_tag = archive.read_u8() if tag.size >= 1 else 0
    value_data = None
    try:
        if tag.size > 1:
            value_data = archive.read_fstring()
    except Exception:
        archive.seek(start + 1)
    consumed = archive.tell() - start
    raw = archive.read_bytes(tag.size - consumed) if tag.size > consumed else b""
    return {
        "kind": "VerseValueProperty",
        "type_tag": type_tag,
        "value": value_data,
        "raw": raw,
    }


def parse_field_path_property(
    tag: PropertyTag,
    archive: "FArchive",
    name_map: Optional[list] = None,
    summary: Optional[Any] = None,
) -> dict:
    """解析 FieldPathProperty（FFieldPath）。

    UE 序列化格式（FieldPath.cpp:316）:
      - Path: TArray<FName>（count + count × FName）
      - Owner: UStruct*（对象引用，版本控制：FFortniteMainBranchObjectVersion
        >= FFieldPathOwnerSerialization 或 FReleaseObjectVersion 同版本）

    name_map 为 None 时 fallback 到 read_fstring 并标记 partial。
    """
    from uasset_read.parsers.utils import read_validated_count

    result: Dict[str, Any] = {"path": [], "owner": None}
    parse_status = "parsed"

    count = read_validated_count(archive, 10_000, "FieldPath")
    path: List[str] = []
    for _ in range(count):
        if name_map is not None:
            path.append(archive.read_name(name_map))
        else:
            # Fallback: name_map 不可用时退化为 FString 读取
            path.append(archive.read_fstring())
            parse_status = "partial"
    result["path"] = path

    # 读取 owner 引用（UStruct* 序列化为 FPackageIndex i32）
    # 版本控制由调用方/summary 决定；未烘焙资产通常包含此字段
    try:
        owner_index = archive.read_i32()
        result["owner"] = owner_index
    except Exception:
        pass  # 旧格式可能没有 owner 字段

    if parse_status != "parsed":
        result["parse_status"] = parse_status
        result["unsupported_reason"] = "fieldpath_missing_name_map"
    return result
