"""Semantic IR builder — the single semantic-projection boundary.

Orchestrates: main-asset selection, reference normalization, coverage/diagnostics.
Does NOT perform standard/debug projection (that is project_semantic's job).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.models import (
    SemanticIR, AssetMeta, AssetStatus, EvidenceEntry,
)
from uasset_read.semantic.kinds import resolve_asset_type
from uasset_read.semantic.references import collect_references
from uasset_read.semantic.coverage import CoverageModel
from uasset_read.semantic.diagnostics import DiagnosticAggregator
from uasset_read.semantic.extensions import get_extractor

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _select_primary_export(package_ir: PackageIR) -> ExportIR | None:
    """Select the primary export using deterministic rules.

    1. Prefer the single export marked with ``b_is_asset``.
    2. Fallback: single top-level export whose name matches package basename.
    3. Otherwise: ``None`` (opaque/partial).

    Do NOT guess when there are multiple candidates, no candidates,
    or insufficient evidence.
    """
    # Rule 1: b_is_asset
    candidates = [e for e in package_ir.exports if getattr(e, "b_is_asset", False)]
    if len(candidates) == 1:
        return candidates[0]

    # Rule 2: name matches package basename
    basename = package_ir.header.package_name.rsplit("/", 1)[-1] if package_ir.header.package_name else ""
    if basename:
        name_matches = [e for e in package_ir.exports if e.object_name == basename]
        if len(name_matches) == 1:
            return name_matches[0]

    return None


def build_semantic_ir(package_ir: PackageIR) -> SemanticIR:
    """Build a mode-independent SemanticIR from PackageIR.

    This is the single semantic-projection boundary. It does NOT perform
    standard/debug pruning — use ``project_semantic()`` for that.
    The returned IR always has ``mode="standard"`` as a placeholder;
    ``project_semantic()`` stamps the actual target mode.

    Args:
        package_ir: PackageIR from ir_builder

    Returns:
        SemanticIR ready for projection and rendering
    """
    diag = DiagnosticAggregator()
    if package_ir.diagnostics_data:
        diag.from_ir(package_ir.diagnostics_data)

    primary = _select_primary_export(package_ir)

    if primary is None:
        diag.add("warning", "NO_EXPORTS", "No suitable primary export found")
        return SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0",
            mode="",
            asset_type="unknown",
            asset=AssetMeta(package=package_ir.header.package_name or "", name="unknown"),
            status=AssetStatus(parse="failed", representation="opaque"),
            references=collect_references(package_ir.imports, package_ir.exports),
            diagnostics=diag.build(),
        )

    # Resolve asset type
    asset_type = resolve_asset_type(primary.object_class or "")

    # Build status
    parse_status = primary.parse_status or "success"
    parse_map = {"success": "complete", "partial": "partial", "partial_metadata": "partial", "failed": "failed", "opaque": "partial"}
    representation_map = {"success": "full", "partial": "partial", "partial_metadata": "partial", "failed": "opaque", "opaque": "opaque"}

    # Unknown type -> opaque representation + evidence with raw class
    evidence: list = []
    if asset_type == "unknown":
        representation = "opaque"
        diag.add("info", "UNKNOWN_TYPE", f"Unresolved asset type for class '{primary.object_class}'")
        # Preserve exact UE class in evidence when normalized type is insufficient
        evidence.append(EvidenceEntry(key="asset_class", value=primary.object_class or ""))
    else:
        representation = representation_map.get(parse_status, "opaque")

    status = AssetStatus(
        parse=parse_map.get(parse_status, "partial"),
        representation=representation,
    )

    # Inject diagnostics for partial/failed
    if status.parse == "partial" and not any(d.code == "PARTIAL_PARSE" for d in diag.build()):
        diag.add("warning", "PARTIAL_PARSE", f"Asset '{primary.object_name}' was only partially parsed")
    elif status.parse == "failed" and not any(d.code == "PARSE_FAILED" for d in diag.build()):
        diag.add("error", "PARSE_FAILED", f"Asset '{primary.object_name}' failed to parse")

    # Coverage + Domain Content
    cov = CoverageModel()
    content: dict = {}
    evidence_list: list = list(evidence)

    extractor = get_extractor(primary.object_class or "")
    if extractor is not None and status.representation != "opaque":
        # Domain extractor populates content and tracks its own coverage scopes
        content = extractor(primary, cov, evidence_list)
    else:
        # No extractor or opaque — track domain_content as unavailable
        cov.track("domain_content", False)

    coverage = cov.build()

    # References
    references = collect_references(package_ir.imports, package_ir.exports)

    return SemanticIR(
        format="uasset_read.asset_semantic",
        format_version="1.0",
        mode="",
        asset_type=asset_type,
        asset=AssetMeta(
            package=package_ir.header.package_name or "",
            name=primary.object_name or "unknown",
            generated_class=primary.object_class if asset_type == "unknown" else None,
        ),
        status=status,
        references=references,
        content=content,
        coverage=coverage,
        diagnostics=diag.build(),
        evidence=tuple(evidence_list),
    )
