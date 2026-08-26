"""Texture semantic JSON domain (#557b)."""

from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.texture.extractor import build_texture_content
from uasset_read.semantic.validator import register_domain_validator, validate_texture_document

for _class in (
    "Texture2D",
    "TextureCube",
    "TextureRenderTarget2D",
    "TextureRenderTargetCube",
    "Texture2DArray",
    "VolumeTexture",
):
    register_extension(
        _class,
        build_texture_content,
        domain_format="uasset_read.texture_semantic",
        domain_format_version="1.0.0",
    )
register_domain_validator("uasset_read.texture_semantic", validate_texture_document)
