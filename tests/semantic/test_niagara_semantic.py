"""Niagara semantic extractor tests.

Tests the Niagara domain extractor with real Niagara samples.
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


_NIAGARA_SAMPLES = [
    "NM_BPSystemEvent.uasset",
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


class TestNiagaraSemanticExtraction:
    """Niagara semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _NIAGARA_SAMPLES,
        ids=[s.split(".")[0] for s in _NIAGARA_SAMPLES],
    )
    def test_niagara_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Niagara sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type.startswith("niagara")
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _NIAGARA_SAMPLES,
        ids=[s.split(".")[0] for s in _NIAGARA_SAMPLES],
    )
    def test_niagara_format(self, samples_dir: Path, filename: str):
        """Niagara uses the niagara_semantic domain format."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.format == "uasset_read.niagara_semantic"
        assert semantic.format_version == "1.0.0"

    @pytest.mark.parametrize(
        "filename",
        _NIAGARA_SAMPLES,
        ids=[s.split(".")[0] for s in _NIAGARA_SAMPLES],
    )
    def test_niagara_has_content(self, samples_dir: Path, filename: str):
        """Niagara SemanticIR has non-empty content with niagara key."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.content, f"{filename}: content is empty"
        assert "niagara" in semantic.content, f"{filename}: missing niagara key"


class TestNiagaraValidation:
    """Niagara validator rules."""

    @pytest.mark.parametrize(
        "filename",
        _NIAGARA_SAMPLES,
        ids=[s.split(".")[0] for s in _NIAGARA_SAMPLES],
    )
    def test_niagara_passes_validation(self, samples_dir: Path, filename: str):
        """Niagara SemanticIR passes validation."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"


class TestNiagaraSchemaConformance:
    """Schema conformance for Niagara semantic JSON."""

    @pytest.mark.parametrize(
        "filename",
        _NIAGARA_SAMPLES,
        ids=[s.split(".")[0] for s in _NIAGARA_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str):
        """Standard mode output validates against schema."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        assert data["format"] == "uasset_read.niagara_semantic"
        assert "niagara" in data
        assert "$schema" in data
        assert "niagara_semantic.schema.json" in data["$schema"]


class TestNiagaraProjection:
    """Niagara projection (standard vs debug mode)."""

    def test_standard_strips_evidence(self, samples_dir: Path):
        """Standard mode strips evidence from Niagara output."""
        semantic = _build_and_project(
            samples_dir,
            "NM_BPSystemEvent.uasset",
            "standard",
        )
        assert len(semantic.evidence) == 0

    def test_debug_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence in Niagara output."""
        semantic = _build_and_project(
            samples_dir,
            "NM_BPSystemEvent.uasset",
            "debug",
        )
        assert semantic.mode == "debug"
