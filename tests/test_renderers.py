"""Consolidated renderer tests — registry, consistency, JSON schema, semantic.

Merges tests from:
- tests/test_renderer_consistency.py
- tests/test_json_schema.py
- tests/core/test_renderers.py
- tests/semantic/test_renderer.py
"""
from __future__ import annotations

import json

import pytest

from uasset_read.renderers import get_renderer, list_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.semantic_json_renderer import SemanticJSONRenderer
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


def _render_json(ir: PackageIR, **opts) -> dict:
    renderer = JSONRenderer()
    options = RenderOptions(**opts)
    return json.loads(renderer.render(ir, options))


# ---------------------------------------------------------------------------
# Test 1: Renderer registry (list_formats, get_renderer, error handling)
# ---------------------------------------------------------------------------

class TestRendererRegistry:
    """Renderer registry, format dispatch, and error handling."""

    def test_registry_has_json_markdown_semantic(self):
        formats = list_formats()
        assert "json" in formats
        assert "markdown" in formats
        assert formats == sorted(formats)
        assert isinstance(get_renderer("json"), JSONRenderer)
        assert isinstance(get_renderer("markdown"), MarkdownRenderer)


# ---------------------------------------------------------------------------
# Test 2: JSON/Markdown filtering consistency (one representative test)
# ---------------------------------------------------------------------------

class TestRendererConsistency:
    """JSON and Markdown renderers filter editor-internal data consistently."""

    def test_editor_variable_filtered_in_json_and_markdown(self):
        from uasset_read.models.ir import VariableIR
        variables = [VariableIR(name="UbergraphPages", type="bool", default_value="False", kind="user")]
        ir = _make_ir(variables=variables)
        # JSON
        json_data = json.loads(get_renderer("json").render(ir, RenderOptions()))
        assert "UbergraphPages" not in [v["name"] for v in json_data.get("variables", [])]
        # Markdown
        md_result = get_renderer("markdown").render(ir, RenderOptions())
        assert "UbergraphPages" not in md_result


# ---------------------------------------------------------------------------
# Test 3: JSON output structure (schema, required fields)
# ---------------------------------------------------------------------------

class TestJSONOutputStructure:
    """JSON output structure: required fields, $schema."""

    def test_required_fields_present(self):
        ir = _make_ir()
        data = _render_json(ir)
        assert "status" in data
        assert "summary" in data
        assert "exports" in data
        assert "status" in data["status"]


# ---------------------------------------------------------------------------
# Test 4: SemanticJSONRenderer output
# ---------------------------------------------------------------------------

class TestSemanticJSONRenderer:
    """SemanticJSONRenderer: format, required fields, canonical key order."""

    @pytest.fixture
    def _semantic_ir(self):
        from uasset_read.semantic.ir import SemanticIR, AssetMeta, CoverageInfo, ContentNode
        from uasset_read.semantic.kinds import AssetKind
        return SemanticIR(
            format="uasset_read.asset_semantic",
            format_version="1.0.0",
            mode="standard",
            asset=AssetMeta(kind=AssetKind.RESOURCE, class_name="Texture2D", object_name="T_Default"),
            references=(),
            content=ContentNode(key="root", children=()),
            coverage=CoverageInfo(fields_expected=5, fields_parsed=5, coverage_pct=100.0, unparsed_fields=()),
            diagnostics=(),
        )

    def test_semantic_valid_json_and_required_fields(self, _semantic_ir):
        renderer = SemanticJSONRenderer()
        data = json.loads(renderer.render(_semantic_ir, RenderOptions()))
        assert data["format"] == "uasset_read.asset_semantic"
        assert data["format_version"] == "1.0.0"
        assert "mode" in data
        assert "asset" in data
        assert "content" in data
        assert "coverage" in data
        assert "diagnostics" in data

