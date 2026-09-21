# Remaining Static UAsset v3 Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the unmerged Tasks 5–9 static Blueprint/Material IR on the execution branch, then implement the still-missing Tasks 10–12 (C++ projection, type-aware registry, canonical writer/CLI, sample acceptance gates) so each sampled package produces one complete `format_version: "3.0"` document.

**Architecture:** Keep one package-first `PackageDocument`. Tasks 5–9 already build typed Blueprint graph/CFG/correlation IR and Material expression graphs on branch `sdd/static-uasset-finish`. Remaining work turns that IR into embedded projections (`render_cpp`, `ProjectorRegistry`, `write_projected_document`) and closes acceptance gates. C++ is a projection, never a second parser.

**Tech Stack:** Python 3.10+, stdlib only, `pytest`, committed golden/oracle JSON fixtures under `tests/samples/`. No CUE4Parse/UAssetAPI/Unreal Editor runtime bridge.

**Spec:** `docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`

**Parent plan (authoritative full Tasks 1–12 step source):** `docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md`

This remaining plan does **not** re-open Tasks 1–4. Those foundations are already on `dev-0.6.0` and on this branch through the tasks 5–9 merge.

## Remaining Progress Snapshot (updated 2026-09-21 R6)

| Tasks | Marker | Evidence |
| --- | --- | --- |
| 1–4 | `implemented` | On `dev-0.6.0` @ `ced9ad8e`: `sources.py`, `layout.py`, `zen_reader.py` availability boundary, tagged/unversioned property readers, byte accounting, `FORMAT_VERSION = "3.0"` in `projection.py`. |
| 5–9 | `implemented on sdd/static-uasset-finish` (R1 green) | Tasks 5–9 modules + focused suite accepted on `sdd/static-uasset-finish`; `objects[].semantic` is projected dict for Blueprint/Material families (E1). Not complete on `dev-0.6.0` until orchestrator merge. |
| 10 / R2 | `implemented on sdd/static-uasset-finish` | `src/uasset_read/projections/cpp_ast.py`, `cpp_render.py`; `tests/test_blueprint_cpp.py`; golden oracle `tests/samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json`. |
| 10A / R3 | `implemented on sdd/static-uasset-finish` | `projections/records.py`, `registry.py`, `material_builder.py`, `data_exports.py`, `bundle.py`; `tests/test_asset_projections.py`, `tests/test_single_output.py`. |
| 11 / R4 | `implemented on sdd/static-uasset-finish` | Projection/CLI/Agent plumbing via `PackageDocument`; `tests/test_projection_v3.py`, `tests/test_cli.py`. |
| 12 / R5 | `implemented on sdd/static-uasset-finish` | `tests/test_complete_samples.py` gates 1–9; quality baseline + size baseline green in full suite. |
| R6 checklist | `walked on sdd/static-uasset-finish` | 23-item checklist walked against source/tests on HEAD `ec2d0da4`: 23 pass / 0 fail / 0 unverifiable. Full suite **442 passed**; compileall clean. Controller whole-branch review remains after this report. |

Markers describe execution-branch and (after merge `8727b067`) `dev-0.6.0`
current behavior. Controller review pass; post-merge suite 442 passed.
README feature claims updated for the landing.

**Samples present under `tests/samples/` (acceptance inputs):**

- `StackOBot_BP_Drone.uasset` — 31 exports; Blueprint gate
- `MyProject_UE58_TestBlueprint.uasset` — 24 exports; C++ declaration oracle input
- `StackOBot_M_BotBase.uasset` — 42 exports; Material gate
- `MyProject_UE58_TestMaterial.uasset` — Material editor-data sample
- `TestMaterial.uasset` — cooked/stripped material (`cooked_material` fixture)
- `BP_UnversionedTest.uasset`, `DA_UnversionedTest.uasset` — unversioned/opaque gates
- DataTable/CurveTable/struct/enum fixtures already used by sample tests

**Execution workspace:** work only in `.worktrees/sdd-static-continue` on branch `sdd/static-uasset-finish` (or a child branch created from it *inside that worktree*). Do not run cross-branch git mutations from `dev-0.6.0` main checkout. Do not stage `reference/` or unrelated dirty files.

## Global Constraints

