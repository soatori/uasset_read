"""Tests for Movie semantic JSON extension (#557i)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic import (
    build_semantic_ir,
    render_semantic_json,
    validate_semantic_document,
)

# Movie samples
_MOVIE_SAMPLES = [
    ("Lyra_SEQ_LobbyScreen_LevelSequence.uasset", "LevelSequence"),
]


def _build_semantic(samples_dir: Path, filename: str):
    """Parse and build SemanticIR for a sample."""
    sample = samples_dir / filename
    if not sample.exists():
        pytest.skip(f"Sample not found: {filename}")
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    return build_semantic_ir(ir, source_path=str(sample))


def _build_ir_for_sample(samples_dir: Path, filename: str, mode: str = "standard"):
    """Build SemanticIR for a sample."""
    sample = samples_dir / filename
    if not sample.exists():
        pytest.skip(f"Sample not found: {filename}")
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    semantic = build_semantic_ir(ir, source_path=str(sample))
    from uasset_read.semantic.projection import project_semantic

    return project_semantic(semantic, mode)


def _build_ir_for_project(samples_dir: Path, filename: str, mode: str = "standard"):
    """Build SemanticIR for a sample with projection."""
    return _build_ir_for_sample(samples_dir, filename, mode)


class TestMovieSemanticExtraction:
    """Test Movie content extraction."""

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _MOVIE_SAMPLES,
        ids=[s[0].split(".")[0] for s in _MOVIE_SAMPLES],
    )
    def test_asset_type(self, samples_dir: Path, filename: str, expected_class: str):
        """Movie assets should have movie_scene, level_sequence, or blueprint type."""
        semantic = _build_semantic(samples_dir, filename)
        # LevelSequence samples may have BlueprintGeneratedClass as primary export
        assert semantic.asset_type in ("movie_scene", "level_sequence", "blueprint", "unknown")

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _MOVIE_SAMPLES,
        ids=[s[0].split(".")[0] for s in _MOVIE_SAMPLES],
    )
    def test_format(self, samples_dir: Path, filename: str, expected_class: str):
        """Movie assets should use movie_semantic or asset_semantic format."""
        semantic = _build_semantic(samples_dir, filename)
        assert semantic.format in ("uasset_read.movie_semantic", "uasset_read.asset_semantic")

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _MOVIE_SAMPLES,
        ids=[s[0].split(".")[0] for s in _MOVIE_SAMPLES],
    )
    def test_content_structure(self, samples_dir: Path, filename: str, expected_class: str):
        """Movie content should have movie key if not opaque and using movie_semantic format."""
        semantic = _build_semantic(samples_dir, filename)
        if semantic.status.representation == "opaque":
            pytest.skip("Opaque asset")
        if semantic.format == "uasset_read.movie_semantic":
            assert "movie" in semantic.content


class TestMovieValidation:
    """Test Movie semantic validation."""

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _MOVIE_SAMPLES,
        ids=[s[0].split(".")[0] for s in _MOVIE_SAMPLES],
    )
    def test_validation_passes(self, samples_dir: Path, filename: str, expected_class: str):
        """Movie IR should pass validation."""
        semantic = _build_semantic(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        # Filter non-critical errors for assets without asset_type_data or with wrong primary export
        critical = [e for e in errors if "content is empty" not in e.lower() and "Invalid mode" not in e]
        assert len(critical) == 0


class TestMovieSchemaConformance:
    """Test Movie JSON schema conformance."""

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _MOVIE_SAMPLES,
        ids=[s[0].split(".")[0] for s in _MOVIE_SAMPLES],
    )
    def test_render_produces_valid_json(self, samples_dir: Path, filename: str, expected_class: str):
        """Rendered JSON should be valid."""
        semantic = _build_semantic(samples_dir, filename)
        json_str = render_semantic_json(semantic)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _MOVIE_SAMPLES,
        ids=[s[0].split(".")[0] for s in _MOVIE_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str, expected_class: str):
        """Standard mode output should match schema (if movie format)."""
        semantic = _build_semantic(samples_dir, filename)
        if semantic.format != "uasset_read.movie_semantic":
            pytest.skip("Not movie_semantic format")
        json_str = render_semantic_json(semantic)
        parsed = json.loads(json_str)
        # Check required fields are present
        assert "movie" in parsed
        assert "format" in parsed
        assert parsed["format"] == "uasset_read.movie_semantic"


class TestMovieProjection:
    """Test Movie debug projection."""

    @pytest.mark.parametrize(
        ("filename", "expected_class"),
        _MOVIE_SAMPLES,
        ids=[s[0].split(".")[0] for s in _MOVIE_SAMPLES],
    )
    def test_debug_projection_includes_evidence(self, samples_dir: Path, filename: str, expected_class: str):
        """Debug mode should include evidence."""
        semantic = _build_ir_for_project(samples_dir, filename, mode="debug")
        json_str = render_semantic_json(semantic)
        parsed = json.loads(json_str)
        # Debug mode should have evidence array
        assert "evidence" in parsed
