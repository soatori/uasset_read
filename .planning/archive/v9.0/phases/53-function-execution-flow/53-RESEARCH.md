# Phase 53: 函数内执行流追踪 - Research

**Researched:** 2026-05-17
**Domain:** Blueprint execution flow tracing, intra-function call chains
**Confidence:** HIGH

## Summary

Phase 53 builds on Phase 52's K2Node_FunctionEntry parsing to construct complete intra-function execution chains: from FunctionEntry through sequential CallFunction nodes along exec pins. The key finding is that **the code already supports ~80% of what Phase 53 needs** — `K2Node_FunctionEntry` is already in `START_EVENT_TYPES`, `_trace_execution_from_event()` already handles FunctionEntry nodes, and `build_execution_flows()` already picks them up as start events. The remaining ~20% consists of: (1) Knot node transparent traversal in execution flows, (2) Pure function marking in flow output, (3) proper `start_event` naming to distinguish Function vs Event, and (4) test coverage for FunctionEntry → CallFunction chains.

**Primary recommendation:** Minimal-diff approach — add Knot traversal and Pure function marking to `_trace_execution_from_event()`, improve `_get_start_event_name()` prefix format, add targeted unit tests. Do not create new arrays or restructuring (CONTEXT.md D-01 already decided to reuse `execution_flows`).

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 复用现有 `build_execution_flows()` 输出结构。FunctionEntry 自动作为 START_EVENT_TYPES 起点被纳入，每个函数生成独立的 execution_flow 条目，以 `start_event` 字段区分（如 `"FunctionEntry.Move"` vs `"Event.ReceiveBeginPlay"`）。不引入新的顶层数组。
- **D-02:** CallFunction 在执行流中仅记录引用 —— `{function_name, params}`。不递归展开被调用函数的内部执行流。
- **D-03:** Pure 函数（无 exec pin）在执行流追踪中跳过，不纳入 execution_flow 序列。它们是数据驱动的，留给 Phase 54 数据流追踪处理。执行流只追踪有 exec pin 的节点。
- **D-04:** 沿用 Phase 52 CONTEXT.md D-02 决定：Knot 节点透明穿透，不产生独立节点记录。执行流直接穿透到下一个有意义的节点。

### Claude's Discretion
- `_trace_execution_from_event` 中对 FunctionEntry 的 `_get_start_event_name` 实现细节由 planner 根据 Phase 52 的数据模型确定
- CallFunction 类型标记的具体字段结构（如 `is_blueprint_callable`, `target_graph` 等）由 researcher 根据 UE 源码确定

### Deferred Ideas (OUT OF SCOPE)
- Pure 函数的数据流追踪（返回值 → 参数输入） — Phase 54
- 跨图函数调用展开（递归展开被调用函数的 execution_flow） — 不在 v9.0 范围内
- JSON function_graphs 独立数组输出 — Phase 55
- 局部变量追踪 — v2 scope，不在 v9.0 范围内
- 控制流节点（Branch/DoOnce）详细展开 — v2 scope，不在 v9.0 范围内

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Function graph execution tracing | Graph/Flow Builder | — | `_trace_execution_from_event()` in `flow_builder.py` owns exec pin traversal |
| Knot node traversal | Graph/Flow Builder | — | Same function, needs modification to skip K2Node_Knot |
| Pure function detection | Graph/Flow Builder | Serializer | Detection via `node_data.b_defaults_to_pure` field from `read_k2node_call_function` |
| start_event naming | Graph/Flow Builder | — | `_get_start_event_name()` needs "FunctionEntry." prefix |
| JSON output | Formatters | Graph/Flow Builder | `_extract_call_function_parameters()` already extracts params |

## Standard Stack

No external packages — this phase is purely internal code changes to existing modules.

