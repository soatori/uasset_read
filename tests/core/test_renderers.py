"""Renderer core tests -- registry, format dispatch, Markdown basic output."""
from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock

import pytest

from uasset_read.renderers import (
    RENDERER_REGISTRY,
    get_renderer,
    list_formats,
)
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
)


def _make_mock_ir(
    package_name: str = "/Game/Test/BP_Test",
    package_class: str = "BP_Test_C",
    package_flags: int = 0,
    export_count: int = 0,
    import_count: int = 0,
    ue_version: str = "5.4.0",
) -> PackageIR:
    """Create a minimal mock PackageIR for renderer tests."""
    header = PackageHeaderIR(
        package_name=package_name,
        package_class=package_class,
        package_flags=package_flags,
        total_export_count=export_count,
        total_import_count=import_count,
        ue_version=ue_version,
    )
    exports = []
    for i in range(export_count):
        exports.append(MagicMock(
            object_name=f"Export_{i}",
            object_class="None",
            serial_size=100,
            properties=[],
            graphs=[],
            parse_status="success",
            fallback_reason=None,
            error_message=None,
            parent_class=None,
        ))
    return PackageIR(
        header=header,
        name_map=(),
        imports=[],
        exports=exports,
        linker=None,
    )


class TestRendererRegistry:
    """Renderer registry tests."""

    def test_registry_has_markdown(self):
        """Registry should contain markdown format and return correct type instance."""
        assert "markdown" in RENDERER_REGISTRY
        assert isinstance(get_renderer("markdown"), MarkdownRenderer)
        # Renderer-level list_formats returns only renderer-registered formats
        formats = list_formats()
        assert "markdown" in formats
        assert formats == sorted(formats)

    def test_json_not_in_renderer_registry(self):
        """json format is no longer in the renderer registry (uses semantic pipeline)."""
        assert "json" not in RENDERER_REGISTRY

    def test_get_unknown_renderer_raises(self):
        """Getting a non-existent format should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent_format")


class TestMarkdownRenderer:
    """Markdown renderer basic tests."""

    def test_render_produces_heading_with_package_info(self):
        """Markdown renderer output should start with # heading, containing asset name, UE version, and class."""
        ir = _make_mock_ir(ue_version="5.4.0")
        renderer = get_renderer("markdown")
        options = RenderOptions()
        output = renderer.render(ir, options)
        assert output.startswith("# ")
        assert "BP_Test" in output
        assert "5.4.0" in output
        assert "BP_Test_C" in output
