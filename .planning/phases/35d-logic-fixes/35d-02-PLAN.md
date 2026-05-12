---
phase: "35d"
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/blueprint/variable_extractor.py
  - src/uasset_read/models/blueprint.py
  - src/uasset_read/formatters/json_formatter.py
autonomous: true
requirements: [MOD-08, MOD-09]
must_haves:
  truths:
    - "is_replicated flag maps to CPF_Replicated (0x00100000), not CPF_Net (0x00000020)"
    - "BlueprintVariable has no redundant meta_data field duplicating metadata"
  artifacts:
    - path: "src/uasset_read/blueprint/variable_extractor.py"
      provides: "Correct CPF flag mapping for is_replicated"
      contains: "is_replicated.*CPF_Replicated"
    - path: "src/uasset_read/models/blueprint.py"
      provides: "BlueprintVariable dataclass without duplicate metadata fields"
      contains: "class BlueprintVariable"
  key_links:
    - from: "src/uasset_read/blueprint/variable_extractor.py"
      to: "src/uasset_read/constants.py"
      via: "CPF_Replicated constant import"
      pattern: "CPF_Replicated"
---

<objective>
Fix blueprint variable extraction: correct is_replicated flag mapping (CR-11), remove BlueprintVariable's redundant meta_data field (LOW-04), and add hasattr guard for prop.type access (HIGH-10).

Purpose: Ensure network replication flags are correctly identified; eliminate redundant data duplication in model; prevent AttributeError on properties without type attribute.
Output: Corrected variable_extractor.py, blueprint.py, and json_formatter.py with regression tests.
</objective>

<execution_context>
@E:\Develop\uasset_read\.planning\phases\35d-logic-fixes\35d-RESEARCH.md
@E:\Develop\uasset_read\REVIEW.md
</execution_context>

<context>
@E:\Develop\uasset_read\.planning\PROJECT.md
@E:\Develop\uasset_read\.planning\ROADMAP.md
@E:\Develop\uasset_read\.planning\STATE.md
@E:\Develop\uasset_read\src\uasset_read\blueprint\variable_extractor.py
@E:\Develop\uasset_read\src\uasset_read\models\blueprint.py
@E:\Develop\uasset_read\src\uasset_read\constants.py
@E:\Develop\uasset_read\src\uasset_read\formatters\json_formatter.py
</context>

<interfaces>
<!-- Key types from codebase -->

From src/uasset_read/constants.py (lines 222-223):
```python
CPF_Net = 0x00000020          # Different from CPF_Replicated
CPF_Replicated = 0x00100000   # Correct flag for is_replicated
```

From src/uasset_read/blueprint/variable_extractor.py (lines 53-66):
```python
def _map_property_flags(flags: int) -> Dict[str, bool]:
    # Line 61: "is_replicated": bool(flags & CPF_Net),  <-- BUG
```

From src/uasset_read/models/blueprint.py (lines 118-156):
```python
@dataclass
class BlueprintVariable:
    # Line 128: metadata: Dict[str, str] = field(default_factory=dict)
    # Line 156: meta_data: Dict[str, Any] = field(default_factory=dict)  <-- DUPLICATE
```

