# Next-Phase Closeout, Polish, and Deferred-Gate Decision Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the completed Wave A+B productize branch, (1) merge and backfill plan status without push, (2) land the three non-deferred second-review polish items, (3) research T15/T13 and decide go/no-go from evidence, (4) evaluate which deferred out-of-plan capabilities should be batched into the next project — **without implementing any of them here**.

**Architecture:**
- Work stays on `docs/productize-unversioned` until merge into `dev-0.6.0` (fast-forward: feature is a strict descendant of `dev-0.6.0`).
- A (merge + docs) and B (polish) are **executable now** and must not be deferred.
- C (T15 `_run_cases` / residual T13) is **research-first**; execution only after an explicit GO decision recorded in the research note.
- D (Zen/IoStore, SchemaProvider, payload route A, batch/diff, C++ skeleton) is **evaluation-only** here; the output is a bundling recommendation, not code.

**Tech Stack:** Python 3.10+ (gate Win + 3.14), pytest, ruff, zero runtime dependencies.

**Spec:**
- Completed productize plan: `docs/designs/2026-09-12-post-refactor-productize-plan.md`
- Authoritative architecture: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`
- Deferred contract maps: `docs/designs/2026-08-31-v1-retirement-plan.md`, `2026-08-31-payload-extraction-path.md`, `docs/designs/README.md`

## Global Constraints

- Worktree: `E:/Develop/uasset_read/.worktrees/productize-unversioned`; branch `docs/productize-unversioned` (currently tip `2419de4e`).
- `$env:PYTHONPATH="E:/Develop/uasset_read/.worktrees/productize-unversioned/src"`; run gates from the **worktree root**.
- Interpreters: `"C:\Program Files\Python314\python.exe"` (or `$env:MIMO_PYTHON` when set).
- Zero runtime dependencies; read-only parser; scratch only under `temp/` (never committed).
- Code/comments/commits English; prefixes `refactor:` / `fix:` / `feat:` / `test:` / `docs:` / `chore:`; **do not push**.
- Do not touch `external/`, `UnrealEngine/`, `dist/`, `build/`.
- Do not restore Wave A deleted symbols (`read_k2node_*`, `FMemberReference` readers, pin write fields, tagged name-index unversioned fallback).
- No `skip`/`xfail` camouflage; semantic key additions do not bump `format_version`.
- Pin five keys frozen: `id`/`name`/`direction`/`category`/`linked`.
- Baseline expectation after polish-only diffs: ruff green; pytest **226 passed + 2 failed** (`test_container_fixtures_match_manifest`, `test_iostore_toc_fixture_headers_match_ue_struct_fields` — missing large ucas, not regressions); `temp/decode_parity.py check` **identical**.

## Explicit Non-Goals

| Forbidden | Reason |
| --- | --- |
| `git push` of any branch | User standing rule until explicit ask |
| Implementing Zen/Pak/SchemaProvider/batch/diff/C++ skeleton | D is evaluation-only |
| Restoring removed blueprint binary readers | Wave A freeze |
| Buying or inventing Zen/cooked fixtures | Prior product decision |
| Closing T15 without a written GO from C2 | Research gate |
| Editing wiki without a local wiki checkout | Wiki path is environment-dependent; see A3 |

---

## File Map

| Path | Role |
| --- | --- |
| `docs/designs/2026-09-12-post-refactor-productize-plan.md` | Status → executed; Wave A/B checkboxes |
| `docs/designs/README.md` | Index rows for productize + ponytail plans |
| `docs/designs/2026-09-12-ponytail-evaluation-fix-plan.md` | Status/index only (execution already done) |
| `tests/test_blueprint_decode.py` | Variable positive-when-present assertion |
| `src/uasset_read/serializers/blueprint_graph.py` | orientation-flip / peer-category comment |
| `src/uasset_read/parsers/property_parser.py` | dead `tell()>property_end` removal |
| `tests/test_unversioned_fixtures.py` | only if FText Base path needs an extra guard (prefer none) |
| `temp/c1-run-cases-survey.md` | C research note (not committed) |
| `temp/c2-test-tree-survey.md` | C residual T13 note (not committed) |
| `temp/d-deferred-bundling-memo.md` | D evaluation memo (not committed) |
| `docs/designs/2026-09-13-deferred-capability-bundling.md` | D committed decision record |

---

# Phase A — Merge and Plan-Status Backfill (execute, do not defer)

### Task A1: Freeze productize plan status

**Files:**
- Modify: `docs/designs/2026-09-12-post-refactor-productize-plan.md` (header + Wave A/B checkboxes + handoff)
- Modify: `docs/designs/README.md` (status index rows 31–32)

**Interfaces:**
- Consumes: git history proving Wave A (`5b07a2e8` region) and Wave B (`42946379`…`2419de4e`) landed.
- Produces: docs state `current` / executed so later readers do not re-run A/B.

- [ ] **Step A1.1: Confirm tip and gates before editing docs**

```powershell
Set-Location "E:/Develop/uasset_read/.worktrees/productize-unversioned"
git status -sb
git log --oneline -20
$env:PYTHONPATH="E:/Develop/uasset_read/.worktrees/productize-unversioned/src"
& "C:\Program Files\Python314\python.exe" -m ruff check src/uasset_read tests/
& "C:\Program Files\Python314\python.exe" -m pytest -q
& "C:\Program Files\Python314\python.exe" temp/decode_parity.py check
```

Expected: clean tree; ruff PASS; 226 passed + 2 ucas fails; parity identical.

- [ ] **Step A1.2: Rewrite plan header Status**

Replace:

```markdown
> **Status:** target（计划已合并；**尚未执行**）
```

with:

```markdown
> **Status:** current（Wave A 已执行于 `docs/productize-unversioned`；Wave B P0–P8 及二次审查加固已执行；本文仅作完成记录与交接索引）
```

- [ ] **Step A1.3: Check off executed Wave A and Wave B steps**

In the same file, mark every completed checkbox for:

- Wave A definition list (pytest / parity / ruff / size-baseline lines) → `[x]` with a dated note: executed on `docs/productize-unversioned` prior to this plan.
- Wave B Tasks P0–P8 steps (P0.1–P0.3, P1, P2, P3, P4.1–P4.5, P5.1–P5.4, P6.1–P6.3, P7.1–P7.3, P8.1–P8.3) → `[x]`.
- Leave unchecked only if a step is known not done; expected: all productize steps done.

- [ ] **Step A1.4: Rewrite “执行交接（仍不执行）” footer**

Replace the footer with:

```markdown
## 执行交接（已执行）

