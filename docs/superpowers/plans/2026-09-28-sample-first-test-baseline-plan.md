# Sample-First Test Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 36-module / 477-item test tree with a sample-first baseline of exactly two test modules and at most 100 collected pytest items, without changing `src/` or the sample corpus.

**Architecture:** `tests/test_samples.py` stays as the single manifest-driven sample driver; parameterized meta-checks are folded into small aggregate loops and synthetic-byte unit tests are deleted. Every other `test_*.py` module and `tests/fixtures.py` are removed in one atomic commit. `tests/conftest.py` shrinks from a fixture library to a collection-budget hook; `tests/test_size_baseline.py` gains a 2-module limit; `tests/size-baseline.json` is re-measured. Canonical design, Agent reference, and README are repointed at the two-file policy.

**Tech Stack:** Python 3.10+, pytest (importlib mode), ruff, git. Local blocking environment: Windows + Python 3.14.

**Spec:** `docs/superpowers/specs/2026-09-28-sample-first-test-baseline-design.md` (revised, committed in Task 1)

## Global Constraints

- At most 2 tracked test modules: `git ls-files 'tests/test_*.py' 'tests/**/test_*.py'` reports exactly 2 files.
- At most 100 collected pytest items (including parameterized), enforced by the `tests/conftest.py` collection hook so `python -m pytest -q` and CI cannot run an overgrown suite.
- Target inventory after this plan: **96 collected items** (93 in `test_samples.py` = 66 parse params + 3 golden params + 27 aggregates; 3 in `test_size_baseline.py`).
- `src/` has no diff from this migration (not even comment edits).
- `tests/samples/` content is unchanged: no sample, manifest, golden, or quality-baseline edit unless a check proves an existing expectation stale (then stop and raise — that is a separate reviewable data update).
- No `skip`, `xfail`, broad exception swallowing, or hidden collection paths.
- The sample driver does not manufacture UE package bytes and does not use mocks to stand in for package objects. Synthetic-byte/synthetic-structure tests are deleted (probes go to untracked `temp/` if still wanted).
- Temporary investigation files belong under untracked `temp/`; nothing new is tracked outside `tests/` + the three doc targets.
- Commit format: `<type>: <summary>` (`docs`, `test`, `chore` types here). Work happens on the current worktree branch.
- `python -m ruff check src/uasset_read tests/` and `git diff --check` pass at every commit point.

---

### Task 1: Lock spec + plan, verify clean baseline

**Files:**
- Modify: `docs/superpowers/specs/2026-09-28-sample-first-test-baseline-design.md` (already revised in working tree, currently uncommitted)
- Create: `docs/superpowers/plans/2026-09-28-sample-first-test-baseline-plan.md` (this file)

**Interfaces:**
- Produces: committed spec + plan as the shared reference for all later tasks.

- [ ] **Step 1: Verify the baseline**

Run: `python -m pytest -q`
Expected (already measured 2026-09-28 on this worktree): `1 failed, 476 passed` — the single failure is `test_docs_tree_within_baseline`: `docs_markdown: 60641 tracked lines exceeds baseline 60450 (files=171)`, caused by the revised spec's growth. Any OTHER failure means the workspace is dirty — stop and report it. The docs overrun is absorbed in Steps 2-3.

- [ ] **Step 2: Measure the post-commit docs ceiling**

The plan file is untracked, so `git ls-files` does not see it yet; add its line count manually:

```bash
python -c "
import subprocess, pathlib
out = subprocess.run(['git','ls-files','-z','docs/'], capture_output=True, check=True)
files = [f for f in out.stdout.decode('utf-8').split(chr(0)) if f.endswith('.md')]
total = sum(sum(1 for _ in open(f,'rb')) for f in files)
plan = pathlib.Path('docs/superpowers/plans/2026-09-28-sample-first-test-baseline-plan.md')
total += sum(1 for _ in plan.open('rb'))
print(f'files={len(files)+1} lines={total}')
"
```

Expected: `lines` = 60641 + plan-file lines (files=172).

- [ ] **Step 3: Raise `docs_markdown.max_lines` to the measured value**

In `tests/size-baseline.json`, set `docs_markdown.max_lines` to the `lines` value from Step 2 and append one `_note` sentence:
`Raised 2026-09-28 sample-first spec revision + plan doc from pre-commit measurement: docs_markdown to <lines> (files=172).`
No other key changes (`src_python`, `tests_python`, `wheel_bytes`, `docs_markdown.min_files` stay).

