# Parser Quality System (reason + baseline gates) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: historical (executed 2026-09-15).** Deliverables landed on `dev-0.6.0` (quality baseline + `Diagnostic.reason` live in `tests/`/`src/`); checkbox state was not maintained during execution. This file is execution evidence. Do not invoke SDD or rerun its commands unless the user explicitly names this file and requests a new replay.

**Goal:** Add an optional `Diagnostic.reason` classification, wire it on high-volume diagnostic sites, and gate tracked sample fixtures with a quality baseline so unexpected recovery/semantic-loss is visible and regressive.

**Architecture:** Runtime stays “structured diagnostics only” (no process-global logging). `reason` is an optional additive field on `Diagnostic` (stable envelope; schema `additionalProperties: false` must be updated in the same change). A thin classifier maps known trailing/recovery situations to closed reason values. Sample tests load `tests/samples/quality_baseline.json` and assert max counts / forbidden codes on a small seed set of tracked fixtures. Deep parser fixes (Niagara node bodies, BP name-index clusters, RefSkeleton) are **out of this plan** and become follow-up plans once reason data is measurable.

**Tech Stack:** Python 3.10+, stdlib dataclasses, existing `uasset_read` package, pytest + jsonschema (already used in `tests/test_samples.py`).

**Spec:** Design brief in this document (§ Design brief). Evidence: `temp/sample_parse/REVIEW.md` (33-type sweep). Do **not** invent a second output format.

**Related contracts:** S1 stable diagnostic structure (`docs/designs/2026-08-31-v2-contract-stability.md`); schema `docs/designs/contract/package_document_v2.schema.json`; package-first target `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`.

---

## Design brief (source of truth for this plan)

### Goals

1. Classify diagnostics so humans/CI can separate expected residue from suspicious recovery.
2. Keep `format_version: "2.0"` — additive optional key only; no new top-level format.
3. Quality gates read PackageDocument; no library file logging.

### Non-goals (this plan)

- Implementing Niagara / RefSkeleton / DataTable payload fixes.
- Changing severity enums or retiring `EXPORT_TRAILING_BYTES_UNCONSUMED`.
- Scanning `E:\Develop\lib\Samples` in CI.
- Count-aggregation (`count` field) and log-formatter CLI redesign.

### `reason` value set (closed)

| value | meaning |
|-------|---------|
| `bulk_expected` | bulk/stream payload intentionally not embedded as properties |
| `editor_only` | editor-only graph / MetaData / K2 tails |
| `known_unimplemented` | known gap with backlog owner |
| `recovered_corruption` | bad read that was recovered (empty string / default name / shifted FName) |
| `conservative_complete` | data may be complete; completeness flag is conservative |
| `unexpected` | does not fit the above — CI attention |

Optional field; omit when unset (`None` → not in `to_dict()`).

### Seed baseline samples (tracked fixtures only)

| fixture | why |
|---------|-----|
| `FirstPerson_DT_WeaponList.uasset` | DataTable table diagnostics |
| `FirstPerson_T_GridChecker_A.uasset` | Texture + MetaData trailing |
| `FirstPerson_BS_Idle_Walk_Run.uasset` | BlendSpace trailing |
| `ALS_Mannequin_Skeleton.uasset` | Skeleton large trailing |
| `BP_CombatCharacter.uasset` | Blueprint recovery / trailing density |

Exclude multi-MB `ALS_AnimBP.uasset` from the default baseline run (too slow for every gate); may be opt-in later.

### File map

| path | responsibility |
|------|----------------|
| `docs/designs/2026-09-15-parser-quality-system.md` | Target design companion (status: target) |
| `docs/designs/contract/package_document_v2.schema.json` | Add optional `reason` to `$defs.Diagnostic` |
| `src/uasset_read/models/diagnostics.py` | `Diagnostic.reason`, `DiagnosticReason` type, `make_diagnostic(..., reason=)`, `classify_trailing_reason()` |
| `src/uasset_read/archive.py` | `_record_structured_diagnostic(..., reason=)`; recovery sites pass `recovered_corruption` |
| `src/uasset_read/parsers/legacy_reader.py` | Trailing-bytes emission uses classifier by class name |
| `src/uasset_read/parsers/...` table path | TABLE_* diagnostics use `conservative_complete` |
| `tests/samples/quality_baseline.json` | Seed thresholds + forbidden codes |
| `tests/test_diagnostics_reason.py` | Unit tests for model/classifier |
| `tests/test_samples.py` | Optional baseline gate helper + one integration test |
| `tools/gen_quality_baseline.py` | Local helper to (re)generate baseline from tracked samples (not on CI path) |

