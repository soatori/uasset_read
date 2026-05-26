---
phase: 72f
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/parse_uasset.py
  - tests/test_bpgc_cache_isolation.py
autonomous: true
requirements:
  - T-72C-04
  - M-01
user_setup: []

must_haves:
  truths:
    - "reset_bpgc_cache() is called before each file's Kismet extraction"
    - "Consecutive parse_uasset() calls on different files do not share BPGC cache"
    - "Existing decompile_uasset() behavior unchanged (already calls reset_bpgc_cache)"
  artifacts:
    - path: "src/uasset_read/parse_uasset.py"
      provides: "Cache reset in _extract_kismet_decompiled()"
      contains: "reset_bpgc_cache()"
    - path: "tests/test_bpgc_cache_isolation.py"
      provides: "Regression test for cache isolation bug"
      exports: ["test_bpgc_cache_reset_between_parse_calls"]
  key_links:
    - from: "src/uasset_read/parse_uasset.py::_extract_kismet_decompiled"
      to: "src/uasset_read/kismet/bytecode_extractor::reset_bpgc_cache"
      via: "local import + function call"
      pattern: "reset_bpgc_cache\\(\\)"
---

<objective>
Fix BPGC bytecode cache isolation bug (M-01): add reset_bpgc_cache() call to _extract_kismet_decompiled() and write a regression test that verifies consecutive parse_uasset() calls on different files do not share stale BPGC cache.

Purpose: Consecutive parse_uasset(file_A) + parse_uasset(file_B) calls share stale _bpgc_bytecode_cache, causing silent data corruption on file B. The fix mirrors what decompile_uasset() already does at pipeline.py:152.
Output: 1-line fix + 1 test file
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From src/uasset_read/kismet/bytecode_extractor.py:
```python
_bpgc_bytecode_cache: dict[str, bytes] | None = None

def reset_bpgc_cache() -> None:
    """Reset the BPGC bytecode cache. Called at start of each file's extraction."""
    global _bpgc_bytecode_cache
    _bpgc_bytecode_cache = None
```

From src/uasset_read/parse_uasset.py (lines 31-65):
```python
def _extract_kismet_decompiled(
    path: str,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    tolerant: bool = True,
) -> List["KismetDecompiledResult"]:
    from uasset_read.kismet.bytecode_extractor import USTRUCT_TYPES
    from uasset_read.serializers.object_resources import resolve_class_name
    from uasset_read.kismet.pipeline import decompile_single_function

    results: List["KismetDecompiledResult"] = []
    for export in export_map:
        # ... loop body
    return results
```

