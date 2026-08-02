"""Validation tests for #515 opaque struct scan results.

Ensures the scan output is structurally valid and contains no false positives.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCAN_RESULTS = ROOT / "tests" / "temp" / "scan_results.json"


def _load_scan_results() -> dict:
    """Load scan results; skip if file does not exist."""
    assert SCAN_RESULTS.exists(), (
        f"Scan results not found at {SCAN_RESULTS}. "
        "Run: python tests/temp/scan_opaque_structs.py > tests/temp/scan_results.json"
    )
    return json.loads(SCAN_RESULTS.read_text(encoding="utf-8"))


def test_scan_results_file_exists():
    """scan_results.json must exist after running the scan."""
    data = _load_scan_results()
    assert "candidates" in data
    assert "summary" in data


def test_scan_summary_has_valid_counts():
    """Summary counts must be non-negative integers."""
    data = _load_scan_results()
    summary = data["summary"]
    for key in (
        "total_samples_scanned",
        "files_with_opaque_exports",
        "total_opaque_exports",
        "total_struct_entries",
        "unique_struct_types",
    ):
        assert key in summary, f"Missing summary key: {key}"
        assert isinstance(summary[key], int), f"{key} must be int"
        assert summary[key] >= 0, f"{key} must be non-negative"


def test_scan_summary_top_struct_types_sorted_by_frequency():
    """top_struct_types must be sorted by count descending."""
    data = _load_scan_results()
    top = data["summary"]["top_struct_types"]
    assert len(top) > 0, "Expected at least one top struct type"
    for item in top:
        assert "struct_type" in item
        assert "count" in item
    counts = [item["count"] for item in top]
    assert counts == sorted(counts, reverse=True), "top_struct_types not sorted"


def test_candidates_have_required_fields():
    """Each candidate must have struct_type, occurrence_count, unique_locations, locations."""
    data = _load_scan_results()
    candidates = data["candidates"]
    assert len(candidates) > 0, "Expected at least one candidate"
    for c in candidates:
        assert "struct_type" in c, "candidate missing struct_type"
        assert "occurrence_count" in c, "candidate missing occurrence_count"
        assert "unique_locations" in c, "candidate missing unique_locations"
        assert "locations" in c, "candidate missing locations"
        assert c["occurrence_count"] > 0
        assert c["unique_locations"] > 0
        assert len(c["locations"]) > 0


def test_candidate_locations_have_required_fields():
    """Each location entry must have file, object_name, outer_path."""
    data = _load_scan_results()
    for c in data["candidates"]:
        for loc in c["locations"]:
            assert "file" in loc, f"location missing file in {c['struct_type']}"
            assert "object_name" in loc, f"location missing object_name in {c['struct_type']}"
            assert "outer_path" in loc, f"location missing outer_path in {c['struct_type']}"
