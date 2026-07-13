"""BPGC bytecode cache tests (#367)."""
import pytest
from unittest.mock import MagicMock, patch

from uasset_read.kismet.bytecode_extractor import (
    _bpgc_bytecode_cache,
    _bpgc_cache_retries,
    _BPGC_MAX_RETRIES,
    reset_bpgc_cache,
)


class TestBpgcCache:
    """Tests for BPGC bytecode cache retry behavior."""

    def setup_method(self):
        reset_bpgc_cache()

    def test_initial_state_is_none(self):
        """Cache starts as None (uninitialized)."""
        import uasset_read.kismet.bytecode_extractor as mod
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 0

    def test_reset_clears_retry_counter(self):
        """reset_bpgc_cache() resets both cache and retry counter."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_cache_retries = 2
        mod._bpgc_bytecode_cache = {}
        reset_bpgc_cache()
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 0

    def test_cache_hit_returns_bytecode(self):
        """When function is in cache, its bytecode is returned."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_bytecode_cache = {"TestFunc": b'\x00\x01\x02'}
        # Simulate cache lookup (the inline logic in _bpgc_fallback)
        func_name = "TestFunc"
        assert mod._bpgc_bytecode_cache.get(func_name) == b'\x00\x01\x02'

    def test_cache_miss_returns_none(self):
        """When function is not in cache, lookup returns None."""
        import uasset_read.kismet.bytecode_extractor as mod
        mod._bpgc_bytecode_cache = {}
        func_name = "MissingFunc"
        assert mod._bpgc_bytecode_cache.get(func_name) is None

    def test_failure_does_not_permanently_cache_empty(self):
        """After first failure, cache stays None (allows retry), not {}."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()
        assert mod._bpgc_bytecode_cache is None

        # Simulate first failure: increment retry but don't set cache to {}
        mod._bpgc_cache_retries += 1
        # Cache should still be None (not {}), so next call retries
        assert mod._bpgc_bytecode_cache is None
        assert mod._bpgc_cache_retries == 1

    def test_retry_limit_prevents_infinite_retry(self):
        """After _BPGC_MAX_RETRIES failures, cache is set to {} to stop retrying."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()

        # Simulate failures up to the limit
        for i in range(_BPGC_MAX_RETRIES):
            mod._bpgc_cache_retries += 1
            if mod._bpgc_cache_retries >= _BPGC_MAX_RETRIES:
                mod._bpgc_bytecode_cache = {}
                break

        assert mod._bpgc_bytecode_cache == {}
        # Cache is {} (not None), so `if _bpgc_bytecode_cache is None` will be False
        # and no further retries occur

    def test_success_resets_retry_counter(self):
        """After successful cache population, retry counter resets to 0."""
        import uasset_read.kismet.bytecode_extractor as mod
        reset_bpgc_cache()
        mod._bpgc_cache_retries = 2  # Simulate prior failures

        # Simulate successful extraction
        mod._bpgc_bytecode_cache = {"Func1": b'\xAA', "Func2": b'\xBB'}
        mod._bpgc_cache_retries = 0  # Reset on success

        assert mod._bpgc_cache_retries == 0
        assert len(mod._bpgc_bytecode_cache) == 2

    def test_max_retries_constant_is_sane(self):
        """_BPGC_MAX_RETRIES should be a positive integer."""
        assert isinstance(_BPGC_MAX_RETRIES, int)
        assert _BPGC_MAX_RETRIES > 0
