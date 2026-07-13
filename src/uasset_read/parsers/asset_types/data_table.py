"""DataTable 资产类型处理器

解析 UDataTable 的 LoadStructData（在 tagged properties 之后）：
- NumRows: int32
- 每行: FName(Index + Number, 各 int32) + RowPayload(size int32 + data)

格式参考：
- Engine/Source/Runtime/Engine/Classes/Engine/DataTable.h
- Engine/Source/Runtime/Engine/Private/DataTable.cpp — UDataTable::Serialize / LoadStructData
"""

import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

# 安全上限：防止将垃圾字节解释为行数
_MAX_ROWS = 100000


def parse_data_table(
    archive: Any,
    name_map: List[str],
) -> Dict[str, Any]:
    """解析 DataTable 资产元数据。

    archive 已定位到 tagged properties 之后的自定义 payload 起始位置。
    读取 NumRows + (FName + RowPayload) 序列。

    Args:
        archive: FArchive 实例（已定位到 property_end）
        name_map: 名称表

    Returns:
        解析结果字典，包含 row_count、rows 等
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
        "row_count": 0,
        "rows": [],
    }

    try:
        # NumRows: int32 — DataTable.cpp: LoadStructData 起始
        row_count = archive.read_i32("NumRows")
        if row_count < 0:
            result["parse_status"] = "partial"
            result["error"] = f"Invalid row count: {row_count}"
            return result
        if row_count > _MAX_ROWS:
            result["parse_status"] = "partial"
            result["error"] = f"Row count {row_count} exceeds safety limit {_MAX_ROWS}"
            return result

        result["row_count"] = row_count
        rows: List[Dict[str, Any]] = []

        for i in range(row_count):
            # FName: Index (int32) + Number (int32)
            name_index = archive.read_i32(f"Row[{i}].FName.Index")
            name_number = archive.read_i32(f"Row[{i}].FName.Number")

            # 解析名称
            if 0 <= name_index < len(name_map):
                row_name = name_map[name_index]
            else:
                row_name = f"<invalid_index_{name_index}>"

            # RowPayload: size (int32) + data (bytes)
            payload_size = archive.read_i32(f"Row[{i}].Payload.Size")
            if payload_size < 0:
                result["parse_status"] = "partial"
                result["error"] = f"Invalid payload size at row {i}: {payload_size}"
                break
            if payload_size > archive.total_size():
                result["parse_status"] = "partial"
                result["error"] = f"Payload size {payload_size} exceeds archive size"
                break

            _payload_data = archive.read(payload_size) if payload_size > 0 else b""  # noqa: F841 - protocol read

            row = {
                "name": row_name,
                "name_index": name_index,
                "name_number": name_number,
                "payload_size": payload_size,
            }
            rows.append(row)

        result["rows"] = rows

    except (struct.error, OSError, ValueError, ParseError) as e:
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result
