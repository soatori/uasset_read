---
phase: "35d"
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/parsers/property_types.py
autonomous: true
requirements: [MOD-08]
must_haves:
  truths:
    - "parse_array_property: remaining_size subtracts 4 bytes for count field"
    - "_extract_map_types_from_tag splits on first comma only, not all commas"
    - "parse_array_property/parse_map_property/parse_set_property validate entry count against upper bound"
  artifacts:
    - path: "src/uasset_read/parsers/property_types.py"
      provides: "Correct array/map/set parsing with bounds checking"
      contains: "remaining_size.*tag.size.*-.*4"
  key_links:
    - from: "src/uasset_read/parsers/property_types.py"
      to: "src/uasset_read/parsers/property_types.py"
      via: "parse_array_property count subtraction"
      pattern: "remaining_size"
---

<objective>
Fix property_types.py: correct array remaining_size calculation (CR-09), fix nested comma type splitting (MED-01), and add entry count validation (HIGH-07/35c-06).

Purpose: Ensure array elements parse correctly, map types with nested commas are correctly extracted, and malformed entries trigger ParseError instead of infinite loops or OOM.
</objective>

<execution_context>
@E:\Develop\uasset_read\.planning\phases\35d-logic-fixes\35d-PLAN.md
</execution_context>

<context>
@E:\Develop\uasset_read\src\uasset_read\parsers\property_types.py
@E:\Develop\uasset_read\.planning\PROJECT.md
@E:\Develop\uasset_read\.planning\ROADMAP.md
@E:\Develop\uasset_read\.planning\STATE.md
</context>

<interfaces>
From src/uasset_read/parsers/property_types.py:

```python
# Line 109-112: parse_array_property
# remaining_size = tag.size  <-- BUG: should subtract 4 for count field

# Line 323: _extract_map_types_from_tag
# params = inner.split(",")  <-- BUG: splits on ALL commas, including nested ones
# Should be: params = inner.split(",", 1)  # Split on first comma only

# parse_array_property: missing count validation (count < 0 or count > MAX_ELEMENTS)
# parse_map_property: missing num_entries validation (was already fixed in 35c-06)
# parse_set_property: missing num_elements validation (was already fixed in 35c-06)
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Fix array remaining_size calculation in parse_array_property</name>
  <files>src/uasset_read/parsers/property_types.py</files>
  <action>
In `src/uasset_read/parsers/property_types.py`, fix the remaining_size for array:

Change from:
```python
remaining_size = tag.size
```
To:
```python
remaining_size = tag.size - 4
```

The count field is a 4-byte uint32 that precedes the array elements. The remaining_size should only track element data remaining, not including the count field itself.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q</automated>
  </verify>
  <done>parse_array_property remaining_size = tag.size - 4 (subtracts count field)</done>
</task>

<task type="auto">
  <name>Task 2: Fix nested comma type splitting in _extract_map_types_from_tag</name>
  <files>src/uasset_read/parsers/property_types.py</files>
  <action>
In `src/uasset_read/parsers/property_types.py`, fix the params splitting at line 323:

Change from:
```python
params = inner.split(",")
```
To:
```python
params = inner.split(",", 1)
```

This ensures that only the first comma splits key_type and value_type. Nested commas in template types like "StructProperty /Game/Path.AssetName:StructName" are preserved.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q</automated>
  </verify>
  <done>_extract_map_types_from_tag splits on first comma only using split(",", 1)</done>
</task>

<task type="auto">
  <name>Task 3: Add entry count validation in parse_array_property</name>
  <files>src/uasset_read/parsers/property_types.py</files>
  <action>
In `src/uasset_read/parsers/property_types.py`, add count validation in parse_array_property:

After reading `count = reader.read_u32()`, add:
```python
MAX_ARRAY_COUNT = 1000000  # Same as MAX_PROPERTY_ARRAY_COUNT in 35c
if count > MAX_ARRAY_COUNT:
    raise ParseError(f"Array property count {count} exceeds maximum {MAX_ARRAY_COUNT}")
```

Import ParseError if not already imported.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q</automated>
  </verify>
  <done>parse_array_property validates count against MAX_ARRAY_COUNT</done>
</task>

</tasks>

<verification>
- grep -n "tag.size - 4" src/uasset_read/parsers/property_types.py
- grep -n 'split(",", 1)' src/uasset_read/parsers/property_types.py
- grep -n "MAX_ARRAY_COUNT" src/uasset_read/parsers/property_types.py
- python -m pytest tests/ -x -q
</verification>

<success_criteria>
- Array remaining_size correctly subtracts count field
- Map types with nested commas are extracted correctly
- Array property count validated against upper bound
- All tests pass with no regressions
</success_criteria>

<output>
After completion, create `.planning/phases/35d-logic-fixes/35d-01-SUMMARY.md`
</output>
