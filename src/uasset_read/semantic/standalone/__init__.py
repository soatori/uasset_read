"""Standalone types semantic JSON domain (#557h)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.standalone.extractor import build_standalone_content
from uasset_read.semantic.validator import register_domain_validator, validate_standalone_document

for _class in ("SubsurfaceProfile", "CurveFloat", "CurveLinearColor", "CurveVector",
               "FoliageType", "FoliageType_InstancedStaticMesh"):
    register_extension(
        _class,
        build_standalone_content,
        domain_format="uasset_read.standalone_semantic",
        domain_format_version="1.0.0",
    )
register_domain_validator("uasset_read.standalone_semantic", validate_standalone_document)