- Pure Python 3.10+; no runtime bridge, subprocess bridge, or FFI to reference parsers/Unreal Editor.
- `PackageDocument` remains the only package-level aggregate; every export stays addressable.
- Legacy/Zen use separate readers; tagged/unversioned use separate property readers.
- No runtime Blueprint execution; control-flow and calls are static analysis only.
- No fabricated data for cooked-away graphs, unknown serialization, encryption, missing chunks, or native C++ bodies.
- `objects[].semantic` at the document boundary is `dict[str, Any] | None` (Edit Playbook E1). Typed IR (`BlueprintSemantic`, `MaterialGraph`, `FunctionAnalysis`) is internal to parser modules.
- Projection status vocabulary is exactly `translated | represented | untranslated | unavailable`.
- Breaking schema is allowed; output major is `format_version: "3.0"` (envelope field from `projection.FORMAT_VERSION`, not state on `PackageDocument`).
- One input package → one canonical JSON document. Ordinary asset/graph/function boundaries never split output.
- Sidecars are schema-ready late boundaries only; core writer keeps one file and raises `OutputBudgetError` when an explicit limit cannot fit the mandatory envelope.
- Every task ends with focused tests plus `tests/test_size_baseline.py`. Raise `tests/size-baseline.json` only from measured pytest failure output, in the same task/commit.
- All `Run:` commands are PowerShell and set `$env:PYTHONPATH='src'` before importing `uasset_read`.
- Temporary probes stay under `temp/` and are never staged.
- UE citations stay relative to the Unreal Engine source root; never hardcode a machine-local UE path.
- Parent plan Edit Playbook E0–E5 remains binding: one concern per commit, green before widen, no dual implementations, no temporary return-type shims.

## File Map (remaining only)

Create under the execution worktree:

- `src/uasset_read/projections/__init__.py`
- `src/uasset_read/projections/cpp_ast.py` — typed C++ declaration/migration AST
- `src/uasset_read/projections/cpp_render.py` — `render_cpp` / `render_cpp_ir` / `build_cpp_ast`
- `src/uasset_read/projections/records.py` — `ProjectionRecord`, `SidecarRecord`, helpers
- `src/uasset_read/projections/registry.py` — `ProjectorRegistry`, `AssetProjector`, family projectors
- `src/uasset_read/projections/material_builder.py` — Material editor-builder C++ projection
- `src/uasset_read/projections/data_exports.py` — DataTable/CurveTable/struct/enum projections
- `src/uasset_read/projections/bundle.py` — `build_canonical_document`, `write_projected_document`
- `tests/samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json`
- `tests/test_blueprint_cpp.py`
- `tests/test_asset_projections.py`
- `tests/test_single_output.py`
- `tests/test_projection_v3.py`
- `tests/test_complete_samples.py`

Modify:

- `src/uasset_read/models/analysis.py` — only if C++ needs additional IR fields already promised by Task 8 projection
- `src/uasset_read/projection.py` — bounded `project_document()` v3 envelope + embedded projections
- `src/uasset_read/cli.py` — canonical `-o` writer path
- `src/uasset_read/agent_tools.py` — same projection layer
- `src/uasset_read/package.py` — thin orchestration only if still needed after tasks 5–9
- `src/uasset_read/parsers/asset_types/registry.py` — only if projector capability status must be attached at domain-dispatch time
- `tests/samples/quality_baseline.json`
- `tests/test_cli.py`, `tests/test_quality_baseline_generator.py`, `tests/test_size_baseline.py`
- `tests/size-baseline.json` (measured only)
- `docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md` — update Execution status table when tasks land

## Suggested Execution Order

```text
R1  Integration gate on sdd/static-uasset-finish (Tasks 5–9 accepted green)
R2  Task 10  Blueprint C++ declaration/migration projection
R3  Task 10A Type-aware projection registry + non-Blueprint projectors
R4  Task 11  Canonical writer + CLI/Agent plumbing
R5  Task 12  Sample quality gates + complete verification
R6  Final checklist + status updates
```

R2 depends on R1. R3 depends on R2 (`render_cpp`). R4 depends on R3 (`ProjectorRegistry` + `bundle`). R5 depends on R4. Do not interleave R2–R5 commits.

---

### Task R1: Accept Tasks 5–9 on the execution branch

**Files:**
- Worktree: `.worktrees/sdd-static-continue` on `sdd/static-uasset-finish`
- Inspect/fix only files already dirty or broken by integration
- Do **not** create projection modules in this task

**Interfaces:**
- Consumes: existing modules listed in the progress snapshot for Tasks 5–9
- Produces: a green focused Tasks 5–9 test suite on the execution branch; `objects[].semantic` projected dicts for Blueprint/Material families; `BlueprintCorrelation.build(...)` available for Task 10

**Current-state notes:**
- Dirty edits already exist on this worktree (`kismet/expressions.py`, `handlers_impl.py`, `parsers/blueprint/control_flow.py`, and several blueprint tests). Finish those edits as their own reviewable commits **before** starting R2.
- Do not re-implement Tasks 5–9 from `dev-0.6.0`. Integration source of truth is this branch.
- `compose/static-uasset-task5-12` @ `92c3a309` is the older unmerged candidate; this branch already merges it and adds property-reader fixes.

- [x] **Step 1: Record baseline**

Run:

```powershell
cd E:/Develop/uasset_read/.worktrees/sdd-static-continue
git status --short
git log --oneline -8
$env:PYTHONPATH='src'; python -m pytest tests/test_handler_registry.py tests/test_blueprint_ir.py tests/test_k2_metadata.py tests/test_blueprint_cfg.py tests/test_blueprint_correlation.py tests/test_material_graph.py tests/test_size_baseline.py -q
```

Expected: either all focused tests pass, or failures are limited to the already-dirty in-progress files. Write down the exact failure list.

- [x] **Step 2: Finish or revert dirty in-progress edits**

