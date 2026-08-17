"""Skeleton semantic JSON domain (#557)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.skeleton.extractor import build_skeleton_content
from uasset_read.semantic.validator import register_domain_validator, validate_skeleton_document

register_extension(
    "Skeleton",
    build_skeleton_content,
    domain_format="uasset_read.skeleton_semantic",
    domain_format_version="1.0.0",
)
register_domain_validator("uasset_read.skeleton_semantic", validate_skeleton_document)
