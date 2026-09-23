# Static UAsset v3 Closeout: Review, Merge, and Status Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: completed / historical (2026-09-21).** Controller review passed, the merge landed on `dev-0.6.0`, the post-merge suite passed, and all 23 task checkboxes are complete. This file is execution evidence. Do not invoke SDD or rerun its commands unless the user explicitly names this file and requests a new replay.

**Goal:** Finish the remaining closeout work for the complete static UAsset v3 delivery: controller whole-branch review of `sdd/static-uasset-finish`, merge that branch into `dev-0.6.0`, re-run the full suite on the merged branch, and update user-facing docs/README so documented claims match source+tests on `dev-0.6.0`.

**Architecture:** Tasks 1–12 of the static parsing/projection work are already implemented and green on execution branch `sdd/static-uasset-finish` (worktree `.worktrees/sdd-static-continue`). This plan does not reopen implementation. It (1) independently reviews that branch against the spec/AGENTS invariants, (2) lands the already-green commits on `dev-0.6.0`, (3) proves the merged tree with a full verification gate, then (4) updates README/spec/design index status only after source+tests support the claims on the user-facing branch.

**Tech Stack:** Git worktree merge (no force-push), Python 3.10+, existing stdlib implementation, `pytest`, `compileall`. No CUE4Parse/UAssetAPI/Unreal Editor runtime bridge.

**Spec:** `docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`

**Parent plan (Tasks 1–12 step source):** `docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md`

**Remaining implementation plan (R1–R6, already executed):** `docs/superpowers/plans/2026-09-21-remaining-static-uasset-v3-projection.md` (authoritative copy lives in the execution worktree)

**R6 evidence:** `.superpowers/sdd/2026-09-21-remaining-static-uasset-v3-projection/task-R6-report.md` on the execution branch — 23/23 checklist pass; full suite **442 passed**; `compileall` clean; HEAD `871ff296`.

## Historical Pre-Execution Snapshot (not current status)

The following table records the inputs that existed before this plan ran. It is retained for auditability and must not be used as a current-task queue.

| Branch / surface | State |
| --- | --- |
| `sdd/static-uasset-finish` @ `.worktrees/sdd-static-continue` | HEAD `871ff296`, worktree clean; Tasks 1–12 + R1–R6 marked executed; 442 passed on last full run. |
| `dev-0.6.0` (main checkout) | Tasks 1–4 only @ `ced9ad8e`; 30 commits behind `sdd/static-uasset-finish`; dirty related docs (see Task 2). |
| README / Wiki | Still claim PackageDocument v2 / `format_version: "2.0"` frozen — must not change until merge + full gate pass. |
| Spec | `status: target`; implementation marker still says Tasks 5–12 are not on `dev-0.6.0`. |
| Planned remaining actions | 1) Controller final review 2) merge into `dev-0.6.0` 3) post-merge full tests 4) update user branch docs/README. |

Committed-tree merge preview: `git merge-tree --write-tree dev-0.6.0 sdd/static-uasset-finish` produced a single tree hash with **no conflict entries**. Real merge is still blocked until main-checkout dirty paths are resolved (Task 2).

## Final Status

- Controller review: pass.
- Merge: landed on `dev-0.6.0`.
- Full suite after merge: pass.
- README/docs: updated to match source and tests.
- Remaining work: none in this plan; create a new plan for any new scope.

## Global Constraints

