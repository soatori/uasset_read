# ALS AnimBP Name-Index Residual + Opt-In Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the last tracked `name_index_out_of_range` on `ALS_AnimBP.uasset` by teaching the tagged-struct fallback about `CachedPoseIndices`, then document how to run the opt-in quality baseline (`UASSET_QUALITY_OPT_IN=1`).

**Architecture:** MapProperty values dispatch StructProperty with `tag.size=0`. `CachedPoseIndices` is a tagged FStructFallback payload but is not in `_TAGGED_FALLBACK_STRUCTS`, so `parse_struct_property` returns an empty opaque value **without consuming bytes**, desynchronizing subsequent map keys and emitting `name_index_out_of_range`. Adding `CachedPoseIndices` to that set restores the inner `OrderedSavedPoseNodeIndices` array walk (verified: 9 valid keys, map end exact, OOR=0). Docs task only adds user-facing instructions for the existing opt-in env flag — no CI workflow changes.

**Tech Stack:** Python 3.10+, stdlib, existing `uasset_read` package, pytest.

**Spec / evidence:**
- Roadmap decision (2026-09-16 brainstorming): next batch = A1 (docs only) + A2 (ALS name_index root cause); success = ALS `name_index_out_of_range == 0` + regenerate opt-in baseline.
- Live root cause: export:281 `OrderedSavedPoseIndicesMap` @ 4497816; map value region [4497889, 4498538); OOR raw index 2560 @ 4497945.
- Monkeypatch proof: `_TAGGED_FALLBACK_STRUCTS |= {"CachedPoseIndices"}` → 9 map entries with real keys (`AnimGraph`, `FootIK`, …), `OrderedSavedPoseNodeIndices` int arrays populated, **0** `name_index_out_of_range`, tell == map value end.
- Prior plan residual: `docs/plans/2026-09-15-parser-quality-system.md` ALS AnimBP name_index row; opt-in baseline from `docs/plans/2026-09-16-als-animbp-opt-in-baseline.md`.

## Global Constraints

- Python 3.10+; no new runtime dependencies.
- Do **not** change `format_version`, Diagnostic codes, or reason enums.
- Do **not** change `read_name` recovery policy (`#339` garbage-high-bit gate stays).
- Default quality gate must still exclude ALS (`opt_in: true` remains; no CI workflow edits).
- After the parser fix, **regenerate** `tests/samples/quality_baseline.json` via `tools/gen_quality_baseline.py` so ALS drops the `name_index_out_of_range` ceiling.
- TDD: failing tests before implementation for each behavior-bearing task.
- Prefer editing existing files; no new package.
- Do not expand scope to `AnimNodeData` / `BakedAnimationStateMachine` empty-field semantics (separate residual).

---

## Design brief

### A2 — Root cause

| Fact | Value |
|------|-------|
| Fixture | `tests/samples/ALS_AnimBP.uasset` |
| Object | `export:281` `ALS_AnimBP_C` / `AnimBlueprintGeneratedClass` |
| Property | `OrderedSavedPoseIndicesMap` (MapProperty: NameProperty → StructProperty `CachedPoseIndices`) |
| Failure mode | `_dispatch_value_parse` builds `PropertyTag(size=0, struct_type="CachedPoseIndices")`; not in `_TAGGED_FALLBACK_STRUCTS`; opaque return with **zero bytes consumed** |
| Symptom | Subsequent map keys read mid-struct; one key hits index 2560 vs name table 1582 → `name_index_out_of_range` / `recovered_corruption` |
| Fix | Append `"CachedPoseIndices"` to `_TAGGED_FALLBACK_STRUCTS` in `src/uasset_read/parsers/property_types.py` |

Verified intended parse (post-fix): keys `AnimGraph`, `FootIK`, `HandIK`, `AimOffsetBehaviors`, `LayerBleding`, `BaseLayer`, `OverlayLayer`, `(N) CycleBlending`, `(CLF) CycleBlending` with `OrderedSavedPoseNodeIndices` lists.

