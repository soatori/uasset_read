# Blueprint v2 Deep Decode Implementation Plan

status: historical

> **状态：已完成（2026-09-05），保留为阶段记录。** Phase 4.5 已落地：图/node/pin 解码、declaration（parent_class/interfaces/functions）、SCS components、NewVariables names 均在 v2 `BlueprintFamilyHandler` 的 decode 分支；入口 `v2/blueprint_graph.py`，验收 `tests/test_blueprint_graph.py` 与 `tests/test_blueprint_decode.py`（StackOBot / BP_CombatCharacter / ABP_RifleAnimLayers / ALS_AnimBP 四个 tracked fixture）。**未迁**：VarType 类型解码、Kismet 反编译、C++ skeleton、parent-asset 解析——按 `docs/designs/2026-08-31-v1-retirement-plan.md` 归 deferred，不属本计划遗留。另：本计划前提中的 v1 文件（`graph/`、`semantic/`、`pipeline/`）与 v1 管线已在 Phase 6（#621）删除，`serializers/graph*.py` 作为 v2 reader 层复用保留。下方步骤复选框**未回填，不作为现状依据**；现状以 `src/` + `tests/` 为准。依 `docs/designs/2026-08-31-doc-status-marking-spec.md`，historical 文档可原地保留。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the blueprint graph/node/pin, function, component, and variable decode capability from the v1 pipeline into a v2 `BlueprintFamilyHandler` decode branch, producing `objects[].semantic` with real graph data at `depth=decode` (issue #621 Phase 4.5).

**Architecture:** The v2 reader already parses tagged properties for every export, but UE editor saves do not export graph pins as separate objects — pin data lives in the node export's serial region after the property stream. A mature, fixture-proven binary graph reader already exists (`serializers/graph.py`, `graph_node.py`, `graph_pin.py`, ~2,400 lines) and takes only `(archive, name_map, summary, import_map, export_map)` — the exact values the v2 reader holds in its decode pass. So the reader extracts graphs once per decode pass and stores JSON-safe dicts in the existing `extras` channel (`package_data[2]`), and the handler shapes them into `semantic`. Per D2 (`docs/designs/2026-08-31-semantic-handlers-boundary.md`) there is no v1-extractor bridging: graphs are a binary reader reused at the reader layer (same pattern as `_read_table_rows`), never the v1 `semantic/` extractors.

**Tech Stack:** Python 3.10+ (gate: Windows + Python 3.14.7), pytest, ruff, stdlib only.

**Spec:**

- Authoritative target: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` (issue #621 body is a copy; the file in `docs/designs/` wins)
- Boundary docs: `docs/designs/2026-08-31-semantic-handlers-boundary.md` (D2), `docs/designs/2026-08-31-v1-retirement-plan.md` (D1), `docs/designs/2026-08-31-v2-contract-stability.md` (S1), `docs/designs/2026-08-31-projection-layering.md` (G4)
- Issue tracker: #621 (umbrella), #629 (capability tier), #630 (decoded-claims rules)

## Global Constraints

- Package-first: all exports stay in `objects`; semantic data appears only under `objects[].semantic`; no new top-level format families.
- Handlers never touch the archive/source: they consume `obj.properties`, `all_objects`, and `package_data = (export_map, name_map, extras)` only.
- Binary decisions trace to UE source (`E:\Develop\lib\UnrealEngine`) or to the existing fixture-proven serializers — no byte-guessing.
- Bounded by default: every read is range-limited; every list the handler emits has a hard cap with explicit `truncated` markers; truncated output must not claim `complete`.
- Status honesty (#629): `status.semantic == "complete"` only when a decoded-tier handler produced non-truncated real output; otherwise `partial` with coverage entries and diagnostics.
- `semantic` is an **experimental** schema domain (S1): additive keys do not bump `format_version`; do not touch the envelope schema.
- Diagnostics are structured (`Diagnostic`) and coverage entries are `CoverageEntry(feature, status, detail)`; no logging configuration anywhere in library code.
- Full local gate is `python -m pytest -q` on Windows + Python 3.14, plus `python -m ruff check .`; no new skipped/xfail tests.
- All new tests run against tracked fixtures in `tests/samples/` (SHA-256-verified by the manifest tests). No `MagicMock` of UE structures; no fixtures added in this plan (the 48 tracked samples suffice).
- Do not edit v1-only files (`graph/`, `kismet/`, `semantic/`, `pipeline/`) — they are feature-frozen legacy (D2). This plan adds the first v2 consumer of the binary graph serializers under `serializers/graph*.py`: they stay unmodified and are imported from the new `v2/blueprint_graph.py` module only (reader-layer reuse, the same pattern v2 already uses for `serializers/object_resources.py`/`serializers/package_summary.py` — not v1-extractor bridging).
- All new output keys are snake_case; ids are stable object ids `export:<n>`; pin ids are the serialized 32-hex-char pin GUID string.

## Ground Truth (verified 2026-09-02 at HEAD d85041bb)

Facts the plan relies on — re-verify with one probe command in Task 1 before writing the test:

- `StackOBot_BP_Drone.uasset` (UE4.27): `export:0` class `Blueprint` name `BP_Drone` owns `export:4` `EdGraph` "EventGraph" (14 nodes in the `Nodes` property) and `export:5` `EdGraph` "UserConstructionScript" (1 node). Nodes are exports with class `K2Node_*`; their tagged properties stop before `Pins`; pins live in the serial region after the properties. `export:1` class `BlueprintGeneratedClass` owns no graphs.
- `ABP_RifleAnimLayers.uasset`: 10 exports; `export:1` class `AnimBlueprint` owns the `EventGraph` (export:3). `export:0` is the CDO (`Default__ABP_RifleAnimLayers_C`), `export:2` is the `AnimBlueprintGeneratedClass`.
- `BP_CombatCharacter.uasset`: `export:1` class `Blueprint`; `NewVariables` ArrayProperty of `BPVariableDescription` structs with 29 entries, members `VarName`/`VarGuid`/`VarType` decoded by the property parser (VarType body is 69 opaque bytes `{"kind": "binary_or_native_property", "struct_type": "EdGraphPinType"}`). `ParentClass` ObjectProperty normalized to `{"source": "import_map", "import_index": 47, "object_name": "Character", ...}`. `FunctionGraphs` ArrayProperty = export refs `[12, 9, 11]` → `export:11` "UserConstructionScript", `export:8` "Aim", `export:10` "Move" (each an `EdGraph`). `UbergraphPages` = `[10]` → `export:9`. `SimpleConstructionScript` ObjectProperty → `export:435` class `SimpleConstructionScript` with props `AllNodes`/`RootNodes`/`DefaultSceneRootNode`; SCS_Node exports (4, at export:431-434) have `ComponentTemplate` ObjectProperty export refs resolving to template exports with real names (`Life Bar_GEN_VARIABLE`, `Camera_GEN_VARIABLE`, …) and classes (`WidgetComponent`, `SpringArmComponent`, `CameraComponent`, `SceneComponent`); `ChildNodes` ArrayProperty holds child SCS_Node refs.
- `ALS_AnimBP.uasset` (UE4.27 editor-saved, 3,395 exports): `export:274` class `AnimBlueprint`, `export:281` `AnimBlueprintGeneratedClass`; 275 graph-class exports, 830 `K2Node_*` exports, 1,866 `AnimGraphNode_*` exports, zero `EdGraphPin` exports. This is the bounds/perf carrier.
- v1 reports **zero** blueprint variables for `BP_CombatCharacter` (`build_blueprint_content` -> `variables` empty) — the variable decode below is net-new v2 capability, not a v1 parity item.
- The graph binary reader works directly on v2 parse state: `extract_blueprint_graphs(archive, summary, name_map, import_map, export_map)` on the archive/state the v2 reader produced during its decode pass returns graphs with parsed nodes and pins (verified: EventGraph 14 nodes, K2Node pins include `execute` with `direction=0` (EGPD_Input), `linked_to_raw = [{"owning_node": <node name>, "pin_guid": <32-hex>}]`).
- Pin links are GUID-keyed, not object-indexed: `UEdGraphPin.pin_id` (32-hex) + `linked_to_raw[].pin_guid` + `linked_to_raw[].owning_node` (owner node's export *name*).

## File Map

| File | Change |
| --- | --- |
| `docs/plans/2026-09-02-blueprint-v2-deep-decode.md` | Create (this plan; Task 0 commits it) |
| `src/uasset_read/v2/blueprint_graph.py` | Create: decode-pass graph extraction + UEdGraph → plain-dict conversion + caps |
| `src/uasset_read/v2/package/legacy.py` | Modify: decode-depth extras step for blueprint-family packages |
| `src/uasset_read/v2/handlers.py` | Modify: replace `BlueprintFamilyHandler` decode branch (lines ~927-995); extend with declaration/components/variables |
| `tests/test_blueprint_decode.py` | Create: per-fixture decode contract tests (new file keeps the matrix file untouched) |
| `tests/test_samples.py` | Modify: decode-branch block (lines ~283-299) re-targeted to graph-owning exports |
| `docs/designs/2026-08-31-semantic-handlers-boundary.md` | Modify: D2 §3 blueprint row status (migration evidence) |
| `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` | Modify: Phase 4.5 status line (only after tests green) |
| `README.md` | Modify: blueprint decode claim under v2 capabilities (only after tests green) |

## Output Contract (decode depth, graph-owning export only)

The Blueprint/AnimBlueprint **asset export** (the export whose outer chain owns the graphs — `export:0`/`export:1` style, not the GeneratedClass export) receives at `depth=decode`. Illustrative example assembled across the tracked fixtures (shape is contract; per-fixture values are pinned by the tests in Tasks 1-6):

```json
{
  "kind": "blueprint",
  "blueprint_type": "Blueprint",
  "name": "BP_Drone",
  "declaration": {
    "parent_class": "Character",
    "interfaces": [],
    "functions": [
      {"id": "export:8", "name": "Aim"},
      {"id": "export:10", "name": "Move"}
    ]
  },
  "graphs": [
    {
      "id": "export:4",
      "name": "EventGraph",
      "graph_class": "EdGraph",
      "kind": "event_graph",
      "nodes": [
        {
          "id": "export:19",
          "type": "K2Node_Event",
          "name": "K2Node_Event_1",
          "position": {"x": -160, "y": 0},
          "pins": [
            {
              "id": "c48c025921cb4a429e1ff0b9b8aef7d7",
              "name": "execute",
              "direction": "input",
              "category": "exec",
              "linked": [{"to_node": "export:11", "to_pin": "e5eeae41f510..."}]
            }
          ]
        }
      ],
      "node_count": 14,
      "pin_count": 84,
      "edge_count": 12,
      "truncated": {"nodes": false, "pins": false}
    }
  ],
  "variables": [
    {"name": "Max HP", "guid": "940d4b9599a18e4a8d95148e32065299", "type": "opaque"}
  ],
  "components": [
    {"id": "export:431", "name": "DefaultSceneRoot_GEN_VARIABLE", "type": "SceneComponent", "parent": null}
  ]
}
```

Rules:

- `graphs[].kind` derives deterministically: name `EventGraph` → `event_graph`; name `UserConstructionScript` → `construction_script`; export id listed in `declaration.functions[].id` → `function`; otherwise `unknown`.
- `direction`: `EGPD_Input == 0` → `"input"`, `EGPD_Output == 1` → `"output"`, else `"unknown"` (UE enum `EEdGraphPinDirection` in `Engine/Source/Runtime/Engine/Public/EdGraph/EdGraphTypes.h`).
- `category` is the decoded `FEdGraphPinType.pin_category` string (empty string is emitted as `""` when unset).
- A pin whose `linked_to_raw[].pin_guid` does not resolve to any parsed pin in the package emits no `linked` entry and adds one aggregated diagnostic `BLUEPRINT_EXTERNAL_PIN_LINK` (warning, recoverable, stage `semantic.blueprint`).
- Every list is capped; when a cap engages, the graph/semantic carries `truncated` flags and coverage entries with status `truncated`; `capability()` then returns `"summary"`, keeping `status.semantic == "partial"`.
- The `BlueprintGeneratedClass`/`AnimBlueprintGeneratedClass` export at decode depth keeps the shallow summary (no owned graphs) — its status stays `partial` with coverage `blueprint.graph: missing` (see Task 2 rationale).

## Task 0: Commit the plan

- [ ] **Step 1:** Commit this document so history carries the plan.

```bash
git add docs/plans/2026-09-02-blueprint-v2-deep-decode.md
git commit -m "docs: blueprint v2 deep decode plan (#621 Phase 4.5)"
```

---

## Task 1: `v2/blueprint_graph.py` — graph extraction and conversion module

**Files:**

- Create: `src/uasset_read/v2/blueprint_graph.py`
- Test: `tests/test_blueprint_graph.py`

**Interfaces:**

- Consumes: `LegacyPackageReader` decode state (Task 2 wires it); unit tests drive it directly with the fixture-opening helper below.
- Produces:
  - `read_blueprint_graphs(archive, summary, name_map, import_map, export_map, *, max_graphs: int = 512) -> list[dict]` — parses every graph-class export and returns JSON-safe graph dicts (shape below). `max_graphs` caps the number of graphs processed; on cap engagement the returned `package_truncated` list entry is appended (see shape).
  - `graph_dicts_from_u_ed_graphs(graphs: list[UEdGraph], graph_exports: list[tuple[int, ObjectExport]]) -> list[dict]` — pure conversion, separately testable.
  - `resolve_pin_links(graphs: list[dict], package_graph: dict) -> None` — resolves `linked` arrays in place from the package-wide pin-guid index.
  - Module constants: `MAX_GRAPHS_PER_PACKAGE = 512`, `MAX_NODES_PER_GRAPH_OUTPUT = 256`, `MAX_PINS_PER_NODE_OUTPUT = 64`.
- Depends on nothing else in v2 (Task 2 consumes the produced dicts).

- [ ] **Step 1: Verify ground truth with one probe (do not commit it; keep in `temp/`)**

```bash
PYTHONPATH=src python temp/probe_graphs.py
```

`temp/probe_graphs.py`:

```python
"""Re-verify the plan's ground-truth facts on the current tree (issue #621 Phase 4.5)."""
import uasset_read.v2.package.legacy as L
from uasset_read.v2.source import FileSource