From src/uasset_read/kismet/pipeline.py (line 152):
```python
    # T-72C-04: Reset BPGC cache for fresh extraction per file
    reset_bpgc_cache()
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Write regression test for BPGC cache isolation</name>
  <files>tests/test_bpgc_cache_isolation.py</files>
  <behavior>
    - Test 1: _extract_kismet_decompiled() calls reset_bpgc_cache() before iterating exports (verify via mock/patch)
    - Test 2: Consecutive parse_uasset() calls with mock exports — verify cache is reset between calls
  </behavior>
  <action>
    Create tests/test_bpgc_cache_isolation.py with two tests:

    Test 1 — test_bpgc_cache_reset_called_in_extract_kismet():
      - Patch reset_bpgc_cache with a mock
      - Call _extract_kismet_decompiled() with mock arguments (empty export_map is sufficient)
      - Assert reset_bpgc_cache was called exactly once
      - Import _extract_kismet_decompiled from uasset_read.parse_uasset
      - Import reset_bpgc_cache from uasset_read.kismet.bytecode_extractor

    Test 2 — test_bpgc_cache_isolation_between_parse_calls():
      - Import _bpgc_bytecode_cache module, reset_bpgc_cache from uasset_read.kismet.bytecode_extractor
      - Manually populate _bpgc_bytecode_cache = {"fileA_func": b"\x01\x02\x53"} (simulate file A's cache)
      - Call _extract_kismet_decompiled() with mock arguments (which should now call reset_bpgc_cache internally)
      - Assert _bpgc_bytecode_cache is None (the fix ensures cache was reset during the call)
      - This proves the integration: _extract_kismet_decompiled calls reset_bpgc_cache, which clears the stale state

    Use the existing test patterns from tests/test_kismet_bpgc.py for style consistency.
  </action>
  <verify>
    <automated>python -m pytest tests/test_bpgc_cache_isolation.py::test_bpgc_cache_isolation_between_parse_calls -xvs --tb=short</automated>
  </verify>
  <done>Test file created with 2 tests. Test 1 will initially fail (reset_bpgc_cache not yet called in _extract_kismet_decompiled); Test 2 verifies the mechanism directly.</done>
</task>

<task type="auto" tdd="true" depends_on="01">
  <name>Task 2: Add reset_bpgc_cache() call to _extract_kismet_decompiled()</name>
  <files>src/uasset_read/parse_uasset.py</files>
  <behavior>
    - After fix, Test 1 from Task 1 passes: reset_bpgc_cache is called before export loop
    - After fix, Test 2 from Task 1 passes: stale cache is cleared during _extract_kismet_decompiled
  </behavior>
  <action>
    In src/uasset_read/parse_uasset.py, inside _extract_kismet_decompiled() (lines 45-47 existing local imports):

    1. Add reset_bpgc_cache to the existing local import block at line 45:
       Change:
         from uasset_read.kismet.bytecode_extractor import USTRUCT_TYPES
       To:
         from uasset_read.kismet.bytecode_extractor import USTRUCT_TYPES, reset_bpgc_cache

    2. Add reset_bpgc_cache() call immediately after the import block (new line ~49), before the results list and export loop:
         reset_bpgc_cache()

    Final structure should be:
       lines 45-47: import block (with reset_bpgc_cache added)
       line 49:     reset_bpgc_cache()
       line 51:     results: List[...] = []
       line 52:     for export in export_map: ...

    Do NOT modify any other code in the function. This is a 1-line import addition + 1-line function call.
  </action>
  <verify>
    <automated>python -m pytest tests/test_bpgc_cache_isolation.py -xvs --tb=short</automated>
    <automated>python -m pytest tests/test_kismet_bpgc.py -xvs --tb=short</automated>
  </verify>
  <done>reset_bpgc_cache imported and called before export loop in _extract_kismet_decompiled. Both isolation tests pass. No regressions in existing BPGC tests.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Module global state → per-file extraction | _bpgc_bytecode_cache persists across calls, crossing file boundary |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-72F-01 | Integrity | _bpgc_bytecode_cache global | mitigate | reset_bpgc_cache() called at entry of _extract_kismet_decompiled() and decompile_uasset() — already mitigated in pipeline.py:152, now also in parse_uasset.py |
| T-72F-02 | Tampering | npm/pip/cargo installs | mitigate | No new packages — T-72C-SC covers baseline supply chain |
</threat_model>

<verification>
1. python -m pytest tests/test_bpgc_cache_isolation.py -xvs — all 2 tests pass
2. python -m pytest tests/test_kismet_bpgc.py -xvs — no regression on existing BPGC tests
3. grep -n "reset_bpgc_cache" src/uasset_read/parse_uasset.py — confirms import and call present
</verification>

<success_criteria>
- reset_bpgc_cache() is imported and called at the start of _extract_kismet_decompiled() (before the export loop)
- New test file tests/test_bpgc_cache_isolation.py exists with 2 passing tests
- No regressions in existing kismet/BPGC test suite
- The fix is exactly 2 lines: 1 import addition, 1 function call — no other changes
</success_criteria>

<output>
Create `.planning/phases/phase-72f/72f-01-SUMMARY.md` when done
</output>
