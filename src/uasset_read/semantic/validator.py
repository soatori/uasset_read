"""Semantic document validator — lightweight structural and cross-ref checks.

Called in production before rendering. Does NOT perform JSON Schema validation
(that is test-only via jsonschema).
"""
from __future__ import annotations

import re as _re

from uasset_read.semantic.models import SemanticIR

_VALID_MODES = {"standard", "debug"}
_VALID_PARSES = {"complete", "partial", "failed"}
_VALID_REPRESENTATIONS = {"full", "partial", "opaque"}
_VALID_SEVERITIES = {"error", "warning", "info"}

_FORMAT_VERSIONS = {
    "uasset_read.asset_semantic": "1.0",
    "uasset_read.blueprint_semantic": "1.0.0",
}

_DOMAIN_VALIDATORS: dict[str, object] = {}


def register_domain_validator(fmt: str, validator) -> None:
    """Register a format-specific semantic validator."""
    _DOMAIN_VALIDATORS[fmt] = validator


def validate_semantic_document(ir: SemanticIR) -> list[str]:
    """Validate a SemanticIR against the public contract.

    Returns:
        List of error messages (empty = valid).
    """
    errors: list[str] = []

    expected_version = _FORMAT_VERSIONS.get(ir.format)
    if expected_version is None:
        errors.append(f"Invalid format: '{ir.format}' is not a known semantic format")
    elif ir.format_version != expected_version:
        errors.append(
            f"Invalid format_version for '{ir.format}': expected '{expected_version}', got '{ir.format_version}'")

    if ir.mode not in _VALID_MODES:
        errors.append(f"Invalid mode: expected one of {_VALID_MODES}, got '{ir.mode}'")

    if not ir.asset.name:
        errors.append("asset.name must not be empty")

    if not ir.asset.package:
        errors.append("asset.package must not be empty")

    if ir.status.parse not in _VALID_PARSES:
        errors.append(f"Invalid status.parse: expected one of {_VALID_PARSES}, got '{ir.status.parse}'")

    if ir.status.representation not in _VALID_REPRESENTATIONS:
        errors.append(f"Invalid status.representation: expected one of {_VALID_REPRESENTATIONS}, got '{ir.status.representation}'")

    if ir.mode == "standard" and ir.evidence:
        errors.append("Standard mode must not contain evidence entries")

    if ir.status.representation == "full" and ir.coverage is not None:
        if ir.coverage.scopes_available < ir.coverage.scopes_expected:
            errors.append(
                f"representation='full' but coverage is {ir.coverage.scopes_available}/{ir.coverage.scopes_expected}"
            )

    for diag in ir.diagnostics:
        if diag.severity not in _VALID_SEVERITIES:
            errors.append(f"Invalid diagnostic severity: '{diag.severity}'")

    # Reference index uniqueness (within kind)
    seen_refs: set[tuple[str, int]] = set()
    for ref in ir.references:
        key = (ref.kind, ref.index)
        if key in seen_refs:
            errors.append(f"Reference index not unique: kind={ref.kind}, index={ref.index}")
        seen_refs.add(key)

    # Opaque representation must have at least one diagnostic
    if ir.status.representation == "opaque" and not ir.diagnostics and ir.format == "uasset_read.asset_semantic":
        errors.append("Opaque representation must have at least one diagnostic")

    domain_validator = _DOMAIN_VALIDATORS.get(ir.format)
    if domain_validator is not None:
        errors.extend(domain_validator(ir))

    return errors
