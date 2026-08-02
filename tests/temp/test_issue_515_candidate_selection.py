"""Tests for #515 candidate selection logic.

Validates that scan candidates do not overlap with already-implemented parsers
(tagged fallback or fast-path).
"""

from __future__ import annotations

import json
from pathlib import Path

from uasset_read.parsers.property_types import (
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
)


ROOT = Path(__file__).resolve().parents[2]
SCAN_RESULTS = ROOT / "tests" / "temp" / "scan_results.json"


def _load_candidates() -> list[dict]:
    if not SCAN_RESULTS.exists():
        return []
    data = json.loads(SCAN_RESULTS.read_text(encoding="utf-8"))
    return data.get("candidates", [])


def test_no_candidate_overlaps_with_tagged_fallback():
    """Candidates must not include structs already in _TAGGED_FALLBACK_STRUCTS."""
    candidates = _load_candidates()
    if not candidates:
        return
    fallback_names = set(_TAGGED_FALLBACK_STRUCTS)
    for c in candidates:
        assert c["struct_type"] not in fallback_names, (
            f"{c['struct_type']} is already in _TAGGED_FALLBACK_STRUCTS "
            f"and should not appear as a candidate"
        )


def test_no_candidate_overlaps_with_tagged_schemas():
    """Candidates must not include structs already in _TAGGED_FALLBACK_STRUCT_SCHEMAS."""
    candidates = _load_candidates()
    if not candidates:
        return
    schema_names = set(_TAGGED_FALLBACK_STRUCT_SCHEMAS.keys())
    for c in candidates:
        assert c["struct_type"] not in schema_names, (
            f"{c['struct_type']} already has a tagged fallback schema"
        )


def test_candidate_occurrence_counts_are_positive():
    """All candidates must have at least one occurrence."""
    candidates = _load_candidates()
    if not candidates:
        return
    for c in candidates:
        assert c["occurrence_count"] >= 1
        assert c["unique_locations"] >= 1


def test_scan_summary_matches_candidate_count():
    """Summary unique_struct_types must equal len(candidates)."""
    if not SCAN_RESULTS.exists():
        return
    data = json.loads(SCAN_RESULTS.read_text(encoding="utf-8"))
    assert data["summary"]["unique_struct_types"] == len(data["candidates"])


def test_total_struct_entries_at_least_as_many_as_candidates():
    """Total struct entries must be >= number of candidates."""
    if not SCAN_RESULTS.exists():
        return
    data = json.loads(SCAN_RESULTS.read_text(encoding="utf-8"))
    assert data["summary"]["total_struct_entries"] >= len(data["candidates"])
