# ALS_AnimBP Opt-In Quality Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: historical (executed 2026-09-16).** Deliverables landed on `dev-0.6.0` (`UASSET_QUALITY_OPT_IN` gate live in `tests/test_samples.py`); checkbox state was not maintained during execution. This file is execution evidence. Do not invoke SDD or rerun its commands unless the user explicitly names this file and requests a new replay.

**Goal:** Add `ALS_AnimBP.uasset` (10MB, ~4.2s parse) to `tests/samples/quality_baseline.json` behind an opt-in gate so default CI stays fast while large AnimBP regressions remain measurable.

**Architecture:** Baseline entries gain an optional `"opt_in": true` flag. The generator always writes both default seeds and the opt-in seed (marked). `test_quality_baseline_diagnostics` keeps its parametrize over baseline keys but **skips** `opt_in` samples unless `UASSET_QUALITY_OPT_IN=1` is set in the environment. No parser changes; no change to default seed list used for non-opt-in ceilings.

**Tech Stack:** Python 3.10+, stdlib, existing `uasset_read` package, pytest, JSON baseline.

**Spec / evidence:**
- Portfolio: Q-ABP / “ALS_AnimBP opt-in baseline” (quality follow-up table).
- Plan follow-up note: `docs/plans/2026-09-15-parser-quality-system.md` (multi-MB ALS_AnimBP opt-in).
- Measured on 2026-09-16 (`depth=asset`, `PYTHONPATH=src`): 1832 diagnostics in ~4.2s —
  - `EXPORT_TRAILING_BYTES_UNCONSUMED` / `known_unimplemented`: **1251**
  - `EXPORT_TRAILING_BYTES_UNCONSUMED` / `editor_only`: **577**
  - `EXPORT_TRAILING_BYTES_UNCONSUMED` / `unexpected`: **3**
  - `name_index_out_of_range` / `recovered_corruption`: **1**
- Fixture path: `tests/samples/ALS_AnimBP.uasset` (already tracked; not new acquisition).

## Global Constraints

- Python 3.10+; no new runtime dependencies.
- Do **not** put `ALS_AnimBP.uasset` on the default (non-opt-in) quality gate path.
- Do **not** change `format_version`, Diagnostic codes, or reason enums.
- Do **not** change parser / `read_name` behavior (the one `name_index_out_of_range` stays a pinned residual, not fixed here).
- Baseline counts for ALS must be regenerated from the live fixture via `tools/gen_quality_baseline.py`, not hand-invented beyond the measured snapshot above.
- TDD: write failing tests before implementation for each behavior-bearing task.
- Prefer editing existing files; no new package.
- Default suite runtime must not absorb the ~4.2s ALS parse unless the env flag is set.

---

## Design brief

### Why opt-in only

`ALS_AnimBP` is ~10MB / 3395 exports. Default quality seeds finish quickly; adding this fixture to the unconditional parametrize would slow every `tests/test_samples.py` quality run. The quality system’s original plan already called for an **opt-in** entry.

### Baseline entry shape

Same keys as other seeds, plus `"opt_in": true`:

```json
"ALS_AnimBP.uasset": {
  "depth": "asset",
  "forbidden_codes": ["EXPORT_PROPERTY_PARSE_FAILED", "HANDLER_FAILURE"],
  "forbid_unlisted": true,
  "opt_in": true,
  "max_by_code_reason": {
    "EXPORT_TRAILING_BYTES_UNCONSUMED": {
      "editor_only": { "max": 577 },
      "known_unimplemented": { "max": 1251 },
      "unexpected": { "max": 3 }
    },
    "name_index_out_of_range": {
      "recovered_corruption": { "max": 1 }
    }
  }
}
```

Exact ceilings come from the generator after Task 3; the numbers above are the measured snapshot and must match unless the generator produces a different (then-reviewed) count.

### Opt-in switch

- Environment variable: **`UASSET_QUALITY_OPT_IN`**
- Value **`"1"`** enables opt-in samples in the quality parametrize.
- Any other value / unset → skip opt-in samples (default).
- Do not invent a second switch (no pytest marker required for this plan).

### Success criteria

1. Default `pytest tests/test_samples.py -k quality_baseline` does **not** parametrize `ALS_AnimBP.uasset`.
2. `UASSET_QUALITY_OPT_IN=1 pytest tests/test_samples.py -k quality_baseline` **does** run `ALS_AnimBP` and passes against the regenerated ceilings.
3. Generator writes `opt_in: true` only for the ALS entry (default seeds unchanged in meaning).
4. Fail-path unit for opt-in skip is covered (see Task 1 tests).
5. Changelog documents the opt-in gate.
6. No parser file changes.

### Non-goals

