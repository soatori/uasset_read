# Phase 72-C Wave 2 Summary: BPGC Fallback Integration

**Status**: ✅ Completed  
**Date**: 2026-05-23  
**Plan**: `.planning/phases/phase-72c/72c-02-PLAN.md`

## Summary

Integrated BPGC bytecode extraction into the existing kismet pipeline with fallback mechanism for UE5 cooked Blueprints. When Function exports have no bytecode in their script_serial_region, the system now falls back to extracting bytecode from the BlueprintGeneratedClass export.

## Changes Made

### 1. bytecode_extractor.py — BPGC Fallback Path

Added:
- Module-level cache `_bpgc_bytecode_cache` for BPGC bytecode (populated on first fallback)
- `_bpgc_fallback()` function that extracts bytecode from BPGC when Function exports have no bytecode
- `reset_bpgc_cache()` function to clear cache for each new decompile_uasset() invocation
- Warning logging when falling back to BPGC extraction

Key features:
- Preserves existing `extract_bytecode_bytes` signature unchanged
- Only triggers BPGC logic when existing path returns None
- T-72C-03 mitigation: wrapped in try/except, returns None on failure
- T-72C-04 mitigation: cache reset at each decompile_uasset() call

### 2. pipeline.py — Cache Reset

Added:
- Import of `reset_bpgc_cache` from bytecode_extractor
- Call to `reset_bpgc_cache()` at start of `decompile_uasset()` to ensure fresh cache per file

### 3. kismet/__init__.py — Export Update

Added:
- Export of `reset_bpgc_cache` to public API

### 4. object_resources.py — Bug Fix

Fixed bug in `detect_blueprint_generated_class()`:
- Changed check from `import_map[idx].class_name` to `import_map[idx].object_name`
- BPGC imports have class_name="Class" but object_name="BlueprintGeneratedClass"

### 5. tests/test_kismet_bpgc.py — New Test File

Created comprehensive test suite with:
- Unit tests for `_parse_cooked_bytecode_buffer` (synthetic data)
- Unit tests for `map_bytecode_to_functions` (mock exports)
- Integration tests for BPGC fallback (skipped if no cooked UE5 Blueprint available)
- Regression tests verifying existing kismet tests still pass

## Test Results

```
tests/test_kismet_bpgc.py:
  test_extract_bpgc_bytecode_parses_cooked_format  PASSED
  test_extract_bpgc_bytecode_empty_region          PASSED
  test_map_bytecode_to_functions_ordinals          PASSED
  test_extract_bytecode_bytes_bpgc_fallback        SKIPPED (no cooked UE5 BP)
  test_decompile_uasset_bpgc_functions             SKIPPED (no cooked UE5 BP)
  test_decompile_uasset_no_regression              PASSED
  test_decompile_uasset_non_blueprint_returns_empty SKIPPED
  test_parse_cooked_bytecode_buffer_inline         PASSED

  5 passed, 3 skipped

Existing tests (test_kismet.py, test_kismet_integration.py):
  28 passed, 11 skipped (no regression)
```

## Key Findings

1. **Test Asset Status**: `BP_FirstPersonCharacter.uasset` is an UNCOOKED editor asset (PKG_Cooked=False). BPGC fallback is designed for COOKED UE5 Blueprints where bytecode is stored in BPGC script_serial_region.

2. **Uncooked Asset Behavior**: For uncooked assets, Function exports have minimal script_serial_size (9 bytes - PropertyTag overhead only), and BPGC script_serial_region contains only PropertyTags, no bytecode.

3. **Correct Fallback Triggering**: The warning log shows BPGC fallback is correctly triggered when Function exports have no bytecode.

## Verification

- ✅ Import verification: `extract_bytecode_bytes` and `reset_bpgc_cache` import successfully
- ✅ Unit tests pass: `_parse_cooked_bytecode_buffer` and `map_bytecode_to_functions` work correctly
- ✅ Regression tests pass: existing kismet tests unchanged
- ✅ BPGC detection fixed: `detect_blueprint_generated_class` now correctly identifies BPGC exports

## Files Modified

| File | Change |
|------|--------|
| `src/uasset_read/kismet/bytecode_extractor.py` | Added BPGC fallback + cache |
| `src/uasset_read/kismet/pipeline.py` | Added cache reset in decompile_uasset() |
| `src/uasset_read/kismet/__init__.py` | Export reset_bpgc_cache |
| `src/uasset_read/serializers/object_resources.py` | Fixed detect_blueprint_generated_class bug |
| `tests/test_kismet_bpgc.py` | New test file created |

## Next Steps

For Phase 72-C Wave 3 or future phases:
- Find a truly cooked UE5 Blueprint asset for integration testing
- Consider adding synthetic test data to verify full pipeline integration
- Monitor BPGC extraction on production cooked assets