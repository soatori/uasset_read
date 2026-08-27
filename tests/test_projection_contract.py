"""Projection contract — view/depth/selection/pagination/max_bytes, no blob by default."""

from __future__ import annotations

from pathlib import Path

import json
import pytest

SAMPLES_DIR = Path(__file__).parent / "samples"
SAMPLE = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")


@pytest.fixture
def doc():
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(SAMPLE)


class TestViewContract:
    def test_semantic_default(self, doc):
        from uasset_read.v2.projection import project_document

        result = project_document(doc)
        assert result["view"] == "semantic"

    def test_raw_has_flags(self, doc):
        from uasset_read.v2.projection import project_document

        result = project_document(doc, view="raw", limit=2)
        for obj in result["objects"]:
            assert "flags" in obj

    def test_debug_has_stats(self, doc):
        from uasset_read.v2.projection import project_document

        result = project_document(doc, view="debug")
        assert "debug" in result
        assert "total_objects" in result["debug"]

    def test_invalid_view_raises(self, doc):
        from uasset_read.v2.projection import project_document

        with pytest.raises(ValueError, match="Invalid view"):
            project_document(doc, view="invalid")

    def test_semantic_no_flags(self, doc):
        from uasset_read.v2.projection import project_document

        result = project_document(doc, view="semantic", limit=2)
        for obj in result["objects"]:
            assert "flags" not in obj


class TestPagination:
    def test_limit_truncates(self):
        from uasset_read.v2.projection import paginate

        items = list(range(10))
        page, next_offset, info = paginate(items, offset=0, limit=3)
        assert len(page) == 3
        assert next_offset == 3
        assert info["truncated"] == 1

    def test_offset_skips(self):
        from uasset_read.v2.projection import paginate

        items = list(range(10))
        page, next_offset, info = paginate(items, offset=5, limit=3)
        assert page == [5, 6, 7]
        assert next_offset == 8

    def test_no_limit_returns_all(self):
        from uasset_read.v2.projection import paginate

        items = list(range(10))
        page, next_offset, info = paginate(items, offset=0)
        assert len(page) == 10
        assert next_offset is None
        assert info["truncated"] == 0

    def test_page_through_all(self, doc):
        from uasset_read.v2.projection import project_document

        all_objects = []
        offset = 0
        while True:
            result = project_document(doc, limit=3, offset=offset)
            all_objects.extend(result["objects"])
            if "next_offset" not in result:
                break
            offset = result["next_offset"]
        assert len(all_objects) == len(doc.objects)


class TestSelection:
    def test_select_by_role(self, doc):
        from uasset_read.v2.projection import select_objects

        asset_objs = select_objects(doc, roles=["asset"])
        assert len(asset_objs) >= 2

    def test_select_by_id(self, doc):
        from uasset_read.v2.projection import select_objects

        result = select_objects(doc, object_ids=["export:0", "export:1"])
        assert len(result) == 2

    def test_select_all_when_no_filters(self, doc):
        from uasset_read.v2.projection import select_objects

        result = select_objects(doc)
        assert len(result) == len(doc.objects)


class TestJsonSerializable:
    def test_all_views_json(self, doc):
        from uasset_read.v2.projection import project_document

        for view in ("semantic", "raw", "debug"):
            result = project_document(doc, view=view, limit=3)
            json_str = json.dumps(result, ensure_ascii=False)
            parsed = json.loads(json_str)
            assert parsed["view"] == view