### Core (Internal Modules)
| Module | Purpose | Changes Needed |
|--------|---------|----------------|
| `graph/flow_builder.py` | Execution flow tracing | Knot traversal, Pure marking, start_event prefix |
| `constants.py` | START_EVENT_TYPES | Already contains K2Node_FunctionEntry (Phase 52) |
| `models/node_types.py` | K2Node dataclasses | Already has K2NodeFunctionEntry + K2NodeCallFunction.b_defaults_to_pure |
| `serializers/graph.py` | Binary deserialization | Already reads FunctionEntry and CallFunction |
| `formatters/json_formatter.py` | `_extract_call_function_parameters` | Already extracts input/output params |

### Version verification
All modules are internal — no version checks needed.

## Package Legitimacy Audit

No external packages to install. This phase is purely internal code modification.

## Architecture Patterns

### Current Execution Flow Pipeline

```
.uasset → extract_blueprint_graphs() → List[UEdGraph]
                                      ↓
                              build_execution_flows()
                                      ↓
                    [for each node in START_EVENT_TYPES:]
                                      ↓
                          _trace_execution_from_event()
                                      ↓
                    [follow exec output pins → next node]
                                      ↓
                    List[{"start_event": str, "nodes": [...]}]
```

### Function Graph vs EventGraph — Key Differences

| Aspect | EventGraph | Function Graph |
|--------|-----------|----------------|
| Start node type | K2Node_Event, K2Node_EnhancedInputAction, K2Node_CustomEvent | K2Node_FunctionEntry |
| Graph class | EdGraph | UberEdGraph (typically) |
| Identification | Contains K2Node_Event | Contains K2Node_FunctionEntry |
| Data pins | Event-driven data flow | Function parameters as output pins on FunctionEntry |
| Return | May have no return (event handler) | May have return via K2Node_FunctionResult (future) |
| Naming | Event name (e.g., "BeginPlay") | Function name (e.g., "Move") |

### Function Graph Execution Chain (from reference file)

The `Move` function in `BP_FirstPersonCharacter` demonstrates a typical function graph chain:

```
K2Node_FunctionEntry_0 ("Move")
  exec output pin → K2Node_CallFunction_7445 ("AddMovementInput")
    exec output pin → K2Node_CallFunction_7346 ("AddMovementInput")
      exec output pin → (none, chain ends)
```

Data flow (NOT exec flow) runs through Knot chains:
```
FunctionEntry "Left / Right" pin → Knot_2 → Knot_1 → CallFunction_7445 "ScaleValue"
FunctionEntry "Forward / Backward" pin → Knot_3 → Knot_4 → CallFunction_7346 "ScaleValue"
```

Pure function call (no exec pins, data-driven):
```
CallFunction_8029 ("GetActorForwardVector") → ReturnValue → CallFunction_7346 "WorldDirection"
CallFunction_8520 ("GetActorRightVector") → ReturnValue → CallFunction_7445 "WorldDirection"
```

### Recommended Code Changes

**`_trace_execution_from_event()` modifications needed:**

1. **Knot transparent traversal** (D-04): When `_find_next_exec_node()` returns a K2Node_Knot, the loop should NOT record it and should NOT break. Instead, continue to find the next non-Knot node. Currently, Knot nodes have no exec pins, so `_find_next_exec_node()` returns None for them — this naturally terminates the chain prematurely. **Fix:** Modify `_find_next_exec_node()` to skip Knot nodes, or add Knot detection in the main loop to continue searching.

   Actually, after closer analysis: K2Node_Knot does NOT have exec pins (it only has InputPin/OutputPin for data). So `_find_next_exec_node()` returns `None` when it hits a Knot — this is NOT a problem for execution flow since Knots are never on the exec path. Knots only appear on data paths. **No code change needed for Knot in execution flow** — they are naturally excluded.

   However, D-04 mentions "Knot 节点透明穿透" in the context of the execution flow. If a Knot somehow appears between two exec-connected nodes (unlikely but possible in malformed graphs), the traversal should skip it. **Recommendation:** Add a `isinstance()` check in the main loop to continue past Knot nodes without recording them.