---

## Global Constraints

- Python 3.10+; no new runtime dependencies.
- Do not configure process-global logging from the library.
- `format_version` stays `"2.0"`. Adding optional Diagnostic `reason` is a **stable additive** schema change (S1): update schema in the same PR; do not rename codes.
- Schema `additionalProperties: false` on Diagnostic — **must** add `reason` or projection validation breaks once the key is emitted.
- TDD: write failing tests before implementation for each behavior-bearing task.
- Temporary scripts under `temp/` only if non-shipping; shipping helper is `tools/gen_quality_baseline.py`.
- Do not add `reason` as required; omit when `None`.
- Prefer editing existing files; no new package under `src/uasset_read/quality/` in this plan.

---

### Task 1: Design companion document

**Files:**
- Create: `docs/designs/2026-09-15-parser-quality-system.md`
- Modify: `docs/designs/README.md` (index row)

**Interfaces:**
- Consumes: none
- Produces: design status `target`; plan executors read it for rationale

- [ ] **Step 1: Write design doc**

Create `docs/designs/2026-09-15-parser-quality-system.md` with:

```markdown
# 解析质量体系：Diagnostic.reason 与样本基线门禁

status: target

> 关联：S1 `2026-08-31-v2-contract-stability.md`；权威 package-first 设计；证据 `temp/sample_parse/REVIEW.md`（33 类扫库，957 诊断中 905 为无分类 trailing）。
> 本设计不改 process-global logging；不改 `format_version`。

## 1. 目标

1. 用可选 `reason` 区分预期残量与可疑 recovery，使 unexpected 成为 CI 主信号。
2. 在 tracked fixtures 上建立 `quality_baseline.json` 门禁。
3. 深度解析修复（Niagara / BP name 集群 / RefSkeleton）不在本文实现范围，只定度量口径。

## 2. reason 值域（封闭）

bulk_expected | editor_only | known_unimplemented | recovered_corruption | conservative_complete | unexpected

规则：code 不变；`reason=None` 时 JSON 省略；不替代 `effect`；未知归 unexpected。

## 3. 接线点

- trailing: `legacy_reader` EXPORT_TRAILING_BYTES_UNCONSUMED + class 名分类
- recovery: archive `fstring_all_null` / `name_index_out_of_range` / `fname_index_shift_recovered` → recovered_corruption
- table: TABLE_PAYLOAD_RESIDUE / TABLE_ROWS_TRUNCATED → conservative_complete

## 4. 基线门禁

`tests/samples/quality_baseline.json`：按样本 allowed max（code×reason）与 forbidden_codes。默认种子：FirstPerson_DT_WeaponList、FirstPerson_T_GridChecker_A、FirstPerson_BS_Idle_Walk_Run、ALS_Mannequin_Skeleton、BP_CombatCharacter。

## 5. 成功标准

- 分类后 unexpected 为主要人工信号
- 门禁可红绿
- 无 format major bump

## 6. 非目标

Niagara/RefSkeleton 实现；库级日志；temp 全量扫库进 CI。
```

- [ ] **Step 2: Update design index**

In `docs/designs/README.md` add a row under Companion Contracts:

```markdown
| — | [`2026-09-15-parser-quality-system.md`](2026-09-15-parser-quality-system.md) | target | Diagnostic.reason taxonomy + sample quality baseline gates. |
```

- [ ] **Step 3: Verify docs only**

Run: `git status --short`  
Expected: only the two docs files changed.

- [ ] **Step 4: Commit**

```bash
git add docs/designs/2026-09-15-parser-quality-system.md docs/designs/README.md
git commit -m "docs: add parser quality system design (target)"
```

