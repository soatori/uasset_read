"""Tests for #521 Phase 4: NiagaraNode handler.

Verifies that:
- NiagaraNode handler is registered and handles all node families
- Output schema matches Phase 4 definition
- Class-specific tagged properties are projected
- Common ChangeId property is projected for all node types
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

def test_niagara_node_handler_is_registered():
    """NiagaraNode handler must be registered in the class registry."""
    registry = get_class_registry()
    handler = registry.find_handler("NiagaraNodeInput")
    assert handler is not None, "NiagaraNode handler not found in registry"
    assert handler.can_handle("NiagaraNodeInput")
    assert handler.can_handle("NiagaraNodeFunctionCall")
    assert handler.can_handle("NiagaraNodeOp")


def test_niagara_node_handler_name():
    """NiagaraNode handler must have a descriptive name."""
    registry = get_class_registry()
    handler = registry.find_handler("NiagaraNodeInput")
    assert handler is not None
    assert "NiagaraNode" in handler.handler_name


# ── Helper ──────────────────────────────────────────────────────────────

def _get_node_exports_by_class(class_name: str) -> list[dict]:
    """Parse fixture and return all exports of given class."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))
    return [
        e for e in payload["exports"]
        if e.get("object_class") == class_name
    ]


# ── NiagaraNodeInput ───────────────────────────────────────────────────

def test_niagara_node_input_has_tagged_properties():
    """NiagaraNodeInput must project Input, CallSortPriority, ChangeId."""
    exports = _get_node_exports_by_class("NiagaraNodeInput")
    assert len(exports) > 0, "No NiagaraNodeInput exports found"
    export = exports[0]
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd
    tagged = atd["tagged_properties"]
    assert "ChangeId" in tagged
    assert "Input" in tagged
    assert "CallSortPriority" in tagged


def test_niagara_node_input_parse_status():
    """NiagaraNodeInput parse_status must be partial_metadata."""
    exports = _get_node_exports_by_class("NiagaraNodeInput")
    assert len(exports) > 0
    assert exports[0].get("parse_status") == "partial_metadata"


# ── NiagaraNodeFunctionCall ────────────────────────────────────────────

def test_niagara_node_function_call_has_tagged_properties():
    """NiagaraNodeFunctionCall must project FunctionScript, FunctionDisplayName, ChangeId."""
    exports = _get_node_exports_by_class("NiagaraNodeFunctionCall")
    assert len(exports) > 0, "No NiagaraNodeFunctionCall exports found"
    export = exports[0]
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd
    tagged = atd["tagged_properties"]
    assert "ChangeId" in tagged
    assert "FunctionScript" in tagged
    assert "FunctionDisplayName" in tagged


def test_niagara_node_function_call_parse_status():
    """NiagaraNodeFunctionCall parse_status must be partial_metadata."""
    exports = _get_node_exports_by_class("NiagaraNodeFunctionCall")
    assert len(exports) > 0
    assert exports[0].get("parse_status") == "partial_metadata"


# ── NiagaraNodeOp ──────────────────────────────────────────────────────

def test_niagara_node_op_has_tagged_properties():
    """NiagaraNodeOp must project OpName, ChangeId."""
    exports = _get_node_exports_by_class("NiagaraNodeOp")
    assert len(exports) > 0, "No NiagaraNodeOp exports found"
    export = exports[0]
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd
    tagged = atd["tagged_properties"]
    assert "ChangeId" in tagged
    assert "OpName" in tagged


def test_niagara_node_op_parse_status():
    """NiagaraNodeOp parse_status must be partial_metadata."""
    exports = _get_node_exports_by_class("NiagaraNodeOp")
    assert len(exports) > 0
    assert exports[0].get("parse_status") == "partial_metadata"


# ── NiagaraNodeOutput ──────────────────────────────────────────────────

def test_niagara_node_output_has_tagged_properties():
    """NiagaraNodeOutput must project Outputs, ScriptType, ChangeId."""
    exports = _get_node_exports_by_class("NiagaraNodeOutput")
    assert len(exports) > 0, "No NiagaraNodeOutput exports found"
    export = exports[0]
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd
    tagged = atd["tagged_properties"]
    assert "ChangeId" in tagged
    assert "Outputs" in tagged
    assert "ScriptType" in tagged


def test_niagara_node_output_parse_status():
    """NiagaraNodeOutput parse_status must be partial_metadata."""
    exports = _get_node_exports_by_class("NiagaraNodeOutput")
    assert len(exports) > 0
    assert exports[0].get("parse_status") == "partial_metadata"


# ── NiagaraNodeParameterMapGet ─────────────────────────────────────────

