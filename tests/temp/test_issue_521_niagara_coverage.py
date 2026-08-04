"""Tests for #521 A3: Niagara class coverage inventory.

Every Niagara class in the fixture must land on an explicit terminal state:
field-level parse (partial_metadata) or evidence-backed skip (skipped).
No Niagara export may carry a None/absent parse_status.

Coverage table: docs/designs/issue-521-niagara-field-contracts.md,
section "Niagara Coverage Contract".
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from uasset_read import parse_single

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"
SOURCE_FIXTURE_SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"

EXPECTED_NIAGARA_CLASS_COUNTS = {
    "NiagaraGraph": 1,
    "NiagaraScript": 1,
    "NiagaraNodeFunctionCall": 1,
    "NiagaraNodeInput": 1,
    "NiagaraNodeOp": 5,
    "NiagaraNodeOutput": 1,
    "NiagaraNodeParameterMapGet": 5,
    "NiagaraNodeParameterMapSet": 5,
    "NiagaraNodeReroute": 5,
    "NiagaraNodeSelect": 1,
    "NiagaraNodeStaticSwitch": 1,
    "NiagaraScriptVariable": 11,
    "NiagaraScriptSource": 1,
}


def _load() -> dict:
    sha256 = hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper()
    assert sha256 == SOURCE_FIXTURE_SHA256, f"Fixture SHA-256 mismatch: {sha256}"
    return json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))


def test_niagara_class_enumeration_matches_coverage_table():
    """Live enumeration confirms the coverage table's class inventory."""
    payload = _load()
    counts = Counter(
        e["object_class"] for e in payload["exports"]
        if str(e.get("object_class", "")).startswith("Niagara")
    )
    assert dict(counts) == EXPECTED_NIAGARA_CLASS_COUNTS


def test_every_niagara_export_has_explicit_parse_status():
    """No Niagara export may carry a None/absent parse_status (status model)."""
    payload = _load()
    offenders = [
        (e.get("object_name"), e.get("object_class"), e.get("parse_status"))
        for e in payload["exports"]
        if str(e.get("object_class", "")).startswith("Niagara")
        and e.get("parse_status") not in ("partial_metadata", "skipped")
    ]
    assert offenders == [], f"Niagara exports without terminal status: {offenders}"


def test_niagara_script_variable_projects_tagged_metadata():
    """NiagaraScriptVariable exports project verified tagged properties."""
    payload = _load()
    variables = [
        e for e in payload["exports"]
        if e.get("object_class") == "NiagaraScriptVariable"
    ]
    assert len(variables) == 11
    for e in variables:
        assert e["parse_status"] == "partial_metadata", e["object_name"]
        atd = e.get("asset_type_data", {})
        tagged = atd.get("tagged_properties", {})
        assert tagged["Variable"]["struct_type"] == "NiagaraVariable"
        assert tagged["Metadata"]["struct_type"] == "NiagaraVariableMetaData"
        assert tagged["DefaultValueVariant"]["struct_type"] == "NiagaraVariant"
        assert atd["native_tail"]["status"] == "opaque"


def test_niagara_script_source_stays_skipped():
    """NiagaraScriptSource keeps its evidence-backed skip state."""
    payload = _load()
    sources = [
        e for e in payload["exports"]
        if e.get("object_class") == "NiagaraScriptSource"
    ]
    assert len(sources) == 1
    assert sources[0]["parse_status"] == "skipped"