**Plan complete, executed** on branch `docs/productize-unversioned`.

1. Wave A (ponytail T1–T14, T16; T15 intentionally **not** executed) landed in the Wave A commit chain through size-baseline tightening.
2. Wave B P0–P8 and second-review hardening (`81eb9de9`…`2419de4e`) landed on the same branch.
3. Remaining work is outside this plan: Phase A (this document’s successor plan), Phase C research gates, Phase D deferred bundling. See `docs/designs/2026-09-13-next-phase-closeout-and-deferred-gates.md` if present.
```

- [ ] **Step A1.5: Update `docs/designs/README.md` index rows**

For the two `2026-09-12-ponytail-evaluation-fix-plan.md` and `2026-09-12-post-refactor-productize-plan.md` rows:

- Change `status:` cell from `target` to `current`.
- For productize row, replace “**Not executed.**” with “**Executed** on `docs/productize-unversioned` (Wave A + Wave B + review hardening through `2419de4e`); T15 `_run_cases` intentionally out of scope.”

- [ ] **Step A1.6: Commit docs backfill**

```powershell
git add docs/designs/2026-09-12-post-refactor-productize-plan.md docs/designs/README.md
git commit -m "docs: mark Wave A/B productize plan executed and update design index"
```

Expected: one commit; working tree clean for docs.

---

### Task A2: Merge productize branch into `dev-0.6.0` (no push)

**Files:**
- None edited; git operations only on local refs.

**Interfaces:**
- Consumes: A1 docs commit on `docs/productize-unversioned`.
- Produces: `dev-0.6.0` advanced to the productize tip (fast-forward).

- [ ] **Step A2.1: Reconfirm ancestry**

```powershell
Set-Location "E:/Develop/uasset_read/.worktrees/productize-unversioned"
git merge-base --is-ancestor dev-0.6.0 docs/productize-unversioned
git rev-list --count dev-0.6.0..docs/productize-unversioned
```

Expected: ancestry true; count ≈ 27 (26 prior + A1 docs commit).

- [ ] **Step A2.2: Fast-forward merge from the main checkout**

```powershell
Set-Location "E:/Develop/uasset_read"
git status -sb
git merge --ff-only docs/productize-unversioned
git log --oneline -5
```

Expected: `Fast-forward`; tip equals productize tip; **do not push**.

If main tree is dirty: stop and report; do not stash user work automatically.

- [ ] **Step A2.3: Spot-check main checkout gates (optional but preferred)**

```powershell
Set-Location "E:/Develop/uasset_read"
$env:PYTHONPATH="E:/Develop/uasset_read/src"
& "C:\Program Files\Python314\python.exe" -m pytest -q
```

Expected: same 226+2 profile.

---

### Task A3: Wiki / external doc sync decision (environment-gated)

**Files:**
- None if wiki absent; if wiki checkout exists later, sync README Blueprint/unversioned claims only.

**Interfaces:**
- Consumes: README claims already aligned in `abf7e1fb`.
- Produces: either a wiki commit **locally only**, or a recorded “blocked: no wiki checkout” note.

- [ ] **Step A3.1: Probe for a local wiki checkout**

```powershell
$roots = @(
  "E:/Develop/uasset_read.wiki",
  "E:/Develop/uasset_read/wiki",
  "E:/Develop/uasset_read/.wiki"
)
foreach ($r in $roots) { if (Test-Path $r) { Write-Output "FOUND $r"; Get-ChildItem $r | Select-Object -First 10 Name } }
```

- [ ] **Step A3.2: Branch on result**

- **Not found (expected on this machine):** write a one-line note in the commit body of A4 or in `temp/wiki-sync.txt`: `wiki checkout not present; deferred until user provides path`. Do **not** invent a remote push.
- **Found:** open the wiki Home/Sidebar pages that still claim Semantic 1.x / pre-Wave-B blueprint features; update only pages that contradict README (pin-level links, exec_chains, tag-derived node_data, unversioned partial). Commit message: `docs: align wiki blueprint/unversioned claims with post-subtraction v2`. **No push.**

---

# Phase B — Second-Review Polish (execute now; not deferred)

Order: B1 Variable test → B2 exec orientation comment → B3 FText dead check. Each is independently commit-able.

### Task B1: Variable positive assertion when MemberName exists

**Files:**
- Modify: `tests/test_blueprint_decode.py` (`test_variable_nodes_do_not_fake_member_reference` and/or a sibling test)

**Interfaces:**
- Consumes: existing negative assertion (size/offset stubs rejected).
- Produces: a **conditional** positive path: if any Variable node’s projected `node_data` contains `MemberName` (string non-empty), assert it is primitive and not a fake; if none exist on current fixtures, the test still enforces the negative contract and documents the empty positive with an explicit inventory assert (count == 0 on today’s sample) so a future sample flip is visible.

- [ ] **Step B1.1: Inventory current Variable node_data on the sample**

```powershell
Set-Location "E:/Develop/uasset_read/.worktrees/productize-unversioned"
$env:PYTHONPATH="E:/Develop/uasset_read/.worktrees/productize-unversioned/src"
& "C:\Program Files\Python314\python.exe" -c "from pathlib import Path; from uasset_read import parse_package_document; from uasset_read.projection import project_document; doc=parse_package_document(Path('tests/samples/BP_CombatCharacter.uasset'), depth='decode', tolerant=True); page=project_document(doc, depth='decode', max_bytes=3_000_000); nodes=[n for o in page.get('objects') or [] for g in (o.get('semantic') or {}).get('graphs') or [] for n in g.get('nodes') or [] if 'Variable' in (n.get('type') or '')]; print('n', len(nodes)); print('ref', sum(1 for n in nodes if (n.get('node_data') or {}).get('VariableReference'))); print('member', sum(1 for n in nodes if (n.get('node_data') or {}).get('MemberName')))"
```

Recorded baseline (2026-09-12): `n=84`, `ref=0`, `member=0`. Use these numbers in the test comments only if still true after re-probe.

- [ ] **Step B1.2: Extend the Variable test**

In `tests/test_blueprint_decode.py`, replace/extend `test_variable_nodes_do_not_fake_member_reference` with the following body (keep the existing negative loop; add the positive-when-present and inventory pins):

```python
def test_variable_nodes_do_not_fake_member_reference():
    """Variable nodes must not emit size/offset-only VariableReference stubs.

    Unmatched tags store ``{size, offset}`` only. Until MemberName/MemberParent
    (or equivalent primitives) survive in tags, that locator must not be
    projected as VariableReference. When MemberName *does* appear it must be a
    non-empty string primitive — a regression guard for the day fixtures carry
    real member tags, without inventing data today.
    """
    from uasset_read import parse_package_document
    from uasset_read.projection import project_document

    doc = parse_package_document(
        SAMPLES / "BP_CombatCharacter.uasset", depth="decode", tolerant=True
    )
    page = project_document(doc, depth="decode", max_bytes=3_000_000)
    nodes = [
        n
        for o in page.get("objects") or []
        for g in (o.get("semantic") or {}).get("graphs") or []
        for n in g.get("nodes") or []
        if "Variable" in (n.get("type") or "")
    ]
    assert nodes
    member_names = []
    for node in nodes:
        node_data = node.get("node_data") or {}
        var_ref = node_data.get("VariableReference")
        if var_ref is not None:
            assert isinstance(var_ref, dict)
            assert set(var_ref) - {"size", "offset"}, f"opaque locator leaked: {var_ref}"
        member = node_data.get("MemberName")
        if member is not None:
            assert isinstance(member, str) and member, f"MemberName must be a non-empty string: {member!r}"
            member_names.append(member)
    # Today's CombatCharacter Variable tags have no MemberName primitives.
    # If this assert fails after a fixture change, that is a visible inventory
    # flip — update the comment and keep the positive constraints above.
    assert member_names == []