---

### Task 2: `Diagnostic.reason` model + schema (additive)

**Files:**
- Modify: `src/uasset_read/models/diagnostics.py`
- Modify: `docs/designs/contract/package_document_v2.schema.json` (`$defs.Diagnostic`)
- Test: `tests/test_diagnostics_reason.py` (create)

**Interfaces:**
- Consumes: existing `Diagnostic` / `make_diagnostic`
- Produces:
  - `DiagnosticReason` = `Literal["bulk_expected", "editor_only", "known_unimplemented", "recovered_corruption", "conservative_complete", "unexpected"]`
  - `Diagnostic.reason: DiagnosticReason | None = None`
  - `make_diagnostic(..., reason: DiagnosticReason | None = None) -> Diagnostic`
  - schema property `reason` (string enum of the six values; not required)

- [ ] **Step 1: Write failing unit tests**

Create `tests/test_diagnostics_reason.py`:

```python
"""Unit tests for Diagnostic.reason (quality system)."""

from uasset_read.models.diagnostics import Diagnostic, make_diagnostic


def test_reason_omitted_from_dict_when_unset():
    d = make_diagnostic("SOME_CODE", "msg", "objects.export")
    assert d.reason is None
    payload = d.to_dict()
    assert "reason" not in payload


def test_reason_included_when_set():
    d = make_diagnostic(
        "EXPORT_TRAILING_BYTES_UNCONSUMED",
        "leaves 53 bytes",
        "objects.export",
        reason="editor_only",
    )
    assert d.reason == "editor_only"
    assert d.to_dict()["reason"] == "editor_only"


def test_make_diagnostic_accepts_reason_keyword():
    d = Diagnostic(
        severity="warning",
        code="name_index_out_of_range",
        message="bad index",
        stage="read_name",
        reason="recovered_corruption",
    )
    assert d.reason == "recovered_corruption"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_diagnostics_reason.py -v`  
Expected: FAIL (`unexpected keyword argument 'reason'` or attribute missing).

- [ ] **Step 3: Implement model change**

In `src/uasset_read/models/diagnostics.py`:

```python
from typing import Any, Literal

DiagnosticReason = Literal[
    "bulk_expected",
    "editor_only",
    "known_unimplemented",
    "recovered_corruption",
    "conservative_complete",
    "unexpected",
]


@dataclass
class Diagnostic:
    severity: Literal["info", "warning", "error", "critical"] = "warning"
    code: str = ""
    message: str = ""
    stage: str = ""
    object_id: str | None = None
    offset: int | None = None
    size: int | None = None
    effect: Literal["semantic_loss", "data_loss", "parse_failure", "recovery"] | None = None
    recoverable: bool = True
    fallback: str | None = None
    reason: DiagnosticReason | None = None  # optional classification

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {
            k: v
            for k, v in d.items()
            if v is not None and (k == "recoverable" or (not isinstance(v, bool) or v))
        }


def make_diagnostic(
    code: str,
    message: str,
    stage: str,
    *,
    object_id: str | None = None,
    severity: Literal["info", "warning", "error", "critical"] = "warning",
    effect: Literal["semantic_loss", "data_loss", "parse_failure", "recovery"] | None = "semantic_loss",
    reason: DiagnosticReason | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity=severity,
        code=code,
        message=message,
        stage=stage,
        object_id=object_id,
        effect=effect,
        reason=reason,
    )
```

Note: existing `DIAGNOSTIC_CODE_*` constants stay unchanged.

- [ ] **Step 4: Update schema**

In `docs/designs/contract/package_document_v2.schema.json` under `$defs.Diagnostic.properties`, after `count`, add:

```json
"reason": {
  "type": "string",
  "enum": [
    "bulk_expected",
    "editor_only",
    "known_unimplemented",
    "recovered_corruption",
    "conservative_complete",
    "unexpected"
  ],
  "description": "Optional classification of why this diagnostic was emitted. Omitted when unset."
}
```

Do not add `reason` to `required`.

- [ ] **Step 5: Run unit tests + schema-consuming sample smoke**

