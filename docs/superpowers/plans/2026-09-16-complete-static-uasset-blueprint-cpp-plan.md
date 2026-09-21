# Complete Static UAsset Parsing and Type-Aware Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current mixed parsing/enrichment path with a modular pure-Python parser that statically reconstructs package and asset semantics, then emits the best available declaration, behavior, editor-builder, structured-data, and payload projections for each asset family.

**Architecture:** Keep one package-first `PackageDocument`, but introduce only the boundaries needed by the core path: bounded source/layout, lossless properties and ranges, domain IR, static Blueprint/Kismet analysis, and projections. Legacy and Zen remain separate format boundaries; Blueprint graph and Kismet bytecode converge in one correlation layer; C++/CSV/JSON are derived artifacts in one canonical output document. C++ is a projection and never a second parser.

**Tech Stack:** Python 3.10+, existing standard-library implementation, `pytest`, JSON golden fixtures, optional local Unreal source only for evidence. No CUE4Parse/UAssetAPI/UAssetGUI/UnrealBPInspect/FModel bridge and no Unreal Editor runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`

## Execution status (2026-09-21)

This plan is still an execution target, not a completion record. The current
working branch is `dev-0.6.0`:

| Tasks | Current marker | Evidence / next boundary |
| --- | --- | --- |
| 1–4 | `complete` on this branch | v3 contract, bounded sources/containers, layout/Zen refusal, separate property readers, and byte accounting present; Step 5 gates green after committing plan/docs WIP and re-measuring `docs_markdown`. |
| 5–9 | `implemented on sdd/static-uasset-finish` | Focused Tasks 5–9 suite green on execution branch `sdd/static-uasset-finish` (worktree `.worktrees/sdd-static-continue`); `objects[].semantic` is projected dict for Blueprint/Material families. Not marked complete on `dev-0.6.0` until an orchestrator merge lands there. |
| 10–12 | `not started` | No current C++/type-aware projection implementation, canonical writer replacement, or complete-sample acceptance suite is present. |

The fresh current-branch check was 155 passed and one failure in
`tests/test_size_baseline.py:67-74`; the failure is the known worktree-only
docs ratchet caused by the uncommitted plan and status-audit documentation, not
a parser test failure.
The final review checklist therefore remains open.

**Evidence used for this plan (do not re-derive from memory):**
- UE source citations below are relative to the Unreal Engine source root; no developer-local checkout path is part of the contract.
- Current-code reuse map and sample gap analysis performed 2026-09-16 against this repository.
- OpenViking corroboration: Blueprint assets / package-system wiki entries only; they are secondary evidence and must not override UE source or fixtures.

## Global Constraints

- Pure Python 3.10+; no runtime bridge, subprocess bridge, FFI bridge, or dependency on the reference projects.
- `PackageDocument` remains the only package-level aggregate; every export remains addressable.
- Legacy and Zen packages use separate readers and converge on shared models.
- Tagged and unversioned properties use separate readers and converge on shared values.
- No runtime Blueprint execution; all control-flow and calls are static analysis.
- No fabricated data for cooked-away graphs, unknown serialization, encryption, missing chunks, or native C++ bodies.
- Existing handler/IR conversion paths are replaced in-place; no backward-compatibility semantic adapter or bridge is required.
- Every unknown region is decoded, opaque, payload-addressable, or unavailable with offset/size/reason.
- A successful reader may not consume and discard a field: every consumed value has a typed projection or a ranged opaque record, including nested Kismet operands and reflection metadata.
- A breaking document schema is allowed; use `format_version: "3.0"` for the rebuilt output.
- C++ is not mandatory for every asset; generated C++ has declaration, migration, and editor-builder modes where the asset family supports them.
- Every asset projector declares its capability and emits `translated`, `represented`, `untranslated`, or `unavailable` status instead of fabricating an equivalent source file. Low-confidence mappings use `untranslated` or `represented` with a diagnostic; `uncertain` is not a v3 projection status.
- Each input package produces one canonical JSON output document containing package data, all addressable objects, semantic projections, type-aware projections, capabilities, diagnostics, and payload references.
- C++ header/source text, CSV-compatible text, and structured JSON projections are embedded in the canonical document; ordinary graphs, functions, exports, and asset types never cause output splitting.
- Physical sidecars are permitted only for a measured hard size/safety boundary; the core writer keeps one file and rejects an explicitly impossible limit. A later sidecar extension must record each sidecar's relative path, size, hash, source range, and reason in the main document.
- Existing unrelated dirty files and `reference/` are not staged or modified.
- New probes and generated files belong under `temp/` unless they are committed fixtures or tests.
- All `Run:` commands in this plan are PowerShell commands and set `$env:PYTHONPATH='src'` before importing `uasset_read`.
- Every task ends with its focused tests plus `tests/test_size_baseline.py`; if measured tracked line counts grow, update `tests/size-baseline.json` in that same task and commit.
- Do not hardcode this machine's absolute UE path into committed documentation or tests; keep UE citations relative to the Unreal Engine source root.

## 2026-09-17 scope revision

This revision makes the plan executable in the current repository and keeps the
minimum path to the user's core goal visible:

- The first deliverable is lossless package/object/property/byte-range data plus
  static Blueprint graph and Kismet analysis. It must expose event entrypoints,
  Branch targets, calls, variable definitions/usages, constructors, dispatchers,
  and unresolved/opaque regions without running a VM or Unreal code.
- `objects[].semantic` is the canonical structured trace. A projection is added
  only when it provides a non-duplicating artifact such as C++ declaration,
  migration C++, editor-builder C++, CSV, or structured data. Generic object data,
  `graphs`, and `functions` are not copied into a second `blueprint_trace` record.
- `PackageArchive` remains the Legacy reader's I/O owner during the core rewrite.
  A source adapter may be introduced at one explicit boundary when a new reader
  needs random access, but the six-commit table-by-table adapter migration is
  removed from the critical path.
- Task 2/3 prove source classification and a truthful Zen unavailable boundary.
  Full Zen table/export/payload decoding is deferred until a redistributable
  `.ucas` package fixture and an explicit package/chunk selection API exist.
- The default output is one canonical JSON file. Sidecar materialization and an
  optional compiler probe are late validation boundaries, activated only after a
  measured safety/size failure or a real compiler fixture; neither is a core
  parser milestone.

The plan still allows the breaking v3 output requested by the design. It does
not preserve the old semantic shape, but every in-tree caller and test that uses
the changed shape is migrated in the same task.

## Edit Execution Playbook

Authoritative procedure for the remaining high-risk *edit* work. It does not add new top-level tasks; it constrains how Tasks 2, 3, 5, 8, 10, 10A, 11, and 12 must be edited so reviewers can reject a half-migrated tree.

### E0. Edit discipline (applies to every task)

1. **One concern per commit.** Never mix a schema bump, a registry move, and a reader rewrite in one commit.
2. **Green before you widen.** After each sub-step, run that sub-step's focused tests plus `tests/test_size_baseline.py`. Do not start the next sub-step on a red tree.
3. **No dual implementations.** If a new API replaces an old one, delete or rewrite every in-tree caller in the *same* commit. Temporary shims are forbidden unless this playbook explicitly names one.
4. **Preserve unrelated dirty files.** Never stage `reference/`, `docs/plans/2026-09-16-als-name-index-and-optin-docs.md`, or any file not listed in the active task's Files block.
5. **Measured baselines only.** `tests/size-baseline.json` changes only from `python -m pytest tests/test_size_baseline.py -q` failure output, never from estimates.
6. **Worktree policy:** execution defaults to the main worktree unless the user later requests isolation. Do not create a worktree unilaterally.

### E1. Semantic shape contract (Tasks 5–11 and 10A)

`ObjectRecord.semantic` remains `dict[str, Any] | None` at the document boundary. Typed IR never lives as a raw dataclass in JSON output.

```text
typed IR (BlueprintSemantic / MaterialGraph / FunctionAnalysis)
        │  project_semantic_blueprint() / project_semantic_material()
        ▼
ObjectRecord.semantic  →  dict with stable keys only
        │  project_document(view=...)
        ▼
