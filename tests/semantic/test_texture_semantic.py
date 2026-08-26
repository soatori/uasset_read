"""Texture semantic extractor tests.

Tests the Texture domain extractor with real Texture samples.
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


_TEXTURE_SAMPLES = [
    "FirstPerson_T_GridChecker_A.uasset",
    "MutableSample_GrayLightTextureCube.uasset",
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


class TestTextureSemanticExtraction:
    """Texture semantic extractor output validation."""

    @pytest.mark.parametrize(
        "filename",
        _TEXTURE_SAMPLES,
        ids=[s.split(".")[0] for s in _TEXTURE_SAMPLES],
    )
    def test_texture_has_semantic_ir(self, samples_dir: Path, filename: str):
        """Texture sample produces a valid SemanticIR."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic is not None
        assert semantic.asset_type == "texture"
        assert semantic.asset.name != "unknown"

    @pytest.mark.parametrize(
        "filename",
        _TEXTURE_SAMPLES,
        ids=[s.split(".")[0] for s in _TEXTURE_SAMPLES],
    )
    def test_texture_format(self, samples_dir: Path, filename: str):
        """Texture uses the texture_semantic domain format."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.format == "uasset_read.texture_semantic"
        assert semantic.format_version == "1.0.0"

    @pytest.mark.parametrize(
        "filename",
        _TEXTURE_SAMPLES,
        ids=[s.split(".")[0] for s in _TEXTURE_SAMPLES],
    )
    def test_texture_has_content(self, samples_dir: Path, filename: str):
        """Texture SemanticIR has non-empty content with texture key."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_semantic(samples_dir, filename)
        assert semantic.content, f"{filename}: content is empty"
        assert "texture" in semantic.content, f"{filename}: missing texture key"


class TestTextureValidation:
    """Texture validator rules."""

    @pytest.mark.parametrize(
        "filename",
        _TEXTURE_SAMPLES,
        ids=[s.split(".")[0] for s in _TEXTURE_SAMPLES],
    )
    def test_texture_passes_validation(self, samples_dir: Path, filename: str):
        """Texture SemanticIR passes validation."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename)
        errors = validate_semantic_document(semantic)
        assert errors == [], f"Validation errors: {errors}"


class TestTextureSchemaConformance:
    """Schema conformance for Texture semantic JSON."""

    @pytest.mark.parametrize(
        "filename",
        _TEXTURE_SAMPLES,
        ids=[s.split(".")[0] for s in _TEXTURE_SAMPLES],
    )
    def test_standard_output_schema_valid(self, samples_dir: Path, filename: str):
        """Standard mode output validates against schema."""
        if not (samples_dir / filename).exists():
            pytest.skip(f"Sample not found: {filename}")

        semantic = _build_and_project(samples_dir, filename, "standard")
        json_str = render_semantic_json(semantic, include_schema=True)
        data = json.loads(json_str)

        assert data["format"] == "uasset_read.texture_semantic"
        assert "$schema" in data
        assert "texture_semantic.schema.json" in data["$schema"]
        # texture key present only when content has non-empty values
        # (renderer strips empty dicts via _strip_none_and_empty)
        if semantic.content and any(v for v in semantic.content.values() if v):
            assert "texture" in data


class TestTextureProjection:
    """Texture projection (standard vs debug mode)."""

    def test_standard_strips_evidence(self, samples_dir: Path):
        """Standard mode strips evidence from Texture output."""
        semantic = _build_and_project(
            samples_dir, "FirstPerson_T_GridChecker_A.uasset", "standard",
        )
        assert len(semantic.evidence) == 0

    def test_debug_keeps_evidence(self, samples_dir: Path):
        """Debug mode keeps evidence in Texture output."""
        semantic = _build_and_project(
            samples_dir, "FirstPerson_T_GridChecker_A.uasset", "debug",
        )
        assert semantic.mode == "debug"


# ---------------------------------------------------------------------------
# Renderer contract tests (merged from tests/renderers/test_texture_semantic.py)
# ---------------------------------------------------------------------------

_MUTABLE_SAMPLE_ROOT = Path("E:/Develop/lib/Samples/MutableSample/Content")
_TEXTURE2D_REL = "Character/Body/BlendShapes/Normals/T_MatBody_Normal_Fat.uasset"
_TEXTURECUBE_REL = "Lobby/SceneElements/GrayLightTextureCube.uasset"


def _resolve_mutable_path(rel_path: str) -> Path | None:
    """Resolve a MutableSample asset path."""
    mutable_path = _MUTABLE_SAMPLE_ROOT / rel_path
    if mutable_path.exists():
        return mutable_path
    return None


class TestTextureCubeRendererContract:
    """TextureCube renderer contract tests (#591)."""

    def test_texture_cube_has_texture_block(self, samples_dir: Path):
        """TextureCube output includes a texture block."""
        asset_path = _resolve_mutable_path(_TEXTURECUBE_REL)
        if asset_path is None:
            pytest.skip("TextureCube MutableSample not found")
        result = parse_uasset_with_linker(str(asset_path), tolerant=True)
        ir = build_package_ir(result)
        semantic = build_semantic_ir(ir, source_path=str(asset_path))
        assert "texture" in semantic.content
        tex = semantic.content["texture"]
        assert "resource_properties" in tex

    def test_texture_cube_face_count(self, samples_dir: Path):
        """TextureCube texture block includes cube_face_count=6."""
        asset_path = _resolve_mutable_path(_TEXTURECUBE_REL)
        if asset_path is None:
            pytest.skip("TextureCube MutableSample not found")
        result = parse_uasset_with_linker(str(asset_path), tolerant=True)
        ir = build_package_ir(result)
        semantic = build_semantic_ir(ir, source_path=str(asset_path))
        tex = semantic.content.get("texture", {})
        rp = tex.get("resource_properties", {})
        assert rp.get("cube_face_count") == 6


@pytest.mark.skip(reason="Texture2D MutableSample (26MB) exceeds 16MB memory budget")
class TestTexture2DRendererContract:
    """Texture2D renderer contract tests — skipped until memory budget resolved."""

    def test_texture2d_has_texture_block(self):
        pass
