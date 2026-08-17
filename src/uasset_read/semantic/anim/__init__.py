"""Animation semantic JSON domain (#557f)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.anim.extractor import build_anim_content
from uasset_read.semantic.validator import register_domain_validator, validate_anim_document

for _class in ("AnimSequence", "AnimMontage", "PoseAsset", "AnimCurveCompressionSettings"):
    register_extension(
        _class,
        build_anim_content,
        domain_format="uasset_read.anim_semantic",
        domain_format_version="1.0.0",
    )
register_domain_validator("uasset_read.anim_semantic", validate_anim_document)
