# tests/test_output_v4.py
"""v4 package output: one producer, exactly ``normal`` and ``debug`` modes.

The frozen contract lives in ``tests/test_contract_v4.py`` and
``docs/designs/contract/package_document_v4.schema.json``. This file asserts
the production producer's envelope shapes against real fixture documents.
"""

from __future__ import annotations

import copy
import json

import pytest

from tests.fixtures import find_blueprint_object, parse_sample, sample_path
from uasset_read.projection import FORMAT_VERSION, project_document
from uasset_read.projections.bundle import write_projected_document

# Retired C++/builder kinds and media prefixes, assembled without re-introducing
# the banned literal tokens into tracked source.
_CPP_KIND_TOKEN = "cpp"
_EDITOR_BUILDER_TOKEN = "editor_builder"
_CPP_MEDIA_PREFIX = "text/x-c"

# Contract-banned evidence key names (SemanticValue.propertyNames): never
# under objects[].semantic in either mode.
_BANNED_SEMANTIC_EVIDENCE_KEYS = (
    "source_range",
    "script_source_range",
    "raw_region",
    "tag_range",
    "value_range",
    "raw_data",
)

_TOP_LEVEL_KEYS = {
    "format",
    "format_version",
    "mode",
    "source",
    "package",
    "summary",
    "objects",
    "relations",
    "dependencies",
    "projections",
    "payloads",
    "sidecars",
    "diagnostics",
}

_DEBUG_KEYS = {
    "object_regions",
    "property_evidence",
    "semantic_source_ranges",
    "payload_sources",
    "sidecar_sources",
    "diagnostic_details",
    "byte_accounting",
}


def test_normal_and_debug_envelopes_from_one_producer(stackobot_document, tmp_path):
    normal = project_document(stackobot_document)
    debug = project_document(stackobot_document, mode="debug")
    assert normal["mode"] == "normal"
    assert debug["mode"] == "debug"
    assert "view" not in normal and "depth" not in normal
    output_path = write_projected_document(stackobot_document, tmp_path / "doc.json")
    assert json.loads(output_path.read_text(encoding="utf-8")) == normal


def test_top_level_keys_are_the_v4_envelope(stackobot_document):
    normal = project_document(stackobot_document)
    assert FORMAT_VERSION == "4.0"
    assert normal["format"] == "uasset_read.package"
    assert normal["format_version"] == "4.0"
    assert set(normal) == _TOP_LEVEL_KEYS
    debug = project_document(stackobot_document, mode="debug")
    assert set(debug) == _TOP_LEVEL_KEYS | {"debug"}


def test_debug_is_normal_plus_evidence(stackobot_document):
    normal = project_document(stackobot_document)
    debug = project_document(stackobot_document, mode="debug")
    stripped = copy.deepcopy(debug)
    stripped.pop("debug")
    stripped["mode"] = "normal"
    assert stripped == normal


def test_debug_block_has_exactly_seven_arrays(stackobot_document):
    debug = project_document(stackobot_document, mode="debug")
    assert set(debug["debug"]) == _DEBUG_KEYS
    for key in _DEBUG_KEYS:
        assert isinstance(debug["debug"][key], list)


def test_objects_carry_ordered_property_entries(stackobot_document):
    normal = project_document(stackobot_document)
    assert {item["id"] for item in normal["objects"]} == {obj.id for obj in stackobot_document.objects}
    for item in normal["objects"]:
        assert set(item) <= {
            "id",
            "table_index",
            "name",
            "class",
            "roles",
            "status",
            "properties",
            "semantic",
            "coverage",
        }
        assert "flags" not in item
        assert "serial_region" not in item
        assert "properties_summary" not in item
        assert isinstance(item["properties"], list)
        occurrences: dict[str, int] = {}
        for prop in item["properties"]:
            assert set(prop) == {"name", "type", "occurrence", "array_index", "value"}
            assert prop["occurrence"] == occurrences.get(prop["name"], 0)
            occurrences[prop["name"]] = prop["occurrence"] + 1


def test_diagnostics_are_summaries_and_details_live_in_debug(stackobot_document):
    normal = project_document(stackobot_document)
    for diag in normal["diagnostics"]:
        assert set(diag) <= {
            "severity",
            "code",
            "message",
            "stage",
            "count",
            "object_id",
            "property_path",
            "effect",
        }
        assert diag["count"] >= 1
    debug = project_document(stackobot_document, mode="debug")
    details = debug["debug"]["diagnostic_details"]
    for detail in details:
        assert set(detail) <= {"index", "offset", "size", "reason", "fallback", "recoverable"}
        assert detail["index"] < len(debug["diagnostics"])


def test_payloads_stay_referenced_and_sources_are_debug_evidence():
    document = parse_sample("T_ParserBulk.uasset", depth="decode")
    normal = project_document(document)
    export = next(obj for obj in document.objects if obj.id == "export:0")
    assert export.serial_region is not None
    payload = next(item for item in normal["payloads"] if item["owner"] == export.id)
    assert set(payload) <= {"id", "owner", "kind", "stored_size", "status", "logical_size", "compression", "hash"}
    assert payload["id"] == f"payload:{export.id}"
    assert payload["stored_size"] > 0

    debug = project_document(document, mode="debug")
    source = next(item for item in debug["debug"]["payload_sources"] if item["payload_id"] == payload["id"])
    physical = export.serial_region.source_slices[0]
    assert physical.source_id.endswith(".uexp")
    assert source["offset"] == physical.source_start
    assert source["source_region"]["start"] == export.serial_region.start
    assert source["source_region"]["size"] == export.serial_region.size


