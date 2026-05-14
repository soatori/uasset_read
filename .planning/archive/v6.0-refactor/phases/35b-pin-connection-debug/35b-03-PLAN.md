---
phase: 35b
plan: 03
type: execute
wave: 2
depends_on:
  - 35b-01
files_modified:
  - src/uasset_read/serializers/graph.py
  - tests/test_ue5_ftext_serialization.py
autonomous: true
requirements:
  - TEST-01
  - TEST-02

must_haves:
  truths:
    - "FText b_has_culture reads exactly 1 byte (uint8) for UE5 assets, not 4 bytes (uint32)"
    - "read_ftext_with_history() can operate in both UE4 mode (4-byte bool) and UE5 mode (1-byte bool)"
    - "UE4 FText parsing is unchanged (still uses read_bool())"
  artifacts:
    - path: "src/uasset_read/serializers/graph.py"
      provides: "Version-aware FText bool reading via ue5_mode parameter"
      contains: "read_bool_ue5() if ue5_mode else read_bool()"
    - path: "src/uasset_read/serializers/graph.py"
      provides: "read_ue_graph_pin() passes ue5_mode to read_ftext_with_history()"
      contains: "ue5_mode=(summary.file_version_ue5 > 0)"
    - path: "tests/test_ue5_ftext_serialization.py"
      provides: "Unit tests for FText b_has_culture byte consumption"
      exports: ["TestUE5FTextSerialization"]
  key_links:
    - from: "src/uasset_read/serializers/graph.py:read_ue_graph_pin()"
      to: "src/uasset_read/serializers/graph.py:read_ftext_with_history()"
      via: "Call at L345 with ue5_mode parameter"
      pattern: "read_ftext_with_history.*ue5_mode"
---

<objective>
Fix FText b_has_culture bool reading in read_ftext_with_history() to use 1 byte (uint8) for UE5 assets.

Purpose: FText with history_type=0xFF (None) consumes flags(4B) + history_type(1B) + b_has_culture(bool). Current code uses read_bool() for b_has_culture which reads 4 bytes instead of 1, adding +3 bytes drift per pin. Combined with the 4 PinType bools (+12 bytes from 35b-01), this brings total bool-related drift to +15 bytes.

Output: Version-aware FText bool reading, unit tests confirming correct byte consumption.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/35b-pin-connection-debug/35b-RESEARCH.md
@src/uasset_read/serializers/graph.py

<interfaces>
<!-- Current read_ftext_with_history() signature: -->
<!-- def read_ftext_with_history(archive, history_type, tolerant=True) -> tuple[str, int] -->

<!-- Current b_has_culture read (L208): -->
<!-- b_has_culture = archive.read_bool()  # WRONG for UE5 -- reads 4 bytes instead of 1 -->

<!-- Current call site (L345 in read_ue_graph_pin): -->
<!-- read_ftext_with_history(archive, history_type, tolerant=True) -->

<!-- This plan adds ue5_mode parameter and updates the call site to pass it. -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add ue5_mode parameter to read_ftext_with_history()</name>
  <files>src/uasset_read/serializers/graph.py</files>
  <action>Update the `read_ftext_with_history()` function signature (L188-192):

From:
```python
def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
) -> tuple[str, int]:
```

To:
```python
def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
    ue5_mode: bool = False,
) -> tuple[str, int]:
```

Then update L208 (the b_has_culture read inside the `if history_type == 0xFF:` block):

From:
```python
b_has_culture = archive.read_bool()
```

To:
```python
b_has_culture = archive.read_bool_ue5() if ue5_mode else archive.read_bool()
```

This preserves UE4 behavior (read_bool reads 4 bytes) while fixing UE5 (read_bool_ue5 reads 1 byte).</action>
  <verify>
    <automated>count=$(grep -n 'ue5_mode' src/uasset_read/serializers/graph.py | grep -v '^#' | wc -l); echo "$count"; [ "$count" -ge 2 ] && echo "PASS" || echo "FAIL"</automated>
  </verify>
  <done>read_ftext_with_history() has ue5_mode parameter; b_has_culture uses conditional bool reading</done>
</task>