cap: dict = {}
_orig = L._make_package_archive
def spy(source, tolerant=False):
    a = _orig(source, tolerant); cap["archive"] = a; return a
L._make_package_archive = spy
_ops = L.read_package_summary
def spys(*a, **k):
    s = _ops(*a, **k); cap["summary"] = s; return s
L.read_package_summary = spys
_ri = L.read_import_map
def spyi(*a, **k):
    m = _ri(*a, **k); cap["import_map"] = m; return m
L.read_import_map = spyi

doc = L.LegacyPackageReader(FileSource("tests/samples/StackOBot_BP_Drone.uasset")).read(depth="decode")
from uasset_read.serializers.object_resources import read_export_map
em = read_export_map(cap["archive"], cap["summary"])
from uasset_read.serializers.package_summary import read_name_table
nm = read_name_table(cap["archive"], cap["summary"])
from uasset_read.graph import extract_blueprint_graphs
graphs = extract_blueprint_graphs(cap["archive"], cap["summary"], nm, cap["import_map"], em)
print("graphs:", [(g.graph_name, len(g.nodes)) for g in graphs])
print("eventgraph nodes:", len(graphs[0].nodes), "first node pins:", [(p.pin_name, p.direction, str(p.linked_to_raw)[:120]) for p in graphs[0].nodes[0].pins])
```

Expected: `graphs: [('EventGraph', 14), ('UserConstructionScript', 1)]` and the first node's pins print with `execute`/`then` and GUID-keyed `linked_to_raw`. If any fact differs, stop and report before writing code.

- [ ] **Step 2: Write the failing test**

`tests/test_blueprint_graph.py`:

```python
"""v2 blueprint graph extraction and conversion (issue #621 Phase 4.5).

Real-fixture tests: the graph binary readers are the shared serializers/graph*
machinery already proven on these samples by the v1 pipeline; this suite pins
the v2 conversion layer on top of it.
"""

import pytest

from uasset_read.v2.source import FileSource

SAMPLES = __import__("pathlib").Path(__file__).parent / "samples"


def _graphs_for(sample: str) -> list[dict]:
    """Open a fixture the way v2's decode pass does and return plain graph dicts."""
    from uasset_read.serializers.object_resources import read_export_map
    from uasset_read.serializers.package_summary import read_name_table, read_package_summary
    from uasset_read.v2.blueprint_graph import read_blueprint_graphs
    from uasset_read.v2.package.legacy import _make_package_archive

    src = FileSource(SAMPLES / sample)
    try:
        archive = _make_package_archive(src, tolerant=True)
        summary = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        import_map = None
        # import_map is read from archive position after name table
        # (mirror legacy.py read order); reuse the v1 serializer:
        from uasset_read.serializers.object_resources import read_import_map

        import_map = read_import_map(archive, summary)
        export_map = read_export_map(archive, summary)
        return read_blueprint_graphs(archive, summary, name_map, import_map, export_map)
    finally:
        src.close()


