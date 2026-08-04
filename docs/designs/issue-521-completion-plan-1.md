# #521 Epic Completion — First Implementation Plan (A1–A3, B0a/B0b, B1-pre)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the immediately-actionable slices of `docs/designs/issue-521-completion-roadmap-design.md` — Track A (acceptance rewrite, execution-flow disposition, coverage inventory) and Track B's gate + intake (pin existence proof, UE source audit, #515 candidate-intake fix) — so that Epic #521's remaining work is either done, evidence-gated, or formally handed to #525/#515 child issues.

**Architecture:** Track A is documentation + one small handler migration (`NiagaraScriptVariable` routed to `OPAQUE_CLASS_PAYLOAD` with a dedicated handler mirroring the Graph/Script precedent). Track B is diagnostic-first: a read-only native-tail inspection script (B0a) feeds a version-pinned UE source audit (B0b) whose recorded gate decision controls the later B1/B2 plans; B1-pre fixes the #515 scan blind spot and intakes the Niagara structs as candidates with per-struct issues.

**Tech Stack:** Python 3.10 stdlib only (zero runtime dependencies); `pytest` (CI-installed, tests only); `gh` CLI for issue operations; UE source checkout at `E:/Develop/lib/UnrealEngine` for read-only audits.

**Slice → Task map:** A1 → Task 1 · A2 → Task 2 · A3 → Tasks 3–5 · B0a → Task 6 · B0b → Task 7 · B1-pre → Tasks 8–10.

## Global Constraints

These apply to every task (copied verbatim in intent from the project constraints and the roadmap design):

- Zero runtime dependencies; no `pip install`; run via `src/` imports. Parser changes are read-only (parse only, never write assets).
- All new tests go to `tests/temp/`; root `tests/` files are NOT modified; `tests/samples/` receives no new files in this plan (holds only `.uasset` samples).
- Evidence discipline: every binary-format claim must carry a version-pinned UE C++ source reference; never guess layouts; unproven bytes stay opaque with recorded offset/size.
- Status model: export-level `parse_status` must be an `ExportParseStatus` enum value; `partial_metadata` only for handler-projected exports; `opaque` never promoted without evidence.
- All code comments, error messages, and documentation in English. Exception: edits to the pre-existing Chinese-language docs (`issue-521-niagara-export-parsing-plan.md`, `issue-515-opaque-structproperty-roadmap.md`) follow that document's language for in-document consistency.
- Commit format: `<type>: <summary> (#issue)` on branch `dev-0.5.5`. Issue tags used here: `(#521)` for Tasks 1–7, `(#515)` for Tasks 8–10.
- Fixture: `tests/samples/NM_BPSystemEvent.uasset`, SHA-256 `B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF` (assert in every fixture-based test).
- UE source checkout: `E:/Develop/lib/UnrealEngine` at commit `7deeb413d3dc1fc034f48d1aacc0861301829d32` (tag `5.8.0-release`). Audits quote `file:line` against exactly this commit. If the fixture's package version differs from 5.8, audited code paths must additionally be checked for version gating and any delta recorded.
- Baseline guards: the existing 59 Niagara tests stay green; root suite stays at **125 passed + 1 known failure** (`tests/test_issue_518_uasset_reader_js_compat.py::test_normal_json_root_keys_are_unchanged`, owned by the test-infrastructure issue created in Task 1); export counts never regress.
- Canonical commands (run from repo root `E:/Develop/uasset_read`):
  - Niagara suite: `python -m pytest tests/temp/test_issue_521_niagara_evidence.py tests/temp/test_issue_521_niagara_graph_handler.py tests/temp/test_issue_521_niagara_node_handler.py tests/temp/test_issue_521_niagara_routing.py tests/temp/test_issue_521_niagara_script_handler.py -q`
  - Root suite: `python -m pytest tests/ --ignore=tests/temp -q`

---

### Task 1: A1 — Test-infrastructure issue, Epic body rewrite, plan-doc sync

**Files:**
- Modify: `docs/designs/issue-521-niagara-export-parsing-plan.md`
- Issues: create one new issue; edit #521 body

**Interfaces:**
- Consumes: `docs/designs/issue-521-completion-roadmap-design.md` (terminal-state table, verified baseline)
- Produces: the new test-infrastructure issue number (referenced by Tasks 6/7 docs and by the Epic body); the rewritten Epic body that later tasks must not contradict

This task is documentation/issue work only — no code changes.

- [ ] **Step 1: Create the independent test-infrastructure issue**

Run:

```bash
gh issue create --title "Test infrastructure: promote tests/temp suites and sync constraints.md" --body @- <<'EOF'
Split out of Epic #521 (roadmap slice A1, `docs/designs/issue-521-completion-roadmap-design.md`).
Tracks test-placement and constraint-document drift that #521 execution surfaced but must not fix inline.

## Items

1. **tests/temp promotion** — CI runs `pytest tests/` and does not collect `tests/temp/`
   (`pytest.ini` `norecursedirs`). The #521 Niagara acceptance suite (59+ tests) and other
   focused suites live there, so "full suite green" does not cover them. Define promotion
   criteria and move stable suites (benchmark-test changes require owner approval per
   constraints.md).
2. **constraints.md desync: root test count** — constraints.md says root `tests/` holds
   exactly 6 test files; the actual count is 18. Reconcile the rule or the files.
3. **constraints.md desync: tests/samples content** — constraints.md says `tests/samples/`
   stores only `.uasset` sample files; the directory also holds `ORIGIN-*.md` provenance
   files and `.umap` samples. Reconcile.
4. **#518-related failure disposition** — issue #518 is closed (2026-08-01) but
   `tests/test_issue_518_uasset_reader_js_compat.py::test_normal_json_root_keys_are_unchanged`
   still fails. Needs an owner: fix, redefine, or remove.

## Out of scope

- Any #521 Niagara parsing work.
- Benchmark test changes without explicit owner approval.

Parent: #521
EOF
```

Record the created issue number as `TEST_ISSUE` (e.g. `#530`).

- [ ] **Step 2: Rewrite the #521 Epic body**

Replace the current body (fetch with `gh issue view 521 --json body -q .body` for the record) with the following. Substitute the real `TEST_ISSUE` number. Save to a temp file and apply with `gh issue edit 521 --body-file temp/issue-521-body.md` (temp files go in `temp/`):

