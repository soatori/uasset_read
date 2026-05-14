---
phase: 35b
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/archive.py
  - src/uasset_read/serializers/graph.py
  - tests/test_ue5_bool_serialization.py
autonomous: true
requirements:
  - TEST-01

must_haves:
  truths:
    - "read_bool_ue5() reads exactly 1 byte (uint8) from the archive"
    - "read_ed_graph_pin_type() uses 1-byte bool reads for UE5 PinType fields (bIsReference, bIsWeakPointer, bIsConst, bIsUObjectWrapper)"
    - "Existing tests still pass (397+ passed, 0 failed)"
  artifacts:
    - path: "src/uasset_read/archive.py"
      provides: "read_bool_ue5() method reading uint8"
      exports: ["read_bool_ue5"]
    - path: "src/uasset_read/serializers/graph.py"
      provides: "Version-aware bool reading in PinType"
      exports: ["read_ed_graph_pin_type"]
    - path: "tests/test_ue5_bool_serialization.py"
      provides: "Unit tests for UE5 bool serialization fix"
      exports: ["TestUE5BoolSerialization"]
  key_links:
    - from: "src/uasset_read/archive.py"
      to: "src/uasset_read/serializers/graph.py"
      via: "archive.read_bool_ue5() called by read_ed_graph_pin_type"
      pattern: "read_bool_ue5"
---

<objective>
Fix UE5 bool serialization in FArchive and PinType parsing: add read_bool_ue5() and update read_ed_graph_pin_type() to use 1-byte bools for UE5.

Purpose: Root cause of empty pin.linked_to_raw -- read_bool() consumes 4 bytes (uint32) per bool, but UE5 serializes bools as 1 byte (uint8). The 4 PinType bools (bIsReference, bIsWeakPointer, bIsConst, bIsUObjectWrapper) each introduce +3 bytes drift = +12 bytes from PinType alone. This plan fixes the PinType bools; the FText b_has_culture bool (+3 bytes) is handled in 35b-03.

Output: Version-aware bool reading in archive.py + graph.py, unit tests confirming 1-byte consumption.
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
@src/uasset_read/archive.py
@src/uasset_read/serializers/graph.py

<interfaces>
<!-- Current read_bool() in archive.py (WRONG for UE5): -->
<!--
def read_bool(self) -> bool:
    """读取 UE bool 值（序列化为 uint32，4 bytes）。"""
    return self.read_u32() != 0
-->

<!-- Current bool reads in read_ed_graph_pin_type() graph.py -- all use read_bool(): -->
<!-- L115: pin_type.is_reference = archive.read_bool() -->
<!-- L116: pin_type.is_weak_pointer = archive.read_bool() -->
<!-- L128: pin_type.is_const = archive.read_bool() -->
<!-- L134: pin_type.is_uobject_wrapper = archive.read_bool() -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add read_bool_ue5() to FArchive</name>
  <files>src/uasset_read/archive.py</files>
  <action>Add a new method `read_bool_ue5()` to the FArchive class (after the existing `read_bool()` method at L180). This method reads exactly 1 byte (uint8) and returns True if non-zero:

```python
def read_bool_ue5(self) -> bool:
    """读取 UE5 bool 值（序列化为 uint8，1 byte）。

    UE5 changed bool serialization from int32 (UE4) to uint8 for compactness.
    Using read_bool() (4 bytes) on UE5 bools causes byte drift in pin body parsing.
    """
    return self.read_u8() != 0
```

Do NOT modify the existing `read_bool()` method -- it is correct for UE4 assets. The fix is additive: a new method for UE5-specific bool reading.</action>
  <verify>
    <automated>python -c "from uasset_read.archive import FArchive; assert hasattr(FArchive, 'read_bool_ue5'); print('OK')"</automated>
  </verify>
  <done>archive.py has read_bool_ue5() method that reads 1 byte via read_u8() != 0</done>
</task>