2. **Pure function marking** (D-03): The CONTEXT says "Pure 函数（无 exec pin）在执行流追踪中跳过". However, the DISCUSSION LOG shows the user selected "标记 Pure 函数节点" — record them but mark as `pure=true`. This is a **conflict between CONTEXT.md D-03 and the DISCUSSION LOG**. The planner should resolve this — the discussion log represents the final user decision after deliberation.

   **Resolution:** The discussion log overrides D-03. Pure functions should be recorded in the flow with `"pure": true` flag, not skipped entirely. This requires checking `node_data.b_defaults_to_pure` for K2Node_CallFunction nodes.

3. **start_event naming**: `_get_start_event_name()` currently returns just `member_name` for FunctionEntry (e.g., `"Move"`). For C++ translation clarity, it should return `"FunctionEntry.Move"` to distinguish from events like `"Event.BeginPlay"`.

**`_find_next_exec_node()` analysis:**

The function correctly finds the next node via exec output pins. It checks `pin.direction == 1` and `pin.pin_type.pin_category == "exec"`, then follows `linked_to_raw` to find the target node. This works correctly for function graphs since the pin structure is identical to EventGraphs.

### Anti-Patterns to Avoid
- **Creating a separate `function_graphs` array**: CONTEXT.md D-01 explicitly rejects this. Phase 55 may add it, but Phase 53 must reuse `execution_flows`.
- **Recursively expanding CallFunction targets**: CONTEXT.md D-02 explicitly forbids this. Target functions may be in other blueprints or C++.
- **Mixing data flow with execution flow**: Pure function data dependencies belong in Phase 54. Phase 53 should only trace exec-pin-connected nodes.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exec pin traversal | New traversal function | `_find_next_exec_node()` | Already handles linked_to_raw resolution, cycle detection, and pin lookup |
| Start event detection | New start node finder | `build_execution_flows()` START_EVENT_TYPES filter | Already includes K2Node_FunctionEntry |
| CallFunction param extraction | Manual pin parsing | `_extract_call_function_parameters()` | Already filters exec pins, separates input/output |

**Key insight:** Phase 52 already laid all the groundwork. Phase 53 is primarily about refinement and testing, not new infrastructure.

## Runtime State Inventory

N/A — this is not a rename/refactor/migration phase.

## Common Pitfalls

### Pitfall 1: Knot Node Confusion in Execution Flow
**What goes wrong:** Assuming Knot nodes appear on exec paths and need special handling.
**Why it happens:** Knot nodes are prominent in function graph visual layouts (they relay function parameters to CallFunction nodes).
**How to avoid:** Understand that Knot nodes only have data pins (InputPin/OutputPin), never exec pins. They cannot appear on an exec chain. The only scenario where Knot matters is if a planner confuses data flow with execution flow.
**Warning signs:** Test fixtures that include Knot nodes in expected execution flow chains.

### Pitfall 2: Pure Function Detection via b_defaults_to_pure vs Actual Pins
**What goes wrong:** Relying solely on `b_defaults_to_pure` flag to detect pure functions.
**Why it happens:** `b_defaults_to_pure` indicates the function defaults to pure, but the actual purity is determined by the presence/absence of exec pins. A function can be set to non-pure even if `b_defaults_to_pure` is true.
**How to avoid:** Check for actual exec pins on the node (`any(pin.pin_type.pin_category == "exec" for pin in node.pins)`) rather than relying on the `b_defaults_to_pure` flag alone. If no exec pins exist, the node is pure regardless of the flag.
**Warning signs:** CallFunction nodes that have exec pins but `b_defaults_to_pure=true`.

### Pitfall 3: start_event Name Collision Between Event and FunctionEntry
**What goes wrong:** Both an Event named "Move" and a FunctionEntry named "Move" produce `start_event: "Move"`.
**Why it happens:** `_get_start_event_name()` returns just the member_name without a prefix.
**How to avoid:** Add a tier-specific prefix: `"FunctionEntry.{name}"` for FunctionEntry, `"Event.{name}"` for K2Node_Event, `"CustomEvent.{name}"` for K2Node_CustomEvent, etc.
**Warning signs:** Two execution flows with identical `start_event` values in the same blueprint.