Run: `python -m pytest tests/test_diagnostics_reason.py tests/test_core.py -q`  
Expected: PASS (core must not regress; new field is optional).

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/models/diagnostics.py docs/designs/contract/package_document_v2.schema.json tests/test_diagnostics_reason.py
git commit -m "feat: add optional Diagnostic.reason and schema enum"
```

---

### Task 3: Thread `reason` through archive + make_diagnostic call sites that need it

**Files:**
- Modify: `src/uasset_read/archive.py` (`_record_structured_diagnostic` and recovery call sites)
- Test: `tests/test_diagnostics_reason.py` (extend)

**Interfaces:**
- Consumes: `Diagnostic.reason` from Task 2
- Produces:
  - `FArchive._record_structured_diagnostic(..., reason: DiagnosticReason | None = None)`
  - Recovery diagnostics carry `reason="recovered_corruption"`

- [ ] **Step 1: Write failing test for archive recovery reason**

Extend `tests/test_diagnostics_reason.py`:

```python
def test_fname_out_of_range_carries_recovered_corruption_reason(tmp_path):
    # Build a minimal ByteArchive-like path is heavy; call _record on FArchive subclass.
    from uasset_read.archive import FArchive

    class _Mem(FArchive):
        def __init__(self):
            self._init_archive_attrs(path="<mem>", tolerant=True)
            self._file = None

    arch = _Mem()
    arch._current_object_id = "export:1"
    arch._record_structured_diagnostic(
        code="name_index_out_of_range",
        stage="read_name",
        offset=16,
        raw_value=3223003549,
        fallback="used_default_name",
        message="Name index out of range",
        reason="recovered_corruption",
    )
    (diag,) = arch.get_structured_diagnostics()
    assert diag.reason == "recovered_corruption"
    assert diag.code == "name_index_out_of_range"
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_diagnostics_reason.py::test_fname_out_of_range_carries_recovered_corruption_reason -v`  
Expected: FAIL (`reason` unexpected keyword).

- [ ] **Step 3: Implement `_record_structured_diagnostic`**

In `src/uasset_read/archive.py`:

```python
def _record_structured_diagnostic(
    self,
    code: str,
    stage: str,
    offset: int,
    raw_value: Any = None,
    ue_version: str = "",
    fallback: str = "",
    message: str = "",
    severity: Literal["info", "warning", "error", "critical"] = "warning",
    reason: Literal[
        "bulk_expected",
        "editor_only",
        "known_unimplemented",
        "recovered_corruption",
        "conservative_complete",
        "unexpected",
    ] | None = None,
) -> None:
    enriched = message
    if raw_value is not None:
        enriched += f" raw_value={raw_value}"
    if ue_version:
        enriched += f" ue_version={ue_version}"
    if fallback:
        enriched += f" fallback={fallback}"

    self._structured_diagnostics.append(
        Diagnostic(
            code=code,
            severity=severity,
            stage=stage,
            object_id=self._current_object_id,
            offset=offset,
            message=enriched,
            fallback=fallback or None,
            reason=reason,
        )
    )
