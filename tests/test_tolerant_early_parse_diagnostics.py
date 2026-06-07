"""Tolerant early parse diagnostics regression tests."""
from __future__ import annotations

import json
import struct

import pytest

from uasset_read.constants import PACKAGE_FILE_TAG, UE5_PACKAGE_SAVED_HASH
from uasset_read.core import ParseError, parse_single


def _package_with_bad_custom_version_count(count: int) -> bytes:
    data = bytearray()
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, -9, 0, 0)
    data += struct.pack("<i", UE5_PACKAGE_SAVED_HASH)
    data += b"\x00" * 20
    data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<I", count)
    data += b"\x00" * 128
    return bytes(data)


def test_tolerant_json_summary_returns_parse_stage_diagnostic(tmp_path):
    path = tmp_path / "bad_custom_versions.uasset"
    path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

    output = parse_single(str(path), format="json_summary", tolerant=True)
    data = json.loads(output)

    assert data["status"]["status"] == "failed"
    assert data["diagnostics"]
    stage_diagnostics = [
        d for d in data["diagnostics"] if d["kind"] == "parse_stage_error"
    ]
    assert stage_diagnostics
    assert stage_diagnostics[0]["fallback_used"] is True
    assert stage_diagnostics[0]["error"]


def test_strict_json_summary_still_raises_on_early_parse_failure(tmp_path):
    path = tmp_path / "bad_custom_versions.uasset"
    path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

    with pytest.raises(ParseError):
        parse_single(str(path), format="json_summary", tolerant=False)