```

- [ ] **Step B1.3: Run the single test**

```powershell
& "C:\Program Files\Python314\python.exe" -m pytest tests/test_blueprint_decode.py::test_variable_nodes_do_not_fake_member_reference -v
```

Expected: PASS.

- [ ] **Step B1.4: Commit**

```powershell
git add tests/test_blueprint_decode.py
git commit -m "test: pin Variable MemberName when present without fabricating refs"
```

---

### Task B2: Document exec orientation flip without peer-category validation

**Files:**
- Modify: `src/uasset_read/serializers/blueprint_graph.py` (docstring of `summarize_exec_edges` only)

**Interfaces:**
- Consumes: existing flip at lines ~360–364 (prefer output→input; no peer category check).
- Produces: comment/docstring honesty; **no behavior change**.

- [ ] **Step B2.1: Confirm no functional change is required**

Current code only checks the current pin is `category==exec`; when flipping to the peer output pin it does **not** re-check that the peer is also exec. That is intentional for unique undirected emission: one side being exec is enough to register the connection. Document that; do not add a peer filter (would change edge sets and parity).

- [ ] **Step B2.2: Extend the docstring**

Append to `summarize_exec_edges` docstring:

```python
    Orientation flip only prefers an output endpoint when the current pin is
    not already output. It does not re-validate that the peer pin's category
    is also ``exec``: the walk already required *this* pin to be exec, and
    filtering on the peer would drop legitimate edges recorded on only one
    side of the link table.
