"""CurveTable 资产类型处理器

解析 UCurveTable 的特有数据：
- NumRows: int32 — 行数
- CurveTableMode: uint8 — 曲线类型 (0=Empty, 1=SimpleCurves, 2=RichCurves)
- RowMap: TArray<FName + FRichCurve/FSimpleCurve>

格式参考：
- Engine/Source/Runtime/Engine/Classes/Engine/CurveTable.h
- Engine/Source/Runtime/Engine/Private/CurveTable.cpp
"""

import logging
import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


# ECurveTableMode 枚举值（CurveTable.h:29-33）
_CURVE_TABLE_MODE_EMPTY = 0
_CURVE_TABLE_MODE_SIMPLE = 1
_CURVE_TABLE_MODE_RICH = 2

_MODE_NAMES = {
    _CURVE_TABLE_MODE_EMPTY: "Empty",
    _CURVE_TABLE_MODE_SIMPLE: "SimpleCurves",
    _CURVE_TABLE_MODE_RICH: "RichCurves",
}


def parse_curve_table(
    archive: Any,
    name_map: List[str],
) -> Dict[str, Any]:
    """解析 CurveTable 资产元数据。

    CurveTable 与 DataTable 不同，其 Serialize 布局为：
      NumRows (int32) + CurveTableMode (uint8) + N × (FName + curve payload)

    参照 CurveTable.cpp:102-130 UCurveTable::Serialize。

    Args:
        archive: FArchive 实例（已定位到 payload 起始位置）
        name_map: 名称表

    Returns:
        解析结果字典，包含 curve_table_mode、row_count、rows 等
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
        "curve_table_mode": "Empty",
        "curve_table_mode_raw": 0,
        "row_count": 0,
        "rows": [],
    }

    try:
        # 1. NumRows: int32
        #    参照 CurveTable.cpp:112-113 Ar << NumRows
        num_rows = archive.read_i32("NumRows")
        if num_rows < 0:
            result["parse_status"] = "partial"
            result["error"] = f"Invalid row count: {num_rows}"
            return result

        result["row_count"] = num_rows

        # 2. CurveTableMode: uint8
        #    参照 CurveTable.cpp:122-123 Ar << CurveTableMode
        #    旧版本（bUpgradingCurveTable）没有此字段，但当前格式均有
        mode_raw = archive.read_u8("CurveTableMode")
        result["curve_table_mode_raw"] = mode_raw
        result["curve_table_mode"] = _MODE_NAMES.get(mode_raw, f"Unknown({mode_raw})")

        # 3. 逐行解析 RowMap
        #    每行：FName (Index:int32 + Number:int32) + curve payload
        rows: List[Dict[str, Any]] = []

        for row_idx in range(num_rows):
            # FName: Index (int32) + Number (int32)
            name_index = archive.read_i32(f"Row[{row_idx}].FName.Index")
            name_number = archive.read_i32(f"Row[{row_idx}].FName.Number")

            # 解析行名称
            if 0 <= name_index < len(name_map):
                row_name = name_map[name_index]
            else:
                row_name = f"<invalid_index_{name_index}>"

            row: Dict[str, Any] = {
                "name": row_name,
                "name_index": name_index,
                "name_number": name_number,
            }

            # 根据 CurveTableMode 解析曲线数据
            if mode_raw == _CURVE_TABLE_MODE_RICH:
                curve_data = _read_rich_curve(archive, row_idx, name_map)
                row["curve"] = curve_data
            elif mode_raw == _CURVE_TABLE_MODE_SIMPLE:
                # SimpleCurve: 使用 SerializeTaggedProperties 序列化
                # 当前跳过，记录为 opaque payload
                row["curve"] = {"type": "SimpleCurve", "note": "payload skipped"}
            else:
                # Empty 模式不应有行数据，但格式上仍可能有
                row["curve"] = {"type": "Unknown", "mode": mode_raw}

            rows.append(row)

        result["rows"] = rows

    except (struct.error, OSError, ValueError, ParseError) as e:
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result


def _read_rich_curve(archive: Any, row_idx: int, name_map: List[str]) -> Dict[str, Any]:
    """解析 FRichCurve 的 tagged properties 格式。

    FRichCurve 通过 SerializeTaggedProperties 序列化：
    - 每个属性前有 FName（属性名）+ FName（类型名）+ int32（size）+ int32（array_index）
    - 属性名为空 FName 时表示结束
    - Keys 属性包含 TArray<FRichCurveKey>

    参照 UStruct::SerializeTaggedProperties：
    Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp
    """
    keys: List[Dict[str, float]] = []

    try:
        # 循环读取 tagged properties 直到遇到空 FName
        while True:
            # 属性名 FName
            prop_name_index = archive.read_i32(f"Row[{row_idx}].Prop.Name.Index")
            prop_name_number = archive.read_i32(f"Row[{row_idx}].Prop.Name.Number")

            # 空 FName（index=0 且 number=0）表示属性列表结束
            if prop_name_index == 0 and prop_name_number == 0:
                break

            # 类型名 FName
            type_name_index = archive.read_i32(f"Row[{row_idx}].Prop.Type.Index")
            _type_name_number = archive.read_i32(f"Row[{row_idx}].Prop.Type.Number")  # noqa: F841 - protocol read

            # Size: int32
            prop_size = archive.read_i32(f"Row[{row_idx}].Prop.Size")

            # ArrayIndex: int32
            _array_index = archive.read_i32(f"Row[{row_idx}].Prop.ArrayIndex")  # noqa: F841 - protocol read

            if prop_size < 0 or prop_size > archive.total_size():
                return {
                    "type": "RichCurve",
                    "keys": keys,
                    "error": f"Invalid property size: {prop_size}",
                }

            # 读取属性数据
            if prop_size > 0:
                prop_data = archive.read(prop_size)

                prop_name = _resolve_name(prop_name_index, name_map)
                type_name = _resolve_name(type_name_index, name_map)

                # 如果是 TArray 属性且属性名为 "Keys"，解析 FRichCurveKey 数组
                if "ArrayProperty" in type_name and "Keys" in prop_name:
                    # TArray 序列化：int32 count + count × element
                    if len(prop_data) >= 4:
                        arr_count = struct.unpack("<i", prop_data[:4])[0]
                        offset = 4
                        for _ in range(arr_count):
                            # FRichCurveKey: Time(f32) + Value(f32) + ...
                            # 仅提取 Time 和 Value（最小 8 字节）
                            if offset + 8 <= len(prop_data):
                                time_val = struct.unpack("<f", prop_data[offset:offset+4])[0]
                                value_val = struct.unpack("<f", prop_data[offset+4:offset+8])[0]
                                keys.append({"time": time_val, "value": value_val})
                                offset += 8

    except (struct.error, OSError, ValueError, ParseError) as e:
        # 解析失败时返回已解析的部分数据
        logger.debug("RichCurve 解析失败: %s", e, exc_info=True)

    return {"type": "RichCurve", "keys": keys}


def _resolve_name(name_index: int, name_map: List[str]) -> str:
    """从名称表解析名称。"""
    from uasset_read.parsers.utils import resolve_name_from_index
    return resolve_name_from_index(None, name_map, name_index, fallback_prefix="name")
