---
title: Testing Guide
section: testing
---

# Testing Guide

## Test Layers

```
tests/
├── Unit tests (no external dependencies, run on every CI)
├── Integration tests (@pytest.mark.integration, require real asset files)
│   ├── test_real_asset_coverage.py    — 20+ assets / 10+ types
│   ├── test_engine_content.py         — Engine built-in assets
│   ├── test_known_failures.py         — Known failure regression
│   ├── test_formatter_outputs.py      — Multiple assets × multiple formatters
│   └── test_asset_type_depth.py       — Multi-type deep field validation
└── fixtures/                          — Known failure records
```

## Running Tests

```python
python -m pytest tests/ -v                                    # Unit tests
UE_SAMPLE_ROOT=/path python -m pytest tests/ -v -m integration # Integration tests
python -m pytest tests/ -v --cov=uasset_read                   # Coverage report
```

## Coverage Requirements

- Core parsing modules coverage **≥ 90%**
- New code must not decrease overall coverage
- New features must include at least one unit test
- Parser changes require supplementary integration tests

## UE 5.8 MCP Real-time Ground Truth Comparison

UE 5.8 now ships with an official Experimental Unreal MCP server. For changes claiming "UE fidelity," testing comparisons should add a layer of Editor real-time ground truth collection on top of existing offline tests, rather than only comparing against static C++ references or just running `pytest`.

### Scope

Changes that **must** collect MCP ground truth:

- Blueprint variables, functions, graphs, nodes, pins, and connection relationships.
- `blueprint.components`, component hierarchy, relative Transform, material/mesh references.
- Enhanced Input / Input Action / Input Mapping Context output.
- SoftObjectPath, dependency graph, asset class names, load status, compile status.
- Fixes claiming to address missing outputs, incorrect names, empty fields, or inconsistencies with Editor-visible data in real samples.

Changes that **may skip** MCP ground truth collection:

- Pure binary reader boundary checks, error messages, internal utility functions.
- Low-level container parsing with no Editor-visible state, e.g., Pak/IoStore header validation.
- Changes affecting only output formatting and already covered by existing fixtures.

### Environment Baseline

Local UE 5.8 installation baseline:

- Engine: `D:\Program Files\Epic Games\Engine\UE_5.8`
- MCP server plugin: `Engine\Plugins\Experimental\ModelContextProtocol`
- MCP client/toolset plugin: `Engine\Plugins\Experimental\Toolsets\MCPClientToolset`
- Toolset aggregation plugin: `Engine\Plugins\Experimental\Toolsets\AllToolsets`

Official server default configuration:

- URL: `http://127.0.0.1:8000/mcp`
- URL path: `/mcp`
- Port: `8000`
- `tools/list` defaults to exposing only `list_toolsets`, `describe_toolset`, `call_tool`
- Tool calls run on the game thread; only HTTP / SSE supported, no stdio or WebSocket
- Should only bind to loopback; do not expose to non-local networks

### Collection Workflow

1. Enable `ModelContextProtocol` in the test project. When existing toolsets are needed, also enable `AllToolsets` and restart the Editor.
2. Start the server: execute `ModelContextProtocol.StartServer` in the Editor console, or launch with `-ModelContextProtocolStartServer`.
3. Connect to `http://127.0.0.1:8000/mcp`, save the `tools/list` response first.
4. Call `list_toolsets`, save the runtime-available toolset names. Do not assume all local plugins are registered.
5. Call `describe_toolset` for the target toolset, save the schema.
6. Use read-only tools to collect Editor real-time data for the target asset. If the existing toolsets cannot cover all fields, add a project-specific read-only `UToolsetDefinition` or Python Toolset instead of using generic scripts that can modify assets.
7. Run `python run.py <asset> --json` and necessary `--markdown` / `--cpp-skeleton`.
8. Compare MCP ground truth with parser output, and categorize any discrepancies.

### Comparison Field Guidelines

MCP ground truth must cover at least the following fields before it can serve as acceptance evidence for real samples:

| Category | MCP Ground Truth Fields | Parser Output Fields |
|------|------------------------|---------------------|
| Asset Identity | package path, asset name, asset class, generated class | `summary.package_name`, `exports[].object_name`, `exports[].class_name` |
| Blueprint | variables, functions, graphs, compile/load status | `blueprint.variables`, `blueprint.functions`, `graphs`, `status` |
| Graph Structure | graph name/guid, node title/class/guid, pin name/type/guid, links | `graphs[].nodes[]`, `pins[]`, `linked_to_raw` |
| Components | SCS/component name, class, parent, relative transform, key properties | `blueprint.components[]`, `transforms`, `properties` |
| Input | Input Action, trigger event, mapping context, bound function | Markdown Input Action table, `blueprint.functions`, related properties |
| References | soft object paths, materials, meshes, dependency package paths | `soft_object_path_list`, `imports`, `depends_map` |

### Pass/Fail Criteria

- `P0`: MCP-visible and parser output is missing key objects, component Transforms are all empty, graph/pin connections are missing, Input Action bindings are missing — must be fixed or explicitly marked as unsupported.
- `P1`: Names, enum prefixes, default values, reference paths inconsistent with Editor, but structure is still usable — should file an issue or add tests.
- `P2`: Sorting, display fields, summary hierarchy inconsistent with Editor — acceptable but must be documented.

When MCP is unavailable, related tests must `skip` or only produce a "not collected" report; do not misinterpret a non-running Editor as a parser pass. MCP collection results also cannot directly replace unit tests; after fixes, minimal fixtures or real-sample integration tests must still be added.

### Evidence Retention

Each real sample acceptance should retain at minimum:

- UE version, plugin enable list, MCP endpoint, startup method.
- `tools/list`, `list_toolsets`, target `describe_toolset` responses.
- Target asset path and Editor collection JSON.
- `run.py` output JSON/Markdown.
- Discrepancy table, clearly identifying one of four causes: `editor-only stripped`, `cooked asset`, `unsupported parser field`, `parser defect`.
