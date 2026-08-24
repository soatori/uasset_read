"""User-Defined types semantic content extractor (#557g).

Dispatches on object_class for UserDefinedEnum and UserDefinedStruct.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _build_enum(asset_type_data: dict, cov) -> dict:
    # Handler may return data nested under "user_defined" key or flat
    ud_data = asset_type_data.get("user_defined", asset_type_data)
    enum_name = ud_data.get("enum_name", "")
    display_name = ud_data.get("display_name", "")
    entries = ud_data.get("entries", [])

    cov.track("enum_data", bool(enum_name) or len(entries) > 0)

    enum_data: dict = {
        "enum_name": enum_name,
        "display_name": display_name,
        "entry_count": len(entries),
        "entries": entries,
    }
    return {"user_defined": {"enum_data": enum_data}}


def _build_struct(asset_type_data: dict, cov) -> dict:
    # Handler may return data nested under "user_defined" key or flat
    ud_data = asset_type_data.get("user_defined", asset_type_data)
    struct_name = ud_data.get("struct_name", "")
    display_name = ud_data.get("display_name", "")
    properties = ud_data.get("properties", [])

    cov.track("struct_data", bool(struct_name) or len(properties) > 0)

    struct_data: dict = {
        "struct_name": struct_name,
        "display_name": display_name,
        "property_count": len(properties),
        "properties": properties,
    }
    return {"user_defined": {"struct_data": struct_data}}


def build_user_defined_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    asset_type_data = getattr(export_ir, "asset_type_data", None)
    object_class = getattr(export_ir, "object_class", "") or ""

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("enum_data", False)
        return {}

    if object_class == "UserDefinedEnum":
        return _build_enum(asset_type_data, coverage_model)
    elif object_class == "UserDefinedStruct":
        return _build_struct(asset_type_data, coverage_model)
    else:
        coverage_model.track("enum_data", False)
        return {}
