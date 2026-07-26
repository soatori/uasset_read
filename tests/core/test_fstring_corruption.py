"""FString all-null corruption detection tests (#330, #405).

Verify read_fstring() behavior for all-null data:
- UTF-8: length > 0 but data is all nulls
- UTF-16: length < 0 but data is all nulls
- Both strict and tolerant modes return empty string with diagnostic (#405)
"""
import pytest
from uasset_read.archive import ByteArchive


def test_fstring_all_nulls_utf8_tolerant():
    """UTF-8 all-null FString in tolerant mode returns empty string."""
    # length=5 (u32 LE), 5 null bytes
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_all_nulls_utf16_tolerant():
    """UTF-16 all-null FString in tolerant mode returns empty string."""
    # length=-3 (i32 LE) -> utf16_len=6, 6 null bytes
    data = b'\xfd\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_all_nulls_utf8_strict():
    """UTF-8 all-null FString in strict mode returns empty string with diagnostic (#405)."""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)

    result = archive.read_fstring()
    assert result == ""
    # Should have a diagnostic recorded
    diags = archive.get_diagnostics()
    assert len(diags) >= 1
    assert "all nulls" in diags[0].error


def test_fstring_all_nulls_utf16_strict():
    """UTF-16 all-null FString in strict mode returns empty string with diagnostic (#405)."""
    data = b'\xfd\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)

    result = archive.read_fstring()
    assert result == ""
    diags = archive.get_diagnostics()
    assert len(diags) >= 1
    assert "all nulls" in diags[0].error


def test_fstring_non_null_strict_still_raises():
    """Non-null FString with bad data still raises ParseError in strict mode."""
    # length=5 but only 2 bytes remain — not enough data
    data = b'\x05\x00\x00\x00AB'
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(Exception):
        archive.read_fstring()


# --- Real-asset regression tests for #405 ---

_SAMPLE_DIR = "tests/samples"


@pytest.mark.integration
def test_all_null_ftext_asset_parses_strict():
    """Asset with all-null FText namespace parses in strict mode (#405).

    FirstPerson_BP_FirstPersonGameMode hits _read_ftext_base -> read_fstring
    with all-null payload at offset 15713. Before #405, strict mode raised
    ParseError; now returns empty string with diagnostic.
    """
    from pathlib import Path

    path = Path(_SAMPLE_DIR) / "FirstPerson_BP_FirstPersonGameMode.uasset"
    if not path.exists():
        pytest.skip(f"sample not found: {path}")

    from uasset_read import parse_uasset_with_linker

    result = parse_uasset_with_linker(str(path), tolerant=False)
    assert result.is_success, f"strict parse failed: {result.errors}"
