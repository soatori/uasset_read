"""Shared fixtures for semantic JSON tests."""
from __future__ import annotations

import pytest

from uasset_read.semantic.ir import (
    SemanticIR, AssetMeta, CoverageInfo, ContentNode,
)
from uasset_read.semantic.kinds import AssetKind
from uasset_read.models.ir import (
    PackageIR, PackageHeaderIR, ExportIR,
    DiagnosticsDataIR, LinkerSummaryIR,
)


def make_ir(mode: str = "standard", **kwargs) -> SemanticIR:
    """Build a minimal SemanticIR for testing."""
    defaults = dict(
        format="uasset_read.asset_semantic",
        format_version="1.0.0",
        mode=mode,
        asset=AssetMeta(
            kind=AssetKind.RESOURCE,
            class_name="Texture2D",
            object_name="T_Default",
        ),
        references=(),
        content=ContentNode(key="root", children=()),
        coverage=CoverageInfo(
            fields_expected=5,
            fields_parsed=5,
            coverage_pct=100.0,
            unparsed_fields=(),
        ),
        diagnostics=(),
    )
    defaults.update(kwargs)
    return SemanticIR(**defaults)


def make_package_ir(
    export_class: str = "Texture2D",
    parse_status: str | None = None,
    **kwargs,
) -> PackageIR:
    """Build a minimal PackageIR for testing."""
    export_kwargs: dict = dict(
        index=0,
        object_name="TestAsset",
        object_class=export_class,
        serial_size=2048,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class=None,
        properties=[],
        graphs=[],
        bulk_data=None,
    )
    if parse_status is not None:
        export_kwargs["parse_status"] = parse_status

    defaults = dict(
        header=PackageHeaderIR(
            package_name="/Game/Test",
            package_class="Package",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.1",
        ),
        name_map=(),
        imports=[],
        exports=[ExportIR(**export_kwargs)],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
        diagnostics_data=DiagnosticsDataIR(),
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)