```markdown
# Epic: Niagara export parsing — completion roadmap

> Status: OPEN — governed by `docs/designs/issue-521-completion-roadmap-design.md` (2026-08-05).
> Fixture: `tests/samples/NM_BPSystemEvent.uasset` (SHA-256 pinned in tests).

## Terminal-state vocabulary

Every original requirement ends in exactly one of:
1. **Achieved** — met with evidence.
2. **Disproven-closed** — shown unreachable, evidence recorded.
3. **Explicitly out of scope** — removed with recorded rationale.

## Original requirement → terminal state

| Original requirement | Disposition | Owner slice |
|---|---|---|
| Node connections — node_exports level | Achieved: 25 NiagaraNode* refs, PackageIndex-verified (value = export_index + 1) | done (plan Phase 2) |
| Node connections — pin level | Pending B0 gate; disproven-closed if UE source shows pins unserialized | Track B (B0a/B0b → #525) |
| Execution flow | Explicitly out of scope — insufficient evidence today; no assertion made | A2 |
| Parameter definitions and values | Achieved path via NiagaraVariable decoding (independent of the pin gate) | Track B (B1 → #525) |
| Script references | Disproven-closed for the tagged-property object-reference ceiling (2026-08-04 audit); opaque containers (`CachedUsageInfo`, `VariableToScriptVariable`) remain open via #515 | done + #515 |
| Graph structure | Achieved path: node composition projected; pin-level edges subject to the B0 gate | done + #525 |
| Niagara type coverage | Coverage contract: every Niagara class in the fixture lands on an evidence-based terminal state | A3 |
| Lyra-wide statistics (39.3% / 1,638 exports) | Explicitly out of scope — not reproducible from repository fixtures (owner, 2026-08-01); acceptance redefined per-fixture | A1 |

## Verified baseline (2026-08-05 live parse)

43 exports = 39 Niagara-class (`NiagaraGraph`×1, `NiagaraScript`×1, 25 `NiagaraNode*`
over 9 classes, `NiagaraScriptVariable`×11, `NiagaraScriptSource`×1 skipped) +
3 `EdGraphNode_Comment` + 1 `MetaData`. No pin-class exports exist in the fixture.
Niagara focused suite: 59+ tests green (run manually from `tests/temp/` until the
test-infrastructure issue below lands).

## Linked work

- Roadmap design: `docs/designs/issue-521-completion-roadmap-design.md`
- Field contracts: `docs/designs/issue-521-niagara-field-contracts.md`
- #525 — node parameters / pin_references (closed by Track B)
- #515 — opaque StructProperty (Niagara struct intake via B1-pre)
- TEST_ISSUE — test promotion + constraints.md sync + #518-failure disposition

## Close-out

Close only when the convergence gate in the roadmap design passes; the closing comment
maps each original requirement to its final disposition.
```

- [ ] **Step 3: Fix the stale baseline in the plan doc**

In `docs/designs/issue-521-niagara-export-parsing-plan.md`, replace the bullet

```
- 当前 tolerant 解析结果为 `partial`：目标夹具有 26 个跳过的 Niagara 节点/相关导出；`NiagaraGraph` 与 `NiagaraScript` 已进入 `opaque` 路径，分别保留 5 个和 4 个 tagged 属性。
```

with

```
- 当前 tolerant 解析结果为 `partial`：目标夹具仅剩 1 个跳过的 Niagara 导出（`NiagaraScriptSource`）；`NiagaraGraph`、`NiagaraScript`、9 个 `NiagaraNode*` 节点类与 `NiagaraScriptVariable` 均以 `partial_metadata` 投影 tagged 属性。最新实测基线见 `issue-521-completion-roadmap-design.md` 的 Verified Baseline。
```

(Only the count 26 → 1 is a numeric correction; do NOT touch the figure 28 elsewhere in this doc — it is the audit-verified `Nodes` reference count.)

- [ ] **Step 4: Update the status line with the roadmap link**

In the same file, replace the status header line content

```
> 状态：partial-metadata 最小切片已完成（2026-08-04 契约缺口审计后修订）；完整 Niagara 解析未完成
```

with

```
> 状态：partial-metadata 最小切片已完成（2026-08-04 契约缺口审计后修订）；Epic 收尾由 `issue-521-completion-roadmap-design.md`（2026-08-05）接管
```

- [ ] **Step 5: Fix the stale full-suite figure in Phase 5**

In the Phase 5 section, replace

```
118/119 完整测试集通过（#518 预先存在失败，与 Niagara 无关）
```

with

```
125/126 完整测试集通过（截至 2026-08-05；唯一失败为 #518 相关测试，见测试基础设施 Issue）
```

- [ ] **Step 6: Add the Lyra-statistics disposition row**

In the `## 明确不在范围内` table, after the `VM bytecode / HLSL` row, add:

```
| Lyra 全量统计（39.3% / 1,638） | 所有者 2026-08-01 确认无法从仓库夹具复现；验收已改为逐夹具定义 |
```

- [ ] **Step 7: Append the roadmap pointer section**

Append at the end of the same file:

```markdown
## 收尾路线图（2026-08-05）

Epic 收尾路线见 `issue-521-completion-roadmap-design.md`：Track A（A1 验收标准重写、
A2 execution flow 落定、A3 覆盖清单）与 Track B（B0a/B0b 引脚证据门、B1-pre #515
候选收录、B1 结构解码、B2 #525 投影）。首批实施计划见
`issue-521-completion-plan-1.md`（A1–A3、B0a/B0b、B1-pre）。
```

- [ ] **Step 8: Consistency check**

Read the three documents (rewritten Epic body, plan doc, roadmap design). Verify every original requirement from the old Epic body (node connections, execution flow, parameters, script references, graph structure, Lyra stats) appears exactly once with exactly one terminal state, and that the test-infrastructure issue number is referenced in the Epic body.

- [ ] **Step 9: Commit**

```bash
git add docs/designs/issue-521-niagara-export-parsing-plan.md
git commit -m "docs: sync #521 plan doc with completion roadmap (#521)"
```

(Issue operations leave no repo changes; they are recorded on GitHub.)

---

### Task 2: A2 — Execution-flow disposition record

**Files:**
- Modify: `docs/designs/issue-521-niagara-field-contracts.md`
- Read-only audit: `E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source/NiagaraEditor/`

**Interfaces:**
- Consumes: UE checkout commit `7deeb413d3dc1fc034f48d1aacc0861301829d32`
- Produces: the "Execution flow" section that the convergence gate (roadmap condition 6) requires; wording quoted by Task 1's Epic body ("no assertion made")

- [ ] **Step 1: Verify the checkout is at the pinned commit**

Run:

```bash
git -C E:/Develop/lib/UnrealEngine rev-parse HEAD
```

Expected: `7deeb413d3dc1fc034f48d1aacc0861301829d32`. If different, record the actual HEAD in the section instead and note the deviation — do not silently cite the pinned commit.

- [ ] **Step 2: Audit attempt for exec-pin evidence**

Run (paths relative to the checkout):

```bash
grep -n -i "exec" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source/NiagaraEditor/Public/EdGraphSchema_Niagara.h"
grep -rn -i "execpin\|exec pin\|bIsExec\|Category=\"Exec\"" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source/NiagaraEditor" --include=*.h --include=*.cpp | head -30
grep -rn "CreateDefaultNodes" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source/NiagaraEditor/Private/EdGraphSchema_Niagara.cpp"
```

