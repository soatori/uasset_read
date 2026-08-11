"""Semantic IR validator — checks public JSON contract constraints.

This module provides external validation for SemanticIR instances.
It is NOT called automatically in the render pipeline — callers should
invoke validate_semantic_ir() explicitly when they need contract validation.

Usage:
    from uasset_read.semantic.validator import validate_semantic_ir
    errors = validate_semantic_ir(semantic_ir)
    if errors:
        raise ValueError(f"Invalid SemanticIR: {errors}")
"""
from __future__ import annotations

from uasset_read.semantic.ir import SemanticIR

_VALID_MODES = {"standard", "debug"}
_VALID_SEVERITIES = {"error", "warning", "info"}


def validate_semantic_ir(ir: SemanticIR) -> list[str]:
    """Validate a SemanticIR against the public JSON contract.

    Args:
        ir: SemanticIR to validate

    Returns:
        List of validation error messages (empty = valid)
    """
    errors: list[str] = []

    # Format
    if ir.format != "uasset_read.asset_semantic":
        errors.append(f"Invalid format: expected 'uasset_read.asset_semantic', got '{ir.format}'")

    # Version
    if ir.format_version != "1.0.0":
        errors.append(f"Invalid format_version: expected '1.0.0', got '{ir.format_version}'")

    # Mode
    if ir.mode not in _VALID_MODES:
        errors.append(f"Invalid mode: expected one of {_VALID_MODES}, got '{ir.mode}'")

    # Asset
    if not ir.asset.class_name:
        errors.append("asset.class_name must not be empty")

    # Coverage
    if ir.coverage.coverage_pct < 0 or ir.coverage.coverage_pct > 100:
        errors.append(f"coverage.coverage_pct must be 0-100, got {ir.coverage.coverage_pct}")

    # Diagnostics
    for diag in ir.diagnostics:
        if diag.severity not in _VALID_SEVERITIES:
            errors.append(f"Invalid diagnostic severity: '{diag.severity}'")

    return errors