```

Prefer importing `DiagnosticReason` from models to avoid a duplicated Literal if import is clean; if circular-import risk, keep the inline Literal only here and a single Literal in models.

- [ ] **Step 4: Pass reason on recovery sites**

In the same file, update these calls (add `reason="recovered_corruption"` only; leave messages otherwise unchanged):

1. `fstring_all_null` (UTF-16 branch ~line 392)
2. `fstring_truncated_at_null` (~line 411)
3. `fstring_all_null` (UTF-8 corrupted branch ~line 444)
4. `fname_index_shift_recovered` (~line 518)
5. `name_index_out_of_range` (~line 537)

Example:

```python
self._record_structured_diagnostic(
    code="name_index_out_of_range",
    stage="read_name",
    offset=self.tell() - 8,
    raw_value=index,
    fallback="used_default_name",
    message=f"Name index {index} out of range [0, {len(name_map)}]",
    reason="recovered_corruption",
)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_diagnostics_reason.py tests/test_core.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/archive.py tests/test_diagnostics_reason.py
git commit -m "feat: classify archive recovery diagnostics as recovered_corruption"
```

---

### Task 4: Classify `EXPORT_TRAILING_BYTES_UNCONSUMED`

**Files:**
- Modify: `src/uasset_read/models/diagnostics.py` (add `classify_trailing_reason`)
- Modify: `src/uasset_read/parsers/legacy_reader.py` (trailing emission ~lines 872-881)
- Test: `tests/test_diagnostics_reason.py` (extend)

**Interfaces:**
- Consumes: `make_diagnostic` / `_diag` with `reason=`
- Produces:
  - `classify_trailing_reason(class_name: str, remaining: int) -> DiagnosticReason`

- [ ] **Step 1: Write failing classifier tests**

```python
def test_classify_trailing_reason_mapping():
    from uasset_read.models.diagnostics import classify_trailing_reason

    assert classify_trailing_reason("PackageMetaData", 53) == "editor_only"
    assert classify_trailing_reason("MetaData", 53) == "editor_only"
    assert classify_trailing_reason("FontFace", 6_715_680) == "bulk_expected"
    assert classify_trailing_reason("SoundWave", 68) == "bulk_expected"
    assert classify_trailing_reason("NiagaraNodeFunctionCall", 7900) == "known_unimplemented"
    assert classify_trailing_reason("NiagaraNodeAssignment", 100) == "known_unimplemented"
    assert classify_trailing_reason("Skeleton", 9191) == "known_unimplemented"
    assert classify_trailing_reason("PhysicsAsset", 940) == "known_unimplemented"
    assert classify_trailing_reason("BlueprintGeneratedClass", 5977) == "editor_only"
    assert classify_trailing_reason("K2Node_CallFunction", 200) == "editor_only"
    assert classify_trailing_reason("EdGraph", 100) == "editor_only"
    assert classify_trailing_reason("SomeUnknownClass", 100) == "unexpected"
```

- [ ] **Step 2: Verify fail**

Run: `python -m pytest tests/test_diagnostics_reason.py::test_classify_trailing_reason_mapping -v`  
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement classifier**

Append to `src/uasset_read/models/diagnostics.py`:

```python
_EDITOR_ONLY_PREFIXES = (
    "MetaData",
    "PackageMetaData",
    "K2Node_",
    "EdGraph",
    "EdGraphNode",
    "Blueprint",
    "WidgetBlueprint",
    "AnimBlueprint",
    "Function",
)

_BULK_CLASSES = frozenset(
    {
        "FontFace",
        "Font",
        "SoundWave",
        "SoundCue",
        "RawAudio",
    }
)

_KNOWN_UNIMPLEMENTED_CLASSES = frozenset(
    {
        "Skeleton",
        "PhysicsAsset",
        "SkeletalBodySetup",
        "StaticMesh",
        "StaticMeshDescriptionBulkData",
        "UserDefinedStruct",
    }
)

_KNOWN_UNIMPLEMENTED_PREFIXES = (
    "NiagaraNode",
    "NiagaraScript",
    "NiagaraEmitter",
    "NiagaraSystem",
)


def classify_trailing_reason(class_name: str, remaining: int) -> DiagnosticReason:
    """Map export trailing-bytes context to a closed reason value."""
    if class_name in _BULK_CLASSES:
        return "bulk_expected"
    if any(class_name.startswith(p) or class_name == p for p in _EDITOR_ONLY_PREFIXES):
        return "editor_only"
    if class_name in _KNOWN_UNIMPLEMENTED_CLASSES or any(
        class_name.startswith(p) for p in _KNOWN_UNIMPLEMENTED_PREFIXES
    ):
        return "known_unimplemented"
    return "unexpected"
```

Adjust edge: `Function` prefix must not swallow `FontFace` — FontFace is checked first. `Blueprint` prefix matches `Blueprint` and `BlueprintGeneratedClass`.

- [ ] **Step 4: Wire emission site**

In `src/uasset_read/parsers/legacy_reader.py` replace the trailing `_diag(...)` call (~872):

```python
from ..models.diagnostics import classify_trailing_reason  # add near top if not present