Record what the hits show: does any Niagara schema/node code create or reference execution pins? Save the decisive `file:line` hits (if any).

- [ ] **Step 3: Write the section**

In `docs/designs/issue-521-niagara-field-contracts.md`, insert the following section between the `NiagaraNode* Contract` section and the `Notes` section. Use Variant B unless Step 2 produced a decisive version-fixed citation, in which case use Variant A and fill the citation.

Variant A (citation found):

```markdown
## Execution Flow Disposition (A2)

**Terminal state:** explicitly out of scope of Epic #521.

**Source reference:** `<file>:<lines>` at checkout commit `7deeb413d3dc1fc034f48d1aacc0861301829d32`
(`5.8.0-release`) shows <what the citation proves about exec pins / execution order>.

**Disposition rationale:** Based on the citation above, execution-flow reconstruction is
not part of this Epic's acceptance. No execution order is projected or inferred.

**Re-open condition:** If version-fixed UE source evidence shows serialized
execution-order semantics beyond what is cited here, open a new issue referencing
this section.
```

Variant B (no decisive citation — the expected outcome):

```markdown
## Execution Flow Disposition (A2)

**Terminal state:** explicitly out of scope of Epic #521.

**Rationale (evidence discipline):** Insufficient evidence today; no assertion is made
about whether Niagara graphs carry an executable control flow. The 2026-08-04 audit
found no fixture-visible exec-pin data, and the project attribution rule forbids
asserting graph semantics — including "pure dataflow" — without a version-fixed UE
source reference. A targeted audit of `EdGraphSchema_Niagara` at checkout commit
`7deeb413d3dc1fc034f48d1aacc0861301829d32` (5.8.0-release) on 2026-08-XX produced no
decisive exec-pin evidence <adjust this sentence to the actual audit result>.

**What this means:** Execution flow is neither projected nor inferred by this parser.
`node_exports` order is document order, not execution order.

**Re-open condition:** If version-fixed UE source evidence demonstrates that Niagara
graphs serialize execution-order semantics (e.g. exec pins in `UEdGraphSchema_Niagara`
or traversal-order serialization in `UNiagaraGraph`), open a new issue referencing
this section.
```

- [ ] **Step 4: Verify section acceptance criteria**

Check: section exists; every sentence asserting a fact about Niagara either carries a `file:line` citation from Step 2 or is explicitly framed as "no assertion made"; re-open condition present.

- [ ] **Step 5: Commit**

```bash
git add docs/designs/issue-521-niagara-field-contracts.md
git commit -m "docs: record execution-flow disposition for #521 (#521)"
```

---

### Task 3: A3 (red) — Coverage audit and failing tests

**Files:**
- Create: `tests/temp/test_issue_521_niagara_coverage.py`
- Modify: `tests/temp/test_issue_521_niagara_routing.py`
- Read-only audit: UE checkout (Niagara plugin source)

**Interfaces:**
- Consumes: fixture + SHA-256; existing routing-test conventions
- Produces: failing tests that define A3's acceptance (Task 4 makes them pass); audit notes consumed by Task 5's coverage table

- [ ] **Step 1: Source audit of the two uncovered classes**

Run:

```bash
grep -rn "class .*UNiagaraScriptVariable" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source" --include=*.h
grep -rn "class .*UNiagaraScriptSource" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source" --include=*.h
```

Open the two headers found; record (a) the serialized UPROPERTY list of `UNiagaraScriptVariable` and cross-check it against the fixture probe below, (b) the role of `UNiagaraScriptSource`. Working note for Task 5: header paths + line numbers.

Fixture probe (already-verified property list for reference):

```bash
python -c "import sys, json; sys.path.insert(0, 'src'); from uasset_read import parse_single; d=json.loads(parse_single('tests/samples/NM_BPSystemEvent.uasset', format='json', tolerant=True, log_enabled=False)); [print(e['object_name'], [(p['name'], p['type']) for p in e.get('properties', [])]) for e in d['exports'] if e.get('object_class')=='NiagaraScriptVariable']"
```

Expected per export: `DefaultMode` (EnumProperty), `Variable` (StructProperty NiagaraVariable), `Metadata` (StructProperty NiagaraVariableMetaData), `DefaultValueVariant` (StructProperty NiagaraVariant), `ChangeId` (StructProperty Guid).

- [ ] **Step 2: Write the failing coverage test**

Create `tests/temp/test_issue_521_niagara_coverage.py`:

```python
"""Tests for #521 A3: Niagara class coverage inventory.

Every Niagara class in the fixture must land on an explicit terminal state:
field-level parse (partial_metadata) or evidence-backed skip (skipped).
No Niagara export may carry a None/absent parse_status.

Coverage table: docs/designs/issue-521-niagara-field-contracts.md,
section "Niagara Coverage Contract".
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from uasset_read import parse_single

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"
SOURCE_FIXTURE_SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"

EXPECTED_NIAGARA_CLASS_COUNTS = {
    "NiagaraGraph": 1,
    "NiagaraScript": 1,
    "NiagaraNodeFunctionCall": 1,
    "NiagaraNodeInput": 1,
    "NiagaraNodeOp": 5,
    "NiagaraNodeOutput": 1,
    "NiagaraNodeParameterMapGet": 5,
    "NiagaraNodeParameterMapSet": 5,
    "NiagaraNodeReroute": 5,
    "NiagaraNodeSelect": 1,
    "NiagaraNodeStaticSwitch": 1,
    "NiagaraScriptVariable": 11,
    "NiagaraScriptSource": 1,
}


def _load() -> dict:
    sha256 = hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper()
    assert sha256 == SOURCE_FIXTURE_SHA256, f"Fixture SHA-256 mismatch: {sha256}"
    return json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))


def test_niagara_class_enumeration_matches_coverage_table():
    """Live enumeration confirms the coverage table's class inventory."""
    payload = _load()
    counts = Counter(
        e["object_class"] for e in payload["exports"]
        if str(e.get("object_class", "")).startswith("Niagara")
    )
    assert dict(counts) == EXPECTED_NIAGARA_CLASS_COUNTS


def test_every_niagara_export_has_explicit_parse_status():
    """No Niagara export may carry a None/absent parse_status (status model)."""
    payload = _load()
    offenders = [
        (e.get("object_name"), e.get("object_class"), e.get("parse_status"))
        for e in payload["exports"]
        if str(e.get("object_class", "")).startswith("Niagara")
        and e.get("parse_status") not in ("partial_metadata", "skipped")
    ]
    assert offenders == [], f"Niagara exports without terminal status: {offenders}"


def test_niagara_script_variable_projects_tagged_metadata():
    """NiagaraScriptVariable exports project verified tagged properties."""
    payload = _load()
    variables = [
        e for e in payload["exports"]
        if e.get("object_class") == "NiagaraScriptVariable"
    ]
    assert len(variables) == 11
    for e in variables:
        assert e["parse_status"] == "partial_metadata", e["object_name"]
        atd = e.get("asset_type_data", {})
        tagged = atd.get("tagged_properties", {})
        assert tagged["Variable"]["struct_type"] == "NiagaraVariable"
        assert tagged["Metadata"]["struct_type"] == "NiagaraVariableMetaData"
        assert tagged["DefaultValueVariant"]["struct_type"] == "NiagaraVariant"
        assert atd["native_tail"]["status"] == "opaque"


def test_niagara_script_source_stays_skipped():
    """NiagaraScriptSource keeps its evidence-backed skip state."""
    payload = _load()
    sources = [
        e for e in payload["exports"]
        if e.get("object_class") == "NiagaraScriptSource"
    ]
    assert len(sources) == 1
    assert sources[0]["parse_status"] == "skipped"
```

