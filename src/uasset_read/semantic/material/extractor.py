"""Material semantic content orchestrator (#556)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def build_material_content(package_ir: "PackageIR", export_ir: "ExportIR",
                            coverage_model, evidence_list) -> dict:
    """Build the Material domain content dict."""
    # Material data comes from PackageIR.material (built by _build_material_ir)
    material_ir = getattr(package_ir, "material", None)

    if material_ir is None:
        coverage_model.track("material_data", False)
        return {}

    coverage_model.track("material_data", True)
    coverage_model.track("expressions", bool(material_ir.expressions))
    coverage_model.track("material_inputs", bool(material_ir.material_inputs))
    coverage_model.track("data_flow", bool(material_ir.data_flow))

    content: dict = {
        "material": _material_to_dict(material_ir),
        "references": [],  # material format omits the raw import/export table
        "diagnostics": [],
    }
    return content


def _material_to_dict(material) -> dict:
    """Convert MaterialIR to dict."""
    from dataclasses import asdict
    return asdict(material)