diagnostics.append(
    _diag(
        "EXPORT_TRAILING_BYTES_UNCONSUMED",
        (
            f"Export {i} ({obj.name}) leaves {remaining} undecoded "
            f"bytes after the tagged properties (class {cn})"
        ),
        "objects.export",
        object_id=obj.id,
        reason=classify_trailing_reason(cn, remaining),
    )
)
```

Confirm `_diag` is `make_diagnostic` alias (already imported as `_diag`); Task 2 added `reason=` to `make_diagnostic`.

- [ ] **Step 5: Run tests + one real sample**

Run:

```bash
python -m pytest tests/test_diagnostics_reason.py -q
python -c "from uasset_read.package import parse_package_document as p; d=p('tests/samples/FirstPerson_T_GridChecker_A.uasset'); print([(x.code, x.reason) for x in d.diagnostics])"
```

Expected: unit PASS; sample diagnostics that are trailing include `editor_only` for MetaData (and any other classified classes).

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/models/diagnostics.py src/uasset_read/parsers/legacy_reader.py tests/test_diagnostics_reason.py
git commit -m "feat: classify export trailing-byte diagnostics by reason"
```

---

### Task 5: Classify DataTable table diagnostics

**Files:**
- Modify: table diagnostic emit sites (search `TABLE_PAYLOAD_RESIDUE`, `TABLE_ROWS_TRUNCATED` under `src/uasset_read/parsers/`)
- Test: `tests/test_diagnostics_reason.py` or extend sample-capability test

**Interfaces:**
- Produces: both TABLE_* diagnostics have `reason="conservative_complete"`

- [ ] **Step 1: Locate emit sites**

Run: `rg "TABLE_PAYLOAD_RESIDUE|TABLE_ROWS_TRUNCATED" src/uasset_read`

Record file:line for the plan implementer.

- [ ] **Step 2: Write failing test**

```python
def test_datatable_table_diagnostics_marked_conservative_complete():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/FirstPerson_DT_WeaponList.uasset")
    table_diags = [
        d for d in doc.diagnostics if d.code in {"TABLE_PAYLOAD_RESIDUE", "TABLE_ROWS_TRUNCATED"}
    ]
    # Fixture may or may not emit both; assert every emitted TABLE_* is classified.
    assert all(d.reason == "conservative_complete" for d in table_diags)
    # At least ensure helper path: if fixture is clean, the assertion is vacuous but still
    # documents the contract for fixtures that do emit (e.g. inventory DT in external sweep).
    if not table_diags:
        # Force one synthetic check that make_diagnostic can carry the reason.
        from uasset_read.models.diagnostics import make_diagnostic

        d = make_diagnostic("TABLE_ROWS_TRUNCATED", "m", "payload.table", reason="conservative_complete")
        assert d.reason == "conservative_complete"
```

Prefer a tracked fixture that actually emits TABLE_* if one exists; otherwise keep synthetic + wiring tests.

- [ ] **Step 3: Implement**

At each TABLE_* emit site pass `reason="conservative_complete"` (use `make_diagnostic`/`_diag` consistently with the local helper).

- [ ] **Step 4: Run**

