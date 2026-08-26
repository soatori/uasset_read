"""Material semantic content orchestrator (#556)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def build_material_content(package_ir: "PackageIR", export_ir: "ExportIR", coverage_model, evidence_list) -> dict:
    """Build the Material domain content dict."""
    # Material data comes from PackageIR.material (built by _build_material_ir)
    material_ir = getattr(package_ir, "material", None)

    if material_ir is None:
        coverage_model.track("material_data", False)
        return {}

    coverage_model.track("material_data", True)

    material_dict = _material_to_dict(material_ir)

    coverage_model.track("expressions", bool(material_ir.expressions))
    coverage_model.track("material_inputs", bool(material_ir.material_inputs))
    coverage_model.track("data_flow", bool(material_ir.data_flow))

    content: dict = {
        "material": material_dict,
    }
    return content


def _material_to_dict(material) -> dict:
    """Convert MaterialIR to a semantic dict with explicit structure."""
    from dataclasses import asdict

    material_dict = asdict(material)

    # Extract top-level semantic fields
    result: dict = {
        "material_type": material_dict["material_type"],
    }

    # Promote key properties from properties dict
    props = material_dict.get("properties", {})
    if props:
        semantic_props: dict = {}
        for key in ("domain", "blend_mode", "shading_model", "usage_flags"):
            if key in props:
                semantic_props[key] = props[key]
        if semantic_props:
            result["properties"] = semantic_props

    # Emit expressions as list of dicts
    expressions = material_dict.get("expressions", [])
    if expressions:
        result["expressions"] = expressions

    # Emit material_inputs as list of dicts
    material_inputs = material_dict.get("material_inputs", [])
    if material_inputs:
        result["material_inputs"] = material_inputs

    # Emit data_flow if present
    data_flow = material_dict.get("data_flow", [])
    if data_flow:
        result["data_flow"] = data_flow

    # Emit parameters if present
    parameters = material_dict.get("parameters")
    if parameters:
        result["parameters"] = parameters

    # Emit base_property_overrides if present
    base_overrides = material_dict.get("base_property_overrides")
    if base_overrides:
        result["base_property_overrides"] = base_overrides

    # Emit parent if present
    parent = material_dict.get("parent")
    if parent:
        result["parent"] = parent

    return result
