# tests/temp/test_serial_size_clamp.py
"""Test that corrupted serial_size values are clamped in IR output."""

import json
from pathlib import Path

import pytest

from uasset_read import parse_single


def test_als_animbp_serial_size_clamped():
    """ALS_AnimBP has 89 exports with serial_size in 10^18 range."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "ALS_AnimBP.uasset"
    if not sample.exists():
        pytest.skip("ALS_AnimBP.uasset sample not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    data = json.loads(output)
    for export in data["exports"]:
        serial = export.get("serial_size", 0)
        # No export should have serial_size > 10GB or negative
        assert serial >= 0, f"Negative serial_size: {serial}"
        assert serial < 10 * 1024 * 1024 * 1024, f"Absurd serial_size: {serial}"


def test_als_animbp_output_line_count():
    """ALS_AnimBP output should be under 25000 lines after filtering corrupted exports."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "ALS_AnimBP.uasset"
    if not sample.exists():
        pytest.skip("ALS_AnimBP.uasset sample not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    line_count = output.count("\n") + 1
    assert line_count < 25000, f"Output too large: {line_count} lines"
