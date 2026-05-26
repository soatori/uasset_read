---
phase: phase-72c
plan: 02
type: execute
wave: 2
depends_on:
  - 72c-01
files_modified:
  - src/uasset_read/kismet/bytecode_extractor.py
  - src/uasset_read/kismet/pipeline.py
  - tests/test_kismet_bpgc.py
autonomous: true
requirements:
  - KISM-03
must_haves:
  truths:
    - "decompile_uasset() returns >= 12 functions for BP_FirstPersonCharacter.uasset"
    - "ExecuteUbergraph has parseable bytecode with >= 50 expressions"
    - "Existing kismet tests still pass (no regression)"
  artifacts:
    - path: "src/uasset_read/kismet/bytecode_extractor.py"
      provides: "BPGC fallback path in extract_bytecode_bytes"
      exports: ["extract_bytecode_bytes"]
    - path: "src/uasset_read/kismet/pipeline.py"
      provides: "Updated decompile_uasset with BPGC bytecode support"
      exports: ["decompile_uasset", "decompile_single_function"]
    - path: "tests/test_kismet_bpgc.py"
      provides: "BPGC bytecode extraction and integration tests"
      min_lines: 50
  key_links:
    - from: "src/uasset_read/kismet/bytecode_extractor.py"
      to: "src/uasset_read/kismet/bpgc_bytecode.py"
      via: "fallback import and call"
      pattern: "from.*bpgc_bytecode import|extract_bpgc_bytecode"
    - from: "src/uasset_read/kismet/pipeline.py"
      to: "src/uasset_read/kismet/bytecode_extractor.py"
      via: "extract_bytecode_bytes with BPGC fallback"
      pattern: "extract_bytecode_bytes"
---

<objective>
Integrate BPGC bytecode extraction into the existing kismet pipeline and add tests. When Function exports have no bytecode in their script_serial_region, fall back to BPGC extraction to recover the bytecode.

Purpose: Bridge the gap between the new bpgc_bytecode module (Plan 01) and the existing decompile_uasset() pipeline. The existing `extract_bytecode_bytes()` returns None for UE5 cooked Blueprints — this plan adds the fallback path.

Output: Modified bytecode_extractor.py with BPGC fallback, modified pipeline.py with two-pass decompilation, new test file.
</objective>

<execution_context>
@.planning/ROADMAP.md
@.planning/STATE.md
@src/uasset_read/kismet/bpgc_bytecode.py (from Plan 01)
@src/uasset_read/kismet/bytecode_extractor.py
@src/uasset_read/kismet/pipeline.py
@tests/test_kismet.py
@tests/test_kismet_integration.py
</execution_context>

<context>
@src/uasset_read/kismet/bytecode_extractor.py
@src/uasset_read/kismet/pipeline.py
@src/uasset_read/kismet/bpgc_bytecode.py
@tests/test_kismet.py
@tests/test_kismet_integration.py

<interfaces>
From src/uasset_read/kismet/bpgc_bytecode.py (Plan 01 output):
```python
def extract_bpgc_bytecode(archive, bpgc_export, summary, asset_name, name_map, import_map, export_map) -> dict[str, bytes]:
    """Extract bytecode buffers from BPGC script_serial_region.
    Returns dict of {index: bytecode_bytes}.
    """

def map_bytecode_to_functions(bytecode_buffers, function_exports, name_map) -> dict[str, bytes]:
    """Map bytecode buffers to Function exports by name.
    Returns dict of {function_name: bytecode_bytes}.
    """
```

From src/uasset_read/kismet/bytecode_extractor.py (existing):
```python
def extract_bytecode_bytes(archive, export, summary, name_map, import_map, export_map) -> bytes | None:
    """Extract ScriptBytecode from a UStruct export."""

def parse_bytecode_stream(bytecode_bytes, name_map, tolerant=False) -> list[KismetExpression]:
    """Parse raw bytecode bytes into KismetExpression list."""

def extract_and_parse(archive, export, summary, name_map, import_map, export_map, tolerant=False) -> tuple[list[KismetExpression], str | None]:
    """Combined extraction + parsing entry point."""
```