JSON / CLI / Agent
```

Canonical dict keys (frozen for v3 decode output):

| key | type | produced by |
|---|---|---|
| `kind` | `"blueprint"` / `"anim_blueprint"` / `"material"` / … | handler/decoder |
| `graphs` | `list[dict]` (node/pin/link projection) | Task 6 |
| `functions` | `list[dict]` each containing `function_name`, `expression_count`, `bytecode_status`, `instructions`, and `cfg` as dictionaries | Tasks 7–8 |
| `declaration` | `dict` containing parent, reflected class metadata, function declarations, and variable definitions | Task 8 |
| `variable_definitions` | `list[dict]` containing Blueprint property declarations and `VarType`/reflection data | Task 8 |
| `entrypoints` / `calls` / `variable_accesses` / `constructors` / `variable_events` | `list[dict]` | Task 8 |
| `control_flow` | `list[dict]` CFG projection | Task 8 |
| `material_graph` | `dict` (not a live dataclass) | Task 9 |
| `projection_capabilities` | `list[dict]` with projection kinds and status | Task 10A |

Rules:
1. Sample-facing `tests/fixtures.py` helpers (`find_function`, `find_material_graph`) read **dicts**, not dataclasses. Unit tests that need the lossless model use the explicitly typed `function_analysis_ir`, `stackobot_semantic`, or `ue58_semantic` fixtures; no fixture silently changes type.
2. Typed IR classes are **internal** to `parsers/blueprint/*` and `parsers/material/*`. The projected dict must contain all declaration/type/reflection context needed by C++; a hidden live dataclass or hidden source handle is never required by the renderer.
3. Public C++ entry is `render_cpp(semantic_dict: dict, mode: str) -> CppProjection` so CLI/Agent/tests share one boundary. The dict is complete enough to reconstruct the typed IR without a `PackageDocument` lookup.
4. Never leave half-migrated objects where some Blueprint exports still use the old K0 shape (`functions[].expressions` tree only) and others use the new IR. Task 8 Step 4 flips the Blueprint-family decoder in one commit.

Type-aware projection descriptors are projection metadata, not parser semantics. They are embedded in the canonical document and carry their content unless a physical sidecar is required:

`objects[].semantic.projection_capabilities` describes what can be emitted for that object; the top-level `project_document()` result exposes the corresponding embedded records as `projections`. `build_projection_records()` supplies the content before the document writer serializes it.

```json
{
  "kind": "blueprint_cpp_declaration",
  "source_object_id": "export:0",
  "media_type": "text/x-c++hdr",
  "content": "...",
  "embedded": true,
  "status": "translated",
  "completeness": 0.92,
  "dependencies": [],
  "diagnostics": [],
  "source_range": null,
  "external": null
}
```

The projection API is the only API allowed to create embedded type-specific content. The document writer is the only API allowed to materialize the canonical output file or technically unavoidable sidecars:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.models.diagnostics import Diagnostic


@dataclass(frozen=True)
class ProjectionRecord:
    kind: str
    source_object_id: str
    media_type: str
    content: str | dict[str, Any] | None
    embedded: bool
    status: Literal["translated", "represented", "untranslated", "unavailable"]
    completeness: float | None
    dependencies: list[str]
    diagnostics: list[Diagnostic]
    source_range: ByteRegion | None = None
    external: "SidecarRecord | None" = None


@dataclass(frozen=True)
class SidecarRecord:
    path: str
    size: int
    sha256: str
    reason: Literal["size_limit", "unsafe_payload"]
    source_range: ByteRegion | None
    projection_kind: str | None


def build_projection_records(
    document: PackageDocument,
    *,
    object_ids: list[str] | None = None,
    kinds: list[str] | None = None,
) -> list[ProjectionRecord]: ...


def build_canonical_document(document: PackageDocument) -> dict[str, Any]: ...


def write_projected_document(
    document: PackageDocument,
    output_path: Path,
    *,
    max_main_bytes: int | None = None,
) -> Path: ...


def minimum_canonical_envelope_bytes(document: PackageDocument) -> int: ...
```

`minimum_canonical_envelope_bytes()` measures the complete envelope with every
object ID, semantic status, capability, diagnostic, projection descriptor, and
payload reference present but with eligible projection `content` externalized.
It is therefore a real lower bound for a canonical file, not an arbitrary test
constant.

There are two deliberately different output boundaries. `project_document()` is
the bounded response API and may apply `object_ids`, `limit`, `offset`, `depth`,
or `max_bytes` for CLI/Agent queries. `build_canonical_document(document)` and
`write_projected_document()` are the file API: they always include every
addressable object, every selected semantic field, every projection record, and
all diagnostics. The file API accepts no object selection or pagination. A
canonical file must never be produced from a page of `project_document()`.

`max_main_bytes` is a strict physical limit. The core writer first materializes
the complete document and raises a structured output-budget error when an
explicit limit cannot contain it, including when it is below the measured
minimum envelope. The default is no limit. `SidecarRecord` and
`ProjectionRecord.external` remain reserved for a later measured hard-boundary
extension; ordinary export, graph, function, and asset-family boundaries never
trigger a sidecar.

Sub-steps for E1:

- [ ] **E1.1** Add `project_semantic_blueprint(semantic: BlueprintSemantic) -> dict` and `project_semantic_material(graph: MaterialGraph) -> dict`.
      Concrete skeleton for the Blueprint half lives in Task 8 Step 4 (`project_semantic_blueprint` / `project_function_analysis`). The Material half maps `MaterialGraph` fields to `{"kind": "material", "material_graph": {...}, "diagnostics": [...]}` with the same no-dataclass rule.
- [ ] **E1.2** Rewrite `find_function` / `find_material_graph` to walk dicts (`fn["function_name"]`, `obj.semantic["material_graph"]`).
- [ ] **E1.3** Point typed unit tests at explicit `*_ir` fixtures and sample tests at projected dicts — not a mixed fixture contract.
- [ ] **E1.4** Point Task 11 and Task 10A projectors at projected dicts; the same `parse_sample` document feeds the single JSON document, embedded C++, editor-builder, and data projections.
- [ ] **E1.5** Grep for `isinstance(.*FunctionAnalysis` / `isinstance(.*MaterialGraph` outside parser modules; none may remain in `tests/fixtures.py` or `projection.py`.
- [ ] **E1.6** Add explicit tests that `project_document()` may paginate while `build_canonical_document()` and `write_projected_document()` reject pagination and contain all object IDs.
- [ ] **E1.7** Keep `SidecarRecord`/`ProjectionRecord.external` as a documented late boundary. Do not add a synthetic sidecar implementation or threshold test until Task 11 measures a real output that cannot safely remain one file; a limit below the mandatory envelope must raise before writing.

### E2. Task 3 Legacy source boundary (minimal)

`legacy_reader.py` is ~1.5k lines with a dense call graph (`read` → property parse → `run_handlers` → blueprint/kismet attach). Do **not** rewrite the file in one commit or replace every existing table reader merely to introduce `ByteSource`.

Current anchors (keep working until each step lands):

```text
LegacyPackageReader.read                         legacy_reader.py:510
_parse_requested_object_properties               :851
_attach_blueprint_graph_extras                   :1121
_attach_kismet_extras                            :1257
_read_table_rows                                 :1304
run_handlers unpack                              :779
parse_package_document                           package.py:260
```

The only required Legacy/source work is:

1. Keep `PackageArchive`'s existing `.uasset` + `.uexp` virtual splice and
   `main_size == TotalHeaderSize` rejection as the single Legacy invariant.
2. Use `CompositeSource` for explicit range mapping and new property/opaque
   readers. If an existing `FArchive` reader must consume a `ByteSource`, add
   one local `FArchiveFromSource` at that call boundary and remove it in the
   same task once the caller is converted; do not create a parallel table-reader
   stack or six migration commits.
3. Run the existing sample/property/Blueprint tests after each boundary change;
   the canonical sample output must not change except for the planned v3 shape.
4. Let `PackageLayoutDetector` choose Legacy/Zen from validated bytes and make
   unknown/container-only inputs structured failures. No Legacy parse of container
   metadata is permitted.

Out of scope for Task 3: property state-machine split (Task 4), handler registry move (Task 5), CFG (Task 7).

### E3. Remaining minor edits (batch with the nearest task)

| Item | Fix | Batch into |
|---|---|---|
| `test_composite_rejects_negative_offset` uses `MemorySource` | rename to `test_memory_source_rejects_negative_offset` or exercise `CompositeSource` | Task 2 |
| clang++ optional probe in Task 10 | defer from the blocking suite; AST/oracle and JSON-safety tests are sufficient for the core plan | Task 10 |
| Task 12 `temp/quality-v3/` | Files list marks it untracked; commit step must not `git add temp/` | Task 12 |

### E4. Suggested execution order for these edits

```text
1. E3 minor batch (Task 2 fixture/name fixes) — no design impact
2. E1.1–E1.2 semantic projection + helpers — before the IR flip
3. Task 2 source/range boundary + Task 3 validated layout — no table rewrite
4. Task 4 property/byte accounting — before Blueprint/Material decoding
5. Tasks 6 → 7 → 8 → 10 — graph, Kismet, correlation, then C++
6. Task 9 → 10A → 11 — Material/data projections and one-file output
```

Each numbered item is one reviewable commit. A source adapter is not a separate
project milestone; it is removed as soon as its one consumer is migrated.

### E5. Blueprint IR task sequencing (Tasks 6 → 7 → 8 → 10)

Tasks 6, 7, 8, and 10 all depend on the same Blueprint IR contract and are
strictly sequential; do not interleave commits.

```text
Task 6  graph IR only          (BlueprintGraph / NodeId / PinLink; serializers stay raw-binary owners)
   │
   ▼
Task 7  instruction + CFG only (BytecodeInstruction / BasicBlock / ControlFlowGraph / FunctionAnalysis)
   │                           — must land SerializedStart/End on KismetExpression first
   ▼
Task 8  declarations + correlation + E1 flip (BlueprintSemantic; one-commit dict flip)
```

Rules:
1. Task 6 must not define instruction or CFG types. Task 7 must not define graph types. Task 8 is the only place that combines them and adds declaration/access records.
2. Task 7 extends `KismetExpression` with `SerializedStart`/`SerializedEnd` in its own commit before `normalize_instructions` lands.
3. Task 8 Step 4 flips every Blueprint-family `ObjectRecord.semantic` from the old K0 shape to the projected dict in **one** commit. Sample fixtures, typed `*_ir` fixtures, and every changed consumer are part of that commit.
4. After Task 8, sample-facing code consumes dicts; only parser/unit code and explicitly named `*_ir` fixtures may use `FunctionAnalysis` or `BlueprintSemantic` instances.

## File Map

The implementation should converge on these focused modules instead of adding more responsibilities to `package.py` or `handlers_impl.py`:

- `src/uasset_read/sources.py`: bounded random-access source protocol and file/memory/composite implementations.
- `src/uasset_read/containers.py`: bounded Pak/IoStore classification and container diagnostics; chunk extraction stays a later evidence-backed boundary.
- `src/uasset_read/layout.py`: validated Legacy/Zen layout selection and shared layout metadata.
- `src/uasset_read/versioning.py`: the minimal immutable version/layout context consumed by readers and handlers.
- `src/uasset_read/models/byte_ranges.py`: source ranges, opaque regions, payload references, and byte accounting.
- `src/uasset_read/models/properties.py`: ordered `PropertyBag`, property occurrences, and JSON-safe value projection.
- `src/uasset_read/models/object_model.py`: addressable object identity, class/super/template refs, serial regions, and object diagnostics.
- `src/uasset_read/models/document.py`: package envelope, relations, dependencies, diagnostics, and attached byte accounting.
- `src/uasset_read/models/analysis.py`: **Create in Task 6**; shared Blueprint/Kismet/Material IR and capability statuses, extended with declarations in Task 8.
- `src/uasset_read/parsers/legacy_reader.py`: Legacy table/object orchestration only.
- `src/uasset_read/parsers/zen_reader.py`: validated Zen header/availability boundary only until a real package fixture exists.
- `src/uasset_read/parsers/properties/tagged.py`: Tagged property state machine.
- `src/uasset_read/parsers/properties/unversioned.py`: Unversioned property state machine.
- `src/uasset_read/parsers/properties/schema.py`: Mapping/schema provider.
- `src/uasset_read/parsers/properties/opaque.py`: Native tails and opaque-region preservation.
- `src/uasset_read/parsers/asset_types/registry.py`: Handler registration and dispatch.
- `src/uasset_read/parsers/blueprint/graph.py`: Blueprint graph decoder.
- `src/uasset_read/serializers/k2_metadata.py`: version-gated K2 member/event/variable metadata reader.
- `src/uasset_read/parsers/blueprint/bytecode.py`: Kismet instruction normalization.
- `src/uasset_read/parsers/blueprint/control_flow.py`: Basic blocks and CFG construction.
- `src/uasset_read/parsers/blueprint/correlation.py`: Graph/bytecode/source-node correlation.
- `src/uasset_read/kismet/archive.py`, `expressions.py`, `property_pointer.py`: lossless Kismet cursor, operand, and pointer records.
- `src/uasset_read/kismet/result.py`, `ufunction_reader.py`, `native_fields.py`: function identity, script ranges, and reflection declarations.
- `src/uasset_read/projections/cpp_ast.py`: C++ projection AST.
- `src/uasset_read/projections/cpp_render.py`: Header/source rendering.
- `src/uasset_read/projections/records.py`: embedded projection records and capability/status records; sidecar descriptors remain a late boundary.
- `src/uasset_read/projections/registry.py`: type-aware projector registry and deterministic dispatch.
- `src/uasset_read/projections/material_builder.py`: editor-only material reconstruction C++ projection.
- `src/uasset_read/projections/data_exports.py`: DataTable/CurveTable/struct/enum CSV, JSON, and optional C++ initializer projections.
- `src/uasset_read/projections/bundle.py`: canonical single-document writer; no binary asset writer or automatic sidecar implementation in the core path.
- `src/uasset_read/parsers/material/graph.py`: Material expression graph decoder.
- `src/uasset_read/projection.py`: JSON/CLI/Agent projection from `PackageDocument`.
- `src/uasset_read/package.py`: thin public entrypoint and cache key construction.
- `tests/fixtures.py`: ordinary named sample/parser helper functions imported by tests.
- `tests/conftest.py`: pytest-discoverable fixtures; fixture definitions do not live only in `tests/fixtures.py`.
- `tests/test_sources.py`, `tests/test_containers.py`, `tests/test_layout.py`, `tests/test_zen_reader.py`: binary input boundaries.
- `tests/test_properties.py`, `tests/test_byte_accounting.py`: tagged/unversioned/opaque property contracts and export-byte coverage.
- `tests/test_handler_registry.py`: single-owner domain dispatch.
- `tests/test_blueprint_ir.py`, `tests/test_blueprint_cfg.py`, `tests/test_blueprint_correlation.py`, `tests/test_blueprint_cpp.py`: Blueprint static analysis and C++ output.
- `tests/test_blueprint_graph.py`, `tests/test_blueprint_decode.py`, `tests/test_samples.py`: existing graph/Kismet consumers migrated with the typed IR and status changes; they are not left on an old return shape.
- `tests/test_k2_metadata.py`, `tests/test_kismet_operand_preservation.py`, `tests/test_native_fields.py`: K2 identity/reflection and Kismet losslessness contracts.
- `tests/samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json`: normalized UE5.8 declaration oracle.
- `tests/test_material_graph.py`: Material expression graph contracts.
- `tests/test_asset_projections.py`: specialized projector capability matrix, material builder, and structured-data projection contracts.
- `tests/test_single_output.py`: single-document embedding and status propagation; measured sidecar behavior is a late boundary, not a synthetic core test.
- `tests/test_projection_v3.py`: v3 envelope and JSON/C++ projection consistency.
- `tests/test_complete_samples.py`: sample acceptance and byte-accounting gates.

The following test helpers are introduced in Task 1 and are the only shared test vocabulary used below:

```python
from pathlib import Path
from typing import Any

from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord
from uasset_read.package import parse_package_document

SAMPLES = Path(__file__).resolve().parent / "samples"


def sample_path(name: str) -> Path:
    path = SAMPLES / name
    if not path.exists():
        raise FileNotFoundError(f"missing fixture sample: {name}")
    return path


def parse_sample(
    name: str,
    *,
    depth: str = "decode",
    object_ids: list[str] | None = None,
) -> PackageDocument:
    return parse_package_document(
        sample_path(name),
        depth=depth,
        object_ids=object_ids,
        tolerant=True,
    )


def find_function(document: PackageDocument, name: str):
    """Return the projected function dict for `name` (E1: dicts, not dataclasses)."""
    for obj in document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            if fn.get("function_name") == name:
                return fn
    raise KeyError(f"function not found: {name}")


def find_blueprint_object(document: PackageDocument) -> ObjectRecord:
    for obj in document.objects:
        if "asset" in obj.roles and (obj.semantic or {}).get("kind") in {"blueprint", "anim_blueprint"}:
            return obj
    raise KeyError("no blueprint asset object in document")


def find_material_graph(document: PackageDocument) -> dict:
    """Return the projected material_graph dict (E1), never a live MaterialGraph dataclass."""
    for obj in document.objects:
        graph = (obj.semantic or {}).get("material_graph")
        if isinstance(graph, dict) and graph.get("expressions") is not None:
            return graph
    raise KeyError("no material graph in document")


def make_property_input(name: str, *, object_name: str | None = None):
    # Imports are lazy so Task 1 can create this helper before Tasks 2/4 add
    # the bounded source and property-input models.
    from uasset_read.parsers.properties import PropertyInput
    from uasset_read.sources import CompositeSource
    from uasset_read.versioning import VersionContext

    path = sample_path(name)
    document = parse_package_document(path, depth="package", tolerant=True)
    candidates = [obj for obj in document.objects if obj.serial_region and obj.serial_region.size > 0]
    obj = next((item for item in candidates if item.name == object_name), candidates[0])
    return PropertyInput(
        source=CompositeSource.from_package(path),
        object_id=obj.id,
        start=obj.serial_region.offset,
        size=obj.serial_region.size,
        class_name=obj.class_name or "Unknown",
        context=VersionContext(depth="object"),
    )
```

`tests/conftest.py` defines the named pytest fixtures used by the focused tests: `tagged_fixture`, `unversioned_fixture`, `fake_source`, `object_record`, `unknown_object_record`, `package_context`, `package_document`, `ue58_blueprint_document`, `ue58_source`, `function_analysis_ir`, `stackobot_document`, `stackobot_source`, `stackobot_material`, `cooked_material`, `stackobot_semantic`, `ue58_semantic`, and `document`. Each fixture is built from a real sample or a bounded synthetic byte window and returns the model named by the test that consumes it. Typed unit tests use `function_analysis_ir`; sample-facing tests use `find_function()` on projected dictionaries. K2 opaque-field and native-field tests construct the smallest typed records inline; they do not depend on undeclared fixture factories. Tests import helper functions from `tests.fixtures`; pytest injects fixture parameters from `tests/conftest.py` automatically.

Implement `tests/conftest.py` with these exact sample bindings (from `tests/samples/manifest.json`, verified 2026-09-16):

```python
import pytest

from tests.fixtures import make_property_input, parse_sample, sample_path
from uasset_read.models.document import PackageDocument


@pytest.fixture
def stackobot_document() -> PackageDocument:
    # manifest: export_count=31, b_is_asset_count=2, legacy, UE4=864
    return parse_sample("StackOBot_BP_Drone.uasset", depth="decode")


@pytest.fixture
def ue58_blueprint_document() -> PackageDocument:
    # manifest: export_count=24, UE4=522, UE5=1018
    return parse_sample("MyProject_UE58_TestBlueprint.uasset", depth="decode")


@pytest.fixture
def stackobot_source():
    from uasset_read.sources import CompositeSource

    return CompositeSource.from_package(sample_path("StackOBot_BP_Drone.uasset"))


@pytest.fixture
def ue58_source():
    from uasset_read.sources import CompositeSource

    return CompositeSource.from_package(sample_path("MyProject_UE58_TestBlueprint.uasset"))


@pytest.fixture
def stackobot_material() -> PackageDocument:
    # manifest: export_count=42; design gate 3 expects 39 material expressions
    return parse_sample("StackOBot_M_BotBase.uasset", depth="decode")


@pytest.fixture
def cooked_material() -> PackageDocument:
    # cooked/editor-stripped material; expected capability limited/unavailable
    return parse_sample("TestMaterial.uasset", depth="decode")


@pytest.fixture
def unversioned_fixture():
    return make_property_input("BP_UnversionedTest.uasset", object_name="Default__BP_UnversionedTest_C")


@pytest.fixture
def tagged_fixture():
    return make_property_input("TestBlueprint.uasset")


@pytest.fixture
def fake_source(tmp_path):
    from uasset_read.sources import CompositeSource

    main = tmp_path / "A.uasset"
    sidecar = tmp_path / "A.uexp"
    main.write_bytes(b"\x00\x01")
    sidecar.write_bytes(b"\x02\x03\x04")
    return CompositeSource.from_package(main)


@pytest.fixture
def package_document(stackobot_document) -> PackageDocument:
    return stackobot_document


@pytest.fixture
def document(package_document) -> PackageDocument:
    return package_document


@pytest.fixture
def object_record(stackobot_document):
    return stackobot_document.objects[0]


@pytest.fixture
def unknown_object_record(object_record):
    from dataclasses import replace

    return replace(object_record, class_name="UnknownClass", roles=[])


@pytest.fixture
def package_context(stackobot_document):
    return stackobot_document.package


@pytest.fixture
def function_analysis_ir():
    """Small typed fixture for operand projection; sample fixtures stay dicts."""
    from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction
    from uasset_read.parsers.blueprint.control_flow import ControlFlowGraph
    from uasset_read.models.analysis import FunctionAnalysis

    instruction = BytecodeInstruction(
        statement_index=0,
        statement_ordinal=0,
        logical_end=4,
        serialized_start=0,
        serialized_end=8,
        opcode="EX_VirtualFunction",
        operands={"parameters": [{"name": "Value", "value": 1}]},
        expression={"parameters": [{"name": "Value", "value": 1}]},
        reads=[],
        writes=[],
        call_target="Synthetic.Call",
        jump_target_statement_index=None,
        jump_kind="none",
        source_node_id=None,
    )
    return FunctionAnalysis(
        object_id="export:9",
        owner_object_id="export:0",
        name="Synthetic",
        function_name="Synthetic",
        script_source_range=None,
        expression_count=1,
        entrypoint=None,
        instructions=[instruction],
        cfg=ControlFlowGraph(blocks=[], edges=[], entry=0, metadata={}),
        reads=set(),
        writes=set(),
        calls=["Synthetic.Call"],
        bytecode_status="parsed",
        diagnostics=[],
    )


@pytest.fixture
def stackobot_semantic(stackobot_document):
    from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation

    return BlueprintCorrelation().build(stackobot_document)


@pytest.fixture
def ue58_semantic(ue58_blueprint_document):
    from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation

    return BlueprintCorrelation().build(ue58_blueprint_document)
```

Reuse these current-code entry points instead of rewriting their binary readers:

```text
parse_package_document(path, *, depth, object_ids, tolerant)     package.py
extract_kismet_decompiled(...) -> list[KismetDecompiledResult]   kismet/decompile_bridge.py:23
parse_bytecode_stream(...) -> list[KismetExpression]             kismet/bytecode_extractor.py:35
read_ufunction_script(...) -> FunctionScriptReadResult           kismet/ufunction_reader.py:442
read_blueprint_graphs(...)                                       serializers/blueprint_graph.py:91
summarize_exec_edges(graphs)                                     serializers/blueprint_graph.py:391
BlueprintFamilyHandler (class `handlers_impl.py:873`, `enrich` at `:891`)  parsers/asset_types/handlers_impl.py
project_document(doc, *, view, depth, ...)                       projection.py:118
```

### Deep source audit amendments (2026-09-17)

This section records findings from the current `src/` implementation and the
committed sample probes. It is binding implementation guidance for the tasks
below; it does not claim that the target design is already implemented.

| Current source evidence | Consequence for complete static parsing | Required plan constraint |
|---|---|---|
| `LegacyPackageReader._parse_requested_object_properties()` parses only the requested export ids, while `read_blueprint_graphs()` needs graph-container properties and node exports. With `object_ids=["export:0"]`, the samples still expose the known graphs only because the serializer falls back to an outer-index scan; graph-container `Nodes`/`SubGraphs` properties remain unparsed. | Object selection can change the graph result and silently lose subgraphs or references. | `object_ids` is an output filter, not a decode prerequisite. Build a bounded prerequisite closure for the selected Blueprint/GeneratedClass: graph containers, `Nodes`/`SubGraphs` references, node exports, function graphs, and the minimum generated-class/CDO references needed for ownership. Return only requested objects, but parse/cache the closure. Add selected-vs-full graph equivalence tests. |
| `read_ue_graph_node()` seeks directly to a node export and `_read_node_pins()` reads from a calculated offset without installing the node export's serial end as a read boundary. | A malformed or version-mismatched node can consume bytes belonging to the next export before failing. | Every node read must save/restore the archive range and use `[serial_offset, serial_offset + serial_size)` as a hard boundary. The entire remaining node region becomes a ranged opaque/unavailable record on failure. |
| `graph_pin.py` reads default values, object/text defaults, subpins, parent/pass-through ids, links, and most `FEdGraphPinType` fields, but the current returned pin dict keeps only a small subset. `graph_node.py` also discards FText values and unknown/tag payloads. | The graph cannot provide complete defaults, type/reflection information, or a reliable reconstruction input. | Every consumed field is typed or retained as a ranged opaque field. Include the concrete pin type, masks, terminal/subcategory object refs, defaults, subpin hierarchy, parent/pass-through refs, and raw unsupported values in the graph IR. |
| The current node allowlist names `FunctionReference`, `EventReference`, `MemberName`, `MemberParent`, and `VariableReference`, but the corresponding K2 member-reference readers were removed in the current Wave A code. | Allowlisting a field does not mean it is decoded; call/event/variable correlation can remain empty while tests appear structurally green. | Restore a minimal source-driven K2 metadata decoder with UE version gates for `K2Node_CallFunction`, `K2Node_Event`, `K2Node_VariableGet/Set`, custom events, and dispatcher nodes. Unsupported variants retain an exact opaque range and remain unresolved rather than being guessed. |
| `FKismetArchive.read_expression()` already has both physical serialized offsets and reconstructed UE logical bytecode offsets, but only `StatementIndex` is retained. `read_ufunction_script()` copies the script to a local archive and does not expose the package source range. | Local bytecode offsets can be mislabeled as package offsets; jump targets can be resolved against the wrong coordinate system. | Preserve local physical, package-virtual/source, and UE logical coordinates explicitly. Every function result carries export/object identity and script source range. Never derive ranges again by reparsing in the correlation or projection layers. |
| Several `KismetExpression.from_archive()` implementations consume nested expressions, call parameters, container elements, switch operands, casts/contexts, and constants without storing them; base `to_dict()` emits only `Inst` and `StatementIndex` for classes without an override. | A list of 85 top-level expressions does not imply complete functional content; calls/branches/variables may be present only as lossy opcode shells. | Successful parsing has an operand-preservation invariant: every consumed pointer, scalar, nested expression, optional field, and container element is stored with its semantic role, or as a ranged `OpaqueOperand` with reason/raw reference. Projection must recurse through all operands. Tolerant unknown tokens become addressable opaque instructions; they are never skipped silently. |
| `_attach_kismet_extras()` currently associates successful decompilation results by function name, not export identity. | Duplicate function names can attach bytecode to the wrong export. | The bridge result carries `export_index`, `object_id`, class name, and script source range; attachment is identity-first and name matching is only a documented fallback with a diagnostic. Add a duplicate-name fixture/probe. |
| `MaterialHandler` currently emits only a summary. `BinaryOrNative` dispatch sees `StructProperty` before the concrete `ExpressionInput` struct type, so the existing `_parse_expression_input()` path can be bypassed; `FMaterialAttributesInput` is not covered. | Material links and function inputs remain raw/empty even though the package contains 39 expression exports. A standalone material decoder cannot recover fields that the property reader already discarded. | Dispatch BinaryOrNative structs by concrete `struct_type` before generic raw fallback; add `ExpressionInput` and `MaterialAttributesInput` (including nested function input/output records), then invoke `MaterialGraphDecoder` from the package/domain path and store one projected `semantic["material_graph"]`. Add StackOBot A/B regression tests and a cooked unavailable/limited test. |
| `PropertyValue`/`StructValue` have source offsets, but normalization collapses values to a name-keyed dict; duplicate names and array indices overwrite each other. `PropertyFallback` also loses its source span in the public normalized form. | Complete property coverage cannot be audited, and repeated/array properties cannot be reconstructed. | Task 4's canonical value is an ordered `PropertyBag` of entries retaining occurrence, array index, tag/value ranges, typed value, and opaque payload. A name lookup is a derived convenience view only. Every fallback and unconsumed tail has a source region and diagnostic. |
| Native field parsing consumes flags, metadata, array dimensions, element size, replication index/notify/condition, and related reflection data without retaining them. | The output cannot faithfully support Blueprint Header View-like declarations or reflection-aware C++ generation. | Retain native-field metadata or exact opaque ranged records, and include it in the declaration/migration input. Header View is declaration-scope evidence; migration C++ remains a static semantic reconstruction and must report untranslated/unavailable bodies explicitly. |

Measured sample anchors used by these amendments: StackOBot Blueprint has 31
exports, 2 graphs, 3 Kismet functions, and 85 top-level expressions; the
StackOBot material has 42 exports and 39 `MaterialExpression*` exports; the
UE5.8 Blueprint exposes `NewFunction`, `K2Node_IfThenElse`, and
`EX_JumpIfNot`. These counts are evidence for tests, not proof that the
current implementation preserves all consumed fields.

### Existing IR migration and execution boundary

The current project does not have a single lossless IR module: binary readers
populate `ObjectRecord` and handler-owned dictionaries, while Blueprint and
Kismet extras are attached later. The rebuild treats that as an internal
migration target, not as a public compatibility surface:

| Current path | Rebuilt path | Migration rule |
|---|---|---|
| `PackageDocument` + `ObjectRecord` envelope | same package-first envelope, extended with object refs, diagnostics, ranges, and accounting | preserve package/object identity; never put domain data at the document root |
| handler-owned `semantic` dictionaries | typed `BlueprintSemantic` / `MaterialGraph` / `FunctionAnalysis` during decode and analysis | one owner per IR; no parallel K0/K1 shapes |
| Kismet expression trees and direct exec summaries | lossless expression tree → `BytecodeInstruction` → CFG/correlation | no runtime VM and no control-flow “execution” simulation |
| `project_document()` field formatting | `project_*()` helpers from typed IR and one canonical writer | JSON/CLI/Agent/C++/CSV all consume the same projected document |

Implementation order is therefore: retain the package envelope first, move
binary results into typed domain IR, flip `ObjectRecord.semantic` to stable
JSON dictionaries in Task 8/9, then delete old handler-specific semantic
conversion and string pseudo-code paths in the same commit. No bridge or
backward-compatible adapter is required. A test that only checks an IR object
exists is insufficient; every IR field must be observable in the projected
JSON or in a ranged opaque record.

“执行功能代码” has one precise meaning in this plan: reconstruct event
entrypoints, branch targets, calls, variable reads/writes, dispatchers, and
static CFG edges from serialized graph/Kismet data. It never means invoking a
Blueprint VM, loading Unreal modules, evaluating a Material, executing native
C++, or producing runtime-equivalent behavior.

---

### Task 1: Freeze the new contract and repair the baseline gates — complete

**Files:**
- Modify: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`
- Modify: `docs/designs/README.md`
- Move: `docs/designs/2026-08-31-v2-contract-stability.md` → `docs/designs/archive/2026-08-31-v2-contract-stability.md` (superseded by the intentional v3 break)
- Modify: `docs/designs/archive/README.md`
- Modify: `docs/formats/output/README.md`
- Modify: `docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`
- Create: `docs/designs/contract/package_document_v3.schema.json`
- Create: `docs/designs/contract/package_document_v3.example.json`
- Delete: `docs/designs/contract/package_document_v2.schema.json`
- Delete: `docs/designs/contract/package_document_v2.example.json`
- Modify: `src/uasset_read/projection.py`
- Modify: `tests/test_samples.py` (schema loader path)
- Modify: `tests/size-baseline.json`
- Modify: `tests/test_core.py`
- Create: `tests/test_contract_v3.py`
- Create: `tests/fixtures.py`
- Create: `tests/conftest.py`
- Create: `tests/__init__.py` (make `tests.fixtures` resolve to this repository)
- Test: `tests/test_contract_v3.py`, `tests/test_core.py`, `tests/test_samples.py`, `tests/test_size_baseline.py`

**Interfaces:**
- Consumes: existing `parse_package_document()`, `project_document()`, and current `PackageDocument` fields.
- Produces: projection envelope `format_version == "3.0"`, a policy-based test structure gate, and shared test helpers/fixtures.
- Test helpers: `sample_path`, `parse_sample`, `find_function`, `find_blueprint_object`, and `find_material_graph` with the signatures defined in the File Map.

**Current-state notes (validated):**
- `format_version` is currently an output-envelope field injected in `projection.py`; keep it there rather than adding presentation-version state to `PackageDocument`.
- `tests/test_core.py::test_test_suite_structure_gate` currently locks an exact root test-file list and exact function count. Replace those brittle counts before later tasks add files.
- The current targeted baseline is already red before this plan: the exact list omits the tracked `tests/test_quality_baseline_generator.py`. Treat that as the first policy-gate correction in Step 4, not as a regression caused by the v3 work.
- Size baseline lives at `tests/size-baseline.json` (not under `tests/samples/`).

- [x] **Step 1: Write the failing contract tests**

```python
# tests/test_contract_v3.py
from tests.fixtures import parse_sample
from uasset_read.projection import project_document


def test_rebuilt_document_declares_v3_and_package_first():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="package")
    output = project_document(document, depth="package")
    assert output["format_version"] == "3.0"
    assert isinstance(output["projections"], list)
    assert isinstance(output["sidecars"], list)
    assert document.objects
    assert all(obj.id.startswith(("export:", "import:")) for obj in document.objects)


def test_stackobot_package_counts_match_manifest():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="package")
    assert len(document.objects) == 31
    assert document.package.export_count == 31
```

- [x] **Step 2: Run the focused tests and verify the expected failures**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_contract_v3.py tests/test_core.py::test_test_suite_structure_gate tests/test_size_baseline.py -q`

Expected: the v3 assertion fails against the current hardcoded `"2.0"`, the structure gate fails because `tests/test_contract_v3.py` is not yet in the policy gate, and `tests/test_samples.py` still loads the old schema path.

- [x] **Step 3: Update the canonical design and quality baseline**

In `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`, reconcile the 2026-09-16/17 target with the older Gate K history:
1. pure Python modular rewrite is the next implementation wave;
2. output schema major becomes `format_version: "3.0"`;
3. Blueprint/Kismet public logic becomes instruction IR + CFG + static call/var analysis;
4. C++ declaration/migration projection is derived from that IR and is not a second parser;
5. Gate K retired the old string-based pseudo-code chain; it does not prohibit the new typed v3 projection;
6. Epic Blueprint Header View (`Engine/Plugins/Editor/BlueprintHeaderView/`) is a declaration-scope reference only — it previews a C++ header in the editor UI and does not export `.h`/`.cpp` files.
7. Type-aware projections are the public v3 target: Blueprint declaration/migration, Material graph/editor-builder, table/curve/struct/enum data, and metadata/payload references for physical assets; no asset family is required to produce C++.
8. Every embedded projection has an explicit capability/status and provenance; unavailable or low-confidence information is not replaced with fabricated source.
9. Testing Strategy: replace the historical "五个正式测试文件 / `len(funcs) == N`" lock with the policy gate defined in Step 4; keep no-test-class / no-dynamic-assignment / `tests/samples/`-only-subdir rules unless deliberately retired.

In `docs/designs/README.md`, add this plan + spec as the current target row and
remove the S1 row from the current-design list. Move S1 to
`docs/designs/archive/2026-08-31-v2-contract-stability.md` with an archive banner
that records that v3 intentionally supersedes the v2 stable envelope. Update
`docs/designs/archive/README.md` accordingly. Update `tests/size-baseline.json`
only from measured values after the test tree is corrected — do not invent
counts.

Bump the committed contract schema in the same task. The current v2 schema and
S1 freeze are superseded because this plan intentionally permits a breaking
output rewrite. Create `package_document_v3.schema.json` and
`package_document_v3.example.json`, update every source/test/document reference
in this task, and delete the misleading v2 contract files. The v3 schema pins
`"format_version": {"const": "3.0"}` and updates `$id`, title, and descriptions;
there must be no active loader that validates the new document against a v2
filename or const.

The v3 schema change must add the fields required by the canonical output
contract, not only change the version string. Add required `projections` and
optional `sidecars` properties, plus `$defs/ProjectionRecord` and
`$defs/SidecarRecord`. `ProjectionRecord` validates `source_object_id`,
`kind`, `media_type`, `embedded`, the four projection statuses,
`completeness`, `dependencies`, `diagnostics`, and either embedded `content`
or an `external` sidecar reference. `SidecarRecord` validates relative `path`,
non-negative `size`, 64-character SHA-256, `reason`, and the serialized source
range. Keep `next_offset`/`truncation` valid only for bounded responses; the
canonical writer omits them.

The same schema update must describe the richer object/property envelope:
object records retain `class_ref`, `outer_ref`, `super_ref`, `template_ref`,
per-object diagnostics, serial source ranges, and an ordered `properties`
representation with occurrence/array-index and value ranges. The complete
`byte_accounting` scopes are part of the canonical file; an object cannot be
declared complete merely because its convenience property map is non-empty.

- [x] **Step 4: Implement test support, the policy gate, and the v3 envelope**

1. Create `tests/__init__.py` and `tests/fixtures.py` with ordinary helper functions from the File Map.
2. Create `tests/conftest.py` with the `@pytest.fixture` definitions from the File Map. Do not rely on pytest discovering fixtures from an ordinary module.
3. In `projection.py`, define and emit one projection constant:

```python
FORMAT_VERSION = "3.0"

# inside project_document(...)
result = {
    "format": "uasset_read.package",
    "format_version": FORMAT_VERSION,
    "projections": [],
    "sidecars": [],
    # existing envelope fields continue here
}
```

4. Replace the exact filename/function-count assertions in `test_test_suite_structure_gate` with a policy check, and amend the package-first design Testing Strategy (~the "五个正式测试文件" / `len(funcs) == N` lock language) in the same commit so the written design no longer contradicts the gate. Retain the no-test-class, no-dynamic-`test_*`-assignment, and `tests/samples/`-only-subdir constraints unless a written decision retires them.

```python
def test_test_suite_structure_gate():
    import ast

    root = Path(__file__).parent
    paths = sorted(root.glob("test_*.py"))
    assert paths
    assert {"test_core.py", "test_samples.py", "test_size_baseline.py"} <= {p.name for p in paths}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        collected = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        ]
        assert collected, f"{path.name} contains no test functions"
        assert all(not node.decorator_list for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
```

Do not introduce byte-accounting placeholders in this task; Task 4 adds the model and parser-produced scopes together so an empty list cannot masquerade as completeness.

- [x] **Step 5: Run the gate and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_contract_v3.py tests/test_core.py tests/test_samples.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add docs/designs/2026-08-26-package-first-uasset-parser-refactor.md docs/designs/README.md docs/designs/archive/README.md docs/formats/output/README.md docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md docs/designs/contract/package_document_v3.schema.json docs/designs/contract/package_document_v3.example.json src/uasset_read/projection.py tests/test_samples.py tests/size-baseline.json tests/test_core.py tests/test_contract_v3.py tests/fixtures.py tests/conftest.py tests/__init__.py
git mv docs/designs/2026-08-31-v2-contract-stability.md docs/designs/archive/2026-08-31-v2-contract-stability.md
git rm docs/designs/contract/package_document_v2.schema.json docs/designs/contract/package_document_v2.example.json
git commit -m "refactor: define parser v3 projection contract"
```

### Task 2: Introduce bounded sources and package container inputs — complete

**Files:**
- Create: `src/uasset_read/sources.py`
- Create: `src/uasset_read/containers.py`
- Modify: `src/uasset_read/iostore.py`
- Modify: `src/uasset_read/package.py`
- Create: `tests/test_sources.py`
- Create: `tests/test_containers.py`

**Interfaces:**
- Consumes: existing `FArchive`, `PackageBundle`, `open_package_bundle()`.
- Produces: `ByteSource`, `FileSource`, `MemorySource`, `CompositeSource`, `ContainerEntry`, `ContainerReport`, and `inspect_container(path) -> ContainerReport`. This task does not add `IoStoreChunkSource` or chunk extraction; `open_source` is not a required public name, and Task 3 consumes `ByteSource` only for validated layout detection.

**Current-state notes (validated):**
- `PackageArchive` already splices `.uasset` + `.uexp` and rejects the splice when `main_size != TotalHeaderSize` (`package.py:106-119`, UE basis `AsyncLoading.cpp` / `FilePackageWriterUtil.cpp` cited in the docstring).
- Committed container fixtures are `MyProject-Windows.pak`, `MyProject-Windows.utoc`, `global.utoc`, and `global.ucas`; `MyProject-Windows.ucas` is a hash-pinned local-only fixture and must never be required by the blocking suite.
- `MyProject-Windows.pak` is an IoStore wrapper, not a traditional `FPakFile`; it can prove classification and truthful unavailability, not `PakEntrySource` extraction. Traditional Pak extraction remains unverified until a redistributable FPak fixture is added.
- Existing IoStore TOC reading lives in `src/uasset_read/iostore.py`; do not duplicate TOC parsers. Classification may wrap its existing metadata, but chunk lookup/decompression is deferred until a real package fixture is committed.

- [x] **Step 1: Add failing source boundary tests**

```python
# tests/test_sources.py
import pytest

from uasset_read.exceptions import ParseError
from uasset_read.sources import CompositeSource, MemorySource


def test_composite_source_maps_sidecar_ranges(tmp_path):
    main = tmp_path / "A.uasset"
    sidecar = tmp_path / "A.uexp"
    main.write_bytes(b"HEAD")
    sidecar.write_bytes(b"PAYLOAD")
    source = CompositeSource.from_package(main)
    assert source.read_at(0, 4) == b"HEAD"
    assert source.read_at(4, 7) == b"PAYLOAD"
    assert source.map_range(2, 5) == [("A.uasset", 2, 2), ("A.uexp", 0, 3)]


def test_source_rejects_out_of_bounds_reads():
    source = MemorySource(b"abc")
    with pytest.raises(ParseError):
        source.read_at(2, 2)


def test_memory_source_rejects_negative_offset():
    source = MemorySource(b"abc")
    with pytest.raises(ParseError):
        source.read_at(-1, 1)
```

```python
# tests/test_containers.py
from pathlib import Path

from uasset_read.containers import inspect_container

CONTAINERS = Path(__file__).parent / "samples" / "containers"


def test_utoc_lists_packages_without_ucas_body():
    report = inspect_container(CONTAINERS / "MyProject-Windows.utoc")
    assert report.kind == "iostore"
    assert report.entry_count > 0
    # body availability is explicit; missing/chunked payloads must not pretend success
    assert report.capabilities["chunk_bytes"] in {"available", "unavailable"}


def test_missing_key_is_structured_unavailable():
    report = inspect_container(CONTAINERS / "MyProject-Windows.utoc")
    for diag in report.diagnostics:
        assert diag.code
        assert diag.stage.startswith("container")


def test_iostore_wrapper_is_not_treated_as_traditional_pak():
    report = inspect_container(CONTAINERS / "MyProject-Windows.pak")
    assert report.kind == "iostore_wrapper"
    assert report.capabilities["traditional_pak_entries"] == "unavailable"
```

- [x] **Step 2: Run the tests and confirm missing interfaces fail**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_sources.py tests/test_containers.py tests/test_size_baseline.py -q`

Expected: import or attribute failures for the new source classes.

- [x] **Step 3: Implement the source protocol with explicit ranges**

Create `src/uasset_read/sources.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from uasset_read.archive import SourceInfo
from uasset_read.exceptions import ParseError


@runtime_checkable
class ByteSource(Protocol):
    def read_at(self, offset: int, size: int) -> bytes: ...
    def size(self) -> int | None: ...
    def describe(self) -> SourceInfo: ...
    def map_range(self, offset: int, size: int) -> list[tuple[str, int, int]]: ...


def _validate_range(offset: int, size: int, total: int | None) -> None:
    if offset < 0 or size < 0:
        raise ParseError(f"invalid range offset={offset} size={size}")
    if total is not None and offset + size > total:
        raise ParseError(f"range out of bounds offset={offset} size={size} total={total}")


class MemorySource:
    def __init__(self, data: bytes, *, name: str = "<memory>"):
        self._data = data
        self._name = name

    def read_at(self, offset: int, size: int) -> bytes:
        _validate_range(offset, size, len(self._data))
        return self._data[offset : offset + size]

    def size(self) -> int | None:
        return len(self._data)

    def describe(self) -> SourceInfo:
        return SourceInfo(kind="memory", name=self._name, size=len(self._data))

    def map_range(self, offset: int, size: int) -> list[tuple[str, int, int]]:
        _validate_range(offset, size, len(self._data))
        return [(self._name, offset, size)]


class FileSource:
    def __init__(self, path: Path):
        self._path = Path(path)

    def read_at(self, offset: int, size: int) -> bytes:
        _validate_range(offset, size, self._path.stat().st_size)
        with self._path.open("rb") as fh:
            fh.seek(offset)
            data = fh.read(size)
        if len(data) != size:
            raise ParseError(f"short read from {self._path}: wanted {size}, got {len(data)}")
        return data

    def size(self) -> int | None:
        return self._path.stat().st_size

    def describe(self) -> SourceInfo:
        return SourceInfo(kind="loose", name=self._path.name, size=self.size() or 0, path=str(self._path))

    def map_range(self, offset: int, size: int) -> list[tuple[str, int, int]]:
        _validate_range(offset, size, self.size())
        return [(self._path.name, offset, size)]


class CompositeSource:
    """Virtual package address space over .uasset/.umap + sidecars.

    Segment mapping lists main bytes first, then any present sidecar files
    (.uexp/.ubulk/.uptnl). This class only maps physical segments; it does
    not evaluate the UE split-file invariant. Legacy readers must still
    reject a .uexp splice when main_size != TotalHeaderSize.
    """

    def __init__(
        self,
        segments: list[tuple[str, ByteSource]],
        *,
        name: str = "package",
        payloads: dict[str, ByteSource] | None = None,
    ):
        self._segments = segments
        self._name = name
        self._payloads = payloads or {}
        self._sizes = [src.size() or 0 for _, src in segments]
        self._total = sum(self._sizes)

    @classmethod
    def from_package(cls, main_path: Path) -> "CompositeSource":
        main_path = Path(main_path)
        segments: list[tuple[str, ByteSource]] = [(main_path.name, FileSource(main_path))]
        uexp = main_path.with_suffix(".uexp")
        if uexp.exists():
            segments.append((uexp.name, FileSource(uexp)))
        payloads = {
            ext: FileSource(candidate)
            for ext in (".ubulk", ".uptnl")
            if (candidate := main_path.with_suffix(ext)).exists()
        }
        return cls(segments, name=main_path.name, payloads=payloads)

    def read_at(self, offset: int, size: int) -> bytes:
        _validate_range(offset, size, self._total)
        remaining = size
        cursor = offset
        chunks: list[bytes] = []
        start = 0
        for (seg_name, src), seg_size in zip(self._segments, self._sizes):
            if remaining <= 0:
                break
            if cursor >= start + seg_size:
                start += seg_size
                continue
            local = cursor - start
            take = min(remaining, seg_size - local)
            chunks.append(src.read_at(local, take))
            cursor += take
            remaining -= take
            start += seg_size
        if remaining:
            raise ParseError(f"composite short read at {offset}+{size}")
        return b"".join(chunks)

    def size(self) -> int | None:
        return self._total

    def payload(self, extension: str) -> ByteSource | None:
        return self._payloads.get(extension)

    def segments(self) -> tuple[tuple[str, int, int], ...]:
        segs = []
        acc = 0
        for name, src in self._segments:
            n = src.size() or 0
            segs.append((name, acc, n))
            acc += n
        return tuple(segs)

    def map_range(self, offset: int, size: int) -> list[tuple[str, int, int]]:
        """Map one virtual range to physical ``(source_id, start, size)`` slices."""
        _validate_range(offset, size, self._total)
        result: list[tuple[str, int, int]] = []
        remaining = size
        cursor = offset
        for source_id, virtual_start, segment_size in self.segments():
            virtual_end = virtual_start + segment_size
            if remaining <= 0:
                break
            if cursor >= virtual_end or cursor < virtual_start and cursor + remaining <= virtual_start:
                continue
            local_start = max(cursor, virtual_start)
            local_end = min(cursor + remaining, virtual_end)
            if local_end > local_start:
                result.append((source_id, local_start - virtual_start, local_end - local_start))
                consumed = local_end - cursor
                cursor = local_end
                remaining -= consumed
        if remaining:
            raise ParseError(f"composite range mapping incomplete at {offset}+{size}")
        return result

    def describe(self) -> SourceInfo:
        return SourceInfo(kind="loose", name=self._name, size=self._total)
```

Rules enforced in code:
- non-negative integers only;
- exact-size reads;
- no unbounded `read()` without size;
- `CompositeSource` exposes physical segment mapping; it never pretends `.ubulk` is part of export serial bytes.

`CompositeSource.from_package` may attach any present `.uexp` as a second segment. It does **not** claim the `PackageArchive` `main_size == TotalHeaderSize` splice invariant — that check stays in the Legacy reader (Task 3). Synthetic tests that splice a 4-byte fake package + sidecar are intentionally testing segment mapping only.

- [x] **Step 4: Add container fixtures and diagnostics**

Create `src/uasset_read/containers.py` that wraps existing `iostore.py` metadata parsing and returns classification/availability data only:

```python
@dataclass(frozen=True)
class ContainerEntry:
    entry_id: str
    offset: int
    size: int
    compression: str | None = None


@dataclass
class ContainerReport:
    kind: Literal["traditional_pak", "iostore_wrapper", "iostore", "unknown"]
    path: str
    entry_count: int
    entries: list[ContainerEntry]
    capabilities: dict[str, Literal["available", "unavailable"]]
    diagnostics: list[Diagnostic]


def inspect_container(path: Path) -> ContainerReport:
    """Classify pak/iostore/unknown, count entries, report capabilities + diagnostics.

    Required by tests/test_containers.py. Wraps existing iostore.py TOC iteration;
    does not invent Traditional Pak extraction without an FPak fixture.
    """
```

`iostore.py` changes in this task are limited to exposing TOC entry iteration as data that `inspect_container` can wrap. `package.py` changes are limited to calling `inspect_container` when a `.utoc`/`.pak` path is opened; do not change Legacy loose-package behavior.

Concrete `package.py` wiring for this task only:

```python
def parse_package_document(path, *, depth="decode", object_ids=None, tolerant=True):
    path = Path(path)
    if path.suffix.lower() in {".utoc", ".pak"}:
        report = inspect_container(path)
        # Task 3 may return the explicit Zen-unavailable result here. For Task 2,
        # surface the report
        # as structured unavailability — never a silent Legacy parse of
        # container metadata bytes.
        raise ParseError(
            f"container input not yet parseable as a package: kind={report.kind}",
            code="CONTAINER_PACKAGE_UNSUPPORTED",
            diagnostics=report.diagnostics,
        )
    # existing loose-package path unchanged
    ...
```

Task 2 only classifies and refuses honestly. Task 3 adds validated layout
selection and the explicit Zen-unavailable boundary; it does not parse Zen
tables without a real package fixture.

For committed-suite execution, treat the local-only `MyProject-Windows.ucas` as absent: set `capabilities["chunk_bytes"] = "unavailable"` and emit `CHUNK_BYTES_UNAVAILABLE`. When the hash-pinned local file is present, optional tests may exercise chunk reads, but blocking acceptance cannot depend on it. Missing keys/codecs use `ENCRYPTION_KEY_MISSING` / `COMPRESSION_UNAVAILABLE`. Never fall back to a Legacy parse of a Zen/IoStore package.

Do not implement `PakEntrySource` in this task: there is no traditional FPak fixture to validate it. Add that capability only with a real redistributable fixture and a separate evidence-backed task.

- [x] **Step 5: Run source/container tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_sources.py tests/test_containers.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/sources.py src/uasset_read/containers.py src/uasset_read/iostore.py src/uasset_read/package.py tests/test_sources.py tests/test_containers.py tests/size-baseline.json
git commit -m "feat: add bounded package sources and containers"
```

### Task 3: Separate the Legacy reader and establish the Zen availability boundary — complete

**Files:**
- Create: `src/uasset_read/layout.py`
- Modify: `src/uasset_read/parsers/legacy_reader.py`
- Create: `src/uasset_read/parsers/zen_reader.py`
- Modify: `src/uasset_read/package.py`
- Modify: `src/uasset_read/versioning.py` (define the minimal consumed `VersionContext`)
- Modify: `src/uasset_read/models/object_model.py`
- Modify: `src/uasset_read/models/document.py`
- Create: `tests/test_layout.py`
- Create: `tests/test_zen_reader.py`

**Interfaces:**
- Consumes: `ByteSource`, the minimal `VersionContext`, and existing package summary/table readers.
- Produces: `PackageLayoutDetector.detect(source) -> PackageLayout`, a Legacy read path that keeps `PackageArchive` as its archive owner, and `ZenPackageReader.read_from_container(report, package_id, chunk_source=None, ...) -> ZenReadResult` with an explicit `unavailable` result when package/chunk bytes are not available.

**Fixture limit:** the committed suite contains no real Zen-layout package payload. Task 3 proves validated layout detection and truthful unavailability against committed IoStore metadata only. It must not implement or claim Zen name/import/export/payload parsing from synthetic bytes. Full Zen decoding is a separate follow-up whose entry condition is a redistributable package fixture plus a concrete package/chunk selection API.

**UE source facts (relative to UE root; re-verify if the checkout moves):**

Legacy summary — `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` and serialize in `.../Private/UObject/PackageFileSummary.cpp`:
- `Tag`, `FileVersionUE` (UE4/UE5), `FileVersionLicenseeUE`, custom versions, `PackageFlags`, `TotalHeaderSize`, name/import/export maps with version-gated neighbors (`SoftObjectPaths*`, `GatherableTextData*`, cell maps for VERSE, `PreloadDependency*`, `PayloadTocOffset`, `DataResourceOffset`).

Zen summary — `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h:302-316`:

```text
FZenPackageSummary
  uint32 bHasVersioningInfo
  uint32 HeaderSize
  FMappedName Name
  uint32 PackageFlags
  uint32 _Unused                 // was CookedHeaderSize
  int32  ImportedPublicExportHashesOffset
  int32  ImportMapOffset
  int32  ExportMapOffset
  int32  ExportBundleEntriesOffset
  int32  DependencyBundleHeadersOffset
  int32  DependencyBundleEntriesOffset
  int32  ImportedPackageNamesOffset
```

`FExportBundleEntry` (`AsyncLoading2.h:327-339`): `uint32 LocalExportIndex`, `uint32 CommandType` (`Create=0`, `Serialize=1`).

`FExportMapEntry` (same header): `CookedSerialOffset/Size` (uint64), object name, outer/class/super/template `FPackageObjectIndex`, public export hash, object flags, filter flags + pad.

`FPackageObjectIndex`: `uint64` with 62-bit id + 2-bit type (`Export=0`, `ScriptImport=1`, `PackageImport=2`, `Null=3`; a separate default sentinel `Invalid = ~0ull` is not the Null enum value).

Package trailer — `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageTrailer.h` / `.../Internal/Serialization/PackageWriterToSharedBuffer.h`:
- header tag `0xD1C43B2E80A5F697`;
- footer tag `0x29BFCA045138DE76` + trailer length + `PACKAGE_FILE_TAG`.

In-memory view — `Engine/Source/Runtime/CoreUObject/Internal/Serialization/ZenPackageHeader.h` (`FZenPackageHeader::MakeView`).

Define the layout result types in `layout.py` / `zen_reader.py` before the tests import them:

```python
@dataclass(frozen=True)
class PackageLayout:
    kind: Literal["legacy", "zen", "unknown"]
    detection_reason: str  # "validated_legacy" | "validated_zen" | "unknown"


@dataclass
class ZenReadResult:
    document: PackageDocument | None
    diagnostics: list[Diagnostic]
    status: Literal["unavailable"]
    reason: str | None = None
```

Define `VersionContext` in `src/uasset_read/versioning.py` before Task 4
imports it. Retain the existing `EngineVersion` and `get_custom_version()`
helpers in that module; `VersionContext` is the small per-read value passed to
new readers and handlers, not a replacement version system:

```python
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping


@dataclass(frozen=True)
class VersionContext:
    depth: Literal["package", "object", "asset", "decode"]
    file_version_ue: int | None = None
    file_version_licensee_ue: int | None = None
    custom_versions: Mapping[str, int] = field(default_factory=dict)
    package_layout: Literal["legacy", "zen", "unknown"] = "legacy"
    cooked: bool | None = None
    editor_only_filtered: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "custom_versions",
            MappingProxyType(dict(self.custom_versions)),
        )
```

Keep only fields consumed by the current plan. A new field requires a reader or
handler consumer in the same task; do not add a speculative version container.

During the object-model part of this task, extend `ObjectRecord` without
changing its stable object id format:

```python
class ObjectRecord:
    # existing fields remain addressable
    class_ref: ObjectRef | None
    template_ref: ObjectRef | None
    diagnostics: list[Diagnostic]
```

Populate `class_ref` and `template_ref` from the Legacy export resource and
the Zen export map's `FPackageObjectIndex` fields. Keep `class_name` as the
resolved display name, but never use it as object identity. `PackageDocument`
stores the detected layout and reader diagnostics; widen
`PackageInfo.layout` to `Literal["legacy", "zen", "unknown"]` so an
unrecognized/container-only input cannot be mislabeled. Task 4 adds the
non-empty `byte_accounting` field after property scopes exist.

- [x] **Step 1: Define layout and reader protocol tests**

```python
# tests/test_layout.py
from tests.fixtures import sample_path
from uasset_read.layout import PackageLayoutDetector
from uasset_read.sources import CompositeSource, MemorySource


def test_loose_sample_selects_legacy_reader():
    source = CompositeSource.from_package(sample_path("StackOBot_BP_Drone.uasset"))
    layout = PackageLayoutDetector().detect(source)
    assert layout.kind == "legacy"
    assert layout.detection_reason == "validated_legacy"


def test_reader_selection_does_not_use_ue_major_version_only():
    # Bytes that look nothing like PACKAGE_FILE_TAG and are not a Zen header.
    layout = PackageLayoutDetector().detect(MemorySource(b"NOT_A_PACKAGE!!!!"))
    assert layout.kind == "unknown"
    assert layout.detection_reason == "unknown"
```

```python
# tests/test_zen_reader.py
from pathlib import Path

from uasset_read.containers import inspect_container
from uasset_read.parsers.zen_reader import ZenPackageReader

CONTAINERS = Path(__file__).parent / "samples" / "containers"


def test_zen_reader_reports_unavailable_without_chunk_bytes():
    report = inspect_container(CONTAINERS / "MyProject-Windows.utoc")
    result = ZenPackageReader().read_from_container(
        report,
        package_id="<fixture-package-not-provided>",
        depth="package",
    )
    assert result.document is None
    assert result.status == "unavailable"
    assert result.reason in {"chunk_bytes_unavailable", "zen_package_fixture_unavailable"}
    assert result.diagnostics
    assert all(d.stage.startswith("zen") or d.stage.startswith("container") for d in result.diagnostics)
```

- [x] **Step 2: Run tests to confirm the protocol is absent**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_layout.py tests/test_zen_reader.py tests/test_size_baseline.py -q`

Expected: missing class/protocol failures.

- [x] **Step 3: Implement validated Legacy detection and orchestration**

`PackageLayoutDetector.detect` algorithm:
1. Read first 4 bytes. If they equal `PACKAGE_FILE_TAG` (`0x9E2A83C1`), candidate = legacy.
2. Validate legacy by reading `TotalHeaderSize`, name/import/export counts with bounded reads; reject absurd counts against remaining source size.
3. Else if source is IoStore/Zen package bytes (from container metadata or `FZenPackageSummary` field sanity: `HeaderSize` within source, offset fields monotonic and inside `HeaderSize`), candidate = zen.
4. Else `unknown` — caller must not guess from UE major version or filename.

**Legacy orchestration:** keep the existing `PackageArchive` readers and
`.uexp` splice guard. Add only the layout dispatch and any one local source
adapter required by the new property/range boundary; do not migrate summary,
name, import, export, depends, and preload readers one by one. A source adapter
is deleted in the same task that removes its last caller.

- [x] **Step 4: Implement the explicit Zen unavailable boundary**

`ZenPackageReader` validates that a concrete `package_id` and a readable chunk
source were supplied. With the current committed fixtures it returns
`ZenReadResult(document=None, status="unavailable", reason=...)` and a bounded
diagnostic; it never creates empty objects or a Legacy document. Keep all future
Zen offsets inside `zen_reader.py`; legacy code must not import Zen-only structs.
The real-fixture capability remains `unverified` until a committed Zen package
exercises export-bundle and payload reconstruction end to end.

- [x] **Step 5: Run both reader tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_layout.py tests/test_zen_reader.py tests/test_core.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/layout.py src/uasset_read/parsers/legacy_reader.py src/uasset_read/parsers/zen_reader.py src/uasset_read/package.py src/uasset_read/versioning.py src/uasset_read/models/object_model.py src/uasset_read/models/document.py tests/test_layout.py tests/test_zen_reader.py tests/size-baseline.json
git commit -m "refactor: separate legacy and zen package boundaries"
```

### Task 4: Modularize property decoding and byte accounting — complete

**Files:**
- Create: `src/uasset_read/parsers/properties/__init__.py`
- Create: `src/uasset_read/parsers/properties/tagged.py`
- Create: `src/uasset_read/parsers/properties/unversioned.py`
- Create: `src/uasset_read/parsers/properties/schema.py`
- Create: `src/uasset_read/parsers/properties/opaque.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Modify: `src/uasset_read/parsers/legacy_reader.py`
- Modify: `src/uasset_read/models/properties.py`
- Modify: `src/uasset_read/models/object_model.py`
- Modify: `src/uasset_read/models/diagnostics.py`
- Modify: `src/uasset_read/models/document.py`
- Modify: `src/uasset_read/projection.py`
- Create: `src/uasset_read/models/byte_ranges.py`
- Create: `tests/test_properties.py`
- Create: `tests/test_byte_accounting.py`

**Interfaces:**
- Consumes: bounded object slices, `VersionContext`, mappings, and existing normalized property values.
- Produces: `PropertyInput(source, object_id, start, size, class_name, context)`, an ordered `PropertyBag` carried by `PropertyReadResult`, `OpaqueRegion(start, size, reason, payload_ref)`, and non-empty per-export `ByteScope` leaf coverage attached to `PackageDocument.byte_accounting`.

`ObjectRecord.properties` becomes `PropertyBag | None` in this task. The
reader may expose a read-only convenience mapping for handlers, but the
document model and all lossless projectors use the ordered bag and its ranges.
`ObjectRecord.serial_region` also becomes the canonical `ByteRegion` type in
this task; any legacy `Region` value is converted once at the reader boundary,
not reinterpreted by each handler. `PropertyBag.get()`/`get_all()`/`items()`
form a read-only convenience API, while `entries` remains the source of truth.

**UE source facts:**

Tagged tags — `Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h`, serialize `.../Private/UObject/PropertyTag.cpp`:
- UE5 (`PROPERTY_TAG_COMPLETE_TYPE_NAME`): `Name`, `TypeName` (`FPropertyTypeName`), `Size` (int32), `Flags` (uint8), optional `ArrayIndex`, optional `PropertyGuid`, optional extensions. `Name == None` ends the stream.
- Older path: `LoadPropertyTagNoFullType` (Type/Name/Size/ArrayIndex/BoolVal/HasPropertyGuid).
- `EPropertyTagSerializeType`: `Unknown`, `Skipped`, `Property`, `BinaryOrNative`.

Unversioned header — class name is `FUnversionedHeader` in `.../Private/Serialization/UnversionedPropertySerialization.cpp:690-711`:

```text
uint16 fragment:
  bits 0-6   SkipNum      (max 127)
  bit  7     HasAnyZeroes
  bit  8     IsLast
  bits 9-15  ValueNum     (max 127)
optional zero-mask after fragments: uint8 (<=8), uint16 (<=16), else uint32 words
```

Current unversioned proof already lives in `tests/test_unversioned_fixtures.py` (usmap-backed DA values, CDO scalars, whole-region opaque for unmapped classes). Preserve those behaviors while relocating the state machine.

- [x] **Step 1: Write strict tagged/unversioned tests**

```python
# tests/test_properties.py
from uasset_read.parsers.properties.tagged import TaggedPropertyReader
from uasset_read.parsers.properties.unversioned import UnversionedPropertyReader
from uasset_read.parsers.properties.unversioned import parse_unversioned_header
from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.models.properties import PropertyBag, PropertyEntry, project_property_bag, project_property_entries


def test_tagged_reader_reports_consumed_boundary(tagged_fixture):
    result = TaggedPropertyReader().read(tagged_fixture)
    assert result.consumed >= 0
    assert result.regions[-1].end == tagged_fixture.start + result.consumed


def test_unversioned_reader_does_not_guess_without_schema(unversioned_fixture):
    result = UnversionedPropertyReader(schema=None).read(unversioned_fixture)
    assert result.status in {"opaque", "unavailable"}
    assert result.diagnostics[0].reason == "schema_required"


def test_unversioned_fragment_bit_layout_synthetic():
    # Synthetic fragment: SkipNum=0, HasAnyZeroes=0, IsLast=1, ValueNum=1
    # packed as ValueNum<<9 | IsLast<<8 = 0x0200
    raw = (0x0200).to_bytes(2, "little")
    header = parse_unversioned_header(raw)
    assert header.fragments[0].value_num == 1
    assert header.fragments[0].is_last is True


def duplicate_bag():
    return PropertyBag(entries=[
        PropertyEntry("Tags", "ArrayProperty", "A", 0, None, ByteRegion(0, 1, "decoded")),
        PropertyEntry("Tags", "ArrayProperty", "B", 1, None, ByteRegion(1, 1, "decoded")),
    ])


def test_property_bag_preserves_duplicate_names_and_array_indices():
    entries = duplicate_bag().get_all("Tags")
    assert [item.array_index for item in entries] == [0, 1]
    assert [item.value_region for item in entries]


def test_known_expression_input_does_not_fall_back_to_generic_struct_bytes(stackobot_material):
    entries = [
        entry
        for obj in stackobot_material.objects
        if obj.properties
        for entry in obj.properties.entries
    ]
    entry = next(item for item in entries if isinstance(item.value, dict) and item.value.get("expression_ref") is not None)
    expression_input = entry.value
    assert expression_input["expression_ref"] is not None
    assert "output_index" in expression_input
    assert entry.value_region is not None


def test_projection_keeps_complete_entries_alongside_lookup_map():
    bag = duplicate_bag()
    projected = project_property_bag(bag)
    entries = project_property_entries(bag)
    assert projected["Tags"] == entries[-1]["value"]
    assert len([item for item in entries if item["name"] == "Tags"]) == 2
```

```python
# tests/test_byte_accounting.py
from tests.fixtures import parse_sample


def test_every_requested_export_scope_is_fully_tiled():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    scopes = document.byte_accounting.scopes
    expected = {obj.id for obj in document.objects if obj.serial_region and obj.serial_region.size > 0}
    assert expected
    assert expected <= set(scopes)
    for object_id in expected:
        scope = scopes[object_id]
        assert scope.leaves, f"{object_id} has no accounting leaves"
        scope.validate_full_coverage()


def test_unknown_tail_is_a_reasoned_leaf():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    for scope in document.byte_accounting.scopes.values():
        for leaf in scope.leaves:
            assert leaf.status in {"decoded", "opaque", "payload", "unavailable"}
            assert leaf.size > 0
            assert leaf.status == "decoded" or leaf.reason


def test_file_backed_leaf_preserves_physical_source_mapping():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    leaves = [leaf for scope in document.byte_accounting.scopes.values() for leaf in scope.leaves]
    assert leaves
    assert all(leaf.source_id for leaf in leaves)
    assert all(leaf.source_start is not None for leaf in leaves)


def test_cross_segment_region_retains_all_physical_slices(fake_source):
    from uasset_read.models.byte_ranges import region_from_source

    region = region_from_source(fake_source, start=2, size=5, status="decoded")
    assert [(item.source_id, item.size) for item in region.source_slices] == [
        ("A.uasset", 2),
        ("A.uexp", 3),
    ]
```

To keep the synthetic test runnable without a full package, implement `parse_unversioned_header(data: bytes) -> UnversionedHeader` as a pure function and have `UnversionedPropertyReader` call it.

Define the lossless property value model in `models/properties.py`:

```python
from dataclasses import dataclass, field
from typing import Any

from uasset_read.models.byte_ranges import ByteRegion


@dataclass(frozen=True)
class PropertyEntry:
    name: str
    type_name: str
    value: Any
    array_index: int | None
    tag_region: ByteRegion | None
    value_region: ByteRegion | None


@dataclass
class PropertyBag:
    """Ordered lossless occurrences; name lookup is only a derived view."""
    entries: list[PropertyEntry] = field(default_factory=list)

    def get(self, name: str, default: Any = None) -> Any: ...
    def get_all(self, name: str) -> list[PropertyEntry]: ...
    def items(self): ...
    def __len__(self) -> int: ...
    def __bool__(self) -> bool: ...


def project_property_value(value: Any) -> Any: ...


def project_property_entries(bag: PropertyBag) -> list[dict[str, Any]]: ...


def project_property_bag(bag: PropertyBag) -> dict[str, Any]: ...
```

Define the shared bounded reader input/result in `parsers/properties/__init__.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Literal

from uasset_read.models.byte_ranges import ByteRegion
from uasset_read.models.properties import PropertyBag


@dataclass(frozen=True)
class PropertyInput:
    source: ByteSource
    object_id: str
    start: int
    size: int
    class_name: str
    context: VersionContext


@dataclass
class PropertyReadResult:
    values: PropertyBag
    consumed: int
    regions: list[ByteRegion]
    diagnostics: list[Diagnostic]
    status: Literal["complete", "partial", "opaque", "unavailable", "failed"]
```

`start`/`size` and every `ByteRegion.start`/`size` use the package's virtual
address space so an export can be tiled even when it crosses `.uasset` and
`.uexp`. Every region also records the physical source mapping:

```python
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class SourceSlice:
    source_id: str
    source_start: int
    size: int


@dataclass(frozen=True)
class ByteRegion:
    start: int                         # package-virtual coordinate
    size: int
    status: Literal["decoded", "opaque", "payload", "unavailable"]
    source_id: str = "package"       # e.g. Main.uasset, Main.uexp, Main.ubulk
    source_start: int | None = None   # physical offset in source_id
    source_slices: tuple[SourceSlice, ...] = ()  # all slices when a range crosses segments
    reason: str | None = None
    feature: str = ""
    payload_ref: str | None = None

    @property
    def end(self) -> int:
        return self.start + self.size

    @property
    def source_end(self) -> int | None:
        return None if self.source_start is None else self.source_start + self.size


def project_region(region: ByteRegion | None) -> dict[str, Any] | None:
    if region is None:
        return None
    return {
        "start": region.start,
        "size": region.size,
        "end": region.end,
        "source_id": region.source_id,
        "source_start": region.source_start,
        "source_end": region.source_end,
        "source_slices": [
            {
                "source_id": item.source_id,
                "source_start": item.source_start,
                "size": item.size,
                "source_end": item.source_start + item.size,
            }
            for item in region.source_slices
        ],
        "status": region.status,
        "reason": region.reason,
        "feature": region.feature,
        "payload_ref": region.payload_ref,
    }


def region_from_source(
    source: Any,
    start: int,
    size: int,
    *,
    status: Literal["decoded", "opaque", "payload", "unavailable"],
) -> ByteRegion:
    mapped = source.map_range(start, size)  # CompositeSource boundary
    slices = tuple(SourceSlice(*item) for item in mapped)
    if len(slices) == 1:
        return ByteRegion(
            start=start,
            size=size,
            status=status,
            source_id=slices[0].source_id,
            source_start=slices[0].source_start,
            source_slices=slices,
        )
    return ByteRegion(
        start=start,
        size=size,
        status=status,
        source_id="composite",
        source_start=None,
        source_slices=slices,
    )


```

`models/properties.py` owns the implementations of `project_property_value()`,
`project_property_entries()`, and `project_property_bag()`. They must preserve
typed nested values and opaque payload references; the convenience map may
overwrite duplicate names only because the complete ordered `property_entries`
list remains alongside it. `models/byte_ranges.py` owns only ranges, physical
mapping, and byte scopes.

`source_start` is mandatory for file-backed regions after reader construction
and may be `None` only for synthetic unit-test regions. `ByteScope` validates
coverage in virtual coordinates while serialization exposes both coordinates.
For a region crossing `.uasset`/`.uexp` or another composite boundary,
`source_slices` is mandatory and contains every physical segment; the singular
`source_id`/`source_start` fields are only a convenience for one-segment
regions. Byte-accounting leaves are split at physical segment boundaries;
semantic ranges may remain compound and use `source_slices`. This prevents a
sidecar or C++ diagnostic from claiming that a virtual `.uexp` offset is a
physical `.uasset` offset.

- [x] **Step 2: Run focused tests and verify failure**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_properties.py tests/test_byte_accounting.py tests/test_unversioned_fixtures.py tests/test_size_baseline.py -q`

Expected: missing reader/result classes or incorrect schema behavior.

- [x] **Step 3: Move tagged parsing into a bounded state machine**

Create `parsers/properties/tagged.py`:
- iterate tags until `Name is None`;
- record each tag's `[start, end)` region;
- parse values via existing type dispatch from `property_parser.py` / `property_types.py` (do not rewrite every scalar);
- invoke registered bounded BinaryOrNative/native decoders before falling back; only an unknown or failed decoder, skipped value, or unsupported control bit becomes an `OpaqueRegion` with reason;
- never read past the export serial slice.

Ownership boundary after this step (do not leave two entry points that both claim to parse a tagged stream):

| Module | Owns | Does not own |
|---|---|---|
| `parsers/properties/tagged.py` | tag loop, region recording, stop condition, opaque fallback | scalar/struct value decoding |
| `parsers/property_parser.py` | value dispatch for a single known tag (`read_property_value(tag, input)`); `CUSTOM_PROPERTY_HANDLERS` stays here | iterating tags; choosing tagged vs unversioned |
| `parsers/property_types.py` | per-type scalar/container readers | stream-level state |
| `parsers/properties/unversioned.py` | fragment header, schema-driven field walk | tagged tags |
| `parsers/legacy_reader.py` | choosing tagged vs unversioned for an export and attaching results to `ObjectRecord` | either state machine's internals |

`TaggedPropertyReader.read(input: PropertyInput) -> PropertyReadResult` is the only public tagged entry. It calls into `property_parser` for each value and folds every consumed range into `result.regions`. The old monolithic `property_parser.parse_properties(...)` entry is deleted or reduced to a thin re-export in the same commit once `LegacyPackageReader` is the only caller.

Replace the current `normalize_property_bag()` lossy name-keyed result with a
lossless `PropertyBag` on `ObjectRecord.properties`. If existing handlers need
fast lookup, expose `PropertyBag.get()`/`get_all()` and keep
`project_property_bag()` as a presentation-only convenience map; no parser or
domain decoder may use the map as its source of truth.

The replacement keeps the current parser's source coordinates:

```python
def normalize_property_bag(
    properties: Sequence[Any],
    *,
    package_source: Any,
    object_id: str,
) -> PropertyBag:
    """Convert every parsed occurrence; never key the result by name."""
```

For a `PropertyValue`, copy `name`, `type`, `value`, `array_index`,
`tag_start_offset`, `value_start_offset`, and `value_end_offset` into one
`PropertyEntry`; for `PropertyFallback`, create an opaque entry with its
declared size and exact value range. Preserve entries whose names repeat and
record a diagnostic for a missing/invalid range instead of silently skipping
them.

Known binary/native structures that already have a bounded decoder must remain
structured at this boundary. In particular, `FExpressionInput` and
`FMaterialAttributesInput` values must preserve JSON-safe fields such as
`expression_ref`, `output_index`, `input_name`, and channel masks, together
with their source region. Only genuinely unknown bytes become an opaque leaf.
Add a regression that parses a material expression input and asserts these
fields survive the property reader and `normalize_property_bag()`; Task 9 is
not allowed to reparse the original bytes to recover them. Extend
`Diagnostic.reason` with `schema_required` in this task because the unversioned
reader uses that stable reason.

Concrete dispatch rule: for a BinaryOrNative `StructProperty`, inspect the
concrete `struct_type` before the generic `StructProperty` raw fallback. Route
`ExpressionInput`/`FExpressionInput`, `MaterialAttributesInput`/
`FMaterialAttributesInput`, and nested material function input/output structs
(`FunctionExpressionInput` / `FunctionExpressionOutput`) to bounded native
decoders. Their output must retain expression object identity, output/input
names, output index, channel masks, and any `UseConstant`/constant fields
defined by the UE struct. A generic raw result for a known concrete struct is
a test failure, not an acceptable partial result. Duplicate property names and
array elements must remain separate `PropertyEntry` records; handlers may use
`PropertyBag.get()` only as a convenience projection.

- [x] **Step 4: Implement schema-backed unversioned parsing**

Create `parsers/properties/unversioned.py` + `schema.py`:
- header fragments per UE layout above;
- schema lookup is explicit (`SchemaProvider.fields_for(class_path, context)`);
- no schema → stop at safe boundary, remaining range becomes opaque with `reason="schema_required"`;
- never infer field width from following bytes;
- keep `mappings.py` / usmap path as the first real `SchemaProvider` implementation.

```python
class SchemaProvider(Protocol):
    def fields_for(self, class_path: str, context: VersionContext) -> list[SchemaField] | None: ...


class UsmapSchemaProvider:
    """First real implementation; wraps the existing usmap/mappings path."""
    def fields_for(self, class_path: str, context: VersionContext) -> list[SchemaField] | None:
        ...
```

`UnversionedPropertyReader(schema: SchemaProvider | None)` never guesses. When `schema` is `None` or the class is unmapped, the whole remaining range becomes one opaque leaf with `reason="schema_required"` — matching the existing `tests/test_unversioned_fixtures.py` whole-region-opaque behavior for unmapped classes.

Define byte accounting in `models/byte_ranges.py` and attach it to `PackageDocument` in this task, not earlier as an empty placeholder:

```python
@dataclass
class ByteScope:
    scope_id: str
    start: int
    size: int
    leaves: list[ByteRegion] = field(default_factory=list)

    def validate_full_coverage(self) -> None:
        if not self.leaves:
            raise ValueError(f"{self.scope_id}: no accounting leaves")
        cursor = self.start
        for leaf in sorted(self.leaves, key=lambda item: item.start):
            if leaf.size <= 0 or leaf.start != cursor:
                raise ValueError(f"{self.scope_id}: gap/overlap at {cursor}")
            cursor = leaf.end
        if cursor != self.start + self.size:
            raise ValueError(f"{self.scope_id}: coverage ends at {cursor}")


@dataclass
class ByteAccounting:
    scopes: dict[str, ByteScope] = field(default_factory=dict)


# Canonical opaque-region type. Use this name everywhere Tasks 4/6/9 mention
# OpaqueRegion; do not invent a second model beside ByteRegion.
OpaqueRegion = ByteRegion  # status must be "opaque"


def opaque_region(
    start: int,
    size: int,
    reason: str,
    *,
    source_id: str = "package",
    source_start: int | None = None,
    feature: str = "",
    payload_ref: str | None = None,
) -> ByteRegion:
    return ByteRegion(
        start=start,
        size=size,
        status="opaque",
        source_id=source_id,
        source_start=source_start,
        reason=reason,
        feature=feature,
        payload_ref=payload_ref,
    )
```

`LegacyPackageReader` creates one scope for every requested export with a non-empty serial region. Tagged/unversioned/native-tail readers contribute non-overlapping leaves. Any unconsumed remainder becomes one reasoned `opaque` or `unavailable` leaf, so full coverage cannot pass through an empty collection.

- [x] **Step 5: Run property and hardening tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_properties.py tests/test_byte_accounting.py tests/test_unversioned_fixtures.py tests/test_parse_hardening.py tests/test_memory_safety.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/parsers/properties src/uasset_read/parsers/property_parser.py src/uasset_read/parsers/legacy_reader.py src/uasset_read/models/properties.py src/uasset_read/models/object_model.py src/uasset_read/models/document.py src/uasset_read/models/byte_ranges.py src/uasset_read/projection.py tests/test_properties.py tests/test_byte_accounting.py tests/size-baseline.json
git commit -m "refactor: separate property readers and account export bytes"
```

### Task 5: Extract the existing handler registry into one domain dispatch path

**Files:**
- Create: `src/uasset_read/parsers/asset_types/registry.py`
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`
- Modify: `src/uasset_read/parsers/legacy_reader.py`
- Modify: `tests/test_handler_capability_ledger.py`
- Modify: `tests/test_core.py` (every `run_handlers` unpack site)
- Create: `tests/test_handler_registry.py`

**Interfaces:**
- Consumes: the existing handler objects with `supports(...)` and `enrich(...)`, `ObjectRecord`, depth, all objects, and package context.
- Produces: the single `_HANDLERS` collection plus `register_handler`, `get_handlers`, and `run_handlers(...) -> DomainResult` in `registry.py`.

**Current-state notes:**
- A registry already exists in `handlers_impl.py` as `_HANDLERS`, `register_handler`, `get_handlers`, and `run_handlers`. This task moves that code; it does not layer `AssetDecoderRegistry` over it.
- `tests/test_handler_capability_ledger.py` imports `_HANDLERS`; update that import to the new owning module while preserving the pinned class coverage.
- `run_handlers` currently returns a 3-tuple and is unpacked at ~20 sites in `tests/test_core.py` (`semantic, _cov, _diags = H.run_handlers(...)` around lines 1109, 1119, 1134, 1412, 1430, 1469, 1494, 1518, 1546, 1621, 1661–1665, 1760–1763, 1845–1847) plus `legacy_reader.py`. Changing the return type to `DomainResult` is a repo-wide break, not a single-file refactor.

- [ ] **Step 1: Write single-owner and failure-isolation tests**

```python
# tests/test_handler_registry.py
from uasset_read.parsers.asset_types import handlers_impl, registry
from uasset_read.parsers.asset_types.registry import get_handlers, run_handlers


def test_registry_has_one_owner():
    assert get_handlers()
    assert not hasattr(handlers_impl, "_HANDLERS")


def test_unknown_handler_is_not_applicable_not_failed(unknown_object_record, package_context):
    result = run_handlers(unknown_object_record, "decode", [], package_context)
    assert result.status == "not_requested"
    assert result.reason == "no_domain_decoder"


def test_one_handler_failure_records_diagnostic_and_continues(unknown_object_record, package_context, monkeypatch):
    class Failing:
        def supports(self, obj, depth):
            return True

        def enrich(self, obj, depth, all_objects, context):
            raise ValueError("boom")

    class Succeeding:
        capability = "decoded"

        def supports(self, obj, depth):
            return True

        def enrich(self, obj, depth, all_objects, context):
            return {"succeeded": True}

    monkeypatch.setattr(registry, "_HANDLERS", [Failing(), Succeeding()])
    result = run_handlers(unknown_object_record, "decode", [], package_context)
    assert any(d.code == "HANDLER_FAILURE" for d in result.diagnostics)
    assert result.semantic == {"succeeded": True}
    assert result.status == "partial"
```

- [ ] **Step 2: Run the tests and verify the ownership test fails**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_handler_registry.py tests/test_size_baseline.py -q`

Expected: import failure for `registry.py` or `_HANDLERS` still owned by `handlers_impl.py`.

- [ ] **Step 3: Move the current registry without creating a second abstraction**

```python
@dataclass
class DomainResult:
    status: Literal["complete", "partial", "unavailable", "not_requested"]
    semantic: dict[str, Any] | None = None
    coverage: list[CoverageEntry] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    reason: str | None = None
```

Move `_HANDLERS`, `register_handler`, `get_handlers`, and the dispatch loop verbatim into `registry.py`, then change its return value from the current tuple to `DomainResult`. Keep handler classes in `handlers_impl.py`; they import only `register_handler`. Update `legacy_reader.py` to consume `DomainResult`. There is no compatibility adapter and no `AssetDecoderRegistry` class.

In the same commit, migrate every `run_handlers` unpack site in `tests/test_core.py` from `semantic, _cov, _diags = run_handlers(...)` to `result = run_handlers(...); result.semantic / result.coverage / result.diagnostics`. Do not leave a dual-return shim; the suite must be green under `DomainResult` only. Update imports that still pull `run_handlers` from `handlers_impl` to the new registry module.

Dispatch rules:
- no matching handler returns `not_requested`, because lack of domain enrichment is not a structural parse failure;
- a matching handler exception emits `HANDLER_FAILURE` and makes that object's result partial/unavailable as appropriate;
- later matching handlers still run;
- the package envelope and unrelated objects remain intact.

- [ ] **Step 4: Run handler regressions and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_handler_registry.py tests/test_handler_capability_ledger.py tests/test_capability_hardening.py tests/test_core.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/parsers/asset_types/registry.py src/uasset_read/parsers/asset_types/handlers_impl.py src/uasset_read/parsers/legacy_reader.py tests/test_handler_registry.py tests/test_handler_capability_ledger.py tests/test_core.py tests/size-baseline.json
git commit -m "refactor: give domain handlers one registry owner"
```

### Task 6: Build the Blueprint graph IR

**Files:**
- Create: `src/uasset_read/parsers/blueprint/__init__.py`
- Create: `src/uasset_read/parsers/blueprint/graph.py`
- Create: `src/uasset_read/serializers/k2_metadata.py`
- Modify: `src/uasset_read/serializers/blueprint_graph.py`
- Modify: `src/uasset_read/serializers/graph_node.py`
- Modify: `src/uasset_read/serializers/graph_pin.py`
- Modify: `src/uasset_read/parsers/legacy_reader.py` (pass the open source into the decoder and preserve the selected-owner prerequisite closure)
- Create: `src/uasset_read/models/analysis.py`
- Create: `tests/test_blueprint_ir.py`
- Create: `tests/test_k2_metadata.py`

**Interfaces:**
- Consumes: an open `ByteSource`/bounded object slice and the current graph/node/pin serializers.
- Produces: `BlueprintGraphDecoder.decode(obj, document, *, source) -> list[BlueprintGraph]`, owner-aware `NodeId`, raw `PinLinkRef`, resolved `PinLink`, `K2NodeMetadata`, and `resolve_pin_links(nodes, refs)`.

`read_blueprint_graphs()` remains the raw binary serializer boundary and keeps
returning `list[dict[str, Any]]`; `BlueprintGraphDecoder` is the single
dict-to-typed-IR conversion boundary. This avoids rewriting all existing raw
serializer tests while still giving the analysis layer a typed model. The
decoder always receives the open source explicitly from the package read
pipeline; it never reparses a closed `PackageDocument` or relies on a hidden
path reopen.

K2 metadata has one narrow binary-reader boundary:

```python
class K2MetadataDecoder:
    def decode(
        self,
        node_export: Any,
        archive: FArchive,
        *,
        context: VersionContext,
    ) -> K2NodeMetadata: ...
```

It reads only the version-gated member/event/variable/dispatcher fields for
known K2 node classes. It does not become a general node serializer; the
remaining node fields stay owned by `graph_node.py` and the graph IR.
The gates must be keyed from the existing `VersionContext`/custom-version
helpers, including the UE source branches represented by
`VER_UE4_VARK2NODE_USE_MEMBERREFSTRUCT`,
`VER_UE4_SWITCH_CALL_NODE_TO_USE_MEMBER_REFERENCE`,
`VER_UE4_MEMBERREFERENCE_IN_PINTYPE`,
`VER_UE4_K2NODE_EVENT_MEMBER_REFERENCE`, and
`VER_UE4_K2NODE_VAR_REFERENCEGUIDS`; do not use a UE major-version shortcut.

**Current-state notes:**
- StackOBot already proves 2 graphs (`EventGraph` 14 nodes, `UserConstructionScript` 1 node) and addressable `export:` node ids (`tests/test_blueprint_decode.py:24-40`, `:623-631`).
- Presentation caps already exist: 512 graphs / 512 nodes / 64 pins (`serializers/blueprint_graph.py:34-36`). They must not limit canonical decode; retain only validated resource budgets and record an opaque tail when a caller explicitly supplies a bounded view.
- `summarize_exec_edges` already emits owner-aware undirected-unique exec edges (`blueprint_graph.py:391`); keep it as a derived summary, not runtime order.
- Current `resolve_pin_links(graphs: list[dict]) -> None` mutates raw serializer dicts in place (`serializers/blueprint_graph.py` around `:310`). Keep that helper as the raw serializer's internal operation and add the typed `(nodes, refs) -> LinkResolution` API in `parsers/blueprint/graph.py`; do not make the typed decoder depend on a second byte parser.

- [ ] **Step 1: Add graph identity and duplicate-GUID tests**

```python
# tests/test_blueprint_ir.py
from uasset_read.parsers.blueprint.graph import BlueprintGraphDecoder, resolve_pin_links
from uasset_read.models.analysis import BlueprintNode, BlueprintPin, NodeId, PinLinkRef


def test_graph_identity_includes_owner_for_duplicate_guids():
    first = NodeId(owner_object_id="export:0", node_export_id="export:9")
    second = NodeId(owner_object_id="export:1", node_export_id="export:9")
    assert first != second
    assert str(first) == "export:0/export:9"


def _node(node_id: NodeId) -> BlueprintNode:
    pin = BlueprintPin(
        id="same-pin",
        name="exec",
        direction="output",
        category="exec",
        subcategory="",
        default_value=None,
        default_object_ref=None,
        default_text=None,
        sub_pin_ids=[],
        parent_pin_id=None,
        reference_pass_through_pin_id=None,
        linked=[],
        owner_node_id=node_id,
        raw_region=None,
        unknown_properties=[],
    )
    return BlueprintNode(
        id=node_id,
        guid="same",
        class_name="SyntheticNode",
        title="SyntheticNode",
        metadata=None,
        pins=[pin],
        raw_region=None,
        unknown_properties=[],
    )


def test_duplicate_pin_guid_resolves_by_owner():
    left = _node(NodeId("export:0", "export:9"))
    right = _node(NodeId("export:1", "export:10"))
    ref = PinLinkRef(
        from_node_id=left.id,
        from_pin_guid="same-pin",
        to_owner_node_id=right.id,
        to_pin_guid="same-pin",
    )
    result = resolve_pin_links([left, right], [ref])
    assert result.links[0].to_node_id == right.id
    assert result.links[0].raw_ref == ref
    assert not result.diagnostics


def test_stackobot_graph_names_and_kinds(stackobot_document, stackobot_source):
    obj = next(o for o in stackobot_document.objects if o.id == "export:0")
    graphs = {g.name: g for g in BlueprintGraphDecoder().decode(obj, stackobot_document, source=stackobot_source)}
    assert set(graphs) == {"EventGraph", "UserConstructionScript"}
    assert graphs["EventGraph"].kind == "event_graph"
    assert graphs["UserConstructionScript"].kind == "construction_script"
    assert len(graphs["EventGraph"].nodes) == 14


def test_selected_owner_uses_same_graph_dependency_closure_as_full_decode():
    full = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    selected = parse_sample(
        "StackOBot_BP_Drone.uasset",
        depth="decode",
        object_ids=["export:0"],
    )
    full_owner = next(obj for obj in full.objects if obj.id == "export:0")
    selected_owner = next(obj for obj in selected.objects if obj.id == "export:0")
    assert (full_owner.semantic or {}).get("graphs") == (selected_owner.semantic or {}).get("graphs")
```

```python
# tests/test_k2_metadata.py
from uasset_read.parsers.blueprint.graph import BlueprintGraphDecoder


def test_ue58_k2_reference_metadata_is_not_only_an_allowlisted_tag(ue58_blueprint_document, ue58_source):
    nodes = [
        node
        for obj in ue58_blueprint_document.objects
        for graph in BlueprintGraphDecoder().decode(obj, ue58_blueprint_document, source=ue58_source)
        for node in graph.nodes
        if node.class_name in {
            "K2Node_CallFunction",
            "K2Node_Event",
            "K2Node_VariableGet",
            "K2Node_VariableSet",
        }
    ]
    assert nodes
    assert all(node.metadata is not None for node in nodes)


def test_k2_metadata_unknown_variant_record_is_ranged_and_unresolved():
    from uasset_read.models.byte_ranges import opaque_region
    from uasset_read.models.analysis import K2NodeMetadata

    metadata = K2NodeMetadata(
        node_class="K2Node_Event",
        opaque_properties=[opaque_region(10, 4, "unsupported_k2_variant")],
    )
    assert metadata.opaque_properties
    assert all(item.size > 0 for item in metadata.opaque_properties)
```

- [ ] **Step 2: Run graph tests and verify the new IR is absent**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_ir.py tests/test_blueprint_graph.py tests/test_k2_metadata.py tests/test_size_baseline.py -q`

Expected: missing IR classes or identity assertions fail.

- [ ] **Step 3: Define graph dataclasses and stable IDs**

In `models/analysis.py`:

```python
@dataclass(frozen=True)
class GraphId:
    owner_export_index: int
    graph_export_index: int

    def __str__(self) -> str:
        return f"export:{self.owner_export_index}/export:{self.graph_export_index}"


@dataclass(frozen=True)
class NodeId:
    owner_object_id: str
    node_export_id: str

    def __str__(self) -> str:
        return f"{self.owner_object_id}/{self.node_export_id}"


@dataclass
class K2NodeMetadata:
    node_class: str
    function_name: str | None = None
    event_name: str | None = None
    variable_name: str | None = None
    dispatcher_name: str | None = None
    member_parent: str | None = None
    member_reference: dict[str, Any] | None = None
    opaque_properties: list[OpaqueRegion] = field(default_factory=list)


@dataclass
class BlueprintNode:
    id: NodeId
    guid: str | None
    class_name: str
    title: str
    metadata: K2NodeMetadata | None
    pins: list[BlueprintPin]
    raw_region: ByteRegion | None
    unknown_properties: list[OpaqueRegion]


@dataclass
class BlueprintPin:
    id: str
    name: str
    direction: str
    category: str
    subcategory: str
    default_value: Any | None
    default_object_ref: str | None
    default_text: Any | None
    sub_pin_ids: list[str]
    parent_pin_id: str | None
    reference_pass_through_pin_id: str | None
    linked: list["PinLink"]
    owner_node_id: NodeId
    raw_region: ByteRegion | None
    unknown_properties: list[OpaqueRegion]


@dataclass(frozen=True)
class PinLinkRef:
    from_node_id: NodeId
    from_pin_guid: str
    to_owner_node_id: NodeId | None
    to_pin_guid: str


@dataclass(frozen=True)
class PinLink:
    from_node_id: NodeId
    from_pin_id: str
    to_node_id: NodeId
    to_pin_id: str
    raw_ref: PinLinkRef


@dataclass
class LinkResolution:
    links: list[PinLink]
    diagnostics: list[Diagnostic]


@dataclass
class BlueprintGraph:
    id: GraphId
    name: str
    kind: Literal["event_graph", "function", "construction_script", "macro", "ubergraph", "unknown"]
    nodes: list[BlueprintNode]
    parse_errors: list[str]
    raw_region: ByteRegion | None
    truncated: bool = False
```

Identity rule: package/export identity is primary; Node GUID is an attribute and never the sole key.

The document-boundary graph projection is a dictionary, not a dataclass. Use
these explicit helpers so ranges and unresolved link identity are not lost:

```python
from uasset_read.models.byte_ranges import project_region


def project_opaque(region: OpaqueRegion) -> dict[str, Any]:
    return project_region(region) or {}


def project_pin_link(link: PinLink) -> dict[str, Any]:
    return {
        "from_node_id": str(link.from_node_id),
        "from_pin_id": link.from_pin_id,
        "to_node_id": str(link.to_node_id),
        "to_pin_id": link.to_pin_id,
        "raw_ref": {
            "from_node_id": str(link.raw_ref.from_node_id),
            "from_pin_guid": link.raw_ref.from_pin_guid,
            "to_owner_node_id": (
                str(link.raw_ref.to_owner_node_id)
                if link.raw_ref.to_owner_node_id else None
            ),
            "to_pin_guid": link.raw_ref.to_pin_guid,
        },
    }
```

```python
def project_k2_metadata(metadata: K2NodeMetadata | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    return {
        "node_class": metadata.node_class,
        "function_name": metadata.function_name,
        "event_name": metadata.event_name,
        "variable_name": metadata.variable_name,
        "dispatcher_name": metadata.dispatcher_name,
        "member_parent": metadata.member_parent,
        "member_reference": metadata.member_reference,
        "opaque_properties": [project_opaque(item) for item in metadata.opaque_properties],
    }


def project_blueprint_graph(graph: BlueprintGraph) -> dict[str, Any]:
    return {
        "id": str(graph.id),
        "name": graph.name,
        "kind": graph.kind,
        "nodes": [
            {
                "id": str(node.id),
                "guid": node.guid,
                "class_name": node.class_name,
                "title": node.title,
                "metadata": project_k2_metadata(node.metadata),
                "pins": [
                    {
                        "id": pin.id,
                        "name": pin.name,
                        "direction": pin.direction,
                        "category": pin.category,
                        "subcategory": pin.subcategory,
                        "default_value": pin.default_value,
                        "default_object_ref": pin.default_object_ref,
                        "default_text": pin.default_text,
                        "sub_pin_ids": list(pin.sub_pin_ids),
                        "parent_pin_id": pin.parent_pin_id,
                        "reference_pass_through_pin_id": pin.reference_pass_through_pin_id,
                        "links": [project_pin_link(link) for link in pin.linked],
                        "unknown_properties": [project_opaque(region) for region in pin.unknown_properties],
                    }
                    for pin in node.pins
                ],
                "unknown_properties": [project_opaque(region) for region in node.unknown_properties],
            }
            for node in graph.nodes
        ],
        "parse_errors": list(graph.parse_errors),
        "truncated": graph.truncated,
        "source_range": project_region(graph.raw_region),
    }
```

These helpers live in `parsers/blueprint/graph.py`; they preserve raw endpoint
identity and physical source coordinates without exposing dataclass instances.

- [ ] **Step 4: Adapt current serializers to populate the IR**

- keep binary readers in `serializers/graph*.py`;
- keep `read_blueprint_graphs` as the raw dict serializer and convert its result
  once into `BlueprintGraph` objects;
- remove the current graph/node/pin presentation caps from canonical decode;
  explicit bounded views become `truncated=True` plus an exact opaque tail and
  diagnostic, never a silent drop;
- before decoding a selected owner, compute a bounded prerequisite closure from
  graph-container `Nodes`/`SubGraphs`, outer relationships, function graphs,
  and the generated-class/CDO references needed to establish ownership. The
  closure is an internal decode/cache set; `object_ids` still controls the
  returned object set and must not remove required graph inputs;
- build the closure with a visited export-id set and a fixed export-count cap;
  cycles, missing references, and cap hits become graph diagnostics with the
  unresolved reference retained. Do not use a name-only search to expand the
  closure;
- parse graph-container properties and referenced node properties through the
  same property cache used by the package reader. A graph decoder must not
  depend on the current outer-index fallback as its only recovery path;
- wrap each node export read in a saved/restored archive range bounded by its
  serial region. Cross-export reads are forbidden; failures produce a ranged
  opaque/unavailable node tail and a diagnostic;
- link resolution keeps both original reference and resolved owner-aware identity (`resolve_pin_links` already does most of this);
- every consumed pin/node field is either mapped to a typed IR field or represented by an `OpaqueRegion` with its exact source range. In particular, do not continue the current read-and-discard behavior for pin defaults, `DefaultObject`, `DefaultTextValue`, `SubPins`, `ParentPin`, reference pass-through, or unsupported `FEdGraphPinType` fields.
- `BlueprintPin` must expose the `FEdGraphPinType` category/subcategory,
  subcategory object and member reference, value/terminal type, container
  type, reference/const/weak/UObject-wrapper flags, and any version-gated
  precision flags. Preserve the raw field range when a field is not yet
  understood.
- add a minimal version-gated K2 metadata reader for function/event/member/
  variable/dispatcher references. The current tag allowlist is insufficient
  because the Wave A readers for those tags were removed; unsupported K2
  variants remain exact opaque fields and correlation stays unresolved.

Bridge contract (new function in `parsers/blueprint/graph.py`, not a rewrite of the serializers):

```python
class BlueprintGraphDecoder:
    def decode(
        self,
        obj: ObjectRecord,
        document: PackageDocument,
        *,
        source: ByteSource,
    ) -> list[BlueprintGraph]:
        """Read package graph exports through the binary serializer, then project
        the graphs owned by ``obj`` into typed IR.

         The current serializer is package-wide because graph nodes and pin
         references can point across export records. It remains the raw binary
         reader; this decoder filters by owner, assigns owner-aware
        NodeId/GraphId, preserves raw/unknown field ranges, builds
         PinLinkRef lists, and runs the typed ``resolve_pin_links(nodes, refs)``
         API. The raw in-place resolver remains private to the serializer and
         is not exposed as a second semantic output.
        """
```

Current `resolve_pin_links(graphs: list[dict]) -> None` at
`serializers/blueprint_graph.py:310` remains the raw serializer helper. The
typed `(nodes, refs) -> LinkResolution` API is owned by
`parsers/blueprint/graph.py`; it consumes the raw result and is the only API
used by correlation and projections.

- [ ] **Step 5: Run Blueprint graph regressions and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_ir.py tests/test_blueprint_graph.py tests/test_review_pins.py tests/test_k2_metadata.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/parsers/blueprint src/uasset_read/serializers/k2_metadata.py src/uasset_read/serializers/blueprint_graph.py src/uasset_read/serializers/graph_node.py src/uasset_read/serializers/graph_pin.py src/uasset_read/parsers/legacy_reader.py src/uasset_read/models/analysis.py tests/test_blueprint_ir.py tests/test_k2_metadata.py tests/size-baseline.json
git commit -m "feat: add owner-aware blueprint graph IR"
```

### Task 7: Normalize Kismet bytecode into instructions and CFG

**Files:**
- Create: `src/uasset_read/parsers/blueprint/bytecode.py`
- Create: `src/uasset_read/parsers/blueprint/control_flow.py`
- Modify: `src/uasset_read/kismet/archive.py`
- Modify: `src/uasset_read/kismet/bytecode_extractor.py`
- Modify: `src/uasset_read/kismet/expressions.py`
- Modify: `src/uasset_read/kismet/decompile_bridge.py`
- Modify: `src/uasset_read/kismet/result.py`
- Modify: `src/uasset_read/kismet/ufunction_reader.py`
- Modify: `src/uasset_read/kismet/native_fields.py`
- Modify: `src/uasset_read/kismet/property_pointer.py`
- Modify: `src/uasset_read/parsers/legacy_reader.py` (identity-first Kismet attachment)
- Create: `tests/test_blueprint_cfg.py`
- Create: `tests/test_kismet_operand_preservation.py`
- Create: `tests/test_native_fields.py`
- Modify: `tests/test_blueprint_decode.py` (read/result status and dual-offset migration)

**Interfaces:**
- Consumes: `FunctionScriptReadResult` and existing Kismet expression records.
- Produces: `BytecodeInstruction`, `BasicBlock`, `ControlFlowGraph`, `FunctionAnalysis`.

**UE source facts — `Engine/Source/Runtime/CoreUObject/Public/UObject/Script.h`:**

| Opcode | Value | Payload (from `ScriptSerialization.inl`) |
|---|---|---|
| `EX_Jump` | `0x06` | code offset |
| `EX_JumpIfNot` | `0x07` | code offset + boolean expression |
| `EX_Let` | `0x0F` | property pointer + variable expr + assign expr |
| `EX_LetBool` | `0x14` | var expr + assign expr |
| `EX_ComputedJump` | `0x4E` | integer expression only |
| `EX_EndOfScript` | `0x53` | terminator (there is **no** `EX_EndThread`) |
| `EX_FinalFunction` | `0x1C` | function pointer + parms until `EX_EndFunctionParms` |
| `EX_VirtualFunction` | `0x1B` | name + parms until `EX_EndFunctionParms` |
| `EX_CallMath` | `0x68` | final-function style math call |

Current Python already models `EX_Jump` / `EX_JumpIfNot` / `EX_ComputedJump` (`kismet/expressions.py:414-479`) and validates absolute jump targets (`bytecode_extractor.py:111`). What is missing is instruction offsets, typed CFG edges, and analysis objects.

- [ ] **Step 1: Write instruction and branch tests**

```python
# tests/test_blueprint_cfg.py
from tests.fixtures import find_function, parse_sample


def test_jump_if_not_creates_true_and_false_edges(ue58_blueprint_document):
    # Design gate 2: UE5.8 sample must expose IfThenElse / EX_JumpIfNot.
    functions = []
    for obj in ue58_blueprint_document.objects:
        functions.extend(((obj.semantic or {}).get("functions") or []))
    assert functions, "UE5.8 blueprint must expose functions"
    opcodes = {item["opcode"] for fn in functions for item in fn["instructions"]}
    assert "EX_JumpIfNot" in opcodes
    kinds = {edge["kind"] for fn in functions for edge in fn["cfg"]["edges"]}
    assert {"true", "false"} <= kinds


def test_instruction_ranges_are_monotonic(stackobot_document):
    for obj in stackobot_document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            instrs = fn["instructions"]
            statement_indexes = [item["statement_index"] for item in instrs]
            serialized_starts = [item["serialized_start"] for item in instrs]
            assert statement_indexes == sorted(statement_indexes)
            assert serialized_starts == sorted(serialized_starts)
            assert all(item["logical_end"] > item["statement_index"] for item in instrs)
            assert all(item["serialized_end"] > item["serialized_start"] for item in instrs)


def test_jump_targets_use_statement_index_not_serialized_offset(ue58_blueprint_document):
    function = find_function(ue58_blueprint_document, "NewFunction")
    valid_targets = {item["statement_index"] for item in function["instructions"]}
    branch = next(item for item in function["instructions"] if item["opcode"] == "EX_JumpIfNot")
    assert branch["jump_target_statement_index"] in valid_targets
    assert branch["jump_target_statement_index"] != branch["serialized_start"]


def test_computed_jump_is_marked_not_enumerated(stackobot_document):
    for obj in stackobot_document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            for edge in fn["cfg"]["edges"]:
                if edge["kind"] == "computed_jump":
                    assert edge["targets_known"] is False
```

```python
# tests/test_kismet_operand_preservation.py
def test_function_call_parameters_are_retained_recursively(function_analysis_ir):
    calls = [
        item
        for item in function_analysis_ir.instructions
        if item.opcode in {"EX_FinalFunction", "EX_VirtualFunction", "EX_CallMath"}
    ]
    assert calls
    assert any(item.operands.get("parameters") for item in calls)
    assert all(item.serialized_end > item.serialized_start for item in calls)


def test_nested_operands_are_projectable_without_repr(function_analysis_ir):
    from uasset_read.parsers.blueprint.bytecode import project_instruction

    for instruction in function_analysis_ir.instructions:
        projected = project_instruction(instruction)
        assert projected["expression"] is not None
        assert "0x" not in str(projected["expression"])
        assert projected["parse_status"] in {"parsed", "partial", "unavailable"}
        import json
        json.dumps(projected)
```

```python
# tests/test_native_fields.py
def test_native_field_reflection_payload_is_retained():
    from uasset_read.kismet.native_fields import NativeFieldDeclaration
    from uasset_read.models.byte_ranges import ByteRegion

    field = NativeFieldDeclaration(
        type_name="bool",
        name="bEnabled",
        property_flags=1,
        metadata={"DisplayName": "Enabled"},
        array_dim=1,
        element_size=1,
        rep_index=None,
        rep_notify_func=None,
        replication_condition=None,
        references=[],
        reference_names=[],
        inner_fields=[],
        opaque_metadata=[],
        source_range=ByteRegion(0, 8, "decoded"),
    )
    assert field.property_flags is not None
    assert field.array_dim >= 1
    assert field.element_size >= 0
    assert field.metadata is not None or field.opaque_metadata
    assert field.source_range is not None
```

- [ ] **Step 2: Run the tests and verify CFG behavior is missing**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_cfg.py tests/test_kismet_operand_preservation.py tests/test_native_fields.py tests/test_blueprint_decode.py tests/test_size_baseline.py -q`

Expected: instruction/CFG assertions fail because current output stops at expressions/direct exec summaries.

- [ ] **Step 3: Normalize expression records into instruction records**

Before normalization, change tolerant expression parsing so an unknown token
cannot disappear:

```python
@dataclass
class OpaqueExpression(KismetExpression):
    token: int
    raw_region: ByteRegion
    reason: str


def read_unknown_expression(
    archive: FKismetArchive,
    token: int,
    *,
    token_start: int,
) -> OpaqueExpression:
    # An unknown opcode has no generic length. Include the token already read
    # and preserve the remaining bounded function bytes as one unavailable tail.
    archive.consume_remaining_function()
    end = archive.serialized_offset
    return OpaqueExpression(
        token=token,
        raw_region=archive.region(token_start, end - token_start),
        reason="unknown_expression_token",
    )
```

When an unknown token is encountered, the parser records the token start before
consuming it, creates one `OpaqueExpression` covering that token through the
bounded function end, and stops parsing that function. There is no fixed
9-byte recovery guess and no attempt to manufacture later instruction
boundaries. The resulting expression is included in the returned list and is
projected as an unavailable instruction with a diagnostic. This preserves the
remaining bytes and prevents an unknown payload from corrupting CFG targets.

```python
@dataclass
class BytecodeInstruction:
    statement_index: int       # UE logical script address (current StatementIndex/CodeOffset)
    statement_ordinal: int     # zero-based order among top-level expressions
    logical_end: int            # bytecode_index after this top-level expression
    serialized_start: int
    serialized_end: int
    opcode: str
    operands: dict[str, Any]
    expression: Any
    reads: list[str]
    writes: list[str]
    call_target: str | None
    jump_target_statement_index: int | None
    jump_kind: Literal["unconditional", "conditional_false", "computed", "none"]
    source_node_id: str | None
    parse_status: Literal["parsed", "partial", "unavailable"] = "parsed"
```

Add one bounded cursor operation to `FKismetArchive` for this recovery path:
`consume_remaining_function() -> bytes` validates the current function end,
returns exactly the remaining local script bytes, advances to that end, and
never reads beyond the function slice. `read_unknown_expression()` uses this
operation; it does not call a generic unbounded archive read.

Implementation rules:
- one `BytecodeInstruction` represents one top-level script statement returned by `parse_bytecode_stream()`; nested expressions remain the statement's expression/operand tree and are not flattened into fake CFG instructions;
- the existing `KismetExpression.StatementIndex` is the UE logical script address used by `CodeOffset`; it is not the ordinal position in the returned list and it is not a serialized file offset. Add `statement_ordinal` for list order instead of changing that meaning;
- capture both cursor pairs at expression entry/exit: `statement_index`/`logical_end` from `bytecode_index`, and `serialized_start`/`serialized_end` from the on-disk cursor;
- **current gap to close in this task:** `FKismetArchive.read_expression` (`kismet/archive.py:48-91`) already computes `serialized_start` / `serialized_end` / `stmt_index` as locals and sets only `expr.StatementIndex`. Extend the capture so each top-level `KismetExpression` also carries `SerializedStart: int` and `SerializedEnd: int` (set right after construction, before return). `KismetExpression.__init__` gains these two optional fields defaulting to `-1`; `to_dict()` emits them. Do not re-derive ranges by re-walking bytes in Task 8 — the archive is the only source of truth.
- `EX_JumpIfNot` → `jump_kind="conditional_false"`, `jump_target_statement_index=CodeOffset`;
- `EX_Jump` → `jump_kind="unconditional"`, `jump_target_statement_index=CodeOffset`;
- `EX_ComputedJump` → `jump_kind="computed"`, `jump_target_statement_index=None`;
- call opcodes set `call_target` from resolved function/name;
- `EX_Let*` record variable write + value reads;
- uncertain byte consumption → instruction `parse_status="partial"` and a
  ranged opaque tail; an unknown token in tolerant mode becomes an addressable
  `parse_status="unavailable"` instruction with its physical/logical range.
  It is never silently skipped. `parse_status` describes binary-read quality;
  the public `ProjectionRecord.status` remains the separate
  `translated|represented|untranslated|unavailable` vocabulary.

Define the lossless fallback operand used by both nested expression records
and normalized instructions in `models/analysis.py` (the shared IR module):
`parsers/blueprint/bytecode.py` and `kismet/native_fields.py` import this one
type rather than defining parser-local copies:

```python
@dataclass(frozen=True)
class OpaqueOperand:
    role: str
    source_range: ByteRegion | None
    payload_ref: str | None
    reason: str
```

`project_operand()` recursively projects `KismetExpression`,
`OpaqueOperand`, lists, tuples, and dictionaries to JSON-safe values. It must
never call `repr()` as a substitute for a consumed value. It must also handle
`ByteRegion`, `bytes`/`memoryview`, enums, and nested dataclasses such as
`FNameRef`/`FFieldPath`; bytes use a deterministic encoded form and every
returned instruction must pass `json.dumps()`.

`FKismetPropertyPointer` and `FFieldPath` are operands too: retain raw name
indices/numbers, resolved owner/object index, path order, and the pointer's
serialized source range. A resolved display name is a derived field and cannot
replace the raw pointer identity.

Operand-preservation invariant: a successful expression reader must retain
every scalar, object/name pointer, nested expression, optional field, call
parameter, switch case, container element, cast/context operand, and constant
payload it consumes. Store known values in typed fields and store unsupported
values as `OpaqueOperand(role, source_range, payload_ref, reason)`. Every
`to_dict()` implementation recursively emits these operands. Add a focused
matrix covering `EX_FinalFunction`/`EX_VirtualFunction` parameters,
`EX_Return`, `EX_Context`/casts, arrays/maps/sets, switch cases, and transform
constants; the test must fail if a parser consumes bytes without an output
field.

The expression audit matrix must include the current lossy families, not only
the sample's currently observed opcodes:

| Family | Required retained operands |
|---|---|
| Function calls | target pointer/name, all parameters, end-parameters marker range |
| Cast/context/member access | class/property pointer, object expression, result expression, conversion flags |
| Let/assignment | destination pointer, assigned expression, bool/property flags |
| Array/map/set | target property, count, every element/key/value, container type |
| Switch | index expression, each case index/result, default expression |
| Constants | complete vector/rotation/transform/soft-object/field-path payload |
| Return/assert/instrumentation | returned expression and event/line/debug metadata |

An expression class may intentionally expose an empty typed payload only when
the UE serialization has no payload; the test must distinguish that from a
reader that consumed payload and discarded it.

Bridge from existing extractor to instruction records (`parsers/blueprint/bytecode.py`):

```python
def normalize_instructions(expressions: list[KismetExpression]) -> list[BytecodeInstruction]:
    """One instruction per top-level statement from parse_bytecode_stream.

    Nested expression trees stay on `instruction.expression`; they are not
    promoted to CFG nodes. Dual offsets come from the archive-captured
    StatementIndex / SerializedStart / SerializedEnd fields.
    """
```

Keep `parse_bytecode_stream` as the binary reader. This function only maps its output into analysis objects and derives reads/writes/call_target/jump_kind from the existing expression types (`kismet/expressions.py` already models `EX_Jump` / `EX_JumpIfNot` / `EX_ComputedJump`).

`KismetDecompiledResult` and `FunctionScriptReadResult` must retain
`export_index`, `object_id`, class name, local bytecode range, and package-
virtual/source range. `FKismetArchive.SerializedStart/End` are local physical
offsets into the copied script buffer; name them as local offsets in the
projection and carry the package source range separately. `_attach_kismet_extras`
must consume this identity directly. `native_fields.py` must also retain or
range-record property flags, metadata, array dimension, element size,
replication index/notify/condition, and native function declaration details so
the C++ declaration projector does not mistake consumed reflection data for
unsupported absence.

Define the shared `OpaqueOperand` in `models/analysis.py` and import it from
both `parsers/blueprint/bytecode.py` and `kismet/native_fields.py`; it must not
be defined separately in either parser, which would create incompatible
opaque-value types. The retained native declaration shape is explicit:

```python
@dataclass
class NativeFieldDeclaration:
    type_name: str
    name: str
    property_flags: int | None
    metadata: dict[str, Any] | None
    array_dim: int | None
    element_size: int | None
    rep_index: int | None
    rep_notify_func: str | None
    replication_condition: int | None
    references: list[int]
    reference_names: list[str | None]
    inner_fields: list["NativeFieldDeclaration"]
    opaque_metadata: list[OpaqueOperand]
    source_range: ByteRegion | None
```

If a UE-version branch cannot be decoded, retain the branch's bounded bytes in
`opaque_metadata` and mark the declaration capability accordingly; do not
populate a plausible default such as zero flags or `void` solely to satisfy a
renderer.

Extend the existing bridge records rather than creating a second function
identity table:

```python
@dataclass
class FunctionScriptReadResult:
    export_index: int
    object_id: str
    class_name: str
    serialized_script: bytes
    bytecode_buffer_size: int
    serialized_script_size: int
    native_fields: list[NativeFieldDeclaration]
    script_local_start: int
    script_local_end: int
    script_source_range: ByteRegion | None
    status: Literal["extracted", "no_script", "failed"]
    failure: FunctionScriptFailure | None


@dataclass
class KismetDecompiledResult:
    export_index: int
    object_id: str
    class_name: str
    function_name: str
    signature: str
    script_source_range: ByteRegion | None
    expressions: list[KismetExpression]
    bytecode_status: Literal["parsed", "partial", "unavailable"]
    error_code: str | None
    error_message: str | None
    error_context: dict[str, Any] | None
    script_metrics: dict[str, Any] | None
    fallback_reasons: list[str]
    errors: list[Diagnostic]
```

The bridge populates `object_id` from the export table before parsing; a
successful parse is not allowed to reconstruct identity from `function_name`.
Keep `FunctionScriptReadResult.status` as the read-phase vocabulary
(`extracted|no_script|failed`), but map it explicitly to the analysis
vocabulary: extracted and fully parsed → `parsed`, extracted with an opaque
tail → `partial`, and `no_script`/failed → `unavailable` with diagnostics.
In the same task, migrate every constructor and assertion in
`tests/test_blueprint_decode.py`: read-phase fixtures keep
`extracted|no_script|failed`, while `KismetDecompiledResult.bytecode_status`
uses only `parsed|partial|unavailable`. Add the new object identity and script
range fields to the expected dictionaries; do not leave tests asserting the
old three-value analysis status.

- [ ] **Step 4: Build basic blocks and typed edges**

```python
@dataclass
class BasicBlock:
    start_statement_index: int
    end_statement_index: int
    instructions: list[BytecodeInstruction]


@dataclass
class ControlFlowEdge:
    source_block: int
    target_block: int
    kind: Literal["fallthrough", "true", "false", "jump", "loop_back", "computed_jump", "return"]
    targets_known: bool = True


@dataclass
class ControlFlowGraph:
    blocks: list[BasicBlock]
    edges: list[ControlFlowEdge]
    entry: int
    metadata: dict[str, Any]


@dataclass
class FunctionAnalysis:
    object_id: str                 # function/UFunction export identity
    owner_object_id: str            # Blueprint/GeneratedClass owner identity
    name: str
    function_name: str
    script_source_range: ByteRegion | None
    expression_count: int
    entrypoint: "EntrypointRecord | None"
    instructions: list[BytecodeInstruction]
    cfg: ControlFlowGraph
    reads: set[str]
    writes: set[str]
    calls: list[str]
    bytecode_status: Literal["parsed", "partial", "unavailable"]
    diagnostics: list[Diagnostic]
```

Define the JSON projection helpers in the same module so Task 8 has stable
names and does not invent a second serialization path:

```python
import base64
import dataclasses
from enum import Enum

from uasset_read.models.byte_ranges import ByteRegion, project_region


def project_operand(value: Any) -> Any:
    if isinstance(value, OpaqueOperand):
        return {
            "kind": "opaque_operand",
            "role": value.role,
            "source_range": project_region(value.source_range),
            "payload_ref": value.payload_ref,
            "reason": value.reason,
        }
    if isinstance(value, ByteRegion):
        return project_region(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            "kind": "bytes",
            "encoding": "base64",
            "value": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, Enum):
        return project_operand(value.value)
    if hasattr(value, "to_dict"):
        return project_operand(value.to_dict())
    if dataclasses.is_dataclass(value):
        return project_operand(dataclasses.asdict(value))
    if isinstance(value, (list, tuple)):
        return [project_operand(item) for item in value]
    if isinstance(value, dict):
        return {str(key): project_operand(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return {
        "kind": "opaque_operand",
        "role": "unprojected_value",
        "source_range": None,
        "payload_ref": None,
        "reason": type(value).__name__,
    }


def project_instruction(instruction: BytecodeInstruction) -> dict[str, Any]:
    expression = instruction.expression
    return {
        "statement_index": instruction.statement_index,
        "statement_ordinal": instruction.statement_ordinal,
        "logical_end": instruction.logical_end,
        "serialized_start": instruction.serialized_start,
        "serialized_end": instruction.serialized_end,
        "opcode": instruction.opcode,
        "operands": project_operand(instruction.operands),
        "expression": project_operand(expression),
        "reads": list(instruction.reads),
        "writes": list(instruction.writes),
        "call_target": instruction.call_target,
        "jump_target_statement_index": instruction.jump_target_statement_index,
        "jump_kind": instruction.jump_kind,
        "source_node_id": instruction.source_node_id,
        "parse_status": instruction.parse_status,
    }


def project_cfg_edge(edge: ControlFlowEdge) -> dict[str, Any]:
    return {
        "source_block": edge.source_block,
        "target_block": edge.target_block,
        "kind": edge.kind,
        "targets_known": edge.targets_known,
    }


def project_cfg(cfg: ControlFlowGraph) -> dict[str, Any]:
    return {
        "blocks": [
            {
                "start_statement_index": block.start_statement_index,
                "end_statement_index": block.end_statement_index,
                "instructions": [project_instruction(item) for item in block.instructions],
            }
            for block in cfg.blocks
        ],
        "edges": [project_cfg_edge(edge) for edge in cfg.edges],
        "entry": cfg.entry,
        "metadata": dict(cfg.metadata),
    }
```

`object_id` identifies the function/UFunction export; `owner_object_id`
identifies the Blueprint/GeneratedClass export that owns it. Keep both because
the current package has separate function exports and the attachment bug is
caused by collapsing them to a name. `script_source_range` identifies the
serialized script region in the package source coordinate model. Every
instruction inherits the function identity through `FunctionAnalysis`; C++
migration records copy both ids, `function_name`, logical `statement_index`,
`serialized_start`, and `serialized_end`. `function_name` mirrors the public
Kismet name so Task 8/12 can assert `fn.expression_count` sums to 85.
`entrypoint` is filled by Task 8 correlation (`kind="function"`); Task 7 may
leave it `None` until then.

Split blocks in the logical `StatementIndex`/`CodeOffset` coordinate system at entry, every jump target, conditional fallthrough after `EX_JumpIfNot`, and returns (`EX_Return` / end of script). Never resolve a jump against serialized disk offsets or list ordinals. `EX_JumpIfNot` emits `false` → target and `true` → fallthrough. `EX_ComputedJump` emits a single `computed_jump` edge with `targets_known=False`. Derive `exec_chains` only after CFG construction, and keep its metadata `{"kind": "direct_exec_edge_summary"}`.

Jump target mapping is explicit: first prefer an exact top-level instruction
`statement_index`; otherwise map a target only when it lies on a documented
instruction interval boundary. A target inside a nested expression, between
unmapped statements, outside the function range, or at an unavailable opaque
tail produces `targets_known=False` plus a diagnostic; never guess an ordinal
or create an edge to the nearest instruction.

Nested parsing must also preserve `StreamPoisonedError`: nested readers may
convert ordinary bounded parse failures into a partial/opaque tail, but they
must re-raise stream-poisoning failures so the function cannot be reported as a
valid partial decode after its cursor has become untrustworthy.

- [ ] **Step 5: Run the complete Blueprint/Kismet tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_cfg.py tests/test_kismet_operand_preservation.py tests/test_native_fields.py tests/test_blueprint_decode.py tests/test_parse_hardening.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/parsers/blueprint/bytecode.py src/uasset_read/parsers/blueprint/control_flow.py src/uasset_read/kismet/archive.py src/uasset_read/kismet/bytecode_extractor.py src/uasset_read/kismet/expressions.py src/uasset_read/kismet/decompile_bridge.py src/uasset_read/kismet/result.py src/uasset_read/kismet/ufunction_reader.py src/uasset_read/kismet/native_fields.py src/uasset_read/kismet/property_pointer.py src/uasset_read/parsers/legacy_reader.py tests/test_blueprint_cfg.py tests/test_kismet_operand_preservation.py tests/test_native_fields.py tests/test_blueprint_decode.py tests/size-baseline.json
git commit -m "feat: preserve kismet dual offsets and build cfg"
```

### Task 8: Correlate graph nodes, bytecode, calls, and variables

**Files:**
- Create: `src/uasset_read/parsers/blueprint/correlation.py`
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`
- Modify: `src/uasset_read/parsers/legacy_reader.py` (run correlation while package inputs are available)
- Modify: `src/uasset_read/models/analysis.py`
- Create: `tests/test_blueprint_correlation.py`
- Modify: `tests/test_blueprint_decode.py`, `tests/test_blueprint_graph.py`, `tests/test_core.py`, `tests/test_samples.py` (consumer migration completed with the semantic flip)

**Interfaces:**
- Consumes: `BlueprintGraph`, `FunctionAnalysis`, object table, imports, and properties.
- Produces: `BlueprintSemantic(declaration, variable_definitions, function_declarations, entrypoints, graphs, functions, calls, variable_accesses, components, dispatchers, constructors, variable_events, diagnostics)`.
- API: `BlueprintCorrelation.build(document: PackageDocument, *, analysis_context: BlueprintAnalysisContext | None = None) -> BlueprintSemantic`.

The package read path invokes `BlueprintCorrelation` while the decoded graph
and function IR are still available, passing one explicit
`BlueprintAnalysisContext(owner_object_id, graphs, functions)` through the
existing per-package analysis context; it does not reopen a closed archive or
reconstruct a second binary reader. `build(document)` without that argument is
the standalone test/re-analysis entry: it consumes the complete projected
`objects[].semantic` dictionaries. The projected dictionary is lossless enough
for that re-analysis, but the normal package path performs only one
binary-to-IR conversion. Keep any live typed inputs in a private analysis
context (or stripped `_ir` slot) and strip them before JSON serialization; the
renderer and writer must never require that hidden state.

Implement the no-context path with explicit `BlueprintGraph.from_dict()` /
`FunctionAnalysis.from_dict()` helpers (or equivalent private constructors)
that accept only the frozen v3 keys. Missing ranges or operands become
unresolved/opaque records; the fallback must not reopen bytes or infer fields
from display names. The package path uses `analysis_context` and therefore
does not perform this dict-to-IR round trip.

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.native_fields import NativeFieldDeclaration


@dataclass(frozen=True)
class BlueprintAnalysisContext:
    owner_object_id: str
    graphs: list[BlueprintGraph]
    functions: list[FunctionAnalysis]


@dataclass(frozen=True)
class EntrypointRecord:
    kind: Literal["event", "function", "construction", "dispatcher"]
    name: str
    object_id: str
    source_node_id: NodeId | None = None
    match_method: Literal["object_id", "function_identity", "source_node", "node_guid", "unresolved"] = "unresolved"
    confidence: float = 0.0
    unresolved: bool = True


@dataclass(frozen=True)
class CallRecord:
    function_name: str
    object_id: str                 # resolved target function/object, when known
    owner_object_id: str           # containing function/UFunction export
    statement_index: int | None
    source_node_id: NodeId | None
    serialized_start: int | None = None
    serialized_end: int | None = None
    match_method: Literal["object_id", "function_identity", "source_node", "node_guid", "unresolved"] = "unresolved"
    confidence: float = 0.0
    unresolved: bool = True
    execution_mode: Literal["static_reference"] = "static_reference"


@dataclass(frozen=True)
class VariableAccessRecord:
    name: str
    access: Literal["read", "write", "read_write", "declaration"]
    object_id: str                 # resolved variable/property owner, when known
    owner_object_id: str           # containing function/UFunction export
    statement_index: int | None = None
    source_node_id: NodeId | None = None
    serialized_start: int | None = None
    serialized_end: int | None = None
    match_method: Literal["object_id", "function_identity", "source_node", "node_guid", "unresolved"] = "unresolved"
    confidence: float = 0.0
    unresolved: bool = True


@dataclass(frozen=True)
class VariableDefinition:
    name: str
    type_name: str | None
    cpp_type: str | None
    raw_type: dict[str, Any] | None
    array_dim: int | None
    property_flags: int | None
    default_value: Any | None
    object_id: str
    source_range: ByteRegion | None
    unresolved: bool = False


@dataclass(frozen=True)
class FunctionParameter:
    name: str
    type_name: str | None
    cpp_type: str | None
    direction: Literal["in", "out", "inout"]
    default_value: Any | None
    source_range: ByteRegion | None


@dataclass(frozen=True)
class FunctionDeclaration:
    name: str
    return_type: str | None
    cpp_return_type: str | None
    parameters: list[FunctionParameter]
    flags: int | None
    native_fields: list[NativeFieldDeclaration]
    source_range: ByteRegion | None
    unresolved: bool = False


@dataclass(frozen=True)
class BlueprintDeclaration:
    class_name: str
    parent_class: str | None
    class_flags: int | None
    metadata: dict[str, Any]
    source_range: ByteRegion | None


@dataclass(frozen=True)
class ComponentRecord:
    name: str
    class_name: str
    object_id: str


@dataclass(frozen=True)
class DispatcherRecord:
    name: str
    object_id: str
    parameters: list[FunctionParameter]
    source_range: ByteRegion | None
    unresolved: bool = False


@dataclass(frozen=True)
class ConstructorRecord:
    name: str
    object_id: str
    parent_class: str | None
    parent_call: str | None
    component_initializers: list[str]
    variable_initializers: list[str]
    source_node_id: NodeId | None = None
    unresolved: bool = False


@dataclass(frozen=True)
class VariableEventRecord:
    variable_name: str
    dispatcher_name: str | None
    object_id: str
    source_node_id: NodeId | None
    event_kind: Literal["on_changed", "on_initialized", "dispatcher", "unknown"]
    match_method: str
    confidence: float
    unresolved: bool


@dataclass
class ExecChainSummary:
    metadata: dict[str, Any]
    edges: list[ControlFlowEdge]


@dataclass
class BlueprintSemantic:
    object_id: str
    name: str
    parent_class: str | None
    declaration: BlueprintDeclaration
    variable_definitions: list[VariableDefinition]
    function_declarations: list[FunctionDeclaration]
    entrypoints: list[EntrypointRecord]
    graphs: list[BlueprintGraph]
    functions: list[FunctionAnalysis]
    calls: list[CallRecord]
    variable_accesses: list[VariableAccessRecord]
    components: list[ComponentRecord]
    dispatchers: list[DispatcherRecord]
    constructors: list[ConstructorRecord]
    variable_events: list[VariableEventRecord]
    control_flow: list[ControlFlowGraph]
    exec_chains: ExecChainSummary
    diagnostics: list[Diagnostic]
```

`control_flow` is the package-level aggregate of every function CFG so Task 8/12 can assert `semantic.control_flow` without reaching into each function. Build it as `[fn.cfg for fn in functions if fn.cfg.blocks]`.

**Current-state notes:**
- StackOBot relations already include `generated_class_of (export:1 → export:0)` and `default_object_of (export:2 → export:1)` (`tests/test_samples.py:814-817`).
- Design gate 1 still requires: 31 exports addressable, 2 graphs, **3 Kismet functions**, **85 expressions**, CFG blocks/edges, call targets, variable reads/writes. Only the graph/exec portion is proven today.

- [ ] **Step 1: Write static semantic tests**

```python
# tests/test_blueprint_correlation.py
from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation


def test_stackobot_has_event_entrypoint_and_function_calls(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    assert semantic.entrypoints
    assert semantic.calls
    assert semantic.variable_accesses
    assert all(call.execution_mode == "static_reference" for call in semantic.calls)


def test_exec_summary_is_not_runtime_execution(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    assert semantic.exec_chains.metadata["kind"] == "direct_exec_edge_summary"
    assert semantic.control_flow


def test_constructor_parent_and_variable_event_records_are_explicit(ue58_blueprint_document):
    semantic = BlueprintCorrelation().build(ue58_blueprint_document)
    assert semantic.constructors
    constructor = semantic.constructors[0]
    assert constructor.object_id
    assert constructor.parent_class is not None
    assert all(item.object_id for item in semantic.variable_events)


def test_stackobot_kismet_counts(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    assert len(semantic.functions) == 3
    total_expr = sum(fn.expression_count for fn in semantic.functions)
    assert total_expr == 85
    assert any(fn.cfg.blocks for fn in semantic.functions)


def test_ue58_new_function_preserves_branch_and_variable_flow(ue58_blueprint_document):
    semantic = BlueprintCorrelation().build(ue58_blueprint_document)
    function = next(fn for fn in semantic.functions if fn.name == "NewFunction")
    branch = next(item for item in function.instructions if item.opcode == "EX_JumpIfNot")
    assert branch.jump_target_statement_index is not None
    assert {edge.kind for edge in function.cfg.edges} >= {"true", "false"}
    assert "NewParam" in function.reads
    assert "NewParam1" in function.writes
    assert function.entrypoint.kind == "function"


def test_every_call_and_variable_record_is_traceable(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    for call in semantic.calls:
        assert call.function_name
        assert call.object_id
        assert call.owner_object_id
        assert call.unresolved or call.statement_index is not None or call.source_node_id
        assert 0.0 <= call.confidence <= 1.0
        assert call.unresolved or call.match_method != "unresolved"
    for variable in semantic.variable_accesses:
        assert variable.name
        assert variable.access in {"read", "write", "read_write", "declaration"}
        assert variable.object_id
        assert variable.owner_object_id
        assert 0.0 <= variable.confidence <= 1.0
        assert variable.unresolved or variable.match_method != "unresolved"


def test_duplicate_function_names_keep_export_identity(stackobot_document, function_analysis_ir):
    from dataclasses import replace
    from uasset_read.models.analysis import BlueprintAnalysisContext

    first = replace(function_analysis_ir, object_id="export:9", name="Same", function_name="Same")
    second = replace(function_analysis_ir, object_id="export:10", name="Same", function_name="Same")
    semantic = BlueprintCorrelation().build(
        stackobot_document,
        analysis_context=BlueprintAnalysisContext(
            owner_object_id="export:0", graphs=[], functions=[first, second]
        ),
    )
    assert [fn.object_id for fn in semantic.functions] == ["export:9", "export:10"]
```

- [ ] **Step 2: Run tests and confirm current output lacks the new contract**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_correlation.py tests/test_blueprint_decode.py tests/test_size_baseline.py -q`

Expected: missing call/variable/entrypoint correlation fields or incorrect execution metadata; StackOBot Kismet counts not yet 3/85.

- [ ] **Step 3: Implement multi-level correlation**

Match priority:
1. Export/Object ID (graph owner, function export index);
2. function identity (`function_name` + signature);
3. source-node metadata (`K2Node_CallFunction` / `K2Node_IfThenElse` node class + linked function reference);
4. Node GUID as last resort.

Store `match_method` and `confidence` on every correlated record. Preserve unresolved references as records with `unresolved=True` — never drop them.
Kismet attachment is identity-first: successful results are indexed by
`object_id`/export index before correlation starts. Function name is never a
primary key; if it is used as a fallback, emit a duplicate-name diagnostic and
mark confidence accordingly. Add a synthetic duplicate-name test proving that
two same-named functions retain separate owners.

Derive calls and variable access with one recursive visitor over
`BytecodeInstruction.expression` and its projected operands:

```python
def walk_expression(value: Any) -> Iterator[tuple[Any, ByteRegion | None]]: ...


def analyze_instruction(instruction: BytecodeInstruction) -> tuple[
    list[CallRecord], list[VariableAccessRecord]
]:
    """Visit nested expressions; attach the parent instruction range to each record."""
```

The visitor classifies `EX_FinalFunction`/`EX_VirtualFunction`/`EX_CallMath`
as calls, `EX_LocalVariable`/`EX_InstanceVariable`/field-path references as
reads, and `EX_Let*`/set expressions as writes. A call or variable that has
only a name but no resolvable object identity remains a record with
`unresolved=True`; do not drop it because the name is ambiguous. Correlation
to a graph node uses K2 metadata and pin links after this expression pass, so
the binary readers remain independent of graph analysis.

Build constructor and event records from explicit evidence: the generated
class's `super_ref` supplies `parent_class`/`parent_call`, the CDO/component
relations supply component initializers, `UserConstructionScript` supplies
construction statements, and K2 variable/event/dispatcher metadata supplies
variable-event records. If any of these sources is absent, keep the record with
the missing field set to `None` and a diagnostic; do not infer a constructor
from the asset name alone.

- [ ] **Step 4: Add Blueprint semantic output under each object**

Keep all functions, graphs, calls, and variable sets under the corresponding Blueprint/GeneratedClass object (`objects[].semantic`). Do not promote domain content to the document root.

Apply Edit Playbook E1 in this step:
1. Implement `project_semantic_blueprint(BlueprintSemantic) -> dict` with the canonical keys from E1.
2. `BlueprintFamilyHandler` / decode path writes that dict into `ObjectRecord.semantic` (never the live dataclass, unless under stripped `_ir`).
3. Sample-facing tests (`parse_sample` / `stackobot_document`) assert dict shapes (`fn["expression_count"]`, `semantic["control_flow"]`); unit tests may use typed IR directly.
4. Flip all Blueprint-family objects in one commit — no mixed K0/IR objects.

Update `LegacyPackageReader` in this same step so the handler phase receives
the already assembled package envelope plus the typed graph/function inputs for
the owning export. Call `BlueprintCorrelation.build(document,
analysis_context=...)` once per Blueprint-family owner, then immediately call
`project_semantic_blueprint()` and store only its JSON-safe dictionary on the
object. The existing tuple/package-data callers may keep their non-Blueprint
fields, but the Blueprint branch must use the named context rather than a
positional guess. The same `PackageDocument` instance is finalized and
returned; do not construct a temporary document solely for correlation.

Concrete projection skeleton (new function in `parsers/blueprint/correlation.py`):

```python
def project_semantic_blueprint(semantic: BlueprintSemantic) -> dict[str, Any]:
    """Typed IR → document-boundary dict. Frozen key set for format_version 3.0."""
    return {
        "kind": "blueprint",  # or anim_blueprint when AnimBP
        "object_id": semantic.object_id,
        "name": semantic.name,
        "parent_class": semantic.parent_class,
        "declaration": {
            "class_name": semantic.declaration.class_name,
            "parent_class": semantic.declaration.parent_class,
            "class_flags": semantic.declaration.class_flags,
            "metadata": semantic.declaration.metadata,
            "source_range": project_region(semantic.declaration.source_range),
        },
        "variable_definitions": [
            {
                "name": item.name,
                "type_name": item.type_name,
                "cpp_type": item.cpp_type,
                "raw_type": item.raw_type,
                "array_dim": item.array_dim,
                "property_flags": item.property_flags,
                "default_value": project_operand(item.default_value),
                "object_id": item.object_id,
                "source_range": project_region(item.source_range),
                "unresolved": item.unresolved,
            }
            for item in semantic.variable_definitions
        ],
        "function_declarations": [
            {
                "name": item.name,
                "return_type": item.return_type,
                "cpp_return_type": item.cpp_return_type,
                "parameters": [
                    {
                        "name": param.name,
                        "type_name": param.type_name,
                        "cpp_type": param.cpp_type,
                        "direction": param.direction,
                        "default_value": project_operand(param.default_value),
                        "source_range": project_region(param.source_range),
                    }
                    for param in item.parameters
                ],
                "flags": item.flags,
                "native_fields": [project_operand(field) for field in item.native_fields],
                "source_range": project_region(item.source_range),
                "unresolved": item.unresolved,
            }
            for item in semantic.function_declarations
        ],
        "entrypoints": [
         {"kind": e.kind, "name": e.name, "object_id": e.object_id,
              "source_node_id": str(e.source_node_id) if e.source_node_id else None,
              "match_method": e.match_method, "confidence": e.confidence,
              "unresolved": e.unresolved}
            for e in semantic.entrypoints
        ],
        "graphs": [project_blueprint_graph(g) for g in semantic.graphs],
        "functions": [project_function_analysis(fn) for fn in semantic.functions],
        "calls": [
             {"function_name": c.function_name, "object_id": c.object_id,
              "owner_object_id": c.owner_object_id,
              "statement_index": c.statement_index,
              "source_node_id": str(c.source_node_id) if c.source_node_id else None,
              "serialized_start": c.serialized_start,
              "serialized_end": c.serialized_end,
              "match_method": c.match_method, "confidence": c.confidence,
              "unresolved": c.unresolved,
              "execution_mode": c.execution_mode}
            for c in semantic.calls
        ],
        "variable_accesses": [
            {"name": v.name, "access": v.access, "object_id": v.object_id,
              "owner_object_id": v.owner_object_id,
              "statement_index": v.statement_index,
              "source_node_id": str(v.source_node_id) if v.source_node_id else None,
              "serialized_start": v.serialized_start,
              "serialized_end": v.serialized_end,
              "match_method": v.match_method, "confidence": v.confidence,
              "unresolved": v.unresolved}
             for v in semantic.variable_accesses
        ],
        "components": [{"name": c.name, "class_name": c.class_name, "object_id": c.object_id}
                       for c in semantic.components],
        "dispatchers": [
            {
                "name": item.name,
                "object_id": item.object_id,
                "parameters": [project_operand(param) for param in item.parameters],
                "source_range": project_region(item.source_range),
                "unresolved": item.unresolved,
            }
            for item in semantic.dispatchers
        ],
        "constructors": [
            {
                "name": item.name,
                "object_id": item.object_id,
                "parent_class": item.parent_class,
                "parent_call": item.parent_call,
                "component_initializers": list(item.component_initializers),
                "variable_initializers": list(item.variable_initializers),
                "source_node_id": str(item.source_node_id) if item.source_node_id else None,
                "unresolved": item.unresolved,
            }
            for item in semantic.constructors
        ],
        "variable_events": [
            {
                "variable_name": item.variable_name,
                "dispatcher_name": item.dispatcher_name,
                "object_id": item.object_id,
                "source_node_id": str(item.source_node_id) if item.source_node_id else None,
                "event_kind": item.event_kind,
                "match_method": item.match_method,
                "confidence": item.confidence,
                "unresolved": item.unresolved,
            }
            for item in semantic.variable_events
        ],
        "control_flow": [project_cfg(cfg) for cfg in semantic.control_flow],
        "exec_chains": {
            "metadata": semantic.exec_chains.metadata,
            "edges": [project_cfg_edge(e) for e in semantic.exec_chains.edges],
        },
        "diagnostics": [d.to_dict() for d in semantic.diagnostics],
    }


def project_function_analysis(fn: FunctionAnalysis) -> dict[str, Any]:
    # Keep expression_count and entrypoint at the top level so
    # tests/fixtures.find_function and Task 12 gates can read them without
    # walking the instruction list.
    return {
        "function_name": fn.function_name,
        "name": fn.name,
        "object_id": fn.object_id,
        "owner_object_id": fn.owner_object_id,
        "source_range": project_region(fn.script_source_range),
        "expression_count": fn.expression_count,
        "entrypoint": ({"kind": fn.entrypoint.kind, "name": fn.entrypoint.name,
                        "object_id": fn.entrypoint.object_id,
                        "source_node_id": (str(fn.entrypoint.source_node_id)
                                            if fn.entrypoint.source_node_id else None),
                        "match_method": fn.entrypoint.match_method,
                        "confidence": fn.entrypoint.confidence,
                        "unresolved": fn.entrypoint.unresolved}
                       if fn.entrypoint else None),
        "instructions": [project_instruction(i) for i in fn.instructions],
        "cfg": project_cfg(fn.cfg),
        "reads": sorted(fn.reads),
        "writes": sorted(fn.writes),
        "calls": list(fn.calls),
        "bytecode_status": fn.bytecode_status,
        "diagnostics": [d.to_dict() for d in fn.diagnostics],
    }
```

`tests/fixtures.find_function` and Task 12 `count_kismet_expressions` read `fn["expression_count"]` / `fn["function_name"]` from this dict. Do not store the live `FunctionAnalysis` dataclass under `semantic["functions"]`.

- [ ] **Step 5: Run sample correlation tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_correlation.py tests/test_blueprint_graph.py tests/test_blueprint_decode.py tests/test_core.py tests/test_samples.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/parsers/blueprint/correlation.py src/uasset_read/parsers/asset_types/handlers_impl.py src/uasset_read/parsers/legacy_reader.py src/uasset_read/models/analysis.py tests/test_blueprint_correlation.py tests/test_blueprint_decode.py tests/test_blueprint_graph.py tests/test_core.py tests/test_samples.py tests/size-baseline.json
git commit -m "feat: correlate blueprint graphs and bytecode"
```

### Task 9: Decode Material expression graphs

**Files:**
- Create: `src/uasset_read/parsers/material/__init__.py`
- Create: `src/uasset_read/parsers/material/graph.py`
- Modify: `src/uasset_read/parsers/asset_types/handlers_impl.py`
- Modify: `src/uasset_read/parsers/legacy_reader.py`
- Modify: `src/uasset_read/parsers/binary_or_native_handlers.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Create: `tests/test_material_graph.py`

**Interfaces:**
- Consumes: Material/MaterialExpression exports, normalized properties, object references, and graph pins.
- Produces: `MaterialGraph(expressions, links, parameters, function_calls, capability)`.
- API: `MaterialGraphDecoder.decode(document: PackageDocument, *, material_object_id: str) -> MaterialGraph`.
- The graph is the canonical input for the later embedded `material_editor_builder` projection; this task does not generate HLSL or claim runtime-material equivalence.

```python
@dataclass
class MaterialExpressionRecord:
    object_id: str
    class_name: str
    properties: PropertyBag
    opaque_regions: list[OpaqueRegion]
    source_range: ByteRegion | None


@dataclass(frozen=True)
class MaterialParameterRecord:
    name: str
    parameter_type: str
    value: Any
    source_range: ByteRegion | None


@dataclass(frozen=True)
class MaterialLink:
    from_expression_id: str
    from_output: str
    to_expression_id: str
    to_input: str
    source_range: ByteRegion | None


@dataclass(frozen=True)
class MaterialFunctionCallRecord:
    object_id: str | None
    name: str | None
    input_names: list[str]
    source_range: ByteRegion | None


@dataclass
class MaterialGraph:
    object_id: str
    name: str
    expressions: list[MaterialExpressionRecord]
    links: list[MaterialLink]
    parameters: list[MaterialParameterRecord]
    function_calls: list[MaterialFunctionCallRecord]
    capability: Literal["complete", "partial", "limited", "unavailable"]
    coverage: list[CoverageEntry]
    diagnostics: list[Diagnostic]
    source_range: ByteRegion | None
```

The material document projection is also a dictionary and keeps all source
identity needed by the editor-builder projector:

```python
from dataclasses import asdict
from uasset_read.models.properties import (
    project_property_bag,
    project_property_entries,
)
from uasset_read.models.byte_ranges import project_region


def project_semantic_material(graph: MaterialGraph) -> dict[str, Any]:
    return {
        "kind": "material",
        "object_id": graph.object_id,
        "name": graph.name,
        "material_graph": {
            "expressions": [
                {
                    "object_id": item.object_id,
                    "class_name": item.class_name,
                    "properties": project_property_bag(item.properties),
                    "property_entries": project_property_entries(item.properties),
                    "opaque_regions": [project_region(region) for region in item.opaque_regions],
                    "source_range": project_region(item.source_range),
                }
                for item in graph.expressions
            ],
            "links": [
                {
                    "from_expression_id": link.from_expression_id,
                    "from_output": link.from_output,
                    "to_expression_id": link.to_expression_id,
                    "to_input": link.to_input,
                    "source_range": project_region(link.source_range),
                }
                for link in graph.links
            ],
            "parameters": [
                {
                    "name": item.name,
                    "parameter_type": item.parameter_type,
                    "value": item.value,
                    "source_range": project_region(item.source_range),
                }
                for item in graph.parameters
            ],
            "function_calls": [
                {
                    "object_id": call.object_id,
                    "name": call.name,
                    "input_names": list(call.input_names),
                    "source_range": project_region(call.source_range),
                }
                for call in graph.function_calls
            ],
            "capability": graph.capability,
            "coverage": [asdict(item) for item in graph.coverage],
            "diagnostics": [item.to_dict() for item in graph.diagnostics],
            "source_range": project_region(graph.source_range),
        },
    }
```

`project_region()` is the JSON-only range helper defined by Task 4 in
`models/byte_ranges.py` and is shared by the graph/material projections; no
material projector reads package bytes.

**Current-state notes:**
- `MaterialHandler` (`handlers_impl.py:576`) only emits flags + EditorX/Y + summary counts.
- `StackOBot_M_BotBase.uasset` exists with `export_count=42` in the manifest; design gate 3 expects **39 material expressions**.
- `TestMaterial.uasset` is the current editor-stripped/cooked candidate and must report `limited`/`unavailable` for the editor expression graph, not invent nodes. `MyProject_UE58_TestMaterial.uasset` contains editor-only material data and is not a valid cooked fixture.
- This task depends on Task 4 preserving decoded `FExpressionInput` / `FMaterialAttributesInput` fields in normalized properties. `MaterialGraphDecoder` consumes those fields and object references; it never reopens the source archive or reparses raw property bytes.

- [ ] **Step 1: Write StackOBot and cooked-material tests**

```python
# tests/test_material_graph.py
from tests.fixtures import find_material_graph, parse_sample
from uasset_read.parsers.material.graph import MaterialGraphDecoder


def test_stackobot_material_exposes_expression_nodes_and_links(stackobot_material):
    graph = MaterialGraphDecoder().decode(stackobot_material, material_object_id="export:0")
    assert len(graph.expressions) == 39
    assert graph.links
    assert graph.parameters
    assert graph.capability in {"complete", "partial"}


def test_material_handler_attaches_one_projected_graph(stackobot_material):
    material = next(obj for obj in stackobot_material.objects if obj.id == "export:0")
    projected = (material.semantic or {}).get("material_graph")
    assert isinstance(projected, dict)
    assert len(projected["expressions"]) == 39
    assert projected["links"]


def test_selected_material_has_same_expression_set_as_full_decode():
    full = parse_sample("StackOBot_M_BotBase.uasset", depth="decode")
    selected = parse_sample(
        "StackOBot_M_BotBase.uasset",
        depth="decode",
        object_ids=["export:0"],
    )
    full_graph = find_material_graph(full)
    selected_graph = find_material_graph(selected)
    assert [item["object_id"] for item in full_graph["expressions"]] == [
        item["object_id"] for item in selected_graph["expressions"]
    ]


def test_cooked_material_marks_editor_graph_unavailable(cooked_material):
    graph = MaterialGraphDecoder().decode(cooked_material, material_object_id="export:0")
    assert graph.capability in {"limited", "unavailable"}
    assert any(item.feature == "editor_expression_graph" for item in graph.coverage)
```

- [ ] **Step 2: Run focused tests and confirm current Material summary is insufficient**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_material_graph.py tests/test_samples.py tests/test_size_baseline.py -q`

Expected: expression/link assertions fail against the current Material summary.

- [ ] **Step 3: Implement expression and pin extraction**

- resolve `MaterialExpression*` exports by object identity / outer chain from the Material export;
- use a bounded material dependency closure so selecting only the Material
  export still decodes its expression exports, output-input records, and
  referenced material-function objects; `object_ids` filters returned objects
  but never removes graph prerequisites;
- copy scalar/vector/texture parameters and `MaterialExpressionMaterialFunctionCall` targets;
- consume the normalized `ExpressionInput`/`MaterialAttributesInput` and
  nested function input/output records produced by Task 4; if a known
  concrete struct still arrives as generic raw bytes, fail the focused property
  regression rather than reparsing it here;
- unknown expression fields stay opaque regions with offsets;
- no graph evaluation and no HLSL generation.

- [ ] **Step 4: Implement link reconstruction and capability reporting**

- use serialized input/output pin references where present;
- if the package has no editor expression graph (cooked/filtered), set `capability` to `limited` or `unavailable` and coverage feature `editor_expression_graph`;
- never invent links from material default properties alone.

Concrete link sources, in priority order (UE basis `MaterialExpression.h` / cooked property layout):

1. **Expression input properties of type `FExpressionInput` / `FMaterialAttributesInput`** on each `MaterialExpression*` export. A connected input carries `OutputIndex` plus an expression reference (object import/export index or name). Emit `MaterialLink(from_expression_id=..., from_output=str(OutputIndex), to_expression_id=this, to_input=property_name)`.
2. **Material's own output inputs** (`BaseColor`, `Metallic`, `Roughness`, `Normal`, `EmissiveColor`, `Opacity`, …) that point at an expression. These become links whose `to_expression_id` is the Material object itself and `to_input` is the material property name.
3. **`MaterialExpressionMaterialFunctionCall`** → record the function package/object reference in `function_calls` and still emit its input links.
4. Anything else stays in `MaterialExpressionRecord.properties` / `opaque_regions` — do not synthesize links from default scalar/vector values alone.

Cooked detection: if the Material export has no editor-only expression object references (or the expression exports are absent from the package), set `capability` to `limited`/`unavailable` and add a `CoverageEntry(feature="editor_expression_graph", status=...)`. Never emit an empty-but-successful builder.

The decoder must preserve enough information for an editor-side reconstruction projection:

- material output property names and expression input/output names remain stable;
- expression class names, editor coordinates, parameters, function-call targets, and object IDs remain traceable;
- a cooked or editor-stripped package produces an unavailable/limited builder descriptor rather than an empty successful builder file.

Integration boundary: `MaterialGraphDecoder` is invoked from the package/domain
decode path after the prerequisite properties are available and writes the
projected dictionary under the owning Material object's
`semantic["material_graph"]`. It is not a standalone post-pass that reopens
the archive. The handler must preserve one owner identity and merge diagnostics
without replacing the package envelope.

- [ ] **Step 5: Run Material tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_material_graph.py tests/test_capability_hardening.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/parsers/material src/uasset_read/parsers/asset_types/handlers_impl.py src/uasset_read/parsers/legacy_reader.py src/uasset_read/parsers/binary_or_native_handlers.py src/uasset_read/parsers/property_parser.py tests/test_material_graph.py tests/size-baseline.json
git commit -m "feat: decode material expression graphs"
```

### Task 10: Build the Blueprint C++ declaration and migration projection

**Files:**
- Create: `src/uasset_read/projections/__init__.py`
- Create: `src/uasset_read/projections/cpp_ast.py`
- Create: `src/uasset_read/projections/cpp_render.py`
- Modify: `src/uasset_read/models/analysis.py`
- Create: `tests/samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json`
- Create: `tests/test_blueprint_cpp.py`

**Interfaces:**
- Consumes: `BlueprintSemantic` or its projected dict. Task 8 must serialize the
  parent, variable definitions, function declarations, type-resolution results,
  ordered property entries, and native reflection metadata into that semantic
  value; the renderer does not look up a `PackageDocument`, reopen bytes, or
  depend on hidden global type state.
- Produces: `build_cpp_ast(semantic: BlueprintSemantic) -> CppClassDecl`, `CppProjection(header_text, source_text, diagnostics, translation_stats)`, and public `render_cpp(semantic_dict: dict[str, Any], mode: Literal["declaration", "migration"]) -> CppProjection`.
- Scope: Blueprint-family assets only. Material uses the editor-builder projection in Task 10A; tables/curves/structs/enums use structured-data projectors in Task 10A. Do not force those assets through `CppClassDecl`.

**Declaration-scope reference (not a runtime dependency):**
- Epic plugin: `Engine/Plugins/Editor/BlueprintHeaderView/` — editor UI preview of a Blueprint as a C++ header (variables, structs, functions). It does not write `.h`/`.cpp` files and must not be imported, spawned, or scraped at runtime.
- Reuse existing native type/signature helpers already in-tree: `kismet/native_fields.py` (`build_native_function_signature`, `native_field_cpp_type`).

The Header View comparison is limited to declaration semantics: reflected class
inheritance, properties, structs, functions, dispatchers, components, and
metadata. It is not evidence that a Blueprint graph has a one-to-one C++ body
or that generated C++ can be compiled into behavior without project-specific
native APIs. Migration mode must therefore emit static reconstructed control
flow and calls, preserve statement/source identity, and mark native-only,
unknown, or semantically unresolved bodies as `untranslated`/
`unavailable`; it must never silently replace them with an empty or guessed
implementation. Constructors, parent construction, variable event dispatch,
reflection flags, and generated-class/CDO ownership are declaration inputs and
must be covered by the source metadata retained in Tasks 3, 6, and 7.

Translation statuses required by the design:
`translated` | `represented` | `untranslated` | `unavailable`.

- [ ] **Step 1: Commit a normalized declaration oracle and write C++ projection tests**

Create `tests/samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json`. It is a normalized semantic oracle for the user-owned UE5.8 fixture, not generated by this parser and not an exact-format snapshot:

```json
{
  "_provenance": "Normalized from the user-owned UE5.8 fixture graph/property declarations and Blueprint Header View declaration scope; replace through reviewed evidence if an Editor capture differs.",
  "class_name": "TestBlueprint",
  "parent_class": "AActor",
  "required_properties": {
    "Is": "bool",
    "Int": "int32",
    "Float": "double",
    "Text": "FText",
    "String": "FString",
    "Array": "TArray<double>",
    "Set": "TSet<double>"
  },
  "functions": [
    {
      "name": "NewFunction",
      "return_type": "void",
      "parameters": [
        {"name": "NewParam", "type": "bool", "direction": "in"},
        {"name": "NewParam1", "type": "bool", "direction": "out"}
      ]
    }
  ],
  "components": ["DefaultSceneRoot_GEN_VARIABLE"],
  "dispatchers": ["NewEventDispatcher"]
}
```

The `_provenance` field records that declarations were normalized against the fixture's graph/property data and Blueprint Header View scope. If an Editor-generated Header View capture later disagrees, the capture wins and the oracle changes in a reviewed evidence commit.

Before locking the oracle, dump a one-time measured projection of `MyProject_UE58_TestBlueprint.uasset` under `temp/quality-v3/` (variables, functions, components, dispatchers) and fill the JSON only from that dump. Fields not present in the dump stay out of the oracle until measured; do not invent `DefaultSceneRoot_GEN_VARIABLE`, `NewEventDispatcher`, or parameter directions without that evidence.

```python
# tests/test_blueprint_cpp.py
import json
from pathlib import Path
import pytest

from uasset_read.projections.cpp_ast import build_cpp_ast
from uasset_read.projections.cpp_render import render_cpp


ORACLE = json.loads(
    (Path(__file__).parent / "samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json")
    .read_text(encoding="utf-8")
)


def test_declaration_ast_matches_normalized_oracle(ue58_semantic):
    decl = build_cpp_ast(ue58_semantic)
    assert decl.name == ORACLE["class_name"]
    assert decl.parent == ORACLE["parent_class"]
    actual_properties = {item.name: item.type.name for item in decl.properties}
    assert ORACLE["required_properties"].items() <= actual_properties.items()
    function = next(item for item in decl.functions if item.name == "NewFunction")
    expected = ORACLE["functions"][0]
    assert function.return_type.name == expected["return_type"]
    assert [(p.name, p.type.name, p.direction) for p in function.params] == [
        (p["name"], p["type"], p["direction"]) for p in expected["parameters"]
    ]
    assert decl.constructors
    assert decl.constructors[0].parent_call is not None


def test_declaration_mode_contains_blueprint_header_elements(stackobot_semantic):
    from uasset_read.parsers.blueprint.correlation import project_semantic_blueprint

    result = render_cpp(project_semantic_blueprint(stackobot_semantic), mode="declaration")
    assert "UCLASS" in result.header_text
    assert "UPROPERTY" in result.header_text
    assert "UFUNCTION" in result.header_text
    assert result.translation_stats["declarations"] > 0


def test_migration_mode_reports_each_untranslated_instruction(ue58_semantic):
    from uasset_read.parsers.blueprint.correlation import project_semantic_blueprint

    result = render_cpp(project_semantic_blueprint(ue58_semantic), mode="migration")
    assert result.source_text
    stats = result.translation_stats
    assert stats["instructions_seen"] > 0
    assert stats["instructions_seen"] == (
        stats["translated"]
        + stats["represented"]
        + stats["untranslated"]
        + stats["unavailable"]
    )


def test_unresolved_type_is_not_silently_void(stackobot_semantic):
    from uasset_read.parsers.blueprint.correlation import project_semantic_blueprint

    result = render_cpp(project_semantic_blueprint(stackobot_semantic), mode="declaration")
    assert "/* unresolved:" in result.header_text or result.diagnostics
```

Do not add a compiler-backed test to the blocking suite. A local compiler
cannot provide Unreal's generated-header, macro, delegate, and reflected-type
environment, so it would make this pure-Python project flaky without proving
semantic correctness. The normalized AST oracle and `json.dumps()`/token
validity checks remain the blocking tests. A real UE compilation probe may be a
separate evidence-backed follow-up with an actual generated prelude.

- [ ] **Step 2: Run the tests and verify the projection is absent**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_cpp.py tests/test_size_baseline.py -q`

Expected: missing renderer or projection fields.

- [ ] **Step 3: Implement the C++ AST**

`render_cpp` is the public document-boundary entry and accepts only the projected dictionary. Keep the typed implementation internal so CLI/Agent cannot bypass the stable v3 shape. Because Task 8 embeds all declaration/type/reflection context, neither entry point accepts a `PackageDocument` or reads source bytes:

```python
def render_cpp(semantic_dict: dict[str, Any], mode: Literal["declaration", "migration"]) -> CppProjection:
    """Public C++ entry for ObjectRecord.semantic dictionaries (E1)."""
    ir = _coerce_semantic(semantic_dict)
    return render_cpp_ir(ir, mode)

def render_cpp_ir(semantic: BlueprintSemantic, mode: Literal["declaration", "migration"]) -> CppProjection:
    """Internal typed-IR renderer used by build_cpp_ast and unit tests."""
    ...
```

`_coerce_semantic` is private and lives in `cpp_render.py`. It is the only place that understands the dict→IR mapping; do not scatter `isinstance` checks through the renderer. `build_cpp_ast(semantic: BlueprintSemantic)` and `render_cpp_ir()` take typed IR only.

```python
@dataclass
class CppType:
    name: str
    is_pointer: bool = False
    is_reference: bool = False
    resolved: bool = True


@dataclass
class CppParam:
    name: str
    type: CppType
    direction: Literal["in", "out", "inout"] = "in"
    default: str | None = None


@dataclass
class CppFunctionDecl:
    name: str
    return_type: CppType
    params: list[CppParam]
    specifiers: list[str]
    is_const: bool = False


@dataclass
class CppPropertyDecl:
    name: str
    type: CppType
    specifiers: list[str]


@dataclass
class CppComponentDecl:
    name: str
    type: CppType


@dataclass
class CppDispatcherDecl:
    name: str
    params: list[CppParam]


@dataclass
class CppConstructorDecl:
    name: str
    parent_call: str | None
    component_initializers: list[str]
    variable_initializers: list[str]
    body: list["CppStmt"]
    status: Literal["translated", "represented", "untranslated", "unavailable"]


@dataclass
class CppClassDecl:
    name: str
    parent: str
    functions: list[CppFunctionDecl]
    properties: list[CppPropertyDecl]
    components: list[CppComponentDecl]
    dispatchers: list[CppDispatcherDecl]
    constructors: list[CppConstructorDecl]


@dataclass
class CppStmt:
    kind: str
    text: str
    statement_index: int | None = None
    serialized_start: int | None = None
    serialized_end: int | None = None
    function_name: str | None = None
    object_id: str | None = None
    source_node_id: str | None = None
    source_range: ByteRegion | None = None
    status: Literal["translated", "represented", "untranslated", "unavailable"] = "unavailable"
    diagnostic: str | None = None


@dataclass
class CppProjection:
    header_text: str
    source_text: str
    diagnostics: list[Diagnostic]
    translation_stats: dict[str, int]
```

`translation_stats` always contains integer keys
`instructions_seen`, `translated`, `represented`, `untranslated`,
`unavailable`, and `declarations`. The sum of the four status counters equals
`instructions_seen`; declaration counts are separate.

Do not concatenate arbitrary bytecode strings into C++ source. Every emitted statement is an AST node with a status.

- [ ] **Step 4: Implement declaration rendering based on Blueprint Header View scope**

Render:
- `UCLASS` + parent;
- `UPROPERTY` variables from `variable_definitions` and retained `VarType`/native reflection data;
- `UFUNCTION` signatures from `function_declarations` and native field helpers;
- components and construction declarations;
- generated-class/CDO constructor records, including explicit parent
  constructor calls, component initializers, and variable initializers;
- event dispatchers;
- variable-change/event-dispatch records as delegate/event declarations or
  status-bearing migration statements;
- access/metadata where recoverable.

Unresolved types render as diagnostic-bearing names (`/* unresolved: Foo */ Foo`) and are never silently replaced with `void`.

- [ ] **Step 5: Implement migration rendering and output accounting**

Map known instructions to C++ AST nodes:
- literals / pure operators → expressions (`translated`);
- resolvable calls → call statements (`translated` or `represented` when only a reference is known);
- known control flow (`if`, sequential assignment, return) → C++ control statements;
- unsupported/ambiguous ops → a self-contained migration hook comment/statement (`untranslated`) plus embedded projection diagnostic carrying `statement_index`, serialized range, `function_name`, and `object_id`.

Every instruction in every function must appear in `translation_stats`. Output is an auditable migration projection, not a claim of binary/runtime equivalence. Native parent constructors, native function bodies, VM implementation details, and missing editor-only data remain explicit represented/unavailable boundaries.

- [ ] **Step 6: Run C++ projection tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_cpp.py tests/test_blueprint_cfg.py tests/test_blueprint_correlation.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/projections src/uasset_read/models/analysis.py tests/samples/golden/blueprint_header_view tests/test_blueprint_cpp.py tests/size-baseline.json
git commit -m "feat: project blueprint semantics to auditable cpp"
```

