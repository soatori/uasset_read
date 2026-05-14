---
phase: "35d"
plan: 04
type: execute
wave: 2
depends_on: ["02"]
files_modified:
  - src/uasset_read/formatters/json_formatter.py
  - src/uasset_read/formatters/markdown_formatter.py
  - src/uasset_read/blueprint/transform_parser.py
autonomous: true
requirements: [MOD-09]
must_haves:
  truths:
    - "MapValue entries are recursively serialized in JSON output (not raw dataclass objects)"
    - "SetValue elements are recursively serialized in JSON output"
    - "Transform parsing returns defaults (0.0) when struct fields are missing"
    - "Markdown tables are not broken by pipe characters in asset names"
  artifacts:
    - path: "src/uasset_read/formatters/json_formatter.py"
      provides: "Recursive serialization for MapValue entries and SetValue elements"
      exports: ["serialize_property_value"]
    - path: "src/uasset_read/formatters/markdown_formatter.py"
      provides: "Markdown table cell escaping"
      exports: ["format_markdown"]
    - path: "src/uasset_read/blueprint/transform_parser.py"
      provides: "Safe dict access for transform field extraction"
      exports: ["parse_vector_value", "parse_rotator_value", "parse_scale_value"]
  key_links:
    - from: "src/uasset_read/formatters/json_formatter.py"
      to: "src/uasset_read/models/properties.py"
      via: "serialize_property_value recursive calls on MapValue entries"
      pattern: "serialize_property_value.*depth.*\\+.*1"
    - from: "src/uasset_read/blueprint/transform_parser.py"
      to: "src/uasset_read/models/properties.py"
      via: "fields.get() instead of fields[]"
      pattern: "fields\\.get\\("
---

<objective>
Fix three formatter/transform bugs: MapValue/SetValue recursive JSON serialization (CR-14/CR-15), markdown table pipe escaping (HIGH-17), and transform parser KeyError protection (HIGH-09).

Purpose: Ensure nested property values serialize correctly to JSON, prevent markdown table corruption, and handle missing transform fields gracefully.
Output: Corrected json_formatter.py, markdown_formatter.py, transform_parser.py with regression tests.
</objective>

<execution_context>
@E:\Develop\uasset_read\.planning\phases\35d-logic-fixes\35d-RESEARCH.md
@E:\Develop\uasset_read\REVIEW.md
</execution_context>

<context>
@E:\Develop\uasset_read\.planning\PROJECT.md
@E:\Develop\uasset_read\.planning\ROADMAP.md
@E:\Develop\uasset_read\.planning\STATE.md
@E:\Develop\uasset_read\src\uasset_read\formatters\json_formatter.py
@E:\Develop\uasset_read\src\uasset_read\formatters\markdown_formatter.py
@E:\Develop\uasset_read\src\uasset_read\blueprint\transform_parser.py
@E:\Develop\uasset_read\src\uasset_read\models\transforms.py
</context>

<interfaces>
<!-- Key types and contracts the executor needs -->

From src/uasset_read/formatters/json_formatter.py (lines 134-190):
```python
def serialize_property_value(value: Any, depth: int = 0, max_depth: int = 10) -> Any:
    # Line 148: if depth > max_depth: return "[deep nesting truncated]"
    # Line 154-158: StructValue → recursive {"fields": {k: serialize_property_value(v, depth + 1, max_depth)}}
    # Line 159-163: MapValue → {"entries": value.entries}  <-- BUG: no recursion
    # Line 165-168: SetValue → {"elements": value.elements}  <-- BUG: no recursion
```

From src/uasset_read/blueprint/transform_parser.py (lines 16-40):
```python
def parse_vector_value(struct_value: StructValue, precision_type: str = 'location') -> VectorValue:
    fields = struct_value.fields
    x = format_transform_value(fields["X"], precision_type)  # <-- KeyError if missing
    y = format_transform_value(fields["Y"], precision_type)  # <-- KeyError if missing
    z = format_transform_value(fields["Z"], precision_type)  # <-- KeyError if missing
    return VectorValue(x=x, y=y, z=z)
```

From src/uasset_read/formatters/markdown_formatter.py (lines 40-100):
```python
# Lines 43, 58, 100: f"| {name} | {cls} | {parent} |"  <-- No escaping of | in values
```

