"""UClass 原生字段解析器 — 解析 UClass::Serialize 的原生序列化字段。

参考 UE 源码 Class.cpp:5987-6263，UClass::Serialize 的序列化顺序：
1. Super::Serialize(Ar) - UStruct::Serialize
2. Ar << FuncMap
3. Ar << ClassFlags
4. Ar << ClassWithin
5. Ar << ClassConfigName
6. Ar << NumInterfaces
7. Ar << Interfaces
8. Ar << ClassGeneratedBy
9. Ar << bDeprecatedForceScriptOrder
10. Ar << Dummy
11. Ar << ClassDefaultObject

注意：本解析器仅处理原生字段，tagged properties 由通用 property parser 处理。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

logger = logging.getLogger(__name__)


def _read_package_index(archive: "FArchive") -> Dict[str, Any]:
    """读取 FPackageIndex（4 字节有符号整数）。

    正值表示 export 索引（从 1 开始），负值表示 import 索引（从 -1 开始），
    0 表示 null。

    Returns:
        dict: {
            "raw_value": int,
            "is_null": bool,
            "is_export": bool,
            "is_import": bool,
            "export_index": Optional[int],  # 0-based
            "import_index": Optional[int],  # 0-based
        }
    """
    raw = archive.read_i32()
    if raw == 0:
        return {
            "raw_value": 0,
            "is_null": True,
            "is_export": False,
            "is_import": False,
            "export_index": None,
            "import_index": None,
        }
    elif raw > 0:
        return {
            "raw_value": raw,
            "is_null": False,
            "is_export": True,
            "is_import": False,
            "export_index": raw - 1,  # 转为 0-based
            "import_index": None,
        }
    else:  # raw < 0
        return {
            "raw_value": raw,
            "is_null": False,
            "is_export": False,
            "is_import": True,
            "export_index": None,
            "import_index": -raw - 1,  # 转为 0-based
        }


def _read_fname(archive: "FArchive", name_map: List[str]) -> str:
    """读取 FName（名称表索引 + 实例编号）。

    Args:
        archive: FArchive 实例
        name_map: 名称表

    Returns:
        解析后的名称字符串
    """
    return archive.read_name(name_map)


def _read_func_map(
    archive: "FArchive", name_map: List[str]
) -> Dict[str, Any]:
    """读取 FuncMap（TMap<FName, FPackageIndex>）。

    UE 源码 Class.cpp:6044: Ar << FuncMap;
    TMap 序列化为：count, 然后 count 个 (key, value) 对。

    Returns:
        dict: {
            "count": int,
            "entries": List[Dict[str, Any]],  # [{"name": str, "function": FPackageIndex}]
        }
    """
    count = archive.read_i32()
    if count < 0 or count > 10000:  # 防御性检查
        logger.warning("FuncMap count %d 异常，可能偏移错误", count)
        return {"count": count, "entries": [], "parse_error": "invalid_count"}

    entries = []
    for _ in range(count):
        func_name = _read_fname(archive, name_map)
        func_ref = _read_package_index(archive)
        entries.append({
            "name": func_name,
            "function": func_ref,
        })

    return {"count": count, "entries": entries}


def _read_implemented_interface(
    archive: "FArchive",
) -> Dict[str, Any]:
    """读取 FImplementedInterface 结构。

    UE 源码 Class.h:
    struct FImplementedInterface {
        UClass* Class;          // FPackageIndex
        int32 PointerOffset;    // int32
        bool bImplementedByK2;  // bool
    };

    Returns:
        dict: {
            "class": FPackageIndex,
            "pointer_offset": int,
            "implemented_by_k2": bool,
        }
    """
    class_ref = _read_package_index(archive)
    pointer_offset = archive.read_i32()
    implemented_by_k2 = archive.read_bool_1byte()

    return {
        "class": class_ref,
        "pointer_offset": pointer_offset,
        "implemented_by_k2": implemented_by_k2,
    }


def _read_interfaces(archive: "FArchive") -> Dict[str, Any]:
    """读取 Interfaces（TArray<FImplementedInterface>）。

    UE 源码 Class.cpp:6060-6061:
    int32 NumInterfaces;
    Ar << NumInterfaces;
    Interfaces.Empty(NumInterfaces);
    for (int32 InterfaceIndex = 0; InterfaceIndex < NumInterfaces; ++InterfaceIndex)
    {
        Ar << Interfaces[InterfaceIndex];
    }

    Returns:
        dict: {
            "count": int,
            "interfaces": List[Dict[str, Any]],
        }
    """
    count = archive.read_i32()
    if count < 0 or count > 1000:  # 防御性检查
        logger.warning("Interfaces count %d 异常，可能偏移错误", count)
        return {"count": count, "interfaces": [], "parse_error": "invalid_count"}

    interfaces = []
    for _ in range(count):
        interfaces.append(_read_implemented_interface(archive))

    return {"count": count, "interfaces": interfaces}


def parse_uclass_fields(
    archive: "FArchive",
    name_map: List[str],
    summary: Optional[Any] = None,
) -> Dict[str, Any]:
    """解析 UClass 原生序列化字段。

    按 UE 序列化顺序读取：
    1. UStruct 层级字段（SuperStruct, Children, PropertiesSize, MinAlignment）
    2. UClass 层级字段（FuncMap, ClassFlags, ClassWithin, ClassConfigName,
       Interfaces, ClassGeneratedBy, bDeprecatedForceScriptOrder, Dummy,
       ClassDefaultObject）

    Args:
        archive: FArchive 实例，已定位到 export 的 serial_offset
        name_map: 名称表
        summary: PackageFileSummary（可选，用于版本检查）

    Returns:
        dict: 包含所有解析的字段
    """
    start_pos = archive.tell()
    result: Dict[str, Any] = {
        "parse_status": "success",
        "start_offset": start_pos,
    }

    try:
        # === UStruct 层级字段 ===
        # SuperStruct (FPackageIndex)
        result["super_struct"] = _read_package_index(archive)

        # Children (FPackageIndex - linked list head)
        result["children"] = _read_package_index(archive)

        # PropertiesSize (int32)
        result["properties_size"] = archive.read_i32()

        # MinAlignment (int32)
        result["min_alignment"] = archive.read_i32()

        # === UClass 层级字段 ===
        # FuncMap (TMap<FName, UFunction*>)
        result["func_map"] = _read_func_map(archive, name_map)

        # ClassFlags (uint32)
        result["class_flags"] = archive.read_u32()

        # ClassWithin (FPackageIndex - UClass*)
        result["class_within"] = _read_package_index(archive)

        # ClassConfigName (FName)
        result["class_config_name"] = _read_fname(archive, name_map)

        # Interfaces (TArray<FImplementedInterface>)
        result["interfaces"] = _read_interfaces(archive)

        # ClassGeneratedBy (FPackageIndex - UBlueprint*)
        result["class_generated_by"] = _read_package_index(archive)

        # bDeprecatedForceScriptOrder (bool)
        result["deprecated_force_script_order"] = archive.read_bool_1byte()

        # Dummy (FName - NAME_None)
        result["dummy"] = _read_fname(archive, name_map)

        # ClassDefaultObject (FPackageIndex - UObject*)
        result["class_default_object"] = _read_package_index(archive)

        result["bytes_read"] = archive.tell() - start_pos

    except Exception as e:
        logger.warning(
            "UClass 原生字段解析失败 at offset %d: %s",
            start_pos, e,
        )
        result["parse_status"] = "partial"
        result["parse_error"] = str(e)
        result["bytes_read"] = archive.tell() - start_pos

    return result
