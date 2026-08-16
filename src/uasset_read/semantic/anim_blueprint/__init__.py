"""Animation Blueprint semantic JSON domain (#555)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.anim_blueprint.extractor import build_anim_blueprint_content
from uasset_read.semantic.validator import register_domain_validator, validate_anim_blueprint_document

register_extension(
    "AnimBlueprint",
    build_anim_blueprint_content,
    domain_format="uasset_read.anim_blueprint_semantic",
    domain_format_version="1.0.0",
)
register_extension(
    "AnimBlueprintGeneratedClass",
    build_anim_blueprint_content,
    domain_format="uasset_read.anim_blueprint_semantic",
    domain_format_version="1.0.0",
)
register_domain_validator("uasset_read.anim_blueprint_semantic", validate_anim_blueprint_document)
