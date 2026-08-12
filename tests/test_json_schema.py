"""JSON Schema integration tests -- verify semantic output structure."""
from __future__ import annotations

import json

import pytest

from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.render import render_semantic_json
from uasset_read.semantic.validator import validate_semantic_document


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_header() -> PackageHeaderIR:
    return PackageHeaderIR(
        package_name="/Game/Test/BP_Test",
        package_class="BP_Test_C",
        package_flags=0,
        total_export_count=1,
        total_import_count=1,
        ue_version="5.3",
    )


def _make_minimal_ir(**kwargs) -> PackageIR:
    """Construct a minimal PackageIR."""
    defaults = dict(
        header=_make_header(),
        name_map=["BP_Test"],
        imports=[],
        exports=[],
        linker=None,
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


def _render_json(ir: PackageIR, output_level: str = "standard") -> dict:
    """Render IR through the semantic pipeline and return as dict."""
    semantic_ir = build_semantic_ir(ir)
    semantic_ir = project_semantic(semantic_ir, output_level)
    output = render_semantic_json(semantic_ir)
    return json.loads(output)


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestSemanticOutputVersion:
    """Verify semantic JSON output uses format_version instead of output_version."""

    def test_no_output_version_default(self):
        """Default rendering should not contain output_version field."""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "output_version" not in data
        assert "format_version" in data

    def test_no_output_version_debug(self):
        """Debug mode should not contain output_version field."""
        ir = _make_minimal_ir()
        data = _render_json(ir, output_level="debug")
        assert "output_version" not in data
        assert "format_version" in data


class TestSchemaReference:
    """Verify $schema reference when include_schema=True."""

    def test_schema_reference_included(self):
        """When include_schema=True, $schema should be included."""
        ir = _make_minimal_ir()
        semantic_ir = build_semantic_ir(ir)
        semantic_ir = project_semantic(semantic_ir, "standard")
        output = render_semantic_json(semantic_ir, include_schema=True)
        data = json.loads(output)
        assert "$schema" in data
        assert "semantic.schema.json" in data["$schema"]

    def test_schema_reference_absent_by_default(self):
        """By default, $schema should not be included."""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "$schema" not in data

    def test_schema_reference_absent_when_false(self):
        """When include_schema=False, $schema should not be included."""
        ir = _make_minimal_ir()
        semantic_ir = build_semantic_ir(ir)
        semantic_ir = project_semantic(semantic_ir, "standard")
        output = render_semantic_json(semantic_ir, include_schema=False)
        data = json.loads(output)
        assert "$schema" not in data


class TestRequiredFields:
    """Verify semantic JSON output has required fields."""

    def test_has_format_status_and_asset(self):
        """Output should contain format, status, and asset keys."""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "format" in data
        assert "status" in data
        assert "asset" in data

    def test_status_structure(self):
        """status field should contain parse and representation."""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "parse" in data["status"]
        assert "representation" in data["status"]

    def test_validation_passes(self):
        """Semantic IR should pass validation."""
        ir = _make_minimal_ir()
        semantic_ir = build_semantic_ir(ir)
        semantic_ir = project_semantic(semantic_ir, "standard")
        errors = validate_semantic_document(semantic_ir)
        assert errors == []
