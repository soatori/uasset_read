# Plan 03 Summary — Create parse_uasset_with_linker() entry point

## Objective
Create parse_uasset_with_linker() — new parallel entry point using PackageLinker from Phase 41.

## What Changed
- `src/uasset_read/parse_uasset.py`:
  - Added `parse_uasset_with_linker(path, tolerant=True, preload_all=False)` after `parse_uasset()`
  - Uses PackageLinker to build UObjectInstance graph
  - Calls _post_process() for shared blueprint/graph/dependency extraction
  - Errors collected into result.errors (D-02 compliant)
  - preload_all=True triggers linker.preload() for all exports
  - NOT exported from top-level uasset_read/__init__.py (D-05 compliant)

## Verification
- `python -c "from uasset_read.parse_uasset import parse_uasset_with_linker; print('OK')"` passed
- `from uasset_read import parse_uasset_with_linker` raises ImportError (D-05)
- All 67 parse-related tests pass (0 regressions)
- parse_uasset() completely unmodified by this plan

## Self-Check: PASSED