From src/uasset_read/models/transforms.py:
```python
def format_transform_value(value, precision_type: str) -> float:
    # Handles float/int/str → float conversion
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix MapValue/SetValue recursive JSON serialization and transform parser KeyError</name>
  <files>src/uasset_read/formatters/json_formatter.py, src/uasset_read/blueprint/transform_parser.py</files>
  <read_first>
    - src/uasset_read/formatters/json_formatter.py (lines 134-190 for serialize_property_value, lines 159-168 for MapValue/SetValue bugs)
    - src/uasset_read/blueprint/transform_parser.py (lines 16-40 for parse_vector_value, parse_rotator_value, parse_scale_value)
    - src/uasset_read/models/properties.py (StructValue, MapValue, SetValue dataclass definitions)
  </read_first>
  <behavior>
    - Test 1: MapValue with StructValue entry → entries[0].value.fields recursively serialized (not raw dataclass repr)
    - Test 2: SetValue with MapValue element → elements[0] recursively serialized
    - Test 3: parse_vector_value with missing "X" field → returns VectorValue(x=0.0, y=0.0, z=0.0)
    - Test 4: parse_rotator_value with missing "Roll" field → returns RotatorValue(roll=0.0, pitch=0.0, yaw=0.0)
    - Test 5: parse_scale_value with missing "Z" field → returns ScaleValue(x=0.0, y=0.0, z=0.0)
    - Test 6: Deeply nested MapValue in MapValue → depth+1 passed correctly, truncation at max_depth
  </behavior>
  <action>
In `src/uasset_read/formatters/json_formatter.py`:

**Fix 1 — CR-14: MapValue entries not recursively serialized (lines 159-163)**

Change from:
```python
if hasattr(value, "entries") and hasattr(value, "key_type"):  # MapValue
    return {
        "key_type": value.key_type,
        "value_type": value.value_type,
        "entries": value.entries
    }
```
To:
```python
if hasattr(value, "entries") and hasattr(value, "key_type"):  # MapValue
    return {
        "key_type": value.key_type,
        "value_type": value.value_type,
        "entries": [
            {
                "key": serialize_property_value(entry.get("key"), depth + 1, max_depth),
                "value": serialize_property_value(entry.get("value"), depth + 1, max_depth),
            }
            for entry in value.entries
        ]
    }
```

**Fix 2 — CR-15: SetValue elements not recursively serialized (lines 165-168)**

Change from:
```python
if hasattr(value, "elements") and hasattr(value, "element_type"):  # SetValue
    return {
        "element_type": value.element_type,
        "elements": value.elements
    }
```
To:
```python
if hasattr(value, "elements") and hasattr(value, "element_type"):  # SetValue
    return {
        "element_type": value.element_type,
        "elements": [serialize_property_value(elem, depth + 1, max_depth) for elem in value.elements]
    }
```

In `src/uasset_read/blueprint/transform_parser.py`:

**Fix 3 — HIGH-09: KeyError on missing dict fields (lines 19-21, 28-30, 37-39)**

Change parse_vector_value (lines 19-21) from:
```python
x = format_transform_value(fields["X"], precision_type)
y = format_transform_value(fields["Y"], precision_type)
z = format_transform_value(fields["Z"], precision_type)
```
To:
```python
x = format_transform_value(fields.get("X", 0.0), precision_type)
y = format_transform_value(fields.get("Y", 0.0), precision_type)
z = format_transform_value(fields.get("Z", 0.0), precision_type)
```

Change parse_rotator_value (lines 28-30) from:
```python
roll = format_transform_value(fields["Roll"], 'rotation')
pitch = format_transform_value(fields["Pitch"], 'rotation')
yaw = format_transform_value(fields["Yaw"], 'rotation')
```
To:
```python
roll = format_transform_value(fields.get("Roll", 0.0), 'rotation')
pitch = format_transform_value(fields.get("Pitch", 0.0), 'rotation')
yaw = format_transform_value(fields.get("Yaw", 0.0), 'rotation')
```

Change parse_scale_value (lines 37-39) from:
```python
x = format_transform_value(fields["X"], 'scale')
y = format_transform_value(fields["Y"], 'scale')
z = format_transform_value(fields["Z"], 'scale')
```
To:
```python
x = format_transform_value(fields.get("X", 0.0), 'scale')
y = format_transform_value(fields.get("Y", 0.0), 'scale')
z = format_transform_value(fields.get("Z", 0.0), 'scale')
```

**Tests**: Create `tests/test_phase35d_formatter_transform_fixes.py` with:
- `test_mapvalue_entries_recursive_serialization`: Create MapValue with entries containing StructValue. Call serialize_property_value. Assert entries[0]["value"] is a dict with "struct_type" key (not a dataclass).
- `test_setvalue_elements_recursive_serialization`: Create SetValue with elements containing MapValue. Call serialize_property_value. Assert elements[0] is a dict with "key_type" key (not a dataclass).
- `test_deeply_nested_map_truncated_at_max_depth`: Create MapValue nested 12 levels deep. Call serialize_property_value with max_depth=10. Assert "[deep nesting truncated]" appears.
- `test_parse_vector_value_missing_fields`: Create StructValue with empty fields. Call parse_vector_value. Assert returns VectorValue(x=0.0, y=0.0, z=0.0).
- `test_parse_rotator_value_missing_fields`: Create StructValue with empty fields. Call parse_rotator_value. Assert returns RotatorValue(roll=0.0, pitch=0.0, yaw=0.0).
- `test_parse_scale_value_missing_fields`: Create StructValue with empty fields. Call parse_scale_value. Assert returns ScaleValue(x=0.0, y=0.0, z=0.0).
- `test_parse_vector_value_with_partial_fields`: Create StructValue with only fields={"X": 1.5}. Call parse_vector_value. Assert returns VectorValue(x=1.5, y=0.0, z=0.0).
</action>
  <verify>
    <automated>python -m pytest tests/test_phase35d_formatter_transform_fixes.py -x -v</automated>
  </verify>
  <done>MapValue entries and SetValue elements recursively serialized via serialize_property_value; transform parser uses .get() with 0.0 defaults; all 7 tests pass</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add markdown table pipe character escaping</name>
  <files>src/uasset_read/formatters/markdown_formatter.py</files>
  <read_first>
    - src/uasset_read/formatters/markdown_formatter.py (entire file, lines 1-166)
    - Lines 43, 44, 48, 58, 62, 100 where table cells are written without escaping
  </read_first>
  <behavior>
    - Test 1: format_markdown with asset name containing "Pipe|Test" → output table line has "Pipe\\|Test"
    - Test 2: format_markdown with multiline value → newlines replaced with spaces in table cells
    - Test 3: Normal asset names without pipe chars are unaffected
  </behavior>
  <action>
In `src/uasset_read/formatters/markdown_formatter.py`:

**Fix — HIGH-17: Table pipe character not escaped**

Add helper function after imports (before line 18):
```python
def _escape_md_cell(text: str) -> str:
    """Escape characters that break markdown table formatting."""
    return str(text).replace("|", "\\|").replace("\n", " ")
