"""Consolidated renderer tests — registry, consistency.

Merges tests from:
- tests/test_renderer_consistency.py
- tests/core/test_renderers.py
"""
from __future__ import annotations

import json

import pytest

from uasset_read.renderers import get_renderer, list_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    LinkerSummaryIR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_header(**kwargs) -> PackageHeaderIR:
    defaults = dict(
        package_name="/Game/Test/BP_Test",
        package_class="BP_Test_C",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.3",
    )
    defaults.update(kwargs)
    return PackageHeaderIR(**defaults)


def _make_export(**kwargs) -> ExportIR:
    defaults = dict(
        index=0,
        object_name="BP_Test_C",
        object_class="BlueprintGeneratedClass",
        serial_size=1024,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class="/Engine/Actor",
        properties=[],
        graphs=[],
        bulk_data=None,
    )
    defaults.update(kwargs)
    return ExportIR(**defaults)


def _make_ir(**kwargs) -> PackageIR:
    defaults = dict(
        header=_make_header(),
        name_map=[],
        imports=[],
        exports=[_make_export()],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


# ---------------------------------------------------------------------------
# Test 1: Renderer registry (list_formats, get_renderer, error handling)
# ---------------------------------------------------------------------------

class TestRendererRegistry:
    """Renderer registry, format dispatch, and error handling."""

    def test_registry_has_markdown(self):
        formats = list_formats()
        assert "markdown" in formats
        assert formats == sorted(formats)
        assert isinstance(get_renderer("markdown"), MarkdownRenderer)

    def test_json_not_in_renderer_registry(self):
        """JSON format routes through semantic pipeline, not renderer registry."""
        formats = list_formats()
        assert "json" not in formats

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent_format")


# ---------------------------------------------------------------------------
# Test 2: Markdown filtering consistency
# ---------------------------------------------------------------------------

class TestRendererConsistency:
    """Markdown renderer filters editor-internal data."""

    def test_editor_variable_filtered_in_markdown(self):
        from uasset_read.models.ir import VariableIR
        variables = [VariableIR(name="UbergraphPages", type="bool", default_value="False", kind="user")]
        ir = _make_ir(variables=variables)
        md_result = get_renderer("markdown").render(ir, RenderOptions())
        assert "UbergraphPages" not in md_result
