"""CurveTable Asset type handler

Parse UCurveTable specific data:
- NumRows: int32 — row count
- CurveTableMode: uint8 — curve type (0=Empty, 1=SimpleCurves, 2=RichCurves)
- RowMap: TArray<FName + FRichCurve/FSimpleCurve>

Format reference:
- Engine/Source/Runtime/Engine/Classes/Engine/CurveTable.h
- Engine/Source/Runtime/Engine/Private/CurveTable.cpp
"""

import logging
import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


# ECurveTableMode enum values (CurveTable.h:29-33)
_CURVE_TABLE_MODE_EMPTY = 0
_CURVE_TABLE_MODE_SIMPLE = 1
_CURVE_TABLE_MODE_RICH = 2

_MODE_NAMES = {
    _CURVE_TABLE_MODE_EMPTY: "Empty",
    _CURVE_TABLE_MODE_SIMPLE: "SimpleCurves",
    _CURVE_TABLE_MODE_RICH: "RichCurves",
}

# Row count safety limit (aligned with DataTable, prevent malicious large row counts)
_MAX_ROWS = 100000


def parse_curve_table(
    archive: Any,
    name_map: List[str],
) -> Dict[str, Any]:
    """Parse CurveTable asset metadata.

    CurveTable differs from DataTable; its Serialize layout is:
      NumRows (int32) + CurveTableMode (uint8) + N × (FName + curve payload)

    Reference CurveTable.cpp:102-130 UCurveTable::Serialize.

    Args:
        archive: FArchive instance (positioned at payload start)
        name_map: name table

    Returns:
        Parse result dictionary, containing curve_table_mode, row_count, rows, etc.
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
        #    Reference CurveTable.cpp:112-113 Ar << NumRows
        num_rows = archive.read_i32("NumRows")
        if num_rows < 0:
            result["parse_status"] = "partial"
            result["error"] = f"Invalid row count: {num_rows}"
            return result
        if num_rows > _MAX_ROWS:
            result["parse_status"] = "partial"
            result["error"] = f"Row count {num_rows} exceeds safety limit {_MAX_ROWS}"
            return result

        result["row_count"] = num_rows

        # 2. CurveTableMode: uint8
        #    Reference CurveTable.cpp:122-123 Ar << CurveTableMode
        #    Old versions (bUpgradingCurveTable) lack this field, but current format always has it
        mode_raw = archive.read_u8("CurveTableMode")
        result["curve_table_mode_raw"] = mode_raw
        result["curve_table_mode"] = _MODE_NAMES.get(mode_raw, f"Unknown({mode_raw})")

        # 3. Parse RowMap line by line
        #    Each row: FName (Index:int32 + Number:int32) + curve payload
        rows: List[Dict[str, Any]] = []

        for row_idx in range(num_rows):
            # FName: Index (int32) + Number (int32)
            name_index = archive.read_i32(f"Row[{row_idx}].FName.Index")
            name_number = archive.read_i32(f"Row[{row_idx}].FName.Number")

            # Parse row name
            if 0 <= name_index < len(name_map):
                row_name = name_map[name_index]
            else:
                row_name = f"<invalid_index_{name_index}>"

            row: Dict[str, Any] = {
                "name": row_name,
                "name_index": name_index,
                "name_number": name_number,
            }

            # Parse curve data based on CurveTableMode
            if mode_raw == _CURVE_TABLE_MODE_RICH:
                curve_data = _read_rich_curve(archive, row_idx, name_map)
                row["curve"] = curve_data
            elif mode_raw == _CURVE_TABLE_MODE_SIMPLE:
                # SimpleCurve: uses SerializeTaggedProperties
                # Reference CurveTable.cpp:138-145
                curve_data = _read_simple_curve(archive, row_idx, name_map)
                row["curve"] = curve_data
            else:
                # Empty mode should not have row data, but format may still contain it
                row["curve"] = {"type": "Unknown", "mode": mode_raw}

            rows.append(row)

        result["rows"] = rows

    except (struct.error, OSError, ValueError, ParseError) as e:
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result


def _read_rich_curve(archive: Any, row_idx: int, name_map: List[str]) -> Dict[str, Any]:
    """Parse FRichCurve tagged properties format.

    FRichCurve serialized via SerializeTaggedProperties:
    - Each property preceded by FName (property name) + FName (type name) + int32 (size) + int32 (array_index)
    - and type-related extra fields (InnerTypeName, etc.)
    - Empty FName as property name indicates end
    - Keys property contains TArray<FRichCurveKey>

    Reference UStruct::SerializeTaggedProperties:
    Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp
    FPropertyTag::Serialize
    """
    keys: List[Dict[str, float]] = []

    try:
        # Loop reading tagged properties until an empty FName is encountered
        while True:
            # Property name FName
            prop_name_index = archive.read_i32(f"Row[{row_idx}].Prop.Name.Index")
            prop_name_number = archive.read_i32(f"Row[{row_idx}].Prop.Name.Number")

            # Empty FName (index=0 and number=0) indicates property list end
            if prop_name_index == 0 and prop_name_number == 0:
                break

            # Type name FName
            type_name_index = archive.read_i32(f"Row[{row_idx}].Prop.Type.Index")
            _type_name_number = archive.read_i32(f"Row[{row_idx}].Prop.Type.Number")  # noqa: F841 - protocol read

            # Parse type name (to determine if extra fields need skipping)
            type_name = _resolve_name(type_name_index, name_map)

            # Size: int32
            prop_size = archive.read_i32(f"Row[{row_idx}].Prop.Size")

            # ArrayIndex: int32
            _array_index = archive.read_i32(f"Row[{row_idx}].Prop.ArrayIndex")  # noqa: F841 - protocol read

            # EnumName: FName (EnumProperty or ByteProperty specific field)
            if type_name in ("EnumProperty", "ByteProperty"):
                archive.read_i32()  # index
                archive.read_i32()  # number

            # InnerTypeName: FName (ArrayProperty or SetProperty)
            if type_name in ("ArrayProperty", "SetProperty"):
                archive.read_i32()  # index
                archive.read_i32()  # number

            # KeyType + ValueType: 2 x FName (MapProperty)
            if type_name == "MapProperty":
                archive.read_i32()  # key type index
                archive.read_i32()  # key type number
                archive.read_i32()  # value type index
                archive.read_i32()  # value type number

            # PropertyGuid: bool(i32) + optional FGuid(16)
            has_guid = archive.read_i32()
            if has_guid != 0:
                archive.read_bytes(16)

            if prop_size < 0 or prop_size > archive.total_size():
                return {
                    "type": "RichCurve",
                    "keys": keys,
                    "error": f"Invalid property size: {prop_size}",
                }

            # Read property data
            if prop_size > 0:
                prop_data = archive.read(prop_size)

                prop_name = _resolve_name(prop_name_index, name_map)

                # If TArray property named "Keys", parse the FRichCurveKey array
                if "ArrayProperty" in type_name and "Keys" in prop_name:
                    # FRichCurveKey full layout (RichCurve.h:80-118):
                    # InterpMode: u8 (1)
                    # TangentMode: u8 (1)
                    # TangentWeightMode: u8 (1)
                    # Time: f32 (4)
                    # Value: f32 (4)
                    # ArriveTangent: f32 (4)
                    # ArriveTangentWeight: f32 (4)
                    # LeaveTangent: f32 (4)
                    # LeaveTangentWeight: f32 (4)
                    # Total 27 bytes per key
                    FRICH_CURVE_KEY_SIZE = 27
                    if len(prop_data) >= 4:
                        arr_count = struct.unpack("<i", prop_data[:4])[0]
                        offset = 4
                        for _ in range(arr_count):
                            if offset + FRICH_CURVE_KEY_SIZE <= len(prop_data):
                                interp_mode = struct.unpack_from("<B", prop_data, offset)[0]
                                tangent_mode = struct.unpack_from("<B", prop_data, offset + 1)[0]
                                tangent_weight_mode = struct.unpack_from("<B", prop_data, offset + 2)[0]
                                time_val = struct.unpack_from("<f", prop_data, offset + 3)[0]
                                value_val = struct.unpack_from("<f", prop_data, offset + 7)[0]
                                arrive_tangent = struct.unpack_from("<f", prop_data, offset + 11)[0]
                                arrive_tangent_weight = struct.unpack_from("<f", prop_data, offset + 15)[0]
                                leave_tangent = struct.unpack_from("<f", prop_data, offset + 19)[0]
                                leave_tangent_weight = struct.unpack_from("<f", prop_data, offset + 23)[0]
                                keys.append({
                                    "time": time_val,
                                    "value": value_val,
                                    "interp_mode": interp_mode,
                                    "tangent_mode": tangent_mode,
                                    "tangent_weight_mode": tangent_weight_mode,
                                    "arrive_tangent": arrive_tangent,
                                    "arrive_tangent_weight": arrive_tangent_weight,
                                    "leave_tangent": leave_tangent,
                                    "leave_tangent_weight": leave_tangent_weight,
                                })
                                offset += FRICH_CURVE_KEY_SIZE

    except (struct.error, OSError, ValueError, ParseError) as e:
        # Return partially parsed data on parse failure
        logger.warning("RichCurve parse failed: %s", e, exc_info=True)

    return {"type": "RichCurve", "keys": keys}


def _read_simple_curve(archive: Any, row_idx: int, name_map: List[str]) -> Dict[str, Any]:
    """Parse FSimpleCurve tagged properties format.

    FSimpleCurve serialized via SerializeTaggedProperties (CurveTable.cpp:138-145):
    - InterpMode: EnumProperty tagged property (TEnumAsByte<ERichCurveInterpMode>)
    - Keys: ArrayProperty tagged property (TArray<FSimpleCurveKey>)
    - FSimpleCurveKey: Time(f32) + Value(f32) = 8 bytes (custom serialization, SimpleCurve.cpp:10-18)

    Reference UStruct::SerializeTaggedProperties:
    Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp
    FPropertyTag::Serialize
    """
    interp_mode: int = 0  # Default RCIM_Linear
    keys: List[Dict[str, float]] = []

    try:
        # Loop reading tagged properties until an empty FName is encountered
        while True:
            # Property name FName
            prop_name_index = archive.read_i32(f"Row[{row_idx}].Prop.Name.Index")
            prop_name_number = archive.read_i32(f"Row[{row_idx}].Prop.Name.Number")

            # Empty FName (index=0 and number=0) indicates property list end
            if prop_name_index == 0 and prop_name_number == 0:
                break

            # Type name FName
            type_name_index = archive.read_i32(f"Row[{row_idx}].Prop.Type.Index")
            _type_name_number = archive.read_i32(f"Row[{row_idx}].Prop.Type.Number")  # noqa: F841 - protocol read

            # Parse type name (to determine if extra fields need skipping)
            type_name = _resolve_name(type_name_index, name_map)

            # Size: int32
            prop_size = archive.read_i32(f"Row[{row_idx}].Prop.Size")

            # ArrayIndex: int32
            _array_index = archive.read_i32(f"Row[{row_idx}].Prop.ArrayIndex")  # noqa: F841 - protocol read

            # EnumName: FName (EnumProperty or ByteProperty specific field)
            if type_name in ("EnumProperty", "ByteProperty"):
                archive.read_i32()  # index
                archive.read_i32()  # number

            # InnerTypeName: FName (ArrayProperty or SetProperty)
            if type_name in ("ArrayProperty", "SetProperty"):
                archive.read_i32()  # index
                archive.read_i32()  # number

            # KeyType + ValueType: 2 x FName (MapProperty)
            if type_name == "MapProperty":
                archive.read_i32()  # key type index
                archive.read_i32()  # key type number
                archive.read_i32()  # value type index
                archive.read_i32()  # value type number

            # PropertyGuid: bool(i32) + optional FGuid(16)
            has_guid = archive.read_i32()
            if has_guid != 0:
                archive.read_bytes(16)

            if prop_size < 0 or prop_size > archive.total_size():
                return {
                    "type": "SimpleCurve",
                    "interp_mode": interp_mode,
                    "keys": keys,
                    "error": f"Invalid property size: {prop_size}",
                }

            # Read property data
            if prop_size > 0:
                prop_data = archive.read(prop_size)

                prop_name = _resolve_name(prop_name_index, name_map)

                # EnumProperty: InterpMode (FSimpleCurve UPROPERTY)
                if "EnumProperty" in type_name and "InterpMode" in prop_name:
                    # Enum value stored as u8 in property data
                    if len(prop_data) >= 1:
                        interp_mode = struct.unpack_from("<B", prop_data, 0)[0]

                # ArrayProperty: Keys (FSimpleCurveKey array)
                # FSimpleCurveKey uses custom serialization (SimpleCurve.cpp:10-18):
                # Time(f32) + Value(f32) = 8 bytes per key
                if "ArrayProperty" in type_name and "Keys" in prop_name:
                    SIMPLE_CURVE_KEY_SIZE = 8
                    if len(prop_data) >= 4:
                        arr_count = struct.unpack("<i", prop_data[:4])[0]
                        offset = 4
                        for _ in range(arr_count):
                            if offset + SIMPLE_CURVE_KEY_SIZE <= len(prop_data):
                                time_val = struct.unpack_from("<f", prop_data, offset)[0]
                                value_val = struct.unpack_from("<f", prop_data, offset + 4)[0]
                                keys.append({"time": time_val, "value": value_val})
                                offset += SIMPLE_CURVE_KEY_SIZE

    except (struct.error, OSError, ValueError, ParseError) as e:
        # Return partially parsed data on parse failure
        logger.warning("SimpleCurve parse failed: %s", e, exc_info=True)

    return {"type": "SimpleCurve", "interp_mode": interp_mode, "keys": keys}


def _resolve_name(name_index: int, name_map: List[str]) -> str:
    """Parse name from name table."""
    from uasset_read.parsers.utils import resolve_name_from_index
    return resolve_name_from_index(None, name_map, name_index, fallback_prefix="name")