- [ ] **Step 3: Add the routing test**

Append to `tests/temp/test_issue_521_niagara_routing.py`:

```python
def test_niagara_script_variable_is_opaque() -> None:
    """NiagaraScriptVariable migrated to _OPAQUE_CLASSES (#521 A3)."""
    assert get_serialization_strategy("NiagaraScriptVariable") == SerializationStrategy.OPAQUE_CLASS_PAYLOAD
```

- [ ] **Step 4: Run to verify failure**

Run:

```bash
python -m pytest tests/temp/test_issue_521_niagara_coverage.py tests/temp/test_issue_521_niagara_routing.py -v
```

Expected: the routing test FAILS (currently `TAGGED_PROPERTIES_ONLY` default), `test_every_niagara_export_has_explicit_parse_status` FAILS listing the 11 `NiagaraScriptVariable` exports with `parse_status=None`, `test_niagara_script_variable_projects_tagged_metadata` FAILS (no `asset_type_data`). The enumeration and ScriptSource tests PASS.

- [ ] **Step 5: Commit the red tests**

```bash
git add tests/temp/test_issue_521_niagara_coverage.py tests/temp/test_issue_521_niagara_routing.py
git commit -m "test: add #521 A3 coverage inventory tests (red) (#521)"
```

---

### Task 4: A3 (green) — NiagaraScriptVariable routing and handler

**Files:**
- Modify: `src/uasset_read/parsers/class_serialization_strategy.py` (add to `_OPAQUE_CLASSES`)
- Create: `src/uasset_read/parsers/asset_types/niagara_script_variable.py`
- Modify: `src/uasset_read/parsers/asset_types/__init__.py` (import, `__all__`, registration)

**Interfaces:**
- Consumes: Task 3's red tests; `ClassHandler`/`HandlerResult`/`FallbackPolicy` from `class_registry.py`; `build_properties_dict` from `property_extractor.py`; `validate_parse_status` from `models/validators.py`
- Produces: `NiagaraScriptVariableHandler` — later B1 work decodes the inner structs this handler currently leaves opaque; Task 5 documents the resulting terminal state

- [ ] **Step 1: Route the class to OPAQUE_CLASS_PAYLOAD**

In `src/uasset_read/parsers/class_serialization_strategy.py`, in the `_OPAQUE_CLASSES` frozenset, after the `"NiagaraNodeStaticSwitch",` entry add:

```python
    # #521 A3: coverage inventory — explicit partial_metadata status
    "NiagaraScriptVariable",
```

- [ ] **Step 2: Create the handler**

Create `src/uasset_read/parsers/asset_types/niagara_script_variable.py`:

```python
"""NiagaraScriptVariable asset type handler

Projects verified tagged properties of UNiagaraScriptVariable exports and
captures the native tail. Mirrors the NiagaraGraph/NiagaraScript handler
precedent (OPAQUE_CLASS_PAYLOAD routing + handler projection).

Verified tagged properties (fixture NM_BPSystemEvent.uasset, all 11 exports):
- DefaultMode: EnumProperty
- Variable: StructProperty (NiagaraVariable) — decoded by B1/#515, opaque here
- Metadata: StructProperty (NiagaraVariableMetaData) — B1/#515
- DefaultValueVariant: StructProperty (NiagaraVariant) — B1/#515
- ChangeId: StructProperty (Guid)
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

from uasset_read.parsers.asset_types.property_extractor import build_properties_dict
from uasset_read.parsers.class_registry import ClassHandler, FallbackPolicy, HandlerResult
from uasset_read.models.validators import validate_parse_status

logger = logging.getLogger(__name__)

_PROJECTED_PROPERTIES = (
    "DefaultMode", "Variable", "Metadata", "DefaultValueVariant", "ChangeId",
)


class NiagaraScriptVariableHandler(ClassHandler):
    """NiagaraScriptVariable handler — projects tagged properties."""

    def can_handle(self, class_name: str) -> bool:
        return class_name == "NiagaraScriptVariable"

    @property
    def handler_name(self) -> str:
        return "NiagaraScriptVariableHandler"

    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.GENERIC_UOBJECT

    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        try:
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return HandlerResult(
                    success=False,
                    error_message="No properties found",
                    fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
                )

            properties = build_properties_dict(properties_list)

            tagged_properties: dict[str, Any] = {}
            for prop_name in _PROJECTED_PROPERTIES:
                if prop_name in properties:
                    tagged_properties[prop_name] = properties[prop_name]

            # Calculate native tail offset/size
            tail_offset = archive.tell()
            serial_end = export.serial_offset + export.serial_size
            tail_size = max(0, serial_end - tail_offset)

            data: dict[str, Any] = {
                "asset_type": "NiagaraScriptVariable",
                "parse_status": validate_parse_status("partial_metadata"),
                "variable_name": str(export.object_name),
                "tagged_properties": tagged_properties,
                "native_tail": {
                    "offset": tail_offset,
                    "size": tail_size,
                    "status": "opaque",
                },
            }

            return HandlerResult(
                success=True,
                data=data,
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("NiagaraScriptVariable parse error: %s", e)
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
```

- [ ] **Step 3: Register the handler**

In `src/uasset_read/parsers/asset_types/__init__.py`:

1. After `from uasset_read.parsers.asset_types.niagara_node import NiagaraNodeHandler` add:

```python
from uasset_read.parsers.asset_types.niagara_script_variable import NiagaraScriptVariableHandler
```

2. In `__all__`, after `"NiagaraNodeHandler",` add `"NiagaraScriptVariableHandler",`.

3. In `register_asset_type_handlers()`, in the `handlers` list after `NiagaraNodeHandler(),` add:

```python
        NiagaraScriptVariableHandler(),
```

- [ ] **Step 4: Run the A3 tests to verify they pass**

```bash
python -m pytest tests/temp/test_issue_521_niagara_coverage.py tests/temp/test_issue_521_niagara_routing.py -v
```

Expected: all PASS.

- [ ] **Step 5: Run the baseline guards**

```bash
python -m pytest tests/temp/test_issue_521_niagara_evidence.py tests/temp/test_issue_521_niagara_graph_handler.py tests/temp/test_issue_521_niagara_node_handler.py tests/temp/test_issue_521_niagara_routing.py tests/temp/test_issue_521_niagara_script_handler.py -q
python -m pytest tests/ --ignore=tests/temp -q
```