<task type="auto">
  <name>Task 2: Update read_ue_graph_pin() call site to pass ue5_mode</name>
  <files>src/uasset_read/serializers/graph.py</files>
  <action>Update the call to `read_ftext_with_history()` in `read_ue_graph_pin()` (L345):

From:
```python
read_ftext_with_history(archive, history_type, tolerant=True)
```

To:
```python
read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=(summary.file_version_ue5 > 0))
```

This propagates the UE5 detection from the pin reader (which has access to the summary object) down to the FText reader.

Note: The `read_ftext_with_history()` function does not have access to `summary` itself, so the ue5_mode flag must be passed in. This is the cleanest approach -- adding a summary parameter would create a circular import concern and couple FText parsing to package metadata.</action>
  <verify>
    <automated>count=$(grep -n 'read_ftext_with_history' src/uasset_read/serializers/graph.py | grep -v 'def ' | grep -v '^#' | wc -l); echo "Call sites: $count"</automated>
  </verify>
  <done>All call sites to read_ftext_with_history() pass ue5_mode parameter based on summary.file_version_ue5</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Unit tests for FText b_has_culture byte consumption</name>
  <files>tests/test_ue5_ftext_serialization.py</files>
  <behavior>
    - Test: read_ftext_with_history(ue5_mode=True) consumes exactly 1 byte for b_has_culture
    - Test: read_ftext_with_history(ue5_mode=False) consumes exactly 4 bytes for b_has_culture
    - Test: Total consumption for FText history_type=0xFF: UE5=6 bytes (4 flags + 1 history_type + 1 b_has_culture), UE4=9 bytes (4 flags + 1 history_type + 4 b_has_culture)
    - Edge case: history_type=0 (Base) and history_type=1-254 (Custom) are unaffected by ue5_mode
  </behavior>
  <action>Create a test file that:
1. Creates a temporary binary file with FText data for history_type=0xFF (None)
2. Calls read_ftext_with_history() with ue5_mode=True and verifies consumed bytes = 6
3. Calls read_ftext_with_history() with ue5_mode=False and verifies consumed bytes = 9
4. Tests other history_types (0, custom) to ensure they work in both modes

Use tempfile + binary write to construct the FText data: 4 bytes flags (0x00000000) + 1 byte history_type (0xFF) + 1 byte b_has_culture (0x00).</action>
  <verify>
    <automated>python -m pytest tests/test_ue5_ftext_serialization.py -v -x</automated>
  </verify>
  <done>FText serialization tests pass, confirming correct byte consumption for both UE4 and UE5 modes</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Binary input -> FText parsing | .uasset files are untrusted; malformed FText should not cause crashes |
| FText -> subsequent fields | Incorrect FText consumption shifts all subsequent pin fields |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35b-06 | Integrity | graph.py FText b_has_culture read | mitigate | Version-aware bool reading via ue5_mode flag; existing tolerant=True mode handles exceptions |
| T-35b-07 | Denial of Service | read_ftext_with_history() on malformed FText | accept | Existing try/except with tolerant=True mode seeks back on error; ParseError on strict mode |
| T-35b-08 | Tampering | ue5_mode parameter | mitigate | Always derived from summary.file_version_ue5 (package header); not user-controlled |
</threat_model>

<verification>
- read_ftext_with_history() accepts ue5_mode parameter (default False for UE4 compatibility)
- b_has_culture uses read_bool_ue5() when ue5_mode=True, read_bool() when False
- read_ue_graph_pin() passes ue5_mode=(summary.file_version_ue5 > 0)
- Unit tests confirm byte consumption: UE5=6 bytes, UE4=9 bytes for FText None type
- All existing tests pass: `python -m pytest tests/ -x --tb=short`
</verification>

<success_criteria>
- read_ftext_with_history() has ue5_mode bool parameter
- b_has_culture reads 1 byte for UE5, 4 bytes for UE4
- tests/test_ue5_ftext_serialization.py passes (4 tests)
- No regression in existing tests
</success_criteria>

<output>
After completion, create `.planning/phases/35b-pin-connection-debug/35b-03-SUMMARY.md`
</output>