### Task 10A: Add the type-aware projection registry and non-Blueprint projections

**Files:**
- Create: `src/uasset_read/projections/records.py`
- Create: `src/uasset_read/projections/registry.py`
- Create: `src/uasset_read/projections/material_builder.py`
- Create: `src/uasset_read/projections/data_exports.py`
- Create: `src/uasset_read/projections/bundle.py`
- Modify: `src/uasset_read/models/analysis.py`
- Modify: `src/uasset_read/parsers/asset_types/registry.py`
- Create: `tests/test_asset_projections.py`
- Create: `tests/test_single_output.py`

**Interfaces:**
- Consumes: one `PackageDocument`, projected `ObjectRecord.semantic` dictionaries, `MaterialGraph` projection, normalized property values, object references, and the Blueprint C++ projector from Task 10.
- Produces: deterministic embedded `ProjectionRecord` records, a capability matrix, and a single-document writer. A projector never reparses package bytes and never invokes Unreal Editor.

```python
class AssetProjector(Protocol):
    asset_kinds: tuple[str, ...]

    def can_project(self, obj: ObjectRecord) -> bool: ...

    def project(
        self,
        document: PackageDocument,
        obj: ObjectRecord,
    ) -> list[ProjectionRecord]: ...


class ProjectorRegistry:
    @classmethod
    def default(cls) -> "ProjectorRegistry": ...
    def register(self, projector: AssetProjector, *, priority: int = 0) -> None: ...
    def project_object(self, document: PackageDocument, object_id: str) -> list[ProjectionRecord]: ...
    def project_document(self, document: PackageDocument) -> list[ProjectionRecord]: ...


def write_projected_document(
    document: PackageDocument,
    output_path: Path,
    *,
    max_main_bytes: int | None = None,
) -> Path: ...


def minimum_canonical_envelope_bytes(document: PackageDocument) -> int: ...


class OutputBudgetError(ValueError):
    """The requested main-document limit cannot fit the mandatory envelope."""
```

