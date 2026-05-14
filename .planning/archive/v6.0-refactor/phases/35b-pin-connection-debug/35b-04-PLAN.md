---
phase: 35b
plan: 04
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/binary_trace_pin.py
autonomous: true
requirements:
  - TEST-01

must_haves:
  truths:
    - "Binary trace tool can parse a single pin from a known offset and dump field positions"
    - "Tool reads PinName, FText, SourceIndex, PinToolTip, Direction, PinType, DefaultValue, AutoDefaultValue, DefaultObject, DefaultTextValue, LinkedTo array"
    - "Tool reports archive position before and after each field read"
    - "Tool compares actual vs expected byte consumption"
  artifacts:
    - path: "tools/binary_trace_pin.py"
      provides: "Standalone CLI tool for binary tracing of pin body fields"
      exports: ["trace_pin_body"]
  key_links:
    - from: "tools/binary_trace_pin.py"
      to: "src/uasset_read/archive.py"
      via: "Uses FArchive for binary reading methods"
      pattern: "from uasset_read.archive import FArchive"
---

<objective>
Create a standalone binary-trace diagnostic tool to verify field positions before and after fixes.

Purpose: After applying the bool serialization fixes (35b-01, 35b-02, 35b-03), we need a way to verify that pin body fields are read at the correct positions. This tool reads a single pin body from a known offset and dumps each field's position, value, and byte consumption. It serves as the verification mechanism for the root cause fix.

Output: tools/binary_trace_pin.py -- standalone script that traces pin body parsing and reports field positions.
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
@src/uasset_read/serializers/package_summary.py
@src/uasset_read/cli.py

<interfaces>
<!-- Key functions the trace tool will call: -->
<!-- - archive.read_name(name_map) -- FName (8 bytes: i32 index + i32 number) -->
<!-- - archive.read_i32() -- i32 (4 bytes) -->
<!-- - archive.read_u8() -- u8 (1 byte) -->
<!-- - archive.read_u32() -- u32 (4 bytes) -->
<!-- - archive.read_fstring() -- FString (variable: 4-byte length + data) -->
<!-- - archive.read_bool_ue5() -- UE5 bool (1 byte) -->
<!-- - archive.read_bool() -- UE4 bool (4 bytes) -->
<!-- - archive.tell() -- current position -->
<!-- - archive.seek(pos) -- set position -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create binary trace tool with field-level position reporting</name>
  <files>tools/binary_trace_pin.py</files>
  <action>Create a standalone Python script that:

1. Accepts CLI arguments: `--asset <path>`, `--node-export-idx <index>`, `--pin-index <index>` (or `--pin-offset <offset>` for direct offset)
2. Loads the asset using parse_uasset() to get the PackageFileSummary (for file_version_ue5) and name_map
3. Seeks to the specified pin body offset (computed from the node export's script_serial_offset + script_serial_size + end_marker + pin headers)
4. Reads each pin body field sequentially, recording:
   - Field name
   - Archive position before read
   - Archive position after read
   - Bytes consumed (after - before)
   - Field value (or hex dump for binary data)
   - Expected bytes for UE5

5. Fields to trace in order:
   - PinName (FName: 8 bytes)
   - PinFriendlyName/FText (flags 4B + history_type 1B + b_has_culture 1B UE5/4B UE4 = 6/9 bytes for None type)
   - SourceIndex (i32: 4 bytes)
   - PinToolTip (FString: variable)
   - Direction (u8: 1 byte)
   - PinType:
     - PinCategory (FName: 8 bytes)
     - PinSubCategory (FName: 8 bytes)
     - PinSubCategoryObject (i32: 4 bytes)
     - ContainerType (u8: 1 byte)
     - bIsReference (bool: 1 byte UE5, 4 bytes UE4)
     - bIsWeakPointer (bool: 1 byte UE5, 4 bytes UE4)
     - MemberReference (i32 + FName + 16B: ~28 bytes)
     - bIsConst (bool: 1 byte UE5, 4 bytes UE4)
     - bIsUObjectWrapper (bool: 1 byte UE5, 4 bytes UE4)
   - DefaultValue (FString: variable)
   - AutoDefaultValue (FString: variable)
   - DefaultObject (i32: 4 bytes)
   - DefaultTextValue (FString: variable)
   - LinkedTo array count (i32: 4 bytes) -- CRITICAL: should show non-zero count after fixes
   - LinkedTo array elements (24 bytes each: b_null + owning + guid)

6. Output format: table with columns [Field, Before, After, Consumed, Expected, Delta]
7. Final summary: total bytes consumed, LinkedTo array_count value, drift detection

The tool should use the actual FArchive class and the existing read_* methods to ensure it mirrors the real parsing behavior. After the fixes are applied, it should use read_bool_ue5() where appropriate for UE5 assets.

Detect UE5 automatically via file_version_ue5 from the package summary and use read_bool_ue5() accordingly for bool fields.</action>
  <verify>
    <automated>python tools/binary_trace_pin.py --help</automated>
  </verify>
  <done>binary_trace_pin.py accepts --asset, --node-export-idx, --pin-index arguments and prints usage</done>
</task>

<task type="auto">
  <name>Task 2: Run binary trace on test asset and verify LinkedTo array_count</name>
  <files>tools/binary_trace_pin.py</files>
  <action>After the trace tool is created, run it on the test asset to generate a baseline trace. Use BP_FirstPersonCharacter.uasset and trace the first non-null pin in the first EventGraph node.

The tool should:
1. Print a table showing each field's position and consumption
2. Highlight fields where actual != expected consumption
3. Report the LinkedTo array_count value
4. After fixes (35b-01, 35b-02, 35b-03 applied), the trace should show:
   - Zero drift (all actual == expected)
   - LinkedTo array_count > 0

This step validates that the fixes resolve the byte drift issue. The trace output serves as evidence for the root cause fix.</action>
  <verify>
    <automated>python tools/binary_trace_pin.py --asset "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" --node-export-idx 0 --pin-index 0 2>&1 | head -30</automated>
  </verify>
  <done>Binary trace tool runs on test asset and reports LinkedTo array_count and drift status</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Binary input -> trace tool | .uasset files are untrusted; malformed data should not cause crashes |
| Trace output -> verification | Tool output must accurately reflect binary positions; incorrect tracing would mislead debugging |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35b-09 | Integrity | binary_trace_pin.py field tracing | mitigate | Use actual FArchive read methods; no manual byte interpretation -- mirrors real parsing |
| T-35b-10 | Denial of Service | Trace tool on malformed pin data | accept | Use try/except around each field read; report position on failure |
| T-35b-11 | Information Disclosure | Trace tool output | accept | Diagnostic tool only; outputs to stdout, no file writes or network access |
</threat_model>

<verification>
- tools/binary_trace_pin.py exists and runs with --help
- Tool accepts --asset, --node-export-idx, --pin-index arguments
- Tool traces all pin body fields with position tracking
- Tool reports LinkedTo array_count value
- Tool can be run on BP_FirstPersonCharacter.uasset to verify fixes
- All existing tests pass: `python -m pytest tests/ -x --tb=short`
</verification>

<success_criteria>
- tools/binary_trace_pin.py is a working standalone diagnostic tool
- Tool reports field positions, byte consumption, and drift detection
- Tool can trace any pin in any UE5 asset
- Tool confirms LinkedTo array_count > 0 after fixes are applied
- No regression in existing tests
</success_criteria>

<output>
After completion, create `.planning/phases/35b-pin-connection-debug/35b-04-SUMMARY.md`
</output>
