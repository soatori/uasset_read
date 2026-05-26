# Phase 72f Summary — BPGC Cache Isolation Fix

## Objective
Fix BPGC bytecode cache isolation bug (M-01): consecutive `parse_uasset()` calls on different files must not share stale `_bpgc_bytecode_cache`.

## Changes

### `src/uasset_read/parse_uasset.py` (2 lines)
- Line 45: Added `reset_bpgc_cache` to the local import from `kismet.bytecode_extractor`
- Line 50: Added `reset_bpgc_cache()` call before the export loop in `_extract_kismet_decompiled()`

This mirrors the existing cache reset in `kismet/pipeline.py:152` (`decompile_uasset()`).

### `tests/test_bpgc_cache_isolation.py` (new file, 57 lines)
- `test_bpgc_cache_reset_called_in_extract_kismet`: Populates stale cache, calls `_extract_kismet_decompiled()`, asserts cache was cleared via state verification
- `test_bpgc_cache_isolation_between_parse_calls`: Same mechanism, proves integration of `_extract_kismet_decompiled` → `reset_bpgc_cache` → `_bpgc_bytecode_cache = None`

## Verification
- 2/2 new tests passed
- 5/5 existing BPGC tests passed (no regression; 3 skipped due to missing cooked UE5 assets)
- 1324/1324 core tests passed (23 pre-existing skill integration failures unrelated)
- Fix is exactly 2 lines: 1 import addition, 1 function call
