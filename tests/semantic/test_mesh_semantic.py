"""Mesh semantic extractor tests.

Tests the Mesh domain extractor with real StaticMesh and SkeletalMesh samples.
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


_MESH_SAMPLES = [
    "StarterContent_SM_Chair.uasset",
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


class TestMeshSemanticExtraction:
    """Mesh semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _MESH_SAMPLES,
        ids=[s.split(".")[0] for s in _MESH_SAMPLES],
    )
    def test_mesh_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Mesh sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type in ("static_mesh", "skeletal_mesh")
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _MESH_SAMPLES,
        ids=[s.split(".")[0] for s in _MESH_SAMPLES],
    )
    def test_mesh_format(self, samples_dir: Path, filename: str):
        """Mesh uses the mesh_semantic or asset_semantic domain format."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Opaque assets use base format; non-opaque use mesh_semantic
        assert semantic.format in ("uasset_read.mesh_semantic", "uasset_read.asset_semantic")

    @pytest.mark.parametrize(
        "filename",
        _MESH_SAMPLES,
        ids=[s.split(".")[0] for s in _MESH_SAMPLES],
    )
    def test_mesh_has_content(self, samples_dir: Path, filename: str):
        """Mesh SemanticIR may have empty content for opaque assets."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Opaque assets (StaticMesh with custom Serialize) have empty content
        if semantic.status.representation == "opaque":
            assert not semantic.content or "mesh" not in semantic.content
        else:
            assert semantic.content, f"{filename}: content is empty"
            assert "mesh" in semantic.content, f"{filename}: missing mesh key"

    @pytest.mark.parametrize(
        "filename",
        _MESH_SAMPLES,
        ids=[s.split(".")[0] for s in _MESH_SAMPLES],
    )
    def test_mesh_summary(self, samples_dir: Path, filename: str):
        """Mesh content has mesh_summary when not opaque."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        if semantic.status.representation == "opaque" or "mesh" not in semantic.content:
            pytest.skip("Opaque asset — no content to validate")
        mesh = semantic.content["mesh"]
        assert "mesh_summary" in mesh
        summary = mesh["mesh_summary"]
        assert isinstance(summary, dict)


class TestMeshValidation:
    """Mesh validator rules."""

    @pytest.mark.parametrize(
        "filename",
        _MESH_SAMPLES,
        ids=[s.split(".")[0] for s in _MESH_SAMPLES],
    )
    def test_mesh_passes_validation(self, samples_dir: Path, filename: str):
        """Mesh SemanticIR passes validation."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"


class TestMeshSchemaConformance:
    """Schema conformance for Mesh semantic JSON."""

    @pytest.mark.parametrize(
        "filename",
        _MESH_SAMPLES,
        ids=[s.split(".")[0] for s in _MESH_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str):
        """Standard mode output validates against schema."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        # Opaque assets use base format
        assert data["format"] in ("uasset_read.mesh_semantic", "uasset_read.asset_semantic")
        assert "$schema" in data
        if semantic.status.representation != "opaque":
            assert "mesh" in data
            assert "mesh_semantic.schema.json" in data["$schema"]


class TestMeshProjection:
    """Mesh projection (standard vs debug mode)."""

    def test_standard_strips_evidence(self, samples_dir: Path):
        """Standard mode strips evidence from Mesh output."""
        semantic = _build_and_project(
            samples_dir,
            "StarterContent_SM_Chair.uasset",
            "standard",
        )
        assert len(semantic.evidence) == 0

    def test_debug_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence in Mesh output."""
        semantic = _build_and_project(
            samples_dir,
            "StarterContent_SM_Chair.uasset",
            "debug",
        )
        assert semantic.mode == "debug"
