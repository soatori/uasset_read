"""Centralized status computation module — unified status derivation for ParseResult / LinkerParseResult / PackageIR.

All statuses use success | partial | failed; legacy fail/error is prohibited.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .fallback import ExportParseStatus

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


# Partial status set: auto-generated from ExportParseStatus.is_partial
# Fully covers all partial variants, ensuring consistent status determination (#315)
PARTIAL_STATUSES: frozenset[str] = frozenset(
    s.value for s in ExportParseStatus if s.is_partial
)

# Failed status set: auto-generated from ExportParseStatus.is_failed
FAILED_STATUSES: frozenset[str] = frozenset(
    s.value for s in ExportParseStatus if s.is_failed
)


def _result_status(result: "ParseResult | LinkerParseResult") -> str:
    """Unified status computation — shared by ParseResult / LinkerParseResult / PackageIR.

    Status rules:
    - failed: all exports are failed, or no core data and is_success=False
    - partial: any export is partial / has errors / has structural diagnostics / lightweight tolerant parsing
    - success: no errors and all exports succeeded

    Check order: export-level status > non-success branch > is_success=True branch

    Args:
        result: ParseResult or LinkerParseResult instance

    Returns:
        "success" | "partial" | "failed"
    """
    # 1. Check export-level status (highest priority)
    export_map = getattr(result, "export_map", None) or []
    if export_map and isinstance(export_map, list):
        failed_count = 0
        partial_count = 0
        for exp in export_map:
            status = getattr(exp, "parse_status", None)
            if status in FAILED_STATUSES:
                failed_count += 1
            elif status in PARTIAL_STATUSES:
                partial_count += 1
        # All exports failed -> overall failed
        if failed_count == len(export_map):
            return "failed"
        # Any partial or present failed (not all failed) -> overall partial
        if failed_count > 0 or partial_count > 0:
            return "partial"

    # 2. Non-success branch: check if core data exists
    if not getattr(result, "is_success", False):
        if (
            getattr(result, "summary", None) is not None
            or getattr(result, "name_map", None)
            or getattr(result, "import_map", None)
            or getattr(result, "export_map", None)
        ):
            return "partial"
        return "failed"

    # 3. is_success=True branch: comprehensive check
    # 3.1 Check errors
    if getattr(result, "errors", None):
        return "partial"

    # 3.2 Check warning-based degradation (corruption / data-skip)
    warnings = getattr(result, "warnings", None) or []
    if any("AssetRegistryData is corrupted" in w for w in warnings):
        return "partial"
    if any("DependsMap" in w for w in warnings):
        return "partial"

    # 3.3 Check lightweight tolerant parsing
    metadata = getattr(result, "metadata", None) or {}
    if metadata.get("lightweight_tolerant_parse"):
        return "partial"

    # 3.3 Check structural diagnostics
    # Note: all OffsetRangeDiagnostic currently use WARNING severity,
    # is_structural() always returns False. This path is defensively retained.
    # If ERROR/CRITICAL severity diagnostics are introduced in the future, sync with ir_builder.py message branch.
    diagnostics = getattr(result, "diagnostics", None) or []
    has_structural_diagnostic = any(
        getattr(d, "is_structural", lambda: False)()
        for d in diagnostics
        if hasattr(d, "is_structural")
    )
    if has_structural_diagnostic:
        return "partial"

    # 3.4 Check heuristic recovery (from decompiled functions)
    decompiled_functions = getattr(result, "decompiled_functions", None) or []
    for func in decompiled_functions:
        fallback_reasons = getattr(func, "fallback_reasons", None) or []
        if "serial_scan_recovery" in fallback_reasons:
            return "partial"

    # 3.5 Check native function status (failed/partial translation)
    for func in decompiled_functions:
        bytecode_status = getattr(func, "bytecode_status", "unknown")
        translation_status = getattr(func, "translation_status", "not_applicable")
        if bytecode_status == "failed":
            return "partial"
        if bytecode_status == "parsed" and translation_status in ("partial", "failed"):
            return "partial"

    return "success"