`project_document()` on the registry means all objects in the supplied
`PackageDocument`; it is not the bounded `uasset_read.projection.project_document`
response API. The registry emits specialized artifacts only. Generic object
identity/properties/semantic data already live in `PackageDocument.objects` and
are not copied into a generic `object` projection. A recognized family with
missing required input receives an explicit `unavailable` record; an unknown
family may legitimately return no additional projection.

Define the registry helpers with these contracts:

```python
from uasset_read.models.diagnostics import make_diagnostic


def dependency_ids(document: PackageDocument, object_id: str) -> list[str]:
    """Return deterministic outgoing relation targets for one source object."""
    return sorted({
        relation.to_id
        for relation in document.relations
        if relation.from_id == object_id and relation.to_id != object_id
    })


def _unavailable_blueprint_projections(
    object_id: str,
    reason: str,
) -> list[ProjectionRecord]:
    return [
        ProjectionRecord(
            kind=kind,
            source_object_id=object_id,
            media_type=media_type,
            content=None,
            embedded=True,
            status="unavailable",
            completeness=None,
            dependencies=[],
            diagnostics=[make_diagnostic(
                reason,
                "Blueprint semantic input is unavailable",
                "projection.blueprint",
                object_id=object_id,
            )],
        )
        for kind, media_type in (
            ("cpp_declaration", "text/x-c++hdr"),
            ("cpp_migration", "text/x-c++src"),
        )
    ]


```