```

- [ ] **Step B2.3: Confirm parity and tests**

```powershell
& "C:\Program Files\Python314\python.exe" -m pytest tests/test_blueprint_decode.py -q
& "C:\Program Files\Python314\python.exe" temp/decode_parity.py check
```

Expected: PASS / identical (docstring-only).

- [ ] **Step B2.4: Commit**

```powershell
git add src/uasset_read/serializers/blueprint_graph.py
git commit -m "docs: note exec edge orientation does not re-check peer category"
```

---

### Task B3: Remove dead Base-FText `tell()>property_end` check

**Files:**
- Modify: `src/uasset_read/parsers/property_parser.py` (`_read_unversioned_ftext`)

**Interfaces:**
- Consumes: early bound `if start + 5 > property_end: return None` before the two reads that advance exactly 5 bytes.
- Produces: same None/rewind contract; fewer impossible branches. Existing tests in `tests/test_unversioned_fixtures.py::TestUnversionedFTextStopPath` must stay green.

- [ ] **Step B3.1: Prove the check is dead (reasoning + probe)**

After `read_i32()` + `read_u8()`, `archive.tell() == start + 5`. The guard `start + 5 > property_end` already returned. Therefore `tell() > property_end` cannot become true on the Base path without an exception, which the outer `except` already handles with rewind.

Optional probe (Base history under tight property_end) already covered by existing unit tests using a synthetic payload.

- [ ] **Step B3.2: Delete the dead lines**

In `_read_unversioned_ftext`, change:

```python
        if history == 0:  # Base
            if archive.tell() > property_end:
                return None
            namespace = archive.read_fstring()
