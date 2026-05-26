---
phase: phase-72c
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/kismet/bpgc_bytecode.py
autonomous: true
requirements:
  - KISM-03
must_haves:
  truths:
    - "BPGC export's script_serial_region can be read via FArchive"
    - "Cooked bytecode format is parsed into per-function bytecode buffers"
    - "Each buffer maps to a Function export by name"
  artifacts:
    - path: "src/uasset_read/kismet/bpgc_bytecode.py"
      provides: "BPGC bytecode extraction and function mapping"
      exports: ["extract_bpgc_bytecode", "map_bytecode_to_functions"]
      min_lines: 80
  key_links:
    - from: "src/uasset_read/kismet/bpgc_bytecode.py"
      to: "src/uasset_read/archive.py"
      via: "FArchive stream reading"
      pattern: "archive\\.(seek|read_)"
    - from: "src/uasset_read/kismet/bpgc_bytecode.py"
      to: "src/uasset_read/serializers/object_resources.py"
      via: "detect_blueprint_generated_class, find_main_blueprint_generated_class"
      pattern: "detect_blueprint_generated_class|find_main_blueprint"
---

<objective>
Create BPGC bytecode extraction module that reads BlueprintGeneratedClass script_serial_region, parses the cooked bytecode format into per-function buffers, and maps each buffer to its corresponding Function export.

Purpose: The current `extract_bytecode_bytes()` returns None for UE5 cooked Blueprints because Function export serial data contains no bytecode — it lives in the BPGC. This module provides the fallback extraction path.

Output: `src/uasset_read/kismet/bpgc_bytecode.py` with two public functions.
</objective>

<execution_context>
@.planning/ROADMAP.md
@.planning/STATE.md
@src/uasset_read/kismet/bytecode_extractor.py
@src/uasset_read/kismet/archive.py
@src/uasset_read/serializers/object_resources.py
@src/uasset_read/kismet/tokens.py
</execution_context>

<context>
@src/uasset_read/kismet/bytecode_extractor.py
@src/uasset_read/kismet/archive.py
@src/uasset_read/serializers/object_resources.py
@src/uasset_read/kismet/tokens.py

<interfaces>
From src/uasset_read/serializers/object_resources.py:
```python
@dataclass
class ObjectExport:
    class_index: PackageIndex
    super_index: PackageIndex
    outer_index: PackageIndex
    object_name: str
    object_flags: int
    serial_size: int
    serial_offset: int
    script_serial_size: int = 0
    script_serial_offset: int = 0
    # ... other fields

def detect_blueprint_generated_class(export, import_map, export_map) -> bool:
    """检测导出是否为 BlueprintGeneratedClass。"""

def find_main_blueprint_generated_class(export_map, import_map, asset_name) -> Optional[ObjectExport]:
    """查找主 BlueprintGeneratedClass 导出。"""
```

From src/uasset_read/kismet/archive.py:
```python
class FKismetArchive(FArchive):
    def __init__(self, data: bytes, name: str, name_map: list[str], tolerant: bool = False)
    def read_expression(self) -> KismetExpression
    def read_expression_array(self, end_token: EExprToken) -> list[KismetExpression]
```

From src/uasset_read/kismet/tokens.py:
```python
class EExprToken(Enum):
    EX_EndOfScript = 0x53  # Last byte in script code
```

