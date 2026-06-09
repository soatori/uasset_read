# C++ Parameter Binding Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix C++ parameter binding so that function parameters correctly trace through Knot node chains to their source FunctionEntry parameters.

**Architecture:** The issue is in `kismet/semantic.py::_resolve_param_name()` which reads from `input_params[].data_source` but the data_source tracing in `graph/_edge_traversal.py::_trace_data_source()` may not be properly handling Knot chains when called from `_extract_call_function_parameters()`. The fix involves ensuring Knot chain resolution works end-to-end.

**Tech Stack:** Python 3.10+, pytest, unittest.mock

---

### Task 1: Diagnose Knot Chain Resolution Failure

**Files:**
- Test: `tests/test_knot_chain_debug.py` (create temporary diagnostic test)
- Read: `src/uasset_read/graph/_edge_traversal.py:336-450`
- Read: `src/uasset_read/formatters/json_formatter.py:594-648`

- [ ] **Step 1: Create diagnostic test to inspect actual data_source values**

Create a test that parses the real blueprint and inspects the `input_params` structure for the Aim and Move functions:

```python
"""tests/test_knot_chain_debug.py — Diagnostic test for Knot chain resolution."""
import os
import pytest
from uasset_read.core import parse_single

_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
    "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)

@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
def test_inspect_aim_data_sources():
    """Inspect Aim function's data_source structure."""
    result = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
    
    # Find Aim function graph
    aim_graph = None
    for graph in result.get("graphs", []):
        if graph.get("graph_name") == "Aim":
            aim_graph = graph
            break
    
    assert aim_graph is not None, "Aim graph not found"
    
    # Find CallFunction nodes
    nodes = aim_graph.get("nodes", [])
    call_nodes = [n for n in nodes if n.get("node_type") == "K2Node_CallFunction"]
    
    print("\n=== Aim Function CallFunction Nodes ===")
    for node in call_nodes:
        func_name = node.get("function_name", "Unknown")
        params = node.get("parameters", {})
        input_params = params.get("input_params", [])
        print(f"\nFunction: {func_name}")
        for param in input_params:
            name = param.get("name", "")
            data_source = param.get("data_source", {})
            print(f"  Param: {name}")
            print(f"    data_source: {data_source}")

@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
def test_inspect_move_data_sources():
    """Inspect Move function's data_source structure."""
    result = parse_single(_REAL_BLUEPRINT, format="json", tolerant=True)
    
    # Find Move function graph
    move_graph = None
    for graph in result.get("graphs", []):
        if graph.get("graph_name") == "Move":
            move_graph = graph
            break
    
    assert move_graph is not None, "Move graph not found"
    
    # Find CallFunction nodes
    nodes = move_graph.get("nodes", [])
    call_nodes = [n for n in nodes if n.get("node_type") == "K2Node_CallFunction"]
    
    print("\n=== Move Function CallFunction Nodes ===")
    for node in call_nodes:
        func_name = node.get("function_name", "Unknown")
        params = node.get("parameters", {})
        input_params = params.get("input_params", [])
        print(f"\nFunction: {func_name}")
        for param in input_params:
            name = param.get("name", "")
            data_source = param.get("data_source", {})
            print(f"  Param: {name}")
            print(f"    data_source: {data_source}")
```

- [ ] **Step 2: Run diagnostic test to see actual data_source values**

Run: `python -m pytest tests/test_knot_chain_debug.py -v -s`

Expected: See the actual `data_source` structure for Pitch and ScaleValue parameters. Look for:
- Is `data_source` present at all?
- If present, what is `source_type`? (should be "function_parameter" for Pitch/ScaleValue)
- If `source_type` is "knot_chain_broken", the Knot resolution is failing

- [ ] **Step 3: Analyze the diagnostic output**

Based on the output, determine:
1. If `data_source` is missing → the issue is in `_extract_call_function_parameters()` not calling `_trace_data_source()`
2. If `data_source` has `source_type: "knot_chain_broken"` → the issue is in `_resolve_knot_chain()`
3. If `data_source` has `source_type: "function_parameter"` but wrong pin name → the issue is in how the pin name is extracted

- [ ] **Step 4: Commit diagnostic test**

```bash
git add tests/test_knot_chain_debug.py
git commit -m "test: add diagnostic test for Knot chain resolution"
```

---

### Task 2: Fix Knot Chain Resolution (if broken)

**Files:**
- Modify: `src/uasset_read/graph/_edge_traversal.py:336-450` (if `_resolve_knot_chain` is failing)
- OR Modify: `src/uasset_read/formatters/json_formatter.py:594-648` (if `_trace_data_source` is not being called)

- [ ] **Step 1: Identify the root cause from diagnostic output**

Based on Task 1 diagnostic output, determine which component is failing:
- If `data_source` is missing entirely → go to Step 2A
- If `data_source` has `source_type: "knot_chain_broken"` → go to Step 2B
- If `data_source` has correct structure but wrong values → go to Step 2C

- [ ] **Step 2A: Ensure `_trace_data_source` is called with required lookups**

If `data_source` is missing from `input_params`, the issue is that `_extract_call_function_parameters()` is called without the required `pin_lookup`, `node_lookup`, and `node_name_lookup` arguments.

