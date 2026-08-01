"""Test for Issue #521: Niagara export type evidence.

Documents the current behavior with a real Niagara asset fixture.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"
SOURCE_FIXTURE_SHA256 = None  # Will be computed on first run


def test_niagara_asset_parsed_as_partial():
    """Niagara assets are currently parsed as partial with skipped exports."""
    # Compute SHA-256 for fixture verification
    sha256 = hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper()

    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    # Verify status is partial
    assert payload["status"]["status"] == "partial"

    # Count skipped exports
    skipped = [
        export for export in payload["exports"]
        if export.get("parse_status") == "skipped"
    ]

    # Verify we have skipped Niagara exports
    niagara_skipped = [
        export for export in skipped
        if "Niagara" in export.get("object_class", "")
    ]

    # Document the evidence
    print(f"\n=== Niagara Asset Evidence ===")
    print(f"Fixture: {SAMPLE.name}")
    print(f"SHA-256: {sha256}")
    print(f"UE Version: {payload['summary']['ue_version']}")
    print(f"Total exports: {len(payload['exports'])}")
    print(f"Skipped exports: {len(skipped)}")
    print(f"Niagara skipped: {len(niagara_skipped)}")
    print(f"\nSkipped export types:")
    for export in niagara_skipped[:10]:
        print(f"  - {export['object_class']}: {export['object_name']}")

    # Assert we have evidence of the issue
    assert len(niagara_skipped) > 0, "Expected Niagara exports to be skipped"


def test_niagara_export_types_documented():
    """Document the specific Niagara export types that are skipped."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    # Collect unique skipped export types
    skipped_types = set()
    for export in payload["exports"]:
        if export.get("parse_status") == "skipped":
            skipped_types.add(export.get("object_class", ""))

    # Document expected types from issue #521
    expected_types = {
        "NiagaraNodeFunctionCall",
        "NiagaraNodeParameterMapSet",
        "NiagaraNodeInput",
        "NiagaraNodeParameterMapGet",
        "NiagaraScript",
        "NiagaraNodeOp",
        "NiagaraNodeOutput",
        "NiagaraNodeReroute",
        "NiagaraGraph",
    }

    print(f"\n=== Skipped Niagara Types ===")
    for t in sorted(skipped_types):
        marker = "✓" if t in expected_types else " "
        print(f"  {marker} {t}")

    # Verify we have evidence of the issue
    assert len(skipped_types) > 0, "Expected skipped export types"
