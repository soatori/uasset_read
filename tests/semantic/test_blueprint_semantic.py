"""Blueprint semantic extractor tests.

Tests the Blueprint domain extractor with real Blueprint samples.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.models import SemanticIR


# Real Blueprint samples
_BLUEPRINT_SAMPLES = [
    "FirstPerson_BP_FirstPersonCharacter.uasset",
    "StackOBot_BP_Drone.uasset",
    "IntroToUnreal_BP_Light.uasset",
]


def _build_semantic(samples_dir: Path, filename: str) -> SemanticIR:
    """Parse and build SemanticIR for a sample."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    return build_semantic_ir(ir, source_path=str(sample))


class TestBlueprintSemanticExtraction:
    """Blueprint semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _BLUEPRINT_SAMPLES,
        ids=[s.split(".")[0] for s in _BLUEPRINT_SAMPLES],
    )
    def test_blueprint_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Blueprint sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type == "blueprint"
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _BLUEPRINT_SAMPLES,
        ids=[s.split(".")[0] for s in _BLUEPRINT_SAMPLES],
    )
    def test_blueprint_status_valid(self, samples_dir: Path, filename: str):
        """Blueprint SemanticIR has valid status fields."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.status.parse in ("complete", "partial", "failed")
        assert semantic.status.representation in ("full", "partial", "opaque")

    @pytest.mark.parametrize(
        "filename",
        _BLUEPRINT_SAMPLES,
        ids=[s.split(".")[0] for s in _BLUEPRINT_SAMPLES],
    )
    def test_blueprint_has_content(self, samples_dir: Path, filename: str):
        """Blueprint SemanticIR has non-empty content (domain data)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # For blueprints with a registered extractor, content should be populated
        if semantic.status.representation != "opaque":
            assert semantic.content, f"{filename}: content is empty"

    @pytest.mark.parametrize(
        "filename",
        _BLUEPRINT_SAMPLES,
        ids=[s.split(".")[0] for s in _BLUEPRINT_SAMPLES],
    )
    def test_blueprint_has_references_or_domain_format(self, samples_dir: Path, filename: str):
        """Blueprint SemanticIR has references or uses domain format (which owns them)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Domain formats own references internally, so top-level may be empty
        if semantic.format != "uasset_read.asset_semantic":
            assert isinstance(semantic.references, tuple)
        else:
            assert len(semantic.references) > 0

    def test_blueprint_asset_meta(self, samples_dir: Path):
        """Blueprint SemanticIR has correct asset metadata."""
        semantic = _build_semantic(
            samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset",
        )
        assert semantic.asset.package
        assert semantic.asset.name
        assert "FirstPersonCharacter" in semantic.asset.name


class TestBlueprintSemanticContent:
    """Blueprint-specific content fields in SemanticIR."""

    def test_blueprint_format_field(self, samples_dir: Path):
        """Blueprint domain format is set."""
        semantic = _build_semantic(
            samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset",
        )
        # Blueprint has a domain format
        assert semantic.format is not None
        assert semantic.format_version is not None