For each dirty file from Step 1:

1. If the edit is part of an unfinished Tasks 5–9 fix, complete it with a failing-test-first proof and commit.
2. If the edit is unrelated/stale, restore it with `git restore <path>` only when that file is not required for green tests.

Commit message form:

```powershell
git add <only the files you finished>
git commit -m "fix: finish tasks 5-9 integration residue"
```

- [x] **Step 3: Prove domain acceptance surface for later tasks**

Add or confirm these assertions in the existing Tasks 5–9 tests if they are missing (do not invent new acceptance numbers):

```python
def test_stackobot_blueprint_semantic_is_projected_dict(stackobot_document):
    from tests.fixtures import find_blueprint_object

    obj = find_blueprint_object(stackobot_document)
    semantic = obj.semantic
    assert isinstance(semantic, dict)
    assert semantic["kind"] in {"blueprint", "anim_blueprint"}
    assert semantic["functions"], "functions[] must be projected dicts"
    assert isinstance(semantic["functions"][0], dict)
    assert "expression_count" in semantic["functions"][0]
    assert "control_flow" in semantic


def test_stackobot_material_semantic_has_graph_dict(stackobot_material):
    from tests.fixtures import find_material_graph

    graph = find_material_graph(stackobot_material)
    assert isinstance(graph, dict)
    assert graph.get("expressions") is not None
```

If `tests/fixtures.py` helpers still return dataclasses, rewrite them to the E1 dict contract in this task (parent plan E1.2). That rewrite belongs with Tasks 5–9 acceptance, not with Task 10.

- [x] **Step 4: Run the Tasks 5–9 focused suite**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_handler_registry.py tests/test_blueprint_ir.py tests/test_k2_metadata.py tests/test_blueprint_cfg.py tests/test_blueprint_correlation.py tests/test_material_graph.py tests/test_blueprint_decode.py tests/test_blueprint_graph.py tests/test_size_baseline.py -q
```

Expected: PASS. If `test_size_baseline.py` fails only on measured line growth, update `tests/size-baseline.json` from the failure output and commit that change with the integration commit.

- [x] **Step 5: Commit acceptance and update parent plan status row**

Commit any remaining measured baseline/docs updates.

Edit parent plan `## Execution status (2026-09-21)` so Tasks 5–9 move from `unmerged candidate` to `implemented on sdd/static-uasset-finish` once Step 4 is green. Do **not** mark them complete on `dev-0.6.0` until an orchestrator merge lands them there.

```powershell
git add tests/size-baseline.json docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md
git commit -m "test: accept tasks 5-9 on static-uasset-finish branch"
```

---

### Task R2: Build the Blueprint C++ declaration and migration projection

This is parent-plan Task 10, restated for remaining execution.

**Files:**
- Create: `src/uasset_read/projections/__init__.py`
- Create: `src/uasset_read/projections/cpp_ast.py`
- Create: `src/uasset_read/projections/cpp_render.py`
- Modify: `src/uasset_read/models/analysis.py` only if projected dict lacks declaration/type fields required by the oracle
- Create: `tests/samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json`
- Create: `tests/test_blueprint_cpp.py`

**Interfaces:**
- Consumes: projected `ObjectRecord.semantic` dict from R1 (`kind`, `declaration`, `variable_definitions`, `function_declarations`, `components`, `dispatchers`, `constructors`, `functions[].instructions`, `functions[].cfg`, dual-offset provenance)
- Produces:
  - `build_cpp_ast(semantic: BlueprintSemantic) -> CppClassDecl` (internal typed path)
  - `render_cpp(semantic_dict: dict[str, Any], mode: Literal["declaration", "migration"]) -> CppProjection` (public E1 boundary)
  - `render_cpp_ir(semantic: BlueprintSemantic, mode: ...) -> CppProjection`
  - Reuse in-tree native helpers: `kismet/native_fields.py` (`build_native_function_signature`, `native_field_cpp_type`)

```python
@dataclass(frozen=True)
class CppProjection:
    header_text: str
    source_text: str
    diagnostics: list[Diagnostic]
    translation_stats: dict[str, int]
```

`translation_stats` integer keys are frozen:

- `instructions_seen`
- `translated`
- `represented`
- `untranslated`
- `unavailable`
- `declarations`

Invariant: `instructions_seen == translated + represented + untranslated + unavailable`. Declaration counts are separate. Statuses are exactly `translated | represented | untranslated | unavailable`. No Gate K `cpp_code` / `translation_status` / `structured_rate` fields return.

Declaration-scope reference only (not a runtime dependency): `Engine/Plugins/Editor/BlueprintHeaderView/`. Header View proves declaration coverage, not native body recovery.

- [x] **Step 1: Dump measured UE5.8 declaration facts under `temp/`**

Run a one-time probe after R1 is green:

```powershell
$env:PYTHONPATH='src'; python - <<'PY'
from pathlib import Path
from tests.fixtures import parse_sample
import json

doc = parse_sample("MyProject_UE58_TestBlueprint.uasset", depth="decode")
out = Path("temp/quality-v3")
out.mkdir(parents=True, exist_ok=True)
records = []
for obj in doc.objects:
    sem = obj.semantic or {}
    if not isinstance(sem, dict):
        continue
    records.append({
        "id": obj.id,
        "name": obj.name,
        "class_name": obj.class_name,
        "kind": sem.get("kind"),
        "parent_class": sem.get("parent_class") or (sem.get("declaration") or {}).get("parent_class"),
        "declaration": sem.get("declaration"),
        "variable_definitions": sem.get("variable_definitions"),
        "function_declarations": sem.get("function_declarations"),
        "components": sem.get("components"),
        "dispatchers": sem.get("dispatchers"),
        "constructors": sem.get("constructors"),
    })
path = out / "MyProject_UE58_TestBlueprint.declarations.json"
path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
print(path)
PY
```

Do **not** invent oracle fields. Populate the golden JSON only from this dump (parent class, properties/types, function signatures/parameters/directions, components, dispatchers that actually appear). If a field is absent, leave it out of the oracle until measured.

- [x] **Step 2: Write the failing C++ projection tests**

Create `tests/samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json` from Step 1 with `_provenance` explaining it is a normalized oracle, not a parser snapshot.

```python
# tests/test_blueprint_cpp.py
import json
from pathlib import Path

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
    function = next(item for item in decl.functions if item.name == ORACLE["functions"][0]["name"])
    expected = ORACLE["functions"][0]
    assert function.return_type.name == expected["return_type"]
    assert [(p.name, p.type.name, p.direction) for p in function.params] == [
        (p["name"], p["type"], p["direction"]) for p in expected["parameters"]
    ]


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


def test_render_cpp_public_entry_accepts_projected_dict(stackobot_document):
    from tests.fixtures import find_blueprint_object
    from uasset_read.projections.cpp_render import render_cpp as public_render

    semantic = find_blueprint_object(stackobot_document).semantic
    assert isinstance(semantic, dict)
    result = public_render(semantic, mode="declaration")
    assert result.header_text
```

Add pytest fixtures if missing:

```python
@pytest.fixture
def ue58_semantic(ue58_blueprint_document):
    from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation, project_semantic_blueprint

    # Prefer the already-projected dict path used by tests that need typed IR:
    # unit fixtures may construct typed IR via BlueprintCorrelation helpers.
    from tests.fixtures import find_blueprint_object
    obj = find_blueprint_object(ue58_blueprint_document)
    # Typed IR is produced inside the parser; expose a test-only helper if needed.
    return BlueprintCorrelation().build(ue58_blueprint_document, analysis_context=None)


@pytest.fixture
def stackobot_semantic(stackobot_document):
    from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation

    return BlueprintCorrelation().build(stackobot_document, analysis_context=None)
```

If `BlueprintCorrelation.build(document)` without context is not yet implemented on this branch, implement that standalone test entry in R2 **using only projected dict keys** (parent Task 8 contract). It must not reopen package bytes.

- [x] **Step 3: Run tests and verify the projection is absent**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_cpp.py tests/test_size_baseline.py -q
```

Expected: FAIL with missing `uasset_read.projections.*` or missing `render_cpp`.

- [x] **Step 4: Implement the C++ AST and renderer**

Implement in `projections/cpp_ast.py`:

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
```

Implement in `projections/cpp_render.py`:

1. `_coerce_semantic(semantic_dict: dict) -> BlueprintSemantic` — private dict→IR mapping. The only place that understands projected-dict keys.
2. `build_cpp_ast(semantic: BlueprintSemantic) -> CppClassDecl`
3. `render_cpp_ir(semantic, mode) -> CppProjection`
4. `render_cpp(semantic_dict, mode) -> CppProjection` — public entry; never accepts `PackageDocument`; never reopens bytes.

Renderer rules:

- Declaration mode emits parent class, `UPROPERTY` variables/types, `UFUNCTION` signatures, components, dispatchers, constructors/parent-call metadata, and visibility/metadata when recoverable.
- Migration mode emits static reconstructed control-flow/calls from instruction IR + CFG; every top-level instruction becomes a `CppStmt` with dual-offset provenance (`statement_index`, `serialized_start`, `serialized_end`).
- Unsupported/ambiguous/native-only bodies are `represented` / `untranslated` / `unavailable` with diagnostics; never empty-guessed implementations.
- Unresolved types render as comments like `/* unresolved: TypeName */` or equivalent diagnostic text — never silently `void`.
- Do not concatenate raw bytecode strings into C++ source.

