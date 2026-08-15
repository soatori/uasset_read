# Blueprint Semantic JSON Extension (#554) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit Blueprint-specific semantic JSON (`format: uasset_read.blueprint_semantic`, `format_version: 1.0.0`) through the #551 common pipeline, covering graphs, nodes, Pin/Port endpoints, control/data flow, types, variables, components, and a declaration index, with Draft 2020-12 schema, semantic validator, honest coverage/diagnostics, standard/debug projection, and byte determinism.

**Architecture:** `Parser -> PackageIR -> build_semantic_ir() -> SemanticIR -> project_semantic() -> validate_semantic_document() -> render_semantic_json()`. A Blueprint package extractor registered in `semantic/extensions.py` produces the domain content dict (graphs/types/variables/components/declaration plus Blueprint-shaped coverage/diagnostics). The #551 envelope (`asset_type`, `status`, mode projection, evidence stripping, canonical rendering) is reused unchanged except for a domain-format hook, an envelope collision guard, and validator format dispatch. Graph data comes from `ExportIR.graphs` (`GraphIR`/`NodeIR`/`PinIR`), enriched in Task 2 with the full UE Pin identity fields already read by `serializers/graph_pin.py`.

**Tech Stack:** Python 3.10+, zero runtime dependencies, pytest, ruff, `jsonschema` (test-only, already used), Draft 2020-12 JSON Schema packaged via `importlib.resources`.

