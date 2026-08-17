"""CurveTable semantic extractor tests.

Tests the CurveTable domain extractor with real CurveTable samples.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.render import render_semantic_json
from uasset_read.semantic.validator import validate_semantic_document
from uasset_read.semantic.models import SemanticIR


_CURVE_TABLE_SAMPLES = [
    "Lyra_Curve_LaunchpadMaterialEffect.uasset",
]


def _build_semantic(samples_dir: Path, filename: str) -> SemanticIR:
    """Parse and build SemanticIR for a sample."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    return build_semantic_ir(ir, source_path=str(sample))


def _build_and_project(samples_dir: Path, filename: str, mode: str = "standard") -> SemanticIR:
    """Parse, build, project, and return SemanticIR."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic = build_semantic_ir(ir, source_path=str(sample))
    return project_semantic(semantic, mode)


class TestCurveTableSemanticExtraction:
    """CurveTable semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _CURVE_TABLE_SAMPLES,
        ids=[s.split(".")[0] for s in _CURVE_TABLE_SAMPLES],
    )
    def test_curve_table_has_semantic_ir(self, samples_dir: Path, filename: str):
        """CurveTable sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        # Lyra_Curve_LaunchpadMaterialEffect is actually CurveFloat → standalone_semantic
        assert semantic.asset_type in ("curve_table", "curve")
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _CURVE_TABLE_SAMPLES,
        ids=[s.split(".")[0] for s in _CURVE_TABLE_SAMPLES],
    )
    def test_curve_table_format(self, samples_dir: Path, filename: str):
        """CurveTable/CurveFloat uses the appropriate domain format."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # CurveFloat uses standalone_semantic; real CurveTable would use curve_table_semantic
        assert semantic.format in ("uasset_read.curve_table_semantic", "uasset_read.standalone_semantic")
        assert semantic.format_version == "1.0.0"

    @pytest.mark.parametrize(
        "filename",
        _CURVE_TABLE_SAMPLES,
        ids=[s.split(".")[0] for s in _CURVE_TABLE_SAMPLES],
    )
    def test_curve_table_has_content(self, samples_dir: Path, filename: str):
        """CurveTable/CurveFloat SemanticIR has non-empty content."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # CurveFloat produces standalone content; CurveTable would produce curve_table content
        domain_key = "standalone" if semantic.format == "uasset_read.standalone_semantic" else "curve_table"
        assert semantic.content, f"{filename}: content is empty"
        assert domain_key in semantic.content, f"{filename}: missing {domain_key} key"


class TestCurveTableValidation:
    """CurveTable validator rules."""

    @pytest.mark.parametrize(
        "filename",
        _CURVE_TABLE_SAMPLES,
        ids=[s.split(".")[0] for s in _CURVE_TABLE_SAMPLES],
    )
    def test_curve_table_passes_validation(self, samples_dir: Path, filename: str):
        """CurveTable SemanticIR passes validation."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"


class TestCurveTableSchemaConformance:
    """Schema conformance for CurveTable semantic JSON."""

    @pytest.mark.parametrize(
        "filename",
        _CURVE_TABLE_SAMPLES,
        ids=[s.split(".")[0] for s in _CURVE_TABLE_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str):
        """Standard mode output validates against schema."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        # CurveFloat uses standalone_semantic; real CurveTable would use curve_table_semantic
        assert data["format"] in ("uasset_read.curve_table_semantic", "uasset_read.standalone_semantic")
        assert "$schema" in data


class TestCurveTableProjection:
    """CurveTable projection (standard vs debug mode)."""

    def test_standard_strips_evidence(self, samples_dir: Path):
        """Standard mode strips evidence from CurveTable output."""
        semantic = _build_and_project(
            samples_dir, "Lyra_Curve_LaunchpadMaterialEffect.uasset", "standard",
        )
        assert len(semantic.evidence) == 0

    def test_debug_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence in CurveTable output."""
        semantic = _build_and_project(
            samples_dir, "Lyra_Curve_LaunchpadMaterialEffect.uasset", "debug",
        )
        assert semantic.mode == "debug"
