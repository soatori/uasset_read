---
phase: "35d"
plan: 06
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/constants.py
  - src/uasset_read/parsers/property_parser.py
  - src/uasset_read/parsers/property_types.py
autonomous: true
requirements: [MOD-08]
must_haves:
  truths:
    - "PROPERTY_TAG_COMPLETE_TYPE_NAME and UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME are not duplicate definitions"
    - "property_parser.py has no unreachable return None after raise"
    - "property_types.py has no duplicate _derive_node_name function"
  artifacts:
    - path: "src/uasset_read/constants.py"
      provides: "Clean constants without duplication"
      contains: "PROPERTY_TAG_COMPLETE_TYPE_NAME"
    - path: "src/uasset_read/parsers/property_parser.py"
      provides: "No dead code after raise"
      contains: "ParseError"
    - path: "src/uasset_read/parsers/property_types.py"
      provides: "No duplicate _derive_node_name"
      contains: "def _derive_node_name"
---

<objective>
Clean up code quality issues: remove duplicate constants (MED-14), dead code after raise (HIGH-08), and duplicate _derive_node_name function (MED-14).

Purpose: Reduce technical debt, eliminate confusion from duplicate definitions, and remove unreachable code paths.
</objective>

<execution_context>
@E:\Develop\uasset_read\.planning\phases\35d-logic-fixes\35d-PLAN.md
</execution_context>

<context>
@E:\Develop\uasset_read\src\uasset_read\constants.py
@E:\Develop\uasset_read\src\uasset_read\parsers\property_parser.py
@E:\Develop\uasset_read\src\uasset_read\parsers\property_types.py
@E:\Develop\uasset_read\.planning\PROJECT.md
@E:\Develop\uasset_read\.planning\ROADMAP.md
@E:\Develop\uasset_read\.planning\STATE.md
</context>

<interfaces>
From src/uasset_read/constants.py:
```python
# Line 50: PROPERTY_TAG_COMPLETE_TYPE_NAME = "PropertyTagCompleteTypeName"
# Line 85: UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = "PropertyTagCompleteTypeName"  <-- DUPLICATE?
```

From src/uasset_read/parsers/property_parser.py:
```python
# Line 97: return None  # <-- DEAD CODE: unreachable after raise on line 96
```

From src/uasset_read/parsers/property_types.py:
```python
# Line 445-451: def _derive_node_name(...)  <-- DUPLICATE: same function exists in flow_builder.py
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Fix duplicate constants and dead code</name>
  <files>src/uasset_read/constants.py, src/uasset_read/parsers/property_parser.py, src/uasset_read/parsers/property_types.py</files>
  <action>
**Fix 1 — constants.py duplicate (MED-14):**
Read constants.py lines 40-95 to understand the relationship. If the two constants are identical values, keep one as the primary definition and make the other an alias with a comment.

Example:
```python
PROPERTY_TAG_COMPLETE_TYPE_NAME = "PropertyTagCompleteTypeName"
# Alias for UE5 compatibility
UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = PROPERTY_TAG_COMPLETE_TYPE_NAME
```

**Fix 2 — property_parser.py dead code (HIGH-08):**
At line 97, remove the unreachable `return None` after a `raise` statement. The `raise ParseError(...)` on the previous line already exits the function.

Read the actual code to understand the exact context.

**Fix 3 — property_types.py duplicate function (MED-14):**
At lines 445-451, remove the `_derive_node_name` function if it's a duplicate of the one in `flow_builder.py`. If the function is used within property_types.py, check whether it's called from within this file or only from the flow_builder.py version. Remove the misplaced duplicate.

Read the actual files to confirm exact locations and relationships.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q</automated>
  </verify>
  <done>constants.py has clean deduplicated constants; property_parser.py has no dead code after raise; property_types.py has no duplicate _derive_node_name</done>
</task>

</tasks>

<verification>
- grep -n "PROPERTY_TAG_COMPLETE_TYPE_NAME" src/uasset_read/constants.py
- python -m pytest tests/ -x -q
</verification>

<success_criteria>
- Constants without duplication (clear primary + alias when needed)
- No unreachable dead code after raise
- No duplicate function definitions
- All tests pass with no regressions
</success_criteria>

<output>
After completion, create `.planning/phases/35d-logic-fixes/35d-06-SUMMARY.md`
</output>