- Pure Python 3.10+; no runtime bridge, subprocess bridge, or FFI to reference parsers/Unreal Editor.
- `PackageDocument` remains the only package-level aggregate; every export stays addressable.
- Legacy/Zen use separate readers; tagged/unversioned use separate property readers.
- No runtime Blueprint execution; control-flow and calls are static analysis only.
- No fabricated data for cooked-away graphs, unknown serialization, encryption, missing chunks, or native C++ bodies.
- `objects[].semantic` at the document boundary is `dict[str, Any] | None` (Edit Playbook E1).
- Projection status vocabulary is exactly `translated | represented | untranslated | unavailable`.
- Output major is `format_version: "3.0"` (envelope field from `projection.FORMAT_VERSION`).
- One input package → one canonical JSON document. Ordinary asset/graph/function boundaries never split output.
- Do not stage `reference/`, `temp/`, or `docs/plans/2026-09-16-als-name-index-and-optin-docs.md`.
- Do not hardcode a machine-local UE path into committed documentation or tests.
- Update README/Wiki feature claims **only** after the merge lands and the post-merge full gate is green.
- Raise `tests/size-baseline.json` only from measured `tests/test_size_baseline.py` failure output, in the same task/commit that grew the tracked lines.
- All `Run:` commands are PowerShell and set `$env:PYTHONPATH='src'` when importing `uasset_read`.
- No force-push; no `git push` unless the user explicitly asks later.
- Parent plan Edit Playbook E0 remains binding: one concern per commit, green before widen, no dual implementations, preserve unrelated dirty files.
- Execution workspaces:
  - Review/source of truth branch: `.worktrees/sdd-static-continue` on `sdd/static-uasset-finish`
  - Merge target: main checkout `E:/Develop/uasset_read` on `dev-0.6.0`
  - Do not mutate `dev-0.6.0` history with force operations.

## File Map

Modify only after the merge gate, or as merge/conflict resolution requires:

- `E:/Develop/uasset_read/.gitignore` — only if dirty main-checkout change is intentional and still needed after inspection.
- `E:/Develop/uasset_read/docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` — prefer the committed execution-branch copy if it supersedes local dirty edits.
- `E:/Develop/uasset_read/docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md` — prefer committed execution-branch copy.
- `E:/Develop/uasset_read/docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md` — prefer committed execution-branch copy; then Task 5 rewrites the implementation marker for post-merge reality.
- `E:/Develop/uasset_read/docs/designs/README.md` — active v3 row: “planning status only” → implemented on `dev-0.6.0` after green gate.
- `E:/Develop/uasset_read/README.md` — replace v2/frozen-2.0 status banner with v3/`format_version: "3.0"` claims supported by tests.
- `E:/Develop/uasset_read/wiki/**` — only if Wiki pages still assert v2 contract; otherwise leave untouched.
- `E:/Develop/uasset_read/tests/size-baseline.json` — measured only, if README/docs growth fails the ratchet.

Do **not** reopen parser/projection source files in this plan unless the controller review finds a concrete defect (then fix on the execution branch before merge).

---

### Task 1: Controller whole-branch review of `sdd/static-uasset-finish`

**Files:**
- Inspect only: execution worktree `.worktrees/sdd-static-continue`
- Evidence references: R6 report, parent plan, remaining plan, design spec, `AGENTS.md`
- Optional defect fixes (if any): same worktree, `sdd/static-uasset-finish` only

**Interfaces:**
- Consumes: HEAD `871ff296` (or later review-fix commits), R6 report 23/23, last full suite 442 passed.
- Produces: written review verdict (pass / pass-with-fixes / blocked) in this plan file or a short review note under `.superpowers/sdd/.../controller-review.md` on the execution branch; any required fixes committed before Task 3.

- [x] **Step 1: Freeze the review baseline**

Run:

```powershell
cd E:/Develop/uasset_read/.worktrees/sdd-static-continue
git status --short
git branch --show-current
git log --oneline -5
git rev-list --count dev-0.6.0..HEAD
```

Expected: branch `sdd/static-uasset-finish`; clean status; HEAD at `871ff296` or newer; ~30 commits not on `dev-0.6.0`. Record exact HEAD once in the review note.