def test_niagara_node_parameter_map_get_has_tagged_properties():
    """NiagaraNodeParameterMapGet must project PinOutputToPinDefaultPersistentId, ChangeId."""
    exports = _get_node_exports_by_class("NiagaraNodeParameterMapGet")
    assert len(exports) > 0, "No NiagaraNodeParameterMapGet exports found"
    export = exports[0]
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd
    tagged = atd["tagged_properties"]
    assert "ChangeId" in tagged
    assert "PinOutputToPinDefaultPersistentId" in tagged


def test_niagara_node_parameter_map_get_parse_status():
    """NiagaraNodeParameterMapGet parse_status must be partial_metadata."""
    exports = _get_node_exports_by_class("NiagaraNodeParameterMapGet")
    assert len(exports) > 0
    assert exports[0].get("parse_status") == "partial_metadata"


# ── NiagaraNodeParameterMapSet ─────────────────────────────────────────

def test_niagara_node_parameter_map_set_has_tagged_properties():
    """NiagaraNodeParameterMapSet must project ChangeId."""
    exports = _get_node_exports_by_class("NiagaraNodeParameterMapSet")
    assert len(exports) > 0, "No NiagaraNodeParameterMapSet exports found"
    export = exports[0]
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd
    tagged = atd["tagged_properties"]
    assert "ChangeId" in tagged


def test_niagara_node_parameter_map_set_parse_status():
    """NiagaraNodeParameterMapSet parse_status must be partial_metadata."""
    exports = _get_node_exports_by_class("NiagaraNodeParameterMapSet")
    assert len(exports) > 0
    assert exports[0].get("parse_status") == "partial_metadata"


# ── NiagaraNodeReroute ─────────────────────────────────────────────────

def test_niagara_node_reroute_has_tagged_properties():
    """NiagaraNodeReroute must project ChangeId."""
    exports = _get_node_exports_by_class("NiagaraNodeReroute")
    assert len(exports) > 0, "No NiagaraNodeReroute exports found"
    export = exports[0]
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd
    tagged = atd["tagged_properties"]
    assert "ChangeId" in tagged


def test_niagara_node_reroute_parse_status():
    """NiagaraNodeReroute parse_status must be partial_metadata."""
    exports = _get_node_exports_by_class("NiagaraNodeReroute")
    assert len(exports) > 0
    assert exports[0].get("parse_status") == "partial_metadata"


# ── Identity fields (contract: node_class, node_name) ─────────────────

def test_niagara_node_projects_node_class_and_name():
    """Every migrated node export must project node_class and node_name."""
    for cls in ("NiagaraNodeInput", "NiagaraNodeFunctionCall", "NiagaraNodeOp",
                "NiagaraNodeOutput", "NiagaraNodeParameterMapGet",
                "NiagaraNodeParameterMapSet", "NiagaraNodeReroute"):
        exports = _get_node_exports_by_class(cls)
        assert len(exports) > 0, f"No {cls} exports found"
        for export in exports:
            atd = export.get("asset_type_data", {})
            assert atd.get("node_class") == cls, (
                f"{cls} '{export.get('object_name')}': expected node_class "
                f"'{cls}', got {atd.get('node_class')!r}"
            )
            assert atd.get("node_name") == export.get("object_name"), (
                f"{cls}: node_name {atd.get('node_name')!r} does not match "
                f"object_name {export.get('object_name')!r}"
            )


# ── Native tail (common) ───────────────────────────────────────────────

def test_niagara_node_has_native_tail():
    """All NiagaraNode exports must include native_tail."""
    for cls in ("NiagaraNodeInput", "NiagaraNodeFunctionCall", "NiagaraNodeOp",
                "NiagaraNodeOutput", "NiagaraNodeReroute"):
        exports = _get_node_exports_by_class(cls)
        assert len(exports) > 0
        atd = exports[0].get("asset_type_data", {})
        assert "native_tail" in atd, f"{cls} missing native_tail"
        tail = atd["native_tail"]
        assert tail["status"] in ("opaque", "decoded"), (
            f"{cls} native_tail status should be 'opaque' or 'decoded', got '{tail['status']}'"
        )
        assert isinstance(tail["offset"], int)
        assert isinstance(tail["size"], int)


# ── No longer skipped ──────────────────────────────────────────────────

def test_niagara_node_exports_no_longer_skipped():
    """All migrated NiagaraNode exports must NOT be skipped."""
    for cls in ("NiagaraNodeInput", "NiagaraNodeFunctionCall", "NiagaraNodeOp",
                "NiagaraNodeOutput", "NiagaraNodeParameterMapGet",
                "NiagaraNodeParameterMapSet", "NiagaraNodeReroute"):
        exports = _get_node_exports_by_class(cls)
        for export in exports:
            assert export.get("parse_status") != "skipped", (
                f"{cls} '{export.get('object_name')}' should not be skipped"
            )