<task type="auto">
  <name>Task 2: Update read_ed_graph_pin_type() to use read_bool_ue5() for UE5</name>
  <files>src/uasset_read/serializers/graph.py</files>
  <action>In `read_ed_graph_pin_type()` (L38-138), update the custom serialization branch (L78-136) to use `archive.read_bool_ue5()` instead of `archive.read_bool()` for the four PinType bool fields. The condition is `summary.file_version_ue5 > 0`:

1. L115: Change `pin_type.is_reference = archive.read_bool()` to:
   ```python
   pin_type.is_reference = archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()
   ```
2. L116: Same pattern for `pin_type.is_weak_pointer`
3. L128: Same pattern for `pin_type.is_const`
4. L134: Same pattern for `pin_type.is_uobject_wrapper`

Each line should check `summary.file_version_ue5 > 0` and call the appropriate method. This preserves UE4 compatibility while fixing UE5 byte consumption.

Do NOT change the custom serialization fallback branch (L102-112) which uses read_bool() for b_is_map/b_is_set/b_is_array -- this branch is never entered for UE5 because `use_modern_container` is True for UE5 (via `summary.file_version_ue5 > 0` on L94).</action>
  <verify>
    <automated>count=$(grep -n 'read_bool_ue5' src/uasset_read/serializers/graph.py | grep -v '^#' | wc -l); echo "$count"; [ "$count" -ge 4 ] && echo "PASS" || echo "FAIL"</automated>
  </verify>
  <done>All 4 PinType bool reads in read_ed_graph_pin_type() use read_bool_ue5() for UE5, read_bool() for UE4</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Unit tests for UE5 bool serialization</name>
  <files>tests/test_ue5_bool_serialization.py</files>
  <behavior>
    - Test: FArchive.read_bool_ue5() consumes exactly 1 byte (position advances by 1, not 4)
    - Test: FArchive.read_bool() still consumes exactly 4 bytes (unchanged behavior)
    - Test: read_bool_ue5() returns correct True/False for 0x00 and 0x01 byte values
    - Edge case: read_bool_ue5() on non-zero byte (e.g., 0xFF) returns True
  </behavior>
  <action>Create a new test file using a temporary binary file with known bytes. Test that:
1. read_bool_ue5() advances position by exactly 1 byte
2. read_bool() advances position by exactly 4 bytes (existing behavior preserved)
3. read_bool_ue5() correctly interprets 0x00 as False, 0x01 as True, 0xFF as True

Use tempfile + binary write to create test fixtures.</action>
  <verify>
    <automated>python -m pytest tests/test_ue5_bool_serialization.py -v -x</automated>
  </verify>
  <done>4 new tests pass, confirming read_bool_ue5() reads 1 byte and returns correct bool values</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Binary input -> FArchive | .uasset files are untrusted binary input; malformed bool values should not cause crashes |
| PinType parsing -> downstream | Incorrect bool consumption cascades into all subsequent fields (LinkedTo, SubPins, etc.) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35b-01 | Integrity | archive.read_bool_ue5() | mitigate | Strictly read 1 byte (read_u8); struct.unpack validates single byte |
| T-35b-02 | Tampering | graph.py version check (file_version_ue5 > 0) | mitigate | Use existing summary.file_version_ue5 field which is set from package header; not user-controlled |
| T-35b-03 | Denial of Service | read_bool_ue5() on malformed file | accept | ParseError from read() boundary check in FArchive prevents out-of-bounds reads |
</threat_model>

<verification>
- read_bool_ue5() exists on FArchive and reads exactly 1 byte
- read_bool() unchanged (still reads 4 bytes for UE4 compatibility)
- read_ed_graph_pin_type() uses read_bool_ue5() for 4 PinType bools when file_version_ue5 > 0
- Unit tests confirm byte consumption: read_bool_ue5=1 byte, read_bool=4 bytes
- All existing tests pass: `python -m pytest tests/ -x --tb=short`
</verification>

<success_criteria>
- archive.py has new read_bool_ue5() method (reads u8, 1 byte)
- graph.py read_ed_graph_pin_type() calls read_bool_ue5() for UE5 on all 4 bool fields
- tests/test_ue5_bool_serialization.py passes (4 tests)
- No regression: all existing tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/35b-pin-connection-debug/35b-01-SUMMARY.md`
</output>
