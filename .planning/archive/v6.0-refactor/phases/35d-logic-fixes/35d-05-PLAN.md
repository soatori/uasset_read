---
phase: "35d"
plan: 05
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/graph/flow_builder.py
autonomous: true
requirements: [MOD-08]
must_haves:
  truths:
    - "flow_builder handles non-list linked_to_raw values gracefully"
    - "flow_builder handles None node_guid without TypeError"
  artifacts:
    - path: "src/uasset_read/graph/flow_builder.py"
      provides: "Safe iteration and GUID checks"
      contains: "_safe_linked_to"
---

<objective>
Fix flow_builder.py: add safe iteration for linked_to_raw which may be non-list (LOW-06), and add None-check for node_guid before using in visited set (LOW-07).

Purpose: Prevent TypeError crashes when linked_to_raw is not iterable and when node_guid is None during graph traversal.
</objective>

<execution_context>
@E:\Develop\uasset_read\.planning\phases\35d-logic-fixes\35d-PLAN.md
</execution_context>

<context>
@E:\Develop\uasset_read\src\uasset_read\graph\flow_builder.py
@E:\Develop\uasset_read\.planning\PROJECT.md
@E:\Develop\uasset_read\.planning\ROADMAP.md
@E:\Develop\uasset_read\.planning\STATE.md
</context>

<interfaces>
From src/uasset_read/graph/flow_builder.py:

```python
# Line 204, 284, 414: linked_to_raw assumed to be iterable (list)
# Line 232: current_node.node_guid in visited — node_guid may be None
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Add _safe_linked_to helper and fix node_guid None check</name>
  <files>src/uasset_read/graph/flow_builder.py</files>
  <action>
In `src/uasset_read/graph/flow_builder.py`:

**Fix 1 — Add _safe_linked_to helper:**
Add a helper function:
```python
def _safe_linked_to(node):
    """Return linked_to as a list, handling None and non-list values."""
    raw = getattr(node, 'linked_to_raw', None)
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    return [raw]
```

**Fix 2 — Replace linked_to_raw iterations:**
At lines 204, 284, 414 (wherever linked_to_raw is iterated directly), replace with _safe_linked_to():
```python
# Before:
for link in node.linked_to_raw:
# After:
for link in _safe_linked_to(node):
```

**Fix 3 — Fix node_guid None check at line 232:**
Change from:
```python
if current_node.node_guid in visited:
```
To:
```python
if current_node.node_guid is not None and current_node.node_guid in visited:
```
Or more defensively:
```python
node_key = current_node.node_guid if current_node.node_guid is not None else id(current_node)
if node_key in visited:
```

Read the actual file to determine the exact line numbers and context.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q</automated>
  </verify>
  <done>flow_builder.py has _safe_linked_to helper and node_guid None guard; no TypeError on non-list linked_to_raw or None node_guid</done>
</task>

</tasks>

<verification>
- grep -n "_safe_linked_to" src/uasset_read/graph/flow_builder.py
- python -m pytest tests/ -x -q
</verification>

<success_criteria>
- Non-list linked_to_raw values don't cause TypeError
- None node_guid values don't cause TypeError in visited check
- All tests pass with no regressions
</success_criteria>

<output>
After completion, create `.planning/phases/35d-logic-fixes/35d-05-SUMMARY.md`
</output>