From src/uasset_read/kismet/pipeline.py (existing):
```python
def decompile_uasset(path: str, tolerant: bool = True) -> list[KismetDecompiledResult]:
    """Decompile all Blueprint functions in a .uasset file."""

def decompile_single_function(archive, export, summary, name_map, import_map, export_map, tolerant=True) -> KismetDecompiledResult | None:
    """Decompile a single UStruct export."""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add BPGC fallback to extract_bytecode_bytes</name>
  <files>src/uasset_read/kismet/bytecode_extractor.py</files>
  <action>
Modify `extract_bytecode_bytes()` in bytecode_extractor.py to add a BPGC fallback path. The function should:

1. Keep existing logic intact: attempt to extract bytecode from the Function export's script_serial_region (skip PropertyTags, read bytecodeBufferSize + serializedScriptSize).
2. If the existing path returns None (bytecodeBufferSize=0 or serializedScriptSize=0), add fallback:
   a. Import `extract_bpgc_bytecode` and `map_bytecode_to_functions` from `uasset_read.kismet.bpgc_bytecode`
   b. Import `detect_blueprint_generated_class` and `find_main_blueprint_generated_class` from `uasset_read.serializers.object_resources`
   c. Find the main BPGC export using `find_main_blueprint_generated_class(export_map, import_map, ???)` — need asset_name (derive from package name or export_map)
   d. Call `extract_bpgc_bytecode()` to get all function bytecode buffers from BPGC
   e. Call `map_bytecode_to_functions()` to map buffers to Function exports by name
   f. Look up the current `export.object_name` in the mapped dict
   g. If found, return the bytecode bytes for this function
   h. If not found, return None (no bytecode for this function)

3. Add a module-level cache variable `_bpgc_bytecode_cache: dict[str, bytes] | None = None` to avoid re-extracting BPGC bytecode for every Function export. The cache is keyed by function name.
4. On first fallback invocation: extract all BPGC bytecode, populate cache, then serve from cache for subsequent calls.
5. Add `import logging` and log a warning when falling back to BPGC extraction: "Falling back to BPGC bytecode extraction for {function_name}"

**Do NOT:**
- Do NOT change the function signature of extract_bytecode_bytes
- Do NOT modify the existing (uncooked) extraction path
- Do NOT add BPGC logic if the existing path succeeds (only on None return)
  </action>
  <verify>
    <automated>python -c "from uasset_read.kismet.bytecode_extractor import extract_bytecode_bytes; print('Import OK')"</automated>
  </verify>
  <done>extract_bytecode_bytes imports successfully, existing function signature unchanged, BPGC fallback logic added after existing path returns None</done>
</task>

<task type="auto">
  <name>Task 2: Add BPGC tests</name>
  <files>tests/test_kismet_bpgc.py</files>
  <action>
Create `tests/test_kismet_bpgc.py` with the following test functions:

**`test_extract_bpgc_bytecode_parses_cooked_format()`**
- Use synthetic bytecode buffer (cooked format: size + data + EX_EndOfScript)
- Call `_parse_cooked_bytecode_buffer` from bpgc_bytecode
- Assert correct number of buffers extracted, each ending with EX_EndOfScript

**`test_extract_bpgc_bytecode_empty_region()`**
- Test with empty bytes → returns empty list
- Test with zero size prefix → returns empty list

**`test_map_bytecode_to_functions_ordinals()`**
- Create mock Function exports (use ObjectExport dataclass)
- Create mock bytecode buffers dict
- Call `map_bytecode_to_functions`
- Assert function names mapped to correct bytecode buffers by ordinal position

**`test_extract_bytecode_bytes_bpgc_fallback()`**
- Integration test using real BP_FirstPersonCharacter.uasset
- Call `extract_bytecode_bytes` for ExecuteUbergraph function export
- Assert bytecode is returned (non-None) even though Function serial has no bytecode
- This tests the BPGC fallback path

**`test_decompile_uasset_bpgc_functions()`**
- End-to-end test: call `decompile_uasset()` on BP_FirstPersonCharacter.uasset
- Assert results contain >= 12 functions (matching the 12 Function exports)
- Assert at least one function (ExecuteUbergraph) has >= 50 expressions
- Verify function names include expected: "ExecuteUbergraph_BP_FirstPersonCharacter", "Aim", "Move", Input events

**`test_decompile_uasset_no_regression()`**
- Run existing test_kismet.py tests to verify no regression
- This is a meta-test that imports and re-runs critical test cases from test_kismet.py

**Test asset directory:**
```python
TEST_ASSET_DIR = Path(r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson")
PRIMARY_BP = TEST_ASSET_DIR / "BP_FirstPersonCharacter.uasset"
```

**Use pytest.importorskip pattern** for graceful skipping when test assets unavailable.
  </action>
  <verify>
    <automated>python -m pytest tests/test_kismet_bpgc.py -v -x --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>All test_kismet_bpgc.py tests pass (or skip gracefully if test assets unavailable)</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| bytecode_extractor→bpgc_bytecode | Fallback path must handle BPGC extraction errors without crashing the main pipeline |
| Pipeline→BPGC cache | Cache must be properly scoped (module-level, not global) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-72C-03 | Denial of Service | BPGC fallback on corrupt BPGC | mitigate | Wrap BPGC extraction in try/except; return None on failure rather than raising; log error |
| T-72C-04 | Integrity | Module-level cache stale across files | mitigate | Cache is per-call-context; reset on new decompile_uasset() invocation by using function-scope cache |
| T-72C-SC | Tampering | pip installs | mitigate | slopcheck + blocking human checkpoint for [ASSUMED]/[SUS] |
</threat_model>

<verification>
1. `decompile_uasset()` on BP_FirstPersonCharacter.uasset returns >= 12 functions
2. ExecuteUbergraph_BP_FirstPersonCharacter has >= 50 expressions
3. All existing test_kismet.py tests pass (no regression)
4. Non-Blueprint .uasset files return empty list (existing behavior preserved)
</verification>

<success_criteria>
1. `decompile_uasset()` on BP_FirstPersonCharacter.uasset returns >= 12 functions (currently returns 0)
2. At minimum ExecuteUbergraph_BP_FirstPersonCharacter has >= 50 parseable expressions
3. All existing kismet tests pass without modification
4. No regression on non-Blueprint .uasset parsing (returns empty list as before)
5. BPGC fallback is transparent — caller does not need to know which path was used
</success_criteria>

<output>
Create `.planning/phases/phase-72c/02-01-SUMMARY.md` when done
</output>
