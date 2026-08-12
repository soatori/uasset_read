"""Shared fixtures for compact test suite."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from uasset_read.models.ir import (
    PackageIR, PackageHeaderIR, ExportIR, ImportIR,
    DiagnosticsDataIR, LinkerSummaryIR,
)
from uasset_read.semantic.ir import (
    SemanticIR, AssetMeta, CoverageInfo, ContentNode,
)
from uasset_read.semantic.kinds import AssetKind

from uasset_read.semantic.models import (
    SemanticIR, AssetMeta, AssetStatus, CoverageInfo, DiagnosticEntry,
)


def make_semantic_ir(mode="standard", **kwargs):
    """Factory for minimal SemanticIR (new model)."""
    defaults = dict(
        format="uasset_read.asset_semantic",
        format_version="1.0",
        mode=mode,
        asset_type="texture",
        asset=AssetMeta(package="/Game/T_Default", name="T_Default"),
        status=AssetStatus(parse="complete", representation="full"),
    )
    defaults.update(kwargs)
    return SemanticIR(**defaults)


SAMPLES_DIR = Path(__file__).resolve().parents[2] / "tests" / "samples"


@pytest.fixture
def sample_uasset():
    """Path to a representative .uasset sample."""
    path = SAMPLES_DIR / "FirstPerson_BP_FirstPersonCharacter.uasset"
    if not path.exists():
        pytest.skip("Test sample not found")
    return path


def make_package_ir(export_class="Texture2D", **kwargs):
    """Factory for minimal PackageIR."""
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
        exports=[
            ExportIR(
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
            ),
        ],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
        diagnostics_data=DiagnosticsDataIR(),
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


def make_semantic_ir(mode="standard", **kwargs):
    """Factory for minimal SemanticIR."""
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
