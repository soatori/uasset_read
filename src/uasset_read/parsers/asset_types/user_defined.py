"""UserDefinedEnum and UserDefinedStruct asset type handler.

Extracts semantic content from UE UserDefinedEnum and UserDefinedStruct exports.
These types use standard UPROPERTY serialization, so we extract the meaningful
fields from the parsed properties.

UE source reference:
- UEnum: Engine/Source/Runtime/CoreUObject/Public/UObject/Class.h
- UStruct: Engine/Source/Runtime/CoreUObject/Public/UObject/Class.h

UEnum exports have:
- Names: TArray<FNamePair> (enum value names)
- CppType: FString (underlying C++ type)

UStruct exports have:
- Properties (tagged properties list)
- StructFlags: uint32
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def extract_user_defined_enum(export: Any, name_map: List[str]) -> Optional[Dict[str, Any]]:
    """Extract semantic data from a UserDefinedEnum export.

    Args:
        export: The parsed ObjectExport with properties
        name_map: The package name table

    Returns:
        Dictionary with enum_name, entries (list of {name, display_name, value}),
        and cpp_type, or None if no meaningful data found.
    """
    properties = getattr(export, "properties", None) or []
    if not properties:
        return None

    enum_entries: List[Dict[str, Any]] = []
    cpp_type = ""
    display_names_map: Dict[int, str] = {}  # name_index -> display_name

    for prop in properties:
        prop_name = getattr(prop, "name", "")
        prop_type = getattr(prop, "type", "")
        prop_value = getattr(prop, "value", None)

        # DisplayNameMap: TMap<FName, FText> - maps enum value names to display names
        # The keys can be name indices (integers) or FName strings
        if prop_name == "DisplayNameMap" and prop_type == "MapProperty":
            if hasattr(prop_value, "entries"):
                for entry in prop_value.entries:
                    if isinstance(entry, dict):
                        key = entry.get("key")
                        value = entry.get("value")
                        if key is not None and value is not None:
                            # key can be int (name index) or str (FName)
                            try:
                                key_idx = int(key)
                            except (ValueError, TypeError):
                                # key is a string FName, try to find its index in name_map
                                key_idx = -1
                                for i, name in enumerate(name_map):
                                    if name == str(key):
                                        key_idx = i
                                        break
                            if key_idx >= 0:
                                display_names_map[key_idx] = str(value) if value else ""

        # CppType: FString - underlying C++ type
        elif prop_name == "CppType" and prop_type == "StrProperty":
            if prop_value is not None:
                cpp_type = str(prop_value)

    # Build enum entries from the name table
    # UserDefinedEnum values are stored in the name table with the pattern:
    # "EnumName::ValueName" and the short name "ValueName"
    object_name = getattr(export, "object_name", "")
    enum_prefix = f"{object_name}::"

    for idx, name in enumerate(name_map):
        if name.startswith(enum_prefix):
            # This is a full enum name like "Enum_PanelType::NewEnumerator0"
            short_name = name[len(enum_prefix):]
            # Skip the MAX entry
            if short_name.endswith("::Enum_MAX") or short_name == "Enum_MAX":
                continue
            # Skip if we already have this entry (from the short name)
            if any(e["name"] == short_name for e in enum_entries):
                continue

            # Get display name from DisplayNameMap if available
            display_name = display_names_map.get(idx, short_name)

            enum_entries.append({
                "name": short_name,
                "display_name": display_name if display_name else short_name,
            })

    if not enum_entries:
        return None

    # Sort entries by their order in the name table for determinism
    enum_entries.sort(key=lambda e: next(
        (i for i, n in enumerate(name_map) if n.endswith(f"::{e['name']}")),
        0
    ))

    return {
        "type": "enum",
        "enum_name": str(object_name),
        "cpp_type": cpp_type,
        "entries": enum_entries,
    }


def extract_user_defined_struct(export: Any, name_map: List[str]) -> Optional[Dict[str, Any]]:
    """Extract semantic data from a UserDefinedStruct export.

    Args:
        export: The parsed ObjectExport with properties
        name_map: The package name table

    Returns:
        Dictionary with struct_name, fields (list of {name, type, default_value}),
        struct_flags, and guid, or None if no meaningful data found.
    """
    properties = getattr(export, "properties", None) or []
    if not properties:
        return None

    struct_fields: List[Dict[str, Any]] = []
    struct_flags = 0
    guid = ""

    for prop in properties:
        prop_name = getattr(prop, "name", "")
        prop_type = getattr(prop, "type", "")
        prop_value = getattr(prop, "value", None)

        # StructFlags: uint32
        if prop_name == "StructFlags" and prop_type == "UInt32Property":
            if prop_value is not None:
                struct_flags = int(prop_value)

        # Guid: FGuid
        elif prop_name == "Guid" and prop_type == "StructProperty":
            if isinstance(prop_value, dict):
                # Try to extract from struct value fields
                fields = prop_value.get("fields", {})
                if isinstance(fields, dict) and all(k in fields for k in ("A", "B", "C", "D")):
                    a = fields.get("A", 0)
                    b = fields.get("B", 0)
                    c = fields.get("C", 0)
                    d = fields.get("D", 0)
                    # Format as standard GUID string: A-B-C-D (8-4-4-4-12)
                    guid = f"{a:08X}-{b:04X}-{c:04X}-{(d >> 16) & 0xFFFF:04X}-{d & 0xFFFF:04X}00000000"
                else:
                    guid = str(prop_value)
            elif hasattr(prop_value, "fields") and isinstance(getattr(prop_value, "fields"), dict):
                # Handle StructValue objects
                fields = prop_value.fields
                if all(k in fields for k in ("A", "B", "C", "D")):
                    a = fields.get("A", 0)
                    b = fields.get("B", 0)
                    c = fields.get("C", 0)
                    d = fields.get("D", 0)
                    guid = f"{a:08X}-{b:04X}-{c:04X}-{(d >> 16) & 0xFFFF:04X}-{d & 0xFFFF:04X}00000000"
                else:
                    guid = str(prop_value)
            elif prop_value is not None:
                guid = str(prop_value)

        # Skip internal UE properties
        elif prop_name in ("DeprecatedData", "EditorOnlyData", "Native"):
            continue

        # Regular user-defined fields (UPROPERTY)
        elif prop_name and prop_type and prop_name not in (
            "None", "ClassDefaultObject", "ClassCDO", "ClassGeneratedBy"
        ):
            field_info: Dict[str, Any] = {
                "name": prop_name,
                "type": prop_type,
            }

            # Extract default value if present
            if prop_value is not None:
                # Don't include complex nested structures as defaults
                if prop_type in (
                    "BoolProperty", "ByteProperty", "IntProperty", "Int8Property",
                    "Int16Property", "Int64Property", "UInt32Property", "UInt64Property",
                    "FloatProperty", "DoubleProperty", "StrProperty", "NameProperty",
                    "TextProperty", "EnumProperty",
                ):
                    field_info["default_value"] = str(prop_value)
                elif prop_type == "ObjectProperty":
                    field_info["default_value"] = str(prop_value) if prop_value else None

            # Extract enum type reference for EnumProperty
            if prop_type == "EnumProperty" and hasattr(prop, "enum_type"):
                enum_type = getattr(prop, "enum_type", None)
                if enum_type:
                    field_info["enum_type"] = str(enum_type)

            # Extract struct type reference for StructProperty
            if prop_type == "StructProperty" and hasattr(prop, "struct_type"):
                struct_type = getattr(prop, "struct_type", None)
                if struct_type:
                    field_info["struct_type"] = str(struct_type)

            struct_fields.append(field_info)

    if not struct_fields:
        return None

    object_name = getattr(export, "object_name", "")
    return {
        "type": "struct",
        "struct_name": str(object_name),
        "struct_flags": struct_flags,
        "guid": guid,
        "fields": struct_fields,
    }


def parse_user_defined(export: Any, archive: Any = None, context: Any = None) -> Dict[str, Any]:
    """Parse UserDefinedEnum or UserDefinedStruct export.

    This is the entry point for the asset type handler registration.
    It delegates to the appropriate extraction function based on the export class.

    Args:
        export: The parsed ObjectExport
        archive: The FArchive (unused for this handler)
        context: Additional context (name_map list)

    Returns:
        Dictionary with extracted data and parse_status
    """
    name_map = context if isinstance(context, list) else []

    # Determine the class type from export
    class_name = getattr(export, "object_class", "") or ""

    # Try to determine type from class name or properties
    if "Enum" in class_name:
        result = extract_user_defined_enum(export, name_map)
    elif "Struct" in class_name:
        result = extract_user_defined_struct(export, name_map)
    else:
        # Try both and use whichever succeeds
        result = extract_user_defined_enum(export, name_map)
        if result is None:
            result = extract_user_defined_struct(export, name_map)

    if result:
        return {
            "user_defined": result,
            "parse_status": "success",
        }
    return {"parse_status": "partial"}