- Fixing ALS `name_index_out_of_range` (residual).
- Tightening trailing ceilings below measured counts.
- CI job authorship (documenting the env var is enough; wiring a CI matrix row is out of scope unless already trivial).
- Adding other large fixtures (`ALS_AnimBP` decode depth, Niagara, etc.).

---

## File map

| path | responsibility |
|------|----------------|
| `tools/gen_quality_baseline.py` | `OPT_IN_SEED` list; write `opt_in: true` |
| `tests/samples/quality_baseline.json` | regenerated ALS entry with `opt_in` |
| `tests/test_samples.py` | filter opt-in samples; skip unless env flag |
| `docs/release-notes/changelog.md` | Unreleased note |

---

## Global test commands

Default quality gate (must stay fast — no ALS):

```powershell
$env:PYTHONPATH="src"
python -m pytest -q tests/test_samples.py -k "quality_baseline"
```

Opt-in gate (includes ALS, ~seconds longer):

```powershell
$env:PYTHONPATH="src"
$env:UASSET_QUALITY_OPT_IN="1"
python -m pytest -q tests/test_samples.py -k "quality_baseline"
```

Clear the flag for other runs:

```powershell
Remove-Item Env:UASSET_QUALITY_OPT_IN -ErrorAction SilentlyContinue
```

Use the machine Python 3.10+ that has pytest (e.g. `"C:\Program Files\Python314\python.exe"`).

---

### Task 1: Opt-in filter + skip logic (TDD)

**Files:**
- Modify: `tests/test_samples.py` (near `QUALITY_BASELINE` load and `test_quality_baseline_diagnostics`)

**Interfaces:**
- Consumes: `QUALITY_BASELINE` already loaded from JSON; env `UASSET_QUALITY_OPT_IN`
- Produces:
  - `def _quality_baseline_sample_names(include_opt_in: bool) -> list[str]`
  - `test_quality_baseline_diagnostics` parametrized only over non-opt-in names when flag unset

- [ ] **Step 1: Write failing unit tests for the filter helper**

Append to `tests/test_samples.py` (module level, near the quality baseline helpers):

```python
def test_quality_baseline_sample_names_excludes_opt_in_by_default():
    baseline = {
        "samples": {
            "A.uasset": {"opt_in": False},
            "B.uasset": {"opt_in": True},
            "C.uasset": {},
        }
    }
    names = _quality_baseline_sample_names(
        False,
        samples=baseline["samples"],
    )
    assert names == ["A.uasset", "C.uasset"]


def test_quality_baseline_sample_names_includes_opt_in_when_enabled():
    baseline = {
        "samples": {
            "A.uasset": {"opt_in": False},
            "B.uasset": {"opt_in": True},
        }
    }
    names = _quality_baseline_sample_names(
        True,
        samples=baseline["samples"],
    )
    assert names == ["A.uasset", "B.uasset"]


def test_quality_baseline_opt_in_env_flag(monkeypatch):
    monkeypatch.setenv("UASSET_QUALITY_OPT_IN", "1")
    assert _quality_baseline_include_opt_in() is True
    monkeypatch.delenv("UASSET_QUALITY_OPT_IN", raising=False)
    assert _quality_baseline_include_opt_in() is False
```

- [ ] **Step 2: Run to verify fail**

Run:

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_samples.py -k "quality_baseline_sample_names or quality_baseline_opt_in_env" -v
```

Expected: FAIL (`ImportError` / `NameError` for the helpers).

- [ ] **Step 3: Implement helpers and wire parametrize**

In `tests/test_samples.py` add:

```python
def _quality_baseline_include_opt_in() -> bool:
    return os.environ.get("UASSET_QUALITY_OPT_IN") == "1"


def _quality_baseline_sample_names(
    include_opt_in: bool,
    samples: dict | None = None,
) -> list[str]:
    src = QUALITY_BASELINE["samples"] if samples is None else samples
    names = []
    for name, entry in src.items():
        if entry.get("opt_in") and not include_opt_in:
            continue
        names.append(name)
    return sorted(names)
```

Ensure `import os` exists at the top of the file (add if missing).

Replace the quality diagnostics parametrize:

```python
@pytest.mark.parametrize(
    "sample_name",
    _quality_baseline_sample_names(_quality_baseline_include_opt_in()),
)
def test_quality_baseline_diagnostics(sample_name):
    from uasset_read.package import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(str(SAMPLES / sample_name), depth="asset")
    page = project_document(doc)
    jsonschema.validate(page, SCHEMA)
    _assert_quality_baseline(doc, sample_name)
```

- [ ] **Step 4: Run unit tests to green**

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_samples.py -k "quality_baseline_sample_names or quality_baseline_opt_in_env or quality_baseline_diagnostics" -q
```

