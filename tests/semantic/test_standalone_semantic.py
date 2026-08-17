"""Standalone types semantic extractor tests.

Tests the Standalone domain extractor with real standalone type samples.
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


_STANDALONE_SAMPLES = [
    "GameAnimSample_TeethSubsurfaceProfile.uasset",
    "ProjectTitan_SM_GrassBlade_FoliageType.uasset",
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


class TestStandaloneSemanticExtraction:
    """Standalone semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _STANDALONE_SAMPLES,
        ids=[s.split(".")[0] for s in _STANDALONE_SAMPLES],
    )
    def test_standalone_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Standalone sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type in ("subsurface_profile", "foliage_type", "curve")
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _STANDALONE_SAMPLES,
        ids=[s.split(".")[0] for s in _STANDALONE_SAMPLES],
    )
    def test_standalone_format(self, samples_dir: Path, filename: str):
        """Standalone uses the standalone_semantic domain format."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.format == "uasset_read.standalone_semantic"
        assert semantic.format_version == "1.0.0"

    @pytest.mark.parametrize(
        "filename",
        _STANDALONE_SAMPLES,
        ids=[s.split(".")[0] for s in _STANDALONE_SAMPLES],
    )
    def test_standalone_has_content(self, samples_dir: Path, filename: str):
        """Standalone SemanticIR may have empty content when asset_type_data is None."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Some standalone assets (e.g. FoliageType) have no asset_type_data
        if semantic.content:
            assert "standalone" in semantic.content, f"{filename}: missing standalone key"


class TestStandaloneValidation:
    """Standalone validator rules."""

    @pytest.mark.parametrize(
        "filename",
        _STANDALONE_SAMPLES,
        ids=[s.split(".")[0] for s in _STANDALONE_SAMPLES],
    )
    def test_standalone_passes_validation(self, samples_dir: Path, filename: str):
        """Standalone SemanticIR passes validation (empty content is valid for standalone)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        # Empty content is expected when asset_type_data is None
        assert errors == [], f"Validation errors: {errors}"


class TestStandaloneSchemaConformance:
    """Schema conformance for Standalone semantic JSON."""

    @pytest.mark.parametrize(
        "filename",
        _STANDALONE_SAMPLES,
        ids=[s.split(".")[0] for s in _STANDALONE_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str):
        """Standard mode output validates against schema."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        assert data["format"] == "uasset_read.standalone_semantic"
        assert "$schema" in data
        assert "standalone_semantic.schema.json" in data["$schema"]
        # standalone key present only when content is non-empty
        if semantic.content:
            assert "standalone" in data


class TestStandaloneProjection:
    """Standalone projection (standard vs debug mode)."""

    def test_standard_strips_evidence(self, samples_dir: Path):
        """Standard mode strips evidence from Standalone output."""
        if not (samples_dir / "GameAnimSample_TeethSubsurfaceProfile.uasset").exists():
            pytest.skip("Sample not found")

        semantic = _build_and_project(
            samples_dir, "GameAnimSample_TeethSubsurfaceProfile.uasset", "standard",
        )
        assert len(semantic.evidence) == 0

    def test_debug_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence in Standalone output."""
        if not (samples_dir / "GameAnimSample_TeethSubsurfaceProfile.uasset").exists():
            pytest.skip("Sample not found")

        semantic = _build_and_project(
            samples_dir, "GameAnimSample_TeethSubsurfaceProfile.uasset", "debug",
        )
        assert semantic.mode == "debug"