- [ ] **Step 4: Verify, then commit spec + plan + ceiling together**

```bash
python -m pytest tests/test_size_baseline.py -q   # expect 3 passed
git add docs/superpowers/specs/2026-09-28-sample-first-test-baseline-design.md docs/superpowers/plans/2026-09-28-sample-first-test-baseline-plan.md tests/size-baseline.json
git commit -m "docs: lock sample-first test baseline spec and plan"
```

(Measurement precedes commit so the raise lands in the same commit as the growth, per repo ratchet convention — Step 2's arithmetic reproduces exactly what `pytest` will count once the plan file is tracked.)

---

### Task 2: Fold `tests/test_samples.py` into the sample-first driver

`tests/test_samples.py` is rewritten in place. The other 34 modules and `tests/fixtures.py` still exist and the suite must still pass after this task (the old conftest fixtures stay untouched until Task 3).

**Files:**
- Modify: `tests/test_samples.py`

**Interfaces:**
- Consumes: nothing new; uses only `uasset_read.*`, `tools/gen_quality_baseline.py` (pytest `pythonpath = src tools`), and `tests/samples/*`.
- Produces: module-level names that survive into Task 3: `_asset_document`, `_object_document`, `_decode_document`, `_graph_owner_id`, `_sha256`, `_raw_depends_map` (self-contained after this task), `_golden_mapped_ids`, `CAPABILITIES`, `_assert_quality_baseline`, `_quality_baseline_include_opt_in`, `_quality_baseline_sample_names`, `_assert_trailing_aggregate`, `_aggregate_from_manifest`, `_UE5_SPLIT_SAMPLES`, `_open_sample_archive`. No import of `tests.fixtures` remains.

Final item inventory for this module (93 items):

| # | Test | Shape |
|---|------|-------|
| 1 | `test_manifest_matches_every_real_sample` | 1 item; absorbs the zero-asset-role manifest pin |
| 2 | `test_container_fixtures_match_manifest` | 1 |
| 3 | `test_fixture_gap_statuses_pin_the_capability_boundary` | 1 |
| 4 | `test_v2_tables_match_independent_golden_reference[...]` | 3 params, unchanged |
| 5 | `test_real_sample_proves_claimed_capability` | folded 27 params → 1 aggregate loop |
| 6 | `test_every_real_sample_forms_a_valid_package_document[...]` | 66 params, unchanged |
| 7 | `test_v2_path_emits_no_handler_warnings` | 1 |
| 8 | `test_object_depth_parses_only_requested_export` | 1 |
| 9 | `test_package_depth_has_no_properties` | 1 |
| 10 | `test_large_sample_all_exports` | 1 |
| 11 | `test_niagara_fixture_enriched_at_summary_tier` | 1 |
| 12 | `test_blueprint_fixtures_carry_generated_and_cdo_relations` | 1 |
| 13 | `test_blueprint_graph_decodes_without_parse_errors` | 1 |
| 14 | `test_als_graph_owners_resolve_beyond_eight_hops` | 1 |
| 15 | `test_iostore_toc_fixture_headers_match_ue_struct_fields` | 1 |
| 16 | `test_iostore_directory_index_lists_real_packages` | 1 |
| 17 | `test_iostore_toc_read_does_not_load_the_container` | 1 |
| 18 | `test_missing_sidecar_diagnostic` | folded 6 params → 1 aggregate loop |
| 19 | `test_quality_baseline_gate_behavior` | folded 5 meta items → 1 |
| 20 | `test_quality_baseline_diagnostics` | folded 10 params → 1 aggregate loop |
| 21 | `test_trailing_diagnostics_carry_structured_size` | 1 |
| 22 | `test_background_cue_sound_node_tails_reclassified_editor_only` | 1 |
| 23 | `test_level_geometry_tails_known_unimplemented_with_bytes` | 1 |
| 24 | `test_collision_and_enum_pose_movie_tails_known_unimplemented` | 1 |
| 25 | `test_trailing_aggregate_report_within_baseline` | 1 |
| 26 | `test_trailing_aggregate_gate_blocks_growth` | 1 |

Deleted from this module: `test_preload_relations_use_ue_ranges_and_sign_semantics`, `test_relation_targets_out_of_range_are_dropped_with_diagnostic`, `test_depends_map_validates_package_index_sign_per_ue_convention`, `test_preload_relations_report_invalid_ranges_without_crashing`, `_synthetic_export`, and `test_zero_asset_role_fixture_is_manifested` (its three assertions move into the manifest test).

- [ ] **Step 1: Inline `open_sample_archive` and drop the `tests.fixtures` imports**

Add this helper next to `_raw_depends_map` (body copied verbatim from `tests/fixtures.py:26-50`), then point both `_raw_depends_map` (line ~257) and `test_als_graph_owners_resolve_beyond_eight_hops` (line ~879) at it:

```python
from contextlib import contextmanager

@contextmanager
def _open_sample_archive(sample):
    """Open a fixture archive and yield (archive, summary, name_map, import_map, export_map)."""
    from uasset_read.package import open_package_bundle
    from uasset_read.serializers.object_resources import read_export_map, read_import_map
    from uasset_read.serializers.package_summary import read_name_table, read_package_summary

    archive = open_package_bundle(str(sample)).open_archive(tolerant=True)
    try:
        summary, _ = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        archive.set_name_map(name_map)
        yield (
            archive,
            summary,
            name_map,
            read_import_map(archive, summary, name_map),
            read_export_map(archive, summary, name_map),
        )
    finally:
        archive.close()
```

Replace `from tests.fixtures import open_sample_archive` with `_open_sample_archive` in both call sites (the `als` call site imports it at line 879 inside the function; `_raw_depends_map` imports it at line 257).

- [ ] **Step 2: Absorb the zero-asset-role pin into the manifest test**

Append to `test_manifest_matches_every_real_sample` (after the golden block, line ~325):

```python
    # Zero-asset-role fixture is part of the pinned manifest contract
    # (was tests/test_samples.py::test_zero_asset_role_fixture_is_manifested).
    zero = MANIFEST_BY_NAME["uasset_rs_UE410_SimpleRefsSoftRef.uasset"]
    assert zero["size_bytes"] == 4037
    assert zero["engine_layout"] == "legacy"
    assert zero["export_count"] == 6
    assert zero["b_is_asset_count"] == 0
```

Then delete `test_zero_asset_role_fixture_is_manifested` (lines ~680-685).

- [ ] **Step 3: Fold the 27 capability params into one aggregate loop**

Replace the `@pytest.mark.parametrize` decorator (lines ~436-440) and the parameter list of `test_real_sample_proves_claimed_capability` with a loop, keeping the name:

```python
def test_real_sample_proves_claimed_capability():
    """Each claimed capability must produce stable semantics from a real fixture.

    The status column pins the #629 tier contract: decoded-tier fixtures are
    ``complete``; summary-tier fixtures prove ``partial`` with coverage.
    Loops the CAPABILITIES table so 27 claims cost one collected item; every
    assertion message carries ``sample:class_name``.
    """
    for sample, class_name, expected, expected_semantic in CAPABILITIES:
        doc = _asset_document(sample)
        obj = next(item for item in doc.objects if item.class_name == class_name)
        assert obj.status.semantic == expected_semantic, f"{sample}:{class_name}"
        assert obj.coverage, f"{sample}:{class_name}"
        assert {key: obj.semantic[key] for key in expected} == expected, f"{sample}:{class_name}"
        # ... existing per-class branch bodies (lines 455-544) run inside this loop,
        # with every bare assert given an f"{sample}:{class_name}" message ...
```

Mechanical rules for the branch bodies moved into the loop (lines 455-544 of the current file):

- Keep every branch verbatim otherwise; only rewrite bare asserts (`assert obj.semantic["bone_count"] == ...`, `assert "spine_01" in names ...`, the StaticMesh `lod_count`, AnimBlueprint node/link asserts) to include `f"{sample}:{class_name}"` (or `f"{sample}: dangling link"` as already written) in the message.
- The `Skeleton` branch (lines 465-474) currently has four message-less asserts — all four get messages.
- The `PhysicsAsset` and `PhysicalMaterial` branches already carry messages; unchanged.

- [ ] **Step 4: Fold the sidecar diagnostics into one loop**

Replace the parametrize on `test_missing_sidecar_diagnostic` (lines ~1009-1013) with:

```python
def test_missing_sidecar_diagnostic():
    """A split package without its .uexp emits PACKAGE_SIDECAR_MISSING."""
    import shutil
    import tempfile

    from uasset_read.package import parse_package_document

    for sample_entry in _UE5_SPLIT_SAMPLES:
        main_path = SAMPLES / sample_entry["name"]
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / main_path.name
            shutil.copy2(main_path, dst)
            # Do NOT copy the .uexp — simulate missing sidecar.
            doc = parse_package_document(dst, depth="package")
            codes = [d.code for d in doc.diagnostics]
            assert "PACKAGE_SIDECAR_MISSING" in codes, (
                f"expected PACKAGE_SIDECAR_MISSING for {sample_entry['name']}, got: {codes}"
            )
```

- [ ] **Step 5: Fold the quality meta checks into `test_quality_baseline_gate_behavior`**

Replace `test_quality_baseline_fail_paths` (lines ~1069-1097), `test_quality_baseline_sample_names_excludes_opt_in_by_default` (~1117), `test_quality_baseline_sample_names_includes_opt_in_when_enabled` (~1132), and `test_quality_baseline_opt_in_env_flag` (~1146) with one test:

```python
def test_quality_baseline_gate_behavior():
    """Fail paths and opt-in plumbing of the quality gate itself (was 5 items).

    forbid_unlisted rejects new (code, reason) pairs; max_total_diagnostics
    rejects overflow; opt-in entries stay out of the default sample set.
    """
    cases = [
        (
            {
                "forbid_unlisted": True,
                "max_by_code_reason": {"EXPORT_TRAILING_BYTES_UNCONSUMED": {"editor_only": {"max": 1}}},
            },
            [
                SimpleNamespace(code="EXPORT_TRAILING_BYTES_UNCONSUMED", reason="editor_only"),
                SimpleNamespace(code="NAME_INDEX_OUT_OF_RANGE", reason="recovered_corruption"),
            ],
            "unlisted",
        ),
        (
            {"max_total_diagnostics": 0, "max_by_code_reason": {}},
            [SimpleNamespace(code="EXPORT_TRAILING_BYTES_UNCONSUMED", reason="editor_only")],
            "total diagnostics",
        ),
    ]
    for entry, diags, match in cases:
        name = "__fail_path__"
        QUALITY_BASELINE["samples"][name] = {**entry, "forbidden_codes": []}
        try:
            with pytest.raises(AssertionError, match=match):
                _assert_quality_baseline(SimpleNamespace(diagnostics=diags), name)
        finally:
            QUALITY_BASELINE["samples"].pop(name, None)

    default_only = {"A.uasset": {"opt_in": False}, "B.uasset": {"opt_in": True}, "C.uasset": {}}
    assert _quality_baseline_sample_names(False, samples=default_only) == ["A.uasset", "C.uasset"]
    assert _quality_baseline_sample_names(True, samples=default_only) == ["A.uasset", "B.uasset", "C.uasset"]

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("UASSET_QUALITY_OPT_IN", "1")
        assert _quality_baseline_include_opt_in() is True
    assert _quality_baseline_include_opt_in() is False
```

(`_quality_baseline_sample_names` signature is `(include_opt_in, samples=None)`; the `MonkeyPatch.context()` form replaces the old `monkeypatch` fixture because the fold no longer runs as a fixture-injected test.)

- [ ] **Step 6: Fold the 10 quality-diagnostic params into one loop**

Replace the parametrize on `test_quality_baseline_diagnostics` (lines ~1153-1156) with:

```python
def test_quality_baseline_diagnostics():
    from uasset_read.package import parse_package_document
    from uasset_read.projection import project_document

    names = _quality_baseline_sample_names(_quality_baseline_include_opt_in())
    assert names, "quality_baseline.json must list at least one default sample"
    for sample_name in names:
        doc = parse_package_document(str(SAMPLES / sample_name), depth="asset")
        page = project_document(doc)
        jsonschema.validate(page, SCHEMA)
        _assert_quality_baseline(doc, sample_name)
```

(`_assert_quality_baseline` messages already carry `sample_name`.)

- [ ] **Step 7: Delete the four synthetic-structure tests**

Remove `test_preload_relations_use_ue_ranges_and_sign_semantics` (lines ~721-748), `test_relation_targets_out_of_range_are_dropped_with_diagnostic` (~751-770), `test_depends_map_validates_package_index_sign_per_ue_convention` (~773-802), `test_preload_relations_report_invalid_ranges_without_crashing` (~805-824), and `_synthetic_export` (~705-718). Optionally park the bodies in untracked `temp/probes_synthetic_relations.py` first — they are investigation material now, not baseline.

- [ ] **Step 8: Update the module docstring**

The header (lines 1-14) still says "64-fixture matrix", mentions the former `tests/contract/` layer, and justifies the pyright pragmas. Replace with:

```python
"""Sample-first behavior baseline: every tracked check is driven by real samples.

Manifest-driven parse items (one per package) plus a small set of aggregate
checks for manifest closure, golden references, capability claims, quality
ceilings, containers, and sidecars. The collection budget (<=100 suite-wide
items) lives in tests/conftest.py; size and module-count ratchets live in
tests/test_size_baseline.py.

This file deliberately feeds duck-typed stub archives/exports to internal helpers, so the
strict-object rules are off here; ``src/uasset_read`` remains the pyright gate (ci.yml).
"""
```

- [ ] **Step 9: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS. Total collected drops from 477 to ~448 (only test_samples changed; other modules unchanged). No new failures — if a fold lost an assertion, fix the fold, do not delete the assertion.

- [ ] **Step 10: Lint and commit**

```bash
python -m ruff check src/uasset_read tests/
git diff --check
git add tests/test_samples.py
git commit -m "test: fold test_samples into sample-first aggregates"
```

---

### Task 3: Atomic replacement — delete the legacy suite, arm the budgets

Constraints.md requires the delete+replace to land as one atomic change; this whole task is a single commit. Order matters: delete modules first, then rewrite conftest, then measure.

**Files:**
- Delete: all 34 tracked `test_*.py` modules except `tests/test_samples.py` and `tests/test_size_baseline.py` (list = `git ls-files 'tests/test_*.py' 'tests/**/test_*.py'` minus those two; includes `tests/serialization/test_package_summary_tag.py` and the whole `tests/serialization/` subtree)
- Delete: `tests/fixtures.py`
- Modify: `tests/conftest.py` (full rewrite)
- Modify: `tests/__init__.py` (comment only)
- Modify: `tests/test_size_baseline.py` (module-count limit)
- Modify: `tests/size-baseline.json` (re-measure)

**Interfaces:**
- Consumes: Task 2's self-contained `test_samples.py` (no `tests.fixtures` imports).
- Produces: the two-file tree the docs describe in Task 4; `BASELINE["tests_python"]["min_files"] == 4`; suite-wide collection == 96.

- [ ] **Step 1: Delete the legacy modules and fixtures.py**

```bash
git ls-files 'tests/test_*.py' 'tests/**/test_*.py' | grep -v -e 'tests/test_samples.py' -e 'tests/test_size_baseline.py' | xargs git rm
git rm tests/fixtures.py
```

After this, the tracked test tree is exactly: `tests/__init__.py`, `tests/conftest.py`, `tests/test_samples.py`, `tests/test_size_baseline.py`, `tests/size-baseline.json`, `tests/samples/**`.

- [ ] **Step 2: Replace `tests/conftest.py` with the collection-budget hook**

Full file content:

```python
"""Collection budget: the sample-first baseline may not grow past 100 items.

Spec: docs/superpowers/specs/2026-09-28-sample-first-test-baseline-design.md
No fixtures live here — the baseline is driven by real samples in
tests/test_samples.py; temporary probes belong to untracked temp/.
"""

from __future__ import annotations

import pytest

ITEM_BUDGET = 100


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    if len(items) > ITEM_BUDGET:
        raise pytest.UsageError(
            f"collected {len(items)} items, sample-first budget is {ITEM_BUDGET}; "
            "fold checks into sample-backed aggregates or move probes to temp/"
        )
```

- [ ] **Step 3: Update the `tests/__init__.py` comment**

Full file content:

```python
# Package marker so ``tests`` resolves as an importable package under
# pytest's importlib import mode (sample-first baseline).
```

- [ ] **Step 4: Add the tracked test-module limit to `tests/test_size_baseline.py`**

Add a helper next to `_tracked_files()`:

```python
def _test_modules() -> list[str]:
    # Both pathspecs: the acceptance command counts top-level and nested modules,
    # and neither pattern alone matches the other's directories.
    out = subprocess.run(
        ["git", "ls-files", "-z", "tests/test_*.py", "tests/**/test_*.py"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [entry for entry in out.stdout.decode("utf-8").split("\0") if entry]
```

Extend `test_test_tree_within_baseline`:

```python
def test_test_tree_within_baseline():
    _assert_area("tests_python", "tests/", ".py")
    modules = _test_modules()
    assert len(modules) <= 2, (
        f"tracked test modules {modules} exceed the sample-first limit of 2 "
        "(docs/superpowers/specs/2026-09-28-sample-first-test-baseline-design.md)"
    )
```

The 100-item budget is NOT duplicated here — only the collection hook enforces it (spec).

- [ ] **Step 5: Run the suite once to read the measured failure output**

Run: `python -m pytest tests/test_size_baseline.py -q`
Expected: FAIL on `tests_python` with measured `files=` and line counts (the old `min_files: 13` now over-counts the 4 remaining `.py` files, and `max_lines` no longer matches).

- [ ] **Step 6: Re-measure and update `tests/size-baseline.json`**

- `tests_python.min_files`: set to the actual tracked `.py` count under `tests/` — **4** (`__init__.py`, `conftest.py`, `test_samples.py`, `test_size_baseline.py`).
- `tests_python.max_lines`: set to the exact measured post-cleanup line total from Step 5's failure output (expect roughly 8–9k; use the measured number, not an estimate).
- `src_python` and `wheel_bytes`: unchanged.
- `docs_markdown`: unchanged in this task (Task 4's doc edits re-measure it).
- Append one sentence to `_note`, per repo convention, e.g.:
  `Tightened 2026-09-28 sample-first baseline (two-module suite): tests_python min_files 13->4, max_lines to measured post-cleanup total from pytest failure output.`

- [ ] **Step 7: Verify budgets and the full suite**

```bash
python -m pytest --collect-only -q
```
Expected: `96 tests collected` (93 + 3), exit 0.

```bash
python -m pytest -q
```
Expected: PASS, 96 passed, 0 failures.

- [ ] **Step 8: Prove the hook actually fires (manual negative check)**

Temporarily edit `tests/conftest.py`: `ITEM_BUDGET = 50`.
Run: `python -m pytest --collect-only -q`
Expected: exit code 4 (UsageError) with message `collected 96 items, sample-first budget is 50`.
Restore `ITEM_BUDGET = 100`. Re-run collect-only: exit 0.
(If `pytest_collection_modifyitems` raising UsageError does not surface as a clean failure on this pytest version, switch the hook to `pytest_collection_finish(session)` reading `len(session.items)` — same message, same budget — and re-run this check.)

- [ ] **Step 9: Verify module count and lint**

```bash
git ls-files 'tests/test_*.py' 'tests/**/test_*.py'
```
Expected: exactly `tests/test_samples.py` and `tests/test_size_baseline.py`.

```bash
python -m ruff check src/uasset_read tests/
git diff --check
```
Expected: both clean. Fix unused imports in `test_samples.py` if ruff flags leftovers from the folds.

- [ ] **Step 10: Commit the atomic replacement**

```bash
git add -A tests/
git commit -m "test: replace legacy suite with two-module sample-first baseline"
```

---

### Task 4: Repoint docs at the two-file policy, final acceptance

**Files:**
- Modify: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` (~lines 821-825, the AST-gate bullet block)
- Modify: `docs/reference/agent-dev-reference.md:30`
- Modify: `README.md` (Testing section, ~lines 219-240)
- Possibly modify: `tests/size-baseline.json` (`docs_markdown` re-measure)

**Interfaces:**
- Consumes: Task 3's tree (2 modules, 96 items) — the docs must describe exactly that.
- Produces: acceptance evidence for the spec's final checklist.

- [ ] **Step 1: Replace the canonical design's three-file/AST-gate policy**

In `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`, replace the block headed `标准库 AST 门禁要求（策略门禁，2026-09-16 Task 1 起替代旧的精确清单/计数锁定）：` and its three bullets (lines ~821-825) with:

```markdown
- sample-first 两文件基线（2026-09-28，spec：`docs/superpowers/specs/2026-09-28-sample-first-test-baseline-design.md`）：
  - 正式测试模块至多两个：`tests/test_samples.py`（manifest 驱动的真实样本驱动）与 `tests/test_size_baseline.py`（体积 + 测试文件数门禁）。计数命令为 `git ls-files 'tests/test_*.py' 'tests/**/test_*.py'`（两个 pathspec 都要，顶层模式不匹配嵌套目录），`tests/test_size_baseline.py` 断言结果至多 2 个文件。
  - pytest 收集项（含参数化）至多 100，由 `tests/conftest.py` 的 collection-budget hook 在收集阶段强制；`python -m pytest -q` 与 CI 走同一命令，无需第二个 runner。
  - 永久子树仅 `tests/samples/`；不再有 `tests/serialization/` 或其他 `test_*.py`。`tests/conftest.py` 只含收集预算 hook，不承载 fixture。合成字节、malformed 实验与一次性 CLI 检查走未跟踪 `temp/`，不进入基线与 CI。
```

- [ ] **Step 2: Update the Agent reference test contract**

In `docs/reference/agent-dev-reference.md`, replace line 30:

```markdown
- 正式测试契约为 sample-first 两文件基线：`tests/test_samples.py`（manifest 驱动的真实样本驱动：manifest 闭合、66 项样本 parse、golden、capability、quality、容器与 sidecar 聚合检查）与 `tests/test_size_baseline.py`（体积 + 2 模块上限门禁）；全树收集项至多 100（`tests/conftest.py` 收集预算 hook）。无 `tests/contract/`、`tests/serialization/` 与其他测试模块；临时调查走未跟踪 `temp/`。
```

- [ ] **Step 3: Update the README Testing section**

In `README.md`, insert immediately after the `## Testing` heading line (before the first code fence):

```markdown
The tracked baseline is intentionally small: two test modules
(`tests/test_samples.py`, `tests/test_size_baseline.py`) and at most 100
collected pytest items (enforced during collection by `tests/conftest.py`).
```

Keep the existing commands unchanged — `python -m pytest tests/ -v` and `-k quality_baseline` still select the folded `test_quality_baseline_*` tests by name.

- [ ] **Step 4: Run the full acceptance sequence**

```bash
python -m pytest --collect-only -q     # expect 96 tests collected
python -m pytest -q                    # expect 96 passed
python -m ruff check src/uasset_read tests/   # expect clean
git diff --check                       # expect clean
git ls-files 'tests/test_*.py' 'tests/**/test_*.py'   # expect exactly 2
git diff b6f5b59f --stat -- src/       # expect empty (no src diff from this migration)
git diff b6f5b59f --stat -- tests/samples/  # expect empty (corpus unchanged)
```

If `docs_markdown` size baseline now fails, re-measure from the failure output and set `max_lines` (and `min_files` if doc files were added/removed) in `tests/size-baseline.json`, appending a one-line `_note`; rerun `python -m pytest -q`.

- [ ] **Step 5: Consistency read-through**

Skim the four artifacts named by the spec's acceptance criteria — canonical design, `agent-dev-reference.md`, README, `tests/size-baseline.json` — and confirm each states the same target: 2 modules, 100 items, samples-only subtree. Also confirm `grep -rn "test_core" docs/reference/agent-dev-reference.md docs/designs/2026-08-26-package-first-uasset-parser-refactor.md README.md` returns no `test_core` hits.

- [ ] **Step 6: Commit docs**

```bash
git add docs/designs/2026-08-26-package-first-uasset-parser-refactor.md docs/reference/agent-dev-reference.md README.md tests/size-baseline.json
git commit -m "docs: repoint test contract at sample-first baseline"
```

(`tests/size-baseline.json` only if Step 4 needed a docs re-measure; otherwise omit it from the add list.)

---

## Self-Review notes (plan author)

- Spec coverage: target structure (Task 3), hard limits 2/100 (Tasks 3-4), sample driver design (Task 2), size baseline ratchet + module limit (Task 3), conftest hook-only (Task 3), temp/ probes policy (documented in hook + docs), migration docs updates (Task 4), acceptance criteria (Task 4 Step 4-5).
- Budget math: 96 ≤ 100 items; aggregates 27 < 34; parse params 66 exactly.
- `src/` untouched: the stale `tests/fixtures.find_function` comment in `src/uasset_read/parsers/blueprint/correlation.py:1082` stays (spec forbids src diffs).
- Type/name consistency: `_open_sample_archive` defined in Task 2 Step 1 is the only archive helper; `ITEM_BUDGET` in conftest is the single budget constant; `_test_modules` in size baseline mirrors the acceptance pathspec command exactly.