### Pitfall 4: Missing Test Coverage for FunctionEntry Chains
**What goes wrong:** No tests verify FunctionEntry → CallFunction execution chains.
**Why it happens:** Current test `test_output_formatting.py` only tests Event → CallFunction, EnhancedInputAction, VariableSet, and CustomEvent start nodes. FunctionEntry is only tested as a constant membership check.
**How to avoid:** Add dedicated test fixture with FunctionEntry → CallFunction → CallFunction chain.
**Warning signs:** `grep K2Node_FunctionEntry tests/` returns only constant assertion.

## Code Examples

### Current `_trace_execution_from_event()` FunctionEntry handling (already present)
```python
# Source: src/uasset_read/graph/flow_builder.py L356-361
if current_node.class_name == "K2Node_FunctionEntry":
    nd = current_node.node_data
    if nd:
        fr = nd.get("function_reference") if isinstance(nd, dict) else getattr(nd, 'function_reference', None)
        if fr:
            node_info["function_name"] = getattr(fr, 'member_name', None)
```

### Current `_get_start_event_name()` FunctionEntry handling (needs prefix)
```python
# Source: src/uasset_read/graph/flow_builder.py L232-243
elif node.class_name == "K2Node_FunctionEntry":
    if not nd:
        return node.class_name
    if isinstance(nd, dict):
        fr = nd.get("function_reference")
    else:
        fr = getattr(nd, 'function_reference', None)
    if fr:
        mn = getattr(fr, 'member_name', None) if not isinstance(fr, dict) else fr.get("member_name")
        if mn and mn != "None":
            return mn  # ← Should be "FunctionEntry.{mn}"
    return node.class_name
```

### Move Function Execution Chain (from reference file)
The expected execution flow for the Move function:
```
FunctionEntry_0 (Move)
  → exec pin → CallFunction_7445 (AddMovementInput)  [gets Right/Left data via knots]
    → exec pin → CallFunction_7346 (AddMovementInput) [gets Forward/Backward data via knots]
      → exec pin → (none, terminates)
```

Pure functions NOT on exec path:
- CallFunction_8029 (GetActorForwardVector) — pure, no exec pins
- CallFunction_8520 (GetActorRightVector) — pure, no exec pins

