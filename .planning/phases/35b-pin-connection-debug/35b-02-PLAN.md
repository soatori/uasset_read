---
phase: 35b
plan: 02
type: execute
wave: 2
depends_on:
  - 35b-01
files_modified:
  - src/uasset_read/serializers/graph.py
  - tests/test_ue5_pin_bitfield.py
autonomous: true
requirements:
  - TEST-01
  - TEST-02

must_haves:
  truths:
    - "BitField reads 4 bytes (uint32) for UE5 assets, not 1 byte (uint8)"
    - "BitField bit extraction (hidden, not_connectable, advanced_view, orphaned_pin) still works correctly"
  artifacts:
    - path: "src/uasset_read/serializers/graph.py"
      provides: "Correct BitField reading: read_u32() for UE5, read_u32() for UE4"
      contains: "bitfield = archive.read_u32() for both UE4 and UE5"
  key_links:
    - from: "src/uasset_read/serializers/graph.py"
      to: "BitField bit extraction"
      via: "bitfield & (1 << N) for hidden/not_connectable/advanced_view/orphaned_pin"
      pattern: "bitfield & \\(1 <<"
---

<objective>
Fix BitField reading to consume 4 bytes (uint32) for UE5 assets instead of 1 byte (uint8).

Purpose: UE5 source code (EdGraphPin.cpp L1902) serializes BitField as `uint32`. Current code reads u8 for UE5, consuming 3 bytes too few. While BitField is the last field in the pin body (so this doesn't cause LinkedTo drift), it corrupts the bitfield value and any post-pin data parsing.

Output: Correct 4-byte BitField read for both UE4 and UE5, unit test confirming behavior.
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
<!-- Current BitField reading (WRONG for UE5): -->
<!-- graph.py L456-459:
if summary.file_version_ue5 > 0:
    bitfield = archive.read_u8()  # WRONG -- reads 1 byte, should be 4
else:
    bitfield = archive.read_u32()

Bit extraction (correct):
hidden = bool(bitfield & (1 << 0))
not_connectable = bool(bitfield & (1 << 1))
advanced_view = bool(bitfield & (1 << 4))
orphaned_pin = bool(bitfield & (1 << 5))
-->

<!-- UE5 source confirmation: -->
<!-- uint32 BitField = 0; -->
<!-- Ar << BitField;  // 4 bytes -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix BitField to read u32 for UE5</name>
  <files>src/uasset_read/serializers/graph.py</files>
  <action>In `read_ue_graph_pin()` at L456-459, replace the version-conditional BitField reading:

Current (WRONG):
```python
if summary.file_version_ue5 > 0:
    bitfield = archive.read_u8()
else:
    bitfield = archive.read_u32()
```

Fixed:
```python
# BitField is uint32 in both UE4 and UE5 (EdGraphPin.cpp L1902)
bitfield = archive.read_u32()
```

The bit extraction logic (L460-463) remains unchanged -- it correctly extracts individual flags from the 32-bit value. Since BitField is now always read_u32(), the version check on L456 is no longer needed.</action>
  <verify>
    <automated>count=$(grep -n 'read_u8()' src/uasset_read/serializers/graph.py | grep -v '^#' | grep -i 'bitfield' | wc -l); echo "$count"; [ "$count" -eq 0 ] && echo "PASS" || echo "FAIL"</automated>
  </verify>
  <done>BitField reads archive.read_u32() for both UE4 and UE5; no read_u8() for BitField</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Unit test for BitField reading</name>
  <files>tests/test_ue5_pin_bitfield.py</files>
  <behavior>
    - Test: BitField parsing consumes exactly 4 bytes from the archive position
    - Test: BitField flags are correctly extracted: bit 0=hidden, bit 1=not_connectable, bit 4=advanced_view, bit 5=orphaned_pin
    - Test: All-zero bitfield (0x00000000) produces all False flags
    - Test: All-ones bitfield (0xFFFFFFFF) produces all True flags for tested bits
  </behavior>
  <action>Create a test file that:
1. Creates a mock FArchive with known BitField bytes (e.g., 0x33 = 0b00110011)
2. Calls the bitfield reading code and verifies position advances by 4 bytes
3. Verifies individual flag extraction matches expected values

Use the bit extraction logic directly from graph.py or test via a helper function.</action>
  <verify>
    <automated>python -m pytest tests/test_ue5_pin_bitfield.py -v -x</automated>
  </verify>
  <done>BitField unit tests pass, confirming 4-byte consumption and correct flag extraction</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Binary input -> BitField parsing | .uasset files are untrusted; malformed BitField should not cause crashes |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35b-04 | Integrity | graph.py BitField read | mitigate | read_u32() is bounded by FArchive boundary checks; struct.unpack handles any 4-byte value |
| T-35b-05 | Denial of Service | BitField bit extraction | accept | Bitwise AND with known bit positions is safe; no user-controlled data affects extraction logic |
</threat_model>

<verification>
- BitField reads read_u32() (4 bytes) for both UE4 and UE5
- Bit extraction (hidden, not_connectable, advanced_view, orphaned_pin) unchanged and correct
- Unit tests confirm 4-byte consumption and correct flag values
- All existing tests pass: `python -m pytest tests/ -x --tb=short`
</verification>

<success_criteria>
- graph.py L456-459 reads archive.read_u32() for BitField regardless of UE version
- tests/test_ue5_pin_bitfield.py passes (4 tests)
- No regression in existing tests
</success_criteria>

<output>
After completion, create `.planning/phases/35b-pin-connection-debug/35b-02-SUMMARY.md`
</output>
