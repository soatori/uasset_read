"""Tests for #521 Phase 2: NiagaraGraph handler.

Verifies that:
- NiagaraGraph handler is registered and can handle NiagaraGraph
- Output schema matches Phase 2 definition
- Tagged properties are projected into structured fields
- Native tail offset/size are captured
"""

from __future__ import annotations

import json
from pathlib import Path

from uasset_read import parse_single
from uasset_read.parsers.class_registry import get_class_registry


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"


# ── Handler registration ────────────────────────────────────────────────

def test_niagara_graph_handler_is_registered():
    """NiagaraGraph handler must be registered in the class registry."""
    registry = get_class_registry()
    handler = registry.find_handler("NiagaraGraph")
    assert handler is not None, "NiagaraGraph handler not found in registry"
    assert handler.can_handle("NiagaraGraph")


def test_niagara_graph_handler_name():
    """NiagaraGraph handler must have a descriptive name."""
    registry = get_class_registry()
    handler = registry.find_handler("NiagaraGraph")
    assert handler is not None
    assert "NiagaraGraph" in handler.handler_name


# ── Output schema ──────────────────────────────────────────────────────

def _get_payload() -> dict:
    """Parse fixture and return the full JSON payload."""
    return json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))


def _get_niagara_graph_export() -> dict:
    """Parse fixture and return first NiagaraGraph export dict."""
    payload = _get_payload()
    for export in payload["exports"]:
        if export.get("object_class") == "NiagaraGraph":
            return export
    raise AssertionError("No NiagaraGraph export found in fixture")


def test_niagara_graph_has_graph_name():
    """NiagaraGraph output must project graph_name in asset_type_data (contract field)."""
    export = _get_niagara_graph_export()
    assert export.get("object_name") == "NiagaraGraph_1"
    atd = export.get("asset_type_data", {})
    assert atd.get("graph_name") == "NiagaraGraph_1", (
        f"Expected graph_name 'NiagaraGraph_1' in asset_type_data, "
        f"got {atd.get('graph_name')!r}"
    )


def test_niagara_graph_has_node_exports():
    """node_exports must contain resolved NiagaraNode* references (contract).

    Nodes is serialized as PackageIndex values (1-based: value = export_index + 1).
    The fixture graph holds 28 node refs: 25 NiagaraNode* + 3 EdGraphNode_Comment.
    Only NiagaraNode* entries are projected per contract.
    """
    export = _get_niagara_graph_export()
    payload_exports = _get_payload()["exports"]
    atd = export.get("asset_type_data", {})
    assert "node_exports" in atd, (
        f"Expected 'node_exports' in asset_type_data, got keys: {list(atd.keys())}"
    )
    node_exports = atd["node_exports"]
    assert isinstance(node_exports, list)
    assert len(node_exports) == 25, (
        f"Expected 25 NiagaraNode* references, got {len(node_exports)}"
    )
    for node in node_exports:
        assert "export_index" in node, f"Missing export_index in node: {node}"
        assert "class" in node, f"Missing class in node: {node}"
        assert node["class"].startswith("NiagaraNode"), (
            f"Non-node class in node_exports: {node}"
        )
        # export_index must be a resolved 0-based index matching the export table
        target = payload_exports[node["export_index"]]
        assert target["object_class"] == node["class"], (
            f"export_index {node['export_index']} resolves to "
            f"{target['object_class']}, expected {node['class']}"
        )

    # Class composition of the fixture graph (evidence-pinned)
    from collections import Counter
    composition = Counter(n["class"] for n in node_exports)
    assert composition == {
        "NiagaraNodeFunctionCall": 1,
        "NiagaraNodeInput": 1,
        "NiagaraNodeOp": 5,
        "NiagaraNodeOutput": 1,
        "NiagaraNodeParameterMapGet": 5,
        "NiagaraNodeParameterMapSet": 5,
        "NiagaraNodeReroute": 5,
        "NiagaraNodeSelect": 1,
        "NiagaraNodeStaticSwitch": 1,
    }


def test_niagara_graph_has_tagged_properties():
    """NiagaraGraph output must include tagged_properties dict."""
    export = _get_niagara_graph_export()
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd, (
        f"Expected 'tagged_properties' in asset_type_data, got keys: {list(atd.keys())}"
    )
    tagged = atd["tagged_properties"]
    assert isinstance(tagged, dict)
    # Must include the5 known properties from evidence
    expected_props = {"ChangeId", "LastBuiltTraversalDataChangeId", "CachedUsageInfo",
                      "VariableToScriptVariable", "Nodes"}
    assert expected_props.issubset(set(tagged.keys())), (
        f"Expected properties {expected_props} in tagged_properties, got: {set(tagged.keys())}"
    )


def test_niagara_graph_has_native_tail():
    """NiagaraGraph output must include native_tail with offset and size."""
    export = _get_niagara_graph_export()
    atd = export.get("asset_type_data", {})
    assert "native_tail" in atd, (
        f"Expected 'native_tail' in asset_type_data, got keys: {list(atd.keys())}"
    )
    tail = atd["native_tail"]
    assert isinstance(tail, dict)
    assert "offset" in tail, "Missing offset in native_tail"
    assert "size" in tail, "Missing size in native_tail"
    assert "status" in tail, "Missing status in native_tail"
    assert tail["status"] == "opaque"
    assert isinstance(tail["offset"], int)
    assert isinstance(tail["size"], int)


def test_niagara_graph_parse_status_is_partial_metadata():
    """NiagaraGraph parse_status must be partial_metadata after handler projection."""
    export = _get_niagara_graph_export()
    parse_status = export.get("parse_status")
    # After handler projects business fields, status should be partial_metadata
    assert parse_status == "partial_metadata", (
        f"Expected parse_status 'partial_metadata', got '{parse_status}'"
    )