def test_byte_accounting_lives_under_debug(stackobot_document):
    debug = project_document(stackobot_document, mode="debug")
    scopes = debug["debug"]["byte_accounting"]
    assert scopes
    for scope in scopes:
        assert scope["object_id"].startswith("export:")
        assert scope["window"]["size"] >= 0
        assert scope["leaves"]
        for leaf in scope["leaves"]:
            assert leaf["size"] > 0
            assert leaf["status"] in {"decoded", "opaque", "payload", "unavailable"}


def test_partial_documents_are_rejected():
    partial = parse_sample("StackOBot_BP_Drone.uasset", depth="decode", object_ids=["export:0"])
    with pytest.raises(ValueError, match="all exports"):
        project_document(partial)
    shallow = parse_sample("StackOBot_BP_Drone.uasset", depth="package")
    with pytest.raises(ValueError, match="depth"):
        project_document(shallow)


def test_invalid_modes_are_rejected(stackobot_document):
    for mode in ("agent", "raw", "semantic", "view", "depth"):
        with pytest.raises(ValueError, match="mode"):
            project_document(stackobot_document, mode=mode)


def test_blueprint_semantic_keeps_ir_cfg_calls_reads_writes(stackobot_document):
    normal = project_document(stackobot_document)
    bp = find_blueprint_object(stackobot_document)
    entry = next(item for item in normal["objects"] if item["id"] == bp.id)
    semantic = entry["semantic"]
    functions = semantic["functions"]
    assert functions
    assert any(fn.get("instructions") for fn in functions)
    assert any((fn.get("cfg") or {}).get("blocks") for fn in functions)
    assert any(fn.get("calls") for fn in functions)
    assert any(fn.get("reads") for fn in functions)
    assert any(fn.get("writes") for fn in functions)
    for fn in functions:
        assert "cpp_code" not in fn


def test_no_projection_is_cpp_typed_or_a_retired_builder_kind(stackobot_document):
    for mode in ("normal", "debug"):
        projected = project_document(stackobot_document, mode=mode)
        for record in projected["projections"]:
            assert _CPP_KIND_TOKEN not in record["kind"]
            assert _EDITOR_BUILDER_TOKEN not in record["kind"]
            assert not record["media_type"].startswith(_CPP_MEDIA_PREFIX)


def test_projections_are_embedded_with_provenance():
    # Families that project carry embedded content with provenance. (The
    # blueprint family emits no records at all — see the retired-kind test.)
    table = parse_sample("FirstPerson_DT_WeaponList.uasset", depth="decode")
    normal = project_document(table)
    assert normal["projections"]
    for record in normal["projections"]:
        assert record["embedded"] is True
        assert record["completeness"] in {"complete", "partial", "opaque", "unavailable", "failed"}
        assert record["provenance"]["derived_from"]
        assert record["provenance"]["generator"]


def _evidence_key_hits(value, hits: list[str], pointer: str = "") -> None:
    """Record JSON pointers of contract-banned evidence keys at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{pointer}/{key}"
            if key in _BANNED_SEMANTIC_EVIDENCE_KEYS:
                hits.append(child)
            _evidence_key_hits(item, hits, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _evidence_key_hits(item, hits, f"{pointer}/{index}")


def test_semantic_carries_no_evidence_keys_in_either_mode(stackobot_document):
    for mode in ("normal", "debug"):
        projected = project_document(stackobot_document, mode=mode)
        for obj in projected["objects"]:
            semantic = obj.get("semantic")
            if semantic is None:
                continue
            hits: list[str] = []
            _evidence_key_hits(semantic, hits)
            assert hits == [], f"{mode}:{obj['id']} semantic still carries evidence keys: {hits}"


def test_removed_semantic_ranges_land_in_debug_semantic_source_ranges(stackobot_document):
    debug = project_document(stackobot_document, mode="debug")
    entries = debug["debug"]["semantic_source_ranges"]
    assert entries, "decoded Blueprint ranges must be relocated, not dropped"
    pointers = [entry["json_pointer"] for entry in entries]
    assert pointers == sorted(pointers), "semantic_source_ranges must be ordered by json_pointer"
    for entry in entries:
        assert set(entry) == {"object_id", "json_pointer", "region"}
        assert entry["json_pointer"].startswith("/")
        region = entry["region"]
        assert region["size"] >= 0
        assert region["source_id"]
    assert any(entry["region"]["size"] > 0 for entry in entries)
    # Parity: debug is normal plus the evidence block.
    stripped = copy.deepcopy(debug)
    stripped.pop("debug")
    stripped["mode"] = "normal"
    assert stripped == project_document(stackobot_document)


def test_inspect_package_matches_python_parse_and_project():
    from uasset_read.agent_tools import inspect_package
    from uasset_read.package import parse_package_document

    path = sample_path("StackOBot_BP_Drone.uasset")
    for mode in ("normal", "debug"):
        expected = project_document(parse_package_document(str(path), depth="decode"), mode=mode)
        assert inspect_package(str(path), mode=mode) == expected