### A1 — Docs only

Document that the quality baseline path can opt into the 10MB AnimBP fixture:

```powershell
$env:UASSET_QUALITY_OPT_IN="1"
python -m pytest tests/test_samples.py -k quality_baseline
```

Do **not** edit `.github/workflows/ci.yml` (product decision: docs convention only).

### Success criteria

1. Unit/integration: `parse_package_document(ALS_AnimBP, depth="asset")` has **0** `name_index_out_of_range`.
2. Integration: export:281 `OrderedSavedPoseIndicesMap` has ≥9 entries whose keys are known name-table strings (include `AnimGraph`).
3. Regenerated `quality_baseline.json`: ALS entry has **no** `name_index_out_of_range` key; still `opt_in: true`; trailing ceilings may stay as measured (regen, do not hand-edit).
4. Default `pytest tests/test_samples.py -k quality_baseline` still excludes ALS; opt-in run includes ALS and passes.
5. README (or testing docs) documents `UASSET_QUALITY_OPT_IN=1`.
6. No `src/` changes beyond the one-line (or few-line) tagged-fallback list addition.

### Non-goals

- Semantics of `AnimNodeData` (933 empty structs) / `BakedAnimationStateMachine` empty fields.
- CI matrix job.
- Niagara / RefSkeleton / DataTable.
- Tightening ALS trailing ceilings below measured values.

---

## File map

| path | responsibility |
|------|----------------|
| `src/uasset_read/parsers/property_types.py` | `_TAGGED_FALLBACK_STRUCTS` gains `CachedPoseIndices` |
| `tests/test_diagnostics_reason.py` (or small new assert block) | ALS zero OOR + map keys |
| `tests/samples/quality_baseline.json` | regenerated via generator |
| `README.md` | A1 opt-in command |
| `docs/release-notes/changelog.md` | Unreleased note |
| `docs/plans/2026-09-15-parser-quality-system.md` | optional residual row note → implemented |

---

## Global test commands

```powershell
$env:PYTHONPATH="src"
python -m pytest -q tests/test_diagnostics_reason.py tests/test_samples.py -k "ALS or quality_baseline or name_index or OrderedSaved"
Remove-Item Env:UASSET_QUALITY_OPT_IN -ErrorAction SilentlyContinue
$env:UASSET_QUALITY_OPT_IN="1"
python -m pytest -q tests/test_samples.py -k quality_baseline
```

Use system Python with pytest (e.g. `"C:\Program Files\Python314\python.exe"`).

---

### Task 1: Failing tests — ALS name_index and OrderedSavedPoseIndicesMap keys

**Files:**
- Modify: `tests/test_diagnostics_reason.py`

**Interfaces:**
- Consumes: `parse_package_document`, fixture `tests/samples/ALS_AnimBP.uasset`
- Produces: integration assertions for Task 2 and Task 3

- [ ] **Step 1: Write failing tests**

Append to `tests/test_diagnostics_reason.py`:

```python
def test_als_animbp_has_no_name_index_out_of_range():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/ALS_AnimBP.uasset", depth="asset")
    codes = [d.code for d in doc.diagnostics]
    assert "name_index_out_of_range" not in codes, (
        [d.message for d in doc.diagnostics if d.code == "name_index_out_of_range"]
    )


def test_als_animbp_ordered_saved_pose_indices_map_keys():
    from uasset_read.package import parse_package_document

    doc = parse_package_document("tests/samples/ALS_AnimBP.uasset", depth="asset")
    export = next(o for o in doc.objects if o.id == "export:281")
    prop = (export.properties or {}).get("OrderedSavedPoseIndicesMap")
    assert prop is not None, "OrderedSavedPoseIndicesMap missing on ALS_AnimBP_C"
    # MapProperty normalizes to a list of {key, value}
    entries = prop["value"] if isinstance(prop, dict) and "value" in prop else prop
    assert isinstance(entries, list) and len(entries) >= 9, entries
    keys = [e.get("key") for e in entries if isinstance(e, dict)]
    assert "AnimGraph" in keys, keys
    # At least one entry should expose OrderedSavedPoseNodeIndices after the fix
    sample = next(e for e in entries if e.get("key") == "AnimGraph")
    value = sample.get("value")
    fields = value.get("fields") if isinstance(value, dict) else getattr(value, "fields", None)
    assert fields is not None, value
    assert "OrderedSavedPoseNodeIndices" in fields, fields
```

