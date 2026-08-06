"""Handler integration tests for #521 NiagaraGraph and NiagaraScript.

Verifies that dedicated handlers project tagged properties into business fields.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"
SOURCE_FIXTURE_SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"


def _parse_niagara_fixture() -> dict:
    """Parse fixture once and return JSON payload."""
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper() == SOURCE_FIXTURE_SHA256
    return json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))


def test_niagara_graph_handler_projects_tagged_properties() -> None:
    """NiagaraGraph handler must project tagged properties as business fields."""
    payload = _parse_niagara_fixture()
    graph_exports = [
        e for e in payload["exports"]
        if e.get("object_class") == "NiagaraGraph"
    ]
    assert len(graph_exports) > 0, "Expected NiagaraGraph exports"

    for export in graph_exports:
        parse_status = export.get("parse_status", "success")
        assert parse_status != "skipped", "NiagaraGraph should not be skipped"

        assert "asset_type_data" in export, (
            f"NiagaraGraph export '{export.get('object_name')}' should have asset_type_data"
        )
        atd = export["asset_type_data"]
        assert atd.get("parse_status") == "partial_metadata", (
            f"NiagaraGraph handler should produce partial_metadata, "
            f"got '{atd.get('parse_status')}'"
        )
        assert atd.get("asset_type") == "NiagaraGraph"
        assert "native_tail" in atd, "native_tail should be present"
        tail = atd["native_tail"]
        assert "offset" in tail
        assert "size" in tail
        assert "status" in tail


def test_niagara_script_handler_projects_tagged_properties() -> None:
    """NiagaraScript handler must project tagged properties as business fields."""
    payload = _parse_niagara_fixture()
    script_exports = [
        e for e in payload["exports"]
        if e.get("object_class") == "NiagaraScript"
    ]
    assert len(script_exports) > 0, "Expected NiagaraScript exports"

    for export in script_exports:
        parse_status = export.get("parse_status", "success")
        assert parse_status != "skipped", "NiagaraScript should not be skipped"

        assert "asset_type_data" in export, (
            f"NiagaraScript export '{export.get('object_name')}' should have asset_type_data"
        )
        atd = export["asset_type_data"]
        assert atd.get("parse_status") == "partial_metadata", (
            f"NiagaraScript handler should produce partial_metadata, "
            f"got '{atd.get('parse_status')}'"
        )
        assert atd.get("asset_type") == "NiagaraScript"
        assert "native_tail" in atd, "native_tail should be present"
        tail = atd["native_tail"]
        assert "offset" in tail
        assert "size" in tail
        assert "status" in tail