- [x] **Step 2: Independent full-suite confirmation (once)**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q
python -m compileall -q src
```

Expected: all tests pass (baseline reference: 442 passed) and compileall silent. Per execution limits: this full suite runs **at most once** in Task 1; Task 4 runs it again only after the merge.

If the suite fails: treat as review fail; open a blocked status; do not proceed to merge.

- [x] **Step 3: Walk the binding invariants against source (not design prose)**

Confirm each item with a concrete file/line or test id. Reject on any failure:

1. Only `PackageDocument` is passed into JSON/CLI/Python/Agent/C++ projection entry points.
2. `objects[].semantic` is a `dict` at the document boundary; `tests/fixtures.py` helpers walk dicts; sample-facing tests do not require live `FunctionAnalysis`/`MaterialGraph` dataclasses.
3. Legacy `PackageArchive` remains the reader owner; no second table-reader stack under `src/`.
4. No import/exec/spawn of CUE4Parse, UAssetAPI, UAssetGUI, UnrealBPInspect, FModel, or Unreal Editor (comments/citations only are OK).
5. Legacy and Zen remain separate; Zen package full decode stays unavailable/unverified without a redistributable fixture.
6. Tagged and unversioned readers are separate sole entries and cannot silently substitute.
7. `exec_chains` is a derived edge summary, not a VM/runtime simulation.
8. Blueprint functions expose `instructions`, `cfg`, `calls`, `reads`/`writes`, entrypoints, and unresolved records.
9. `statement_index` is logical CodeOffset; `statement_ordinal` is list order; serialized ranges retained.
10. Correlations carry `match_method`, bounded `confidence`, truthful `unresolved`.
11. Material exposes expressions/links when editor data exists; cooked material builder stays `unavailable`.
12. C++ declaration AST matches the committed UE5.8 golden oracle; migration stats satisfy `instructions_seen == translated + represented + untranslated + unavailable`.
13. Statuses are exactly the four projection values; no Gate K `cpp_code` / `translation_status` / `structured_rate` resurrection.
14. `ProjectorRegistry` has deterministic ownership; equal-priority ambiguity raises.
15. One package → one canonical JSON; `sidecars` remain empty in ordinary paths; `write_projected_document` rejects `max_main_bytes < minimum_canonical_envelope_bytes` before creating a file.
16. `build_canonical_document` / `write_projected_document` reject pagination; bounded `project_document` may paginate.
17. No `reference/`, `temp/`, or ALS plan file staged in recent commits.

Quick probes (read-only):

```powershell
git log --name-only --oneline dev-0.6.0..HEAD -- reference/ temp/ docs/plans/2026-09-16-als-name-index-and-optin-docs.md
Select-String -Path src/uasset_read/projections/cpp_render.py -Pattern 'cpp_code|translation_status|structured_rate'
Select-String -Path src/uasset_read/projection.py -Pattern 'FORMAT_VERSION'
```

Expected: first command prints no forbidden paths (or only historically explained paths — investigate any hit); cpp_render has no Gate K fields; `FORMAT_VERSION = "3.0"` present.

- [x] **Step 4: Sample-facing golden-path spot check**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_complete_samples.py tests/test_blueprint_cpp.py tests/test_asset_projections.py tests/test_single_output.py tests/test_projection_v3.py tests/test_cli.py tests/test_size_baseline.py -q
```

Expected: PASS. These are the acceptance surfaces for merge confidence (not a substitute for Task 2’s full suite if already run).

- [x] **Step 5: Write the review verdict**

Create/update (on execution branch, commit only this note if the worktree policy allows committing docs notes):

```markdown
# Controller review — sdd/static-uasset-finish
- HEAD: <sha>
- Full suite: <N passed / fail>
- Invariant walk: pass/fail per item 1–17
- Defects: none | list with file:line
- Verdict: pass | blocked
- Reviewer date: <YYYY-MM-DD>
```

If defects exist: fix on `sdd/static-uasset-finish` with failing-test-first proof, re-run only the focused tests plus `tests/test_size_baseline.py`, commit, then re-walk only the broken invariant. Do **not** start a second full-suite storm unless the earlier run hung/timed out.

- [x] **Step 6: Mark this plan’s review checkboxes**

Update Task 1 boxes in this file only after the verdict is `pass`. Commit this plan file on the execution branch if it lives there, or leave for the docs commit in Task 5 — one concern per commit: **do not mix review note + merge + README**.

---

### Task 2: Prepare `dev-0.6.0` main checkout for a clean merge

**Files:**
- Modify/restore only as decided after inspection:
  - `E:/Develop/uasset_read/.gitignore`
  - `E:/Develop/uasset_read/docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`
  - `E:/Develop/uasset_read/docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md`
  - `E:/Develop/uasset_read/docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`
