# tests/temp/test_serial_size_clamp.py
"""Test that corrupted serial_size values are clamped in IR output."""

import json
from pathlib import Path

import pytest

from uasset_read import parse_single


def test_als_animbp_references_are_valid():
    """ALS_AnimBP should have valid references in output."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "ALS_AnimBP.uasset"
    if not sample.exists():
        pytest.skip("ALS_AnimBP.uasset sample not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    data = json.loads(output)
    refs = data.get("references", [])
    # No reference should have absurd values
    for ref in refs:
        assert "index" in ref, f"Reference missing index: {ref}"
        assert ref["index"] >= 0, f"Negative index: {ref['index']}"


def test_als_animbp_output_line_count():
    """ALS_AnimBP output should be under 30000 lines."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "ALS_AnimBP.uasset"
    if not sample.exists():
        pytest.skip("ALS_AnimBP.uasset sample not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    line_count = output.count("\n") + 1
    assert line_count < 30000, f"Output too large: {line_count} lines"