**Spec:**
- Issue #554 (GitHub) and its comments (audit findings, #551 migration notes, design references).
- `docs/superpowers/specs/2026-08-11-blueprint-semantic-json-design.md` (Blueprint design spec — the authoritative contract; sections cited as BP-§N below).
- `docs/designs/2026-08-13-non-blueprint-semantic-design.md` (shared patterns: §4 collision guard, §7 coverage states, §8 `$bounded`, §9.1 test layers, §11.3 one-shot replacement).
- `docs/formats/uasset/semantic-json.md` (common envelope contract from #551).

## Global Constraints

- Zero runtime dependencies: no `pip install`; `jsonschema` is test-only.
- Python 3.10+; read-only parsing; unbaked/editor-saved assets only.
- All code, comments, logs, docs in English.
- Format identity is exactly: `"format": "uasset_read.blueprint_semantic"`, `"format_version": "1.0.0"` (BP-§1).
- Canonical JSON: UTF-8 (no BOM), LF line endings, `allow_nan=False`, exactly one trailing newline; same input + parser version + config => byte-identical output across processes and `PYTHONHASHSEED` values.
- Mode contract: only `standard` and `debug`; `project_semantic(debug_ir, "standard")` must equal the standard build (BP-§3). Parse runs once; mode only affects evidence rendering.
- ID regexes (BP-§5): Graph `^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*$`; Node `^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*/node/[a-z][a-z0-9-]*/[A-Za-z][A-Za-z0-9_.-]*/[0-9]+$`; endpoints match `input.<Name>` / `output.<Name>` / `exec.<Role>`. Ordinals start at 0 in deterministic serialization-source order; no coordinates, no UUIDs, no guessed names in semantic IDs.
- Pin/GUID safe behavior until the research gate (Task 1) passes (BP-§5.1): semantic Node/Pin URIs are the only authoritative references; raw GUIDs are debug-only inconclusive evidence; never merge NodeGuid/PinId/PersistentGuid into one identity; never infer connections from pin names.
- No C++ source, no generated pseudocode, no Blueprint VM bytecode in the JSON; external/engine function targets emit only confirmed target/signature/args/connections (issue scope comment).
- Omit `None` and empty containers; preserve `false`, `0`, `""`, confirmed `null` (BP-§15.1).
- Never fabricate: unconfirmed semantics are marked `partial`/`opaque` with coverage + diagnostics (BP-§7, BP-§8).
- Verification commands (run from repo root; PowerShell):

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_blueprint_semantic.py tests/test_semantic.py
python -m pytest -q
python -m compileall -q src tests
python -m ruff check src tests
python -m build
```

## v1 Scope Decisions (from the spec, recorded for reviewers)

- Extractors are registered for exact classes `Blueprint` and `BlueprintGeneratedClass`. `AnimBlueprint`/`AnimBlueprintGeneratedClass` stay opaque for #555.
- The Blueprint envelope keeps the common required headers (`format`, `format_version`, `mode`, `asset_type`, `asset`, `status`) plus the BP-§4 domain objects; `asset` is extended with `kind`/`generated_class`/`parent_class` (Task 11 step 6).
- Blueprint redefines `coverage` (array of scope entries, BP-§16) and `diagnostics` (aggregated entries, BP-§16); the common `references` table is omitted — external references appear inline with `kind` where confirmed (BP-§5).
- Symbols/constants interning (BP-§15.3/15.4) and reroute folding (BP-§8) are deferred: v1 keeps full endpoints on nodes and reroute nodes as kind `reroute`; `$bounded` wrappers are implemented for oversized literals (BP-§15.5).
- Variables: declaration facts come from `PackageIR.variables`; CDO runtime comparison and inherited-variable chains are not resolved in v1 and are reported as `partial` coverage (BP-§13 forbids guessing).
- Components: origin is `scs_owned`/`scs_inherited`/`native` only with explicit evidence keys; otherwise `unverified` with `partial` coverage (BP-§14 forbids name guessing).
- Deferred to follow-up work (record explicitly, never fabricate now): node-level `refs`/`target` role arrays (BP-§7), `execution.model` latent/async inference and edge `transition` values, FunctionResult signature-compatibility check, node `enabled_state`, Switch selector typing/case metadata, symbols/constants interning (BP-§15.3/15.4), reroute folding (BP-§8), CDO/inheritance variable resolution. Each deferred area surfaces as `partial` coverage where it applies.

## File Structure

| File | Responsibility |
|---|---|
| `src/uasset_read/models/ir.py` (modify) | `PinIR`/`NodeIR` enrichment: pin self-ID, split-pin refs, default fields, flags, node member references |
| `src/uasset_read/ir_builder.py` (modify) | Populate the new `PinIR`/`NodeIR` fields from the raw models |
| `src/uasset_read/semantic/extensions.py` (modify) | Package-scoped extractor contract + domain format/version registration |
| `src/uasset_read/semantic/builder.py` (modify) | Stamp domain format; domain content owns `coverage`/`diagnostics`/`references` |
| `src/uasset_read/semantic/render.py` (modify) | Envelope collision guard; domain override of `coverage`/`diagnostics`/`references` |
| `src/uasset_read/semantic/validator.py` (modify) | Format/version dispatch table; domain validator registry + Blueprint rules |
| `src/uasset_read/semantic/projection.py` (modify) | Strip debug-only `extensions` alongside `evidence` |
| `src/uasset_read/semantic/blueprint/__init__.py` (create) | Extractor registration side effect |
| `src/uasset_read/semantic/blueprint/ids.py` | ASCII slugs, Blueprint URI builders, endpoint IDs, ID regexes |
| `src/uasset_read/semantic/blueprint/types.py` | Pin type fields -> `TypeRef` union + `types` table interning |
| `src/uasset_read/semantic/blueprint/nodes.py` | Node kind classification, data pins/control ports emission, status |
| `src/uasset_read/semantic/blueprint/flows.py` | `control_flow`/`data_flow` entries and canonical edges |
| `src/uasset_read/semantic/blueprint/defaults.py` | Runtime default value selection (BP-§12) |
| `src/uasset_read/semantic/blueprint/variables.py` | `variables` array + `declaration` index |
| `src/uasset_read/semantic/blueprint/components.py` | `components` array with origin and parent closure |
| `src/uasset_read/semantic/blueprint/reporting.py` | Blueprint coverage entries + aggregated diagnostics |
| `src/uasset_read/semantic/blueprint/extractor.py` | Orchestrator registered for Blueprint classes |
| `src/uasset_read/schemas/blueprint_semantic.schema.json` (create) | Draft 2020-12 schema, wheel-packaged by the existing `package-data` glob |
| `src/uasset_read/schema_loader.py` (modify) | `load_blueprint_semantic_schema()` |
| `tests/test_blueprint_semantic.py` (create) | Blueprint semantic unit/contract/acceptance tests |
| `docs/designs/issue-554-pin-guid-research.md` (create) | Research-gate deliverable |
| `docs/formats/uasset/blueprint-semantic-json.md` (create) | Format reference doc |

---

### Task 0: Sync branch onto the #551 foundation

**Files:**
- Modify: working branch `soatori/feature-blueprint-semantic-json-extension` (currently at master `v0.5.4.45`, which predates #551)

**Interfaces:**
- Consumes: `dev-0.5.5` branch containing #551 (semantic package, common schema, `json` routing).
- Produces: a worktree where `src/uasset_read/semantic/` exists and `tests/test_semantic.py` passes.

The #551 common base exists only on `dev-0.5.5`. This branch has no unique commits, so move it onto `dev-0.5.5`.

- [ ] **Step 1: Verify the branch has no unique commits**

Run: `git log --oneline master..HEAD`
Expected: empty output (branch tip equals `master`). If non-empty, STOP and ask the user.

- [ ] **Step 2: Verify the worktree is clean**

Run: `git status --porcelain`
Expected: empty (this plan file was merged into `dev-0.5.5` ahead of time and is tracked there; `temp/` is gitignored).

- [ ] **Step 3: Move the branch onto dev-0.5.5**

```powershell
git reset --hard dev-0.5.5
```

The plan file is already committed on `dev-0.5.5`, so it survives intact.

- [ ] **Step 4: Verify baseline test suite and tooling**

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_semantic.py tests/core/test_json_schema_contract.py
python -m ruff --version
python -c "import jsonschema; print(jsonschema.__version__)"
```

Expected: tests pass; ruff available; `jsonschema` importable (test-only dependency already used by `tests/core/test_json_schema_contract.py`). If `jsonschema` is missing, STOP and report — it is required for Task 13 and must already be present in the environment.

- [ ] **Step 5: Verify the plan file is tracked**

Run: `git log --oneline -1 -- docs/superpowers/plans/2026-08-15-blueprint-semantic-json-extension.md`
Expected: a docs commit already present on the branch (merged to dev ahead of time). If empty, the file was lost — STOP and report.

---

### Task 1: Pin/GUID research gate

**Files:**
- Create: `docs/designs/issue-554-pin-guid-research.md`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: raw parse access via `uasset_read.parse_uasset.parse_uasset(path, tolerant=True)`; exports carry `.graphs` lists of `UEdGraph` with `UEdGraphNode.pins` (`UEdGraphPin`: `pin_id`, `persistent_guid`, `parent_pin`, `sub_pins`, `linked_to_raw`, `ref_pass_through`, `orphaned_pin`).
- Produces: research conclusions doc gating GUID debug evidence; fixture tests pinning the LinkedTo↔PinId relationship used by Tasks 2/7.

BP-§5.1 requires research deliverables before identity semantics are fixed. The parser (`serializers/graph_pin.py`) already reads `PinId`, `PersistentGuid`, `ParentPin`, `SubPins`, `LinkedTo`, `ReferencePassThroughConnection`, and the orphaned/hidden bitfield; this task confirms their real-asset behavior against UE source at `E:\Develop\lib\UnrealEngine` and pins it with executable assertions. Until the gate passes, the safe behavior (semantic IDs only, no GUID identity) is the baseline for all later tasks.

- [ ] **Step 1: Locate UE serialization evidence**

```powershell
Get-Content "E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Classes\EdGraph\EdGraphNode.h" | Select-String -Pattern "NodeGuid|CreateNewGuid|CreateDeterministicGuid" -Context 2,2
Get-Content "E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Classes\EdGraph\EdGraphPin.h" | Select-String -Pattern "PinId|PersistentGuid|ParentPin|SubPins|LinkedTo|ReferencePassThroughConnection|bOrphanedPin|HasAnyConnections" -Context 2,2
Get-Content "E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Private\EdGraph\EdGraphPin.cpp" | Select-String -Pattern "PinId|PersistentGuid|Serialize" -Context 2,2 | Select-Object -First 60
```

- [ ] **Step 2: Write the probe script and run it on real samples**

Create `temp/probe_pin_guids.py`:

```python
"""One-shot probe: Pin identity field presence across real Blueprint samples."""
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset

SAMPLES = [
    "FirstPerson_BP_FirstPersonCharacter.uasset",
    "FirstPerson_BP_FirstPersonGameMode.uasset",
    "StackOBot_BP_Drone.uasset",
    "IntroToUnreal_BP_Light.uasset",
    "IntroToUnreal_BP_SaveData.uasset",
]

def probe(path):
    result = parse_uasset(str(path), tolerant=True)
    stats = {"graphs": 0, "nodes": 0, "pins": 0, "pin_id_present": 0,
             "pin_id_zero": 0, "persistent_guid_nonzero": 0,
             "parent_pin": 0, "sub_pins": 0, "linked_to": 0,
             "ref_pass_through": 0, "orphaned": 0, "dup_pin_ids": 0}
    for export in result.export_map or []:
        for graph in getattr(export, "graphs", None) or []:
            stack = [graph]
            while stack:
                g = stack.pop()
                stats["graphs"] += 1
                for node in g.nodes or []:
                    stats["nodes"] += 1
                    seen = set()
                    for pin in node.pins or []:
                        stats["pins"] += 1
                        pid = getattr(pin, "pin_id", "") or ""
                        if pid:
                            stats["pin_id_present"] += 1
                            if set(pid) == {"0"}:
                                stats["pin_id_zero"] += 1
                            if pid in seen:
                                stats["dup_pin_ids"] += 1
                            seen.add(pid)
                        if (getattr(pin, "persistent_guid", None) or "").strip("0"):
                            stats["persistent_guid_nonzero"] += 1
                        if getattr(pin, "parent_pin", None):
                            stats["parent_pin"] += 1
                        if getattr(pin, "sub_pins", None):
                            stats["sub_pins"] += 1
                        if getattr(pin, "linked_to_raw", None):
                            stats["linked_to"] += 1
                        if getattr(pin, "ref_pass_through", None):
                            stats["ref_pass_through"] += 1
                        if getattr(pin, "orphaned_pin", False):
                            stats["orphaned"] += 1
                    stack.extend(g.subgraphs or [])
    return stats

for name in SAMPLES:
    p = Path("tests/samples") / name
    if not p.exists():
        print(f"SKIP {name} (missing)")
        continue
    print(name, probe(p))
```

Run: `python temp/probe_pin_guids.py`

- [ ] **Step 3: Verify LinkedTo references resolve against PinId**

Extend the probe (or a second script): for `FirstPerson_BP_FirstPersonCharacter.uasset`, build `pin_index = {pin.pin_id: (node.node_guid, pin.pin_name)}` across all graphs of all exports, then for every `pin.linked_to_raw` entry check `ref["pin_guid"] in pin_index`. Record totals: refs, resolved, unresolved (dangling/cross-export refs are expected counter-examples — record them).

- [ ] **Step 4: Write research conclusions**

Create `docs/designs/issue-554-pin-guid-research.md` containing:
1. UE source locations and field semantics for `NodeGuid`, `PinId`, `PersistentGuid`, `ParentPin`/`SubPins`, `LinkedTo`, `ReferencePassThroughConnection`, `bOrphanedPin` (from Step 1).
2. Per-sample probe table (Steps 2–3) covering: normal pins, exec pins, struct split pins (parent/sub), reroute (`K2Node_Knot`), macro instances, orphaned pins, function entry/result.
3. Confirmed/unknown table per field with standard/debug mapping decision.
4. Counter-examples observed: all-zero GUIDs, missing fields, duplicates, one-sided `LinkedTo`.
5. Decision paragraph: whether `source.guid` debug evidence is enabled for NodeGuid/PinId (enable only if Steps 2–3 show stable, non-zero, per-document-unique PinIds; otherwise keep GUIDs out of output entirely).

- [ ] **Step 5: Add regression fixture tests**

Create `tests/test_blueprint_semantic.py`:

```python
"""Blueprint semantic JSON (#554) tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "tests" / "samples"


def _sample(name: str) -> Path:
    path = SAMPLES_DIR / name
    if not path.exists():
        pytest.skip(f"Sample not found: {name}")
    return path


class TestPinGuidResearchFixtures:
    """Pins the research-gate findings (docs/designs/issue-554-pin-guid-research.md)."""

    def test_firstperson_character_pin_identity_fields(self):
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset")), tolerant=True)
        pins = 0
        pin_ids: set[str] = set()
        split_parents = 0
        linked = 0
        for export in result.export_map or []:
            for graph in getattr(export, "graphs", None) or []:
                stack = [graph]
                while stack:
                    g = stack.pop()
                    for node in g.nodes or []:
                        for pin in node.pins or []:
                            pins += 1
                            if getattr(pin, "pin_id", ""):
                                pin_ids.add(pin.pin_id)
                            if getattr(pin, "sub_pins", None):
                                split_parents += 1
                            if getattr(pin, "linked_to_raw", None):
                                linked += 1
                    stack.extend(g.subgraphs or [])
        assert pins > 100
        assert len(pin_ids) > 50
        assert split_parents > 0  # struct split pins present (research counter-example)
        assert linked > 0

    def test_linkedto_refs_resolve_to_pin_ids(self):
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset")), tolerant=True)
        index: set[str] = set()
        pins = []
        for export in result.export_map or []:
            for graph in getattr(export, "graphs", None) or []:
                stack = [graph]
                while stack:
                    g = stack.pop()
                    for node in g.nodes or []:
                        for pin in node.pins or []:
                            if getattr(pin, "pin_id", ""):
                                index.add(pin.pin_id)
                            pins.append(pin)
                    stack.extend(g.subgraphs or [])
        resolved = unresolved = 0
        for pin in pins:
            for ref in pin.linked_to_raw or []:
                guid = ref.get("pin_guid") if isinstance(ref, dict) else None
                if guid and guid in index:
                    resolved += 1
                else:
                    unresolved += 1
        assert resolved > 0
        # Research finding: a bounded number of dangling refs may exist;
        # they must never produce authoritative edges.
        assert unresolved <= resolved
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py`
Expected: PASS. If the split-pin or resolution assertions fail against the real sample, STOP — the edge-building premise of Tasks 2/7 is wrong and the research doc must record why before continuing.

- [ ] **Step 7: Delete probe script and commit**

```powershell
Remove-Item temp/probe_pin_guids.py
git add tests/test_blueprint_semantic.py docs/designs/issue-554-pin-guid-research.md
git commit -m "test: pin/guid research gate fixtures and conclusions (#554)"
```

---

### Task 2: Enrich PinIR/NodeIR with full Pin identity fields

**Files:**
- Modify: `src/uasset_read/models/ir.py` (`PinIR`, `NodeIR`)
- Modify: `src/uasset_read/ir_builder.py` (`_build_pin_ir`, `_build_node_ir`)
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: raw `UEdGraphPin` attributes (`pin_id`, `pin_friendly_name`, `source_index`, `persistent_guid`, `default_text_value`, `auto_default_value`, `default_object_ref`, `parent_pin`, `sub_pins`, `ref_pass_through`, `hidden`, `not_connectable`, `advanced_view`, `orphaned_pin`) and raw node member references (`function_reference`, `event_reference`, `variable_reference` — `FMemberReference` with `.member_name`/`.member_parent`).
- Produces: `PinIR.pin_guid` holds the normalized PinId; new fields `friendly_name`, `source_index`, `persistent_guid`, `default_text_value`, `auto_default_value`, `default_object_name`, `parent_pin_guid`, `sub_pin_guids: list[str]`, `ref_pass_through_guid`, `hidden`, `not_connectable`, `advanced_view`, `orphaned`; `NodeIR.member_name`, `NodeIR.member_parent`.

Spec BP-§20 names the broken boundary: "Pin 自身 ID 字段读取不一致" — `_build_pin_ir` reads `pin.pin_guid` (always empty for `UEdGraphPin`, whose field is `pin_id`) and drops `ParentPin`/`SubPins`/`ReferencePassThroughConnection`, default text/object values, and the editor bitfield. Fix once, at the shared IR, so the semantic layer consumes verified facts.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestPinIRIdentityFields:
    def test_pin_ir_carries_self_id_and_relations(self):
        from uasset_read.parse_uasset import parse_uasset
        from uasset_read.ir_builder import build_package_ir

        result = parse_uasset(str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset")), tolerant=True)
        pkg = build_package_ir(result)
        pin_ids: list[str] = []
        parent_refs = sub_refs = 0
        for export in pkg.exports:
            for graph in export.graphs:
                stack = [graph]
                while stack:
                    g = stack.pop()
                    for node in g.nodes:
                        for pin in node.pins:
                            if pin.pin_guid:
                                pin_ids.append(pin.pin_guid)
                            if pin.parent_pin_guid:
                                parent_refs += 1
                            if pin.sub_pin_guids:
                                sub_refs += 1
                    stack.extend(g.subgraphs)
        assert len(pin_ids) > 50
        assert len(set(pin_ids)) == len(pin_ids)  # PinId unique across the package
        assert parent_refs > 0 and sub_refs > 0   # split-pin tree preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestPinIRIdentityFields -v`
Expected: FAIL (`AttributeError: parent_pin_guid` or empty `pin_ids`).

- [ ] **Step 3: Extend the IR models**

In `src/uasset_read/models/ir.py` extend `PinIR` (new fields after `map_key_pin_subcategory_object_name`):

```python
    friendly_name: str | None = None
    source_index: int | None = None
    persistent_guid: str = ""
    default_text_value: str | None = None
    auto_default_value: str | None = None
    default_object_name: str | None = None
    parent_pin_guid: str = ""
    sub_pin_guids: list[str] = field(default_factory=list)
    ref_pass_through_guid: str = ""
    hidden: bool = False
    not_connectable: bool = False
    advanced_view: bool = False
    orphaned: bool = False
```

(`field` is already imported in `ir.py`.) Extend `NodeIR` (after `event_type`):

```python
    member_name: str | None = None
    member_parent: str | None = None
```

- [ ] **Step 4: Populate the fields in ir_builder**

In `_build_pin_ir` replace the pin_guid line:

```python
    pin_guid = _normalize_guid(getattr(pin, "pin_guid", None)) or _normalize_guid(getattr(pin, "pin_id", None))
```

and extend the returned `PinIR(...)` with:

```python
        friendly_name=_safe_str(getattr(pin, "pin_friendly_name", None)) or None,
        source_index=getattr(pin, "source_index", None),
        persistent_guid=_normalize_guid(getattr(pin, "persistent_guid", None)),
        default_text_value=_safe_str(getattr(pin, "default_text_value", None)) or None,
        auto_default_value=_safe_str(getattr(pin, "auto_default_value", None)) or None,
        default_object_name=_resolve_default_object_name(getattr(pin, "default_object_ref", None)),
        parent_pin_guid=_extract_pin_guid(getattr(pin, "parent_pin", None)) or "",
        sub_pin_guids=[g for g in (_extract_pin_guid(ref) for ref in getattr(pin, "sub_pins", None) or []) if g],
        ref_pass_through_guid=_extract_pin_guid(getattr(pin, "ref_pass_through", None)) or "",
        hidden=bool(getattr(pin, "hidden", False)),
        not_connectable=bool(getattr(pin, "not_connectable", False)),
        advanced_view=bool(getattr(pin, "advanced_view", False)),
        orphaned=bool(getattr(pin, "orphaned_pin", False)),
```

Add the helper (module-level, near `_extract_pin_guid`):

```python
def _resolve_default_object_name(ref) -> str | None:
    """Object name of a linker-resolved pin DefaultObject, or None."""
    if ref is None:
        return None
    if isinstance(ref, dict):
        return ref.get("object_name") or ref.get("name") or None
    return _safe_str(getattr(ref, "object_name", None)) or None
```

In `_build_node_ir` extract member references before the `return NodeIR(...)` (the raw node objects are `models/node_types.py` subclasses carrying `FMemberReference` fields):

```python
    member_name = None
    member_parent = None
    for ref_attr in ("function_reference", "event_reference", "variable_reference"):
        ref = getattr(node, ref_attr, None)
        if ref is not None and getattr(ref, "member_name", ""):
            member_name = _safe_str(ref.member_name)
            member_parent = _safe_str(getattr(ref, "member_parent", None))
            break
```

and add `member_name=member_name, member_parent=member_parent,` to the `NodeIR(...)` constructor.

- [ ] **Step 5: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py tests/test_ir_builder.py tests/test_graph.py`
Expected: PASS (new fields are additive with defaults; no GraphIR consumer regressions).

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/models/ir.py src/uasset_read/ir_builder.py tests/test_blueprint_semantic.py
git commit -m "feat: carry full pin identity fields through PinIR/NodeIR (#554)"
```

---

### Task 3: Extension contract v2 + envelope plumbing for a domain format

**Files:**
- Modify: `src/uasset_read/semantic/extensions.py`
- Modify: `src/uasset_read/semantic/builder.py`
- Modify: `src/uasset_read/semantic/render.py`
- Modify: `src/uasset_read/semantic/validator.py`
- Modify: `src/uasset_read/semantic/models.py` (comment fix)
- Modify: `src/uasset_read/semantic/graph_domain.py`, `structured_domain.py`, `resource_domain.py` (stub docstrings)
- Test: `tests/test_semantic.py` (update registry tests), `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: existing #551 pipeline functions.
- Produces: `register_extension(class_name, extractor, *, domain_format=None, domain_format_version=None)`; extractor signature `(package_ir, export_ir, coverage_model, evidence_list) -> dict`; `get_domain_format(class_name) -> tuple[str, str] | None`; `render_semantic_json` raises `ValueError` on envelope-key collisions and lets content override exactly `{references, coverage, diagnostics}`; `validate_semantic_document` accepts any format in `_FORMAT_VERSIONS` and dispatches `_DOMAIN_VALIDATORS[format](ir)`.

Decisions (one-shot replacement — no extractor is currently registered, so no compatibility layer):
1. Extractor signature becomes `extractor(package_ir, export_ir, coverage_model, evidence_list) -> dict`. Blueprint needs package-wide facts (graphs live on the `BlueprintGeneratedClass` export, metadata on the `Blueprint` export).
2. When a domain format is registered, the builder stamps it onto `SemanticIR.format`/`format_version`; the domain content owns the `coverage`, `diagnostics`, and `references` top-level keys (the Blueprint format redefines their shapes per BP-§16; `references` is omitted — external refs are inline with `kind` per BP-§5).
3. Renderer gains the collision guard from non-bp design §4.
4. Validator gains a format/version table and a domain-validator registry keyed by format.

- [ ] **Step 1: Write the failing tests**

Replace the bodies of the two tests in `tests/test_semantic.py::TestExtensionRegistry`:

```python
    def test_register_and_lookup(self):
        from uasset_read.semantic.extensions import register_extension, get_extractor, _REGISTRY
        def dummy_extractor(package_ir, export_ir, cov, evidence):
            return {}
        register_extension("TestDummyClass", dummy_extractor)
        assert get_extractor("TestDummyClass") is dummy_extractor
        _REGISTRY.pop("TestDummyClass", None)

    def test_duplicate_registration_raises(self):
        from uasset_read.semantic.extensions import register_extension, _REGISTRY
        def dummy_extractor(package_ir, export_ir, cov, evidence):
            return {}
        register_extension("TestDup", dummy_extractor)
        with pytest.raises(ValueError):
            register_extension("TestDup", dummy_extractor)
        _REGISTRY.pop("TestDup", None)
```

(`pytest` is already imported in `tests/test_semantic.py`.) Append to `tests/test_blueprint_semantic.py`:

```python
class TestDomainFormatPlumbing:
    def _package_ir(self, export):
        from uasset_read.models.ir import PackageIR, PackageHeaderIR, DiagnosticsDataIR
        header = PackageHeaderIR(
            package_name="/Game/BP_Fake", package_class="Package", package_flags=0,
            total_export_count=1, total_import_count=0, ue_version="5.4.0",
        )
        pkg = PackageIR(header=header, name_map=(), imports=[], exports=[export])
        pkg.diagnostics_data = DiagnosticsDataIR(status="success", errors=None, warnings=None)
        return pkg

    def _fake_export(self):
        from uasset_read.models.ir import ExportIR
        return ExportIR(
            index=0, object_name="BP_Fake", object_class="Blueprint",
            serial_size=0, outer_index_resolved=None, super_index_resolved=None,
            parent_class=None, properties=[], graphs=[], bulk_data=None,
        )

    def _build(self, monkeypatch, content, domain_format=None, domain_version=None):
        from uasset_read.semantic import extensions
        from uasset_read.semantic.builder import build_semantic_ir

        def extractor(package_ir, export_ir, cov, evidence):
            return content

        monkeypatch.setattr(extensions, "_REGISTRY", {"Blueprint": extractor})
        monkeypatch.setattr(
            extensions, "_DOMAIN_FORMATS",
            {"Blueprint": (domain_format, domain_version)} if domain_format else {})
        return build_semantic_ir(self._package_ir(self._fake_export()), source_path="BP_Fake.uasset")

    def test_domain_format_stamped(self, monkeypatch):
        ir = self._build(monkeypatch, {"graphs": []},
                         domain_format="uasset_read.blueprint_semantic", domain_version="1.0.0")
        assert ir.format == "uasset_read.blueprint_semantic"
        assert ir.format_version == "1.0.0"

    def test_collision_guard_raises(self, monkeypatch):
        from uasset_read.semantic.render import render_semantic_json
        ir = self._build(monkeypatch, {"format": "evil"})
        with pytest.raises(ValueError, match="collides"):
            render_semantic_json(ir)

    def test_domain_coverage_override(self, monkeypatch):
        from uasset_read.semantic.render import render_semantic_json
        ir = self._build(
            monkeypatch,
            {"references": [], "coverage": [{"scope": "graphs", "status": "partial"}],
             "diagnostics": [{"code": "BP_TEST", "scope": "asset", "severity": "info",
                              "effect": "none", "count": 1}]},
            domain_format="uasset_read.blueprint_semantic", domain_version="1.0.0")
        doc = json.loads(render_semantic_json(ir))
        assert doc["coverage"] == [{"scope": "graphs", "status": "partial"}]
        assert "references" not in doc  # empty list stripped by renderer
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestDomainFormatPlumbing tests/test_semantic.py::TestExtensionRegistry -v`
Expected: FAIL (missing `_DOMAIN_FORMATS`, collision guard, override behavior, new signature).

- [ ] **Step 3: Implement extensions.py**

Replace `src/uasset_read/semantic/extensions.py` with:

```python
"""Extension registry — maps exact UE class names to domain extractors.

Extractor contract (v2, package-scoped):

    extractor(package_ir, export_ir, coverage_model, evidence_list) -> dict

The returned dict is merged into SemanticIR.content. Reserved envelope keys
must not appear in it except the overridable set {coverage, diagnostics,
references}, which a domain format may redefine.
"""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR

_REGISTRY: dict[str, Callable] = {}
_DOMAIN_FORMATS: dict[str, tuple[str, str]] = {}


def register_extension(
    class_name: str,
    extractor: Callable,
    *,
    domain_format: str | None = None,
    domain_format_version: str | None = None,
) -> None:
    """Register a domain extractor for an exact UE class name.

    Raises ValueError on duplicate registration, or when domain_format and
    domain_format_version are not provided together.
    """
    if class_name in _REGISTRY:
        raise ValueError(f"Extension already registered for class '{class_name}'")
    if bool(domain_format) != bool(domain_format_version):
        raise ValueError("domain_format and domain_format_version must be provided together")
    _REGISTRY[class_name] = extractor
    if domain_format:
        _DOMAIN_FORMATS[class_name] = (domain_format, domain_format_version)


def get_extractor(class_name: str) -> Callable | None:
    """Get the registered extractor for a class, or None."""
    return _REGISTRY.get(class_name)


def get_domain_format(class_name: str) -> tuple[str, str] | None:
    """Get (format, format_version) for a domain-format class, or None."""
    return _DOMAIN_FORMATS.get(class_name)


def is_registered(class_name: str) -> bool:
    """Check whether a class has a registered extractor."""
    return class_name in _REGISTRY
```

- [ ] **Step 4: Update builder.py**

Import `get_domain_format` alongside `get_extractor`. In `build_semantic_ir` restructure the extractor section (current lines ~170-220) to:

```python
    extractor = get_extractor(primary.object_class or "")
    domain_format = get_domain_format(primary.object_class or "")

    # Known type but no registered extractor -> opaque (not full)
    if asset_type != "unknown" and extractor is None:
        representation = "opaque"
        diag.add("info", "NO_EXTRACTOR", f"No semantic extractor registered for class '{primary.object_class}'")

    status = AssetStatus(parse=parse, representation=representation)

    if status.parse == "partial" and not any(d.code == "PARTIAL_PARSE" for d in diag.build()):
        diag.add("warning", "PARTIAL_PARSE", f"Asset '{primary.object_name}' was only partially parsed")
    elif status.parse == "failed" and not any(d.code == "PARSE_FAILED" for d in diag.build()):
        diag.add("error", "PARSE_FAILED", f"Asset '{primary.object_name}' failed to parse")

    cov = CoverageModel()
    content: dict = {}
    evidence_list: list = list(evidence)

    if extractor is not None and status.representation != "opaque":
        content = extractor(package_ir, primary, cov, evidence_list)
    else:
        cov.track("domain_content", False)

    # Domain formats own coverage/diagnostics/references inside content.
    owns_envelope_sections = domain_format is not None and status.representation != "opaque"
    if owns_envelope_sections and content.get("coverage"):
        # Any reported coverage entry means some scope is not complete:
        # representation cannot be "full" (honest status contract).
        representation = "partial"
        status = AssetStatus(parse=parse, representation="partial")
    coverage = None if owns_envelope_sections else cov.build()
    diagnostics = () if owns_envelope_sections else diag.build()
    references = () if owns_envelope_sections else collect_references(package_ir.imports, package_ir.exports)

    fmt, fmt_version = "uasset_read.asset_semantic", "1.0"
    if owns_envelope_sections:
        fmt, fmt_version = domain_format

    return SemanticIR(
        format=fmt,
        format_version=fmt_version,
        mode="",
        asset_type=asset_type,
        asset=AssetMeta(
            package=_resolve_package_name(package_ir, source_path),
            name=primary.object_name or "unknown",
            generated_class=primary.object_class if asset_type == "unknown" else None,
        ),
        status=status,
        references=references,
        content=content,
        coverage=coverage,
        diagnostics=diagnostics,
        evidence=tuple(evidence_list),
    )
```

Keep everything above the extractor section (primary selection, asset_type resolution, status mapping, evidence entries, unknown-type handling) unchanged. Update the stale comment on `models.py` line 88 to: `content: dict = field(default_factory=dict)   # domain content; promoted to top-level JSON by renderer`.

- [ ] **Step 5: Update render.py merge with collision guard**

Replace the merge block inside `render_semantic_json`:

```python
    _COMMON_FIELDS = {"format", "format_version", "mode", "asset_type", "asset", "status",
                      "references", "coverage", "diagnostics", "evidence"}
    _OVERRIDABLE = {"references", "coverage", "diagnostics"}
    for key, value in content.items():
        if key in _COMMON_FIELDS and key not in _OVERRIDABLE:
            raise ValueError(f"Domain content collides with envelope key: '{key}'")
        if key in _OVERRIDABLE:
            raw[key] = value
        elif key not in raw:
            raw[key] = value
```

- [ ] **Step 6: Update validator.py dispatch**

Replace the module-level mode/parse constants block additions and the two format checks. Add after the existing constants:

```python
_FORMAT_VERSIONS = {
    "uasset_read.asset_semantic": "1.0",
    "uasset_read.blueprint_semantic": "1.0.0",
}

_DOMAIN_VALIDATORS: dict[str, object] = {}


def register_domain_validator(fmt: str, validator) -> None:
    """Register a format-specific semantic validator."""
    _DOMAIN_VALIDATORS[fmt] = validator
```

Replace the format/version checks with:

```python
    expected_version = _FORMAT_VERSIONS.get(ir.format)
    if expected_version is None:
        errors.append(f"Invalid format: '{ir.format}' is not a known semantic format")
    elif ir.format_version != expected_version:
        errors.append(
            f"Invalid format_version for '{ir.format}': expected '{expected_version}', got '{ir.format_version}'")
```

Guard the full-representation coverage check (Blueprint carries coverage in content):

```python
    if ir.status.representation == "full" and ir.coverage is not None:
```

Guard the opaque-diagnostic check for domain formats:

```python
    if ir.status.representation == "opaque" and not ir.diagnostics and ir.format == "uasset_read.asset_semantic":
        errors.append("Opaque representation must have at least one diagnostic")

    domain_validator = _DOMAIN_VALIDATORS.get(ir.format)
    if domain_validator is not None:
        errors.extend(domain_validator(ir))

    return errors
```

- [ ] **Step 7: Update the three domain stub docstrings**

Replace the module docstring of `graph_domain.py`, `structured_domain.py`, `resource_domain.py` with e.g.:

```python
"""Graph domain extractor — stub for #556.

Extractor contract v2: extractor(package_ir, export_ir, cov, evidence_list) -> dict.
"""
```

- [ ] **Step 8: Run all tests**

Run: `python -m pytest -q tests/test_semantic.py tests/test_blueprint_semantic.py tests/core/test_json_schema_contract.py tests/core/test_json_output_levels.py`
Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add src/uasset_read/semantic tests/test_semantic.py tests/test_blueprint_semantic.py
git commit -m "refactor: package-scoped extension contract with domain formats and collision guard (#554)"
```

---

### Task 4: Blueprint ID module (slugs, URIs, endpoint IDs)

**Files:**
- Create: `src/uasset_read/semantic/blueprint/__init__.py`
- Create: `src/uasset_read/semantic/blueprint/ids.py`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Produces: `ascii_slug(name) -> str`, `kind_slug(kind) -> str`, `graph_id(slug)`, `node_id(graph_slug, kind, name_slug, ordinal)`, `data_endpoint(pin_name, direction)`, `exec_endpoint(pin_name)`, regexes `GRAPH_ID_RE`, `NODE_ID_RE`, `ENDPOINT_RE` (patterns without anchors; consumers use `re.fullmatch` or wrap with `^...$`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintIds:
    def test_ascii_slug_rules(self):
        from uasset_read.semantic.blueprint.ids import ascii_slug
        assert ascii_slug("EventGraph") == "EventGraph"
        assert ascii_slug("BeginPlay") == "BeginPlay"
        assert ascii_slug("My Var/Name") == "My_Var_Name"
        assert ascii_slug("123abc") == "x123abc"
        assert ascii_slug("") == "unnamed"
        assert ascii_slug("节点") == "unnamed"

    def test_id_builders(self):
        from uasset_read.semantic.blueprint.ids import graph_id, node_id, data_endpoint, exec_endpoint
        assert graph_id("EventGraph") == "blueprint://graph/EventGraph"
        assert node_id("EventGraph", "call", "SetActorLocation", 0) == \
            "blueprint://graph/EventGraph/node/call/SetActorLocation/0"
        assert data_endpoint("NewLocation", "input") == "input.NewLocation"
        assert exec_endpoint("execute") == "exec.in"
        assert exec_endpoint("then") == "exec.out"
        assert exec_endpoint("True") == "exec.true"

    def test_id_regexes_match_builders(self):
        import re
        from uasset_read.semantic.blueprint.ids import (
            GRAPH_ID_RE, NODE_ID_RE, ENDPOINT_RE,
            graph_id, node_id, data_endpoint, exec_endpoint,
        )
        assert re.fullmatch(GRAPH_ID_RE, graph_id("EventGraph"))
        assert re.fullmatch(NODE_ID_RE, node_id("Function_TakeDamage", "variable-set", "Health", 3))
        for ep in (data_endpoint("NewLocation", "input"), exec_endpoint("then")):
            assert re.fullmatch(ENDPOINT_RE, ep)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintIds -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement ids.py**

Create `src/uasset_read/semantic/blueprint/__init__.py`:

```python
"""Blueprint semantic JSON domain (#554)."""
```

Create `src/uasset_read/semantic/blueprint/ids.py`:

```python
"""Blueprint semantic IDs — readable URIs, ASCII slugs, endpoint IDs (BP-§5)."""
from __future__ import annotations

import re

GRAPH_ID_RE = r"blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*"
NODE_ID_RE = r"blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*/node/[a-z][a-z0-9-]*/[A-Za-z][A-Za-z0-9_.-]*/[0-9]+"
ENDPOINT_RE = r"(input|output|exec)\.[A-Za-z][A-Za-z0-9_.-]*"

_SLUG_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_KIND_RE = re.compile(r"[^a-z0-9-]+")


def ascii_slug(name: str) -> str:
    """ASCII slug preserving case; invalid runs collapse to '_'."""
    slug = _SLUG_RE.sub("_", name or "").strip("_")
    if not slug:
        return "unnamed"
    if not slug[0].isalpha():
        slug = "x" + slug
    return slug


def kind_slug(kind: str) -> str:
    """Lowercase slug for the <Kind> node-ID segment."""
    slug = _KIND_RE.sub("-", (kind or "").lower()).strip("-")
    return slug or "custom"


def graph_id(graph_slug: str) -> str:
    return f"blueprint://graph/{graph_slug}"


def node_id(graph_slug: str, kind: str, name_slug: str, ordinal: int) -> str:
    return f"blueprint://graph/{graph_slug}/node/{kind_slug(kind)}/{name_slug}/{ordinal}"


def data_endpoint(pin_name: str, direction: str) -> str:
    """direction: ``input`` or ``output`` (graph direction, BP-§8)."""
    return f"{direction}.{ascii_slug(pin_name)}"


_EXEC_ROLE_MAP = {"execute": "in", "then": "out"}


def exec_endpoint(pin_name: str) -> str:
    """Canonical exec role: execute->in, then->out, else lowercased slug."""
    role = _EXEC_ROLE_MAP.get((pin_name or "").lower())
    if role is None:
        role = ascii_slug(pin_name).lower().replace("_", "-") or "port"
    return f"exec.{role}"
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintIds -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/semantic/blueprint tests/test_blueprint_semantic.py
git commit -m "feat: blueprint semantic id builders and slug rules (#554)"
```

---

### Task 5: Type system — TypeRef union and `types` table

**Files:**
- Create: `src/uasset_read/semantic/blueprint/types.py`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: PinIR-shaped fields (`pin_category`, `pin_subcategory`, `pin_subcategory_object_name`, `container_type` string `"None"|"Array"|"Set"|"Map"`, `is_reference`, `is_const`, `is_weak_pointer`, `is_uobject_wrapper`, `map_key_pin_category`, `map_key_pin_subcategory`, `map_key_pin_subcategory_object_name`).
- Produces: `TypeTable` with `.entries: dict[str, dict]` (the emitted `types` object) and `.type_ref_for(**fields) -> str | {"$type": id}`; `type_ref_from_pin(table, pin)`.

BP-§11: `TypeRef` is a strict union of primitive strings and `{"$type": "t<N>"}`; the table interns complex types by canonical JSON encoding in first-encounter order. Map: the main `FEdGraphPinType` is the key, the terminal is the value (BP-§11 explicit rule — the underlying serializer field names are misleading, see `graph_pin.py:79-100`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintTypes:
    def test_primitive_categories_inline(self):
        from uasset_read.semantic.blueprint.types import TypeTable
        table = TypeTable()
        assert table.type_ref_for(category="bool") == "bool"
        assert table.type_ref_for(category="real", subcategory="double") == "double"
        assert table.type_ref_for(category="real") == "float"
        assert table.entries == {}

    def test_struct_deduplicated(self):
        from uasset_read.semantic.blueprint.types import TypeTable
        table = TypeTable()
        r1 = table.type_ref_for(category="struct", subcategory_object_name="Vector")
        r2 = table.type_ref_for(category="struct", subcategory_object_name="Vector")
        assert r1 == r2 == {"$type": "t0"}
        assert table.entries == {"t0": {"kind": "struct", "path": "Vector"}}

    def test_map_key_value_terminal(self):
        from uasset_read.semantic.blueprint.types import TypeTable
        table = TypeTable()
        ref = table.type_ref_for(category="name", container_type=3,
                                 map_key_terminal_category="struct",
                                 map_key_terminal_sub_category_object_name="Objective")
        entry = table.entries[ref["$type"]]
        assert entry["kind"] == "map"
        assert entry["key"] == "name"
        assert entry["value"] == {"$type": "t0"}
        assert table.entries["t0"] == {"kind": "struct", "path": "Objective"}

    def test_reference_and_const_modifiers(self):
        from uasset_read.semantic.blueprint.types import TypeTable
        table = TypeTable()
        ref = table.type_ref_for(category="object", subcategory_object_name="Actor",
                                 is_reference=True, is_const=True)
        entry = table.entries[ref["$type"]]
        assert entry["kind"] == "ref"
        assert entry["const"] is True
        inner = table.entries[entry["target"]["$type"]]
        assert inner == {"kind": "object", "path": "Actor"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintTypes -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement types.py**

Create `src/uasset_read/semantic/blueprint/types.py`:

```python
"""Blueprint type system — TypeRef union and interned types table (BP-§11)."""
from __future__ import annotations

import json
from typing import Any


class TypeTable:
    """Builds the ``types`` table and TypeRef values in first-encounter order.

    ``type_ref_for`` accepts PinIR-shaped keyword arguments. Primitive
    categories return inline strings; complex types are interned and returned
    as ``{"$type": "t<N>"}``. Map pins: main type is the key, the terminal is
    the value (BP-§11).
    """

    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}
        self._by_encoding: dict[str, str] = {}
        self._counter = 0

    def _intern(self, entry: dict) -> dict:
        key = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        type_id = self._by_encoding.get(key)
        if type_id is None:
            type_id = f"t{self._counter}"
            self._counter += 1
            self._by_encoding[key] = type_id
            self.entries[type_id] = entry
        return {"$type": type_id}

    def type_ref_for(
        self,
        category: str = "",
        subcategory: str = "",
        subcategory_object_name: str | None = None,
        container_type: int | str = 0,
        is_reference: bool = False,
        is_const: bool = False,
        is_weak_pointer: bool = False,
        is_uobject_wrapper: bool = False,
        map_key_terminal_category: str = "",
        map_key_terminal_sub_category: str = "",
        map_key_terminal_sub_category_object_name: str | None = None,
    ) -> Any:
        base = self._base_ref(category, subcategory, subcategory_object_name,
                              container_type, is_weak_pointer, is_uobject_wrapper,
                              map_key_terminal_category, map_key_terminal_sub_category,
                              map_key_terminal_sub_category_object_name)
        if is_reference or is_const:
            entry: dict = {"kind": "ref", "target": base}
            if is_const:
                entry["const"] = True
            return self._intern(entry)
        return base

    def _base_ref(self, category, subcategory, subcategory_object_name, container_type,
                  is_weak_pointer, is_uobject_wrapper,
                  map_key_terminal_category, map_key_terminal_sub_category,
                  map_key_terminal_sub_category_object_name) -> Any:
        category = (category or "").lower()
        subcategory = (subcategory or "").lower()
        name = subcategory_object_name or ""

        code = _container_code(container_type)
        if code == 1:
            elem = self.type_ref_for(category=category, subcategory=subcategory,
                                    subcategory_object_name=subcategory_object_name)
            return self._intern({"kind": "array", "element": elem})
        if code == 2:
            elem = self.type_ref_for(category=category, subcategory=subcategory,
                                    subcategory_object_name=subcategory_object_name)
            return self._intern({"kind": "set", "element": elem})
        if code == 3:
            key_ref = self.type_ref_for(category=category, subcategory=subcategory,
                                        subcategory_object_name=subcategory_object_name)
            value_ref = self.type_ref_for(category=map_key_terminal_category,
                                          subcategory=map_key_terminal_sub_category,
                                          subcategory_object_name=map_key_terminal_sub_category_object_name)
            return self._intern({"kind": "map", "key": key_ref, "value": value_ref})

        if category in ("bool", "string", "name", "text", "byte", "int", "int64",
                        "int8", "uint8", "uint16", "uint32", "uint64", "float",
                        "double", "vector", "vector2d", "rotator", "transform",
                        "color", "guid"):
            return category
        if category == "real":
            return "double" if subcategory == "double" else "float"

        if category == "struct":
            return self._intern({"kind": "struct", "path": name or subcategory or "unnamed"})
        if category == "enum":
            return self._intern({"kind": "enum", "path": name or subcategory or "unnamed"})
        if category == "delegate":
            entry = {"kind": "delegate", "signature": name or subcategory or "unnamed"}
            if subcategory == "mcdelegate":
                entry["multicast"] = True
            return self._intern(entry)
        if category == "interface":
            return self._intern({"kind": "interface", "path": name or "unnamed"})
        if category == "class":
            return self._intern({"kind": "class", "path": name or "unnamed"})
        if category in ("object", "softobject"):
            entry = {"kind": "object", "path": name or "Object"}
            if category == "softobject":
                entry["soft"] = True
            if is_weak_pointer:
                entry["weak"] = True
            if is_uobject_wrapper:
                entry["uobject_wrapper"] = True
            return self._intern(entry)
        if category == "wildcard":
            return self._intern({"kind": "wildcard", "declared": "wildcard"})

        return self._intern({"kind": "unknown", "category": category or "unknown",
                             "name": name or subcategory or ""})


def type_ref_from_pin(table: TypeTable, pin) -> Any:
    """TypeRef for a PinIR using its FEdGraphPinType-derived fields."""
    return table.type_ref_for(
        category=getattr(pin, "pin_category", ""),
        subcategory=getattr(pin, "pin_subcategory", ""),
        subcategory_object_name=getattr(pin, "pin_subcategory_object_name", None),
        container_type=getattr(pin, "container_type", "None"),
        is_reference=getattr(pin, "is_reference", False),
        is_const=getattr(pin, "is_const", False),
        is_weak_pointer=getattr(pin, "is_weak_pointer", False),
        is_uobject_wrapper=getattr(pin, "is_uobject_wrapper", False),
        map_key_terminal_category=getattr(pin, "map_key_pin_category", ""),
        map_key_terminal_sub_category=getattr(pin, "map_key_pin_subcategory", ""),
        map_key_terminal_sub_category_object_name=getattr(pin, "map_key_pin_subcategory_object_name", None),
    )


def _container_code(value: Any) -> int:
    if isinstance(value, int):
        return value
    return {"None": 0, "Array": 1, "Set": 2, "Map": 3}.get(str(value), 0)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintTypes -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/semantic/blueprint/types.py tests/test_blueprint_semantic.py
git commit -m "feat: blueprint type table and typeref union (#554)"
```

---

### Task 6: Graph and Node emission

**Files:**
- Create: `src/uasset_read/semantic/blueprint/reporting.py` (Task 6 dependency, completed here)
- Create: `src/uasset_read/semantic/blueprint/nodes.py`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: `GraphIR` (`graph_guid`, `graph_name`, `graph_class`, `nodes`, `subgraphs`) and `NodeIR`/`PinIR` from Task 2; `TypeTable` (Task 5); `BlueprintReporting` (this task).
- Produces: `emit_graphs(graphs, table, reporting, mode) -> (graphs_json, index)` where `index` maps `pin_guid -> {"node", "graph", "endpoint", "direction", "is_exec", "orphaned", "not_connectable", "linked": list[str]}` for Task 7; `BlueprintReporting.coverage(scope, status, **kw)`, `.diagnostic(code, scope, severity, effect, occurrence)`, `.coverage_entries()`, `.diagnostics_entries(mode)`.

BP-§6/§7 behavior: graphs `{id, name, kind, nodes}` with `kind` from graph class/name; nodes `{id, kind, label?, status?, source_type?, data_pins, control_ports, defaults(Task 8)}`; ordinals per `(kind, name)` in serialization order; comment nodes excluded; unknown classes -> `kind: "custom"`, `status: "opaque"`, `source_type` preserved, aggregated `BP_NODE_UNRECOGNIZED` diagnostic (BP-§7). Exec endpoints normalized (`execute->exec.in`, `then->exec.out`); data endpoints keep readable names. Debug mode adds node/graph `evidence` (GUIDs are debug-only per research gate; enable `source.guid` evidence only if Task 1 decided so — default below emits GUID evidence in debug only, drop the keys if the research doc says otherwise).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintNodeEmission:
    def _graphs(self):
        from uasset_read.models.ir import GraphIR, NodeIR, PinIR
        pin_exec_out = PinIR(pin_name="then", pin_type="exec", linked_to=[], direction="EGPD_Output",
                             default_value=None, pin_guid="b" * 32, pin_category="exec")
        pin_exec_in = PinIR(pin_name="execute", pin_type="exec", linked_to=[], direction="EGPD_Input",
                            default_value=None, pin_guid="a" * 32, pin_category="exec")
        pin_data = PinIR(pin_name="NewLocation", pin_type="struct", linked_to=[], direction="EGPD_Input",
                         default_value="(X=1.0,Y=2.0,Z=3.0)", pin_guid="c" * 32,
                         pin_category="struct", pin_subcategory_object_name="Vector")
        node_event = NodeIR(node_guid="1" * 32, node_class="K2Node_Event", node_comment=None,
                            pins=[pin_exec_out], execution_flow=[])
        node_event.member_name = "ReceiveBeginPlay"
        node_call = NodeIR(node_guid="2" * 32, node_class="K2Node_CallFunction", node_comment=None,
                           pins=[pin_exec_in, pin_exec_out, pin_data], execution_flow=[])
        node_call.member_name = "SetActorLocation"
        return [GraphIR(graph_guid="9" * 32, graph_name="EventGraph", graph_class="EdGraph",
                        nodes=[node_event, node_call], execution_chains=[])]

    def test_graph_and_node_shape(self):
        from uasset_read.semantic.blueprint.nodes import emit_graphs
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        table = TypeTable()
        rep = BlueprintReporting()
        graphs_json, index = emit_graphs(self._graphs(), table, rep, mode="standard")
        g = graphs_json[0]
        assert g["id"] == "blueprint://graph/EventGraph"
        assert g["kind"] == "event_graph"
        event, call = g["nodes"]
        assert event["id"] == "blueprint://graph/EventGraph/node/event/ReceiveBeginPlay/0"
        assert call["id"] == "blueprint://graph/EventGraph/node/call/SetActorLocation/0"
        assert "input.NewLocation" in call["data_pins"]
        assert call["data_pins"]["input.NewLocation"]["type"] == {"$type": "t0"}
        assert table.entries["t0"] == {"kind": "struct", "path": "Vector"}
        assert "exec.in" in call["control_ports"]
        assert call["control_ports"]["exec.out"]["role"] == "then"
        assert "b" * 32 in index and index["b" * 32]["is_exec"]

    def test_unknown_node_is_custom_opaque(self):
        from uasset_read.models.ir import GraphIR, NodeIR, PinIR
        from uasset_read.semantic.blueprint.nodes import emit_graphs
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        pin = PinIR(pin_name="then", pin_type="exec", linked_to=[], direction="EGPD_Output",
                    default_value=None, pin_guid="d" * 32, pin_category="exec")
        node = NodeIR(node_guid="3" * 32, node_class="K2Node_SomePluginThing", node_comment=None,
                      pins=[pin], execution_flow=[])
        graph = GraphIR(graph_guid="8" * 32, graph_name="EventGraph", graph_class="EdGraph",
                        nodes=[node], execution_chains=[])
        rep = BlueprintReporting()
        graphs_json, _ = emit_graphs([graph], TypeTable(), rep, mode="standard")
        emitted = graphs_json[0]["nodes"][0]
        assert emitted["kind"] == "custom"
        assert emitted["status"] == "opaque"
        assert emitted["source_type"] == "K2Node_SomePluginThing"
        assert any(d["code"] == "BP_NODE_UNRECOGNIZED" for d in rep.diagnostics_entries("standard"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintNodeEmission -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement reporting.py**

Create `src/uasset_read/semantic/blueprint/reporting.py`:

```python
"""Blueprint coverage entries and aggregated diagnostics (BP-§16)."""
from __future__ import annotations

_MAX_OCCURRENCES = 8


class BlueprintReporting:
    """Collects coverage entries and aggregated diagnostics.

    Coverage entries: {"scope": str, "status": "partial"|"unavailable"|"truncated",
    optional: reason, declared, emitted, omitted}. Diagnostics are aggregated
    by (code, scope, severity, effect); message/occurrence never joins the
    identity (BP-§16). Debug occurrences are bounded.
    """

    def __init__(self) -> None:
        self._coverage: list[dict] = []
        self._coverage_scopes: set[str] = set()
        self._diags: dict[tuple, dict] = {}

    def coverage(self, scope: str, status: str, *, reason: str = "",
                 declared: int | None = None, emitted: int | None = None,
                 omitted: int | None = None) -> None:
        if scope in self._coverage_scopes:
            return
        self._coverage_scopes.add(scope)
        entry: dict = {"scope": scope, "status": status}
        if reason:
            entry["reason"] = reason
        if declared is not None:
            entry["declared"] = declared
        if emitted is not None:
            entry["emitted"] = emitted
        if omitted is not None:
            entry["omitted"] = omitted
        self._coverage.append(entry)

    def diagnostic(self, code: str, scope: str, severity: str, effect: str,
                   occurrence: dict | None = None) -> None:
        key = (code, scope, severity, effect)
        entry = self._diags.get(key)
        if entry is None:
            entry = {"code": code, "scope": scope, "severity": severity,
                     "effect": effect, "count": 0, "_occurrences": []}
            self._diags[key] = entry
        entry["count"] += 1
        if occurrence is not None and len(entry["_occurrences"]) < _MAX_OCCURRENCES:
            entry["_occurrences"].append(occurrence)

    def coverage_entries(self) -> list[dict]:
        return sorted(self._coverage, key=lambda e: e["scope"])

    def diagnostics_entries(self, mode: str) -> list[dict]:
        entries = []
        for entry in sorted(self._diags.values(),
                            key=lambda e: (e["severity"], e["code"], e["scope"], e["effect"])):
            item = {k: v for k, v in entry.items() if k != "_occurrences"}
            if mode == "debug" and entry["_occurrences"]:
                item["evidence"] = {"occurrences": entry["_occurrences"]}
            entries.append(item)
        return entries
```

- [ ] **Step 4: Implement nodes.py**

Create `src/uasset_read/semantic/blueprint/nodes.py`:

```python
"""Graph/node/pin/port emission for Blueprint semantic JSON (BP-§6, §7, §8)."""
from __future__ import annotations

from typing import Any

from uasset_read.semantic.blueprint.ids import (
    ascii_slug, graph_id, node_id, data_endpoint, exec_endpoint,
)
from uasset_read.semantic.blueprint.types import type_ref_from_pin

_NODE_KIND_MAP = {
    "K2Node_Event": "event",
    "K2Node_CustomEvent": "custom_event",
    "K2Node_FunctionEntry": "function_entry",
    "K2Node_FunctionResult": "function_result",
    "K2Node_CallFunction": "call",
    "K2Node_VariableGet": "variable_get",
    "K2Node_VariableSet": "variable_set",
    "K2Node_IfThenElse": "branch",
    "K2Node_SwitchInteger": "switch",
    "K2Node_SwitchString": "switch",
    "K2Node_SwitchEnum": "switch",
    "K2Node_SwitchName": "switch",
    "K2Node_ExecutionSequence": "sequence",
    "K2Node_MultiGate": "sequence",
    "K2Node_MacroInstance": "macro",
    "K2Node_DynamicCast": "cast",
    "K2Node_ClassDynamicCast": "cast",
    "K2Node_MakeStruct": "make_struct",
    "K2Node_BreakStruct": "break_struct",
    "K2Node_CreateDelegate": "delegate_bind",
    "K2Node_AddDelegate": "delegate_bind",
    "K2Node_RemoveDelegate": "delegate_unbind",
    "K2Node_CallDelegate": "delegate_call",
    "K2Node_Literal": "literal",
    "K2Node_Knot": "reroute",
    "K2Node_Tunnel": "tunnel",
    "EdGraphNode_Comment": "comment",
}

_GRAPH_KIND_RULES = (
    ("UserConstructionScript", "construction_script"),
    ("MacroGraph", "macro"),
    ("collapsed", "collapsed_graph"),
    ("FunctionGraph", "function"),
    ("EdGraph", "event_graph"),
)


def _graph_kind(graph_name: str, graph_class: str) -> str:
    text = f"{graph_class}.{graph_name}".lower()
    for needle, kind in _GRAPH_KIND_RULES:
        if needle.lower() in text:
            return kind
    return "event_graph"


def _node_name(node) -> str:
    """Semantic node name: member ref > variable/event pin > class (BP-§5)."""
    member = getattr(node, "member_name", None)
    if member:
        return member
    for pin in getattr(node, "pins", None) or []:
        name = getattr(pin, "pin_name", "") or ""
        if name and name.lower() not in {"execute", "then", "self", "inputpin", "outputpin"}:
            return name
    return getattr(node, "node_class", "") or getattr(node, "class_name", "") or "unnamed"


def _direction_str(pin) -> str:
    direction = getattr(pin, "direction", 0)
    if direction in ("EGPD_Input", "EGPD_Output"):
        return "output" if direction == "EGPD_Output" else "input"
    return "output" if direction == 1 else "input"


def _is_exec(pin) -> bool:
    category = getattr(pin, "pin_category", "") or ""
    if not category:
        pin_type_str = str(getattr(pin, "pin_type", "") or "")
        category = pin_type_str.split("(", 1)[0].strip().lower()
    return category.lower() == "exec"


def _linked_guids(pin) -> list[str]:
    linked = getattr(pin, "linked_to", None)
    if isinstance(linked, list) and linked and isinstance(linked[0], str):
        return [g for g in linked if g]
    raw = getattr(pin, "linked_to_raw", None) or []
    return [r.get("pin_guid") for r in raw if isinstance(r, dict) and r.get("pin_guid")]


def _pin_keep(pin, connected: bool) -> bool:
    """BP-§8 keep rule: connected, defaulted, ref/wildcard pins are kept."""
    if connected:
        return True
    if getattr(pin, "orphaned", False) or getattr(pin, "orphaned_pin", False):
        return False
    if getattr(pin, "default_value", "") or getattr(pin, "default_object_name", None) \
            or getattr(pin, "default_text_value", None):
        return True
    if getattr(pin, "is_reference", False):
        return True
    category = (getattr(pin, "pin_category", "") or "").lower()
    return category == "wildcard"


def emit_graphs(graphs, table, reporting, *, mode: str) -> tuple[list[dict], dict]:
    """Emit graphs with nodes/pins/ports.

    Returns (graphs_json, index): index maps pin_guid -> endpoint info for
    flows.py. Deterministic order: graphs and nodes in serialization order;
    duplicate graph names get a numeric suffix.
    """
    graphs_json: list[dict] = []
    index: dict[str, dict] = {}
    graph_slug_counts: dict[str, int] = {}

    def emit(graph) -> None:
        name = getattr(graph, "graph_name", "") or "Graph"
        slug = ascii_slug(name)
        seen = graph_slug_counts.get(slug, 0)
        graph_slug_counts[slug] = seen + 1
        if seen:
            slug = f"{slug}_{seen}"
        gid = graph_id(slug)
        nodes_json: list[dict] = []
        ordinal_counts: dict[tuple[str, str], int] = {}

        for node in getattr(graph, "nodes", None) or []:
            node_json, node_index = _emit_node(node, slug, ordinal_counts, table, reporting, mode)
            if node_json is None:
                continue
            nodes_json.append(node_json)
            index.update(node_index)

        kind = _graph_kind(name, getattr(graph, "graph_class", "") or "")
        if kind == "event_graph" and any(
                _NODE_KIND_MAP.get(getattr(n, "node_class", "") or getattr(n, "class_name", "") or "") == "function_entry"
                for n in getattr(graph, "nodes", None) or []):
            kind = "function"  # evidence-based: graph contains a FunctionEntry node
        entry: dict = {"id": gid, "name": name, "kind": kind, "nodes": nodes_json}
        if mode == "debug":
            entry["evidence"] = {"graph_guid": getattr(graph, "graph_guid", "") or ""}
        graphs_json.append(entry)

        for subgraph in getattr(graph, "subgraphs", None) or []:
            emit(subgraph)

    for graph in graphs:
        emit(graph)
    return graphs_json, index


def _emit_node(node, graph_slug, ordinal_counts, table, reporting, mode):
    node_class = getattr(node, "node_class", "") or getattr(node, "class_name", "") or ""
    kind = _NODE_KIND_MAP.get(node_class)
    status = "recognized"
    if kind is None:
        kind = "custom"
        status = "opaque"
        reporting.diagnostic("BP_NODE_UNRECOGNIZED", f"graph:{graph_id(graph_slug)}/nodes",
                             "warning", "semantic_loss", occurrence={"class": node_class})
    if kind == "comment":
        return None, {}

    raw_name = _node_name(node)
    name_slug = ascii_slug(raw_name)
    key = (kind, name_slug)
    ordinal = ordinal_counts.get(key, 0)
    ordinal_counts[key] = ordinal + 1
    nid = node_id(graph_slug, kind, name_slug, ordinal)

    node_index: dict[str, dict] = {}
    data_pins: dict[str, dict] = {}
    control_ports: dict[str, dict] = {}

    for pin in getattr(node, "pins", None) or []:
        pin_id = getattr(pin, "pin_guid", "") or ""
        direction = _direction_str(pin)
        is_exec = _is_exec(pin)
        pin_name = getattr(pin, "pin_name", "") or ""
        endpoint = exec_endpoint(pin_name) if is_exec else data_endpoint(pin_name, direction)
        linked = _linked_guids(pin)
        if pin_id:
            node_index[pin_id] = {
                "node": nid, "graph": graph_id(graph_slug), "endpoint": endpoint,
                "direction": direction, "is_exec": is_exec,
                "orphaned": bool(getattr(pin, "orphaned", False)
                                 or getattr(pin, "orphaned_pin", False)),
                "not_connectable": bool(getattr(pin, "not_connectable", False)),
                "linked": linked,
            }
        connected = bool(linked)
        if is_exec:
            role = ascii_slug(pin_name).lower().replace("_", "-") or "port"
            control_ports[endpoint] = {"name": pin_name, "direction": direction, "role": role}
        elif _pin_keep(pin, connected):
            dpin: dict = {"name": pin_name, "direction": direction,
                          "type": type_ref_from_pin(table, pin)}
            if getattr(pin, "sub_pin_guids", None):
                dpin["path"] = [ascii_slug(pin_name)]
            if getattr(pin, "parent_pin_guid", ""):
                dpin["split_child"] = True
            data_pins[endpoint] = dpin

    result: dict = {"id": nid, "kind": kind}
    if raw_name != name_slug:
        result["label"] = raw_name
    if status != "recognized":
        result["status"] = status
        result["source_type"] = node_class
    if data_pins:
        result["data_pins"] = data_pins
    if control_ports:
        result["control_ports"] = control_ports
    if mode == "debug":
        result["evidence"] = {"node_guid": getattr(node, "node_guid", "") or "",
                              "source_class": node_class}
    return result, node_index
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintNodeEmission -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/semantic/blueprint/reporting.py src/uasset_read/semantic/blueprint/nodes.py tests/test_blueprint_semantic.py
git commit -m "feat: blueprint graph and node emission with pin/port endpoints (#554)"
```

---

### Task 7: Control flow and data flow

**Files:**
- Create: `src/uasset_read/semantic/blueprint/flows.py`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: `graphs_json` and `index` from `emit_graphs()` (Task 6), `BlueprintReporting`.
- Produces: `attach_flows(graphs_json, index, reporting, mode)` mutating each graph with `control_flow` (`entries`, `edges` with `ordinal`) and `data_flow` (`edges`).

BP-§9/§10 rules: entries are exec outputs of `event`/`custom_event`/`function_entry` nodes; canonical edge emitted from the output side only (LinkedTo is bidirectional — emit once); only output→input; exec never mixes with data; orphaned/not-connectable pins never enter flow; unresolved targets produce `BP_LINK_UNRESOLVED` diagnostics and never guessed edges; execution source order preserved via `ordinal` (index iteration order is deterministic because `emit_graphs` inserts pins in serialization order and Python dicts preserve it).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintFlows:
    def _linked_graph(self):
        from uasset_read.models.ir import GraphIR, NodeIR, PinIR
        out_exec = PinIR(pin_name="then", pin_type="exec", direction="EGPD_Output",
                         default_value=None, pin_guid="e1" + "0" * 30, pin_category="exec",
                         linked_to=["e2" + "0" * 30])
        in_exec = PinIR(pin_name="execute", pin_type="exec", direction="EGPD_Input",
                        default_value=None, pin_guid="e2" + "0" * 30, pin_category="exec",
                        linked_to=["e1" + "0" * 30])
        out_data = PinIR(pin_name="Value", pin_type="int", direction="EGPD_Output",
                         default_value=None, pin_guid="d1" + "0" * 30, pin_category="int",
                         linked_to=["d2" + "0" * 30])
        in_data = PinIR(pin_name="Target", pin_type="int", direction="EGPD_Input",
                        default_value=None, pin_guid="d2" + "0" * 30, pin_category="int",
                        linked_to=["d1" + "0" * 30])
        event = NodeIR(node_guid="n1" + "0" * 30, node_class="K2Node_Event", node_comment=None,
                       pins=[out_exec, out_data], execution_flow=[])
        event.member_name = "ReceiveBeginPlay"
        call = NodeIR(node_guid="n2" + "0" * 30, node_class="K2Node_CallFunction", node_comment=None,
                      pins=[in_exec, in_data], execution_flow=[])
        call.member_name = "SetHealth"
        return [GraphIR(graph_guid="f" * 32, graph_name="EventGraph", graph_class="EdGraph",
                        nodes=[event, call], execution_chains=[])]

    def test_flows_single_canonical_edge(self):
        from uasset_read.semantic.blueprint.nodes import emit_graphs
        from uasset_read.semantic.blueprint.flows import attach_flows
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        rep = BlueprintReporting()
        graphs_json, index = emit_graphs(self._linked_graph(), TypeTable(), rep, mode="standard")
        attach_flows(graphs_json, index, rep, mode="standard")
        flow = graphs_json[0]["control_flow"]
        assert flow["entries"] == [
            {"node": "blueprint://graph/EventGraph/node/event/ReceiveBeginPlay/0",
             "port": "exec.out"}]
        assert len(flow["edges"]) == 1  # bidirectional LinkedTo -> one canonical edge
        edge = flow["edges"][0]
        assert edge["from"] == {"node": "blueprint://graph/EventGraph/node/event/ReceiveBeginPlay/0",
                                "port": "exec.out"}
        assert edge["to"] == {"node": "blueprint://graph/EventGraph/node/call/SetHealth/0",
                              "port": "exec.execute"}
        assert edge["ordinal"] == 0
        data_edges = graphs_json[0]["data_flow"]["edges"]
        assert len(data_edges) == 1
        assert data_edges[0]["from"]["pin"] == "output.Value"
        assert data_edges[0]["to"]["pin"] == "input.Target"

    def test_unresolved_link_diagnosed_not_emitted(self):
        from uasset_read.models.ir import GraphIR, NodeIR, PinIR
        from uasset_read.semantic.blueprint.nodes import emit_graphs
        from uasset_read.semantic.blueprint.flows import attach_flows
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        dangling = PinIR(pin_name="then", pin_type="exec", direction="EGPD_Output",
                         default_value=None, pin_guid="f1" + "0" * 30, pin_category="exec",
                         linked_to=["ff" * 16])
        node = NodeIR(node_guid="n3" + "0" * 30, node_class="K2Node_Event", node_comment=None,
                      pins=[dangling], execution_flow=[])
        graph = GraphIR(graph_guid="e" * 32, graph_name="EventGraph", graph_class="EdGraph",
                        nodes=[node], execution_chains=[])
        rep = BlueprintReporting()
        graphs_json, index = emit_graphs([graph], TypeTable(), rep, mode="standard")
        attach_flows(graphs_json, index, rep, mode="standard")
        assert graphs_json[0]["control_flow"] == {"entries": [
            {"node": graphs_json[0]["nodes"][0]["id"], "port": "exec.out"}]}
        codes = [d["code"] for d in rep.diagnostics_entries("standard")]
        assert "BP_LINK_UNRESOLVED" in codes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintFlows -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement flows.py**

Create `src/uasset_read/semantic/blueprint/flows.py`:

```python
"""Control flow and data flow emission (BP-§9, BP-§10)."""
from __future__ import annotations

_ENTRY_KINDS = {"event", "custom_event", "function_entry"}


def attach_flows(graphs_json: list[dict], index: dict, reporting, *, mode: str) -> None:
    """Attach control_flow/data_flow to each emitted graph, in place.

    Canonical edges are emitted from the output side only (LinkedTo is
    bidirectional). Exec and data edges never mix. Orphaned, not-connectable,
    cross-graph, and unresolved endpoints never produce edges — they produce
    diagnostics (BP-§10: no guessed edges).
    """
    node_graph: dict[str, str] = {}
    for graph in graphs_json:
        for node in graph["nodes"]:
            node_graph[node["id"]] = graph["id"]

    exec_edges: dict[str, list[dict]] = {g["id"]: [] for g in graphs_json}
    data_edges: dict[str, list[dict]] = {g["id"]: [] for g in graphs_json}
    entries: dict[str, list[dict]] = {g["id"]: [] for g in graphs_json}
    seen_edges: set[tuple[str, str]] = set()

    for graph in graphs_json:
        for node in graph["nodes"]:
            if node.get("kind") in _ENTRY_KINDS:
                for endpoint, port in (node.get("control_ports") or {}).items():
                    if port.get("direction") == "output":
                        entries[graph["id"]].append({"node": node["id"], "port": endpoint})

    for pin_id, info in index.items():
        if info["direction"] != "output" or info["orphaned"] or info["not_connectable"]:
            continue
        gid = info["graph"]
        for target_guid in info.get("linked", []):
            edge_key = (pin_id, target_guid)
            if edge_key in seen_edges or (target_guid, pin_id) in seen_edges:
                continue
            seen_edges.add(edge_key)
            target = index.get(target_guid)
            if target is None or target["orphaned"] or target["not_connectable"] \
                    or target["graph"] != gid:
                reporting.diagnostic("BP_LINK_UNRESOLVED", f"graph:{gid}/data_flow",
                                     "warning", "semantic_loss",
                                     occurrence={"pin": pin_id, "target": target_guid})
                continue
            if target["direction"] != "input":
                reporting.diagnostic("BP_LINK_DIRECTION", f"graph:{gid}/data_flow",
                                     "warning", "semantic_loss",
                                     occurrence={"pin": pin_id, "target": target_guid})
                continue
            if info["is_exec"] != target["is_exec"]:
                reporting.diagnostic("BP_LINK_KIND_MISMATCH", f"graph:{gid}/data_flow",
                                     "warning", "semantic_loss",
                                     occurrence={"pin": pin_id, "target": target_guid})
                continue
            endpoint_key = "port" if info["is_exec"] else "pin"
            edge = {"from": {"node": info["node"], endpoint_key: info["endpoint"]},
                    "to": {"node": target["node"], endpoint_key: target["endpoint"]}}
            (exec_edges[gid] if info["is_exec"] else data_edges[gid]).append(edge)

    for graph in graphs_json:
        gid = graph["id"]
        exec_list = exec_edges[gid]
        for ordinal, edge in enumerate(exec_list):
            edge["ordinal"] = ordinal
        control: dict = {"entries": entries[gid]}
        if exec_list:
            control["edges"] = exec_list
        graph["control_flow"] = control
        if data_edges[gid]:
            graph["data_flow"] = {"edges": data_edges[gid]}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintFlows -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/semantic/blueprint/flows.py tests/test_blueprint_semantic.py
git commit -m "feat: blueprint control flow and data flow edges (#554)"
```

---

### Task 8: Default values (BP-§12)

**Files:**
- Create: `src/uasset_read/semantic/blueprint/defaults.py`
- Modify: `src/uasset_read/semantic/blueprint/nodes.py` (wire `defaults` into node output)
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: PinIR default fields (Task 2).
- Produces: `default_value_for(pin, reporting) -> Any` returning scalars inline and wrappers `{"object": str}`, `{"enum": str}`, `{"text": {"raw": str}}`, `{"raw": {"value", "expected"}}`; returns `None` for connected pins / absent defaults.

v1 implements BP-§12 rules 1, 2, 4–8. Rule 3 (`bDefaultValueIsIgnored`) is not parsed by the serializer — report as coverage, never guess. Rule 7: `AutogeneratedDefaultValue` is debug evidence only. `false`/`0`/`""` are preserved by field existence, never truthiness (spec rule 8).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintDefaults:
    def test_scalar_and_object_defaults(self):
        from uasset_read.semantic.blueprint.defaults import default_value_for
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        class Pin:
            def __init__(self, **kw):
                self.pin_category = kw.get("pin_category", "")
                self.default_value = kw.get("default_value", "")
                self.default_object_name = kw.get("default_object_name", None)
                self.default_text_value = kw.get("default_text_value", None)
                self.linked_to = []

        rep = BlueprintReporting()
        assert default_value_for(Pin(pin_category="bool", default_value="true"), rep) is True
        assert default_value_for(Pin(pin_category="int", default_value="0"), rep) == 0
        assert default_value_for(Pin(pin_category="real", default_value="1.5"), rep) == 1.5
        assert default_value_for(Pin(pin_category="string", default_value=""), rep) == ""
        assert default_value_for(Pin(pin_category="object", default_object_name="/Game/X"), rep) == {"object": "/Game/X"}
        assert default_value_for(Pin(pin_category="text", default_text_value="Hello"), rep) == {"text": {"raw": "Hello"}}
        connected = Pin(pin_category="int", default_value="5")
        connected.linked_to = ["aa" * 16]
        assert default_value_for(connected, rep) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintDefaults -v`
Expected: FAIL.

- [ ] **Step 3: Implement defaults.py**

Create `src/uasset_read/semantic/blueprint/defaults.py`:

```python
"""Runtime default value selection (BP-§12).

v1 implements rules 1, 2, 4-8. Rule 3 (bDefaultValueIsIgnored) is not parsed
by the serializer yet — treated as unavailable, never guessed. Rule 7:
AutogeneratedDefaultValue is debug evidence only.
"""
from __future__ import annotations

from typing import Any


def default_value_for(pin, reporting) -> Any:
    """Semantic runtime default for an input data pin, or None."""
    if getattr(pin, "linked_to", None):
        return None
    category = (getattr(pin, "pin_category", "") or "").lower()
    raw = getattr(pin, "default_value", "") or ""

    if category in ("object", "class", "interface", "softobject"):
        obj = getattr(pin, "default_object_name", None)
        if obj:
            return {"object": obj}
        if raw:
            return {"object": raw}
        return None

    if category == "text":
        text = getattr(pin, "default_text_value", None)
        return {"text": {"raw": text}} if text is not None else None

    if raw == "":
        if category in ("string", "name"):
            return ""
        return None

    if category == "bool":
        return raw.strip().lower() == "true"
    if category in ("int", "int8", "int64", "byte", "uint8", "uint16", "uint32", "uint64"):
        try:
            return int(raw)
        except ValueError:
            reporting.diagnostic("BP_DEFAULT_UNRESOLVED", "graphs", "info", "value_loss",
                                 occurrence={"value": raw[:64]})
            return {"raw": {"value": raw[:256], "expected": category}}
    if category in ("real", "float", "double"):
        try:
            return float(raw)
        except ValueError:
            reporting.diagnostic("BP_DEFAULT_UNRESOLVED", "graphs", "info", "value_loss",
                                 occurrence={"value": raw[:64]})
            return {"raw": {"value": raw[:256], "expected": category}}
    if category in ("string", "name"):
        return raw
    if category == "enum":
        return {"enum": raw}
    return _bounded_raw(raw, category or "unknown", reporting)


def _bounded_raw(raw: str, expected: str, reporting) -> dict:
    """BP-§15.5: bounding a large value must be visible, never silent."""
    value = {"value": raw[:256], "expected": expected}
    if len(raw) > 256:
        value["truncated"] = True
        value["original_length"] = len(raw)
        reporting.coverage("graphs", "truncated", reason="bounded_default_value",
                           declared=len(raw), emitted=256, omitted=len(raw) - 256)
        reporting.diagnostic("BP_DEFAULT_TRUNCATED", "graphs", "info", "value_loss")
    return {"raw": value}
```

The int/real `except` branches keep the plain raw wrapper (those are parse failures, not bounding). The struct/container/default fallback path goes through `_bounded_raw` so any truncation produces coverage + diagnostics (BP-§15.5 forbids silent loss).

Wire into `nodes.py::_emit_node` — after `control_ports` is built and before `result` assembly, add (and import `default_value_for` at module top; also import `Any` is already there):

```python
    defaults: dict[str, Any] = {}
    for pin in getattr(node, "pins", None) or []:
        if _is_exec(pin) or _direction_str(pin) != "input":
            continue
        endpoint = data_endpoint(getattr(pin, "pin_name", "") or "", "input")
        if endpoint not in data_pins:
            continue
        value = default_value_for(pin, reporting)
        if value is not None:
            defaults[endpoint] = value
    if defaults:
        result["defaults"] = defaults
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/semantic/blueprint tests/test_blueprint_semantic.py
git commit -m "feat: blueprint pin default value selection (#554)"
```

---

### Task 9: Variables and declaration index

**Files:**
- Create: `src/uasset_read/semantic/blueprint/variables.py`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: `PackageIR.variables` (`VariableIR`: `name`, `type`, `default_value`, `guid`, `category`, `property_flags`, `replication_condition`, `rep_notify_func`, `flags_labels`, `is_replicated`, ...), `BlueprintIR` (`parent_class`, `interfaces`, `functions`).
- Produces: `emit_variables(variables, table, reporting) -> list[dict]` (always registers `variables` coverage `partial`, reason `cdo_and_inheritance_not_resolved`); `emit_declaration(variable_names, component_ids, functions, parent_class, interfaces) -> dict` (index only — no duplicated facts).

BP-§13/#551-P0 rules: flags emitted only when `flags_labels` present (source complete); missing + non-complete source must not mean false. RepNotify emitted only when both the flag and a function name exist. `FBPVariableDescription.DefaultValue == ""` is not a confirmed empty string — omit.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintVariables:
    def _variable(self):
        from uasset_read.models.ir import VariableIR
        return VariableIR(name="Health", type="float", default_value="100.0",
                          guid="ab" * 16, property_flags=0,
                          flags_labels=["EditAnywhere", "BlueprintVisible", "RepNotify"],
                          is_replicated=True, replication_condition=0,
                          rep_notify_func="OnRep_Health")

    def test_variable_emission(self):
        from uasset_read.semantic.blueprint.variables import emit_variables
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        rep = BlueprintReporting()
        variables_json = emit_variables([self._variable()], TypeTable(), rep)
        var = variables_json[0]
        assert var["name"] == "Health"
        assert var["type"] == "float"
        assert var["default"] == 100.0
        assert var["flags"] == ["BlueprintVisible", "EditAnywhere", "RepNotify"]
        assert var["identity"] == "ab" * 16
        assert var["replication"] == {"condition": "always", "notify": "OnRep_Health"}
        assert [e["scope"] for e in rep.coverage_entries()] == ["variables"]

    def test_empty_default_not_confirmed(self):
        from uasset_read.models.ir import VariableIR
        from uasset_read.semantic.blueprint.variables import emit_variables
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        var = VariableIR(name="Note", type="string", default_value="")
        emitted = emit_variables([var], TypeTable(), BlueprintReporting())
        assert "default" not in emitted[0]

    def test_declaration_index_references_only(self):
        from uasset_read.semantic.blueprint.variables import emit_declaration
        decl = emit_declaration(variable_names=["Health"], component_ids=["c0"],
                                functions=[{"name": "TakeDamage", "graph": None}],
                                parent_class="/Script/Engine.Character",
                                interfaces=["/Game/IF_Damageable"])
        assert decl["parent_class"] == "/Script/Engine.Character"
        assert decl["variables"] == ["Health"]
        assert decl["components"] == ["c0"]
        assert decl["functions"] == [{"name": "TakeDamage"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintVariables -v`
Expected: FAIL.

- [ ] **Step 3: Implement variables.py**

Create `src/uasset_read/semantic/blueprint/variables.py`:

```python
"""Variables and declaration index (BP-§13, #551 P0 declaration layer)."""
from __future__ import annotations

from typing import Any

_REPLICATION_CONDITIONS = {
    0: "always", 1: "initial_only", 2: "initial_or_ongoing", 3: "owner_only",
}

_PRIMITIVES = {"bool", "int", "int64", "float", "double", "string", "name",
               "text", "byte", "object", "vector", "rotator", "transform"}


def emit_variables(variables, table, reporting) -> list[dict]:
    """Emit the ``variables`` array from VariableIR facts."""
    out: list[dict] = []
    for var in variables or []:
        if getattr(var, "kind", "user") in ("metadata", "input_action"):
            continue  # internal engine entries are not Blueprint variables (BP-§13)
        entry: dict[str, Any] = {"name": getattr(var, "name", "") or ""}
        var_type = (getattr(var, "type", "") or "").strip()
        entry["type"] = _type_for(var_type, table)
        default = getattr(var, "default_value", None)
        if default not in (None, ""):
            entry["default"] = _coerce_default(var_type, default)
        flags = sorted(getattr(var, "flags_labels", None) or [])
        if flags:
            entry["flags"] = flags
        guid = getattr(var, "guid", None)
        if guid:
            entry["identity"] = guid
        category = getattr(var, "category", "") or ""
        if category and category != "Default":
            entry["category"] = category
        replication: dict[str, Any] = {}
        if getattr(var, "is_replicated", False):
            replication["condition"] = _REPLICATION_CONDITIONS.get(
                getattr(var, "replication_condition", 0), "unknown")
            notify = getattr(var, "rep_notify_func", "") or ""
            if notify and "RepNotify" in flags:
                replication["notify"] = notify
        if replication:
            entry["replication"] = replication
        out.append(entry)

    reporting.coverage("variables", "partial", reason="cdo_and_inheritance_not_resolved")
    return out


def emit_declaration(variable_names, component_ids, functions, parent_class, interfaces) -> dict:
    """Declaration index — references only, no duplicated facts (#551 P0)."""
    decl: dict[str, Any] = {}
    if parent_class:
        decl["parent_class"] = parent_class
    if interfaces:
        decl["interfaces"] = sorted(interfaces)
    func_entries = []
    for fn in functions or []:
        item: dict[str, Any] = {"name": fn.get("name", "")}
        if fn.get("graph"):
            item["graph"] = fn["graph"]
        func_entries.append(item)
    if func_entries:
        decl["functions"] = func_entries
    if variable_names:
        decl["variables"] = sorted(variable_names)
    if component_ids:
        decl["components"] = sorted(component_ids)
    return decl


def _type_for(type_str: str, table) -> Any:
    lowered = type_str.lower()
    if lowered in _PRIMITIVES:
        return lowered
    if not type_str:
        return "unknown"
    return table.type_ref_for(category="unknown", subcategory=type_str)


def _coerce_default(type_str: str, raw: Any) -> Any:
    lowered = (type_str or "").lower()
    if not isinstance(raw, str):
        return raw
    if lowered == "bool":
        return raw.strip().lower() == "true"
    if lowered in ("int", "int64", "byte"):
        try:
            return int(raw)
        except ValueError:
            return raw
    if lowered in ("float", "double"):
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintVariables -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/semantic/blueprint/variables.py tests/test_blueprint_semantic.py
git commit -m "feat: blueprint variables and declaration index (#554)"
```

---

### Task 10: Components

**Files:**
- Create: `src/uasset_read/semantic/blueprint/components.py`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: `BlueprintIR.components` (list of dicts from the existing `extract_components` machinery).
- Produces: `emit_components(source_components, table, reporting) -> list[dict]` (`id: c<N>`, `name`, `type` TypeRef, `origin`, optional `parent`/`socket`/`transform`); registers `components` coverage `partial` (origin provenance not fully verified in v1); `BP_COMPONENT_PARENT_UNRESOLVED` diagnostic for dangling parents.

BP-§14 rules: parent refs must close; no name-guessing; origin only from explicit evidence keys. Step 1 pins the actual dict keys from a real sample before coding — adapt the key names in the implementation to what the probe shows (the mapping below assumes `name`/`class`/`parent`/`socket` style keys; if the probe shows different names, update the implementation AND the unit test's source dicts accordingly — both directions are wrong guesses until probed).

- [ ] **Step 1: Probe component dict shape**

Run (after Task 2 enrichment; from repo root):

```powershell
python -c "from uasset_read.parse_uasset import parse_uasset; from uasset_read.ir_builder import build_package_ir; r = parse_uasset('tests/samples/FirstPerson_BP_FirstPersonCharacter.uasset', tolerant=True); pkg = build_package_ir(r); import json; comps = pkg.blueprint.components if pkg.blueprint else []; print(len(comps)); print(json.dumps(comps[:2], default=str, indent=1))"
```

Record the actual keys; adjust `emit_components` field access to them.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintComponents:
    def test_component_emission_and_parent_resolution(self):
        from uasset_read.semantic.blueprint.components import emit_components
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        source = [
            {"name": "CollisionCylinder", "class": "CapsuleComponent"},
            {"name": "Mesh", "class": "SkeletalMeshComponent",
             "parent": "CollisionCylinder", "socket": "WeaponSocket"},
        ]
        rep = BlueprintReporting()
        comps = emit_components(source, TypeTable(), rep)
        assert comps[0]["id"] == "c0"
        assert comps[0]["origin"] == "unverified"
        assert comps[0]["type"] == {"$type": "t0"}
        assert comps[1]["parent"] == "c0"
        assert comps[1]["socket"] == "WeaponSocket"
        assert [e["scope"] for e in rep.coverage_entries()] == ["components"]

    def test_dangling_parent_diagnosed(self):
        from uasset_read.semantic.blueprint.components import emit_components
        from uasset_read.semantic.blueprint.types import TypeTable
        from uasset_read.semantic.blueprint.reporting import BlueprintReporting

        rep = BlueprintReporting()
        comps = emit_components([{"name": "Mesh", "class": "X", "parent": "Nope"}],
                                TypeTable(), rep)
        assert "parent" not in comps[0]
        assert any(d["code"] == "BP_COMPONENT_PARENT_UNRESOLVED"
                   for d in rep.diagnostics_entries("standard"))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintComponents -v`
Expected: FAIL.

- [ ] **Step 4: Implement components.py**

Create `src/uasset_read/semantic/blueprint/components.py`:

```python
"""Components emission (BP-§14).

v1 provenance scope: origin is scs_owned/scs_inherited/native only when an
explicit evidence key is present in the source dict; otherwise 'unverified'
with partial coverage. Parent/socket come from the source dict only.
"""
from __future__ import annotations

from typing import Any


def emit_components(source_components, table, reporting) -> list[dict]:
    by_name: dict[str, int] = {}
    pending_parent: list[tuple[dict, str, int]] = []
    out: list[dict] = []
    for idx, comp in enumerate(source_components or []):
        name = str(comp.get("name") or f"Component{idx}")
        entry: dict[str, Any] = {"id": f"c{len(out)}", "name": name}
        cls = comp.get("class") or comp.get("component_class") or ""
        if cls:
            entry["type"] = table.type_ref_for(category="class", subcategory_object_name=str(cls))
        entry["origin"] = _origin(comp)
        socket = comp.get("socket") or comp.get("attach_socket_name")
        if socket:
            entry["socket"] = str(socket)
        transform = comp.get("transform")
        if isinstance(transform, dict) and transform:
            entry["transform"] = transform
        parent_name = comp.get("parent") or comp.get("attach_parent")
        by_name[name] = len(out)
        if parent_name:
            pending_parent.append((entry, str(parent_name), len(out)))
        out.append(entry)

    for entry, parent_name, self_idx in pending_parent:
        parent_idx = by_name.get(parent_name)
        if parent_idx is not None and parent_idx != self_idx:
            entry["parent"] = f"c{parent_idx}"
        else:
            reporting.diagnostic("BP_COMPONENT_PARENT_UNRESOLVED", "components",
                                 "warning", "semantic_loss",
                                 occurrence={"component": entry["name"], "parent": parent_name})

    if out:
        reporting.coverage("components", "partial", reason="scs_origin_not_fully_verified")
    return out


def _origin(comp: dict) -> str:
    if comp.get("scs_node") or comp.get("from_scs"):
        return "scs_owned"
    if comp.get("inherited_override"):
        return "scs_inherited"
    if comp.get("native"):
        return "native"
    return "unverified"
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintComponents -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/semantic/blueprint/components.py tests/test_blueprint_semantic.py
git commit -m "feat: blueprint components emission with origin and parent closure (#554)"
```

---

### Task 11: Orchestrator extractor + end-to-end Blueprint document

**Files:**
- Create: `src/uasset_read/semantic/blueprint/extractor.py`
- Modify: `src/uasset_read/semantic/blueprint/__init__.py`
- Modify: `src/uasset_read/semantic/__init__.py` (registration side effect)
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: all `semantic/blueprint` modules (Tasks 4–10), the #551 pipeline after Task 3.
- Produces: `build_blueprint_content(package_ir, export_ir, coverage_model, evidence_list) -> dict` registered for `Blueprint` and `BlueprintGeneratedClass` with `domain_format="uasset_read.blueprint_semantic"`, `domain_format_version="1.0.0"`; `parse_single(..., format="json")` on a Blueprint asset emits the blueprint_semantic document.

The orchestrator collects graphs from all exports (graphs live on nested/BPGC exports, not necessarily on the primary), deduplicated by `graph_guid` in deterministic export order. `asset_type`/`status` stay builder-owned; the extractor also extends the IR `asset` fields via content — but `asset` is an envelope key and collision-guarded. Therefore the extended blueprint asset identity (`kind`, `generated_class`, `parent_class`) is emitted under `declaration.asset` instead.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintEndToEnd:
    def test_firstperson_character_blueprint_document(self):
        from uasset_read.core import parse_single

        output = parse_single(str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset")),
                              format="json", output_level="standard")
        doc = json.loads(output)
        assert doc["format"] == "uasset_read.blueprint_semantic"
        assert doc["format_version"] == "1.0.0"
        assert doc["mode"] == "standard"
        assert doc["asset_type"] == "blueprint"
        assert doc["status"]["parse"] != "failed"
        assert doc["status"]["representation"] in ("full", "partial")
        assert doc["asset"]["package"]
        graphs = doc["graphs"]
        assert len(graphs) >= 1
        total_nodes = sum(len(g["nodes"]) for g in graphs)
        total_edges = sum(len(g.get("control_flow", {}).get("edges", []))
                          + len(g.get("data_flow", {}).get("edges", [])) for g in graphs)
        assert total_nodes > 20
        assert total_edges > 10
        assert any(g["control_flow"].get("entries") for g in graphs)
        assert "references" not in doc
        assert "evidence" not in doc

    def test_debug_projection_equals_standard(self):
        from uasset_read.semantic.builder import build_semantic_ir
        from uasset_read.semantic.projection import project_semantic
        from uasset_read.semantic.render import render_semantic_json
        from uasset_read.parse_uasset import parse_uasset_with_linker
        from uasset_read.ir_builder import build_package_ir

        sample = str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset"))
        result = parse_uasset_with_linker(sample, tolerant=True)
        pkg = build_package_ir(result)
        standard = project_semantic(build_semantic_ir(pkg, source_path=sample), "standard")
        debug_ir = project_semantic(build_semantic_ir(pkg, source_path=sample), "debug")
        assert '"evidence"' in render_semantic_json(debug_ir)
        projected = project_semantic(debug_ir, "standard")
        assert render_semantic_json(projected) == render_semantic_json(standard)
```

The debug document carries nested `evidence` objects, not top-level `evidence` — the test asserts on the rendered string, which is the projection invariant that matters (BP-§3).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintEndToEnd -v`
Expected: FAIL (Blueprint still opaque — no extractor registered).

- [ ] **Step 3: Implement extractor.py**

Create `src/uasset_read/semantic/blueprint/extractor.py`:

```python
"""Blueprint semantic content orchestrator (#554)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.blueprint.components import emit_components
from uasset_read.semantic.blueprint.flows import attach_flows
from uasset_read.semantic.blueprint.nodes import emit_graphs
from uasset_read.semantic.blueprint.reporting import BlueprintReporting
from uasset_read.semantic.blueprint.types import TypeTable
from uasset_read.semantic.blueprint.variables import emit_variables, emit_declaration

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def build_blueprint_content(package_ir: "PackageIR", export_ir: "ExportIR",
                            coverage_model, evidence_list) -> dict:
    """Build the Blueprint domain content dict (BP-§4 top-level shape)."""
    reporting = BlueprintReporting()
    table = TypeTable()

    # Content is built ONCE with evidence included (BP-§3: parse once, mode
    # only affects evidence rendering). project_semantic strips `evidence`
    # keys recursively for standard; diagnostics occurrences live under
    # `evidence` too, so both modes derive from this single build.
    graphs = _collect_graphs(package_ir)
    if not graphs:
        reporting.coverage("graphs", "unavailable", reason="no_graph_exports")
        reporting.diagnostic("BP_GRAPH_MISSING", "asset", "warning", "semantic_loss")

    graphs_json, index = emit_graphs(graphs, table, reporting, mode="debug")
    attach_flows(graphs_json, index, reporting, mode="debug")

    variables_json = emit_variables(getattr(package_ir, "variables", None) or [], table, reporting)
    blueprint = getattr(package_ir, "blueprint", None)
    components_json = emit_components(getattr(blueprint, "components", None) or [], table, reporting)

    declaration = emit_declaration(
        variable_names=[v["name"] for v in variables_json],
        component_ids=[c["id"] for c in components_json],
        functions=_function_index(blueprint, graphs_json),
        parent_class=getattr(blueprint, "parent_class", None) or "",
        interfaces=[i.get("name", "") for i in getattr(blueprint, "interfaces", None) or []
                    if isinstance(i, dict) and i.get("name")],
    )
    declaration.update(_asset_identity(package_ir, export_ir, blueprint))

    content: dict = {
        "references": [],  # blueprint format omits the raw import/export table
        "graphs": graphs_json,
    }
    if table.entries:
        content["types"] = table.entries
    if variables_json:
        content["variables"] = variables_json
    if components_json:
        content["components"] = components_json
    if declaration:
        content["declaration"] = declaration

    coverage_entries = reporting.coverage_entries()
    if coverage_entries:
        content["coverage"] = coverage_entries
    diagnostics = reporting.diagnostics_entries("debug")
    if diagnostics:
        content["diagnostics"] = diagnostics
    return content


def _asset_identity(package_ir, export_ir, blueprint) -> dict:
    """Blueprint-specific asset identity under declaration.asset."""
    identity: dict = {"kind": "blueprint"}
    parent = getattr(blueprint, "parent_class", None) or ""
    if parent:
        identity["parent_class"] = parent
    header = package_ir.header
    if getattr(header, "saved_by_engine_version", ""):
        identity["saved_by_engine"] = header.saved_by_engine_version
    return {"asset": identity}


def _collect_graphs(package_ir) -> list:
    """All GraphIR objects across exports, deduplicated by graph_guid, in
    deterministic export order."""
    seen: set[str] = set()
    graphs = []
    for export in package_ir.exports:
        for graph in getattr(export, "graphs", None) or []:
            guid = getattr(graph, "graph_guid", "") or \
                f"{len(graphs)}:{getattr(graph, 'graph_name', '')}"
            if guid in seen:
                continue
            seen.add(guid)
            graphs.append(graph)
    return graphs


def _function_index(blueprint, graphs_json) -> list[dict]:
    """Function declarations joined to implementation graphs by name."""
    graph_by_name = {g["name"]: g["id"] for g in graphs_json}
    functions = []
    for fn in getattr(blueprint, "functions", None) or []:
        name = getattr(fn, "name", "") or ""
        if not name:
            continue
        functions.append({"name": name, "graph": graph_by_name.get(name)})
    return functions
```

Update `src/uasset_read/semantic/blueprint/__init__.py`:

```python
"""Blueprint semantic JSON domain (#554)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.blueprint.extractor import build_blueprint_content

register_extension(
    "Blueprint",
    build_blueprint_content,
    domain_format="uasset_read.blueprint_semantic",
    domain_format_version="1.0.0",
)
register_extension(
    "BlueprintGeneratedClass",
    build_blueprint_content,
    domain_format="uasset_read.blueprint_semantic",
    domain_format_version="1.0.0",
)
```

Append to `src/uasset_read/semantic/__init__.py`:

```python
import uasset_read.semantic.blueprint  # noqa: F401  (registers #554 extractors)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py -v`
Expected: PASS. If `status.representation` is `opaque` despite the extractor, inspect gating in `build_semantic_ir` (extractor lookup must hit for the primary export class; the primary of a Blueprint asset is usually the `Blueprint` export) and fix there.

- [ ] **Step 5: Update the sample-consistency contract tests**

`tests/core/test_schema_consistency.py` pins the #551 single-format contract; Blueprint samples now legitimately use the domain format. One-shot replacement: update the tests to the new contract (no dual-format compatibility code in product).

Replace the body of `test_all_samples_have_references_and_diagnostics`'s loop with:

```python
    for sample in samples:
        output = parse_single(str(sample), format="json", tolerant=True)
        data = json.loads(output)
        if data.get("format") == "uasset_read.blueprint_semantic":
            # Blueprint format omits the raw references table by design;
            # opaque output must still carry diagnostics.
            if data["status"]["representation"] == "opaque":
                assert data.get("diagnostics"), f"{sample.name}: opaque without diagnostics"
            continue
        assert "references" in data, f"{sample.name}: missing references"
        assert "diagnostics" in data, f"{sample.name}: missing diagnostics"
        assert isinstance(data["references"], list), f"{sample.name}: references not list"
        assert isinstance(data["diagnostics"], list), f"{sample.name}: diagnostics not list"
```

Replace the last two assertions of `test_all_samples_have_format` with:

```python
        _FORMAT_VERSIONS = {
            "uasset_read.asset_semantic": "1.0",
            "uasset_read.blueprint_semantic": "1.0.0",
        }
        assert data["format"] in _FORMAT_VERSIONS, f"{sample.name}: wrong format"
        assert data["format_version"] == _FORMAT_VERSIONS[data["format"]], \
            f"{sample.name}: wrong format_version"
```

Two more sample-loop tests validate every sample against the common schema and must route Blueprint documents to the Blueprint schema instead:

In `tests/core/test_json_schema_contract.py`, replace the loop body of `test_all_standard_and_debug_sample_outputs_validate_against_schema`:

```python
    from uasset_read.schema_loader import load_blueprint_semantic_schema
    blueprint_schema = load_blueprint_semantic_schema()

    for sample in sorted(SAMPLES_DIR.glob("*.uasset")):
        for output_level in ("standard", "debug"):
            data = _parse_sample(sample.name, output_level)
            if data.get("format") == "uasset_read.blueprint_semantic":
                jsonschema.validate(data, blueprint_schema)
            else:
                jsonschema.validate(data, schema)
```

In `tests/core/test_json_output_levels.py::test_graphs_use_nodes_only_and_validate`, replace `jsonschema.validate(data, SCHEMA)` with:

```python
    if data.get("format") == "uasset_read.blueprint_semantic":
        from uasset_read.schema_loader import load_blueprint_semantic_schema
        jsonschema.validate(data, load_blueprint_semantic_schema())
        assert data.get("graphs"), "blueprint document must carry graphs"
    else:
        jsonschema.validate(data, SCHEMA)
```

(These test files are owned by the #551 contract; per the one-shot replacement rule they follow the format change rather than the format preserving legacy assertions.)

Two `tests/test_semantic.py` tests also pin the pre-#554 behavior:

- `TestRealAssetSmoke::test_bp_firstperson_parses_without_crash` — replace `assert data["format"] == "uasset_read.asset_semantic"` with:

```python
          assert data["format"] in ("uasset_read.asset_semantic",
                                    "uasset_read.blueprint_semantic")
```

- `TestOpaqueFallback::test_unregistered_asset_is_opaque` — the test's `BlueprintGeneratedClass` export is now registered. Change the fixture to `object_class="AnimBlueprintGeneratedClass"` (known type `anim_blueprint`, no extractor until #555); the NO_EXTRACTOR/opaque assertions stay unchanged.

- [ ] **Step 6: Run the full suite for regressions**

Run: `python -m pytest -q`
Expected: PASS (non-Blueprint assets still emit `asset_semantic`).

- [ ] **Step 7: Commit**

```powershell
git add src/uasset_read/semantic tests/test_blueprint_semantic.py tests/test_semantic.py tests/core/test_schema_consistency.py tests/core/test_json_schema_contract.py tests/core/test_json_output_levels.py
git commit -m "feat: blueprint semantic extractor with graphs, variables, components, declaration (#554)"
```

---

### Task 12: Semantic validator for the Blueprint format

**Files:**
- Modify: `src/uasset_read/semantic/validator.py`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: Task 3's `register_domain_validator`; blueprint content shape from Tasks 6–11.
- Produces: `validate_blueprint_document(ir) -> list[str]` registered for `uasset_read.blueprint_semantic`, enforcing BP-§18: ID format regexes, graph/node ID uniqueness, flow endpoint closure, data/exec edge endpoint existence, type `$type` closure, component parent closure + acyclicity, function graphs single `function_entry`, opaque-requires-diagnostics, standard-mode evidence ban.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintValidator:
    def _ir(self, content):
        from uasset_read.semantic.models import SemanticIR, AssetMeta, AssetStatus
        return SemanticIR(
            format="uasset_read.blueprint_semantic", format_version="1.0.0",
            mode="standard", asset_type="blueprint",
            asset=AssetMeta(package="/Game/BP_X", name="BP_X"),
            status=AssetStatus(parse="complete", representation="partial"),
            content=content)

    def test_valid_document_passes(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {
            "graphs": [{
                "id": "blueprint://graph/EventGraph", "name": "EventGraph",
                "kind": "event_graph",
                "nodes": [{
                    "id": "blueprint://graph/EventGraph/node/event/BeginPlay/0",
                    "kind": "event",
                    "control_ports": {"exec.out": {"name": "then", "direction": "output", "role": "then"}},
                }],
                "control_flow": {"entries": [
                    {"node": "blueprint://graph/EventGraph/node/event/BeginPlay/0", "port": "exec.out"}]},
            }],
            "diagnostics": [{"code": "BP_GRAPH_MISSING", "scope": "asset",
                             "severity": "warning", "effect": "semantic_loss", "count": 1}],
        }
        assert validate_semantic_document(self._ir(content)) == []

    def test_dangling_flow_endpoint_rejected(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {
            "graphs": [{
                "id": "blueprint://graph/EventGraph", "name": "EventGraph",
                "kind": "event_graph", "nodes": [],
                "control_flow": {"entries": [
                    {"node": "blueprint://graph/EventGraph/node/event/BeginPlay/0", "port": "exec.out"}]},
            }],
        }
        errors = validate_semantic_document(self._ir(content))
        assert any("closure" in e.lower() for e in errors)

    def test_type_closure_violation_rejected(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {"types": {"t0": {"kind": "array", "element": {"$type": "t9"}}}, "graphs": []}
        errors = validate_semantic_document(self._ir(content))
        assert any("type" in e.lower() for e in errors)

    def test_component_cycle_rejected(self):
        from uasset_read.semantic.validator import validate_semantic_document
        content = {
            "graphs": [],
            "components": [
                {"id": "c0", "name": "A", "origin": "unverified", "parent": "c1"},
                {"id": "c1", "name": "B", "origin": "unverified", "parent": "c0"},
            ],
        }
        errors = validate_semantic_document(self._ir(content))
        assert any("cycle" in e.lower() for e in errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintValidator -v`
Expected: FAIL.

- [ ] **Step 3: Implement validate_blueprint_document**

Append to `src/uasset_read/semantic/validator.py` (after `validate_semantic_document`; add `import re as _re` to the module's top import block — ruff rejects in-body imports):

```python
_GRAPH_ID_FULL = _re.compile(r"^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*$")
_NODE_ID_FULL = _re.compile(
    r"^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*/node/[a-z][a-z0-9-]*/[A-Za-z][A-Za-z0-9_.-]*/[0-9]+$")
_ENDPOINT_FULL = _re.compile(r"^(input|output|exec)\.[A-Za-z][A-Za-z0-9_.-]*$")


def _validate_type_refs(value, known: set, errors: list, ctx: str) -> None:
    if isinstance(value, dict):
        if "$type" in value and value["$type"] not in known:
            errors.append(f"Type closure violation at {ctx}: unknown '{value['$type']}'")
        for v in value.values():
            _validate_type_refs(v, known, errors, ctx)
    elif isinstance(value, list):
        for item in value:
            _validate_type_refs(item, known, errors, ctx)


def validate_blueprint_document(ir) -> list[str]:
    """BP-§18 semantic rules for uasset_read.blueprint_semantic content."""
    errors: list[str] = []
    content = ir.content or {}
    graphs = content.get("graphs", []) or []
    types = content.get("types", {}) or {}

    graph_ids: set[str] = set()
    node_ids: set[str] = set()
    endpoints: set[tuple[str, str, str]] = set()  # (graph_id, node_id, endpoint)
    for graph in graphs:
        gid = graph.get("id", "")
        if not _GRAPH_ID_FULL.match(gid):
            errors.append(f"Invalid graph id format: '{gid}'")
        if gid in graph_ids:
            errors.append(f"Duplicate graph id: '{gid}'")
        graph_ids.add(gid)
        entry_nodes = [n for n in graph.get("nodes", []) or [] if n.get("kind") == "function_entry"]
        if len(entry_nodes) > 1:
            errors.append(f"Function graph '{gid}' has {len(entry_nodes)} entry nodes")
        for node in graph.get("nodes", []) or []:
            nid = node.get("id", "")
            if not _NODE_ID_FULL.match(nid):
                errors.append(f"Invalid node id format: '{nid}'")
            if nid in node_ids:
                errors.append(f"Duplicate node id: '{nid}'")
            node_ids.add(nid)
            for endpoint in list(node.get("data_pins", {}) or {}) + list(node.get("control_ports", {}) or {}):
                if not _ENDPOINT_FULL.match(endpoint):
                    errors.append(f"Invalid endpoint id format: '{endpoint}' on node '{nid}'")
                endpoints.add((gid, nid, endpoint))

    for section, key in (("control_flow", "port"), ("data_flow", "pin")):
        for graph in graphs:
            gid = graph.get("id", "")
            flow = graph.get(section, {}) or {}
            for entry in flow.get("entries", []) or []:
                if (gid, entry.get("node", ""), entry.get(key, "")) not in endpoints:
                    errors.append(f"Endpoint closure violation: {section} entry {entry} in '{gid}'")
            for edge in flow.get("edges", []) or []:
                for side in ("from", "to"):
                    ref = edge.get(side, {}) or {}
                    if (gid, ref.get("node", ""), ref.get(key, "")) not in endpoints:
                        errors.append(f"Endpoint closure violation: {section} edge {side} in '{gid}'")

    _validate_type_refs(content, set(types.keys()), errors, "content")

    component_ids = {c.get("id") for c in content.get("components", []) or []}
    parent_of: dict[str, str] = {}
    for comp in content.get("components", []) or []:
        parent = comp.get("parent")
        if parent is not None:
            if parent not in component_ids:
                errors.append(f"Component parent closure violation: '{comp.get('id')}' -> '{parent}'")
            parent_of[comp.get("id")] = parent
    for start in parent_of:
        seen: set[str] = set()
        cur = start
        while cur in parent_of:
            if cur in seen:
                errors.append(f"Component hierarchy cycle at '{start}'")
                break
            seen.add(cur)
            cur = parent_of[cur]

    if ir.status.representation == "opaque" and not content.get("diagnostics"):
        errors.append("Opaque blueprint representation must have at least one diagnostic")
    if ir.mode == "standard":
        def _has_evidence(value) -> bool:
            if isinstance(value, dict):
                return "evidence" in value or any(_has_evidence(v) for v in value.values())
            if isinstance(value, list):
                return any(_has_evidence(v) for v in value)
            return False
        if _has_evidence(content):
            errors.append("Standard blueprint content must not contain evidence")

    return errors


register_domain_validator("uasset_read.blueprint_semantic", validate_blueprint_document)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py tests/test_semantic.py -v`
Expected: PASS. Also run `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintEndToEnd` — real outputs must now also satisfy the validator (the core pipeline runs it before rendering).

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/semantic/validator.py tests/test_blueprint_semantic.py
git commit -m "feat: blueprint semantic validator rules (#554)"
```

---

### Task 13: Draft 2020-12 JSON Schema + packaging + projection hardening

**Files:**
- Create: `src/uasset_read/schemas/blueprint_semantic.schema.json`
- Modify: `src/uasset_read/schema_loader.py`
- Modify: `src/uasset_read/semantic/projection.py`
- Test: `tests/test_blueprint_semantic.py`

**Interfaces:**
- Consumes: rendered blueprint documents (Tasks 11–12).
- Produces: `load_blueprint_semantic_schema() -> dict`; wheel-packaged schema (existing `package-data` glob covers it); `project_semantic` also strips debug-only `extensions`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintSchema:
    def test_schema_loads_and_validates_real_samples(self):
        import jsonschema
        from uasset_read.schema_loader import load_blueprint_semantic_schema
        from uasset_read.core import parse_single

        schema = load_blueprint_semantic_schema()
        for name in ("FirstPerson_BP_FirstPersonCharacter.uasset",
                     "FirstPerson_BP_FirstPersonGameMode.uasset",
                     "StackOBot_BP_Drone.uasset",
                     "IntroToUnreal_BP_Light.uasset",
                     "IntroToUnreal_BP_SaveData.uasset"):
            for level in ("standard", "debug"):
                doc = json.loads(parse_single(str(_sample(name)), format="json", output_level=level))
                if doc.get("format") == "uasset_read.blueprint_semantic":
                    jsonschema.validate(doc, schema)

    def test_schema_rejects_bad_mode(self):
        import jsonschema
        from jsonschema import ValidationError
        from uasset_read.schema_loader import load_blueprint_semantic_schema
        schema = load_blueprint_semantic_schema()
        doc = {"format": "uasset_read.blueprint_semantic", "format_version": "1.0.0",
               "mode": "compact", "asset_type": "blueprint",
               "asset": {"package": "/Game/X", "name": "X"},
               "status": {"parse": "complete", "representation": "partial"},
               "graphs": []}
        with pytest.raises(ValidationError):
            jsonschema.validate(doc, schema)

    def test_projection_strips_extensions(self):
        from uasset_read.semantic.projection import _recursive_strip_evidence
        assert _recursive_strip_evidence({"a": 1, "evidence": {}, "extensions": {"x": 1}}) == {"a": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintSchema -v`
Expected: FAIL.

- [ ] **Step 3: Create the schema**

Create `src/uasset_read/schemas/blueprint_semantic.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/soatori/uasset_read/schemas/blueprint_semantic.schema.json",
  "title": "UAsset Read Blueprint Semantic JSON",
  "type": "object",
  "required": ["format", "format_version", "mode", "asset_type", "asset", "status", "graphs"],
  "properties": {
    "format": {"type": "string", "const": "uasset_read.blueprint_semantic"},
    "format_version": {"type": "string", "const": "1.0.0"},
    "mode": {"type": "string", "enum": ["standard", "debug"]},
    "asset_type": {"type": "string", "const": "blueprint"},
    "asset": {"$ref": "#/$defs/BlueprintAsset"},
    "status": {"$ref": "#/$defs/AssetStatus"},
    "types": {"type": "object", "additionalProperties": {"$ref": "#/$defs/TypeEntry"}},
    "symbols": {"type": "object"},
    "constants": {"type": "object"},
    "variables": {"type": "array", "items": {"type": "object", "required": ["name"]}},
    "components": {"type": "array", "items": {"$ref": "#/$defs/Component"}},
    "declaration": {"type": "object"},
    "graphs": {"type": "array", "items": {"$ref": "#/$defs/Graph"}},
    "coverage": {"type": "array", "items": {"$ref": "#/$defs/CoverageEntry"}},
    "diagnostics": {"type": "array", "items": {"$ref": "#/$defs/BlueprintDiagnostic"}},
    "evidence": {"type": "array", "items": {"$ref": "#/$defs/EvidenceEntry"}},
    "extensions": {"type": "object"}
  },
  "allOf": [
    {
      "if": {"properties": {"mode": {"const": "standard"}}},
      "then": {"properties": {"evidence": {"type": "array", "maxItems": 0},
                              "extensions": {"maxProperties": 0}}}
    }
  ],
  "$defs": {
    "BlueprintAsset": {
      "type": "object",
      "required": ["package", "name"],
      "properties": {
        "package": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "kind": {"type": "string"},
        "generated_class": {"type": "string"}
      },
      "additionalProperties": false
    },
    "AssetStatus": {
      "type": "object",
      "required": ["parse", "representation"],
      "properties": {
        "parse": {"type": "string", "enum": ["complete", "partial", "failed"]},
        "representation": {"type": "string", "enum": ["full", "partial", "opaque"]}
      },
      "additionalProperties": false
    },
    "Graph": {
      "type": "object",
      "required": ["id", "name", "kind", "nodes"],
      "properties": {
        "id": {"type": "string", "pattern": "^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*$"},
        "name": {"type": "string"},
        "kind": {"type": "string", "enum": ["event_graph", "function", "macro", "construction_script", "collapsed_graph"]},
        "nodes": {"type": "array", "items": {"$ref": "#/$defs/Node"}},
        "control_flow": {"$ref": "#/$defs/Flow"},
        "data_flow": {"$ref": "#/$defs/Flow"},
        "evidence": {"type": "object"}
      },
      "additionalProperties": false
    },
    "Node": {
      "type": "object",
      "required": ["id", "kind"],
      "properties": {
        "id": {"type": "string", "pattern": "^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*/node/[a-z][a-z0-9-]*/[A-Za-z][A-Za-z0-9_.-]*/[0-9]+$"},
        "label": {"type": "string"},
        "kind": {"type": "string"},
        "status": {"type": "string", "enum": ["recognized", "partial", "opaque"]},
        "source_type": {"type": "string"},
        "enabled_state": {"type": "string", "enum": ["enabled", "disabled", "development_only"]},
        "symbol": {"type": "string"},
        "execution": {"type": "object"},
        "data_pins": {"type": "object", "additionalProperties": {"$ref": "#/$defs/DataPin"}},
        "control_ports": {"type": "object", "additionalProperties": {"$ref": "#/$defs/ControlPort"}},
        "defaults": {"type": "object"},
        "evidence": {"type": "object"}
      },
      "additionalProperties": false
    },
    "DataPin": {
      "type": "object",
      "required": ["name", "direction", "type"],
      "properties": {
        "name": {"type": "string"},
        "direction": {"type": "string", "enum": ["input", "output"]},
        "type": {"$ref": "#/$defs/TypeRef"},
        "path": {"type": "array", "items": {"type": "string"}},
        "access": {"type": "string", "enum": ["read", "write", "read_write"]},
        "signature_role": {"type": "string", "enum": ["parameter", "return"]},
        "parameter_mode": {"type": "string", "enum": ["in", "out", "inout"]},
        "split_child": {"type": "boolean"},
        "non_compiling": {"type": "boolean"}
      },
      "additionalProperties": false
    },
    "ControlPort": {
      "type": "object",
      "required": ["name", "direction", "role"],
      "properties": {
        "name": {"type": "string"},
        "direction": {"type": "string", "enum": ["input", "output"]},
        "role": {"type": "string"}
      },
      "additionalProperties": false
    },
    "Flow": {
      "type": "object",
      "properties": {
        "entries": {"type": "array", "items": {"$ref": "#/$defs/EndpointRef"}},
        "edges": {"type": "array", "items": {"$ref": "#/$defs/FlowEdge"}}
      },
      "additionalProperties": false
    },
    "EndpointRef": {
      "type": "object",
      "required": ["node"],
      "properties": {
        "node": {"type": "string"},
        "port": {"type": "string"},
        "pin": {"type": "string"}
      },
      "additionalProperties": false
    },
    "FlowEdge": {
      "type": "object",
      "required": ["from", "to"],
      "properties": {
        "from": {"$ref": "#/$defs/EndpointRef"},
        "to": {"$ref": "#/$defs/EndpointRef"},
        "transition": {"type": "string", "enum": ["immediate", "resume", "callback"]},
        "ordinal": {"type": "integer", "minimum": 0}
      },
      "additionalProperties": false
    },
    "TypeRef": {
      "oneOf": [
        {"type": "string", "minLength": 1},
        {"type": "object", "required": ["$type"],
         "properties": {"$type": {"type": "string", "pattern": "^t[0-9]+$"}},
         "additionalProperties": false}
      ]
    },
    "TypeEntry": {
      "type": "object",
      "required": ["kind"],
      "properties": {
        "kind": {"type": "string", "enum": ["struct", "enum", "object", "class", "interface", "delegate", "array", "set", "map", "ref", "wildcard", "unknown"]},
        "path": {"type": "string"},
        "signature": {"type": "string"},
        "multicast": {"type": "boolean"},
        "soft": {"type": "boolean"},
        "weak": {"type": "boolean"},
        "uobject_wrapper": {"type": "boolean"},
        "const": {"type": "boolean"},
        "declared": {"type": "string"},
        "category": {"type": "string"},
        "name": {"type": "string"},
        "element": {"$ref": "#/$defs/TypeRef"},
        "key": {"$ref": "#/$defs/TypeRef"},
        "value": {"$ref": "#/$defs/TypeRef"},
        "target": {"$ref": "#/$defs/TypeRef"}
      },
      "additionalProperties": false
    },
    "Component": {
      "type": "object",
      "required": ["id", "name", "origin"],
      "properties": {
        "id": {"type": "string", "pattern": "^c[0-9]+$"},
        "name": {"type": "string"},
        "type": {"$ref": "#/$defs/TypeRef"},
        "origin": {"type": "string", "enum": ["scs_owned", "scs_inherited", "native", "unverified"]},
        "parent": {"type": "string"},
        "socket": {"type": "string"},
        "transform": {"type": "object"},
        "properties": {"type": "object"},
        "evidence": {"type": "object"}
      },
      "additionalProperties": false
    },
    "CoverageEntry": {
      "type": "object",
      "required": ["scope", "status"],
      "properties": {
        "scope": {"type": "string"},
        "status": {"type": "string", "enum": ["partial", "unavailable", "truncated"]},
        "reason": {"type": "string"},
        "declared": {"type": "integer", "minimum": 0},
        "emitted": {"type": "integer", "minimum": 0},
        "omitted": {"type": "integer", "minimum": 0}
      },
      "additionalProperties": false
    },
    "BlueprintDiagnostic": {
      "type": "object",
      "required": ["code", "scope", "severity", "effect", "count"],
      "properties": {
        "code": {"type": "string"},
        "scope": {"type": "string"},
        "severity": {"type": "string", "enum": ["error", "warning", "info"]},
        "effect": {"type": "string"},
        "count": {"type": "integer", "minimum": 1},
        "evidence": {"type": "object"}
      },
      "additionalProperties": false
    },
    "EvidenceEntry": {
      "type": "object",
      "required": ["key"],
      "properties": {"key": {"type": "string"}, "value": {}},
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

- [ ] **Step 4: Extend schema_loader.py**

```python
def load_blueprint_semantic_schema() -> dict[str, Any]:
    """Load the Blueprint semantic JSON schema from bundled package data."""
    try:
        from importlib.resources import files
        ref = files("uasset_read.schemas").joinpath("blueprint_semantic.schema.json")
        with ref.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, TypeError):
        from pathlib import Path
        schema_path = Path(__file__).parent / "schemas" / "blueprint_semantic.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"blueprint_semantic.schema.json not found at {schema_path}")
        return json.loads(schema_path.read_text(encoding="utf-8"))
```

- [ ] **Step 5: Harden projection**

In `projection.py::_recursive_strip_evidence`, strip both debug-only keys:

```python
            if k not in ("evidence", "extensions")
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py tests/core/test_json_schema_contract.py -v`
Expected: PASS. If real-sample schema validation fails on a legitimate field, fix the **implementation** to match the schema (contract first) — unless the schema contradicts the BP spec, in which case fix the schema and record the decision in the commit message.

- [ ] **Step 7: Verify wheel packaging**

```powershell
python -m build
python -c "import zipfile, glob; w = sorted(glob.glob('dist/*.whl'))[-1]; z = zipfile.ZipFile(w); print([n for n in z.namelist() if 'schemas' in n])"
```

Expected: both `semantic.schema.json` and `blueprint_semantic.schema.json` listed. (`dist/` is build output — do not commit it.)

- [ ] **Step 8: Commit**

```powershell
git add src/uasset_read/schemas/blueprint_semantic.schema.json src/uasset_read/schema_loader.py src/uasset_read/semantic/projection.py tests/test_blueprint_semantic.py
git commit -m "feat: blueprint semantic json schema draft 2020-12 (#554)"
```

---

### Task 14: Determinism, CLI/API equivalence, real-asset acceptance, docs

**Files:**
- Test: `tests/test_blueprint_semantic.py` (acceptance section)
- Create: `docs/formats/uasset/blueprint-semantic-json.md`
- Modify: `docs/formats/uasset/semantic-json.md` (cross-reference + reference-scope note update)

**Interfaces:**
- Consumes: everything above.
- Produces: byte-determinism proof across `PYTHONHASHSEED`, CLI==API equivalence, multi-sample acceptance assertions, format reference doc, issue-closing comment body.

Maps to issue acceptance criteria: schema + semantic validator (Tasks 12–13), standard/debug differences + Pin/Port completeness metrics (this task), stable IDs with partial/opaque traceability (validated here on real assets), complete node/connection/property/reference output (asserted here), CLI/API full JSON output (asserted here).

- [ ] **Step 1: Write the acceptance tests**

Append to `tests/test_blueprint_semantic.py`:

```python
class TestBlueprintAcceptance:
    SAMPLES = [
        "FirstPerson_BP_FirstPersonCharacter.uasset",
        "FirstPerson_BP_FirstPersonGameMode.uasset",
        "StackOBot_BP_Drone.uasset",
        "IntroToUnreal_BP_Light.uasset",
        "IntroToUnreal_BP_SaveData.uasset",
    ]

    def test_all_blueprint_samples_schema_valid_and_honest(self):
        import jsonschema
        from uasset_read.schema_loader import load_blueprint_semantic_schema
        from uasset_read.core import parse_single

        schema = load_blueprint_semantic_schema()
        for name in self.SAMPLES:
            doc = json.loads(parse_single(str(_sample(name)), format="json"))
            if doc.get("format") != "uasset_read.blueprint_semantic":
                continue
            jsonschema.validate(doc, schema)
            assert doc["status"]["parse"] != "failed"
            if doc["status"]["representation"] == "opaque":
                assert doc.get("diagnostics")
            for graph in doc["graphs"]:
                for node in graph["nodes"]:
                    for endpoint in list(node.get("data_pins", {})) + list(node.get("control_ports", {})):
                        assert "." in endpoint  # direction-prefixed endpoint id
            # Pin/Port completeness metric: every edge endpoint resolves to a
            # declared pin/port on its node.
            for graph in doc["graphs"]:
                declared = set()
                for node in graph["nodes"]:
                    for ep in list(node.get("data_pins", {})):
                        declared.add((node["id"], ep))
                    for ep in list(node.get("control_ports", {})):
                        declared.add((node["id"], ep))
                for section, key in (("control_flow", "port"), ("data_flow", "pin")):
                    for edge in graph.get(section, {}).get("edges", []):
                        for side in ("from", "to"):
                            ref = edge[side]
                            assert (ref["node"], ref[key]) in declared

    def test_standard_debug_modes_differ_and_complete(self):
        from uasset_read.core import parse_single

        sample = str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset"))
        standard = parse_single(sample, format="json", output_level="standard")
        debug = parse_single(sample, format="json", output_level="debug")
        assert standard != debug
        assert '"evidence"' in debug
        assert '"evidence"' not in standard
        assert json.loads(standard)["status"] == json.loads(debug)["status"]

    def test_byte_determinism_across_pythonhashseed(self):
        import os
        import subprocess
        import sys

        sample = str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset")).replace("\\", "/")
        snippet = (
            "from uasset_read.core import parse_single;"
            f"print(parse_single(r'{sample}', format='json', output_level='standard'), end='')"
        )
        outputs = []
        for seed in ("0", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH="src")
            proc = subprocess.run([sys.executable, "-c", snippet], capture_output=True,
                                  text=True, env=env, check=True)
            outputs.append(proc.stdout)
        assert outputs[0] == outputs[1]
        assert outputs[0].endswith("}\n")

    def test_cli_single_file_matches_python_api(self):
        import subprocess
        import sys

        from uasset_read.core import parse_single

        sample = str(_sample("FirstPerson_BP_FirstPersonCharacter.uasset"))
        api_output = parse_single(sample, format="json", output_level="standard")
        assert api_output.endswith("}\n")  # exactly one trailing newline
        proc = subprocess.run([sys.executable, "run.py", "--json", sample],
                              capture_output=True, text=True, check=True,
                              env={**__import__("os").environ, "PYTHONPATH": "src"})
        # Compare parsed documents (CLI print may append a newline); byte
        # determinism of the API output itself is covered by
        # test_byte_determinism_across_pythonhashseed.
        assert json.loads(proc.stdout) == json.loads(api_output)
```

- [ ] **Step 2: Run acceptance tests**

Run: `python -m pytest -q tests/test_blueprint_semantic.py::TestBlueprintAcceptance -v`
Expected: PASS. If a sample does not produce `blueprint_semantic` (e.g. its primary export class is not registered), check `kinds.py` mapping for that class and register it only if the asset is genuinely a Blueprint (evidence: `b_is_asset` + graphs); otherwise record it as a counter-example in the research doc and keep the `continue` guard.

- [ ] **Step 3: Run the full verification matrix**

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_blueprint_semantic.py tests/test_semantic.py
python -m pytest -q
python -m compileall -q src tests
python -m ruff check src tests
python -m build
```

Expected: all green. Fix any ruff findings in new files.

- [ ] **Step 4: Write the format reference doc**

Create `docs/formats/uasset/blueprint-semantic-json.md` covering (same structure as the non-bp domain docs): applicable classes (`Blueprint`, `BlueprintGeneratedClass`), envelope fields, `graphs`/`nodes`/endpoint/flow contract with the BP-§5 ID regexes, `types`/`variables`/`components`/`declaration` fields, coverage scopes and diagnostic codes (`BP_GRAPH_MISSING`, `BP_NODE_UNRECOGNIZED`, `BP_LINK_UNRESOLVED`, `BP_LINK_DIRECTION`, `BP_LINK_KIND_MISMATCH`, `BP_DEFAULT_UNRESOLVED`, `BP_COMPONENT_PARENT_UNRESOLVED`), size limits (no raw coordinates/GUIDs in standard; `$bounded` reserved), CLI/API usage examples (`python run.py --json file.uasset`, `--output-level debug`), and one complete example excerpt generated from `FirstPerson_BP_FirstPersonCharacter.uasset` (standard mode, trimmed to one graph).

- [ ] **Step 5: Update the common doc**

In `docs/formats/uasset/semantic-json.md`, under "Asset Type Resolution" add: Blueprint classes with a registered domain extractor now emit the dedicated `uasset_read.blueprint_semantic` format — see `blueprint-semantic-json.md`. Update the Reference Scope note: reference closure remains deferred for non-Blueprint formats; the Blueprint format omits the raw table by design.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_blueprint_semantic.py docs/formats/uasset/blueprint-semantic-json.md docs/formats/uasset/semantic-json.md
git commit -m "test: blueprint semantic acceptance, determinism, and docs (#554)"
```

- [ ] **Step 7: Post the acceptance summary to the issue**

Compose a `gh issue comment 554 --body "..."` summarizing: commits, acceptance criteria verification (schema + validator; standard/debug Pin/Port completeness metrics; stable URI IDs with partial/opaque traceability; node/connection/property/reference coverage; CLI/API output), test totals, and explicitly: research-gate outcome, deferred items (symbols/constants interning, reroute folding, CDO variable comparison, SCS origin proof, latent/async transition inference, AnimBlueprint via #555), with doc references. Do NOT close the issue unless the user asks.

---

## Verification Matrix (final)

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_blueprint_semantic.py
python -m pytest -q tests/test_semantic.py tests/core/test_semantic_determinism.py
python -m pytest -q
python -m compileall -q src tests
python -m ruff check src tests
python -m build
```

Additional checks performed by tests above:
- byte comparison across subprocesses with different `PYTHONHASHSEED` (Task 14);
- CLI single-file output == Python API (Task 14);
- recursive `debug -> standard` projection equality (Task 11);
- schema discovery after wheel build (Task 13);
- real-asset honesty: no fabricated completeness, opaque requires diagnostics (Tasks 12/14).