Expected: PASS. Default parametrize still has the original 5 seeds (none are `opt_in` yet).

- [ ] **Step 5: Commit**

```bash
git add tests/test_samples.py
git commit -m "test: skip opt-in quality baseline samples unless UASSET_QUALITY_OPT_IN=1"
```

---

### Task 2: Generator writes opt-in seed with `opt_in: true`

**Files:**
- Modify: `tools/gen_quality_baseline.py`

**Interfaces:**
- Consumes: Task 1’s meaning of `opt_in` (test filter already respects the flag)
- Produces: `OPT_IN_SEED = ["ALS_AnimBP.uasset"]`; each sample entry may include `"opt_in": true`

- [ ] **Step 1: Write a failing generator unit-style test (optional lightweight)**

Prefer a small pure-function extract so the flag is testable without re-parsing:

Refactor `tools/gen_quality_baseline.py` to expose:

```python
def build_sample_entry(doc, name: str, *, opt_in: bool = False) -> dict:
    counts: Counter[tuple[str, str | None]] = Counter()
    for d in doc.diagnostics:
        counts[(d.code, d.reason)] += 1
    max_by: dict[str, dict[str, dict[str, int]]] = {}
    for (code, reason), n in sorted(counts.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        key = reason or "_"
        max_by.setdefault(code, {})[key] = {"max": n}
    entry = {
        "depth": "asset",
        "forbidden_codes": ["EXPORT_PROPERTY_PARSE_FAILED", "HANDLER_FAILURE"],
        "forbid_unlisted": True,
        "max_by_code_reason": max_by,
    }
    if opt_in:
        entry["opt_in"] = True
    if name == "FirstPerson_DT_WeaponList.uasset":
        entry["max_total_diagnostics"] = 0
    return entry
```

Add `tests/test_quality_baseline_generator.py`:

```python
from types import SimpleNamespace

from tools.gen_quality_baseline import build_sample_entry


def test_build_sample_entry_marks_opt_in():
    doc = SimpleNamespace(diagnostics=[])
    entry = build_sample_entry(doc, "ALS_AnimBP.uasset", opt_in=True)
    assert entry["opt_in"] is True
    entry2 = build_sample_entry(doc, "BP_CombatCharacter.uasset", opt_in=False)
    assert "opt_in" not in entry2
```

Ensure `tools` is importable: either `tools/__init__.py` if missing, or adjust sys.path in the test the same way other repo tests import package code (prefer a tiny `sys.path` insert of repo root consistent with existing tests if needed). If the repo does not treat `tools` as a package, import via `importlib.util.spec_from_file_location` instead — pick one mechanism and use it consistently in the test.

- [ ] **Step 2: Verify fail**

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_quality_baseline_generator.py -v
```

Expected: FAIL until `build_sample_entry` exists / is exported.

- [ ] **Step 3: Implement generator changes**

In `tools/gen_quality_baseline.py`:

```python
SEED = [
    "FirstPerson_DT_WeaponList.uasset",
    "FirstPerson_T_GridChecker_A.uasset",
    "FirstPerson_BS_Idle_Walk_Run.uasset",
    "ALS_Mannequin_Skeleton.uasset",
    "BP_CombatCharacter.uasset",
]

OPT_IN_SEED = [
    "ALS_AnimBP.uasset",
]


