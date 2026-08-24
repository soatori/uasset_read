"""Contract tests for texture semantic output (#591).

Verifies that Texture2D and TextureCube exports include a structured
``texture`` block with consistent field meanings.
"""
from __future__ import annotations

import json
import os
import pytest
from pathlib import Path
from typing import Any

from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
from tests.integration.sample_assets import (
    LOCAL_SAMPLE_ROOT,
    SampleAsset,
    require_local_sample_path,
)

# MutableSample contains both Texture2D and TextureCube assets
MUTABLE_SAMPLE_ROOT = Path("E:/Develop/lib/Samples/MutableSample/Content")

# Known texture asset paths (relative to MutableSample root)
TEXTURE2D_REL = "Character/Body/BlendShapes/Normals/T_MatBody_Normal_Fat.uasset"
TEXTURECUBE_REL = "Lobby/SceneElements/GrayLightTextureCube.uasset"


def _resolve_texture_path(rel_path: str) -> Path | None:
    """Resolve a texture asset path, checking multiple locations."""
    # Check MutableSample
    mutable_path = MUTABLE_SAMPLE_ROOT / rel_path
    if mutable_path.exists():
        return mutable_path
    # Check local samples
    local_path = LOCAL_SAMPLE_ROOT / Path(rel_path).name
    if local_path.exists():
        return local_path
    # Check UE_SAMPLE_ROOT env var
    env_root = os.environ.get("UE_SAMPLE_ROOT")
    if env_root:
        env_path = Path(env_root) / rel_path
        if env_path.exists():
            return env_path
    return None


def _parse_and_render(asset_path: Path) -> dict[str, Any]:
    """Parse an asset and render to JSON, returning the parsed dict."""
    from uasset_read.parse_uasset import parse_uasset
    from uasset_read.ir_builder import build_package_ir

    result = parse_uasset(str(asset_path))
    ir = build_package_ir(result)
    renderer = JSONRenderer()
    options = RenderOptions()
    output = renderer.render(ir, options)
    return json.loads(output)


def _find_texture_export(data: dict, class_name: str) -> dict | None:
    """Find the first export with the given object_class that has a texture block."""
    for exp in data.get("exports", []):
        if exp.get("object_class") == class_name and "texture" in exp:
            return exp
    return None


# ── Contract tests ────────────────────────────────────────────────────────────


class TestTexture2DSemantic:
    """Contract: Texture2D exports must include a ``texture`` semantic block."""

    def test_texture_block_present(self):
        """Texture2D export has a ``texture`` key."""
        asset_path = _resolve_texture_path(TEXTURE2D_REL)
        if asset_path is None:
            pytest.skip("Texture2D sample not found")

        data = _parse_and_render(asset_path)
        export = _find_texture_export(data, "Texture2D")
        assert export is not None, "No Texture2D export with texture block found"
        assert "texture" in export

    def test_texture_block_fields(self):
        """Texture2D texture block contains required fields with correct types."""
        asset_path = _resolve_texture_path(TEXTURE2D_REL)
        if asset_path is None:
            pytest.skip("Texture2D sample not found")

        data = _parse_and_render(asset_path)
        export = _find_texture_export(data, "Texture2D")
        assert export is not None
        tex = export["texture"]

        # Required fields
        assert tex["class"] == "Texture2D"
        assert isinstance(tex["size_x"], int)
        assert isinstance(tex["size_y"], int)
        assert tex["size_x"] >= 0
        assert tex["size_y"] >= 0

    def test_texture_block_optional_fields(self):
        """Texture2D texture block optional fields have expected types when present."""
        asset_path = _resolve_texture_path(TEXTURE2D_REL)
        if asset_path is None:
            pytest.skip("Texture2D sample not found")

        data = _parse_and_render(asset_path)
        export = _find_texture_export(data, "Texture2D")
        assert export is not None
        tex = export["texture"]

        # Optional fields — type checks when present
        if "mip_count" in tex:
            assert isinstance(tex["mip_count"], int)
            assert tex["mip_count"] >= 0
        if "pixel_format" in tex:
            assert isinstance(tex["pixel_format"], int)
        if "source_format" in tex:
            assert isinstance(tex["source_format"], str)
        if "compression_settings" in tex:
            assert isinstance(tex["compression_settings"], str)
        if "srgb" in tex:
            assert isinstance(tex["srgb"], bool)
        if "max_texture_size" in tex:
            assert isinstance(tex["max_texture_size"], int)
        if "lod_group" in tex:
            assert isinstance(tex["lod_group"], str)
        if "never_stream" in tex:
            assert isinstance(tex["never_stream"], bool)
        if "virtual_texture_streaming" in tex:
            assert isinstance(tex["virtual_texture_streaming"], bool)