```

to:

```python
        if history == 0:  # Base
            namespace = archive.read_fstring()
```

Leave the early `start + 5 > property_end` guard and the `history in (255, 0xFF)` + unknown-history rewind paths unchanged.

- [ ] **Step B3.3: Run focused + full gates**

```powershell
& "C:\Program Files\Python314\python.exe" -m pytest tests/test_unversioned_fixtures.py -q
& "C:\Program Files\Python314\python.exe" -m ruff check src/uasset_read/parsers/property_parser.py
& "C:\Program Files\Python314\python.exe" -m pytest -q
& "C:\Program Files\Python314\python.exe" temp/decode_parity.py check
```

Expected: unversioned tests PASS; ruff PASS; suite 226+2; parity identical (or note any intentional decode-hash delta — expected none for this pure branch delete).

- [ ] **Step B3.4: Commit**

```powershell
git add src/uasset_read/parsers/property_parser.py
git commit -m "fix: drop unreachable Base-FText property_end check after fixed header read"
```

---

# Phase C — Research First, Then Decide (do not implement T15/T13 here)

C produces evidence and a GO/NO-GO. **No production refactor** unless C2/C3 end with GO **and** the user later authorizes a separate execution plan.

### Task C1: Survey `_run_cases` (T15) and write research note

**Files:**
- Create (scratch): `temp/c1-run-cases-survey.md`
- Read: `tests/test_core.py` and every `_run_cases(` call site

**Interfaces:**
- Consumes: current helper at `tests/test_core.py:49-54`.
- Produces: recommendation GO / NO-GO / DEFER with effort and risk; no code change.

- [ ] **Step C1.1: Enumerate call sites and case shapes**

```powershell
Set-Location "E:/Develop/uasset_read/.worktrees/productize-unversioned"
& "C:\Program Files\Python314\python.exe" -c "import ast,pathlib; p=pathlib.Path('tests/test_core.py'); t=ast.parse(p.read_text()); locs=[]; 
for n in ast.walk(t):
  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id=='_run_cases':
    locs.append(n.lineno)
print('call_sites', locs)"
```

Manually record for each site: whether cases are multi-assertion packs, whether isolation contexts wrap them, and whether pytest parametrize would change failure attribution.

- [ ] **Step C1.2: Draft the native-pytest shape (design only)**

Preferred target shape if GO:

```python
@pytest.mark.parametrize("case_name,check", _CASES, ids=[c[0] for c in _CASES])
def test_reader_boundaries(case_name, check):
    check()
```

or nested functions collected via a thin loop that still yields separate test items. Constraints for any design:
- Preserve failure messages that include `case_name`.
- Keep `_isolated_handlers` semantics.
- No skip/xfail; zero production-code change; size-baseline tests may grow slightly.

- [ ] **Step C1.3: Estimate blast radius**

- Count approximate assertion blocks under all `_run_cases` sites.
- Note whether any case depends on prior case order (shared module state). If yes → strong NO-GO for blind parametrize.

- [ ] **Step C1.4: Write `temp/c1-run-cases-survey.md`**

Required sections: Call sites; Dependency/order risks; Proposed shape; Effort (S/M/L); Recommendation (`GO` | `NO-GO` | `DEFER`); Rationale ≤10 lines.

- [ ] **Step C1.5: Decision gate (user-facing)**

Present the note’s Recommendation to the user. **Do not start T15 implementation in this plan** unless the user opens a new execution authorization in the same conversation after GO.

---

### Task C2: Residual T13 test-tree survey

**Files:**
- Create (scratch): `temp/c2-test-tree-survey.md`
- Read: `tests/` layout, `tests/size-baseline.json`, Wave A T13 commit `71ab2b7b`

**Interfaces:**
- Consumes: prior dedupe already landed.
- Produces: residual-duplicate inventory; GO/NO-GO for a second tightening pass.

- [ ] **Step C2.1: List remaining fixture boilerplate clusters**

Search for repeated `parse_package_document` + `project_document` scaffolds in `tests/` (exclude intentionally independent contract tests).

- [ ] **Step C2.2: Classify each cluster**

| Class | Action if GO |
| --- | --- |
| True duplicate | extract helper |
| Same shape, different assertion | keep separate |
| Isolation-critical | keep separate |

- [ ] **Step C2.3: Write `temp/c2-test-tree-survey.md` and recommend**

Default expectation: **DEFER / NO-GO** unless a cluster is ≥3 identical 10+ line blocks with no isolation need.

---

### Task C3: Record Phase C outcome (no code)

- [ ] **Step C3.1:** After C1+C2 notes exist, send the user a short GO/NO-GO table (T15, T13).
- [ ] **Step C3.2:** If both NO-GO/DEFER, stop. If GO, offer to write a **new** implementation plan (`docs/designs/YYYY-MM-DD-t15-run-cases-refactor.md`) — do not execute under this plan.

---

# Phase D — Deferred Capability Bundling Evaluation (evaluate only)

D answers: **which deferred capabilities should ship as one future project vs stay separate**, and **what blocks each**. No implementation.

### Task D1: Dependency map of deferred capabilities

**Files:**
- Create (scratch): `temp/d-deferred-bundling-memo.md`
- Create (committed): `docs/designs/2026-09-13-deferred-capability-bundling.md`
- Read: `2026-08-26-package-first-uasset-parser-refactor.md` (still-incomplete list), `2026-08-31-v1-retirement-plan.md` (batch/diff), `2026-08-31-payload-extraction-path.md` (route A/B), `2026-08-31-agent-doc-cache-contract.md` (G2), `docs/designs/README.md` index.

**Capabilities under evaluation (do not implement):**

| ID | Capability | Issue / design anchor |
| --- | --- | --- |
| D-ZEN | `ZenPackageReader` + IoStore package body | #624, canonical Phase 5 |
| D-PAK | Pak container full product path | #625 |
| D-SCHEMA | Full `SchemaProvider` / cooked unversioned | canonical UnversionedPropertyReader; README “no full SchemaProvider” |
| D-PLA | Payload-only parse (route A) | `2026-08-31-payload-extraction-path.md` |
| D-G2 | Shared PackageDocument cache | G2 |
| D-BATCH | CLI `--batch` | D1 retirement plan deferred |
| D-DIFF | CLI `--diff` | D1 retirement plan deferred |
| D-CPP | Blueprint C++ skeleton | Gate K retired; skeleton still unmigrated |

- [ ] **Step D1.1: Build the edge table**

For each pair, mark coupling: `hard` (same fixtures, same reader), `soft` (shared protocol only), `none`.

Seed expectations to verify against source (correct if wrong):

| Edge | Expected | Why |
| --- | --- | --- |
| D-ZEN ↔ D-PAK | soft | Both containers; package body vs archive-of-packs; may share Source abstraction but different fixtures |
| D-ZEN ↔ D-PLA | hard | Payload route A assumes container trailer descriptors; Zen body is the descriptor source |
| D-ZEN ↔ D-SCHEMA | none | Unversioned SchemaProvider is orthogonal to package layout |
| D-SCHEMA ↔ D-PAK | none | cooked unversioned is property schema, not pack index |
| D-G2 ↔ D-PLA | soft | Cache accelerates extract; does not create descriptors |
| D-G2 ↔ all | soft | Pure performance contract |
| D-BATCH ↔ D-DIFF | soft | Workflow CLI pair; share parse entrypoints only |
| D-CPP ↔ D-ZEN | none | Blueprint source emission independent of container |
| D-CPP ↔ Wave B blueprint | soft | Consumes same object model; no Zen need |

- [ ] **Step D1.2: Apply bundling rules**

Rules (fixed for this evaluation):

1. **Same fixtures + same trust boundary → one project.**
2. **Pure workflow (batch/diff) never blocks format work** — separate product decision.
3. **G2 is always a free-standing cheap win** if multi-extract is a real consumer path.
4. **C++ skeleton** only bundles with Blueprint semantic depth work, never with containers.
5. **No sample acquisition** inside a bundle; fixtures remain a listed precondition with `fixture_gaps`.

- [ ] **Step D1.3: Produce recommended bundles**

Fill this table in the memo (values below are the **hypothesis to confirm**):

| Bundle | Members | Why together | Preconditions | Suggested order |
| --- | --- | --- | --- | --- |
| Bundle 1 — Container body | D-ZEN (+ optional D-PLA only when Zen descriptors exist) | Same trust boundary; payload-only is worthless without real trailer map | Zen/IoStore fixtures (#624); no “buy samples” inside bundle | 1 |
| Bundle 2 — Property schema | D-SCHEMA | Orthogonal to layout; editor usmap path already partial | UE SchemaProvider evidence + cooked/unversioned fixtures | after or parallel to Bundle 1 if fixtures allow |
| Bundle 3 — Workflow CLI | D-BATCH + D-DIFF | Same CLI surface decision | User product need for batch orchestration | whenever product asks |
| Bundle 4 — Perf | D-G2 | Independent; helps extract_payload immediately | Multi-extract consumer | anytime |
| Bundle 5 — Blueprint depth | D-CPP (only if revived) | Only if product wants C++ skeleton; Gate K already retired pseudocode | Explicit product revival; not implied by Wave B | lowest priority |

D-PAK: evaluate whether it joins Bundle 1 or stays its own pack-index project; default **own project** unless Pak samples share the Zen IoStore trust path in source review.

- [ ] **Step D1.4: Write scratch memo `temp/d-deferred-bundling-memo.md`**

Sections: Capability inventory; Edge table (verified); Bundle recommendation; Explicit non-bundles; Open questions for the user (fixtures, product need for batch, whether C++ skeleton is ever wanted).

- [ ] **Step D1.5: Commit the decision record (docs only)**

Copy the durable parts into `docs/designs/2026-09-13-deferred-capability-bundling.md`:

```markdown
# Deferred Capability Bundling Record

> **Status:** current (evaluation record; **no implementation**)
> Date: 2026-09-13
> Branch context: post Wave A+B productize on `docs/productize-unversioned` / `dev-0.6.0`

## Capabilities evaluated
... (table from D1.1)

## Bundles
... (table from D1.3)

## Non-goals of this record
- Does not authorize Zen/Pak/SchemaProvider/batch/diff/C++ skeleton implementation.
- Does not change `fixture_gaps` or README feature claims.

## Next execution trigger
A new implementation plan is required before any Bundle N code lands.
```

```powershell
git add docs/designs/2026-09-13-deferred-capability-bundling.md
git commit -m "docs: record deferred capability bundling recommendation without implementation"
```

---

# Final Gates (this plan)

- [ ] **F1.** `git status -sb` clean on productize branch (or only `temp/` noise).
- [ ] **F2.** `ruff check` PASS.
- [ ] **F3.** `pytest -q` → 226 passed + 2 ucas.
- [ ] **F4.** `temp/decode_parity.py check` identical.
- [ ] **F5.** `dev-0.6.0` tip == productize tip; **no push**.
- [ ] **F6.** C notes exist; user received GO/NO-GO; no T15/T13 production edit unless separately authorized.
- [ ] **F7.** D bundling doc committed; zero production code in D.

---

## Execution Handoff

Two options:

1. **Subagent-Driven (recommended)** — one subagent per task (A1, A2, B1, B2, B3, C1, C2, D1), parent reviews between tasks.
2. **Inline Execution** — batch in this session with checkpoints after A, after B, after C/D.

Recommended sequence: A1 → A2 → (A3) → B1 → B2 → B3 → C1 → C2 → C3/user gate → D1. Do not parallelize A2 with B* (merge first keeps polish on a known tip).

## Self-Review Notes

- Spec coverage: A = merge+status; B = three review Minors; C = research gate for T15/T13; D = bundling evaluation only.
- No TBD placeholders; C/D intentionally stop at research/memo artifacts.
- Type consistency: no new runtime APIs; B3 only deletes a dead branch; B1 uses existing SAMPLES and projection API.
