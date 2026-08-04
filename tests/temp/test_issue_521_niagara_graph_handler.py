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

def _get_niagara_graph_export() -> dict:
    """Parse fixture and return first NiagaraGraph export dict."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))
    for export in payload["exports"]:
        if export.get("object_class") == "NiagaraGraph":
            return export
    raise AssertionError("No NiagaraGraph export found in fixture")


def test_niagara_graph_has_graph_name():
    """NiagaraGraph output must include graph_name from object_name."""
    export = _get_niagara_graph_export()
    # graph_name is projected from the export object_name
    assert export.get("object_name") == "NiagaraGraph_1"


def test_niagara_graph_has_node_exports():
    """NiagaraGraph output must include node_exports list."""
    export = _get_niagara_graph_export()
    # After handler implementation, asset_type_data should contain node_exports
    atd = export.get("asset_type_data", {})
    assert "node_exports" in atd, (
        f"Expected 'node_exports' in asset_type_data, got keys: {list(atd.keys())}"
    )
    node_exports = atd["node_exports"]
    assert isinstance(node_exports, list)
    assert len(node_exports) > 0, "Expected at least one node export reference"
    # Each entry should have export_index and class
    for node in node_exports:
        assert "export_index" in node, f"Missing export_index in node: {node}"
        assert "class" in node, f"Missing class in node: {node}"


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
