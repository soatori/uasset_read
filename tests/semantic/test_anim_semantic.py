"""Animation semantic extractor tests.

Tests the Animation domain extractor with real Animation samples.
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


_ANIM_SAMPLES = [
    ("ALS_N_FallLoop.uasset", "AnimSequence"),
    ("ALS_CLF_GetUp_Back_Montage_Default.uasset", "AnimMontage"),
    ("Echo_calf_l_PoseAsset.uasset", "PoseAsset"),
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


class TestAnimSemanticExtraction:
    """Animation semantic extractor output validation."""

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _ANIM_SAMPLES,
        ids=[s[0].split(".")[0] for s in _ANIM_SAMPLES],
    )
    def test_anim_has_semantic_ir(self, samples_dir: Path, filename: str, expected_class: str):
        """Animation sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type in ("anim_sequence", "anim_montage", "pose_asset", "anim_curve_compression_settings")
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _ANIM_SAMPLES,
        ids=[s[0].split(".")[0] for s in _ANIM_SAMPLES],
    )
    def test_anim_format(self, samples_dir: Path, filename: str, expected_class: str):
        """Animation uses the anim_semantic domain format."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Opaque assets use base format; non-opaque use anim_semantic
        assert semantic.format in ("uasset_read.anim_semantic", "uasset_read.asset_semantic")

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _ANIM_SAMPLES,
        ids=[s[0].split(".")[0] for s in _ANIM_SAMPLES],
    )
    def test_anim_has_content(self, samples_dir: Path, filename: str, expected_class: str):
        """Animation SemanticIR has content with anim key (may be empty for opaque assets)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Opaque assets (AnimSequence, AnimMontage) have empty content
        if semantic.status.representation == "opaque":
            assert not semantic.content or "anim" not in semantic.content
        else:
            assert semantic.content, f"{filename}: content is empty"
            assert "anim" in semantic.content, f"{filename}: missing anim key"

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _ANIM_SAMPLES,
        ids=[s[0].split(".")[0] for s in _ANIM_SAMPLES],
    )
    def test_anim_structure(self, samples_dir: Path, filename: str, expected_class: str):
        """Animation content has correct structure based on class type."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Skip structure check for opaque assets
        if semantic.status.representation == "opaque" or "anim" not in semantic.content:
            pytest.skip("Opaque asset — no content to validate")
        anim = semantic.content["anim"]
        assert isinstance(anim, dict)

        if expected_class == "AnimSequence":
            assert "anim_summary" in anim
        elif expected_class == "AnimMontage":
            assert "montage_summary" in anim
        elif expected_class == "PoseAsset":
            assert "pose_summary" in anim


class TestAnimValidation:
    """Animation validator rules."""

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _ANIM_SAMPLES,
        ids=[s[0].split(".")[0] for s in _ANIM_SAMPLES],
    )
    def test_anim_passes_validation(self, samples_dir: Path, filename: str, expected_class: str):
        """Animation SemanticIR passes validation."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"


class TestAnimProjection:
    """Animation projection (standard vs debug mode)."""

    def test_standard_strips_evidence(self, samples_dir: Path):
        """Standard mode strips evidence from Animation output."""
        semantic = _build_and_project(
            samples_dir,
            "ALS_N_FallLoop.uasset",
            "standard",
        )
        assert len(semantic.evidence) == 0

    def test_debug_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence in Animation output."""
        semantic = _build_and_project(
            samples_dir,
            "ALS_N_FallLoop.uasset",
            "debug",
        )
        assert semantic.mode == "debug"


class TestAnimSchemaConformance:
    """Schema conformance for Animation semantic JSON."""

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _ANIM_SAMPLES,
        ids=[s[0].split(".")[0] for s in _ANIM_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str, expected_class: str):
        """Standard mode output validates against schema."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        # Opaque assets use base format; non-opaque use anim_semantic
        assert data["format"] in ("uasset_read.anim_semantic", "uasset_read.asset_semantic")
        assert "$schema" in data
        # anim key present only for non-opaque assets
        if semantic.status.representation != "opaque":
            assert "anim" in data
            assert "anim_semantic.schema.json" in data["$schema"]