- [x] **Step 5: Run C++ projection tests and commit**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_blueprint_cpp.py tests/test_blueprint_correlation.py tests/test_size_baseline.py -q
```

Expected: PASS.

```powershell
git add src/uasset_read/projections tests/samples/golden/blueprint_header_view tests/test_blueprint_cpp.py tests/size-baseline.json
git commit -m "feat: project blueprint semantics to auditable cpp"
```

Do not add a compiler-backed blocking test. Local clang++ cannot prove Unreal reflected-type correctness (parent plan E3).

---

### Task R3: Add the type-aware projection registry and non-Blueprint projections

This is parent-plan Task 10A, restated for remaining execution.

**Files:**
- Create: `src/uasset_read/projections/records.py`
- Create: `src/uasset_read/projections/registry.py`
- Create: `src/uasset_read/projections/material_builder.py`
- Create: `src/uasset_read/projections/data_exports.py`
- Create: `src/uasset_read/projections/bundle.py`
- Modify: `src/uasset_read/models/analysis.py` only if capability descriptors need shared types
- Create: `tests/test_asset_projections.py`
- Create: `tests/test_single_output.py`

**Interfaces:**

```python
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


class AssetProjector(Protocol):
    asset_kinds: tuple[str, ...]

    def can_project(self, obj: ObjectRecord) -> bool: ...
    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]: ...


class ProjectorRegistry:
    @classmethod
    def default(cls) -> "ProjectorRegistry": ...
    def register(self, projector: AssetProjector, *, priority: int = 0) -> None: ...
    def project_object(self, document: PackageDocument, object_id: str) -> list[ProjectionRecord]: ...
    def project_document(self, document: PackageDocument) -> list[ProjectionRecord]: ...


def build_canonical_document(document: PackageDocument) -> dict[str, Any]: ...
def write_projected_document(
    document: PackageDocument,
    output_path: Path,
    *,
    max_main_bytes: int | None = None,
) -> Path: ...
def minimum_canonical_envelope_bytes(document: PackageDocument) -> int: ...


class OutputBudgetError(ValueError):
    """The requested main-document limit cannot contain the mandatory envelope."""
```

Registry `project_document()` means **all objects in the supplied PackageDocument**. It is not the bounded `uasset_read.projection.project_document` response API.

Initial capability matrix:

| Asset family | Embedded projections | Capability rule |
| --- | --- | --- |
| Blueprint / AnimBlueprint / BlueprintFunctionLibrary / BlueprintInterface | `cpp_declaration`, `cpp_migration` | from R2 `render_cpp`; full trace remains in `objects[].semantic` |
| Material | `material_editor_builder` | `represented` when editor graph exists, else `unavailable` + diagnostic |
| MaterialInstance | `material_instance`, `material_parameters` | parent/overrides resolved or explicit unresolved |
| DataTable | `data_table`, `data_table_csv`, `data_table_json` | row struct + values decoded, else opaque/unavailable |
| CurveTable / RichCurve | `curve_table`, `curve_table_csv`, `curve_table_json` | keys/interp explicit; compressed-only unavailable unless decoded |
| UserDefinedStruct / UserDefinedEnum | `cpp_declaration`, `defaults_json` | fields/enumerators + defaults when reflected data exists |
| Other registered graph assets | `graph`, optional `asset_builder_cpp` | no generic fake C++ body |
| Physical/binary assets | `asset_metadata`, `payload_reference` | metadata/payload references unless an evidenced projector exists |

Dispatch rules:

1. Match semantic `kind` first, then normalized `class_name` family.
2. Highest priority projector wins; equal-priority ambiguity is a hard error.
3. Sort output by `(source_object_id, kind, media_type)`.
4. Do not copy generic object data into a generic `object` projection.
5. Keep C++/CSV/JSON content embedded; no physical path merely because media type differs.
6. `dependencies` come from document relations when resolvable.
7. Recognized-but-missing input → explicit `unavailable` records, not silent absence.

Helper contracts:

```python
def dependency_ids(document: PackageDocument, object_id: str) -> list[str]:
    return sorted({
        relation.to_id
        for relation in document.relations
        if relation.from_id == object_id and relation.to_id != object_id
    })
```

Frozen data shapes:

```json
{
  "kind": "data_table",
  "row_struct": "/Script/Game.MyRow",
  "columns": [{"name": "Score", "type": "int32"}],
  "rows": [{"name": "Row_A", "values": {"Score": 10}}]
}
```

`material_builder.py` may emit editor-only reconstruction C++ referencing `UMaterialEditingLibrary`-style operations when the editor graph is present. It must never claim HLSL/shader equivalence or invent cooked-away expressions.

- [x] **Step 1: Write registry and single-document tests**

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

Add a `document` fixture if missing:

```python
@pytest.fixture
def document(stackobot_document):
    return stackobot_document
```

- [x] **Step 2: Run focused tests and verify absence**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_asset_projections.py tests/test_single_output.py tests/test_material_graph.py tests/test_size_baseline.py -q
```

Expected: import failures for `projections.registry` / `projections.bundle`.

- [x] **Step 3: Implement records, registry, projectors, and bundle**

Blueprint projector wiring:

```python
class BlueprintCppProjector:
    asset_kinds = (
        "blueprint",
        "anim_blueprint",
        "blueprint_function_library",
        "blueprint_interface",
    )

    def can_project(self, obj: ObjectRecord) -> bool:
        return (obj.semantic or {}).get("kind") in self.asset_kinds

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = obj.semantic
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

`_unavailable_blueprint_projections(object_id, reason)` returns two explicit unavailable records (`cpp_declaration`, `cpp_migration`) with structured diagnostics via `make_diagnostic`.

`build_canonical_document(document)` always includes:

- `format_version == "3.0"`
- package envelope
- every object id
- semantic data
- projection records
- capability/diagnostic data
- payload references

It accepts no pagination/selection. `write_projected_document()` serializes that dict to one UTF-8 JSON file. If `max_main_bytes` cannot fit the complete document or falls below `minimum_canonical_envelope_bytes(document)`, raise `OutputBudgetError` **before creating any file**. Measure UTF-8 byte length, not Python character count. Do not implement automatic sidecars in this task.

- [x] **Step 4: Run projection tests and commit**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_asset_projections.py tests/test_single_output.py tests/test_material_graph.py tests/test_blueprint_cpp.py tests/test_size_baseline.py -q
```

Expected: PASS.

```powershell
git add src/uasset_read/projections tests/test_asset_projections.py tests/test_single_output.py tests/size-baseline.json
git commit -m "feat: add embedded type-aware asset projections"
```

---

### Task R4: Replace output and CLI plumbing with projections

This is parent-plan Task 11, restated for remaining execution.

**Files:**
- Modify: `src/uasset_read/projection.py`
- Modify: `src/uasset_read/cli.py`
- Modify: `src/uasset_read/agent_tools.py`
- Modify: `src/uasset_read/package.py`
- Modify: `src/uasset_read/__init__.py`
- Modify: `src/uasset_read/projections/registry.py` / `bundle.py` only for export cleanup
- Create: `tests/test_projection_v3.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Bounded response API: `project_document(document, *, view, object_ids=None, limit=None, offset=None, max_bytes=None) -> dict`
- File API: `build_canonical_document(document) -> dict`, `write_projected_document(...) -> Path`
- C++ API: `project_cpp(document, *, object_id, mode) -> CppProjection` loads `object.semantic` dict and calls `render_cpp(semantic_dict, mode=...)`
- Projection API: `build_projection_records(document, *, object_ids=None, kinds=None) -> list[ProjectionRecord]`

Current-state notes:

- `projection.py` already injects `FORMAT_VERSION = "3.0"` and empty `projections`/`sidecars` lists. This task fills real projection records and wires CLI/Agent.
- CLI batch envelope at `cli.py` (`format: uasset_read.batch`, `format_version: "1.0"`) stays as the multi-file wrapper. Each `results[]` entry must be a complete v3 canonical document.
- When `-o/--output` is a file, call `write_projected_document()`. Reject combining canonical output with `--limit`/`--offset`/object selection (usage error).
- Retired CLI flags stay retired. Do not resurrect Gate K `cpp_code` on Kismet results.
- Agent tools keep the six purposes: `inspect_package`, `list_objects`, `get_object`, `list_dependencies`, `get_diagnostics`, `extract_payload`. Selection/pagination/`max_bytes` apply after semantic projection. Expose embedded projection records through `get_object`. No process-global logging.

- [x] **Step 1: Write projection consistency tests**

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


def test_canonical_file_api_is_not_paginated(stackobot_document, tmp_path):
    from uasset_read.projections.bundle import build_canonical_document, write_projected_document

    full = build_canonical_document(stackobot_document)
    expected_ids = {obj.id for obj in stackobot_document.objects}
    assert expected_ids <= {item["id"] for item in full["objects"]}
    path = write_projected_document(stackobot_document, tmp_path / "full.json")
    assert path.exists()
```

- [x] **Step 2: Run output tests and verify old plumbing fails**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_projection_v3.py tests/test_cli.py tests/test_payload_extraction.py tests/test_size_baseline.py -q
```

Expected: missing projection records, wrong format_version assertions, or CLI still writing non-canonical shape.

- [x] **Step 3: Wire projection layer, package entry, CLI, and Agent**

Implementation checklist:

1. `projection.project_document()` embeds registry projection records after semantic projection; keep pagination/`max_bytes` for query/Agent responses.
2. `package.py` stays thin: source detection → layout → reader → properties → domain registry → analysis → projection.
3. CLI `-o file.json` calls `write_projected_document()`; stdout/query path may keep bounded `project_document()`.
4. Agent tools call the same v3 projection layer.
5. `build_projection_records()` is the only API that creates embedded type-specific content.
6. Document writer is the only API that materializes the canonical file.

- [x] **Step 4: Run CLI/Agent/projection tests and commit**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_projection_v3.py tests/test_cli.py tests/test_payload_extraction.py tests/test_core.py tests/test_size_baseline.py -q
```

Expected: PASS.

```powershell
git add src/uasset_read/projection.py src/uasset_read/cli.py src/uasset_read/agent_tools.py src/uasset_read/package.py src/uasset_read/__init__.py tests/test_projection_v3.py tests/test_cli.py tests/size-baseline.json
git commit -m "refactor: route outputs through package document projections"
```

---

### Task R5: Add sample quality gates and complete verification

This is parent-plan Task 12, restated for remaining execution.

