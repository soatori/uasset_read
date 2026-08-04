"""Tests for #521 Phase 3: NiagaraScript handler.

Verifies that:
- NiagaraScript handler is registered and can handle NiagaraScript
- Output schema matches Phase 3 definition
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

def test_niagara_script_handler_is_registered():
    """NiagaraScript handler must be registered in the class registry."""
    registry = get_class_registry()
    handler = registry.find_handler("NiagaraScript")
    assert handler is not None, "NiagaraScript handler not found in registry"
    assert handler.can_handle("NiagaraScript")


def test_niagara_script_handler_name():
    """NiagaraScript handler must have a descriptive name."""
    registry = get_class_registry()
    handler = registry.find_handler("NiagaraScript")
    assert handler is not None
    assert "NiagaraScript" in handler.handler_name


# ── Output schema ──────────────────────────────────────────────────────

def _get_niagara_script_export() -> dict:
    """Parse fixture and return first NiagaraScript export dict."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))
    for export in payload["exports"]:
        if export.get("object_class") == "NiagaraScript":
            return export
    raise AssertionError("No NiagaraScript export found in fixture")


def test_niagara_script_has_script_name():
    """NiagaraScript output must project script_name in asset_type_data (contract field)."""
    export = _get_niagara_script_export()
    assert export.get("object_name") == "NM_BPSystemEvent"
    atd = export.get("asset_type_data", {})
    assert atd.get("script_name") == "NM_BPSystemEvent", (
        f"Expected script_name 'NM_BPSystemEvent' in asset_type_data, "
        f"got {atd.get('script_name')!r}"
    )


def test_niagara_script_projects_script_usage():
    """script_usage must be projected from the Usage enum property (contract field).

    Fixture evidence: Usage = EnumProperty with value_name 'ENiagaraScriptUsage::Module'.
    """
    export = _get_niagara_script_export()
    atd = export.get("asset_type_data", {})
    assert atd.get("script_usage") == "ENiagaraScriptUsage::Module", (
        f"Expected script_usage 'ENiagaraScriptUsage::Module', "
        f"got {atd.get('script_usage')!r}"
    )


def test_niagara_script_has_tagged_properties():
    """NiagaraScript output must include tagged_properties dict."""
    export = _get_niagara_script_export()
    atd = export.get("asset_type_data", {})
    assert "tagged_properties" in atd, (
        f"Expected 'tagged_properties' in asset_type_data, got keys: {list(atd.keys())}"
    )
    tagged = atd["tagged_properties"]
    assert isinstance(tagged, dict)
    # Must include the4 known properties from evidence
    expected_props = {"Usage", "ExposedVersion", "VersionData", "RapidIterationParameters"}
    assert expected_props.issubset(set(tagged.keys())), (
        f"Expected properties {expected_props} in tagged_properties, got: {set(tagged.keys())}"
    )


def test_niagara_script_usage_value():
    """NiagaraScript Usage enum must be projected."""
    export = _get_niagara_script_export()
    atd = export.get("asset_type_data", {})
    tagged = atd.get("tagged_properties", {})
    usage = tagged.get("Usage")
    assert usage is not None, "Usage property not found in tagged_properties"
    # Usage is an enum; should have value_name or be a string
    if isinstance(usage, dict):
        assert "value_name" in usage or "enum_type" in usage


def test_niagara_script_has_native_tail():
    """NiagaraScript output must include native_tail with offset and size."""
    export = _get_niagara_script_export()
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


def test_niagara_script_parse_status_is_partial_metadata():
    """NiagaraScript parse_status must be partial_metadata after handler projection."""
    export = _get_niagara_script_export()
    parse_status = export.get("parse_status")
    assert parse_status == "partial_metadata", (
        f"Expected parse_status 'partial_metadata', got '{parse_status}'"
    )
