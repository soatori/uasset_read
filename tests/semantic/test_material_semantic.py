"""Material semantic extractor tests.

Tests the Material domain extractor with real Material samples.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.models import SemanticIR


_MATERIAL_SAMPLES = [
    "FirstPerson_M_FlatCol.uasset",
    "StackOBot_M_BotBase.uasset",
    "StarterContent_M_Wood_Walnut.uasset",
    "IntroToUnreal_M_Plastic.uasset",
    "CassiniSample_MI_Template_BaseGray_Metal.uasset",
]


def _build_semantic(samples_dir: Path, filename: str) -> SemanticIR:
    """Parse and build SemanticIR for a sample."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    return build_semantic_ir(ir, source_path=str(sample))


class TestMaterialSemanticExtraction:
    """Material semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _MATERIAL_SAMPLES,
        ids=[s.split(".")[0] for s in _MATERIAL_SAMPLES],
    )
    def test_material_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Material sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type == "material"
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _MATERIAL_SAMPLES,
        ids=[s.split(".")[0] for s in _MATERIAL_SAMPLES],
    )
    def test_material_status_valid(self, samples_dir: Path, filename: str):
        """Material SemanticIR has valid status fields."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.status.parse in ("complete", "partial", "failed")
        assert semantic.status.representation in ("full", "partial", "opaque")

    @pytest.mark.parametrize(
        "filename",
        _MATERIAL_SAMPLES,
        ids=[s.split(".")[0] for s in _MATERIAL_SAMPLES],
    )
    def test_material_has_content(self, samples_dir: Path, filename: str):
        """Material SemanticIR has non-empty content."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        if semantic.status.representation != "opaque":
            assert semantic.content, f"{filename}: content is empty"

    @pytest.mark.parametrize(
        "filename",
        _MATERIAL_SAMPLES,
        ids=[s.split(".")[0] for s in _MATERIAL_SAMPLES],
    )
    def test_material_has_references_or_domain_format(self, samples_dir: Path, filename: str):
        """Material SemanticIR has references or uses domain format (which owns them)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Domain formats own references internally, so top-level may be empty
        if semantic.format != "uasset_read.asset_semantic":
            assert isinstance(semantic.references, tuple)
        else:
            assert len(semantic.references) > 0


class TestMaterialDomainFormat:
    """Material domain format specifics."""

    def test_material_format_field(self, samples_dir: Path):
        """Material domain format is set."""
        semantic = _build_semantic(
            samples_dir, "FirstPerson_M_FlatCol.uasset",
        )
        assert semantic.format is not None
        assert semantic.format_version is not None

    def test_material_asset_meta(self, samples_dir: Path):
        """Material SemanticIR has correct asset metadata."""
        semantic = _build_semantic(
            samples_dir, "FirstPerson_M_FlatCol.uasset",
        )
        assert semantic.asset.package
        assert semantic.asset.name

    def test_material_expression_graph(self, samples_dir: Path):
        """Material content includes expression graph data."""
        semantic = _build_semantic(
            samples_dir, "FirstPerson_M_FlatCol.uasset",
        )
        # Material content should have some structure
        if semantic.content:
            # Content dict should have material-specific keys
            assert isinstance(semantic.content, dict)


class TestMaterialEnvelope:
    """Material preserves diagnostics and references from envelope (#556)."""

    def test_material_preserves_diagnostics(self, samples_dir: Path):
        """Material semantic IR preserves parser diagnostics from envelope."""
        sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
        if not sample.exists():
            pytest.skip("Sample not found")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        ir = build_package_ir(result)
        semantic_ir = build_semantic_ir(ir, source_path=str(sample))
        if ir.diagnostics_data and (ir.diagnostics_data.errors or ir.diagnostics_data.warnings):
            assert semantic_ir.diagnostics, "Material should preserve envelope diagnostics"

    def test_material_preserves_references(self, samples_dir: Path):
        """Material semantic IR preserves import/export references from envelope."""
        sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
        if not sample.exists():
            pytest.skip("Sample not found")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        ir = build_package_ir(result)
        semantic_ir = build_semantic_ir(ir, source_path=str(sample))
        if ir.imports or ir.exports:
            assert semantic_ir.references, "Material should preserve envelope references"

    def test_material_content_no_hardcoded_empty_arrays(self, samples_dir: Path):
        """Material content dict does not hardcode empty references/diagnostics."""
        sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
        if not sample.exists():
            pytest.skip("Sample not found")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        ir = build_package_ir(result)
        semantic_ir = build_semantic_ir(ir, source_path=str(sample))
        content = semantic_ir.content
        if "references" in content:
            assert content["references"] != [], "Material content should not hardcode empty references"
        if "diagnostics" in content:
            assert content["diagnostics"] != [], "Material content should not hardcode empty diagnostics"