def test_stackobot_graphs_convert_with_pins_and_links():
    graphs = _graphs_for("StackOBot_BP_Drone.uasset")
    by_name = {g["name"]: g for g in graphs}
    assert set(by_name) == {"EventGraph", "UserConstructionScript"}
    ev = by_name["EventGraph"]
    assert ev["id"] == "export:4"
    assert ev["node_count"] == 14 == len(ev["nodes"])
    assert all(n["id"].startswith("export:") for n in ev["nodes"])
    # Pins must be decoded (this is what the v1 property stream alone cannot give).
    all_pins = [p for n in ev["nodes"] for p in n["pins"]]
    assert all_pins, "no pins decoded"
    assert all(p["id"] for p in all_pins)
    names = {p["name"] for p in all_pins}
    assert {"execute", "then"} <= names
    # Linked pins resolve to node ids inside the same package graph index.
    node_ids = {n["id"] for n in ev["nodes"]}
    for n in ev["nodes"]:
        for p in n["pins"]:
            for link in p["linked"]:
                assert link["to_node"] in node_ids, f"dangling link {link}"
    assert ev["pin_count"] == len(all_pins)
    assert ev["truncated"] == {"nodes": False, "pins": False}
    ucs = by_name["UserConstructionScript"]
    assert ucs["node_count"] == 1 == len(ucs["nodes"])
    assert ucs["truncated"]["nodes"] is False
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python -m pytest tests/test_blueprint_graph.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'uasset_read.v2.blueprint_graph'`.

- [ ] **Step 4: Implement `read_blueprint_graphs`**

`src/uasset_read/v2/blueprint_graph.py`:

```python
"""Blueprint graph decode-pass support (issue #621 Phase 4.5).

The v2 handler layer never touches the archive, but editor-saved graph pins
are not exports — they are serialized inside each node export's serial region
after the tagged property stream. The fixture-proven binary readers in
``serializers/graph*.py`` are v1 modules this plan reuses unchanged (first v2
consumer, reader-layer reuse like serializers/object_resources.py — not v1
extractor bridging per D2). This module is the v2 decode-pass seam: it runs
those readers once per package at depth="decode" and converts the result into
JSON-safe plain dicts that travel through the ``extras`` channel
(``package_data[2]``) to the handlers.

UE source: UEdGraph::Serialize / UEdGraphNode::Serialize /
UEdGraphPin::Serialize in Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph*.h.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport
    from uasset_read.serializers.package_summary import PackageFileSummary

# Hard caps on converted output. Values chosen so the largest tracked package
# (ALS_AnimBP: 275 graphs, ~2,700 node exports) passes without cap engagement
# while runaway editor graphs stay bounded (canonical design: bounded by default).
MAX_GRAPHS_PER_PACKAGE = 512
MAX_NODES_PER_GRAPH_OUTPUT = 256
MAX_PINS_PER_NODE_OUTPUT = 64

# Graph-class detection is intentionally narrower than v1's
# graph/parser.py EDGRAPH_CLASS_NAMES: v1 also lists "graph-ish" non-Graph
# classes (AnimBlueprintGeneratedClass, MaterialGraphEdNode, NiagaraScript)
# whose exports are not UEdGraph containers in the Blueprint-family context —
# running read_ue_graph on them would fabricate phantom empty graphs owned by
# the wrong export. This pass only decodes exports whose resolved class ends
# in "Graph" (EdGraph, UberEdGraph, custom graph subclasses — all tracked
# fixtures use EdGraph).
def _is_graph_class(class_name: str | None) -> bool:
    if not class_name:
        return False
    return class_name.endswith("Graph")


def _pin_direction(direction: int) -> str:
    # EEdGraphPinDirection: EGPD_Input = 0, EGPD_Output = 1
    return {0: "input", 1: "output"}.get(direction, "unknown")


def read_blueprint_graphs(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list[Any],
    export_map: list[ObjectExport],
    *,
    max_graphs: int = MAX_GRAPHS_PER_PACKAGE,
) -> list[dict[str, Any]]:
    """Parse all graph exports in the package and return plain graph dicts.

    Runs the shared binary readers (serializers/graph.read_ue_graph per graph
    export) and converts the resulting UEdGraph trees. Never raises on a
    single bad graph: failures produce a dict-level ``parse_errors`` count and
    the caller's diagnostics cover it. The archive must be open on the full
    package (decode pass restores the full read range before calling).
    """
    from uasset_read.serializers.graph_node import read_ue_graph_node
    from uasset_read.serializers.graph import _validate_graph_export_offset
    from uasset_read.serializers.object_resources import get_asset_class

    graphs: list[dict[str, Any]] = []
    processed = 0
    for export_idx, export in enumerate(export_map):
        class_name = get_asset_class(export, import_map, export_map)
        if not _is_graph_class(class_name):
            continue
        if processed >= max_graphs:
            break
        processed += 1
        try:
            if not _validate_graph_export_offset(export, archive.total_size()):
                graphs.append(_error_graph(export_idx, class_name, "offset validation failed"))
                continue
            graph = read_ue_graph(
                archive,
                name_map,
                summary,
                export_map,
                import_map,
                export,
                class_name,
                export_idx + 1,
                None,  # linker is optional; single-package resolution only
            )
            graphs.append(_graph_to_dict(graph, export_idx, class_name, export))
        except Exception as exc:  # one bad graph must not kill the decode pass
            graphs.append(_error_graph(export_idx, class_name, f"{type(exc).__name__}: {exc}"))
    resolve_pin_links(graphs)
    return graphs


def _error_graph(export_idx: int, class_name: str, reason: str) -> dict[str, Any]:
    return {
        "id": f"export:{export_idx}",
        "name": "",
        "graph_class": class_name or "",
        "kind": "unknown",
        "nodes": [],
        "node_count": 0,
        "pin_count": 0,
        "edge_count": 0,
        "truncated": {"nodes": False, "pins": False},
        "parse_errors": [reason],
    }


def _graph_to_dict(graph: Any, export_idx: int, class_name: str, export: Any) -> dict[str, Any]:
    """Convert one UEdGraph tree into a JSON-safe dict (bounded).

    Node object model (models/core.py UEdGraphNode): ``_export_index`` is the
    1-based export index stamped by the shared readers; ``node_pos_x/y`` carry
    the editor position; ``pin_id`` is the 32-hex serialized pin GUID. Node
    display names come from the export entry (models/core UEdGraphNode has no
    name field); ``export.object_name`` is the serialized object name.
    """
    nodes: list[dict[str, Any]] = []
    pin_count = 0
    node_truncated = False
    pin_truncated = False
    for node in graph.nodes:
        if len(nodes) >= MAX_NODES_PER_GRAPH_OUTPUT:
            node_truncated = True
            break
        pins: list[dict[str, Any]] = []
        for pin in node.pins:
            if len(pins) >= MAX_PINS_PER_NODE_OUTPUT:
                pin_truncated = True
                break
            pins.append(
                {
                    "id": str(pin.pin_id),
                    "name": str(pin.pin_name),
                    "direction": _pin_direction(pin.direction),
                    "category": str(pin.pin_type.pin_category),
                    # links are resolved package-wide by resolve_pin_links
                    # (GUID-indexed; see Task 1 Step 5).
                    "linked": [],
                }
            )
        pin_count += len(pins)
        nodes.append(
            {
                "id": f"export:{node._export_index - 1}" if getattr(node, "_export_index", 0) else "",
                "type": str(node.class_name or ""),
                # The UEdGraphNode model has no display-name field; the export
                # entry's object_name is the serialized node name.
                "name": str(getattr(export, "object_name", "") or ""),
                "position": {
                    "x": int(node.node_pos_x or 0),
                    "y": int(node.node_pos_y or 0),
                },
                "pins": pins,
            }
        )
    # _pin_links carries the raw GUID-keyed link records for the resolver;
    # resolve_pin_links consumes and removes it before the dicts leave the
    # module (extras and semantic output never contain non-JSON keys).
    return {
        "id": f"export:{export_idx}",
        "name": str(graph.graph_name or ""),
        "graph_class": class_name,
        "kind": "unknown",  # finalized by the handler from name / FunctionGraphs
        "nodes": nodes,
        "node_count": len(nodes),
        "pin_count": pin_count,
        "edge_count": 0,  # set by resolve_pin_links
        "truncated": {"nodes": node_truncated, "pins": pin_truncated},
        "_pin_links": _collect_pin_links(graph),
    }
```

- [ ] **Step 5: Run the test; then add the conversion helpers it needs**

Run: `python -m pytest tests/test_blueprint_graph.py -v` and iterate until the test passes. Implement `_collect_pin_links(graph)` and `resolve_pin_links(graphs)` (pure functions, package-wide GUID index) as follows — the test's link assertions exercise them once `read_blueprint_graphs` calls `resolve_pin_links(graphs)` before returning:

```python
def _collect_pin_links(graph: Any) -> list[dict[str, Any]]:
    """Collect (source pin, target pin-guid) link records from one UEdGraph tree.

    ``UEdGraphPin.linked_to_raw`` entries are ``{"owning_node": <target node
    name>, "pin_guid": <target 32-hex>}`` — the *target's* GUID (verified on
    the tracked fixtures); the source is the pin owning the list. So each
    record carries the owning pin's own id (``from_pin``) plus the target
    ``pin_guid``; ``owning_node`` (a display name, not an index) is unused.
    """
    links: list[dict[str, Any]] = []
    for node in graph.nodes:
        for pin in node.pins:
            for entry in pin.linked_to_raw:
                links.append(
                    {
                        "from_node": getattr(node, "_export_index", 0),  # 1-based
                        "from_pin": str(pin.pin_id),
                        "to_pin": str(entry.get("pin_guid", "")),
                    }
                )
    return links


def resolve_pin_links(graphs: list[dict[str, Any]]) -> None:
    """Resolve every graph's GUID-keyed links to (to_node, to_pin), in place.

    Builds one package-wide index of pin_guid -> (node id, pin id), then walks
    each graph's ``_pin_links`` records. A link whose target guid is absent is
    counted in the graph's ``unresolved_links`` (cross-package or clipped pin)
    and dropped — the reader pass turns that counter into a diagnostic, never
    a silent loss. Consumes and deletes ``_pin_links``; sets ``edge_count``.
    """
    guid_index: dict[str, tuple[str, str]] = {}
    for graph in graphs:
        for node in graph["nodes"]:
            for pin in node["pins"]:
                if pin["id"]:
                    guid_index[pin["id"]] = (node["id"], pin["id"])
    for graph in graphs:
        graph["unresolved_links"] = 0
        edge_count = 0
        for rec in graph.pop("_pin_links", []):
            target = guid_index.get(rec["to_pin"])
            if target is None:
                graph["unresolved_links"] += 1
                continue
            edge_count += 1
            source_node_id = f"export:{rec['from_node'] - 1}"
            for node in graph["nodes"]:
                if node["id"] != source_node_id:
                    continue
                for pin in node["pins"]:
                    if pin["id"] == rec["from_pin"]:
                        pin["linked"].append({"to_node": target[0], "to_pin": target[1]})
        graph["edge_count"] = edge_count
```

- [ ] **Step 6: Full new-file test pass**

Run: `python -m pytest tests/test_blueprint_graph.py -v`
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add src/uasset_read/v2/blueprint_graph.py tests/test_blueprint_graph.py
git commit -m "feat: v2 blueprint graph decode-pass module (#621 Phase 4.5)"
```

---

## Task 2: Decode-pass extras wiring + handler graphs output (replaces the coarse branch)

**Files:**

- Modify: `src/uasset_read/v2/package/legacy.py` (extras step ~line 517; per-export property loop ~line 648)
- Modify: `src/uasset_read/v2/handlers.py` (BlueprintFamilyHandler decode branch lines 927-995; capability line 997)
- Modify: `tests/test_samples.py` (decode-branch block ~lines 283-299)
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**

- Consumes: Task 1's `read_blueprint_graphs`; existing extras channel `extras: dict[str, dict]` with per-object-id keys.
- Produces: extras entries `extras[<graph-owning export id>] = {"graphs": [...]}` (graphs whose outer chain resolves to that export); handler `semantic["graphs"]`; the coarse `semantic["graph"]` key is deleted.

Rationale for owner attribution: in UE editor packages, graph exports' outer is the UBlueprint/AnimBlueprint **asset** object (verified: StackOBot `export:0`, ABP `export:1`). The GeneratedClass export owns no graphs; its decode output stays the shallow summary with `partial` status and coverage `blueprint.graph: missing`. This matches the v1 era, where blueprint semantic content was attached to the primary asset export.

- [ ] **Step 1: Write the failing contract test**

`tests/test_blueprint_decode.py`:

```python
"""Blueprint v2 deep-decode contract (issue #621 Phase 4.5).

The decode branch previously attached a package-wide coarse node scan to every
Blueprint-family export. It now attaches real graphs (export-scoped, pin
decoded) to the export that owns them.
"""

from functools import lru_cache

from uasset_read.v2.api import parse_package_document

SAMPLES = __import__("pathlib").Path(__file__).parent / "samples"


@lru_cache(maxsize=None)
def _decode(sample: str, object_ids: tuple[str, ...]):
    return parse_package_document(SAMPLES / sample, depth="decode", object_ids=list(object_ids))


def test_stackobot_blueprint_asset_export_gets_real_graphs():
    dec = _decode("StackOBot_BP_Drone.uasset", ("export:0",))
    bp = next(o for o in dec.objects if o.id == "export:0")
    assert bp.status.semantic == "complete", bp.status
    graphs = {g["name"]: g for g in bp.semantic["graphs"]}
    assert set(graphs) == {"EventGraph", "UserConstructionScript"}
    ev = graphs["EventGraph"]
    assert ev["node_count"] == 14 == len(ev["nodes"])
    assert ev["pin_count"] > 0
    # graph kind derivation
    assert ev["kind"] == "event_graph"
    assert graphs["UserConstructionScript"]["kind"] == "construction_script"
    # old coarse package-wide scan key is gone
    assert "graph" not in bp.semantic
    # no spurious diagnostics
    assert not [d for d in dec.diagnostics if d.code == "BLUEPRINT_EXTERNAL_PIN_LINK"]


def test_stackobot_generated_class_export_stays_summary_partial():
    dec = _decode("StackOBot_BP_Drone.uasset", ("export:1",))
    bpgc = next(o for o in dec.objects if o.id == "export:1")
    assert bpgc.status.semantic == "partial"
    assert "graphs" not in bpgc.semantic
    assert bpgc.semantic["kind"] == "blueprint"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_blueprint_decode.py -v`
Expected: FAIL — `export:0` semantic has no `graphs` key (current code emits `graph`), and `export:0` has no graphs under current attribution.

- [ ] **Step 3: Reader wiring — decode-pass extras step in `legacy.py`**

In `LegacyPackageReader.read`, after the step-16 extras call and before step 17 (`run_handlers`), insert (gated to decode depth, non-cooked packages, and only when the parse set touches a Blueprint-family export):

```python
            # 16b. Blueprint deep-decode graph pass at depth="decode".
            # Editor saves do not export pins — they live in each node export's
            # serial region after the property stream. The shared
            # serializers/graph* readers decode them; results travel to the
            # handlers through extras under the owning export id.
            if depth == "decode" and not (summary.package_flags & PKG_Cooked):
                _attach_blueprint_graph_extras(
                    archive=archive,
                    summary=summary,
                    name_map=name_map,
                    import_map=import_map,
                    export_map=export_map,
                    objects=objects,
                    extras=extras,
                    diagnostics=diagnostics,
                    object_ids=object_ids,
                )
```

(`PKG_Cooked` is already imported from `...constants`.) Then define the module-level helper next to `_read_table_rows`:

```python
_BLUEPRINT_FAMILY_CLASSES = frozenset(
    {"Blueprint", "AnimBlueprint", "BlueprintGeneratedClass", "AnimBlueprintGeneratedClass"}
)


def _resolve_graph_owner(
    export_idx: int, export_map: list[Any], objects: list[ObjectRecord]
) -> str | None:
    """Walk a graph export's outer chain to its Blueprint-family owner.

    Graph exports' outer is the UBlueprint asset object (verified on the
    tracked fixtures: StackOBot EventGraph export:4 outer=export:0,
    ABP_RifleAnimLayers EventGraph export:3 outer=export:1). Walks the raw
    ``outer_index`` chain (FPackageIndex: positive = export index + 1,
    negative = import) at most 8 hops — a chain cannot cycle in a valid
    package. Returns None when no family export is on the chain.
    """
    by_index = {o.table_index: o for o in objects}
    idx = export_idx
    for _ in range(8):
        rec = by_index.get(idx)
        if rec is None:
            return None
        if (rec.class_name or "") in _BLUEPRINT_FAMILY_CLASSES:
            return rec.id
        if idx >= len(export_map):
            return None
        outer = export_map[idx].outer_index
        value = outer.index if outer is not None else 0
        if value > 0:  # export ref (1-based)
            idx = value - 1
        else:
            return None  # import or null outer cannot own a package graph
    return None


def _attach_blueprint_graph_extras(
    archive,
    summary,
    name_map,
    import_map,
    export_map,
    objects,
    extras,
    diagnostics,
    *,
    object_ids: Sequence[str] | None,
) -> None:
    """Parse all graphs at decode depth and route them to owning exports.

    Runs only when the caller's object selection reaches a Blueprint-family
    export (decode of e.g. a single Texture must not pay for the package's
    graphs). One bad graph never aborts the pass: the conversion module emits
    a graph dict with parse_errors instead, and this helper drops it with a
    diagnostic (the export id stays addressable).
    """
    from ...v2.blueprint_graph import read_blueprint_graphs

    family = {o.id for o in objects if (o.class_name or "") in _BLUEPRINT_FAMILY_CLASSES}
    if not family:
        return
    if object_ids is not None and not family.intersection(object_ids):
        return
    graphs = read_blueprint_graphs(archive, summary, name_map, import_map, export_map)
    owners: dict[str, list[dict]] = {}
    for graph in graphs:
        if graph.get("parse_errors"):
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="BLUEPRINT_GRAPH_PARSE_FAILED",
                    message=f"graph export {graph['id']}: {graph['parse_errors'][0]}",
                    stage="semantic.blueprint",
                    object_id=graph["id"],
                    recoverable=True,
                )
            )
            continue
        export_idx = int(graph["id"].split(":")[1])
        owner = _resolve_graph_owner(export_idx, export_map, objects)
        if owner is None:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="BLUEPRINT_GRAPH_OWNER_UNRESOLVED",
                    message=f"graph export {graph['id']} has no Blueprint-family owner",
                    stage="semantic.blueprint",
                    object_id=graph["id"],
                    recoverable=True,
                )
            )
            continue
        owners.setdefault(owner, []).append(graph)
    for owner_id, owner_graphs in owners.items():
        entry = extras.setdefault(owner_id, {})
        entry["graphs"] = owner_graphs
```

Note the walk reads only `export_map` entries' `outer_index` (raw FPackageIndex: positive = export index + 1, negative = import index) — ObjectRecord.outer_ref (`ObjectRef(table, index)`) must not be used here since it reindexes. (In the tracked fixtures the first hop is already the owner: StackOBot graph `export:4` outer → `export:0`.)

- [ ] **Step 4: Handler rewrite — replace the coarse decode branch**

Replace the body of `BlueprintFamilyHandler.enrich` decode section (lines ~927-995) and the `capability` method:

```python
    def enrich(
        self,
        obj: ObjectRecord,
        context: VersionContext,
        all_objects: list[ObjectRecord],
        package_data: Any,
    ) -> dict[str, Any] | None:
        cn = obj.class_name or ""
        result: dict[str, Any] = {
            "kind": self._kind,
            "blueprint_type": cn,
            "name": obj.name,
        }

        if context.depth == "asset":
            obj.coverage.append(
                CoverageEntry(
                    feature=f"{self._feature}.summary",
                    status="present",
                    detail="light summary at depth=asset",
                )
            )
            return result

        # depth == "decode": real graphs arrive via extras (reader-side pass).
        # Only the owning asset export carries them; GeneratedClass exports
        # keep the summary and stay "partial" (#629 tier contract).
        if context.depth == "decode":
            extras = package_data[2] if package_data else {}
            entry = extras.get(obj.id, {}) if isinstance(extras, dict) else {}
            graphs = entry.get("graphs", []) if isinstance(entry, dict) else []
            if graphs:
                self._finalize_graph_kinds(graphs, _function_graph_ids(obj.properties))
                truncated = any(
                    g["truncated"]["nodes"] or g["truncated"]["pins"] for g in graphs
                )
                result["graphs"] = graphs
                result["truncated_graphs"] = truncated
                detail = f"{len(graphs)} graphs, {sum(g['node_count'] for g in graphs)} nodes"
                if truncated:
                    detail += " (truncated)"
                obj.coverage.append(
                    CoverageEntry(
                        feature=f"{self._feature}.graph",
                        status="truncated" if truncated else "present",
                        detail=detail,
                    )
                )
            else:
                obj.coverage.append(
                    CoverageEntry(
                        feature=f"{self._feature}.graph",
                        status="missing",
                        detail="no graphs owned by this export",
                    )
                )
            return result

    @staticmethod
    def _finalize_graph_kinds(graphs: list[dict[str, Any]], fg_ids: set[str]) -> None:
        """Set per-graph kind from name / FunctionGraphs membership.

        Deterministic derivation: EventGraph/UserConstructionScript by name,
        graphs listed in FunctionGraphs -> "function", else "unknown".
        (Task 3 introduces the ``_function_graph_ids`` helper and reuses this
        method unchanged.)
        """
        for graph in graphs:
            if graph["name"] == "EventGraph":
                graph["kind"] = "event_graph"
            elif graph["name"] == "UserConstructionScript":
                graph["kind"] = "construction_script"
            elif graph["id"] in fg_ids:
                graph["kind"] = "function"
            else:
                graph["kind"] = "unknown"

    def capability(self, result: dict[str, Any]) -> str:
        # Truncated decode output must not claim "complete" (#629, bounded by
        # default); summary echoes stay summary tier.
        if result.get("graphs") and not result.get("truncated_graphs"):
            return "decoded"
        return "summary"
```

The handler never emits diagnostics (it cannot reach the document list); the aggregated `BLUEPRINT_EXTERNAL_PIN_LINK` diagnostic is emitted reader-side in Step 5.

Add the module-level helper next to the class (Task 3's declaration block reuses it unchanged):

```python
def _function_graph_ids(properties: dict[str, Any] | None) -> set[str]:
    """Export ids of the FunctionGraphs property (positive refs = export idx + 1)."""
    fg = properties.get("FunctionGraphs", {}).get("value") if properties else None
    ids: set[str] = set()
    if isinstance(fg, list):
        for ref in fg:
            if isinstance(ref, int) and ref > 0:
                ids.add(f"export:{ref - 1}")
    return ids
```

- [ ] **Step 5: Reader-side unresolved-link diagnostic**

`read_blueprint_graphs` (Task 1) calls `resolve_pin_links` before returning, which consumes `_pin_links` and leaves a per-graph `unresolved_links` int. In `_attach_blueprint_graph_extras`, AFTER the per-graph owner loop (Step 3) has dropped error graphs (`parse_errors`) and grouped the rest, aggregate the counter over the grouped graphs only, emit one diagnostic, then strip transient keys from the dicts that go into extras:

```python
    total_unresolved = sum(g.get("unresolved_links", 0) for grouped in owners.values() for g in grouped)
    if total_unresolved:
        # Diagnostic has no count field — the aggregate lives in the message
        # (same code + object scope across graphs; the design's aggregation
        # semantics are textual here).
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="BLUEPRINT_EXTERNAL_PIN_LINK",
                message=(
                    f"{total_unresolved} pin link(s) did not resolve to a parsed pin "
                    "(cross-package links are not decoded)"
                ),
                stage="semantic.blueprint",
                recoverable=True,
            )
        )
    for grouped in owners.values():
        for graph in grouped:
            graph.pop("unresolved_links", None)
```

Extras then holds only JSON-safe keys (int/str/list/dict); the handler never has to strip transient keys. Ordering matters: error-graph detection (`graph.get("parse_errors")`) in Step 3 runs before this strip, so error graphs are dropped while their `parse_errors` key is still present.

- [ ] **Step 6: Update the matrix decode-branch in `tests/test_samples.py`**

The block at ~lines 283-299 currently decodes the `AnimBlueprintGeneratedClass` export and asserts a package-wide `graph`. Replace it: decode the graph-owning **AnimBlueprint asset export** (discovered from the asset-level document, not hardcoded) and assert the deep contract there. The row's own GeneratedClass export keeps the shallow-summary assertions above the branch (`assert not {"nodes", "bytecode", "graph", "graphs"} & obj.semantic.keys()` stays).

Add this small helper next to the other `_decode_document` helpers:

```python
def _graph_owner_id(doc) -> str | None:
    """Export id of the Blueprint-family asset that owns the package's graphs.

    A graph export's outer chain resolves to the UBlueprint/UAnimBlueprint
    asset export (verified on ABP_RifleAnimLayers and ALS_AnimBP). Returns the
    first family-class export reachable from any EdGraph export's outer.
    ObjectRef(table, index) — outer_ref of an export is table="export".
    """
    family = {"Blueprint", "AnimBlueprint", "BlueprintGeneratedClass",
              "AnimBlueprintGeneratedClass"}
    by_id = {o.id: o for o in doc.objects}
    for o in doc.objects:
        if (o.class_name or "").endswith("Graph") or (o.class_name or "") == "EdGraph":
            cur = o
            for _ in range(8):
                outer = cur.outer_ref
                if outer is None or outer.table != "export":
                    break
                nxt = by_id.get(f"export:{outer.index}")
                if nxt is None:
                    break
                if (nxt.class_name or "") in family:
                    return nxt.id
                cur = nxt
    return None
```

Then replace the decode branch body:

```python
        if class_name == "AnimBlueprintGeneratedClass":
            owner = _graph_owner_id(doc)
            assert owner is not None, f"{sample}:{class_name} graph owner not found"
            dec = _decode_document(sample, (owner,))
            abp = next(o for o in dec.objects if o.id == owner)
            assert abp.semantic is not None, f"{sample}:{class_name} decode"
            assert abp.semantic["kind"] == "anim_blueprint"
            assert abp.semantic.get("graphs"), f"{sample}:{class_name} graphs missing"
            assert abp.status.semantic == "complete", f"{sample}:{class_name} decode tier"
            node_ids = {n["id"] for g in abp.semantic["graphs"] for n in g["nodes"]}
            for graph in abp.semantic["graphs"]:
                for node in graph["nodes"]:
                    for pin in node["pins"]:
                        for link in pin["linked"]:
                            assert link["to_node"] in node_ids, f"{sample} dangling link"
```

Expected owner ids (verify by running the helper once): `ABP_RifleAnimLayers.uasset` → `export:1`, `ALS_AnimBP.uasset` → `export:274`. The old assertions that hardcoded the GeneratedClass export id are gone; nothing else in the suite asserts the coarse `graph` shape — if a run reveals another consumer (grep `"graph"` in `tests/`), migrate it the same way.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/test_blueprint_decode.py tests/test_blueprint_graph.py tests/test_samples.py -q`
Expected: all pass (the old coarse decode assertions that hardcoded `export:2`/package-wide behavior are gone; nothing else in the suite asserts the coarse `graph` shape — verify with a grep for `"graph"` in `tests/` if anything else fails).

- [ ] **Step 8: Commit**

```bash
git add src/uasset_read/v2/package/legacy.py src/uasset_read/v2/handlers.py tests/test_blueprint_decode.py tests/test_samples.py
git commit -m "feat: real blueprint graph decode at v2 depth=decode (#621 Phase 4.5)"
```

---

## Task 3: Declaration — parent class, interfaces, functions

**Files:**

- Modify: `src/uasset_read/v2/handlers.py` (decode branch — add `declaration` construction)
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**

- Consumes: `obj.properties` of the graph-owning export (already parsed at decode depth), extras from Task 2.
- Produces: `semantic["declaration"] = {"parent_class": str | None, "interfaces": [str, ...], "functions": [{"id": str, "name": str}, ...]}` on the owning export only; `graphs[].kind == "function"` for graphs whose export id appears in `functions`.

- [ ] **Step 1: Write the failing tests**

```python
def test_combat_character_declaration_and_function_kinds():
    dec = _decode("BP_CombatCharacter.uasset", ("export:1",))
    bp = next(o for o in dec.objects if o.id == "export:1")
    decl = bp.semantic["declaration"]
    assert decl["parent_class"] == "Character"
    fns = {f["name"]: f["id"] for f in decl["functions"]}
    assert set(fns) == {"Aim", "Move", "UserConstructionScript"}
    by_name = {g["name"]: g for g in bp.semantic["graphs"]}
    assert by_name["Aim"]["kind"] == "function"
    assert by_name["Move"]["kind"] == "function"
    assert by_name["UserConstructionScript"]["kind"] == "construction_script"
    assert decl["interfaces"] == ["BPI_Attacker_C"]  # resolved via import table
```

`_decode` with `("export:1",)` is BP_CombatCharacter's Blueprint export per ground truth (verified 2026-09-02: `export:0` is the CDO `Default__BP_CombatCharacter_C`, `export:1` is the `Blueprint` asset export with `ParentClass` → import `Character` and `ImplementedInterfaces` → import `BPI_Attacker_C`; graphs "Aim"/"Move"/"UserConstructionScript" live at `export:8`/`export:10`/`export:11`).

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_blueprint_decode.py::test_combat_character_declaration_and_function_kinds -v`
Expected: FAIL with `KeyError: 'declaration'`.

- [ ] **Step 3: Implement declaration construction**

Reader side: `BPInterfaceDescription.Interface` is a negative FPackageIndex *inside a struct* — normalization does not resolve struct fields, and `package_data` has no import map, so `_attach_blueprint_graph_extras` resolves it while the maps are in scope. Extend the helper so that after grouping graphs it also fills the owning export's extras entry:

```python
    for owner_id, owner_graphs in owners.items():
        entry = extras.setdefault(owner_id, {})
        entry["graphs"] = owner_graphs
        # Interfaces: BPInterfaceDescription.Interface is a struct-nested
        # negative FPackageIndex (ObjectResource.h convention) that the
        # property normalizer does not resolve — resolve it here against the
        # import map. Class name for display: import.object_name.
        obj = next((o for o in objects if o.id == owner_id), None)
        if obj is not None and obj.properties:
            ifaces = obj.properties.get("ImplementedInterfaces") or obj.properties.get("Interfaces")
            raw = ifaces.get("value") if isinstance(ifaces, dict) else None
            names: list[str] = []
            if isinstance(raw, list):
                for desc in raw:
                    ref = desc.get("fields", {}).get("Interface") if isinstance(desc, dict) else None
                    if isinstance(ref, int) and ref < 0:
                        imp = import_map[-ref - 1]
                        names.append(imp.object_name)
            entry["interfaces"] = names
```

Handler side: `BlueprintFamilyHandler.enrich` decode branch calls the helpers (after `graphs` is read from extras, before `result["graphs"]` is set; `_function_graph_ids` was introduced in Task 2):

```python
            fg_ids = _function_graph_ids(obj.properties)
            self._finalize_graph_kinds(graphs, fg_ids)
            result["declaration"] = _extract_declaration(
                obj, entry, graphs, fg_ids, package_data[0] if package_data else None
            )
            result["graphs"] = graphs
```

```python
def _extract_declaration(
    obj: ObjectRecord,
    entry: dict[str, Any],
    graphs: list[dict[str, Any]],
    fg_ids: set[str],
    export_map: Any,
) -> dict[str, Any]:
    """parent_class / interfaces / functions for the owning asset export.

    ParentClass is a plain ObjectProperty — normalization already resolves
    import refs to {"source": "import_map", ..., "object_name": ...} dicts.
    The export-scoped int-ref branch (positive value -> export_map index) has
    no tracked-fixture occurrence; it stays for correctness and returns None
    when the export map cannot resolve the index. Functions are the
    FunctionGraphs export refs; the referenced graph's export name IS the
    function name (verified: BP_CombatCharacter FunctionGraphs [12, 9, 11]
    -> graphs "UserConstructionScript"/"Aim"/"Move"). Interfaces arrive
    already resolved by the reader pass (entry["interfaces"]).
    """
    props = obj.properties or {}
    parent = None
    parent_value = props.get("ParentClass")
    if isinstance(parent_value, dict):
        value = parent_value.get("value")
        if isinstance(value, dict):
            parent = value.get("object_name")
        elif isinstance(value, int) and value > 0 and export_map is not None:
            entry_obj = export_map[value - 1] if value - 1 < len(export_map) else None
            if entry_obj is not None:
                parent = getattr(entry_obj, "object_name", None)
    functions: list[dict[str, Any]] = []
    graph_by_id = {g["id"]: g for g in graphs}
    for oid in sorted(fg_ids):
        graph = graph_by_id.get(oid)
        if graph is not None and graph.get("name"):
            functions.append({"id": oid, "name": graph["name"]})
    return {
        "parent_class": parent,
        "interfaces": entry.get("interfaces", []),
        "functions": functions,
    }
```

`_finalize_graph_kinds(graphs, fg_ids)` already has the final signature from Task 2 — no rework needed; `_extract_declaration` never mutates graph kinds (the kind pass runs first).

- [ ] **Step 4: Run tests, fix, run full suite**

Run: `python -m pytest tests/test_blueprint_decode.py tests/test_samples.py -q` — all pass.

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/v2/handlers.py src/uasset_read/v2/package/legacy.py tests/test_blueprint_decode.py
git commit -m "feat: blueprint declaration (parent/interfaces/functions) at decode depth (#621 Phase 4.5)"
```

---

## Task 4: Components — SCS_Node tree with template names

**Files:**

- Modify: `src/uasset_read/v2/handlers.py`
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**

- Consumes: `all_objects` (records of SCS_Node/SimpleConstructionScript exports with parsed properties at decode), `obj.properties`.
- Produces: `semantic["components"] = [{"id": str, "name": str, "type": str, "parent": str | None}, ...]` on the owning export.

Ground truth: BP_CombatCharacter export:1 has SCS at export:435 with SCS_Node exports at export:431-434; each SCS_Node's `ComponentTemplate` ObjectProperty value (resolved dict, `object_name` `"..._GEN_VARIABLE"`-style, or int export ref) and the template's class name = the node's `ComponentClass` resolved ObjectProperty dict `object_name`; `ChildNodes` ArrayProperty holds child SCS_Node export refs (positive ints → `export:<ref-1>`). StackOBot_BP_Drone SCS_Node exports (3) include SpringArm/Camera pattern; use BP_CombatCharacter for assertions (4 nodes, deeper tree).

- [ ] **Step 1: Write the failing test**

```python
def test_combat_character_components_tree():
    # Full-package decode: SCS_Node properties are parsed only when the parse
    # set covers their exports (object_ids narrowing would skip them).
    from uasset_read.v2.api import parse_package_document

    dec = parse_package_document(SAMPLES / "BP_CombatCharacter.uasset", depth="decode")
    bp = next(o for o in dec.objects if o.id == "export:1")
    comps = {c["name"]: c for c in bp.semantic["components"]}
    assert {"Life Bar_GEN_VARIABLE", "Camera_GEN_VARIABLE"} <= set(comps)
    assert comps["Life Bar_GEN_VARIABLE"]["type"] == "WidgetComponent"
    assert comps["Camera_GEN_VARIABLE"]["type"] == "CameraComponent"
    # one of the components nests under another (ChildNodes linkage)
    parents = [c["parent"] for c in bp.semantic["components"] if c["parent"] is not None]
    assert parents, "expected at least one child component"
    ids = {c["id"] for c in bp.semantic["components"]}
    assert all(p in ids for p in parents)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_blueprint_decode.py::test_combat_character_components_tree -v`
Expected: FAIL with `KeyError: 'components'`.

- [ ] **Step 3: Implement component extraction**

Add to the handler decode branch (module-level helper, called only when `context.depth == "decode"`):

```python
_BLUEPRINT_FAMILY = frozenset(
    {"Blueprint", "AnimBlueprint", "BlueprintGeneratedClass", "AnimBlueprintGeneratedClass"}
)


def _pair_key(name: str) -> str:
    """Key joining a Blueprint asset export with its GeneratedClass export.

    GeneratedClass exports carry the "_C" suffix (BP_Drone_C vs BP_Drone);
    SCS sub-objects may be owned by either side depending on engine path, so
    component attribution compares pair keys, not exact outer ids.
    """
    return name[:-2] if name.endswith("_C") else name


def _family_root_key(
    record: ObjectRecord | None, all_objects: list[ObjectRecord]
) -> str | None:
    """Pair key of the Blueprint-family root of ``record``'s outer chain.

    SCS_Node -> SimpleConstructionScript -> Blueprint-family asset. Walks at
    most 8 hops via outer_ref (ObjectRef(table, index)); returns None for
    detached/import-outer chains.
    """
    by_id = {o.id: o for o in all_objects}
    cur = record
    for _ in range(8):
        if cur is None:
            return None
        if (cur.class_name or "") in _BLUEPRINT_FAMILY:
            return _pair_key(cur.name)
        outer = cur.outer_ref
        if outer is None or outer.table != "export":
            return None
        cur = by_id.get(f"export:{outer.index}")
    return None


def _extract_components(
    obj: ObjectRecord, all_objects: list[ObjectRecord], package_data: Any
) -> list[dict[str, Any]]:
    """SCS component tree from SCS_Node exports (UE: SimpleConstructionScript.cpp).

    Each SCS_Node export (class SCS_Node) carries ComponentClass (a resolved
    import dict: {"object_name": "WidgetComponent", ...} — verified on
    BP_CombatCharacter) and ComponentTemplate (an export ref int, positive =
    export index + 1, resolving through package_data[0] to template exports
    named like "Life Bar_GEN_VARIABLE"). ChildNodes ArrayProperty holds child
    SCS_Node export refs. Only nodes whose outer chain roots at the same
    Blueprint family as ``obj`` are attributed to it; nodes whose properties
    were not parsed are skipped — coverage reports the scope.
    """
    scope = _family_root_key(obj, all_objects)
    if scope is None:
        return []
    nodes = [
        o
        for o in all_objects
        if o.class_name == "SCS_Node"
        and o.properties
        and _family_root_key(o, all_objects) == scope
    ]
    export_map = package_data[0] if package_data else None
    out: list[dict[str, Any]] = []
    for node in nodes:
        props = node.properties or {}
        comp = props.get("ComponentTemplate", {}).get("value")
        cclass = props.get("ComponentClass", {}).get("value")
        name = ""
        if isinstance(comp, dict):
            name = comp.get("object_name") or comp.get("name") or node.name
        elif isinstance(comp, int) and comp > 0 and export_map is not None:
            target = export_map[comp - 1] if comp - 1 < len(export_map) else None
            name = getattr(target, "object_name", None) or node.name
        else:
            name = node.name
        ctype = cclass.get("object_name", "") if isinstance(cclass, dict) else ""
        parent: str | None = None
        this_idx = node.table_index
        for other in nodes:
            children = (other.properties or {}).get("ChildNodes", {}).get("value")
            if isinstance(children, list) and any(
                isinstance(c, int) and c > 0 and c - 1 == this_idx for c in children
            ):
                parent = other.id
                break
        out.append({"id": node.id, "name": name, "type": ctype, "parent": parent})
    out.sort(key=lambda c: c["id"])
    return out
```

Call it in the decode branch, emit `result["components"]`, and add coverage `f"{self._feature}.components"` (`present` when non-empty, `missing` otherwise with detail).

**Important — decode selection for this task:** SCS_Node properties are only parsed when the parse set covers their exports. The Task 3 `_decode` helper narrows to a single export id, which would leave SCS_Node exports unparsed and the components list empty. For the components test (and the ALS/Task 6 tests if they assert components) use a full-package decode instead: `parse_package_document(SAMPLES / "BP_CombatCharacter.uasset", depth="decode")` (no `object_ids` — the package has ~445 exports and stays cheap) and select the Blueprint asset record by id `export:1`. Do not add an object_ids-closure expansion to the reader in this plan; that is tracked as a follow-up when an agent tool needs it.

- [ ] **Step 4: Run tests, fix, full suite**

Run: `python -m pytest tests/test_blueprint_decode.py tests/test_samples.py -q` — all pass.

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/v2/handlers.py tests/test_blueprint_decode.py
git commit -m "feat: blueprint SCS component tree at decode depth (#621 Phase 4.5)"
```

---

## Task 5: Variables — NewVariables names and GUIDs

**Files:**

- Modify: `src/uasset_read/v2/handlers.py`
- Test: `tests/test_blueprint_decode.py`

**Interfaces:**

- Consumes: owning export `obj.properties["NewVariables"]` (array of `BPVariableDescription` structs; members `VarName`/`VarGuid` already decoded by the property parser).
- Produces: `semantic["variables"] = [{"name": str, "guid": str, "type": "opaque"}, ...]`; `type` is `"opaque"` because the `VarType` member body (FEdGraphPinType, 69 opaque bytes in these UE4.27 fixtures) is not decoded — decoding it requires a UE-source-verified layout (FEdGraphPinType has TStructOpsTypeTraits-based member serialization; follow-up, not this plan). Honest-by-construction: type claims are never made.

- [ ] **Step 1: Write the failing test**

```python
def test_combat_character_variables_names_and_guids():
    dec = _decode("BP_CombatCharacter.uasset", ("export:1",))
    bp = next(o for o in dec.objects if o.id == "export:1")
    names = [v["name"] for v in bp.semantic["variables"]]
    assert "Max HP" in names
    assert len(bp.semantic["variables"]) == 29
    for v in bp.semantic["variables"]:
        assert v["type"] == "opaque"          # no type claim without decode
        assert len(v["guid"]) == 32
        assert all(ch in "0123456789abcdef" for ch in v["guid"])
    feature_names = [c.feature for c in bp.coverage]
    assert "blueprint.variables" in feature_names


def test_manny_anim_blueprint_variables():
    # LevelDesign_ABP_Manny: AnimBlueprint asset export:18 owns NewVariables
    # (6 entries; verified 2026-09-02). export:0 is not the asset export.
    dec = _decode("LevelDesign_ABP_Manny.uasset", ("export:18",))
    abp = next(o for o in dec.objects if o.id == "export:18")
    variables = abp.semantic["variables"]
    assert len(variables) == 6
    assert all(v["name"] for v in variables)
    assert all(len(v["guid"]) == 32 for v in variables)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_blueprint_decode.py::test_combat_character_variables_names_and_guids tests/test_blueprint_decode.py::test_manny_anim_blueprint_variables -v`
Expected: FAIL with `KeyError: 'variables'`.

- [ ] **Step 3: Implement variable extraction**

Module-level helper in `handlers.py`:

```python
def _guid_hex(guid_fields: Any) -> str:
    """Serialize a decoded Guid struct fields dict (A/B/C/D int32) to 32 hex."""
    if not isinstance(guid_fields, dict):
        return ""
    return "".join(f"{int(guid_fields.get(k, 0)) & 0xFFFFFFFF:08x}" for k in ("A", "B", "C", "D"))


def _extract_variables(obj: ObjectRecord) -> list[dict[str, Any]]:
    """NewVariables (BPVariableDescription) names and GUIDs; VarType stays opaque.

    VarType bodies are serialized member-wise (FEdGraphPinType, TStructOpsTypeTraits)
    and are NOT decoded — type claims are therefore never made (#630). A
    UE-source-verified VarType decode is a tracked follow-up.
    """
    props = obj.properties or {}
    raw = props.get("NewVariables")
    if not isinstance(raw, dict) or not isinstance(raw.get("value"), list):
        return []
    out: list[dict[str, Any]] = []
    for desc in raw["value"]:
        if not isinstance(desc, dict):
            continue
        fields = desc.get("fields", {})
        if not isinstance(fields, dict):
            continue
        out.append(
            {
                "name": fields.get("VarName"),
                "guid": _guid_hex(fields.get("VarGuid", {}).get("fields"))
                if isinstance(fields.get("VarGuid"), dict)
                else "",
                "type": "opaque",
            }
        )
    return out
```

Call it in the decode branch and emit `result["variables"]` with coverage entry `f"{self._feature}.variables"`.

- [ ] **Step 4: Run tests; add the ABP variable case; full suite**

Run: `python -m pytest tests/test_blueprint_decode.py tests/test_samples.py -q` — all pass.

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/v2/handlers.py tests/test_blueprint_decode.py
git commit -m "feat: blueprint NewVariables names/guids at decode depth (#621 Phase 4.5)"
```

---

## Task 6: Bounds honesty on the large carrier (ALS_AnimBP) + matrix rows

**Files:**

- Modify: `src/uasset_read/v2/blueprint_graph.py` (caps already present — this task proves them)
- Modify: `tests/test_blueprint_decode.py`, `tests/test_samples.py`
- Test: `tests/test_blueprint_decode.py` (new tests), `tests/test_samples.py` (matrix rows unchanged but decode branch must run on ALS too)

**Interfaces:**

- Consumes: everything from Tasks 1-5.
- Produces: evidence that (a) the largest tracked package decodes with bounded output and honest status, (b) the decode branch of the sample matrix runs for the AnimBlueprint asset row of ALS, (c) no diagnostic floods.

- [ ] **Step 1: Write the failing/large test**

```python
def test_als_anim_blueprint_decode_is_bounded_and_complete():
    dec = _decode("ALS_AnimBP.uasset", ("export:274",))
    abp = next(o for o in dec.objects if o.id == "export:274")
    assert abp.semantic is not None
    graphs = abp.semantic["graphs"]
    assert len(graphs) > 50, "expected the full anim-graph family"
    total_nodes = sum(g["node_count"] for g in graphs)
    total_pins = sum(g["pin_count"] for g in graphs)
    assert total_nodes > 1000
    assert total_pins > total_nodes  # every node carries pins
    assert not any(g["truncated"]["nodes"] or g["truncated"]["pins"] for g in graphs)
    # decoded-tier output and no handler failure
    assert abp.status.semantic == "complete"
    handler_failures = [d for d in dec.diagnostics if d.code == "HANDLER_FAILURE"]
    assert not handler_failures
    bounds = [d for d in dec.diagnostics if d.code == "EXPORT_PROPERTY_BOUNDS_EXCEEDED"]
    assert len(bounds) == 0  # existing ALS contract: in-bounds property parse
```

(Note: `export:274` is ALS's AnimBlueprint asset export per ground truth; this test decodes with a single-object request and takes several seconds on the local gate machine — acceptable, the suite already decodes ALS at decode depth. If the assertion `total_pins > total_nodes` or the exact export literal disagrees with the probe, correct the literal — the structural claims must hold.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_blueprint_decode.py::test_als_anim_blueprint_decode_is_bounded_and_complete -v`
Expected: FAIL — currently `export:274` has no `graphs` key (coarse scan was package-wide and kind/status behavior differs).

- [ ] **Step 3: Fix whatever the run reveals**

Likely fixes, each only when the failing assertion shows it:

- If `semantic` stays `partial`: check `capability()` — with pins decoded and no truncation it must return `"decoded"`. If some graph reports `truncated` (node/pin caps), raise the module constants above ALS's real maxima (`MAX_GRAPHS_PER_PACKAGE`/`MAX_NODES_PER_GRAPH_OUTPUT`/`MAX_PINS_PER_NODE_OUTPUT`) — ALS must pass without cap engagement so the honesty contract stays meaningful.
- If `EXPORT_PROPERTY_BOUNDS_EXCEEDED` appears: the extras graph pass must run after the property loop restored the full read range, and node reads are bounded by the shared readers — verify the pass runs with the archive at full range (Task 2 wiring).
- Slow runs are fine (no wall-clock gates); a single decode of ALS at ~10-20 s is within the suite's existing ALS budget.

- [ ] **Step 4: Sample-matrix decode coverage**

The matrix decode branch (Task 2 Step 6) already runs the deep-decode assertions for the `AnimBlueprintGeneratedClass` rows of `ABP_RifleAnimLayers.uasset` and `ALS_AnimBP.uasset` via `_graph_owner_id` — no further matrix changes needed here. Verify by running the matrix decode tests once and confirming the ALS row exercises the branch (it must, since the ALS `AnimBlueprintGeneratedClass` row is in `CAPABILITIES`). If the ALS decode makes the suite noticeably slower, keep the single `_decode_document` lru_cache call (shared with Task 6 Step 1's `("export:274",)` only if the owner id matches — otherwise accept the extra decode; no wall-clock gates exist).

- [ ] **Step 5: Run full suite; ruff**

Run: `python -m pytest -q` then `python -m ruff check .`
Expected: full pass, 0 failures; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/v2/blueprint_graph.py tests/test_blueprint_decode.py tests/test_samples.py
git commit -m "test: ALS decode bounds and matrix rows for blueprint v2 decode (#621 Phase 4.5)"
```

---

## Task 7: Capability claims, status sync, and docs

**Files:**

- Modify: `docs/designs/2026-08-31-semantic-handlers-boundary.md` (D2 §3 blueprint row)
- Modify: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` (Phase 4.5 status line)
- Modify: `README.md` (v2 capability wording)

- [ ] **Step 1: Update D2 §3**

Change the blueprint row's 差距 cell from "大头未迁移 … Phase 4.5 deferred" to a three-state list: migrated (graph/node/pin decode + declaration + SCS components + NewVariables names — with fixture tests `tests/test_blueprint_decode.py`); partial (VarType/type decode, pose flows, baked state machines); deferred (Kismet decompilation, C++ skeleton, parent-asset resolution — per D1). Add one line noting the migration consumed `serializers/graph*.py` as shared readers, consistent with D2's no-bridging rule (reader layer reuse, not v1 extractor bridging).

- [ ] **Step 2: Update the canonical design status line**

In `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`, mark the "Blueprint handler 迁移 graph/Pin/coverage 能力" deliverable of Phase 4 as implemented-for-graphs (with the same three-state split) — status line style must match the file's existing convention.

- [ ] **Step 3: Update README v2 claims**

Move "Blueprint graph decode (depth=decode)" from any future/unimplemented wording into the implemented v2 section, with the fixture/status caveat sentence ("graph/node/pin decode on tracked editor-saved fixtures; VarType typing and Kismet decompilation not implemented").

- [ ] **Step 4: Full gate + commit**

Run: `python -m pytest -q` (all green), `python -m ruff check .` (clean), then:

```bash
git add docs/designs/2026-08-31-semantic-handlers-boundary.md docs/designs/2026-08-26-package-first-uasset-parser-refactor.md README.md
git commit -m "docs: blueprint v2 deep decode status sync (#621 Phase 4.5)"
```

---

## Self-Review Notes

**Spec coverage check:** Phase 4.5 (graph/Pin/coverage migration) → Tasks 1-6; capability/coverage honesty (#629/#630) → Tasks 2-6; bounded-by-default and truncation → Tasks 1, 2, 6; no-bridging (D2) → Tasks 1-2 design; doc status rules → Task 7. Explicitly **out of scope** (tracked follow-ups, not plan gaps): VarType member decode (UE-source layout work), Kismet bytecode/pseudocode and C++ generation (D1 deferred, needs Function-serial-region reader + linker machinery), baked AnimBP state machines, pose-flow edges, multi-Blueprint-per-package graph attribution (no tracked fixture exists — manifest gap), parent-asset/rewrite resolution (D1 deferred).