- [ ] **Step 2: Run to verify FAIL**

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_diagnostics_reason.py -k "als_animbp" -v
```

Expected: both tests FAIL (`name_index_out_of_range` present; map keys garbage / missing `OrderedSavedPoseNodeIndices` fields).

- [ ] **Step 3: Commit tests only (optional RED commit)**

```bash
git add tests/test_diagnostics_reason.py
git commit -m "test: pin ALS AnimBP name_index residual and pose map keys"
```

---

### Task 2: Add `CachedPoseIndices` to tagged fallback

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py` (`_TAGGED_FALLBACK_STRUCTS`)

**Interfaces:**
- Consumes: Task 1 tests
- Produces: map values consume tagged struct body; OOR disappears

- [ ] **Step 1: Locate `_TAGGED_FALLBACK_STRUCTS`**

Open `src/uasset_read/parsers/property_types.py` near the set that already contains `"BPVariableDescription"`, `"EdGraphPinType"`, `"AnimNotifyTrack"`, etc.

- [ ] **Step 2: Add one entry with a short comment**

```python
    # AnimBlueprintGeneratedClass::OrderedSavedPoseIndicesMap values
    # (FCachedPoseIndices is tagged FStructFallback: OrderedSavedPoseNodeIndices + None)
    "CachedPoseIndices",
```

Insert alphabetically or next to other Anim* entries (`AnimNotifyTrack` is a good neighbor). Do **not** remove any existing set members.

- [ ] **Step 3: Run Task 1 tests to green**

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_diagnostics_reason.py -k "als_animbp" -v
```

Expected: PASS.

- [ ] **Step 4: Broader smoke**

```powershell
$env:PYTHONPATH="src"
python -m pytest -q tests/test_core.py tests/test_diagnostics_reason.py
```

Expected: PASS (no parser regressions from a one-name fallback addition).

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/parsers/property_types.py tests/test_diagnostics_reason.py
git commit -m "fix: parse CachedPoseIndices as tagged struct to stop ALS name_index OOR"
```

---

### Task 3: Regenerate quality baseline (drop ALS name_index ceiling)

**Files:**
- Modify: `tests/samples/quality_baseline.json` (via generator only)

**Interfaces:**
- Consumes: Task 2 parse output; `tools/gen_quality_baseline.py` + `OPT_IN_SEED` from prior opt-in plan
- Produces: ALS entry without `name_index_out_of_range`

- [ ] **Step 1: Regenerate**

```powershell
$env:PYTHONPATH="src"
python tools/gen_quality_baseline.py
```

- [ ] **Step 2: Inspect ALS entry**

In `tests/samples/quality_baseline.json` under `ALS_AnimBP.uasset`:

- `"opt_in": true` still present
- **No** `"name_index_out_of_range"` key
- Trailing keys only (`EXPORT_TRAILING_BYTES_UNCONSUMED` reasons) — ceilings may differ slightly from 1251/577/3 if the fix changes trailing counts; **accept generator output** and note deltas in the report (do not hand-edit numbers)

- [ ] **Step 3: Default gate excludes ALS; opt-in gate includes and passes**