`make_diagnostic()` is the existing structured-diagnostic factory imported by
`projections/records.py`; it must not create free-form strings. The complete
Blueprint trace remains in `objects[].semantic`; no second record is created
just to copy graphs, functions, calls, or variables.

The initial capability matrix is fixed as follows:

| Asset family | Embedded projections | Capability rule |
|---|---|---|
| Blueprint / AnimBlueprint / BlueprintFunctionLibrary / BlueprintInterface | `cpp_declaration`, `cpp_migration` | declaration can be `translated`; behavior is per-instruction status-bearing migration output; the full trace remains in `objects[].semantic` |
| Material | `material_editor_builder` | the complete graph remains in `objects[].semantic.material_graph`; builder is `represented` when the editor graph is present, otherwise `unavailable` with an explicit diagnostic |
| MaterialInstance | `material_instance`, `material_parameters` | parent and overrides must be resolved; unresolved parent is explicit |
| DataTable | `data_table`, `data_table_csv`, `data_table_json` | row struct and values must be decoded; unknown row bytes remain opaque |
| CurveTable / RichCurve | `curve_table`, `curve_table_csv`, `curve_table_json` | keys and interpolation data are explicit; compressed-only data is unavailable unless decoded |
| UserDefinedStruct / UserDefinedEnum | `cpp_declaration`, `defaults_json` | fields/enumerators and defaults are exported when reflected data is present |
| Other graph assets | `graph`, optional `asset_builder_cpp` | only registered graph semantics are emitted; no generic fake C++ body |
| Physical/binary assets | `asset_metadata`, `payload_reference` | metadata and payload references only unless a separate, evidenced projector exists |

