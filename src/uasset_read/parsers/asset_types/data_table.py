"""DataTable Asset type handler

Parse UDataTable LoadStructData (after tagged properties):
- NumRows: int32
- Per row: FName(Index + Number, each int32) + RowPayload(size int32 + data)

Format reference:
- Engine/Source/Runtime/Engine/Classes/Engine/DataTable.h
- Engine/Source/Runtime/Engine/Private/DataTable.cpp — UDataTable::Serialize / LoadStructData
"""

import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

# Safety limit: prevent garbage bytes from being interpreted as row count
_MAX_ROWS = 100000


def parse_data_table(
    archive: Any,
    name_map: List[str],
) -> Dict[str, Any]:
    """Parse DataTable asset metadata.

    archive is positioned at the start of the custom payload after tagged properties.
    Reads the NumRows + (FName + RowPayload) sequence.

    Args:
        archive: FArchive instance (positioned at property_end)
        name_map: name map

    Returns:
        Parse result dictionary containing row_count, rows, etc.
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
        "row_count": 0,
        "rows": [],
    }

    try:
        # NumRows: int32 — DataTable.cpp: LoadStructData start
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

            # Parse name
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