```powershell
$env:PYTHONPATH="src"
Remove-Item Env:UASSET_QUALITY_OPT_IN -ErrorAction SilentlyContinue
python -m pytest -q tests/test_samples.py -k quality_baseline --collect-only
# expected: no ALS_AnimBP id

$env:UASSET_QUALITY_OPT_IN="1"
python -m pytest -q tests/test_samples.py -k quality_baseline -v
# expected: includes ALS_AnimBP.uasset; PASS
```

- [ ] **Step 4: Commit**

```bash
git add tests/samples/quality_baseline.json
git commit -m "test: drop ALS_AnimBP name_index_out_of_range from quality baseline"
```

---

### Task 4: A1 — Document opt-in quality baseline (no CI edit)

**Files:**
- Modify: `README.md` (Testing section ~line 221)
- Optional same-commit: one sentence in `docs/reference/agent-dev-reference.md` if a Testing/QA subsection exists

**Interfaces:**
- Consumes: env flag already implemented in opt-in baseline work
- Produces: discoverable run instructions

- [ ] **Step 1: Add to README Testing section**

After the existing pytest lines, add:

```markdown
# Quality baseline (default seeds; skips large opt-in fixtures)
python -m pytest tests/test_samples.py -k quality_baseline

# Include ALS_AnimBP opt-in quality entry (~10MB; slower)
UASSET_QUALITY_OPT_IN=1 python -m pytest tests/test_samples.py -k quality_baseline
```

On Windows PowerShell, document the equivalent:

```powershell
$env:UASSET_QUALITY_OPT_IN="1"
python -m pytest tests/test_samples.py -k quality_baseline
```

Match the README’s existing shell style (if the file uses bash-style examples, show both or the style already used).

- [ ] **Step 2: Do not touch CI workflows**

Confirm `git status` shows no `.github/` changes.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document UASSET_QUALITY_OPT_IN quality baseline opt-in"
```

---

### Task 5: Changelog + residual row

**Files:**
- Modify: `docs/release-notes/changelog.md` (`### Improvements`)
- Modify: `docs/plans/2026-09-15-parser-quality-system.md` residual table row for ALS name_index (mark fixed)

- [ ] **Step 1: Changelog bullet**

```markdown
- Parser: `CachedPoseIndices` (AnimBlueprint `OrderedSavedPoseIndicesMap` values) is parsed as a tagged struct. Removes the residual `name_index_out_of_range` on `tests/samples/ALS_AnimBP.uasset`; quality opt-in baseline regenerated.
```

- [ ] **Step 2: Residual table**

Update the ALS_AnimBP name_index follow-up row so it records fixed-on date / this plan path (keep the row as history; do not delete the table).

- [ ] **Step 3: Commit**

```bash
git add docs/release-notes/changelog.md docs/plans/2026-09-15-parser-quality-system.md
git commit -m "docs: note CachedPoseIndices fix and ALS name_index residual close"
```

---

## Out of scope — follow-up plans

| follow-up | depends on |
|-----------|------------|
| AnimNodeData / BakedAnimationStateMachine semantic fill | separate evidence + plan |
| CI job for `UASSET_QUALITY_OPT_IN=1` | product revisit |
| Q2 RefSkeleton / DataTable / Niagara | portfolio phase 2 |

---

## Self-review notes (plan author)

1. **Spec coverage:** A2 (Tasks 1–3, 5) + A1 (Task 4) + baseline regen; no CI edit per decision.
2. **Placeholders:** concrete set member, exact fixture ids, exact map keys, regen commands; no TBD.
3. **Type consistency:** `entries` list of `{key, value}`; `StructValue.fields` / dict `fields`; generator API unchanged from opt-in plan.
4. **Scope:** one set-membership fix; residual AnimNodeData explicitly out.
5. **Risk:** tagged-fallback for this struct name is proven on the live fixture; other packages with a different `CachedPoseIndices` layout would be a new finding — success criteria are ALS-scoped.

---

## Execution handoff

1. **Subagent-Driven (recommended)**
2. **Inline Execution**