Each embedded projection carries `source_object_id`, `kind`, `media_type`, `content`, `embedded`, `status`, `completeness`, `dependencies`, and diagnostics. Recognized but unsupported families still receive a capability descriptor with `unavailable`; they do not silently disappear. A completely unknown family may have no additional projection because its generic identity/properties/semantic record is already canonical in `PackageDocument.objects`. No projection gets a physical output path merely because it has a different media type.

- [ ] **Step 1: Write registry and embedded-projection contract tests**

```python
# tests/test_asset_projections.py
from uasset_read.projections.registry import ProjectorRegistry


def test_registry_selects_one_owner_for_each_asset_family(document):
    registry = ProjectorRegistry.default()
    for obj in document.objects:
        projections = registry.project_object(document, obj.id)
        assert all(item.source_object_id == obj.id for item in projections)
        assert all(item.status in {
            "translated", "represented", "untranslated", "unavailable"
        } for item in projections)
    assert any(item.kind == "cpp_declaration" for item in registry.project_document(document))


def test_cooked_material_builder_is_not_reported_as_complete(cooked_material):
    projections = ProjectorRegistry.default().project_document(cooked_material)
    builders = [item for item in projections if item.kind == "material_editor_builder"]
    assert builders
    assert builders[0].status == "unavailable"
```