### Knot Data Flow Chain (Phase 54 scope, shown for context)
```
FunctionEntry "Left / Right" (double)
  → Knot_2 → Knot_1 → CallFunction_7445 "ScaleValue" (float, implicit conversion)
FunctionEntry "Forward / Backward" (double)
  → Knot_3 → Knot_4 → CallFunction_7346 "ScaleValue" (float)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No FunctionEntry support | FunctionEntry in START_EVENT_TYPES, basic tracing | Phase 52 | Function graphs now produce execution flows |
| Generic node info in flow | Function-specific info (function_name, params) | Phase 49/52 | CallFunction nodes include structured params |
| No Knot handling in flow | Knots naturally excluded (no exec pins) | Current | No change needed for execution flow |

**Deprecated/outdated:**
- None — the existing flow_builder.py code is current and functional.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Knot nodes never have exec pins in any UE version | Pitfall 1 | If some UE version adds exec pins to Knot, traversal would need explicit skip |
| A2 | `b_defaults_to_pure` is the only purity indicator available from binary serialization | Pitfall 2 | If UE stores additional purity flags, detection may be incomplete |
| A3 | The Move function reference file is representative of typical function graph structure | Code Examples | Atypical graphs (multiple branches, loops) may need additional handling |

## Open Questions

1. **CONTEXT.md D-03 vs DISCUSSION LOG conflict on Pure functions**
   - What we know: D-03 says "skip pure functions", DISCUSSION LOG says "mark with pure=true"
   - What's unclear: Which should the planner follow?
   - Recommendation: Follow the DISCUSSION LOG (user's final decision after deliberation). Pure functions should be recorded with `"pure": true` flag.

2. **Multiple exec outputs from a single node (branching)**
   - What we know: `_find_next_exec_node()` returns the FIRST exec-connected node it finds (linear traversal)
   - What's unclear: What happens when a node has multiple exec output pins connected to different targets (e.g., a non-control-flow node with a secondary exec output)?
   - Recommendation: For Phase 53, keep linear traversal. Branching is handled by CONTROL_FLOW_NODES (IfThenElse, Switch), which already terminate the flow. This is correct behavior — the planner should document that each branch becomes a separate execution flow in real UE blueprints, but our current linear approach captures the primary path.

3. **Test asset availability**
   - What we know: No `.uasset` files exist in the test directory. Tests use synthetic fixtures.
   - What's unclear: Whether real BP_FirstPersonCharacter.uasset is available for integration testing.
   - Recommendation: Continue using synthetic fixtures (pytest fixtures with manually constructed UEdGraph/UEdGraphNode/UEdGraphPin objects). This is the established pattern in `test_output_formatting.py`.

## Environment Availability

No external dependencies — pure Python code changes.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | None (pytest auto-discovery) |
| Quick run command | `python -m pytest tests/test_output_formatting.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUNC-01 | FunctionEntry as execution flow start | unit | `pytest tests/test_output_formatting.py -x -k "function_entry"` | Wave 0 — needs creation |
| FUNC-02 | FunctionEntry → CallFunction chain | unit | `pytest tests/test_output_formatting.py -x -k "function_flow"` | Wave 0 — needs creation |
| D-04 | Knot nodes not in execution flow | unit | `pytest tests/test_output_formatting.py -x -k "knot"` | Wave 0 — needs creation |
| DISC-01 | Pure functions marked in flow | unit | `pytest tests/test_output_formatting.py -x -k "pure"` | Wave 0 — needs creation |

### Wave 0 Gaps
- [ ] `tests/test_output_formatting.py` — needs `sample_function_graph_with_execution_flow` fixture
- [ ] `tests/test_output_formatting.py` — needs `test_build_execution_flows_function_entry` test
- [ ] `tests/test_output_formatting.py` — needs `test_build_execution_flows_pure_function_marking` test
- [ ] `tests/test_output_formatting.py` — needs `test_get_start_event_name_function_entry_prefix` test

## Security Domain

N/A — this phase has no external dependencies, no network I/O, no user input handling. Pure graph traversal on deserialized data.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `src/uasset_read/graph/flow_builder.py` — full file read
- Codebase inspection: `src/uasset_read/constants.py` — full file read
- Codebase inspection: `src/uasset_read/serializers/graph.py` — L580-744 read
- Codebase inspection: `src/uasset_read/models/node_types.py` — full file read
- Codebase inspection: `src/uasset_read/formatters/json_formatter.py` — `_extract_call_function_parameters` read
- Context file: `.planning/phases/53-function-execution-flow/53-CONTEXT.md`
- Discussion log: `.planning/phases/53-function-execution-flow/53-DISCUSSION-LOG.md`

### Secondary (MEDIUM confidence)
- Reference file: `reference/蓝图节点文本参考.md` L228-341 — Move function graph structure
- Phase 52 plan: `.planning/phases/52-struct-offset-alignment/52-01-PLAN.md` — FunctionEntry implementation details

### Tertiary (LOW confidence)
- UE C++ source patterns for FK2Node_CallFunction::Serialize() — not verified against actual UE source

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all internal modules, verified via code inspection
- Architecture: HIGH — execution flow patterns traced through actual code
- Pitfalls: MEDIUM — based on code analysis + inference, not yet tested against real blueprints
- Pure function detection: MEDIUM — `b_defaults_to_pure` flag confirmed in code, but actual UE behavior not verified

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (30 days — stable internal codebase)