Expected: the original 59 Niagara tests green; root suite 125 passed + the 1 known #518-related failure.

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/parsers/class_serialization_strategy.py src/uasset_read/parsers/asset_types/niagara_script_variable.py src/uasset_read/parsers/asset_types/__init__.py
git commit -m "feat: project NiagaraScriptVariable tagged metadata (#521)"
```

---

### Task 5: A3 docs — Coverage contract table and ScriptSource skip evidence

**Files:**
- Modify: `docs/designs/issue-521-niagara-field-contracts.md`

**Interfaces:**
- Consumes: Task 3's audit notes (header paths/lines for `UNiagaraScriptVariable`, `UNiagaraScriptSource`), Task 4's implemented state
- Produces: the coverage contract table required by convergence gate condition 3 ("no Niagara class undecided")

- [ ] **Step 1: Confirm the live enumeration**

```bash
python -m pytest tests/temp/test_issue_521_niagara_coverage.py -v
```

Expected: PASS (the enumeration test pins the table's counts).

- [ ] **Step 2: Complete the NiagaraScriptSource audit**

Using the header located in Task 3 Step 1, record: class purpose (compiled script source holder for `UNiagaraScript`), and the rationale that its payload is compiled bytecode — decoding VM bytecode/HLSL is out of scope per the roadmap's "Explicitly Out of Scope". Note the header path and line numbers.

- [ ] **Step 3: Add the coverage contract section**

In `docs/designs/issue-521-niagara-field-contracts.md`, insert after the Task 2 "Execution flow" section (before `Notes`), filling the two `<header>:<lines>` placeholders from the Task 3/Step 2 audits:

```markdown
## Niagara Coverage Contract (A3)

Every Niagara class present in the fixture lands on an evidence-based terminal
state. Live enumeration is pinned by `tests/temp/test_issue_521_niagara_coverage.py`;
uncovered classes are exactly two and both are settled below.

| Class | Count | Terminal state | parse_status | Evidence |
|---|---|---|---|---|
| NiagaraGraph | 1 | field-level parse | partial_metadata | NiagaraGraphHandler; §NiagaraGraph above |
| NiagaraScript | 1 | field-level parse | partial_metadata | NiagaraScriptHandler; §NiagaraScript above |
| NiagaraNodeFunctionCall / Input / Op / Output / ParameterMapGet / ParameterMapSet / Reroute / Select / StaticSwitch | 25 | field-level parse | partial_metadata | NiagaraNodeHandler; §NiagaraNode* above |
| NiagaraScriptVariable | 11 | field-level parse | partial_metadata | NiagaraScriptVariableHandler; tagged properties verified against `UNiagaraScriptVariable` UPROPERTYs (`<header>:<lines>`, checkout `7deeb413d3dc1fc034f48d1aacc0861301829d32`) and fixture probe |
| NiagaraScriptSource | 1 | evidence-backed skip | skipped | `UNiagaraScriptSource` (`<header>:<lines>`) holds compiled script source; bytecode decoding is out of scope (roadmap §Explicitly Out of Scope) |