**Files:**
- Create: `tests/test_complete_samples.py`
- Modify: `tests/samples/quality_baseline.json`
- Create: `temp/quality-v3/README.md` (untracked; do not commit)
- Modify: `tests/test_quality_baseline_generator.py`
- Modify: `tests/test_size_baseline.py` only if gate helpers change

**Interfaces:**
- Consumes: complete parser output from R4, sample manifest, type-aware `ProjectorRegistry`
- Produces: repeatable acceptance checks for byte accounting, domain coverage, embedded projections, single-document output, capability/status coverage, and failure truthfulness

Acceptance numbers (from spec + manifest, verified 2026-09-16):

| Gate | Sample | Required proof |
| --- | --- | --- |
| 1 | `StackOBot_BP_Drone.uasset` | 31 exports; 2 graphs; 3 Kismet functions; 85 expressions; CFG blocks/edges; call targets; var reads/writes |
| 2 | `MyProject_UE58_TestBlueprint.uasset` | `K2Node_IfThenElse` present; `EX_JumpIfNot` present; explicit true/false CFG edges |
| 3 | `StackOBot_M_BotBase.uasset` | 42 exports; 39 material expressions; expression properties; links when present |
| 4 | `BP_UnversionedTest.uasset` / `DA_UnversionedTest.uasset` | schema decode or bounded opaque; no position-only field guessing |
| 5 | committed containers | IoStore metadata/classification and truthful Zen unavailability; real Zen package parsing remains deferred until redistributable fixtures exist |
| 6 | C++ projection | declaration AST matches normalized UE5.8 oracle; migration has dual-offset trace for every top-level instruction |
| 7 | type-aware projections | recognized families have specialized embedded projections or explicit `unavailable` |
| 8 | single-document output | one canonical JSON per package; ordinary asset/graph boundaries do not split it |
| 9 | byte accounting | every requested non-empty export scope is tiled by non-empty leaves |
| 10 | suite | full pytest + structure/size/quality baselines |

- [x] **Step 1: Write sample acceptance tests**

```python
# tests/test_complete_samples.py
from tests.fixtures import parse_sample, find_blueprint_object, find_material_graph
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
    graph = find_material_graph(document)
    assert len(graph["expressions"]) == 39


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
    expected = {
        obj.id
        for obj in stackobot_document.objects
        if obj.serial_region and obj.serial_region.size > 0
    }
    scopes = stackobot_document.byte_accounting.scopes
    assert expected
    assert expected <= set(scopes)
    for object_id in expected:
        scope = scopes[object_id]
        assert scope.leaves
        scope.validate_full_coverage()
```

If `MaterialGraphDecoder().decode(...)` is awkward after the E1 dict flip, keep using `find_material_graph(document)["expressions"]`. Do not require a live dataclass in sample-facing tests.

- [x] **Step 2: Run sample tests and record real failures**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_complete_samples.py tests/test_size_baseline.py -q
```

Expected: if gaps remain, failures identify sample/feature gaps, not generic assertion noise. Fix parser/projection gaps in the owning task (R2/R3/R4), not by weakening these gates.

- [x] **Step 3: Generate quality-v3 evidence under `temp/`**

Run the parser for StackOBot Blueprint, UE5.8 Blueprint, StackOBot Material, unversioned samples, and available container fixtures. Store one canonical JSON per sample under `temp/quality-v3/` containing diagnostics, Blueprint semantic trace, Blueprint C++ declaration/migration projections, Material graph/editor-builder projections, available table/curve/struct/enum projections, and capability matrix. Include a short README listing commands and git SHA. Do not stage `temp/`.

- [x] **Step 4: Update only measured baselines**

Update `tests/samples/quality_baseline.json` and `tests/size-baseline.json` from generated evidence. Add gate samples currently missing from the quality baseline. Do not suppress a parser failure by widening a baseline or marking an unavailable feature complete.

- [x] **Step 5: Run all verification commands**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q
$env:PYTHONPATH='src'; python -m pytest tests/test_complete_samples.py tests/test_quality_baseline_generator.py tests/test_size_baseline.py -q
python -m compileall -q src
```

Expected: all tests pass; all baseline gates pass; every discovered Blueprint instruction has a translation status; every sampled recognized asset has a best-fit embedded projection or explicit capability/diagnostic outcome; ordinary samples produce one canonical JSON file each.

- [x] **Step 6: Commit the acceptance gate**

```powershell
git add tests/test_complete_samples.py tests/samples/quality_baseline.json tests/test_quality_baseline_generator.py tests/test_size_baseline.py
git commit -m "test: add complete parser quality gates"
```

Never `git add temp/`.

---

### Task R6: Final checklist and documentation status — complete (execution branch)

**Files:**
- Modify: `docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md`
- Modify: `docs/superpowers/plans/2026-09-21-remaining-static-uasset-v3-projection.md` (this file) — mark tasks done
- Modify: `docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md` implementation marker only after source+tests support the claim
- Do **not** update README feature claims until implementation is on the user-facing branch

- [x] **Step 1: Walk the final review checklist**