```

Wrap ALL table cell values with `_escape_md_cell()`:

Line 43: `lines.append(f"| Package | {_escape_md_cell(result.summary.package_name)} |")`
Line 44: `lines.append(f"| Version | UE {_escape_md_cell(ue_version)} |")`
Line 48: `lines.append(f"| Status | {_escape_md_cell(status_info.status)} |")`
Line 50: `lines.append(f"| Message | {_escape_md_cell(status_info.message)} |")` (only if status_info.message)
Line 58: `lines.append(f"| Parent Class | {_escape_md_cell(result.blueprint.parent_class or 'Unknown')} |")`
Line 62: `lines.append(f"| Variables | {_escape_md_cell(f'{var_count} ({comp_count} components, {var_count - comp_count} regular)')} |")`
Line 95-100: In the exports loop:
```python
name = _escape_md_cell(exp.object_name)
cls = _escape_md_cell(get_asset_class(exp, result.import_map, result.export_map))
parent = _escape_md_cell(result.blueprint.parent_class or "") if result.blueprint and i == 0 else ""
lines.append(f"| {name} | {cls} | {parent} |")
```

**Tests**: Create `tests/test_phase35d_formatter_transform_fixes.py` (append to existing test file from Task 1):
- `test_markdown_pipe_char_escaped`: Create mock ParseResult with package_name containing "|". Call format_markdown. Assert output contains "\|" in the table line.
- `test_markdown_newline_escaped`: Create mock ParseResult with multiline value. Call format_markdown. Assert output has no literal newlines in table cells (only between table rows).
- `test_markdown_normal_names_unchanged`: Create mock ParseResult with simple names (no pipe or newline). Call format_markdown. Assert no "\|" appears in output.
</action>
  <verify>
    <automated>python -m pytest tests/test_phase35d_formatter_transform_fixes.py -x -v</automated>
  </verify>
  <done>_escape_md_cell function exists and is called for all table cells; pipe chars and newlines escaped; all 3 tests pass</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Binary file → json_formatter | Nested MapValue/SetValue produce raw dataclass repr instead of valid JSON |
| User input → markdown_formatter | Asset names with pipe chars break markdown table rendering |
| Binary file → transform_parser | Missing struct fields cause KeyError crash |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35d-08 | Data Integrity | serialize_property_value (MapValue) | mitigate | Recursively call serialize_property_value on each entry's key and value |
| T-35d-09 | Data Integrity | serialize_property_value (SetValue) | mitigate | Recursively call serialize_property_value on each element |
| T-35d-10 | Denial of Service | transform_parser | mitigate | Use .get() with 0.0 default instead of direct dict access for X/Y/Z/Roll/Pitch/Yaw |
| T-35d-11 | Data Integrity | markdown_formatter | mitigate | Add _escape_md_cell() to escape | and \n in all table cell values |
</threat_model>

<verification>
- python -m pytest tests/test_phase35d_formatter_transform_fixes.py -x -v
- python -m pytest tests/ -x -q (no regression)
- grep -n "serialize_property_value.*depth.*+.*1" src/uasset_read/formatters/json_formatter.py (confirms recursive calls)
- grep -n "fields\.get(" src/uasset_read/blueprint/transform_parser.py (confirms safe access)
- grep -n "_escape_md_cell" src/uasset_read/formatters/markdown_formatter.py (confirms escaping)
</verification>

<success_criteria>
- MapValue entries and SetValue elements fully recursive-serialized to JSON-compatible dicts
- Transform parser returns 0.0 defaults for missing fields instead of crashing
- Markdown tables survive pipe characters and newlines in cell values
- All new tests pass, no existing tests regress
</success_criteria>

<output>
After completion, create `.planning/phases/35d-logic-fixes/35d-04-SUMMARY.md`
</output>