def main() -> None:
    samples: dict[str, object] = {}
    for name in SEED:
        path = SAMPLES / name
        doc = parse_package_document(str(path), depth="asset")
        samples[name] = build_sample_entry(doc, name, opt_in=False)
        print(f"{name}: {sum(1 for _ in samples[name]['max_by_code_reason'].values())} codes")
    for name in OPT_IN_SEED:
        path = SAMPLES / name
        doc = parse_package_document(str(path), depth="asset")
        samples[name] = build_sample_entry(doc, name, opt_in=True)
        print(f"{name} (opt-in): diagnostics={len(doc.diagnostics)}")
    OUT.write_text(json.dumps({"version": 1, "samples": samples}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
```

(Remove the old inline counter loop; keep print format close enough that operators can still see counts.)

- [ ] **Step 4: Run generator unit test green**

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_quality_baseline_generator.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/gen_quality_baseline.py tests/test_quality_baseline_generator.py
git commit -m "feat: support opt-in seeds in quality baseline generator"
```

---

### Task 3: Regenerate baseline including ALS_AnimBP

**Files:**
- Modify: `tests/samples/quality_baseline.json` (via generator)

**Interfaces:**
- Consumes: Task 2 generator
- Produces: ALS entry with `opt_in: true` and measured ceilings

- [ ] **Step 1: Regenerate**

```powershell
$env:PYTHONPATH="src"
python tools/gen_quality_baseline.py
```

- [ ] **Step 2: Inspect ALS entry**

Expected in `quality_baseline.json`:

- `ALS_AnimBP.uasset` has `"opt_in": true`
- `forbid_unlisted`: true
- `EXPORT_TRAILING_BYTES_UNCONSUMED`: `known_unimplemented` max **1251**, `editor_only` max **577**, `unexpected` max **3** (or exactly what the generator printed if slightly different — if different, stop and investigate before committing)
- `name_index_out_of_range` / `recovered_corruption` max **1**
- No `max_total_diagnostics` on ALS
- Default five seeds unchanged in meaning (BP seed still without `fstring_all_null`)

- [ ] **Step 3: Default gate skips ALS**

```powershell
$env:PYTHONPATH="src"
Remove-Item Env:UASSET_QUALITY_OPT_IN -ErrorAction SilentlyContinue
python -m pytest tests/test_samples.py -k "quality_baseline_diagnostics" -q --collect-only
```

Expected: collected ids **do not** include `ALS_AnimBP`.

- [ ] **Step 4: Opt-in gate runs ALS and passes**

```powershell
$env:PYTHONPATH="src"
$env:UASSET_QUALITY_OPT_IN="1"
python -m pytest tests/test_samples.py -k "quality_baseline_diagnostics" -v
```

Expected: includes `ALS_AnimBP.uasset` id; PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/samples/quality_baseline.json
git commit -m "test: add ALS_AnimBP opt-in quality baseline entry"
```

---

### Task 4: Changelog + residual note (docs)

**Files:**
- Modify: `docs/release-notes/changelog.md` (`## [Unreleased]` → `### Improvements`)
- Modify (optional, preferred): residual row in `docs/plans/2026-09-15-parser-quality-system.md` follow-up table — mark ALS_AnimBP opt-in as done / point at this plan

**Interfaces:**
- Consumes: Tasks 1–3
- Produces: user-visible note

- [ ] **Step 1: Run broader verification**

```powershell
$env:PYTHONPATH="src"
Remove-Item Env:UASSET_QUALITY_OPT_IN -ErrorAction SilentlyContinue
python -m pytest -q tests/test_samples.py -k "quality_baseline" tests/test_quality_baseline_generator.py
```

Expected: PASS without ALS in the quality parametrize.

- [ ] **Step 2: Changelog bullet**

Under `### Improvements` in `docs/release-notes/changelog.md`:

```markdown
- Quality baseline: large fixture `ALS_AnimBP.uasset` (~10MB) is gated behind `UASSET_QUALITY_OPT_IN=1` (`"opt_in": true` in `quality_baseline.json`). Default sample quality tests stay fast; opt-in run pins known trailing/recovery ceilings for the AnimBP regression surface.
```

- [ ] **Step 3: Residual table update (small)**

In `docs/plans/2026-09-15-parser-quality-system.md` follow-up table, update the ALS_AnimBP row (or add a note under Out of scope) to:

```markdown
| Optional CI job for multi-MB ALS_AnimBP | opt-in baseline entry — implemented 2026-09-16 (`docs/plans/2026-09-16-als-animbp-opt-in-baseline.md`, env `UASSET_QUALITY_OPT_IN=1`) |
```

If the existing row only says “opt-in baseline entry”, replace the depends-on cell with the completed note; keep the row as historical follow-up.

- [ ] **Step 4: Commit**

```bash
git add docs/release-notes/changelog.md docs/plans/2026-09-15-parser-quality-system.md
git commit -m "docs: note ALS_AnimBP opt-in quality baseline gate"
```

---

## Out of scope — follow-up plans (do not implement here)

| follow-up | depends on |
|-----------|------------|
| ALS_AnimBP `name_index_out_of_range` (export:281, index 2560 vs 1582) | dedicated root-cause plan |
| CI workflow matrix row for `UASSET_QUALITY_OPT_IN=1` | product wants CI coverage of the flag |
| Tightening ALS unexpected trailing max (currently 3) | root-cause those three sites |
| Niagara / RefSkeleton / DataTable portfolio Q2–Q3 | separate plans |

---

## Self-review notes (plan author)

1. **Spec coverage:** opt-in flag, generator, regen, env gate, changelog → Tasks 1–4.
2. **Placeholders:** no TBD; measured ceilings listed; concrete code for helpers/generator/tests.
3. **Type consistency:** `_quality_baseline_sample_names(include_opt_in, samples=None) -> list[str]`; `build_sample_entry(doc, name, *, opt_in=False) -> dict`; JSON key `opt_in`.
4. **Scope:** gates only; zero parser edits.
5. **Runtime:** default path avoids ALS parse; opt-in path accepts ~4.2s.

---

## Execution handoff

After this plan is saved, choose:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
2. **Inline Execution** — execute in-session with checkpoints
