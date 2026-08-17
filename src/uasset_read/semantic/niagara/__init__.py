"""Niagara semantic JSON domain (#557e)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.niagara.extractor import build_niagara_content
from uasset_read.semantic.validator import register_domain_validator, validate_niagara_document

for _class in ("NiagaraSystem", "NiagaraEmitter", "NiagaraScript"):
    register_extension(
        _class,
        build_niagara_content,
        domain_format="uasset_read.niagara_semantic",
        domain_format_version="1.0.0",
    )
register_domain_validator("uasset_read.niagara_semantic", validate_niagara_document)
