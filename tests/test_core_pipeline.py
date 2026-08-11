"""Core pipeline consolidated tests — parse_single, parse_package, boundary cases."""
from __future__ import annotations

import gc
import json
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from uasset_read.core import parse_single
from uasset_read.exceptions import ParseError
from uasset_read.models.result import ParseResult


# ---------------------------------------------------------------------------
# parse_single error path
# ---------------------------------------------------------------------------

def test_parse_single_raises_on_parse_failure():
    """parse_single raises ParseError when linker parse fails."""
    from uasset_read.link.result import LinkerParseResult

    with patch("uasset_read.core.parse_uasset_with_linker") as mock_parse:
        mock_parse.return_value = LinkerParseResult(
            is_success=False,
            errors=["test error"],
        )
        with pytest.raises(ParseError, match="Parse failed"):
            parse_single("nonexistent.uasset", format="json")


# ---------------------------------------------------------------------------
# parse_package / parse_uasset_with_linker
# ---------------------------------------------------------------------------

def test_parse_package_returns_result():
    """parse_package returns a valid ParseResult with summary and maps."""
    from uasset_read.parse_uasset import parse_package

    test_assets = list(Path("tests/assets").glob("*.uasset"))[:3]
    for asset_path in test_assets:
        result = parse_package(str(asset_path))
        assert result.summary is not None
        assert result.name_map is not None
        assert result.export_map is not None
        del result
        gc.collect()


def test_parse_uasset_with_linker_returns_result():
    """parse_uasset_with_linker returns a valid LinkerParseResult."""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    test_assets = list(Path("tests/assets").glob("*.uasset"))[:3]
    for asset_path in test_assets:
        result = parse_uasset_with_linker(str(asset_path))
        assert result.summary is not None
        assert result.linker is not None
        assert result.all_objects is not None
        del result
        gc.collect()


# ---------------------------------------------------------------------------
# Lazy loading
# ---------------------------------------------------------------------------

def test_parse_lazy_returns_result():
    """parse_package_lazy returns a ParseResult with summary and name_map."""
    from uasset_read.parse_uasset import parse_package_lazy

    samples = Path("tests/samples")
    if not samples.exists():
        pytest.skip("samples directory not found")
    assets = list(samples.glob("*.uasset"))
    if not assets:
        pytest.skip("no .uasset test files available")

    result = parse_package_lazy(str(assets[0]), tolerant=True)
    assert isinstance(result, ParseResult)
    assert result.summary is not None
    assert result.name_map is not None


# ---------------------------------------------------------------------------
# Tolerant parsing — corrupt header
# ---------------------------------------------------------------------------

def _package_with_bad_custom_version_count(count: int) -> bytes:
    """Build minimal package data with an abnormal custom version count."""
    from uasset_read.constants import PACKAGE_FILE_TAG, UE5_PACKAGE_SAVED_HASH

    data = bytearray()
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, -9, 0, 0)
    data += struct.pack("<i", UE5_PACKAGE_SAVED_HASH)
    data += b"\x00" * 20
    data += struct.pack("<i", 0)  # total_header_size
    data += struct.pack("<I", count)
    data += b"\x00" * 128
    return bytes(data)


def test_tolerant_json_returns_failed_status(tmp_path):
    """Tolerant mode returns status=failed for a corrupt header instead of raising."""
    path = tmp_path / "bad_custom_versions.uasset"
    path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

    output = parse_single(str(path), format="json", tolerant=True)
    data = json.loads(output)

    assert data["status"]["status"] == "failed"
