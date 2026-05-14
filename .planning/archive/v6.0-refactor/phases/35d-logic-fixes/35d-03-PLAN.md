---
phase: "35d"
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/models/properties.py
autonomous: true
requirements: [MOD-08]
must_haves:
  truths:
    - "StructValue has default property_type='StructProperty'"
    - "MapValue has default property_type='MapProperty'"
    - "SetValue has default property_type='SetProperty'"
    - "Each XXXValue subclass declares its own default property_type"
  artifacts:
    - path: "src/uasset_read/models/properties.py"
      provides: "Default property_type values for all Value subclasses"
      contains: "class StructValue"
---

<objective>
Add default property_type values to StructValue, MapValue, SetValue and other Value subclasses in properties.py (CR-13).

Purpose: Ensure subclasses don't require manually passing property_type on construction — each subclass should declare its own default.
</objective>

<execution_context>
@E:\Develop\uasset_read\.planning\phases\35d-logic-fixes\35d-PLAN.md
</execution_context>

<context>
@E:\Develop\uasset_read\src\uasset_read\models\properties.py
@E:\Develop\uasset_read\.planning\PROJECT.md
@E:\Develop\uasset_read\.planning\ROADMAP.md
@E:\Develop\uasset_read\.planning\STATE.md
</context>

<interfaces>
From src/uasset_read/models/properties.py:

```python
@dataclass
class StructValue(PropertyValue):
    struct_type: str = ""
    fields: Dict[str, Any] = field(default_factory=dict)
    # Missing: property_type: str = "StructProperty"

@dataclass
class MapValue(PropertyValue):
    key_type: str = ""
    value_type: str = ""
    entries: List[Dict[str, Any]] = field(default_factory=list)
    # Missing: property_type: str = "MapProperty"

@dataclass
class SetValue(PropertyValue):
    element_type: str = ""
    elements: List[Any] = field(default_factory=list)
    # Missing: property_type: str = "SetProperty"

# Possibly more subclasses with missing defaults
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Add default property_type to all Value subclasses</name>
  <files>src/uasset_read/models/properties.py</files>
  <action>
In `src/uasset_read/models/properties.py`:

For `StructValue` (around line 45):
Add `property_type: str = "StructProperty"` as a field.

For `MapValue` (around line 55-60):
Add `property_type: str = "MapProperty"` as a field.

For `SetValue` (around line 65-70):
Add `property_type: str = "SetProperty"` as a field.

For any other Value subclass without an explicit property_type default:
Add the appropriate default (e.g., "ArrayProperty", "TextProperty", etc. based on class name convention).

Read the full file to identify ALL Value subclasses and add defaults where missing.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q</automated>
  </verify>
  <done>All Value subclasses have default property_type values</done>
</task>

</tasks>

<verification>
- python -m pytest tests/ -x -q
- Check each Value subclass has property_type default
</verification>

<success_criteria>
- Every Value subclass declares its own default property_type
- No manual property_type passing needed in tests or usage
- All tests pass with no regressions
</success_criteria>

<output>
After completion, create `.planning/phases/35d-logic-fixes/35d-03-SUMMARY.md`
</output>