```python
# tests/test_single_output.py
import json
import pytest

from uasset_read.projections.registry import ProjectorRegistry
from uasset_read.projections.bundle import write_projected_document


def test_projections_are_embedded_and_have_no_default_output_paths(document):
    projections = ProjectorRegistry.default().project_document(document)
    assert projections
    assert all(item.embedded for item in projections)
    assert all(item.content is not None or item.status == "unavailable" for item in projections)


def test_single_document_writer_writes_canonical_document(document, tmp_path):
    output = write_projected_document(document, tmp_path / "Asset.json")
    assert output.name == "Asset.json"
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["package"]
    assert "objects" in payload
    assert "projections" in payload

def test_writer_rejects_a_limit_below_the_mandatory_envelope(document, tmp_path):
    from uasset_read.projections.bundle import minimum_canonical_envelope_bytes, OutputBudgetError

    minimum = minimum_canonical_envelope_bytes(document)
    with pytest.raises(OutputBudgetError):
        write_projected_document(document, tmp_path / "TooSmall.json", max_main_bytes=minimum - 1)
```

- [ ] **Step 2: Run the focused tests and verify the registry is absent**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_asset_projections.py tests/test_single_output.py tests/test_material_graph.py tests/test_size_baseline.py -q`

Expected: import or registry assertions fail before the projection layer exists; existing material graph tests remain the decoder evidence.

- [ ] **Step 3: Implement embedded projection records and deterministic dispatch**

Implement embedded `ProjectionRecord` records and `ProjectorRegistry` with these rules:

1. match semantic `kind` first, then normalized `class_name` family;
2. choose the highest-priority projector and reject ambiguous equal-priority ownership;
3. sort projections by `(source_object_id, kind, media_type)`;
4. preserve every diagnostic and dependency without reparsing;
5. do not add a generic structured `object` projection: `PackageDocument.objects` is the canonical generic record; an unknown family may return no additional projection;
6. keep C++ header/source text, CSV text, and structured JSON content in the projection record instead of assigning output paths;
7. compute projection dependencies from object relations and referenced imports; do not return `dependencies=[]` when the document contains resolvable references;
8. keep the complete Blueprint trace in `objects[].semantic`; add only non-duplicating C++ artifacts to the registry.

Blueprint C++ wiring (Task 10 → this registry):

```python
class BlueprintCppProjector:
    asset_kinds = ("blueprint", "anim_blueprint", "blueprint_function_library",
                   "blueprint_interface")

    def can_project(self, obj: ObjectRecord) -> bool:
        return (obj.semantic or {}).get("kind") in self.asset_kinds

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = obj.semantic  # E1: dict
        if not isinstance(semantic, dict) or semantic.get("kind") not in self.asset_kinds:
            return _unavailable_blueprint_projections(obj.id, "blueprint_semantic_unavailable")
        decl = render_cpp(semantic, mode="declaration")
        mig = render_cpp(semantic, mode="migration")
        dependencies = dependency_ids(document, obj.id)
        return [
            ProjectionRecord(
                kind="cpp_declaration",
                source_object_id=obj.id,
                media_type="text/x-c++hdr",
                content=decl.header_text,
                embedded=True,
                status=_status_from_stats(decl.translation_stats),
                completeness=_completeness(decl.translation_stats),
                dependencies=dependencies,
                diagnostics=decl.diagnostics,
            ),
            ProjectionRecord(
                kind="cpp_migration",
                source_object_id=obj.id,
                media_type="text/x-c++src",
                content=mig.source_text,
                embedded=True,
                status=_status_from_stats(mig.translation_stats),
                completeness=_completeness(mig.translation_stats),
                dependencies=dependencies,
                diagnostics=mig.diagnostics,
            ),
        ]
