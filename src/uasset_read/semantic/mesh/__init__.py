"""Mesh semantic JSON domain (#557a)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.mesh.extractor import build_mesh_content
from uasset_read.semantic.validator import register_domain_validator, validate_mesh_document

for _class in ("StaticMesh", "SkeletalMesh"):
    register_extension(
        _class,
        build_mesh_content,
        domain_format="uasset_read.mesh_semantic",
        domain_format_version="1.0.0",
    )
register_domain_validator("uasset_read.mesh_semantic", validate_mesh_document)
