"""Tests for v2 projection — raw/debug views."""

from __future__ import annotations

from pathlib import Path
import json
import pytest

SAMPLES_DIR = Path(__file__).parent.parent / "samples"

SAMPLE = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")


class TestRawView:
    def test_raw_view_has_flags(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        result = project_document(doc, view="raw", limit=2)
        for obj in result["objects"]:
            assert "flags" in obj

    def test_raw_view_has_total_header_size(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        result = project_document(doc, view="raw")
        assert "total_header_size" in result["package"]

    def test_raw_view_string(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        result = project_document(doc, view="raw")
        assert result["view"] == "raw"


class TestDebugView:
    def test_debug_view_has_flags(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        result = project_document(doc, view="debug", limit=2)
        for obj in result["objects"]:
            assert "flags" in obj

    def test_debug_view_has_debug_stats(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        result = project_document(doc, view="debug")
        assert "debug" in result
        assert "total_objects" in result["debug"]
        assert "total_relations" in result["debug"]
        assert "total_diagnostics" in result["debug"]
        assert "object_diagnostics" in result["debug"]

    def test_debug_view_string(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        result = project_document(doc, view="debug")
        assert result["view"] == "debug"


class TestViewConsistency:
    def test_all_views_json_serializable(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        for view in ("semantic", "raw", "debug"):
            result = project_document(doc, view=view, limit=3)
            json_str = json.dumps(result, ensure_ascii=False)
            parsed = json.loads(json_str)
            assert parsed["view"] == view

    def test_invalid_view_raises(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        with pytest.raises(ValueError, match="Invalid view"):
            project_document(doc, view="invalid")

    def test_semantic_no_flags(self):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE)
        result = project_document(doc, view="semantic", limit=2)
        for obj in result["objects"]:
            assert "flags" not in obj