- Do not touch: `docs/plans/2026-09-16-als-name-index-and-optin-docs.md` (unrelated), `reference/`, `temp/`

**Interfaces:**
- Consumes: dirty main-checkout status; committed execution-branch doc versions at `871ff296`.
- Produces: main checkout with a mergeable index/worktree for the three related docs (plus intentional `.gitignore` decision); ALS file left untracked/untouched.

- [x] **Step 1: Capture main checkout baseline**

Run:

```powershell
cd E:/Develop/uasset_read
git status --short
git branch --show-current
git log --oneline -3
git diff --stat
git diff -- .gitignore
```

Expected: branch `dev-0.6.0`; four modified paths + one untracked ALS plan. Record `.gitignore` diff content in the task note.

- [x] **Step 2: Decide per dirty path**

For each of the three related docs:

1. Run `git diff -- <path>` and compare intent with the execution-branch committed file (`git show sdd/static-uasset-finish:<path>`).
2. If the dirty local edit is an earlier/incomplete expansion already superseded by the branch copy → `git restore -- <path>` (worktree only; no history rewrite).
3. If the dirty edit contains unique, still-needed content not on the branch → copy that hunk into a short note, then still restore the file for merge cleanliness; re-apply the unique hunk **after** merge in Task 5 (one docs commit).

For `.gitignore`:

1. If the one-line addition is required by already-committed execution-branch artifacts → keep it staged/committed **before** merge as its own tiny commit (`chore: ...`).
2. If unrelated to this delivery → `git restore -- .gitignore`.
3. Never fold `.gitignore` into the merge commit unless git itself includes it (it should not).

Expected after Step 2: `git status --short` shows only the untracked ALS file (and nothing else, unless a deliberate pre-merge `.gitignore` commit was made).

- [x] **Step 3: Confirm merge is still conflict-free on the real trees**

Run:

```powershell
git merge-tree --write-tree dev-0.6.0 sdd/static-uasset-finish
```

Expected: a single tree object id, no `CONFLICT` lines. If conflicts appear, resolve them as **execution-branch versions win for the four related docs**, unless AGENTS.md rules are violated; never resolve by discarding implementation commits.

- [x] **Step 4: Reconfirm clean status**

Run:

```powershell
git status --short
```

Expected: clean except untracked `docs/plans/2026-09-16-als-name-index-and-optin-docs.md`. If not, return to Step 2.

---

### Task 3: Merge `sdd/static-uasset-finish` into `dev-0.6.0`

**Files:**
- Git history only (plus automatic doc updates carried by the merge).
- Conflict files only if Step 3 reports them.

**Interfaces:**
- Consumes: Task 1 verdict `pass`; Task 2 clean main checkout; committed-tree merge preview without conflicts.
- Produces: `dev-0.6.0` containing Tasks 1–12 source/tests/docs; working tree clean; no push.

- [x] **Step 1: Create the merge commit**

Run (main checkout, branch `dev-0.6.0`):

```powershell
cd E:/Develop/uasset_read
git status --short
git merge --no-ff sdd/static-uasset-finish -m "merge: land static uasset v3 tasks 1-12"
git status --short
git log --oneline -3
```

Expected: merge succeeds; status clean (ALS untracked remains); HEAD history includes `871ff296` as an ancestor (`git merge-base --is-ancestor sdd/static-uasset-finish HEAD` exits 0).

- [x] **Step 2: Abort/recover if merge fails**

If git reports conflicts or refuses due to dirty files:

1. Do **not** use `git merge --abort` until you have saved `git diff > temp/merge-conflict.diff` when partial changes matter.
2. `git merge --abort` if mid-merge and no intended partial resolution.
3. Return to Task 2 and fix the dirty/conflicting path.
4. Retry merge **once**. If the second attempt still fails: mark this plan `blocked`, list attempted commands, and stop (no third blind retry).

- [x] **Step 3: Verify ancestry and contents**

Run:

```powershell
git merge-base --is-ancestor sdd/static-uasset-finish HEAD; echo "ancestor_exit=$LASTEXITCODE"
git diff --stat sdd/static-uasset-finish HEAD -- src tests
```

Expected: `ancestor_exit=0`; `src`/`tests` diff empty (merge landed implementation as-is).

---

### Task 4: Post-merge full verification gate

**Files:**
- No source edits expected.
- `tests/size-baseline.json` only if docs growth from the merge fails the measured ratchet.

**Interfaces:**
- Consumes: merged `dev-0.6.0` from Task 3.
- Produces: green full suite + compileall on the user-facing branch; evidence line for Task 5 docs claims.

- [x] **Step 1: Run the full suite once on merged `dev-0.6.0`**

Run:

```powershell
cd E:/Develop/uasset_read
$env:PYTHONPATH='src'; python -m pytest -q
```

Expected: all tests pass (expect 442 or a higher count if only additive). Per limits: **one** full run here; optional second run only if the first hangs/times out.

- [x] **Step 2: Run baseline gates and compileall**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_complete_samples.py tests/test_quality_baseline_generator.py tests/test_size_baseline.py tests/test_core.py tests/test_contract_v3.py -q
python -m compileall -q src
```

Expected: PASS + silent compileall.

If only `tests/test_size_baseline.py` fails on `docs_markdown` growth:

1. Copy the **exact** measured `max_lines` from the failure output.
2. Edit `tests/size-baseline.json` only to that measured value.
3. Re-run `tests/test_size_baseline.py` once.
4. Commit: `test: raise docs_markdown ceiling after v3 merge docs`.

Do not widen any other baseline from estimates. Do not weaken sample/quality gates.

- [x] **Step 3: Record gate evidence**

Write one short note (this plan checkbox text is enough if no review file is required):

- merged HEAD sha (once)
- full suite result
- baseline/compileall result

Mark Task 4 steps complete only when all three are green.

---

### Task 5: Update user-facing docs and README status

**Files:**
- Modify: `README.md` (status banner + any still-wrong v2 contract sentences)
- Modify: `docs/designs/README.md` (v3 target row: planning → implemented on `dev-0.6.0`)
- Modify: `docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md` (implementation marker; keep `status: target` unless the canonical design index rule says otherwise — only change `status:` if `docs/designs/README.md` + design doc now claim current v3 behavior)
- Modify: `docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md` (Execution status: tasks complete on `dev-0.6.0`; controller review + merge recorded)
- Modify: `docs/superpowers/plans/2026-09-21-remaining-static-uasset-v3-projection.md` (snapshot: landed on `dev-0.6.0`)
- Modify: `docs/superpowers/plans/2026-09-21-closeout-static-uasset-v3-merge.md` (this file — mark steps done)
- Modify: `wiki/**` only if pages still assert v2 / `format_version: "2.0"` / “Zen deferred” contrary to current tests
- Modify: `tests/size-baseline.json` only from measured failure after these edits

**Interfaces:**
- Consumes: Task 4 green evidence; AGENTS.md documentation authority rules.
- Produces: documented status that matches source+tests on `dev-0.6.0`; no premature feature claims; no machine-local UE paths.

- [x] **Step 1: Inventory stale claims**

Run:

```powershell
cd E:/Develop/uasset_read
rg -n "format_version.*2\.0|PackageDocument v2|S1, 2026-09-13|not started|unmerged candidate|planning status only|Tasks 5–12|Tasks 5-12" README.md docs wiki -g '!docs/plans/**' -g '!reference/**'
```

List every hit that contradicts Task 4 evidence. Hits inside archive/ are historical — leave them.

- [x] **Step 2: Rewrite the README status banner**

Replace the v2 frozen-contract banner with claims supported by tests, including at least:

- package-first `PackageDocument` with `format_version: "3.0"`;
- static Blueprint graph/Kismet instruction/CFG/correlation analysis in `objects[].semantic` (dict);
- embedded type-aware projections (`cpp_declaration`, `cpp_migration`, material/table/curve/struct/enum, metadata/payload) via one canonical document;
- Zen/IoStore package full decode still explicitly unverified/unavailable without redistributable fixtures (keep this honest limit);
- payload extraction / views language only where tests still prove it.

Do **not** claim: native C++ body equivalence, Blueprint VM execution, traditional FPak entry extraction, or real Zen package parse.

- [x] **Step 3: Update design index, spec marker, and plan status rows**

1. `docs/designs/README.md` — v3 row still binds as target architecture, but remove “planning status only until source tasks are executed” for the plan link; state Tasks 1–12 implemented on `dev-0.6.0` after gate `<sha>`.
2. Spec implementation marker — Tasks 1–12 current on `dev-0.6.0`; point to this closeout plan’s gate evidence; keep excluded-scope language (no runtime exec, no native body recovery, Zen unverified).
3. Parent plan Execution status — all task rows `implemented (dev-0.6.0)`; controller review + merge dates recorded.
4. Remaining plan snapshot — R1–R6 landed via merge; no remaining implementation tasks.
5. Do not edit `docs/designs/archive/**`.

- [x] **Step 4: Commit docs in one reviewable commit**

Run:

```powershell
git add README.md docs/designs/README.md docs/superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md docs/superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md docs/superpowers/plans/2026-09-21-remaining-static-uasset-v3-projection.md docs/superpowers/plans/2026-09-21-closeout-static-uasset-v3-merge.md
# include wiki only if Step 1 required wiki edits
git status --short
git commit -m "docs: mark static uasset v3 landed on dev-0.6.0"
```

Expected: only the listed docs (and wiki if needed) staged; ALS file and `reference/` absent.

- [x] **Step 5: Re-run size ratchet after docs growth**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/test_size_baseline.py -q
```

Expected: PASS, or FAIL with measured `docs_markdown` ceiling. On FAIL: raise only that measured value, amend **not** used — create a follow-up commit `test: raise docs_markdown ceiling for v3 status docs`, then re-run once.

- [x] **Step 6: Final verification snapshot**

Run:

```powershell
$env:PYTHONPATH='src'; python -m pytest -q
python -m compileall -q src
git status --short
git log --oneline -5
```

Expected: all tests pass; compileall clean; status clean except unrelated ALS untracked file; log shows merge + docs commit.

This second full suite is allowed because Task 5 changed tracked docs/README and the plan requires green-before-done evidence after user-facing edits. If it fails only on size baseline, follow Step 5; if it fails anywhere else, mark Task 5 `blocked` with the failure list — do not claim completion.

- [x] **Step 7: Close this plan**

Check off remaining boxes; record final HEAD once; state explicitly:

- Controller review: pass
- Merge: landed on `dev-0.6.0`
- Full suite after merge: pass
- README/docs: updated to match source+tests
- Push: **not performed** (user must ask separately)

---

## Self-Review Checklist (plan author)

1. **Spec coverage:** Acceptance gates 1–9 are already covered by R5/R6 on the execution branch; this closeout plan does not re-implement them. Spec “Migration constraints” and “Capability and error contract” are re-checked in Task 1 invariant walk; post-merge proof is Task 4; documentation authority rules are Task 5. Zen unverified / no runtime bridge / one canonical document constraints remain global.
2. **Placeholder scan:** No TBD/TODO steps. Review items name exact commands and pass criteria. README rewrite lists required claim classes and forbidden claims rather than “update docs later”. Merge failure has an explicit abort/retry/blocked path.
3. **Type consistency:** No new runtime APIs. Names used in commands (`FORMAT_VERSION`, `write_projected_document`, `minimum_canonical_envelope_bytes`, gate test modules) match the parent/remaining plans and R6 report. Branch names are fixed: source `sdd/static-uasset-finish`, target `dev-0.6.0`.

## Out of Scope

- Pushing `dev-0.6.0` or `sdd/static-uasset-finish` to a remote.
- Writer/binary `.uasset` mutation support.
- Traditional FPak extraction or real Zen package decode without new fixtures.
- Reopening Tasks 1–12 implementation beyond review-found defects.
- Updating Wiki API examples that are not contradicted by current tests.
