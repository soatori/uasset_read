"""Regression test for #515 NiagaraParameterStore struct parsing.

NiagaraParameterStore stores rapid iteration parameters for Niagara VFX.
UE source: Niagara/NiagaraParameterStore.h
"""

from __future__ import annotations

import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"


def _find_niagara_parameter_store_fields() -> list[dict]:
    """Find all NiagaraParameterStore StructProperty fields in the fixture."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    results = []
    for export in payload["exports"]:
        props = export.get("properties", [])
        for prop in props:
            if prop.get("type") == "StructProperty":
                value = prop.get("value", {})
                if isinstance(value, dict) and value.get("struct_type") in ("NiagaraParameterStore", "FNiagaraParameterStore"):
                    results.append({
                        "export": export.get("object_name", "?"),
                        "name": prop.get("name", "?"),
                        "struct_type": value.get("struct_type"),
                        "parse_status": value.get("parse_status", "success"),
                        "fields": value.get("fields", {}),
                    })
    return results


def test_niagara_parameter_store_is_no_longer_opaque() -> None:
    """NiagaraParameterStore structs must be parsed (not opaque)."""
    stores = _find_niagara_parameter_store_fields()
    assert len(stores) > 0, "Expected at least one NiagaraParameterStore in fixture"

    for store in stores:
        assert store["parse_status"] != "opaque", (
            f"NiagaraParameterStore '{store['name']}' in '{store['export']}' "
            f"should not be opaque; got '{store['parse_status']}'"
        )
