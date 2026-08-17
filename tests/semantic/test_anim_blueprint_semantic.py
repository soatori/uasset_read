"""AnimBlueprint semantic extractor tests.

Tests the AnimBlueprint domain extractor with real AnimBP samples.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.models import SemanticIR


# ABP_RifleAnimLayers parses cleanly; ALS_AnimBP has corrupted class names
# and resolves to "unknown" — tested separately with relaxed assertions.
_CLEAN_ANIMBP = ["ABP_RifleAnimLayers.uasset"]
_ALL_ANIMBP = ["ABP_RifleAnimLayers.uasset", "ALS_AnimBP.uasset"]


def _build_semantic(samples_dir: Path, filename: str) -> SemanticIR:
    """Parse and build SemanticIR for a sample."""
    sample = samples_dir / filename
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    ir = build_package_ir(result)
    return build_semantic_ir(ir, source_path=str(sample))


class TestAnimBlueprintSemanticExtraction:
    """AnimBlueprint semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _CLEAN_ANIMBP,
        ids=[s.split(".")[0] for s in _CLEAN_ANIMBP],
    )
    def test_animbp_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Clean AnimBlueprint sample produces a valid SemanticIR with correct type."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type == "anim_blueprint"
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _ALL_ANIMBP,
        ids=[s.split(".")[0] for s in _ALL_ANIMBP],
    )
    def test_animbp_produces_valid_ir(self, samples_dir: Path, filename: str):
        """All AnimBP samples produce a valid SemanticIR (type may be unknown)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type in ("anim_blueprint", "unknown")

    @pytest.mark.parametrize(
        "filename",
        _ALL_ANIMBP,
        ids=[s.split(".")[0] for s in _ALL_ANIMBP],
    )
    def test_animbp_status_valid(self, samples_dir: Path, filename: str):
        """AnimBlueprint SemanticIR has valid status fields."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.status.parse in ("complete", "partial", "failed")
        assert semantic.status.representation in ("full", "partial", "opaque")

    @pytest.mark.parametrize(
        "filename",
        _ALL_ANIMBP,
        ids=[s.split(".")[0] for s in _ALL_ANIMBP],
    )
    def test_animbp_has_content_when_not_opaque(self, samples_dir: Path, filename: str):
        """AnimBlueprint SemanticIR has non-empty content when not opaque."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        if semantic.status.representation != "opaque":
            assert semantic.content, f"{filename}: content is empty"

    @pytest.mark.parametrize(
        "filename",
        _ALL_ANIMBP,
        ids=[s.split(".")[0] for s in _ALL_ANIMBP],
    )
    def test_animbp_has_references_or_domain_format(self, samples_dir: Path, filename: str):
        """AnimBlueprint SemanticIR has references or uses domain format (which owns them)."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        # Domain formats own references internally, so top-level may be empty
        if semantic.format != "uasset_read.asset_semantic":
            # Domain format — references are in content
            assert isinstance(semantic.references, tuple)
        else:
            assert len(semantic.references) > 0


class TestAnimBlueprintDomainFormat:
    """AnimBlueprint domain format specifics."""

    def test_animbp_format_field(self, samples_dir: Path):
        """AnimBlueprint domain format is set."""
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")

        semantic = _build_semantic(samples_dir, "ABP_RifleAnimLayers.uasset")
        assert semantic.format is not None
        assert semantic.format_version is not None

    def test_animbp_asset_meta(self, samples_dir: Path):
        """AnimBlueprint SemanticIR has correct asset metadata."""
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")

        semantic = _build_semantic(samples_dir, "ABP_RifleAnimLayers.uasset")
        assert semantic.asset.package
        assert semantic.asset.name