The inner opaque structs of `NiagaraScriptVariable` (`NiagaraVariable`,
`NiagaraVariableMetaData`, `NiagaraVariant`) and the `Outputs`/`OutputVars`
element structs are owned by the B1/#515 path and are not decoded here.
```

- [ ] **Step 4: Verify acceptance**

Check: every Niagara export class in the fixture appears in the table with exactly one terminal state; the two previously-uncovered classes have explicit `parse_status` values; inner structs are explicitly assigned to B1/#515. Also discharge the A3 "issues for classes qualifying for parsing" deliverable: the only qualifying class (`NiagaraScriptVariable`) was parsed directly by this plan (Task 4), and `NiagaraScriptSource` is an evidence-backed skip — therefore no independent issues are required; note this in the commit message body if asked, no issue creation happens.

- [ ] **Step 5: Commit**

```bash
git add docs/designs/issue-521-niagara-field-contracts.md
git commit -m "docs: add Niagara coverage contract table (#521)"
```

---

### Task 6: B0a — Fixture-level pin existence proof (diagnostic)

**Files:**
- Create: `tests/temp/inspect_521_node_tails.py`
- Create: `docs/designs/issue-521-b0-pin-existence-evidence.md`
- Scratch output: `temp/b0a_report.txt`

**Interfaces:**
- Consumes: `native_tail` offset/size recorded by all 11 migrated handlers (verified: e.g. NiagaraNodeFunctionCall tail ≈ 458 bytes)
- Produces: the evidence document that Task 7's gate decision consumes; the `Outputs`/`OutputVars` element-type identification that Task 9's candidate intake consumes

This task MUST NOT change parse output: it adds a read-only diagnostic script and documentation only.

- [ ] **Step 1: Write the inspection script**

Create `tests/temp/inspect_521_node_tails.py`:

```python
"""Diagnostic for #521 B0a: inspect native tails of Niagara exports.

Read-only: parses the fixture, then hex-inspects the native-tail byte ranges
already recorded by the handlers. Prints a report to stdout. Does NOT modify
parse behavior or source code.

Usage: python tests/temp/inspect_521_node_tails.py > temp/b0a_report.txt
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from uasset_read import parse_single

SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"
EXPECTED_SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"


def _hexdump(data: bytes, limit: int = 64) -> str:
    rows = []
    for off in range(0, min(len(data), limit), 16):
        chunk = data[off:off + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        rows.append(f"  {off:08x}  {hex_part:<47}  {ascii_part}")
    return "\n".join(rows)


def main() -> None:
    sha = hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper()
    assert sha == EXPECTED_SHA256, f"fixture mismatch: {sha}"
    raw = SAMPLE.read_bytes()

    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    print("=== B0a native-tail inventory ===")
    for exp in payload["exports"]:
        cls = exp.get("object_class", "")
        if not cls.startswith("Niagara"):
            continue
        atd = exp.get("asset_type_data", {})
        tail = atd.get("native_tail") or {}
        size = tail.get("size", 0)
        print(f"\n[{cls}] {exp.get('object_name')} "
              f"tail offset={tail.get('offset')} size={size}")
        if size <= 0:
            continue
        data = raw[tail["offset"]:tail["offset"] + size]
        print(_hexdump(data, limit=64))
        # int32 scan: candidate name indices / export refs / counts
        n = size // 4
        ints = struct.unpack(f"<{n}i", data[:n * 4])
        small = [v for v in ints if 0 <= v < 200000]
        print(f"  int32 values: {len(ints)} total, {len(small)} in [0, 200000)")
        if small:
            print(f"  small-int range: {min(small)}..{max(small)}")
        # repeated 16-byte runs: candidate GUID arrays (pin persistent ids)
        seen: dict[bytes, int] = {}
        for off in range(0, size - 16, 4):
            block = data[off:off + 16]
            if any(block):
                seen[block] = seen.get(block, 0) + 1
        repeats = {k: v for k, v in seen.items() if v > 1}
        if repeats:
            print(f"  repeated 16-byte blocks: {len(repeats)} distinct")

    print("\n=== Outputs/OutputVars UnknownStruct elements ===")
    for exp in payload["exports"]:
        atd = exp.get("asset_type_data", {})
        tagged = atd.get("tagged_properties", {})
        for prop_name in ("Outputs", "OutputVars"):
            value = tagged.get(prop_name)
            if not isinstance(value, dict):
                continue
            items = value.get("items", [])
            for i, item in enumerate(items):
                iv = item.get("value", item) if isinstance(item, dict) else item
                if isinstance(iv, dict) and iv.get("struct_type") in (
                    None, "UnknownStruct", "Unknown",
                ):
                    print(f"\n[{exp.get('object_name')}] {prop_name}[{i}]:")
                    print(json.dumps(iv, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script and capture the report**

```bash
python tests/temp/inspect_521_node_tails.py > temp/b0a_report.txt
```

Read the report. For each node class note: tail size, presence of FName-index-shaped int32 clusters, repeated 16-byte GUID blocks, ASCII name fragments.

- [ ] **Step 3: Identify the Outputs/OutputVars element structs**

Using the report's element dumps plus the UE checkout, compare against candidate layouts:

```bash
grep -n "struct FNiagaraVariable\b" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source/Niagara/Public/NiagaraTypes.h"
grep -rn "StaticSwitchTypeData\|FNiagaraStaticSwitchType" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source" --include=*.h | head
```

For each of the 7 `UnknownStruct` elements record: identified type with evidence (size/layout/GUID match against a checkout struct definition) or "unidentified — deferred to B0b". This result feeds Task 9.

- [ ] **Step 4: Write the evidence document**

Create `docs/designs/issue-521-b0-pin-existence-evidence.md` with this structure (fill from the report):

```markdown
# Issue #521 B0a — Pin Existence Evidence

> Status: diagnostic evidence (2026-08-XX)
> Fixture: `tests/samples/NM_BPSystemEvent.uasset`
> SHA-256: `B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF`
> UE checkout: `E:/Develop/lib/UnrealEngine` @ `7deeb413d3dc1fc034f48d1aacc0861301829d32` (5.8.0-release)
> Script: `tests/temp/inspect_521_node_tails.py` (read-only; parse output unchanged)

## Method

Handler-recorded native tails (offset/size) were hex-inspected for pin markers:
FName-index-shaped int32 clusters, repeated 16-byte GUID blocks, ASCII name
fragments. No decoding was attempted.

## Per-node-class tail inventory

| Node class | Export | Tail offset | Tail size | Markers found |
|---|---|---|---|---|
| … | … | … | … | … |

## Outputs/OutputVars element identification

| Element | Identified type | Evidence |
|---|---|---|
| … | … | … |

## Conclusion

One of:
- Pin structures FOUND in native tails → proceed to B0b with targets.
- Pin structures NOT found → B0b source conclusion decides fixture expansion
  vs disproven-closed (roadmap decision tree).
- INCONCLUSIVE → list exactly what B0b must settle.
```

- [ ] **Step 5: Verify parse output is unchanged**

```bash
python -m pytest tests/temp/test_issue_521_niagara_coverage.py tests/temp/test_issue_521_niagara_evidence.py -q
```

Expected: PASS (the script touched no `src/` code).

- [ ] **Step 6: Commit**

```bash
git add tests/temp/inspect_521_node_tails.py
git commit -m "test: add #521 B0a native-tail inspection script (#521)"
git add docs/designs/issue-521-b0-pin-existence-evidence.md
git commit -m "docs: record #521 B0a pin existence evidence (#521)"
```

---

### Task 7: B0b — UE source audit and gate decision

**Files:**
- Create: `docs/designs/issue-521-b0-gate-decision.md`
- Issue: comment on #521; conditionally create a fixture-expansion issue

**Interfaces:**
- Consumes: Task 6's evidence document (its conclusion selects the audit focus)
- Produces: THE gate decision that controls all later B1/B2 planning (roadmap: "B1/B2 plans are written after the B0 gate result is known"); pin-path verdict consumed by #525 scoping

- [ ] **Step 1: Record the fixture's exact package version**

```bash
python -c "import sys, json; sys.path.insert(0, 'src'); from uasset_read import parse_single; d=json.loads(parse_single('tests/samples/NM_BPSystemEvent.uasset', format='json', tolerant=True, log_enabled=False)); s=d['summary']; print(json.dumps({k: v for k, v in s.items() if 'version' in k.lower()}, indent=2))"
```

Record the values in the decision doc. If the package version is older than 5.8, every cited code path must additionally be checked for version guards (`Ar.IsAtLeastVersion`, `#if`, FCustomVersion checks); record deltas.

- [ ] **Step 2: Audit pin serialization (the gate question)**

Run against the checkout (adjust paths if the B0a conclusion points elsewhere):

```bash
grep -rn "class NIAGARAEDITOR_API UNiagaraNode" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source/NiagaraEditor/Public/NiagaraNode.h"
grep -n "Serialize\|InputPins\|OutputPins\|Pins" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source/NiagaraEditor/Private/NiagaraNode.cpp" | head -40
grep -n "Serialize" "E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphNode.cpp" | head -20
grep -rn "SerializePin\|LinkedTo" "E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Public/EdGraph/EdGraphPin.h" | head -20
grep -rn "SerializePin\|LinkedTo" "E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp" | head -30
```

Answer with `file:line` citations (all against the recorded checkout commit):
1. Where are pins stored for Niagara nodes (member declarations)?
2. Are pins serialized into the package at all, and by which function? If version-gated, quote the guard.
3. How is `LinkedTo` serialized (reference form and boundary — e.g. index-based resolution within the node's pin list)?

- [ ] **Step 3: Apply the roadmap decision tree and write the decision**

Combine B0a's fixture conclusion (Task 6) with Step 2's source answer:

| Source says | Fixture says | Decision |
|---|---|---|
| serialized | markers found | **Pin path live** — B1/B2 planning includes the pin half |
| serialized | not found | **Fixture expansion** — create the Phase 1.5 issue (Step 4); B0a re-entry after expansion |
| not serialized | not found | **Pin half disproven-closed** — record the source evidence; #525 scope change touches its pin half only (`parameters` acceptance stands) |

Create `docs/designs/issue-521-b0-gate-decision.md`:

```markdown
# Issue #521 B0b — Source Audit Gate Decision

> Status: gate decision (2026-08-XX)
> Inputs: `issue-521-b0-pin-existence-evidence.md` (B0a); UE checkout
> `E:/Develop/lib/UnrealEngine` @ `7deeb413d3dc1fc034f48d1aacc0861301829d32` (5.8.0-release)
> Fixture package version: <from Step 1>

## Source citations

1. Pin storage: `<file>:<lines>` — …
2. Pin serialization: `<file>:<lines>` — … (version guards: …)
3. LinkedTo boundary: `<file>:<lines>` — …

## Gate decision

<one row of the decision table, justified>

## Consequences

- #525: <pin half stands / narrows — parameters path unaffected in all branches>
- Next plan: B1/B2 planning proceeds / waits for fixture expansion
```

- [ ] **Step 4 (conditional): fixture expansion issue**

Only if the decision is "Fixture expansion":

```bash
gh issue create --title "#521 Phase 1.5: acquire Niagara fixture with serialized pin data" --body @- <<'EOF'
Outcome of the #521 B0b gate (`docs/designs/issue-521-b0-gate-decision.md`): UE source
shows pin structures are serialized, but the current fixture
(`tests/samples/NM_BPSystemEvent.uasset`) contains no pin-class exports and no pin
markers in node native tails (B0a evidence).

## Tasks

1. Acquire a Niagara asset with populated pin data from UE sample content
   (respect the `tests/samples/` content rules in force at that time).
2. Pin its SHA-256; extend the B0a inventory script to the new fixture.
3. Re-enter B0a, then re-evaluate the B0b gate.

Parent: #521
EOF
```

- [ ] **Step 5: Comment the decision on the Epic**

```bash
gh issue comment 521 --body "B0 gate decided (see docs/designs/issue-521-b0-gate-decision.md): <one-line decision>. Consequences for #525: <one line>."
```

- [ ] **Step 6: Commit**

```bash
git add docs/designs/issue-521-b0-gate-decision.md
git commit -m "docs: record #521 B0b source-audit gate decision (#521)"
```

---

### Task 8: B1-pre code — Extend the #515 struct scan

**Files:**
- Modify: `tests/temp/scan_opaque_structs.py`
- Scratch output: `temp/b1_pre_scan.json`

**Interfaces:**
- Consumes: nothing from earlier tasks (may run in parallel with B0)
- Produces: the re-scan JSON that Task 9 turns into candidate entries; the `export_status` field on occurrence records

The scan currently filters `if ps != "opaque": continue` and therefore structurally misses structs inside `partial_metadata` exports — which now includes ALL Niagara exports. This task fixes that blind spot. The re-scan must not change any parse output (no `src/` changes).

- [ ] **Step 1: Broaden the scan filter**

In `tests/temp/scan_opaque_structs.py` make these edits:

1. Module docstring, replace

```python
and extracts StructProperty candidates from exports with parse_status == "opaque".
```

with

```python
and extracts StructProperty candidates from exports whose parse_status is
"opaque" or "partial_metadata" (B1-pre intake fix: partial_metadata exports
were structurally missed before).
```

2. In `scan_opaque_structs()`, replace the filter block

```python
            ps = exp.get("parse_status", "success")
            if ps != "opaque":
                continue

            total_opaque_exports += 1
            files_with_opaque.add(rel_path)
```

with

```python
            ps = exp.get("parse_status", "success")
            if ps not in ("opaque", "partial_metadata"):
                continue

            total_opaque_exports += 1
            files_with_opaque.add(rel_path)
            export_status = ps
```

3. In the occurrence record (inside the `for entry in struct_entries:` loop), add the status:

```python
                by_type[entry["struct_type"]].append({
                    "file": rel_path,
                    "object_name": exp.get("object_name", "?"),
                    "outer_path": entry["outer_path"],
                    "raw_size": entry["raw_size"],
                    "export_status": export_status,
                })
```

(`export_status` is assigned before the loop in edit 2, so it is in scope here.)

- [ ] **Step 2: Re-run the scan**

```bash
python tests/temp/scan_opaque_structs.py > temp/b1_pre_scan.json
```

Expected: `NM_BPSystemEvent` now contributes Niagara structs — verify in the JSON: `NiagaraVariable` (occurrences ≥ 12), `NiagaraVariableMetaData` (≥ 11), `NiagaraVariant` (≥ 11), `NiagaraTypeDefinition` (≥ 1), `StaticSwitchTypeData` (≥ 1), all with `export_status: "partial_metadata"`; pre-existing opaque candidates (`AlphaBlend`, `MeshSectionInfoMap`, `MeshNaniteSettings`, `NiagaraParameterStore`, `RawCurveTracks`, `StaticMeshSourceModel`, `BoxSphereBounds`) still present with `export_status: "opaque"`. Note: summary counts will drift from the stale candidates-doc header (41/39/8) — Task 9 refreshes them.

- [ ] **Step 3: Verify parse output unchanged**

```bash
python -m pytest tests/temp/test_issue_521_niagara_coverage.py tests/temp/test_issue_521_niagara_evidence.py -q
python -m pytest tests/ --ignore=tests/temp -q
```

Expected: PASS (script-only change; root suite 125 + 1 known failure).

- [ ] **Step 4: Commit**

```bash
git add tests/temp/scan_opaque_structs.py
git commit -m "feat: extend #515 struct scan to partial_metadata exports (#515)"
```

---

### Task 9: B1-pre docs — Candidate intake into the #515 list

**Files:**
- Modify: `docs/designs/issue-515-candidates.md`
- Modify: `docs/designs/issue-515-opaque-structproperty-roadmap.md`
- Scratch input: `temp/b1_pre_scan.json`

**Interfaces:**
- Consumes: Task 8's scan JSON; Task 6's `Outputs`/`OutputVars` identification (if any element type was identified, it is added here too); UE checkout for source references
- Produces: the candidate entries and gate evaluations that Task 10 converts into issues

- [ ] **Step 1: Refresh the scan summary**

In `docs/designs/issue-515-candidates.md`, update the `## Scan Summary` table and the header dates from `temp/b1_pre_scan.json` (total samples, files with in-scope exports, total in-scope exports, total struct entries, unique struct types). Add a note line:

```markdown
> 2026-08-XX (B1-pre): scan extended to `partial_metadata` exports; counts refreshed.
```

- [ ] **Step 2: Collect source references for each new struct**

Run and record `file:line` per struct (adjust to actual hits):

```bash
grep -n "struct FNiagaraVariable\b\|struct FNiagaraVariableMetaData\|struct FNiagaraVariant\|struct FNiagaraTypeDefinition" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source/Niagara/Public/NiagaraTypes.h"
grep -rn "StaticSwitchTypeData" "E:/Develop/lib/UnrealEngine/Engine/Plugins/FX/Niagara/Source" --include=*.h | head
```

- [ ] **Step 3: Add the candidate entries**

In `issue-515-candidates.md`: add each struct to the `## All Candidates by Frequency` table (frequency from the scan JSON), and append a new section:

```markdown
## Niagara Intake (B1-pre, from #521 roadmap)

Fixture: `tests/samples/NM_BPSystemEvent.uasset`, SHA-256
`B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF`.
UE checkout: `E:/Develop/lib/UnrealEngine` @ `7deeb413d3dc1fc034f48d1aacc0861301829d32`
(5.8.0-release). Property paths observed: `NiagaraScriptVariable.Variable` /
`.Metadata` / `.DefaultValueVariant`, `NiagaraNodeOutput.Outputs`,
`NiagaraNodeSelect.OutputVars`, `NiagaraNodeStaticSwitch.OutputVars` /
`.SwitchTypeData`.

| Struct | Source reference | Selection gate (fixture / boundary / source / semantics) | Qualifies |
|---|---|---|---|
| NiagaraVariable | `<NiagaraTypes.h>:<lines>` | ✓ / ✓ (tag.size) / ✓ / ✓ | yes |
| NiagaraVariableMetaData | `<file>:<lines>` | ✓ / ✓ / ✓ / ✓ | yes |
| NiagaraVariant | `<file>:<lines>` | ✓ / ✓ / ✓ / ✓ | yes |
| NiagaraTypeDefinition | `<file>:<lines>` | ✓ / ✓ / ✓ / ✓ | yes |
| StaticSwitchTypeData | `<file>:<lines>` | ✓ / ✓ / ✓ / ✓ | yes |
| <Outputs element type, if B0a identified it> | … | … | … |
```

Fill the `file:line` cells from Step 2; adjust any gate cell that fails and mark that struct "no" with the reason. If B0a left the `Outputs` element type unidentified, add a row `Outputs element (unidentified)` marked "pending B0a re-entry" instead of an issue.

- [ ] **Step 4: Add the intake-fix note to the #515 roadmap doc**

Append to the `## 当前基线` list in `docs/designs/issue-515-opaque-structproperty-roadmap.md` (document is Chinese; note follows it):

```markdown
- B1-pre（2026-08-XX，源自 #521 收尾路线图）：扫描脚本 `tests/temp/scan_opaque_structs.py` 已扩展至 `partial_metadata` 导出（此前结构性遗漏）；新增 Niagara 结构候选及筛选结果见 `issue-515-candidates.md` 的 Niagara Intake 一节。
```

- [ ] **Step 5: Commit**

```bash
git add docs/designs/issue-515-candidates.md docs/designs/issue-515-opaque-structproperty-roadmap.md
git commit -m "docs: intake Niagara structs into #515 candidate list (#515)"
```

---

### Task 10: B1-pre issues — Per-struct slice issues and #515 linkage

**Files:**
- Issues only (no repo changes)

**Interfaces:**
- Consumes: Task 9's gate results (only structs marked "yes" get issues)
- Produces: the per-struct #515 child issues that the later B1 plan executes; the #515 linkage comment

- [ ] **Step 1: Create one issue per qualifying struct**

For each struct marked "yes" in Task 9's intake table (expected: `NiagaraVariable`, `NiagaraVariableMetaData`, `NiagaraVariant`, `NiagaraTypeDefinition`, `StaticSwitchTypeData`, plus the `Outputs` element type only if identified), substitute the struct-specific values and run:

```bash
gh issue create --title "#515 slice: decode <StructType> from NM_BPSystemEvent" --body @- <<'EOF'
Child of #515 (opaque StructProperty roadmap), intaken via #521 roadmap slice B1-pre.

## Target

Struct: `<StructType>`
Fixture: `tests/samples/NM_BPSystemEvent.uasset`
SHA-256: `B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF`
UE version / checkout: 5.8.0-release, `E:/Develop/lib/UnrealEngine` @ `7deeb413d3dc1fc034f48d1aacc0861301829d32`
Property path(s): `<outer_path(s) from the candidates doc>`
Source reference: `<file>:<lines>`

## Acceptance

- Tagged fallback first; a native parser only when the #515 roadmap trigger
  conditions are met (fixed layout documented in UE source / tagged fallback
  cannot express the layout / performance).
- 4 test scenarios in `tests/temp/`: normal / truncated / unknown version / malformed.
- Malformed data keeps the opaque fallback; no silent partial decode.
- No layout guessing — every decoded field cites the source reference above.
- No regression: root suite and Niagara focused suite stay green.

Parent: #515 · Related: #521, #525
EOF
```

Ordering note for later B1 planning (record in each issue's body is unnecessary — the B1 plan owns order): `NiagaraVariable` first (parameters path), then the `Outputs`/`OutputVars` element structs, then `NiagaraVariableMetaData`/`NiagaraVariant`, then `NiagaraParameterStore` (already a candidate).

- [ ] **Step 2: Link from #515**

```bash
gh issue comment 515 --body "B1-pre intake (#521 roadmap): <N> new child issues created — <comma-separated issue numbers>. Candidate entries: docs/designs/issue-515-candidates.md §Niagara Intake."
```

- [ ] **Step 3: Verify**

```bash
gh issue list --state open --search "515 slice" --json number,title
```

Expected: one issue per qualifying struct; all reference parent #515.

---

## Final Verification (after Task 10)

- [ ] Run the full guard set:

```bash
python -m pytest tests/temp/test_issue_521_niagara_evidence.py tests/temp/test_issue_521_niagara_graph_handler.py tests/temp/test_issue_521_niagara_node_handler.py tests/temp/test_issue_521_niagara_routing.py tests/temp/test_issue_521_niagara_script_handler.py tests/temp/test_issue_521_niagara_coverage.py -q
python -m pytest tests/ --ignore=tests/temp -q
```

Expected: 59 original Niagara tests + new coverage/routing tests green; root suite 125 passed + the 1 known #518-related failure.

- [ ] Slice completion check against the roadmap:
  - A1: Epic body rewritten ✓ · plan doc synced ✓ · test-infrastructure issue created ✓
  - A2: execution-flow section in the field-contract doc ✓
  - A3: coverage table ✓ · NiagaraScriptVariable `partial_metadata` ✓ · no Niagara class undecided ✓
  - B0a: evidence doc ✓ · B0b: gate decision doc + Epic comment ✓
  - B1-pre: scan fixed ✓ · candidates updated ✓ · per-struct issues created ✓

- [ ] Next step (not in this plan): write the B1/B2 implementation plan from the recorded B0 gate result.

## Self-Review Record

- Spec coverage: every roadmap slice in scope (A1–A3, B0a, B0b, B1-pre) maps to tasks; B1/B2 intentionally deferred per the roadmap's Plan Splitting.
- The review-found corrections are baked in: only the stale count 26 is fixed (28 preserved), baseline 125/126 (not 118/119), #518 failure tracked via the Task 1 issue, B1-pre ordering note (Outputs types await B0a), B0b failure-branch wording aligned with #525.
- Type/name consistency: `asset_type_data.tagged_properties` / `asset_type_data.native_tail` access matches existing handler tests; `_PROJECTED_PROPERTIES` names match the live fixture probe; `EXPECTED_NIAGARA_CLASS_COUNTS` matches the verified baseline.
