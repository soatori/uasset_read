"""BPGC bytecode cache isolation tests — Phase 72-F.

Verifies that _extract_kismet_decompiled() calls reset_bpgc_cache() at entry,
preventing stale cache carryover between consecutive parse_uasset() calls.
"""
import pytest
from unittest.mock import patch, MagicMock

from uasset_read.parse_uasset import _extract_kismet_decompiled
from uasset_read.kismet.bytecode_extractor import (
    reset_bpgc_cache,
    _bpgc_bytecode_cache,
)


def test_bpgc_cache_reset_called_in_extract_kismet():
    """Verify _extract_kismet_decompiled clears cache before iterating exports.

    Uses state verification: populate stale cache, call function, assert it was reset.
    This is more robust than mocking because it tests the actual integration.
    """
    import uasset_read.kismet.bytecode_extractor as be_mod

    # Set stale cache state
    be_mod._bpgc_bytecode_cache = {"stale_key": b"\xDE\xAD"}

    _extract_kismet_decompiled(
        path="dummy.uasset",
        archive=MagicMock(),
        summary=MagicMock(),
        name_map=["TestAsset"],
        import_map=[],
        export_map=[],
        tolerant=True,
    )

    # reset_bpgc_cache() should have been called, clearing the stale state
    assert be_mod._bpgc_bytecode_cache is None


def test_bpgc_cache_isolation_between_parse_calls():
    """Populate stale cache, call _extract_kismet_decompiled, assert cache was cleared.

    This proves the integration: _extract_kismet_decompiled calls reset_bpgc_cache,
    which clears the stale _bpgc_bytecode_cache global state.
    """
    import uasset_read.kismet.bytecode_extractor as be_mod

    # Simulate stale cache from a previous file's extraction
    be_mod._bpgc_bytecode_cache = {"fileA_func": b"\x01\x02\x53"}
    assert be_mod._bpgc_bytecode_cache is not None

    _extract_kismet_decompiled(
        path="dummy.uasset",
        archive=MagicMock(),
        summary=MagicMock(),
        name_map=["TestAsset"],
        import_map=[],
        export_map=[],
        tolerant=True,
    )

    # The fix ensures reset_bpgc_cache() was called during the function
    assert be_mod._bpgc_bytecode_cache is None
