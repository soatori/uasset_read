---
phase: 52
phase-slug: function-graph-node-parsing
date: "2026-05-17"
---

# Phase 52: 函数图节点解析 - Validation Strategy

## Validation Architecture

| Dimension | Validation Approach | Automated Command |
|-----------|-------------------|-------------------|
| 1. Data Model | K2NodeFunctionEntry dataclass exists, imports correctly | `python -c "from uasset_read import K2NodeFunctionEntry; print('OK')"` |
| 2. Serialization | read_k2node_functionentry parses and returns function_reference | `python -c "from uasset_read.serializers.graph import read_k2node_functionentry; print('OK')"` |
| 3. Factory Dispatch | create_node_from_archive dispatches K2Node_FunctionEntry | Parse BP_FirstPersonCharacter and check FunctionEntry nodes have non-None node_data |
| 4. Constants | START_EVENT_TYPES contains K2Node_FunctionEntry | `python -c "from uasset_read import START_EVENT_TYPES; assert 'K2Node_FunctionEntry' in START_EVENT_TYPES; print('OK')"` |
| 5. Execution Flow | build_execution_flows traces from FunctionEntry | Parse BP_FirstPersonCharacter, verify Move/Aim graphs have execution flows starting with function name |
| 6. Graph Classification | is_function_graph distinguishes EventGraph vs Function Graph | `python -c "from uasset_read.graph.flow_builder import is_function_graph; ..."` against parsed graphs |
| 7. Backward Compatibility | EventGraph output unchanged | Compare EventGraph JSON output before/after changes (diff or hash comparison) |
| 8. Integration | Full parse pipeline runs without errors | `uasset-read BP_FirstPersonCharacter.uasset --graph` exits 0 |

## Test Commands by Task

### Plan 01 Tasks

| Task | Validation Command |
|------|-------------------|
| Task 1 (dataclass) | `python -c "from uasset_read.models import K2NodeFunctionEntry; n = K2NodeFunctionEntry(); assert n.function_reference is None; print('OK')"` |
| Task 2 (serializer) | `python -c "from uasset_read.serializers.graph import read_k2node_functionentry, create_node_from_archive; print('OK')"` |
| Task 3 (exports) | `python -c "from uasset_read import read_k2node_functionentry; print('OK')"` |

### Plan 02 Tasks

| Task | Validation Command |
|------|-------------------|
| Task 1 (constants) | `python -c "from uasset_read import START_EVENT_TYPES; assert len(START_EVENT_TYPES) == 5; print('OK')"` |
| Task 2 (flow builder) | `python -c "from uasset_read.graph.flow_builder import is_function_graph; print('OK')"` |
| Task 3 (backward compat) | `pytest tests/test_output_formatting.py::test_start_event_types_contains_four_types -v` (update assertion to ==5) |

## End-to-End Validation

```bash
# Full parse of BP_FirstPersonCharacter
python -c "
from uasset_read import parse_uasset
r = parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Blueprints/BP_FirstPersonCharacter.uasset', graph=True)
graphs = {g.graph_name: g for g in r.graphs}

# FUNC-02: FunctionEntry nodes parsed
for name, g in graphs.items():
    for n in g.nodes:
        if n.class_name == 'K2Node_FunctionEntry':
            assert n.node_data is not None, f'{name}: FunctionEntry node_data is None'
            if isinstance(n.node_data, dict):
                fr = n.node_data.get('function_reference')
            else:
                fr = getattr(n.node_data, 'function_reference', None)
            assert fr is not None, f'{name}: FunctionEntry missing function_reference'
            print(f'{name}: FunctionEntry -> {fr}')

# FUNC-01: is_function_graph classification
from uasset_read.graph.flow_builder import is_function_graph
assert is_function_graph(graphs['Move']) == True
assert is_function_graph(graphs['Aim']) == True
assert is_function_graph(graphs['EventGraph']) == False
print('All validations passed')
"
```

## Regression Guard

| Check | Command | Expected |
|-------|---------|----------|
| Existing tests | `pytest tests/ -v --ignore=tests/test_linker.py` | No new failures beyond pre-existing 26 |
| EventGraph output | `uasset-read ... --graph | jq '.graphs[0]'` | Same structure as pre-Phase-52 |
