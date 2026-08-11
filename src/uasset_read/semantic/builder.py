"""Semantic IR builder -- orchestrates classifier, domain extractor, and IR assembly.

This is the main entry point for building a SemanticIR from PackageIR.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.kinds import AssetKind, classify_asset
from uasset_read.semantic.ir import (
    SemanticIR, AssetMeta, ContentNode, CoverageInfo,
)
from uasset_read.semantic.references import ReferenceTable
from uasset_read.semantic.coverage import CoverageModel
from uasset_read.semantic.diagnostics import DiagnosticAggregator
from uasset_read.semantic.graph_domain import extract_graph
from uasset_read.semantic.structured_domain import extract_structured
from uasset_read.semantic.resource_domain import extract_resource

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def _extract_content(export: ExportIR, kind: AssetKind) -> ContentNode:
    """Route to the appropriate domain extractor based on kind."""
    if kind == AssetKind.GRAPH:
        return extract_graph(export)
    if kind == AssetKind.STRUCTURED:
        return extract_structured(export)
    if kind == AssetKind.RESOURCE:
        return extract_resource(export)
    # Opaque -- minimal metadata
    return ContentNode(key="root", children=(
        ContentNode(key="class_name", value=export.object_class),
        ContentNode(key="object_name", value=export.object_name),
        ContentNode(key="serial_size", value=export.serial_size),
        ContentNode(key="parse_status", value=export.parse_status or "opaque"),
    ))


def build_semantic_ir(package_ir: PackageIR, mode: str = "standard") -> SemanticIR:
    """Build a SemanticIR from PackageIR.

    Args:
        package_ir: PackageIR from ir_builder
        mode: "standard" or "debug"

    Returns:
        SemanticIR ready for rendering
    """
    # Pick the primary export (first non-Blueprint export, or first export)
    primary_export: ExportIR | None = None
    for export in package_ir.exports:
        # Skip Blueprint exports (#551 handles these)
        if export.object_class and (
            export.object_class.endswith("_C")
            or export.object_class in ("BlueprintGeneratedClass", "AnimBlueprintGeneratedClass")
        ):
            continue
        primary_export = export
        break

    if primary_export is None and package_ir.exports:
        primary_export = package_ir.exports[0]

    if primary_export is None:
        # No exports -- return opaque
        return SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0.0",
            mode=mode,
            asset=AssetMeta(
                kind=AssetKind.OPAQUE,
                class_name="Unknown",
                object_name="Unknown",
            ),
            references=(),
            content=ContentNode(key="root", children=()),
            coverage=CoverageInfo(fields_expected=0, fields_parsed=0, coverage_pct=0.0, unparsed_fields=()),
            diagnostics=(),
        )

    # Classify
    kind = classify_asset(primary_export.object_class, primary_export.asset_type_data)

    # Build references
    ref_table = ReferenceTable()
    references = ref_table.collect(package_ir.imports, package_ir.exports)

    # Extract content
    content = _extract_content(primary_export, kind)

    # Build coverage
    coverage_model = CoverageModel()
    if primary_export.asset_type_data:
        atd = primary_export.asset_type_data
        fields_expected = len(atd)
        fields_parsed = sum(1 for v in atd.values() if v is not None)
        unparsed = [k for k, v in atd.items() if v is None]
        coverage_model.track(fields_expected, fields_parsed, unparsed)
    else:
        # Minimal coverage for opaque
        coverage_model.track(3, 3, [])

    # Collect diagnostics
    diag_agg = DiagnosticAggregator()
    if package_ir.diagnostics_data:
        diag_agg.from_ir(package_ir.diagnostics_data)

    # Asset meta
    asset_meta = AssetMeta(
        kind=kind,
        class_name=primary_export.object_class or "Unknown",
        object_name=primary_export.object_name or "Unknown",
        parse_status=primary_export.parse_status or "success",
    )

    return SemanticIR(
        format="uasset_read.asset_semantic",
        format_version="1.0.0",
        mode=mode,
        asset=asset_meta,
        references=references,
        content=content,
        coverage=coverage_model.build(),
        diagnostics=diag_agg.build(),
    )