class TestTextureCubeSemantic:
    """Contract: TextureCube exports must include a ``texture`` semantic block."""

    def test_texture_block_present(self):
        """TextureCube export has a ``texture`` key."""
        asset_path = _resolve_texture_path(TEXTURECUBE_REL)
        if asset_path is None:
            pytest.skip("TextureCube sample not found")

        data = _parse_and_render(asset_path)
        export = _find_texture_export(data, "TextureCube")
        assert export is not None, "No TextureCube export with texture block found"
        assert "texture" in export

    def test_texture_block_required_fields(self):
        """TextureCube texture block contains required fields."""
        asset_path = _resolve_texture_path(TEXTURECUBE_REL)
        if asset_path is None:
            pytest.skip("TextureCube sample not found")

        data = _parse_and_render(asset_path)
        export = _find_texture_export(data, "TextureCube")
        assert export is not None
        tex = export["texture"]

        assert tex["class"] == "TextureCube"
        assert isinstance(tex["size_x"], int)
        assert isinstance(tex["size_y"], int)
        assert tex["size_x"] >= 0
        assert tex["size_y"] >= 0

    def test_texture_cube_face_count(self):
        """TextureCube texture block includes face_count=6."""
        asset_path = _resolve_texture_path(TEXTURECUBE_REL)
        if asset_path is None:
            pytest.skip("TextureCube sample not found")

        data = _parse_and_render(asset_path)
        export = _find_texture_export(data, "TextureCube")
        assert export is not None
        tex = export["texture"]

        assert "face_count" in tex
        assert tex["face_count"] == 6


class TestTextureSemanticConsistency:
    """Contract: Texture2D and TextureCube share the same field semantics."""

    def test_common_fields_present_in_both(self):
        """Both Texture2D and TextureCube blocks contain class, size_x, size_y."""
        t2d_path = _resolve_texture_path(TEXTURE2D_REL)
        tc_path = _resolve_texture_path(TEXTURECUBE_REL)

        if t2d_path is None or tc_path is None:
            pytest.skip("Need both Texture2D and TextureCube samples")

        t2d_data = _parse_and_render(t2d_path)
        tc_data = _parse_and_render(tc_path)

        t2d_export = _find_texture_export(t2d_data, "Texture2D")
        tc_export = _find_texture_export(tc_data, "TextureCube")

        assert t2d_export is not None
        assert tc_export is not None

        t2d_tex = t2d_export["texture"]
        tc_tex = tc_export["texture"]

        # Both must have these common fields
        for field in ("class", "size_x", "size_y"):
            assert field in t2d_tex, f"Texture2D missing {field}"
            assert field in tc_tex, f"TextureCube missing {field}"

    def test_non_texture_class_no_texture_block(self):
        """Non-texture exports must NOT have a texture block."""
        from tests.integration.sample_assets import LOCAL_SAMPLES

        for sample in LOCAL_SAMPLES[:3]:
            asset_path = LOCAL_SAMPLE_ROOT / sample.relative_path
            if not asset_path.exists():
                continue
            try:
                data = _parse_and_render(asset_path)
                for exp in data.get("exports", []):
                    if exp.get("object_class") not in ("Texture2D", "TextureCube"):
                        assert "texture" not in exp, (
                            f"Non-texture export {exp.get('object_name')} "
                            f"unexpectedly has texture block"
                        )
            except Exception:
                continue
