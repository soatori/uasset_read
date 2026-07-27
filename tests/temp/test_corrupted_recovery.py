"""Test corrupted data recovery in FArchive."""

from pathlib import Path

import pytest

from uasset_read import parse_uasset_with_linker


def test_starter_content_bg_cue_parses():
    """StarterContent_Starter_Background_Cue has corrupted FString and out-of-range name index."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "StarterContent_Starter_Background_Cue.uasset"
    if not sample.exists():
        pytest.skip("sample not available")
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    assert result.is_success, f"Errors: {result.errors}"
    # Should have diagnostics about the corrupted FString
    diag_messages = [d.error for d in result.diagnostics]
    has_corruption_note = any("null" in m.lower() or "corrupt" in m.lower() or "out of range" in m.lower() for m in diag_messages)
    assert has_corruption_note, f"Expected corruption diagnostics, got: {diag_messages[:5]}"


def test_als_animbp_negative_serial_size():
    """ALS_AnimBP has negative serial_size: -5116089176692876519."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "ALS_AnimBP.uasset"
    if not sample.exists():
        pytest.skip("sample not available")
    result = parse_uasset_with_linker(str(sample), tolerant=True)
    assert result.is_success, f"Errors: {result.errors}"
