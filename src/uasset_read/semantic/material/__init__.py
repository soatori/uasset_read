"""Material semantic JSON domain (#556)."""

from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.material.extractor import build_material_content
from uasset_read.semantic.validator import register_domain_validator, validate_material_document

register_extension(
    "Material",
    build_material_content,
    domain_format="uasset_read.material_semantic",
    domain_format_version="1.0.0",
)
register_extension(
    "MaterialInstanceConstant",
    build_material_content,
    domain_format="uasset_read.material_semantic",
    domain_format_version="1.0.0",
)
register_extension(
    "MaterialInstance",
    build_material_content,
    domain_format="uasset_read.material_semantic",
    domain_format_version="1.0.0",
)
register_domain_validator("uasset_read.material_semantic", validate_material_document)
