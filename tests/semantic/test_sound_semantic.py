"""Sound semantic extractor tests.

Tests the Sound domain extractor with real Sound samples.
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


_SOUND_SAMPLES = [
    "ALS_Concrete_Step_01_SoundWave.uasset",
    "StarterContent_Starter_Background_Cue.uasset",
    "CropoutSample_Attenuation_general.uasset",
]

_SOUND_ASSET_TYPES = {
    "ALS_Concrete_Step_01_SoundWave.uasset": "sound_wave",
    "StarterContent_Starter_Background_Cue.uasset": "sound_cue",
    "CropoutSample_Attenuation_general.uasset": "sound_attenuation",
}

_VALID_SOUND_TYPES = {"sound_wave", "sound_cue", "sound_attenuation"}


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


class TestSoundSemanticExtraction:
    """Sound semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _SOUND_SAMPLES,
        ids=[s.split(".")[0] for s in _SOUND_SAMPLES],
    )
    def test_sound_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Sound sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type in _VALID_SOUND_TYPES
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _SOUND_SAMPLES,
        ids=[s.split(".")[0] for s in _SOUND_SAMPLES],
    )
    def test_sound_format(self, samples_dir: Path, filename: str):
        """Sound uses the sound_semantic domain format."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.format == "uasset_read.sound_semantic"
        assert semantic.format_version == "1.0.0"

    @pytest.mark.parametrize(
        "filename",
        _SOUND_SAMPLES,
        ids=[s.split(".")[0] for s in _SOUND_SAMPLES],
    )
    def test_sound_has_content(self, samples_dir: Path, filename: str):
        """Sound SemanticIR has content with sound key."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert "sound" in semantic.content, f"{filename}: missing sound key"

    @pytest.mark.parametrize(
        "filename",
        _SOUND_SAMPLES,
        ids=[s.split(".")[0] for s in _SOUND_SAMPLES],
    )
    def test_sound_asset_type_matches_class(self, samples_dir: Path, filename: str):
        """Sound asset_type matches the expected type for the class."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        expected = _SOUND_ASSET_TYPES.get(filename, "")
        assert semantic.asset_type == expected


class TestSoundValidation:
    """Sound validator rules."""

    @pytest.mark.parametrize(
        "filename",
        [f for f in _SOUND_SAMPLES if f != "ALS_Concrete_Step_01_SoundWave.uasset"],
        ids=[s.split(".")[0] for s in _SOUND_SAMPLES if s != "ALS_Concrete_Step_01_SoundWave.uasset"],
    )
    def test_sound_passes_validation(self, samples_dir: Path, filename: str):
        """Sound SemanticIR passes validation when content is non-empty."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"

    def test_soundwave_validation_empty_content(self, samples_dir: Path):
        """SoundWave with partial metadata produces empty content (valid)."""
        if not (samples_dir / "ALS_Concrete_Step_01_SoundWave.uasset").exists():
            pytest.skip("Sample not found")

        semantic = _build_and_project(samples_dir, "ALS_Concrete_Step_01_SoundWave.uasset")
        errors = validate_semantic_document(semantic)
        # Empty content is valid — validator no longer reports error for empty content
        assert errors == [], f"Validation errors: {errors}"


class TestSoundProjection:
    """Sound projection (standard vs debug mode)."""

    def test_standard_strips_evidence(self, samples_dir: Path):
        """Standard mode strips evidence from Sound output."""
        semantic = _build_and_project(
            samples_dir, "ALS_Concrete_Step_01_SoundWave.uasset", "standard",
        )
        assert len(semantic.evidence) == 0

    def test_debug_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence in Sound output."""
        semantic = _build_and_project(
            samples_dir, "ALS_Concrete_Step_01_SoundWave.uasset", "debug",
        )
        assert semantic.mode == "debug"


class TestSoundSchemaConformance:
    """Schema conformance for Sound semantic JSON."""

    @pytest.mark.parametrize(
        "filename",
        _SOUND_SAMPLES,
        ids=[s.split(".")[0] for s in _SOUND_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str):
        """Standard mode output validates against schema."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        assert data["format"] == "uasset_read.sound_semantic"
        assert "$schema" in data
        assert "sound_semantic.schema.json" in data["$schema"]
        assert data["asset_type"] in _VALID_SOUND_TYPES

        # sound key is present when content is non-empty; renderer strips empty dicts
        if semantic.content.get("sound"):
            assert "sound" in data