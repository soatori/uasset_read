"""DataTable 资产类型处理器

解析 UDataTable 的特有数据：
- RowStruct: FObjectProperty（int32 对象引用）
- RowMap: TMap<FName, FTableRowBase>

格式参考：
- Engine/Source/Runtime/Engine/Classes/Engine/DataTable.h
- Engine/Source/Runtime/Engine/Private/DataTable.cpp
"""
from __future__ import annotations

import struct
from typing import Any, Dict, List


def parse_data_table(
    archive: Any,
    name_map: List[str],
) -> Dict[str, Any]:
    """解析 DataTable 资产元数据。

    Args:
        archive: FArchive 实例（已定位到 payload 起始位置）
        name_map: 名称表

    Returns:
        解析结果字典，包含 row_struct_index、row_count、rows 等
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
        "row_struct_index": 0,
        "row_count": 0,
        "rows": [],
    }

    try:
        # 1. RowStruct: FObjectProperty — int32 index into linker's ImportMap/ExportMap
        #    参照 DataTable.cpp: UDataTable::Serialize 写入 RowStruct
        row_struct_index = archive.read_i32("RowStruct")
        result["row_struct_index"] = row_struct_index

        # 2. RowMap: TMap<FName, FTableRowBase>
        #    TMap 序列化为 count + entries，每个 entry = Key(FName) + Value(payload)
        row_count = archive.read_i32("RowMap.Count")
        if row_count < 0:
            result["parse_status"] = "partial"
            result["error"] = f"Invalid row count: {row_count}"
            return result

        result["row_count"] = row_count
        rows: List[Dict[str, Any]] = []

        for _ in range(row_count):
            # FName: Index (int32) + Number (int32)
            name_index = archive.read_i32("FName.Index")
            name_number = archive.read_i32("FName.Number")

            # 解析名称
            if 0 <= name_index < len(name_map):
                row_name = name_map[name_index]
            else:
                row_name = f"<invalid_index_{name_index}>"

            # FTableRowBase payload: size (int32) + data (bytes)
            payload_size = archive.read_i32("Payload.Size")
            if payload_size < 0 or payload_size > archive.total_size():
                result["parse_status"] = "partial"
                result["error"] = f"Invalid payload size: {payload_size}"
                break

            payload_data = archive.read(payload_size) if payload_size > 0 else b""

            row = {
                "name": row_name,
                "name_index": name_index,
                "name_number": name_number,
                "payload_size": payload_size,
            }
            rows.append(row)

        result["rows"] = rows

    except Exception as e:
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result