Run: `python -m pytest tests/test_diagnostics_reason.py tests/test_samples.py -q -k "DataTable or table or reason"`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -u src/uasset_read tests/test_diagnostics_reason.py
git commit -m "feat: mark TABLE_* diagnostics as conservative_complete"
```

---

### Task 6: Seed `quality_baseline.json` + gate helper

**Files:**
- Create: `tests/samples/quality_baseline.json`
- Create: `tools/gen_quality_baseline.py`
- Modify: `tests/test_samples.py` (add baseline gate test near other sample gates)
- Test: same file

**Interfaces:**
- Consumes: `parse_package_document`, schema validation patterns already in `test_samples.py`
- Produces:
  - baseline schema: `{ "version": 1, "samples": { "<name>": { "depth": "asset", "forbidden_codes": [...], "max_by_code_reason": { "<code>": { "reason_or_": { "max": N } } } } } }`
  - helper `tests/test_samples.py::_assert_quality_baseline(doc, name)` used by a parametrized test over baseline keys

- [ ] **Step 1: Write generator (throwaway-friendly but shipping under tools/)**

Create `tools/gen_quality_baseline.py`:

```python
"""Generate tests/samples/quality_baseline.json from tracked fixtures.

Usage (from repo root):
  python tools/gen_quality_baseline.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from uasset_read.package import parse_package_document

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "tests" / "samples"
OUT = SAMPLES / "quality_baseline.json"

SEED = [
    "FirstPerson_DT_WeaponList.uasset",
    "FirstPerson_T_GridChecker_A.uasset",
    "FirstPerson_BS_Idle_Walk_Run.uasset",
    "ALS_Mannequin_Skeleton.uasset",
    "BP_CombatCharacter.uasset",
]


def main() -> None:
    samples: dict[str, object] = {}
    for name in SEED:
        path = SAMPLES / name
        doc = parse_package_document(str(path), depth="asset")
        counts: Counter[tuple[str, str | None]] = Counter()
        for d in doc.diagnostics:
            counts[(d.code, getattr(d, "reason", None))] += 1
        max_by: dict[str, dict[str, dict[str, int]]] = {}
        for (code, reason), n in sorted(counts.items()):
            key = reason or "_"
            max_by.setdefault(code, {})[key] = {"max": n}
        samples[name] = {
            "depth": "asset",
            "forbidden_codes": ["EXPORT_PROPERTY_PARSE_FAILED", "HANDLER_FAILURE"],
            "max_by_code_reason": max_by,
        }
        print(f"{name}: {sum(counts.values())} diagnostics")

    OUT.write_text(json.dumps({"version": 1, "samples": samples}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate baseline**

Run: `python tools/gen_quality_baseline.py`  
Expected: creates `tests/samples/quality_baseline.json` with the five seeds.

- [ ] **Step 3: Write failing gate test**

In `tests/test_samples.py` add:

```python
QUALITY_BASELINE = json.loads((SAMPLES / "quality_baseline.json").read_text(encoding="utf-8"))


def _assert_quality_baseline(doc, name: str) -> None:
    entry = QUALITY_BASELINE["samples"][name]
    codes = [d.code for d in doc.diagnostics]
    for forbidden in entry.get("forbidden_codes", []):
        assert forbidden not in codes, f"{name}: forbidden diagnostic {forbidden}"

    def _count(code: str, reason: str | None) -> int:
        return sum(
            1
            for d in doc.diagnostics
            if d.code == code and getattr(d, "reason", None) == reason
        )

    for code, by_reason in entry.get("max_by_code_reason", {}).items():
        for reason_key, rule in by_reason.items():
            reason = None if reason_key == "_" else reason_key
            actual = _count(code, reason)
            assert actual <= rule["max"], (
                f"{name}: {code}/{reason_key} count {actual} > baseline max {rule['max']}"
            )


@pytest.mark.parametrize("sample_name", sorted(QUALITY_BASELINE["samples"]))
def test_quality_baseline_diagnostics(sample_name):
    from uasset_read.package import parse_package_document

    doc = parse_package_document(str(SAMPLES / sample_name), depth="asset")
    page = project_document(doc)
    jsonschema.validate(page, SCHEMA)
    _assert_quality_baseline(doc, sample_name)
```

If `project_document` is not already imported in `test_samples.py`, follow an existing sample test that validates schema (around line 583) and reuse that import pattern.

- [ ] **Step 4: Run baseline gate**

Run: `python -m pytest tests/test_samples.py::test_quality_baseline_diagnostics -v`  
Expected: PASS on seed fixtures.

- [ ] **Step 5: Intentional break check (manual)**

Temporarily raise a seed’s trailing max to 0, run the one test, expect FAIL, restore file, PASS again.

- [ ] **Step 6: Commit**

```bash
git add tests/samples/quality_baseline.json tools/gen_quality_baseline.py tests/test_samples.py
git commit -m "test: add quality baseline gate for seed sample fixtures"
```

---

### Task 7: End-to-end reason visibility on a blueprint fixture

**Files:**
- Test only: `tests/test_diagnostics_reason.py` or `tests/test_samples.py`

**Interfaces:**
- Consumes: Tasks 2–6
- Produces: assertion that `BP_CombatCharacter` trailing/recovery diagnostics, when present, carry non-null `reason` **or** are explicitly allowed as unset during transition — **choose unset-illegal for trailing** after Task 4:

- [ ] **Step 1: Write test**

```python
def test_bp_combat_character_trailing_diagnostics_carry_reason():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/BP_CombatCharacter.uasset", depth="asset")
    trailing = [d for d in doc.diagnostics if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED"]
    assert trailing, "expected trailing diagnostics on this fixture"
    assert all(d.reason is not None for d in trailing)
    assert {"editor_only", "bulk_expected", "known_unimplemented", "unexpected"} & {
        d.reason for d in trailing
    }
```

- [ ] **Step 2: Run**

Run: `python -m pytest tests/test_diagnostics_reason.py::test_bp_combat_character_trailing_diagnostics_carry_reason -v`  
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_diagnostics_reason.py
git commit -m "test: require trailing reason on BP_CombatCharacter fixture"
```

---

### Task 8: Full local verification + changelog note

**Files:**
- Modify: `docs/release-notes/changelog.md` (Unreleased section if present; else add brief note under current)

- [ ] **Step 1: Run broader suite**

Run: `python -m pytest -q tests/test_diagnostics_reason.py tests/test_core.py tests/test_samples.py`  
Expected: PASS. If wall-clock is long, at minimum run diagnostics_reason + core + quality baseline tests.

- [ ] **Step 2: Schema validation spot-check**

Run existing sample validation path (covered in Task 6 gate). No extra schema file copies.

- [ ] **Step 3: Changelog**

Add under Unreleased / next version:

```markdown
- Diagnostics: optional `reason` classification (`bulk_expected`, `editor_only`, `known_unimplemented`, `recovered_corruption`, `conservative_complete`, `unexpected`) on `Diagnostic`; trailing-bytes and recovery sites populate it. Sample tests gain `tests/samples/quality_baseline.json` gate.
```

- [ ] **Step 4: Commit**

```bash
git add docs/release-notes/changelog.md
git commit -m "docs: note Diagnostic.reason and quality baseline gate"
```

---

## Out of scope — follow-up plans (do not implement in this plan)

| follow-up | depends on |
|-----------|------------|
| Niagara node-body decode | reason=`known_unimplemented` volume becomes measurable |
| BP/GA name_index root cause | `recovered_corruption` forbidden-list tightening |
| DataTable residue / row_names | TABLE_* semantics fix + baseline tighten |
| RefSkeleton real hierarchy | Skeleton trailing size drop |
| Optional CI job for multi-MB ALS_AnimBP | opt-in baseline entry — implemented 2026-09-16 (`docs/plans/2026-09-16-als-animbp-opt-in-baseline.md`, env `UASSET_QUALITY_OPT_IN=1`) |
| ALS_AnimBP `name_index_out_of_range` at offset 4497945 (export:281, raw index 2560 vs name table 1582) | fixed 2026-09-21 — `CachedPoseIndices` added to tagged fallback (`docs/plans/2026-09-16-als-name-index-and-optin-docs.md`); moderate out-of-range cluster, not the external 1e9 garbage cluster |
| External sweep `BP_Player` `name_index` cluster unverified against tracked fixtures | needs fixture-level confirmation |

Each follow-up gets its own plan with red baseline → fix → tighten.

---

## Self-review notes (plan author)

1. **Spec coverage:** design goals 1–3 map to Tasks 2–6; deep parser fixes are follow-up plans only.  
2. **Placeholders:** classifier sets, seed fixture names, and baseline JSON shape are concrete.  
3. **Type consistency:** `reason=` keyword on `make_diagnostic` and `_record_structured_diagnostic`; `classify_trailing_reason` returns `DiagnosticReason`; baseline keys use `"_"` for unset reason.  
4. **Schema:** `$defs.Diagnostic.additionalProperties: false` requires the Task 2 schema edit in the same change as the model field.  
5. **Scope:** one shippable subsystem (reason + gates).

---

## Execution handoff

After this plan is saved, choose:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute in-session with checkpoints