Confirm each item against source/tests, not against design text:

1. `PackageDocument` is the only aggregate passed to JSON/CLI/Python/Agent/C++ projections.
2. E1: `objects[].semantic` is dict at the document boundary; typed IR is not required by sample fixtures/CLI.
3. E2: Legacy `PackageArchive` remains the reader owner; no duplicate table-reader stack.
4. No reference project is imported/executed/spawned at runtime.
5. Legacy and Zen remain separate; real Zen payload support stays `unverified` without redistributable fixtures.
6. Tagged and unversioned readers cannot silently substitute for each other.
7. `exec_chains` is a derived direct-edge summary, not runtime simulation.
8. Blueprint functions expose instructions, CFG, calls, variable accesses/definitions, and unresolved records.
9. Kismet `statement_index` is logical CodeOffset; `statement_ordinal` is list order; both logical and physical ranges are preserved.
10. Every correlated call/variable/entrypoint carries `match_method`, bounded `confidence`, and truthful `unresolved`.
11. Material expressions expose nodes and links when present.
12. C++ declaration AST matches the normalized UE5.8 oracle and covers Header View declaration scope.
13. C++ migration output is status-bearing and never claims native-body equivalence.
14. Type-aware registry has one deterministic owner per proven family; unknown families may emit no extra projection.
15. Material output distinguishes graph JSON from editor-builder C++; no HLSL equivalence claim.
16. DataTable/CurveTable use stable CSV/JSON; C++ initializers only when values are decoded.
17. Physical/binary assets use metadata/payload references unless an evidenced projector exists.
18. Every embedded projection has `source_object_id`, media type, content or explicit `unavailable`, completeness, dependencies, and diagnostics.
19. One input package produces one canonical JSON document.
20. `build_canonical_document()`/`write_projected_document()` are separate from paginated `project_document()`.
21. Core writer rejects an impossible size limit before writing; automatic sidecars remain deferred.
22. Cooked-away/encrypted/missing/unknown data are unavailable/opaque with reasons.
23. Full tests, quality baseline, size baseline, and compileall pass.

- [x] **Step 2: Update plan execution status**

In the parent plan, set:

| Tasks | Marker |
| --- | --- |
| 1–4 | implemented (dev-0.6.0 + this branch) |
| 5–9 | implemented on `sdd/static-uasset-finish` after R1 green |
| 10 | implemented after R2 green |
| 10A | implemented after R3 green |
| 11 | implemented after R4 green |
| 12 | implemented after R5 green |

In this remaining plan, check off completed task boxes.

- [x] **Step 3: Commit documentation status updates**

```powershell
git add docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md docs/superpowers/plans/2026-09-21-remaining-static-uasset-v3-projection.md
git commit -m "docs: mark remaining static uasset v3 tasks executed"
```

Do not push or merge to `dev-0.6.0` unless the user explicitly asks. Cross-branch landing is an orchestrator/user action.

---

## Self-Review Checklist (plan author)

1. **Spec coverage:** Acceptance gates 1–9 from the design spec map to R5 gates 1–10; C++ declaration/migration statuses map to R2; single-file contract maps to R3/R4; capability/error contract maps to R3/R5. Zen package full decoding remains explicitly deferred, matching the 2026-09-17 scope revision.
2. **Placeholder scan:** No TBD/TODO steps. Each remaining task includes concrete tests, APIs, Run commands, and commit boundaries. Oracle fields must be measured, not invented — that is an evidence rule, not a placeholder.
3. **Type consistency:** Public C++ entry is `render_cpp(semantic_dict, mode)`. Registry method `project_document(document)` is the full-document registry API; bounded response API remains `uasset_read.projection.project_document`. Projection statuses are the frozen four-value set. `format_version` is always `"3.0"` at the projection envelope.

## Evidence Appendix (unchanged from parent plan)

Use these UE relative paths instead of re-guessing layouts:

1. Legacy summary: `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h`
2. Import/export resources: `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`
3. Tagged property tag: `Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h`
4. Unversioned fragments: `Engine/Source/Runtime/CoreUObject/Private/Serialization/UnversionedPropertySerialization.cpp`
5. Zen package summary/bundles: `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`
6. Zen header view: `Engine/Source/Runtime/CoreUObject/Internal/Serialization/ZenPackageHeader.h`
7. Package trailer: `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageTrailer.h`
8. Kismet opcodes: `Engine/Source/Runtime/CoreUObject/Public/UObject/Script.h`
9. Kismet serialize: `Engine/Source/Runtime/CoreUObject/Public/UObject/ScriptSerialization.inl`
10. Blueprint Header View (declaration-scope reference only): `Engine/Plugins/Editor/BlueprintHeaderView/`
11. Blueprint compiler VM backend: `Engine/Source/Editor/KismetCompiler/Public/KismetCompiledFunctionContext.h`, `Engine/Source/Editor/KismetCompiler/Private/KismetCompilerBackend.h`, `Engine/Source/Editor/KismetCompiler/Private/KismetCompilerVMBackend.cpp`
