# Plan 02 Summary — Extract _post_process() and refactor parse_uasset()

## Objective
Extract common post-processing (blueprint metadata, graphs, dependencies) from parse_uasset() into a shared `_post_process()` function.

## What Changed
- `src/uasset_read/parse_uasset.py`:
  - Added `Union` to typing imports, imported `LinkerParseResult`
  - Added `_post_process()` function before `parse_uasset()` with exact logic from original lines 77-144
  - All field writes use `hasattr()` guards to support both ParseResult and LinkerParseResult
  - Refactored `parse_uasset()` to delegate to `_post_process()` with single call
  - Outer exception handlers and export property parsing loop unchanged

## Verification
- `python -c "from uasset_read.parse_uasset import parse_uasset, _post_process; print('OK')"` passed
- All 67 parse-related tests pass (0 regressions)
- 4 pre-existing test failures confirmed unrelated to these changes

## Self-Check: PASSED