From src/uasset_read/archive.py (FArchive methods used):
```python
def seek(self, pos)
def tell(self) -> int
def read_u8() -> int
def read_u32() -> int
def read_i32() -> int
def read_bytes(n) -> bytes
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create bpgc_bytecode.py module</name>
  <files>src/uasset_read/kismet/bpgc_bytecode.py</files>
  <action>
Create `src/uasset_read/kismet/bpgc_bytecode.py` with two public functions:

**`extract_bpgc_bytecode(archive, bpgc_export, summary, asset_name, name_map, import_map, export_map) -> dict[str, bytes]`**

1. Validate BPGC export: call `detect_blueprint_generated_class()` from object_resources to confirm the export is a BPGC. Return empty dict if not.
2. Check `bpgc_export.script_serial_size > 0`. If zero, return empty dict (no bytecode in this BPGC).
3. Calculate script start position using the same logic as `extract_bytecode_bytes()`: if `summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION`, use `serial_offset + script_serial_offset`, else use `serial_offset`.
4. Seek to script start position in archive.
5. Skip PropertyTags until "None" terminator (same loop as extract_bytecode_bytes using `read_property_tag`).
6. After "None", read the cooked bytecode format. The format is a sequence of per-function bytecode buffers:
   - Read a u32 size value (this is the bytecode buffer size for one function)
   - If size is 0 or exceeds remaining bytes in script_serial_region, stop parsing
   - Read `size` bytes as the function's bytecode buffer
   - The bytecode buffer should end with EX_EndOfScript (0x53) — use this to validate
   - Repeat until no more data or invalid size
7. Return dict mapping function index (as string: "0", "1", ...) to bytecode bytes.

**`map_bytecode_to_functions(bytecode_buffers, function_exports, name_map) -> dict[str, bytes]`**

1. Input: dict of {index_str: bytecode_bytes} from extract_bpgc_bytecode, list of Function exports, name_map.
2. Filter function_exports to only those with class "Function" (using resolve_class_name).
3. Map bytecode buffers to functions by name matching:
   - Strategy: BPGC bytecode buffers are in the same order as Function exports in the export table (UE cooked format convention)
   - Pair bytecode_buffers[i] with function_exports[i] by ordinal position
   - For each pair: use function_export.object_name as the function name key
4. Return dict mapping function_name to bytecode_bytes.
5. Log warning if buffer count != function count (mismatch in expected vs found).

**Error handling:**
- Use `ParseError` for invalid structures
- Use tolerant parsing for unknown tokens within bytecode buffers (EX_EndOfScript detection)
- Do NOT raise on empty buffers — return empty dict

**Imports needed:**
- `from uasset_read.archive import FArchive`
- `from uasset_read.serializers.object_resources import detect_blueprint_generated_class, resolve_class_name`
- `from uasset_read.serializers.property_tags import read_property_tag`
- `from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION`
- `from uasset_read.exceptions import ParseError`
- `from uasset_read.kismet.tokens import EExprToken`

**Do NOT:**
- Do NOT read raw bytes without using FArchive methods (FArchive stream parsing STRICT per project rules)
- Do NOT modify existing bytecode_extractor.py (that's Plan 03)
- Do NOT assume uncooked format (bytecodeBufferSize + serializedScriptSize header) — this is cooked format
  </action>
  <verify>
    <automated>python -c "from uasset_read.kismet.bpgc_bytecode import extract_bpgc_bytecode, map_bytecode_to_functions; print('OK')"</automated>
  </verify>
  <done>Module created with extract_bpgc_bytecode and map_bytecode_to_functions, importable without errors</done>
</task>

<task type="auto">
  <name>Task 2: Unit test for cooked bytecode parsing logic</name>
  <files>src/uasset_read/kismet/bpgc_bytecode.py</files>
  <action>
Within the same bpgc_bytecode.py file, add a helper function `_parse_cooked_bytecode_buffer(data: bytes) -> list[bytes]` that parses raw BPGC script region bytes into per-function buffers. This is the pure logic function (no archive dependency) that extract_bpgc_bytecode delegates to after reading the raw bytes.

The function:
1. Takes raw bytes (the script_serial_region content after PropertyTags)
2. Iterates: reads u32 size, extracts size bytes, validates ends with 0x53 (EX_EndOfScript) or 0xDD (cooked variant)
3. Returns list of bytecode buffers
4. Stops on invalid size (0 or exceeding remaining)

Add inline test via `if __name__ == "__main__"` block:
- Construct synthetic cooked bytecode buffer with 2 functions
- Call _parse_cooked_bytecode_buffer
- Assert 2 buffers returned, each ending with EX_EndOfScript
  </action>
  <verify>
    <automated>python -c "from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer; bufs = _parse_cooked_bytecode_buffer(b'\\x05\\x00\\x00\\x00\\x01\\x02\\x03\\x53\\x00'); assert len(bufs) == 1; assert bufs[0].endswith(b'\\x53'); print('OK')"</automated>
  </verify>
  <done>_parse_cooked_bytecode_buffer correctly splits synthetic buffer into individual function bytecode</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| File→FArchive | .uasset file content is untrusted binary data |
| script_serial_region→bytecode parser | BPGC script region may be malformed in corrupted files |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-72C-01 | Tampering | script_serial_region parsing | mitigate | Validate size values against remaining region bounds before each read; reject sizes exceeding region |
| T-72C-02 | Elevation of Privilege | function name mapping | mitigate | Use ordinal-based pairing (index position) only; do not trust function export names for buffer identification |
| T-72C-SC | Tampering | pip installs | mitigate | slopcheck + blocking human checkpoint for [ASSUMED]/[SUS] |
</threat_model>

<verification>
- Module imports without errors
- `_parse_cooked_bytecode_buffer` correctly splits synthetic multi-function buffer
- EX_EndOfScript (0x53) detection works at buffer boundaries
</verification>

<success_criteria>
1. `bpgc_bytecode.py` exists with `extract_bpgc_bytecode` and `map_bytecode_to_functions` functions
2. `_parse_cooked_bytecode_buffer` handles synthetic buffers correctly
3. Function signature matches FArchive stream parsing patterns (no raw byte reads)
4. Module is importable from `uasset_read.kismet.bpgc_bytecode`
</success_criteria>

<output>
Create `.planning/phases/phase-72c/01-01-SUMMARY.md` when done
</output>