From src/uasset_read/blueprint/variable_extractor.py (line 149):
```python
def _extract_pin_type_from_property(prop):
    prop_type = prop.type  # <-- HIGH-10: no hasattr guard
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix is_replicated flag mapping in _map_property_flags</name>
  <files>src/uasset_read/blueprint/variable_extractor.py</files>
  <read_first>
    - src/uasset_read/blueprint/variable_extractor.py (lines 53-66 for _map_property_flags, line 61 for the bug)
    - src/uasset_read/constants.py (CPF_Net = 0x00000020, CPF_Replicated = 0x00100000)
  </read_first>
  <behavior>
    - Test 1: flags = CPF_Replicated (0x00100000) → is_replicated=True, is_net=False
    - Test 2: flags = CPF_Net (0x00000020) → is_replicated=False, is_net=True
    - Test 3: flags = CPF_Net | CPF_Replicated → is_replicated=True, is_net=True
    - Test 4: flags = 0 → is_replicated=False, is_net=False
  </behavior>
  <action>
In `src/uasset_read/blueprint/variable_extractor.py`:

**Fix — CR-11: is_replicated uses wrong flag (line 61)**

Change line 61 from:
```python
"is_replicated": bool(flags & CPF_Net),
```
To:
```python
"is_replicated": bool(flags & CPF_Replicated),
```

CPF_Net (0x00000020) means "property is networked" — a broader concept.
CPF_Replicated (0x00100000) means "property is explicitly replicated" — the correct semantic for is_replicated.

Both constants are already imported at line 27 (`CPF_Replicated`).

**Tests**: Create `tests/test_phase35d_variable_extractor_fixes.py` with:
- `test_is_replicated_uses_cpf_replicated_not_cpf_net`: Call `_map_property_flags(flags=0x00100000)` (CPF_Replicated). Assert is_replicated=True and is_net=False.
- `test_is_net_uses_cpf_net_not_cpf_replicated`: Call `_map_property_flags(flags=0x00000020)` (CPF_Net). Assert is_net=True and is_replicated=False.
- `test_both_flags_set`: Call with `flags=0x00100020` (CPF_Net | CPF_Replicated). Assert both is_net=True and is_replicated=True.
- `test_no_flags`: Call with `flags=0`. Assert both are False.
</action>
  <verify>
    <automated>python -m pytest tests/test_phase35d_variable_extractor_fixes.py -x -v</automated>
  </verify>
  <done>_map_property_flags uses CPF_Replicated for is_replicated; all 4 tests pass; CPF_Net still mapped to is_net on line 60</done>
</task>

<task type="auto">
  <name>Task 2: Remove redundant meta_data field from BlueprintVariable</name>
  <files>src/uasset_read/models/blueprint.py, src/uasset_read/blueprint/variable_extractor.py, src/uasset_read/formatters/json_formatter.py</files>
  <read_first>
    - src/uasset_read/models/blueprint.py (lines 118-156 for BlueprintVariable dataclass)
    - src/uasset_read/blueprint/variable_extractor.py (line 543 where var.meta_data = var.metadata.copy())
    - src/uasset_read/formatters/json_formatter.py (line 369 where variable.meta_data is accessed)
  </read_first>
  <acceptance_criteria>
    - models/blueprint.py: BlueprintVariable dataclass no longer has `meta_data: Dict[str, Any]` field (was line 156)
    - variable_extractor.py: line 543 `var.meta_data = var.metadata.copy()` is removed
    - json_formatter.py: `_format_variable_enhanced` references `variable.metadata` (not `variable.meta_data`)
    - json_formatter.py line 369: `"meta_data": variable.metadata` instead of `"meta_data": variable.meta_data`
    - python -m pytest tests/ -x -q passes with 0 failures
  </acceptance_criteria>
  <action>
**LOW-04: Remove meta_data duplicate from BlueprintVariable**

In `src/uasset_read/models/blueprint.py`:
- Delete line 156: `meta_data: Dict[str, Any] = field(default_factory=dict)` from BlueprintVariable dataclass

In `src/uasset_read/blueprint/variable_extractor.py`:
- Delete line 543: `var.meta_data = var.metadata.copy()` (no longer needed since metadata field already exists)

In `src/uasset_read/formatters/json_formatter.py`:
- Line 369: Change `"meta_data": variable.meta_data` to `"meta_data": variable.metadata`
- This preserves the JSON output field name for backward compatibility while using the single source of truth
</action>
  <verify>
    <automated>python -m pytest tests/ -x -q</automated>
  </verify>
  <done>BlueprintVariable has only `metadata` field (no `meta_data`); variable_extractor.py no longer sets meta_data; json_formatter.py reads variable.metadata; no test regressions</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add hasattr guard for prop.type access in _extract_pin_type_from_property</name>
  <files>src/uasset_read/blueprint/variable_extractor.py</files>
  <read_first>
    - src/uasset_read/blueprint/variable_extractor.py (line 149 for prop.type access in _extract_pin_type_from_property)
  </read_first>
  <behavior>
    - Test 1: prop with type attribute → returns prop.type value
    - Test 2: prop without type attribute → returns None (no AttributeError)
    - Test 3: prop with type=None → returns None
  </behavior>
  <action>
**HIGH-10: Add hasattr guard before accessing prop.type**

In `src/uasset_read/blueprint/variable_extractor.py`, line 149 in `_extract_pin_type_from_property`:

Change from:
```python
prop_type = prop.type
```
To:
```python
prop_type = getattr(prop, 'type', None)
```

This prevents AttributeError when the property object does not have a `type` attribute.

**Tests**: Append to `tests/test_phase35d_variable_extractor_fixes.py`:
- `test_extract_pin_type_with_type_attribute`: Create mock prop with `type="IntProperty"`. Call `_extract_pin_type_from_property`. Assert returns "IntProperty".
- `test_extract_pin_type_without_type_attribute`: Create mock prop without type attribute (use `type(mock_prop) = type('MockProp', (), {})()`). Call function. Assert returns None (no AttributeError).
- `test_extract_pin_type_with_none_type`: Create mock prop with `type=None`. Call function. Assert returns None.
</action>
  <verify>
    <automated>python -m pytest tests/test_phase35d_variable_extractor_fixes.py -x -v</automated>
  </verify>
  <done>variable_extractor.py contains hasattr/getattr guard before prop.type access; all 3 tests pass; no AttributeError on properties without type</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Binary file → _map_property_flags | Wrong flag mapping produces incorrect variable metadata |
| Property object → _extract_pin_type_from_property | Missing type attribute causes AttributeError |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35d-05 | Data Integrity | _map_property_flags | mitigate | Map is_replicated to CPF_Replicated (0x00100000), not CPF_Net (0x00000020) |
| T-35d-06 | Data Integrity | BlueprintVariable | accept | meta_data removal is internal schema cleanup; JSON output preserves backward-compatible field name |
| T-35d-16 | Denial of Service | _extract_pin_type_from_property | mitigate | Use getattr(prop, 'type', None) instead of direct prop.type access |
</threat_model>

<verification>
- python -m pytest tests/test_phase35d_variable_extractor_fixes.py -x -v
- python -m pytest tests/ -x -q (no regression)
- grep -n "is_replicated.*CPF_Replicated" src/uasset_read/blueprint/variable_extractor.py (confirms fix)
- grep -v '^#' src/uasset_read/models/blueprint.py | grep -c "meta_data" (should be 0 after removal)
- grep -n "variable.metadata" src/uasset_read/formatters/json_formatter.py (confirms json_formatter uses metadata)
- grep -n "getattr(prop, 'type'" src/uasset_read/blueprint/variable_extractor.py (confirms HIGH-10 guard)
</verification>

<success_criteria>
- CPF_Replicated maps to is_replicated, CPF_Net maps to is_net (distinct flags)
- BlueprintVariable has single `metadata` field, no redundant `meta_data`
- JSON formatter preserves backward-compatible output field name using variable.metadata
- prop.type access guarded with hasattr/getattr to prevent AttributeError
- All tests pass with no regressions
</success_criteria>

<output>
After completion, create `.planning/phases/35d-logic-fixes/35d-02-SUMMARY.md`
</output>
