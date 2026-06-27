---
title: Graph Analysis
section: graph
---

# Graph Analysis

> **Module path**: `graph/`
> **Responsibility**: Extract and analyze blueprint execution flow, data flow, and connection relationships.

## Module Structure

| File | Responsibility |
|------|----------------|
| `__init__.py` | Module entry point, exports all public APIs |
| `parser.py` | Graph extraction entry — discovers EdGraph/UberEdGraph from ExportMap |
| `flow_builder.py` | Execution flow, data flow, and connection mapping construction (core logic) |
| `chain_builder.py` | Execution flow chain representation (N1->N2->N3 format) |
| `macro_expander.py` | Macro instance expansion handling |

## Core API

### extract_blueprint_graphs

<!-- data-api="extract_blueprint_graphs" -->
```python
extract_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional[PackageLinker] = None,
) -> List[UEdGraph]
```

Extracts all blueprint graphs (EdGraph/UberEdGraph) from the ExportMap. Iterates over the export table and calls `read_ue_graph` for each graph to fully parse the Graph->Node->Pin three-layer structure.

**Safety check**: `PKG_Cooked` check — graph data has been stripped from cooked assets, returns an empty list early.

### build_execution_flow_entries

<!-- data-api="build_execution_flow_entries" -->
```python
build_execution_flow_entries(graph: UEdGraph) -> List[Dict]
```

Starting from `START_EVENT_TYPES` nodes (K2Node_Event, K2Node_EnhancedInputAction, K2Node_VariableSet, K2Node_CustomEvent, K2Node_FunctionEntry), traces execution flow along exec pin connections.

Returns each entry containing:
- `start_event`: name of the starting event
- `nodes`: list of execution flow nodes (including parameter extraction, pure function annotations, and control flow termination markers)

### build_data_flows

<!-- data-api="build_data_flows" -->
```python
build_data_flows(graph: UEdGraph, mode: str = "name") -> List[Dict]
```

Extracts data pass-through relationships from non-exec pins and constructs a `data_flows` array. Each entry contains `source` and `target` node + pin references.

Supports synthetic data flow supplementation (for misplaced missing function graph parameter edges in the FirstPerson template).

### build_connections_map

<!-- data-api="build_connections_map" -->
```python
build_connections_map(graph: UEdGraph) -> Tuple[List[Dict], List[str]]
```

Converts `linked_to_raw` (PinId GUID hex) to user-friendly node reference format. Returns a connections list and warning messages.

Uses the normalized edge iterator `_iter_normalized_edges` to uniformly handle output->input direction, covering cases where LinkedTo may appear on both Input and Output sides in UE text exports.

### build_execution_chains

<!-- data-api="build_execution_chains" -->
```python
build_execution_chains(
    graph: UEdGraph,
    execution_flows: Optional[List[Dict]] = None,
) -> List[Dict]
```

Converts pair-by-pair execution flows to chained string format (Phase 71):
- Linear flow: `["N1->N2->N3"]`
- Branching flow: `["N1->N2", "N1->N3"]`
- Cycle detection: chains may be incomplete when `has_cycle=True`

## Execution Flow Tracing Process

```
1. Find START_EVENT_TYPES nodes (K2Node_Event, etc.)
2. For each start_node -> _trace_execution_from_event()
   |--- Iterate: output exec pin -> linked input pin -> next node
   |--- CallFunction: extract parameters + trace data sources
   |--- CONTROL_FLOW_NODES: mark branch type (Branch/Sequence/Switch)
   |--- Pure nodes: mark data_providers (forward trace output targets)
   └── Cycle detection: visited GUID set
3. Return list of execution flow entries
```

### Enhanced Input Action Tracing

`K2Node_EnhancedInputAction` has multiple trigger times (Started/Triggered/Completed), each traced independently from its exec output pin using `_trace_execution_from_pin`.

### Knot Penetration

When encountering `K2Node_Knot` nodes during data flow tracing, `_resolve_knot_chain` recursively penetrates until a non-Knot terminal node is reached (max depth 20).

### Data Source Reverse Tracing

`_trace_data_source` starts from a CallFunction input pin, penetrates the Knot chain, and finds the data source:
- `function_parameter` — FunctionEntry parameter pin
- `pure_function` — pure function output
- `self_reference` — self/Target reference
- `default_value` — pin default value
- `boundary` — data flow boundary node

## Key Design Decisions

- **PKG_Cooked check**: Graph data stripped from cooked assets, returns empty early
- **Chain format**: pair format -> chain string "N1->N2->N3", skips Knot and nodes without GUIDs
- **Cycle detection**: DFS three-color marking (WHITE/GRAY/BLACK)
- **Normalized edge iteration**: Unified output->input direction, covers assets that record connections on input pins
- **Synthetic edge supplementation**: Adds semantic data edges for parameter pins missing due to misalignment (Move/Aim functions)
- **String sanitization**: `_sanitize_string` removes null and control characters to ensure JSON safety
- **Circular reference protection**: `_sanitize_recursive` uses a visited set to prevent infinite recursion

## Graph Formatting

### format_graphs_json

<!-- data-api="format_graphs_json" -->
```python
format_graphs_json(graphs: List[UEdGraph]) -> List[Dict]
```

Fully formats blueprint graph data as JSON output. Includes node DTOs (with Pin connection references), connections, execution_chains, and data_flows.

### build_function_graphs

<!-- data-api="build_function_graphs" -->
```python
build_function_graphs(
    graphs: List[UEdGraph],
    blueprint_functions: Optional[List] = None,
) -> List[Dict]
```

Constructs the top-level `function_graphs` array. Each FunctionEntry node corresponds to one entry, containing a signature (extracted from blueprint_functions or Pin fallback), with embedded execution flow and data flow annotations.

## Helper Functions

| Function | Description |
|----------|-------------|
| `is_boundary_node` | Determines if a node is a data flow boundary node (DATA_BOUNDARY_NODES + self/Target) |
| `_derive_node_name` | Derives a user-friendly node name from a node (`class_name_idx` format) |
| `format_pin_ref` | Formats a Pin reference (name or guid mode) |
| `_get_start_event_name` | Gets the event name of a start node (supports 5 start node types) |
| `_find_next_exec_node` | Finds the next node connected to an exec output pin |
| `_iter_normalized_edges` | Normalized edge iterator (unified output->input direction) |
| `_resolve_knot_chain` | Recursively penetrates a Knot chain to find the terminal node |
| `_trace_data_source` | Reverse traces the data source of a parameter |

## Related Sections

- [[Blueprint]] - Blueprint Parsing
- [[Kismet]] - Kismet Decompilation
- [[Linker]] - Object Linker