```

Define `_unavailable_blueprint_projections()` and `dependency_ids()` in
`projections/registry.py`/`projections/records.py` with explicit return types.
The Blueprint projector therefore yields two records (or two explicit
`unavailable` records) without reparsing package bytes; the complete trace is
already in `objects[].semantic`. Register
`BlueprintFunctionLibrary` and `BlueprintInterface` only after Task 8 emits
those semantic kinds; otherwise the registry must emit their explicit
unavailable capability rather than treating them as ordinary Blueprints.

- [ ] **Step 4: Implement material builder and structured-data projectors**

`material_builder.py` emits editor-only C++ that creates expressions and connects material properties through the equivalent `UMaterialEditingLibrary` operations. It must never emit HLSL, shader bytecode, or a normal runtime `UMaterial` subclass claim.

`data_exports.py` emits embedded projection records for:

- DataTable row schema, CSV, and JSON with stable column order;
- CurveTable/RichCurve key arrays including interpolation and tangent fields;
- UserDefinedStruct/Enum C++ declarations and JSON defaults;
- MaterialInstance parent/parameter overrides as JSON and optional initialization code.

Only register a dedicated projector when the current repository has a real
fixture proving the required fields. For an unproven but recognized asset
family, keep the generic object/semantic record and emit a capability or
`unavailable` result; do not add a projector merely to enlarge the matrix.

Freeze the data projection shapes in this task so later projectors do not
invent incompatible formats:

```json
{
  "kind": "data_table",
  "row_struct": "/Script/Game.MyRow",
  "columns": [{"name": "Score", "type": "int32"}],
  "rows": [{"name": "Row_A", "values": {"Score": 10}}]
}
```

`data_table_json` embeds that object; `data_table_csv` embeds RFC 4180-style
text with the same ordered columns. Curve output uses
`{"kind":"curve_table","curves":[{"name":...,"keys":[{"time":...,"value":...,"interp":...,"arrive_tangent":...,"leave_tangent":...}]}]}`.
User-defined structs/enums use `fields`/`enumerators` plus `defaults`; a
MaterialInstance uses `parent`, `scalar_parameters`, `vector_parameters`,
`texture_parameters`, and `static_switch_parameters`. If a required field is
not decoded, the record keeps the available fields and reports `represented`,
`untranslated`, or `unavailable` with the exact source diagnostic; the
projection status vocabulary has no separate `partial` value.

When the required semantic record is absent, emit an empty projection only with `unavailable` status and a diagnostic code; do not invent a field list or value from positional bytes.

- [ ] **Step 5: Implement single-document materialization**

`build_canonical_document(document) -> dict[str, Any]` materializes all object
records and all registry projections with no selection or pagination. It is the
only input to `write_projected_document()`. The writer serializes the package
envelope, all objects, semantic data, projection records, capabilities,
diagnostics, and payload references into one UTF-8 JSON file. It never
overwrites the source asset. The core writer has no automatic split path: if
`max_main_bytes` is supplied and the complete UTF-8 document would exceed it,
raise `OutputBudgetError` before creating any file. `ProjectionRecord.external`
and `SidecarRecord` remain schema-ready late-bound fields; implement their
materialization only in a follow-up after a real measured output proves that a
single file is unsafe. Ordinary asset, graph, function, and export boundaries
never trigger a sidecar.

`OutputBudgetError(ValueError)` is raised before any output file is created when
`max_main_bytes < minimum_canonical_envelope_bytes(document)` or when the full
document exceeds an explicitly supplied limit. The writer uses UTF-8 byte
length, not Python character count. No test uses an arbitrary limit to pretend
that a sidecar was necessary.

- [ ] **Step 6: Run projection tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_asset_projections.py tests/test_single_output.py tests/test_material_graph.py tests/test_blueprint_cpp.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/projections src/uasset_read/models/analysis.py src/uasset_read/parsers/asset_types/registry.py tests/test_asset_projections.py tests/test_single_output.py tests/size-baseline.json
git commit -m "feat: add embedded type-aware asset projections"
```

### Task 11: Replace output and CLI plumbing with projections

**Files:**
- Modify: `src/uasset_read/projection.py`
- Modify: `src/uasset_read/cli.py`
- Modify: `src/uasset_read/agent_tools.py`
- Modify: `src/uasset_read/package.py`
- Modify: `src/uasset_read/__init__.py`
- Modify: `src/uasset_read/projections/registry.py`
- Modify: `src/uasset_read/projections/bundle.py`
- Create: `tests/test_projection_v3.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: one fully populated `PackageDocument` plus selection/depth/size options. C++ rendering consumes the **projected** `objects[].semantic` dict (E1), not a live dataclass.
- Produces: one canonical JSON document per input package, bounded Agent responses, and embedded type-aware projections from projection functions only.
- APIs: `project_document(document, *, view, object_ids=None, limit=None, offset=None, max_bytes=None) -> dict` is the bounded response API; `build_canonical_document(document) -> dict` and `write_projected_document(...)` are the complete file API. `project_cpp(document, *, object_id, mode) -> CppProjection` loads `object.semantic` as the dict and calls `render_cpp(semantic_dict, mode=...)`.
- Projection API: `build_projection_records(document, *, object_ids=None, kinds=None) -> list[ProjectionRecord]`.
- Output API: `write_projected_document(document, output_path, *, max_main_bytes=None) -> Path`; it writes one canonical document. In the core plan an explicit limit that cannot contain the complete document raises a structured budget error; sidecar materialization is deferred.

**Current-state notes:**
- Envelope is currently hardcoded `"format": "uasset_read.package"`, `"format_version": "2.0"` in `projection.py:214-215`. After Task 1 it should already emit the projection-level `FORMAT_VERSION`; this task finishes CLI/Agent wiring.
- Retired CLI flags stay retired (`cli.py` retired set`). C++ content is embedded in the canonical projection document, not exposed as a separate output mode or as a resurrection of Gate K `cpp_code` fields on Kismet results.
- `cli.py:186-188` has a *separate* batch envelope (`format: uasset_read.batch`, `format_version: 1.0`). That is the multi-file batch wrapper, not the per-package projection document. Do **not** change the batch envelope's `format_version` in this task unless a written decision retires or renumbers it; each per-package entry inside `results[]` must carry the v3 canonical document produced by `build_canonical_document`.

- [ ] **Step 1: Write projection consistency tests**

```python
# tests/test_projection_v3.py
from pathlib import Path

from uasset_read.projections.cpp_render import render_cpp
from uasset_read.projection import project_document
from tests.fixtures import find_blueprint_object, parse_sample


def test_json_and_cpp_use_the_same_document():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    json_view = project_document(document, view="semantic")
    blueprint = find_blueprint_object(document)
    # E1: semantic is a dict; render_cpp must not require a live BlueprintSemantic.
    assert isinstance(blueprint.semantic, dict)
    cpp_view = render_cpp(blueprint.semantic, mode="declaration")
    assert json_view["package"]["name"]
    assert cpp_view.header_text
    assert json_view["format_version"] == "3.0"


def test_large_payloads_are_not_embedded_by_default(document):
    output = project_document(document, view="semantic")
    assert output.get("payloads", []) == []


def test_projection_embeds_type_aware_content(document):
    output = project_document(document, view="semantic")
    assert "projections" in output
    assert all("source_object_id" in item for item in output["projections"])
    assert all(item["embedded"] for item in output["projections"])
```

- [ ] **Step 2: Run output tests and verify old plumbing fails the v3 assertions**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_projection_v3.py tests/test_cli.py tests/test_payload_extraction.py tests/test_size_baseline.py -q`

Expected: format version, projection, or C++ command assertions fail before migration.

- [ ] **Step 3: Make `package.py` a thin orchestration entrypoint**

Route source detection → layout → reader → property decode → domain registry → analysis → projection through the named modules. Cache keys must include source/container/mapping stats (path, size, layout kind, usmap id when present).

- [ ] **Step 4: Wire the CLI to the canonical output writer and embedded projections**

```text
python -m uasset_read <path> --depth decode --view semantic -o out/<package>.json
```

The CLI always writes one canonical JSON document per input package. The projection registry embeds Blueprint C++ declaration/migration content, Material builder content, and table CSV/JSON content in that document. There is no user-selected split or standalone projection-output mode in this task. Return nonzero only for fatal package, output-path, or explicitly requested budget failures; partial/unavailable capabilities stay in structured diagnostics when the package envelope is intact. Automatic sidecars are not implemented until a measured safety/size failure justifies a follow-up.

When `-o/--output` is a file, the CLI calls `write_projected_document()` and
does not pass `--limit`, `--offset`, or object selection into the canonical
writer; reject that combination with a usage error. Query-style stdout/Agent
responses may continue to use the bounded `project_document()` API. Batch mode
keeps its v1 wrapper while each `results[]` item is an independently complete
v3 package document.

- [ ] **Step 5: Update Agent tools to project the same document**

Keep the six tool purposes (`inspect_package`, `list_objects`, `get_object`, `list_dependencies`, `get_diagnostics`, `extract_payload`). Implement them by calling the v3 projection layer with selection/pagination/`max_bytes` applied after semantic projection. Expose embedded projection records and capabilities through `get_object`; sidecar materialization is outside this core task and is never an Agent transport. Do not reintroduce process-global logging.

- [ ] **Step 6: Run CLI/Agent/projection tests and commit**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_projection_v3.py tests/test_cli.py tests/test_payload_extraction.py tests/test_core.py tests/test_size_baseline.py -q`

Commit:

```powershell
git add src/uasset_read/projection.py src/uasset_read/cli.py src/uasset_read/agent_tools.py src/uasset_read/package.py src/uasset_read/__init__.py tests/test_projection_v3.py tests/test_cli.py tests/size-baseline.json
git commit -m "refactor: route outputs through package document projections"
```

### Task 12: Add sample quality gates and complete verification

**Files:**
- Create: `tests/test_complete_samples.py`
- Modify: `tests/samples/quality_baseline.json`
- Create: `temp/quality-v3/README.md` (untracked investigation output; do not commit)
- Modify: `tests/test_quality_baseline_generator.py`
- Modify: `tests/test_size_baseline.py`

**Interfaces:**
- Consumes: complete parser output, sample manifest, reference reports as corroborating evidence only, and the type-aware `ProjectorRegistry`.
- Produces: repeatable acceptance checks for byte accounting, domain coverage, embedded C++/data projection coverage, single-document output, capability/status coverage, and failure truthfulness.

**Acceptance numbers to lock (from spec + manifest, verified 2026-09-16):**

| Gate | Sample | Required proof |
|---|---|---|
| 1 | `StackOBot_BP_Drone.uasset` | 31 exports; 2 graphs; 3 Kismet functions; 85 expressions; CFG blocks/edges; call targets; var reads/writes |
| 2 | `MyProject_UE58_TestBlueprint.uasset` | `K2Node_IfThenElse` present; `EX_JumpIfNot` present; explicit true/false CFG edges |
| 3 | `StackOBot_M_BotBase.uasset` | 42 exports; 39 material expressions; expression properties; links when present |
| 4 | `BP_UnversionedTest.uasset` / `DA_UnversionedTest.uasset` | schema decode or bounded opaque; no position-only field guessing |
| 5 | committed containers | IoStore metadata/classification and truthful Zen unavailability; chunk extraction, traditional Pak, and real Zen package parsing remain deferred until redistributable fixtures exist |
| 6 | C++ projection | declaration AST matches the normalized UE5.8 oracle; migration has a dual-offset trace for every instruction |
| 7 | type-aware projections | canonical objects/semantic carry generic data; recognized families have specialized embedded projections or explicit `unavailable`; Material has semantic graph/builder status; data assets use CSV/JSON where decoded |
| 8 | single-document output | each input package produces one canonical JSON document containing package/object/semantic/projection/capability/diagnostic data; ordinary asset or graph boundaries do not split it |
| 9 | byte accounting | every requested non-empty export scope has non-empty, contiguous, non-overlapping decoded/opaque/payload/unavailable leaves |
| 10 | suite | full pytest + structure/size/quality baselines |

- [ ] **Step 1: Write sample acceptance tests**

```python
# tests/test_complete_samples.py
from tests.fixtures import parse_sample
from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation
from uasset_read.parsers.material.graph import MaterialGraphDecoder


def count_kismet_expressions(document) -> int:
    total = 0
    for obj in document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            total += fn.get("expression_count") or 0
    return total


def test_stackobot_blueprint_acceptance():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="decode")
    assert len(document.objects) == 31
    assert count_kismet_expressions(document) == 85
    semantic = BlueprintCorrelation().build(document)
    assert len(semantic.functions) == 3
    assert semantic.control_flow


def test_ue58_blueprint_acceptance():
    document = parse_sample("MyProject_UE58_TestBlueprint.uasset", depth="decode")
    assert len(document.objects) == 24
    opcodes = set()
    for obj in document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            opcodes.update(item["opcode"] for item in fn["instructions"])
    assert "EX_JumpIfNot" in opcodes


def test_stackobot_material_acceptance():
    document = parse_sample("StackOBot_M_BotBase.uasset", depth="decode")
    assert len(document.objects) == 42
    graph = MaterialGraphDecoder().decode(document, material_object_id="export:0")
    assert len(graph.expressions) == 39


def test_type_aware_projection_acceptance():
    from uasset_read.projections.registry import ProjectorRegistry

    document = parse_sample("StackOBot_M_BotBase.uasset", depth="decode")
    projections = ProjectorRegistry.default().project_document(document)
    material = next(obj for obj in document.objects if obj.id == "export:0")
    assert len((material.semantic or {}).get("material_graph", {}).get("expressions", [])) == 39
    builder = [item for item in projections if item.kind == "material_editor_builder"]
    assert builder and builder[0].status in {"represented", "unavailable"}
    assert all(item.source_object_id for item in projections)


def test_single_document_contains_all_projection_sections(stackobot_document):
    from uasset_read.projections.bundle import build_canonical_document

    output = build_canonical_document(stackobot_document)
    assert output["format_version"] == "3.0"
    assert output["package"]
    assert output["objects"]
    assert "projections" in output
    assert all(item["embedded"] for item in output["projections"])


def test_every_requested_export_is_fully_accounted(stackobot_document):
    expected = {obj.id for obj in stackobot_document.objects if obj.serial_region and obj.serial_region.size > 0}
    scopes = stackobot_document.byte_accounting.scopes
    assert expected
    assert expected <= set(scopes)
    for object_id in expected:
        scope = scopes[object_id]
        assert scope.leaves
        scope.validate_full_coverage()
```

- [ ] **Step 2: Run the sample tests and record real failures**

Run: `$env:PYTHONPATH='src'; python -m pytest tests/test_complete_samples.py tests/test_size_baseline.py -q`

Expected: failures identify remaining parser gaps by sample and feature, not generic assertion noise.

- [ ] **Step 3: Generate quality-v3 evidence under `temp/`**

Run the parser for StackOBot Blueprint, UE5.8 Blueprint, StackOBot Material, unversioned samples, and available container fixtures. Store one canonical JSON output per sample containing diagnostics, the complete Blueprint semantic trace, Blueprint C++ declaration/migration projections, Material graph/editor-builder projections, available DataTable/CurveTable/struct/enum projections, and the type capability matrix under `temp/quality-v3/`. Do not generate sidecars unless a measured hard safety/size failure is recorded and a follow-up boundary is explicitly enabled. Include a short README listing commands and git SHA. `temp/` outputs are investigation artifacts and are not staged; only fixtures, tests, manifest facts, and measured baselines are committed.

- [ ] **Step 4: Update only measured baselines**

Update `tests/samples/quality_baseline.json` and `tests/size-baseline.json` from the generated evidence. Add the gate samples that are currently missing from the quality baseline (StackOBot BP, UE58 BP/Material, StackOBot material). Do not suppress a parser failure by widening a baseline or marking an unavailable feature complete.

- [ ] **Step 5: Run all verification commands**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q
$env:PYTHONPATH='src'; python -m pytest tests/test_complete_samples.py tests/test_quality_baseline_generator.py tests/test_size_baseline.py -q
python -m compileall -q src
```

Expected: all tests pass, all baseline gates pass, every discovered Blueprint instruction has a translation status, every sampled non-Blueprint asset has either its best-fit embedded projection or an explicit capability/diagnostic outcome, and ordinary samples produce one canonical JSON file each.

- [ ] **Step 6: Commit the acceptance gate and close the plan**

Commit:

```powershell
git add tests/test_complete_samples.py tests/samples/quality_baseline.json tests/test_quality_baseline_generator.py tests/test_size_baseline.py
git commit -m "test: add complete parser quality gates"
```

## Final Review Checklist

- [ ] `PackageDocument` is the only aggregate passed to JSON, CLI, Python, Agent, and C++ projections.
- [ ] Edit Playbook E1: `objects[].semantic` is a dict at the document boundary; typed IR is not required by fixtures/CLI.
- [ ] Edit Playbook E2: Legacy `PackageArchive` remains the reader owner; any temporary source adapter has one explicit consumer and is deleted with that migration, with no duplicate table-reader stack.
- [ ] No reference project is imported, executed, spawned, or required at runtime.
- [ ] Legacy and Zen readers have separate format-specific code paths; real Zen payload support remains `unverified` unless a committed fixture proves it.
- [ ] Tagged and unversioned readers cannot silently substitute for each other.
- [ ] `exec_chains` is documented and implemented as a derived direct-edge summary, not runtime simulation.
- [ ] Blueprint functions expose instructions, CFG, calls, variable accesses, variable definitions, and unresolved records; declarations are not conflated with accesses.
- [ ] Kismet `statement_index` is the UE logical `CodeOffset` coordinate, `statement_ordinal` is list order, and both logical and physical ranges are preserved.
- [ ] Every correlated call, variable, and entrypoint carries `match_method`, bounded `confidence`, and truthful `unresolved` state.
- [ ] Material expressions expose nodes and links when present.
- [ ] C++ declaration AST matches the normalized UE5.8 declaration oracle and covers the Blueprint Header View scope.
- [ ] C++ migration output is traceable, status-bearing, and never claims native-body equivalence.
- [ ] Type-aware projection registry has one deterministic owner per proven asset family and does not duplicate the generic object/semantic trace or require every asset to produce C++.
- [ ] Material output distinguishes graph JSON from editor-builder C++; it never claims shader/HLSL equivalence.
- [ ] DataTable and CurveTable output uses stable CSV/JSON structures, with optional C++ initializers only when values are decoded.
- [ ] UserDefinedStruct/Enum and MaterialInstance have explicit declaration/data capabilities; physical/binary assets use metadata/payload references unless an evidenced projector exists.
- [ ] Every embedded projection has a source object ID, media type, content or explicit `unavailable` status, completeness, dependencies, and diagnostics.
- [ ] One input package produces one canonical JSON document; ordinary asset, graph, function, and export boundaries never split it.
- [ ] `build_canonical_document()`/`write_projected_document()` are separate from paginated `project_document()` responses; canonical files contain all object IDs.
- [ ] The core writer keeps one canonical file and rejects an explicitly impossible size limit before writing; automatic sidecars remain a separately enabled, measured hard size/safety boundary with path, size, SHA-256, source range, and reason.
- [ ] Cooked-away, encrypted, missing, and unknown data are reported as unavailable/opaque with reasons.
- [ ] Full tests, quality baseline, size baseline, and compileall verification pass.

## Evidence Appendix (immutable citations for implementers)

Use these instead of re-guessing layouts. Re-read the UE file if the field list must change.

1. Legacy summary: `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h`
2. Import/export resources: `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`
3. Tagged property tag: `Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h`
4. Unversioned fragments: `Engine/Source/Runtime/CoreUObject/Private/Serialization/UnversionedPropertySerialization.cpp` (`FUnversionedHeader`)
5. Zen package summary/bundles: `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`
6. Zen header view: `Engine/Source/Runtime/CoreUObject/Internal/Serialization/ZenPackageHeader.h`
7. Package trailer: `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageTrailer.h`
8. Kismet opcodes: `Engine/Source/Runtime/CoreUObject/Public/UObject/Script.h`
9. Kismet serialize: `Engine/Source/Runtime/CoreUObject/Public/UObject/ScriptSerialization.inl`
10. Blueprint Header View (declaration-scope reference only): `Engine/Plugins/Editor/BlueprintHeaderView/`
11. Blueprint compiler statement/context and VM backend: `Engine/Source/Editor/KismetCompiler/Public/KismetCompiledFunctionContext.h`, `Engine/Source/Editor/KismetCompiler/Private/KismetCompilerBackend.h`, and `Engine/Source/Editor/KismetCompiler/Private/KismetCompilerVMBackend.cpp`
12. Generated Blueprint class reflection/runtime fields: `Engine/Source/Runtime/Engine/Classes/Engine/BlueprintGeneratedClass.h`
13. Material expression/object graph: `Engine/Source/Runtime/Engine/Classes/Materials/MaterialExpression.h` and `Engine/Source/Runtime/Engine/Classes/Materials/Material.h`
14. Material editor reconstruction APIs: `Engine/Source/Editor/MaterialEditor/Classes/MaterialEditingLibrary.h`
15. DataTable CSV/JSON export and row serialization: `Engine/Source/Runtime/Engine/Classes/Engine/DataTable.h` and `Engine/Source/Runtime/Engine/Private/Engine/DataTable.cpp`
16. RichCurve keys and serialization: `Engine/Source/Runtime/Engine/Classes/Curves/RichCurve.h`

In-repo current entrypoints to keep working until replaced:
- `src/uasset_read/package.py` — `parse_package_document`, `PackageArchive`
- `src/uasset_read/models/document.py` — `PackageDocument`
- `src/uasset_read/projection.py` — `project_document`
- `src/uasset_read/kismet/decompile_bridge.py` — `extract_kismet_decompiled`
- `src/uasset_read/serializers/blueprint_graph.py` — `read_blueprint_graphs`, `summarize_exec_edges`
- `src/uasset_read/parsers/asset_types/handlers_impl.py` — `BlueprintFamilyHandler`, material handlers
- `src/uasset_read/agent_tools.py` — six bounded agent tools
