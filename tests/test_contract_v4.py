"""Contract gate for the v4 package-output document (normal/debug modes).

Hand-built fixtures validate against
``docs/designs/contract/package_document_v4.schema.json``. The schema is the
frozen contract; producers migrate against it in later tasks.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema

_CONTRACT_DIR = Path(__file__).resolve().parents[1] / "docs" / "designs" / "contract"
_SCHEMA_PATH = _CONTRACT_DIR / "package_document_v4.schema.json"

_DEBUG_KEYS = {
    "object_regions",
    "property_evidence",
    "semantic_source_ranges",
    "payload_sources",
    "sidecar_sources",
    "diagnostic_details",
    "byte_accounting",
}


def _schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _region(start: int, size: int, *, status: str = "decoded") -> dict[str, Any]:
    return {
        "start": start,
        "size": size,
        "end": start + size,
        "source_id": "package",
        "source_start": start,
        "source_end": start + size,
        "source_slices": [
            {"source_id": "package", "source_start": start, "size": size, "source_end": start + size}
        ],
        "status": status,
        "reason": None,
        "feature": "",
        "payload_ref": None,
    }


def _property_entry(name: str, value: Any) -> dict[str, Any]:
    return {
        "name": name,
        "type": "StrProperty",
        "occurrence": 0,
        "array_index": None,
        "value": value,
    }


def _normal_document() -> dict[str, Any]:
    return {
        "format": "uasset_read.package",
        "format_version": "4.0",
        "mode": "normal",
        "source": {"kind": "loose", "name": "BP_Light.uasset", "size": 32145},
        "package": {"name": "/Game/BP_Light", "layout": "legacy", "package_flags": 0},
        "summary": {"object_count": 1, "asset_object_ids": ["export:0"]},
        "objects": [
            {
                "id": "export:0",
                "table_index": 0,
                "name": "BP_Light",
                "class": "Blueprint",
                "roles": ["asset"],
                "status": {"parse": "complete", "semantic": "complete"},
                "properties": [_property_entry("DisplayName", "Light")],
                "semantic": {
                    "kind": "blueprint",
                    "external_refs": [
                        {
                            "local_id": "import:1",
                            "package": "/Script/Engine",
                            "class_name": "Function",
                            "symbol": "PrintString",
                            "qualified_key": "/Script/Engine::Function::PrintString",
                            "origin": "unknown_origin",
                            "source_evidence": [{"kind": "stack_node", "value": 1}],
                            "status": "resolved",
                            "reason": "",
                            "candidate_local_ids": [],
                        }
                    ],
                    "graphs": [
                        {
                            "id": "export:0/export:1",
                            "name": "EventGraph",
                            "links": [
                                {
                                    "graph_id": "export:0/export:1",
                                    "source_node_id": "export:0/export:2",
                                    "source_pin_guid": "a" * 32,
                                    "target_owner_id": "export:3",
                                    "target_node_id": "export:0/export:3",
                                    "target_pin_guid": "b" * 32,
                                    "connection_type": "exec",
                                    "status": "resolved",
                                    "reason": "",
                                }
                            ],
                        }
                    ],
                    "functions": [
                        {
                            "name": "ReceiveBeginPlay",
                            "instructions": [
                                {
                                    "opcode": "EX_EndOfScript",
                                    "source_node_id": None,
                                    "source_node_reason": "debug_mapping_unavailable",
                                }
                            ],
                        }
                    ],
                },
                "coverage": [{"feature": "graphs", "status": "present"}],
            }
        ],
        "relations": [],
        "dependencies": [],
        "projections": [
            {
                "source_object_id": "export:0",
                "kind": "table_data",
                "media_type": "application/json",
                "embedded": True,
                "status": "represented",
                "completeness": "complete",
                "dependencies": [],
                "diagnostics": [],
                "provenance": {
                    "derived_from": ["export:0"],
                    "generator": "uasset_read.projections.table_data",
                },
                "content": {"rows": []},
            }
        ],
        "payloads": [],
        "sidecars": [],
        "diagnostics": [
            {
                "severity": "warning",
                "code": "PROPERTY_VALUE_REMAINDER",
                "message": "Property value left 8 unread bytes",
                "stage": "properties.tagged",
                "object_id": "export:0",
                "effect": "semantic_loss",
                "count": 1,
            }
        ],
    }


def _debug_document() -> dict[str, Any]:
    doc = _normal_document()
    doc["mode"] = "debug"
    link = doc["objects"][0]["semantic"]["graphs"][0]["links"][0]
    link["debug_evidence"] = {
        "raw_source_owner_package_index": 2,
        "raw_target_owner_package_index": 4,
        "raw_source_pin_guid": "a" * 32,
        "raw_target_pin_guid": "b" * 32,
        "source_pin_range": _region(4096, 64),
        "target_reference_range": _region(4160, 8),
        "target_pin_range": _region(4168, 64),
    }
    instruction = doc["objects"][0]["semantic"]["functions"][0]["instructions"][0]
    instruction["debug_evidence"] = {
        "raw_opcode": 0,
        "serialized_range": _region(8192, 1),
        "source_node_evidence": None,
        "diagnostics": [],
    }
    doc["debug"] = {
        "object_regions": [{"object_id": "export:0", "region": _region(4096, 4096)}],
        "property_evidence": [
            {
                "object_id": "export:0",
                "property_index": 0,
                "tag_region": _region(4096, 32),
                "value_region": _region(4128, 16),
                "raw": {
                    "encoding": "hex",
                    "data": "00",
                    "total_size": 8,
                    "truncated": False,
                },
            }
        ],
        "semantic_source_ranges": [
            {
                "object_id": "export:0",
                "json_pointer": "/semantic/declaration",
                "region": _region(0, 64),
            }
        ],
        "payload_sources": [
            {
                "payload_id": "payload:export:0",
                "source_region": _region(1024, 256, status="payload"),
                "offset": 1024,
            }
        ],
        "sidecar_sources": [
            {"path": "BP_Light.uexp", "region": _region(0, 32145)}
        ],
        "diagnostic_details": [{"index": 0, "offset": 4096, "size": 8}],
        "byte_accounting": [
            {
                "object_id": "export:0",
                "window": _region(4096, 4096),
                "leaves": [_region(4096, 4096)],
            }
        ],
    }
    return doc


def _rejects(document: dict[str, Any]) -> None:
    try:
        jsonschema.validate(document, _schema())
    except jsonschema.ValidationError:
        return
    raise AssertionError("document unexpectedly validated")


def test_schema_is_draft_2020_12() -> None:
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)


def test_normal_and_debug_fixtures_validate() -> None:
    schema = _schema()
    jsonschema.validate(_normal_document(), schema)
    jsonschema.validate(_debug_document(), schema)


def test_envelope_fields() -> None:
    normal = _normal_document()
    debug = _debug_document()
    assert normal["format"] == "uasset_read.package"
    assert normal["format_version"] == "4.0"
    assert normal["mode"] == "normal"
    assert "debug" not in normal
    assert debug["mode"] == "debug"
    assert set(debug["debug"]) == {
        "object_regions",
        "property_evidence",
        "semantic_source_ranges",
        "payload_sources",
        "sidecar_sources",
        "diagnostic_details",
        "byte_accounting",
    }


def test_unsupported_modes_rejected() -> None:
    for mode in ("agent", "raw", "semantic", "view"):
        document = _normal_document()
        document["mode"] = mode
        _rejects(document)


def test_normal_document_with_debug_rejected() -> None:
    document = _normal_document()
    document["debug"] = _debug_document()["debug"]
    _rejects(document)


def test_debug_document_without_evidence_array_rejected() -> None:
    document = _debug_document()
    del document["debug"]["payload_sources"]
    _rejects(document)


def test_detailed_diagnostic_in_common_list_rejected() -> None:
    document = _normal_document()
    document["diagnostics"][0]["offset"] = 4096
    _rejects(document)


def test_missing_projection_provenance_rejected() -> None:
    document = _normal_document()
    del document["projections"][0]["provenance"]
    _rejects(document)


def test_semantic_source_range_in_common_output_rejected() -> None:
    document = _normal_document()
    document["objects"][0]["semantic"]["graphs"][0]["source_range"] = _region(0, 64)
    _rejects(document)
    debug_document = copy.deepcopy(_debug_document())
    debug_document["objects"][0]["semantic"]["graphs"][0]["source_range"] = _region(0, 64)
    _rejects(debug_document)
    nested = _normal_document()
    nested["objects"][0]["semantic"]["external_refs"][0]["source_evidence"][0]["value"] = {
        "source_range": _region(0, 64)
    }
    _rejects(nested)


def test_empty_byte_accounting_leaves_for_non_empty_window_rejected() -> None:
    document = _debug_document()
    document["debug"]["byte_accounting"][0]["leaves"] = []
    _rejects(document)