Check `src/uasset_read/graph/_node_format.py:60-62`:

```python
if node.class_name == "K2Node_CallFunction":
    from uasset_read.formatters.json_formatter import _extract_call_function_parameters
    result["parameters"] = _extract_call_function_parameters(node)
```

This call is missing the lookup arguments! The function signature is:

```python
def _extract_call_function_parameters(
    node: Any,
    pin_lookup: Optional[Dict] = None,
    node_lookup: Optional[Dict] = None,
    node_name_lookup: Optional[Dict] = None
) -> Dict[str, List[Dict]]:
```

Fix: Pass the lookups to enable data_source tracing. But wait — `format_node_dict()` doesn't have access to the graph-level lookups. This means we need to refactor to pass graph context down, OR do the data_source enhancement at a higher level.

**Better approach:** The data_source enhancement should happen in `build_data_flows()` or a similar graph-level function that has access to all nodes and pins. Check if there's a post-processing step that enhances node parameters with data_source info.

Actually, looking at the code flow:
1. `format_node_dict()` creates basic node structure
2. `build_data_flows()` creates separate data_flow objects
3. But `input_params[].data_source` needs to be populated during node formatting

The issue is architectural: `format_node_dict()` is called per-node without graph context, but data_source tracing requires graph-wide lookups.

**Solution:** Add a post-processing step in the graph building pipeline that enriches CallFunction nodes with data_source info after all nodes are formatted.

- [ ] **Step 2B: Fix `_resolve_knot_chain()` if it's returning broken status**

If the diagnostic shows `source_type: "knot_chain_broken"`, read `_resolve_knot_chain()` in `_edge_traversal.py` and fix the Knot traversal logic.

- [ ] **Step 2C: Fix pin name extraction if data_source structure is correct but values are wrong**

If the diagnostic shows `source_type: "function_parameter"` but the pin name is wrong (e.g., "Val" instead of "Pitch"), the issue is in how the terminal pin name is extracted after Knot resolution.

- [ ] **Step 3: Write failing test for the fix**

Based on the diagnosis, write a unit test that reproduces the issue:

```python
def test_knot_chain_resolves_to_function_parameter():
    """Knot chain should resolve to the original FunctionEntry parameter."""
    # Setup: Create mock nodes with Knot chain
    # FunctionEntry:Pitch → Knot_6:InputPin → Knot_6:OutputPin → Knot_5:InputPin → Knot_5:OutputPin → CallFunction:Val
    
    # Execute: Call _trace_data_source on CallFunction:Val pin
    
    # Assert: data_source should have source_type="function_parameter" and pin="Pitch"
```

- [ ] **Step 4: Implement the fix**

Implement the minimal fix based on the diagnosis.

- [ ] **Step 5: Run test to verify fix**

Run: `python -m pytest tests/test_knot_chain_debug.py -v`

Expected: All tests pass

- [ ] **Step 6: Run C++ quality gate tests**

Run: `python -m pytest tests/test_cpp_quality_gate.py::TestCppParameterBinding -v`

Expected: All 6 tests pass, including:
- `test_aim_binds_pitch_parameter`
- `test_move_no_undefined_pin_names`

- [ ] **Step 7: Commit the fix**

```bash
git add src/uasset_read/graph/_edge_traversal.py  # or whichever file was modified
git commit -m "fix: resolve Knot chain data flow to FunctionEntry parameters"
```

---

### Task 3: Full Test Suite Verification

- [ ] **Step 1: Run full test suite**

Run: `python scripts/test_matrix.py all`

Expected: 100% pass rate, 0 failures, 0 errors

- [ ] **Step 2: Verify C++ output manually**

Run: `python run.py E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset --cpp-skeleton`

Expected output should contain:
```cpp
void Aim(float Yaw, float Pitch) {
    AddControllerYawInput(Yaw);
    AddControllerPitchInput(Pitch);  // Not Val
}

void Move(float Left__Right, float Forward__Backward) {
    AddMovementInput(GetActorRightVector(), Left__Right, false);  // Not ScaleValue
    AddMovementInput(GetActorForwardVector(), Forward__Backward, false);  // Not ScaleValue
}
```

- [ ] **Step 3: Clean up diagnostic test**

Remove or convert the diagnostic test to a permanent regression test:

```bash
git rm tests/test_knot_chain_debug.py
git commit -m "chore: remove diagnostic test"
```

OR convert to a proper regression test that asserts the correct behavior.

- [ ] **Step 4: Final commit and verification**

Run: `python scripts/test_matrix.py quality`

Expected: All quality gates pass

---

## Summary

This plan focuses on diagnosing and fixing the Knot chain resolution issue that prevents proper C++ parameter binding. The key insight is that:

1. **Yaw works** because it has a direct connection: `FunctionEntry:Yaw → CallFunction:Val`
2. **Pitch fails** because it goes through Knot nodes: `FunctionEntry:Pitch → Knot_6 → Knot_5 → CallFunction:Val`
3. The `_trace_data_source()` function already has Knot resolution logic via `_resolve_knot_chain()`, but it may not be called with the required lookups, or the Knot resolution itself may be failing.

The diagnostic test in Task 1 will reveal the exact failure point, allowing us to apply the minimal fix in Task 2.
