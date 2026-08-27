"""Tests for v2 Agent tools."""

from __future__ import annotations

from pathlib import Path
import json
import pytest

SAMPLES_DIR = Path(__file__).parent.parent / "samples"

SAMPLE = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")
MULTI_ASSET = str(SAMPLES_DIR / "BP_CombatCharacter.uasset")
SINGLE_ASSET = str(SAMPLES_DIR / "ALS_FootstepDataTable.uasset")


class TestInspectPackage:
    def test_returns_summary(self):
        from uasset_read.v2.agent_tools import inspect_package
        result = inspect_package(SAMPLE)
        assert "source" in result
        assert "package" in result
        assert "summary" in result
        assert result["source"]["name"] == "ABP_RifleAnimLayers.uasset"
        assert result["package"]["layout"] == "legacy"

    def test_multi_asset_summary(self):
        from uasset_read.v2.agent_tools import inspect_package
        result = inspect_package(MULTI_ASSET)
        assert result["summary"]["total_exports"] == 440
        assert len(result["summary"]["asset_object_ids"]) >= 2

    def test_diagnostics_count(self):
        from uasset_read.v2.agent_tools import inspect_package
        result = inspect_package(SAMPLE)
        assert "diagnostics_count" in result
        assert "diagnostics_summary" in result


class TestListObjects:
    def test_list_all(self):
        from uasset_read.v2.agent_tools import list_objects
        result = list_objects(SAMPLE)
        assert result["total"] == 10
        assert result["returned"] == 10
        assert "next_offset" not in result

    def test_paginate(self):
        from uasset_read.v2.agent_tools import list_objects
        result = list_objects(SAMPLE, limit=3)
        assert result["returned"] == 3
        assert result["next_offset"] == 3
        assert result["total"] == 10

    def test_filter_by_role(self):
        from uasset_read.v2.agent_tools import list_objects
        result = list_objects(SAMPLE, roles=["asset"])
        assert result["total"] >= 2
        for obj in result["objects"]:
            assert "asset" in obj["roles"]

    def test_filter_by_class(self):
        from uasset_read.v2.agent_tools import list_objects
        result = list_objects(SAMPLE, classes=["AnimBlueprintGeneratedClass"])
        assert result["total"] >= 1

    def test_page_through(self):
        from uasset_read.v2.agent_tools import list_objects
        all_objs = []
        offset = 0
        while True:
            result = list_objects(SAMPLE, limit=3, offset=offset)
            all_objs.extend(result["objects"])
            if "next_offset" not in result:
                break
            offset = result["next_offset"]
        assert len(all_objs) == 10


class TestGetObject:
    def test_existing_object(self):
        from uasset_read.v2.agent_tools import get_object
        result = get_object(SAMPLE, "export:1")
        assert result["id"] == "export:1"
        assert result["name"] == "ABP_RifleAnimLayers"
        assert "asset" in result["roles"]
        assert "serial_region" in result
        assert "status" in result

    def test_nonexistent_object(self):
        from uasset_read.v2.agent_tools import get_object
        result = get_object(SAMPLE, "export:999")
        assert "error" in result
        assert "available_ids" in result

    def test_object_with_relations(self):
        from uasset_read.v2.agent_tools import get_object
        result = get_object(MULTI_ASSET, "export:1")
        assert result["id"] == "export:1"
        assert "BP_CombatCharacter" in result["name"]


class TestListDependencies:
    def test_returns_dependencies(self):
        from uasset_read.v2.agent_tools import list_dependencies
        result = list_dependencies(SAMPLE)
        assert result["total_dependencies"] == 191
        assert result["total_relations"] > 0
        assert len(result["relations"]) > 0

    def test_pagination(self):
        from uasset_read.v2.agent_tools import list_dependencies
        result = list_dependencies(SAMPLE, limit=10)
        assert result["returned"] == 10
        assert result["next_offset"] == 10


class TestGetDiagnostics:
    def test_returns_diagnostics(self):
        from uasset_read.v2.agent_tools import get_diagnostics
        result = get_diagnostics(SAMPLE)
        assert "diagnostics" in result
        assert "total" in result

    def test_filter_by_severity(self):
        from uasset_read.v2.agent_tools import get_diagnostics
        result = get_diagnostics(SAMPLE, severity="error")
        for d in result["diagnostics"]:
            assert d["severity"] == "error"

    def test_filter_by_object(self):
        from uasset_read.v2.agent_tools import get_diagnostics
        result = get_diagnostics(SAMPLE, object_id="export:0")
        for d in result["diagnostics"]:
            if d.get("object_id"):
                assert d["object_id"] == "export:0"


class TestExtractPayload:
    def test_no_payloads_yet(self):
        from uasset_read.v2.agent_tools import extract_payload
        result = extract_payload(SAMPLE, "payload:0")
        assert "error" in result
        assert "note" in result


class TestJsonSerializable:
    """All tool outputs must be JSON-serializable."""

    @pytest.mark.parametrize("tool_name,args", [
        ("inspect_package", {"file_path": SAMPLE}),
        ("list_objects", {"file_path": SAMPLE, "limit": 3}),
        ("get_object", {"file_path": SAMPLE, "object_id": "export:1"}),
        ("list_dependencies", {"file_path": SAMPLE, "limit": 5}),
        ("get_diagnostics", {"file_path": SAMPLE}),
        ("extract_payload", {"file_path": SAMPLE, "payload_id": "payload:0"}),
    ])
    def test_json_serializable(self, tool_name, args):
        from uasset_read.v2 import agent_tools
        tool_fn = getattr(agent_tools, tool_name)
        result = tool_fn(**args)
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
