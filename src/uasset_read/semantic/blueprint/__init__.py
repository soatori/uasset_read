"""Blueprint semantic JSON domain (#554)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.blueprint.extractor import build_blueprint_content

register_extension(
    "Blueprint",
    build_blueprint_content,
    domain_format="uasset_read.blueprint_semantic",
    domain_format_version="1.0.0",
)
register_extension(
    "BlueprintGeneratedClass",
    build_blueprint_content,
    domain_format="uasset_read.blueprint_semantic",
    domain_format_version="1.0.0",
)
