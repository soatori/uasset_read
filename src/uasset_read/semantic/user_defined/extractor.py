"""User-Defined types semantic content extractor (#557g).

Dispatches on object_class for UserDefinedEnum and UserDefinedStruct.
"""

from __future__ import annotations

from uasset_read.semantic.asset_data import class_extractor


def _build_enum(data: dict, cov, _object_class: str) -> dict:
    # Handler may return data nested under "user_defined" key or flat
    ud_data = data.get("user_defined", data)
    enum_name = ud_data.get("enum_name", "")
    entries = ud_data.get("entries", [])

    cov.track("enum_data", bool(enum_name) or len(entries) > 0)

    enum_data: dict = {
        "enum_name": enum_name,
        "display_name": ud_data.get("display_name", ""),
        "entry_count": len(entries),
        "entries": entries,
    }
    return {"user_defined": {"enum_data": enum_data}}


def _build_struct(data: dict, cov, _object_class: str) -> dict:
    # Handler may return data nested under "user_defined" key or flat
    ud_data = data.get("user_defined", data)
    struct_name = ud_data.get("struct_name", "")
    properties = ud_data.get("properties", [])

    cov.track("struct_data", bool(struct_name) or len(properties) > 0)

    struct_data: dict = {
        "struct_name": struct_name,
        "display_name": ud_data.get("display_name", ""),
        "property_count": len(properties),
        "properties": properties,
    }
    return {"user_defined": {"struct_data": struct_data}}


build_user_defined_content = class_extractor(
    "user_defined",
    {"UserDefinedEnum": _build_enum, "UserDefinedStruct": _build_struct},
    miss_cov="enum_data",
)
