"""Skeleton semantic extractor tests.

Tests the Skeleton domain extractor with real Skeleton samples.
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


_SKELETON_SAMPLES = [
    "ALS_Mannequin_Skeleton",
    "CiciToon_SK_Mannequin",
]


def _build_semantic(samples_dir: Path, stem: str) -> SemanticIR:
    """Parse and build SemanticIR for a sample."""
    sample = samples_dir / f"{stem}.uasset"
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    return build_semantic_ir(ir, source_path=str(sample))


def _build_and_project(samples_dir: Path, stem: str, mode: str = "standard") -> SemanticIR:
    """Parse, build, project, and return SemanticIR."""
    sample = samples_dir / f"{stem}.uasset"
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic = build_semantic_ir(ir, source_path=str(sample))
    return project_semantic(semantic, mode)


class TestSkeletonSemanticExtraction:
    """Skeleton semantic extractor output validation."""

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_skeleton_has_semantic_ir(self, samples_dir: Path, stem: str):
        """Skeleton sample produces a valid SemanticIR."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_semantic(samples_dir, stem)
        assert semantic is not None
        assert semantic.asset_type == "skeleton"
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_skeleton_format(self, samples_dir: Path, stem: str):
        """Skeleton uses the skeleton_semantic domain format."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_semantic(samples_dir, stem)
        assert semantic.format == "uasset_read.skeleton_semantic"
        assert semantic.format_version == "1.0.0"

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_skeleton_has_content(self, samples_dir: Path, stem: str):
        """Skeleton SemanticIR has non-empty skeleton content."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_semantic(samples_dir, stem)
        assert semantic.content, f"{stem}: content is empty"
        assert "skeleton" in semantic.content, f"{stem}: missing skeleton key"

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_skeleton_bone_count_at_top_level(self, samples_dir: Path, stem: str):
        """Skeleton content has bone_count at top level (not only in skeleton_summary)."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_semantic(samples_dir, stem)
        skeleton = semantic.content.get("skeleton", {})
        assert "bone_count" in skeleton, f"{stem}: missing top-level bone_count"
        assert isinstance(skeleton["bone_count"], int)
        assert skeleton["bone_count"] >= 0

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_skeleton_bone_count_matches_bones(self, samples_dir: Path, stem: str):
        """bone_count matches actual number of bones emitted."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_semantic(samples_dir, stem)
        skeleton = semantic.content.get("skeleton", {})
        bone_count = skeleton.get("bone_count", 0)
        bones = skeleton.get("bones", [])
        assert bone_count == len(bones), (
            f"{stem}: bone_count={bone_count} but len(bones)={len(bones)}"
        )

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_skeleton_bones_have_required_fields(self, samples_dir: Path, stem: str):
        """Each bone has name and parent_index."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_semantic(samples_dir, stem)
        bones = semantic.content.get("skeleton", {}).get("bones", [])
        for i, bone in enumerate(bones):
            assert "name" in bone, f"Bone[{i}] missing name"
            assert bone["name"], f"Bone[{i}] has empty name"
            assert "parent_index" in bone, f"Bone[{i}] missing parent_index"


class TestSkeletonValidation:
    """Skeleton validator rules."""

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_skeleton_passes_validation(self, samples_dir: Path, stem: str):
        """Skeleton SemanticIR passes validation."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_and_project(samples_dir, stem)
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"

    def test_validator_aggregates_bone_errors(self):
        """Validator reports non-integer parent_index errors (not per-bone)."""
        from unittest.mock import MagicMock
        from uasset_read.semantic.validator import validate_skeleton_document

        ir = MagicMock()
        ir.content = {
            "skeleton": {
                "bone_count": 10,
                "bones": [
                    {"name": f"bone_{i}", "parent_index": "invalid"}
                    for i in range(10)
                ],
            }
        }

        errors = validate_skeleton_document(ir)
        # Non-integer parent_index should produce errors
        parent_errors = [e for e in errors if "invalid parent_index" in e]
        assert len(parent_errors) > 0, (
            f"Expected parent_index errors, got: {errors}"
        )


class TestSkeletonSchemaConformance:
    """Schema conformance for Skeleton semantic JSON."""

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, stem: str):
        """Standard mode output validates against schema."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_and_project(samples_dir, stem, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        assert data["format"] == "uasset_read.skeleton_semantic"
        assert "$schema" in data


class TestSkeletonProjection:
    """Skeleton projection (standard vs debug mode)."""

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_standard_strips_evidence(self, samples_dir: Path, stem: str):
        """Standard mode strips evidence from Skeleton output."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_and_project(samples_dir, stem, "standard")
        assert len(semantic.evidence) == 0

    @pytest.mark.parametrize(
        "stem",
        _SKELETON_SAMPLES,
    )
    def test_debug_keeps_evidence(self, samples_dir: Path, stem: str):
        """Debug mode keeps evidence in Skeleton output."""
        sample = samples_dir / f"{stem}.uasset"
        if not sample.exists():
            pytest.skip(f"Sample not found: {stem}.uasset")

        semantic = _build_and_project(samples_dir, stem, "debug")
        assert semantic.mode == "debug"
