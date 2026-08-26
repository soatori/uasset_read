"""Tests for v2 projection — selection, pagination, view/depth."""

from __future__ import annotations

from pathlib import Path
import json
import pytest

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


@pytest.fixture
def doc():
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset"))


class TestSelectObjects:
    def test_select_by_role(self, doc):
        from uasset_read.v2.projection import select_objects
        from uasset_read.v2.object_model import ROLES_ASSET

        asset_objs = select_objects(doc, roles=[ROLES_ASSET])
        assert len(asset_objs) >= 2
        for o in asset_objs:
            assert ROLES_ASSET in o.roles

    def test_select_by_id(self, doc):
        from uasset_read.v2.projection import select_objects

        result = select_objects(doc, object_ids=["export:0", "export:1"])
        assert len(result) == 2
        assert result[0].id == "export:0"
        assert result[1].id == "export:1"

    def test_select_combined(self, doc):
        from uasset_read.v2.projection import select_objects

        result = select_objects(doc, object_ids=["export:0"], roles=["asset"])
        assert len(result) == 0  # export:0 is not an asset

    def test_select_all_when_no_filters(self, doc):
        from uasset_read.v2.projection import select_objects

        result = select_objects(doc)
        assert len(result) == len(doc.objects)


class TestPagination:
    def test_no_limit_returns_all(self):
        from uasset_read.v2.projection import paginate

        items = list(range(10))
        page, next_offset, info = paginate(items, offset=0)
        assert len(page) == 10
        assert next_offset is None
        assert info["truncated"] == 0

    def test_limit_truncates(self):
        from uasset_read.v2.projection import paginate

        items = list(range(10))
        page, next_offset, info = paginate(items, offset=0, limit=3)
        assert len(page) == 3
        assert next_offset == 3
        assert info["truncated"] == 1
        assert info["total"] == 10

    def test_offset_skips(self):
        from uasset_read.v2.projection import paginate

        items = list(range(10))
        page, next_offset, info = paginate(items, offset=5, limit=3)
        assert page == [5, 6, 7]
        assert next_offset == 8

    def test_offset_at_end(self):
        from uasset_read.v2.projection import paginate

        items = list(range(10))
        page, next_offset, info = paginate(items, offset=10)
        assert len(page) == 0
        assert next_offset is None


class TestProjectDocument:
    def test_full_projection(self, doc):
        from uasset_read.v2.projection import project_document

        result = project_document(doc)
        assert result["format"] == "uasset_read.package"
        assert len(result["objects"]) == 10
        assert "summary" in result

    def test_paginated_projection(self, doc):
        from uasset_read.v2.projection import project_document

        result = project_document(doc, limit=3)
        assert len(result["objects"]) == 3
        assert result["next_offset"] == 3
        assert result["truncation"]["total"] == 10

    def test_filtered_projection(self, doc):
        from uasset_read.v2.projection import project_document
        from uasset_read.v2.object_model import ROLES_ASSET

        result = project_document(doc, roles=[ROLES_ASSET])
        assert len(result["objects"]) >= 2
        for obj in result["objects"]:
            assert ROLES_ASSET in obj["roles"]

    def test_json_serializable(self, doc):
        from uasset_read.v2.projection import project_document

        result = project_document(doc, limit=5)
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["format"] == "uasset_read.package"
        assert len(parsed["objects"]) == 5

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
