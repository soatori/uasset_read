# v2 Package-First Recovery & Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

> **Status:** Recovery plan. Closes the gap between the current committed code and the acceptance gates of the canonical execution plan. Does not re-derive the target architecture — that is already authoritative in the design doc.

**Goal:** Make the v2 package-first pipeline honestly green and documented: byte-bounded projection, schema-validated output, no broken/duplicate tests, no dead adapter code, and current documentation.

**Architecture:** The core pipeline (LegacyPackageReader → tagged properties → handlers → PackageDocument → projection) already works end-to-end on every tracked sample (verified: semantics produced for DataTable/Texture/Sound/Skeleton/Mesh/AnimBlueprint). This plan hardens the remaining correctness gaps — projection byte-budget, schema/projection drift, weak/broken tests, dead adapter, and documentation/CI drift — without touching the working reader, property parser, or handler logic.

**Tech Stack:** Python 3.10+ (local gate: Windows/3.14), standard library, existing `uasset_read` serializers, pytest, Ruff, JSON Schema (jsonschema 4.26.0 already installed), GitHub Actions.

**Spec:** `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` (authoritative target architecture) and `docs/plans/2026-08-28-package-first-refactor-execution-plan.md` (canonical task chain this plan closes out).

## Verified Baseline (this plan's starting point)

Snapshot gathered before writing this plan:

- Branch: `dev-0.6.0`, HEAD `cec8a6b3 docs: synchronize package-first implementation status`
- Dirty tree: only cosmetic Ruff line-length reformatting in `projection.py`, `properties.py`, and 3 test files (no logic changes).
- Collected tests: 303. Known red:
  - `tests/test_schema_contract.py`: **2 failures** (`test_projection_output_validates`, `test_all_views_validate`) — projection emits `next_offset`/`truncation`/`debug`/`flags` rejected by `additionalProperties:false` schema.
  - `tests/v2/test_handlers.py`: **4 failures** — unpacks `run_handlers` as a 2-tuple (it returns 3), re-runs the v1 pipeline, and wraps assertions in `if semantic is not None`.
  - `tests/v2/` (full): >5 min runtime (timed out) — re-parses every sample and re-invokes the v1 pipeline.
- Working (verified by probe `temp/probe_v2_state.py`): properties parse non-empty on every sample; semantics produced for DataTable, Texture2D, SoundWave, Skeleton, StaticMesh, AnimBlueprint. CLI has `--v2 --depth --limit --max-bytes` and calls `project_document`. All 6 agent tools call `project_document(..., max_bytes=...)`. Ruff clean. jsonschema 4.26.0 installed.
- Audit claims that turned out **stale** (do not re-fix): "tagged property parsing all fails" (false — legacy.py:407 passes the full archive, property_parser.py:1163 seeks absolute offsets against the full-file SliceReader, works), "run_handlers called with None" (false — legacy.py:322 passes `(export_map, name_map)`), "CLI/Agent ignore projection" (false), "113/262 tests" (actual 303).

## File Responsibility Map (this plan's scope)

| File | Change in this plan |
| --- | --- |
| `src/uasset_read/v2/projection.py` | Guarantee `len(encoded) <= max_bytes`; scope relations + object diagnostics to the returned object page |
| `docs/designs/contract/package_document_v2.schema.json` | Add optional `next_offset`/`truncation`/`debug` (root) and `flags` (ObjectEntry) so all views validate |
| `tests/test_schema_contract.py` | Drop the 3 `pytest.skip("jsonschema not installed")` guards; import jsonschema at module top |
| `tests/test_projection_contract.py` | Add byte-budget + page-scoping regression tests |
| `tests/test_property_contract.py` | Replace `is not None` weak assertions with non-empty + zero-failure gates on healthy samples |
| `tests/v2/*.py` (5 files) | Delete — root contracts are a strict, fast superset |
| `src/uasset_read/v2/package/__init__.py` | Delete dead `build_package_document()` adapter and its private helpers (zero callers) |
| `tests/samples/manifest.json` | Fix "All 47 samples" → 48 |
| `docs/reference/agent-dev-reference.md` | Record the current implementation boundary (legacy+tagged+sample-backed handlers done; Zen/unversioned/payload deferred) |
| `README.md` | Correct test count; scope the "implemented" claim to what the gate proves |
| `docs/plans/2026-08-28-package-first-refactor-execution-plan.md` | Update baseline count and check off Tasks 1–9 that this recovery verifies |
| `.github/workflows/ci.yml` | Add a pytest job |

## Dependency Order

`Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 6 -> Task 7`

Task 1 (projection behavior) must precede Task 2 (schema matches that behavior). Tasks 3–6 are independent of each other but all precede the final gate (Task 7).

## Global Constraints

- Python `>=3.10`; the blocking local gate is Windows with Python 3.14.
- Core behavior cross-platform; first v2 milestone is read-only.
- Every output byte budget is bounded before use; `project_document(max_bytes=...)` must never emit more than `max_bytes` bytes of compact UTF-8 JSON.
- Library code returns structured diagnostics and never configures process-global logging.
- No `skip`/`xfail`/broad-exception aggregate tests; missing optional dependencies fail collection, not skip.
- Investigation scripts stay under ignored `temp/`; reusable checks live in `tests/`.
- Preserve unrelated dirty changes in the worktree.
- The v1 pipeline (`parse_uasset_with_linker` etc.) is a compatibility consumer and is NOT removed in this plan; only the dead v1→v2 adapter `build_package_document()` is removed.

---

### Task 1: Enforce the projection byte budget and scope envelope to the object page

Closes execution-plan Task 5 remainder. The current `max_bytes` block adds the `TRUNCATED` diagnostic *after* measuring, so the final encoded output can exceed the budget, and relations/diagnostics are emitted for the whole document rather than the returned page.

**Files:**

- Modify: `src/uasset_read/v2/projection.py:101-197` (selection/pagination/envelope/max_bytes)
- Test: `tests/test_projection_contract.py` (append `TestByteBudget` class)

**Interfaces:**

- Consumes: `select_objects`, `paginate`, `PackageDocument`.
- Produces: `project_document(...)` where, when `max_bytes` is set, the compact UTF-8 encoding of the returned dict is guaranteed `<= max_bytes`; relations are filtered to those whose `from` is in the returned object page; diagnostics with an `object_id` are filtered to the page (package-level diagnostics with `object_id is None` are always kept).

- [x] **Step 1: Write the failing byte-budget and page-scoping tests**

Append to `tests/test_projection_contract.py`:

```python
class TestByteBudget:
    def test_max_bytes_is_enforced_and_continuable(self, doc):
        import json as _json
        from uasset_read.v2.projection import project_document

        page = project_document(doc, limit=100, max_bytes=4096)
        encoded = _json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        assert len(encoded) <= 4096
        assert page["truncation"]["reason"] == "max_bytes"
        assert page["next_offset"] > 0
        assert any(d["code"] == "TRUNCATED" for d in page["diagnostics"])

    def test_relations_scoped_to_returned_page(self, doc):
        from uasset_read.v2.projection import project_document

        page = project_document(doc, limit=2)
        page_ids = {o["id"] for o in page["objects"]}
        assert len(page_ids) == 2
        for r in page["relations"]:
            assert r["from"] in page_ids

    def test_object_diagnostics_scoped_to_page(self, doc):
        from uasset_read.v2.projection import project_document

        page = project_document(doc, limit=2)
        page_ids = {o["id"] for o in page["objects"]}
        for d in page["diagnostics"]:
            oid = d.get("object_id")
            assert oid is None or oid in page_ids

    def test_budget_too_small_raises(self, doc):
        from uasset_read.v2.projection import project_document

        with pytest.raises(ValueError, match="too small"):
            project_document(doc, max_bytes=64)

    def test_no_truncation_when_budget_generous(self, doc):
        from uasset_read.v2.projection import project_document

        page = project_document(doc, limit=2, max_bytes=1_000_000)
        assert page.get("truncation") is None or page["truncation"].get("reason") != "max_bytes"
```

- [x] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_projection_contract.py::TestByteBudget -q`

Expected: FAIL — `test_relations_scoped_to_returned_page` and `test_object_diagnostics_scoped_to_page` fail because relations/diagnostics are currently emitted for the whole document; `test_max_bytes_is_enforced_and_continuable` may fail because the TRUNCATED diagnostic is added after measurement.

- [x] **Step 3: Scope relations and diagnostics to the returned page**

In `project_document`, immediately after the `page, next_offset, truncation_info = paginate(...)` call and **before** the `if fields:` block (which reassigns `page` from `ObjectRecord` objects to dicts), compute the page id set from the paginated `ObjectRecord` list:

```python
    page_ids = {o.id for o in page}
    relations = [
        {"kind": r.kind, "from": r.from_id, "to": r.to_id}
        for r in doc.relations
        if r.from_id in page_ids
    ]
    page_diagnostics = [
        d for d in doc.diagnostics
        if getattr(d, "object_id", None) is None or getattr(d, "object_id", None) in page_ids
    ]
```

Then in the `result` dict, replace the `relations` line with `relations` (the scoped list above), and replace `"diagnostics": [d.to_dict() for d in doc.diagnostics]` with `"diagnostics": [d.to_dict() for d in page_diagnostics]`.

- [x] **Step 4: Rewrite the max_bytes block to guarantee the bound**

Replace the `if max_bytes is not None:` block with logic that measures *after* the TRUNCATED diagnostic is appended and re-truncates until it fits:

```python
    if max_bytes is not None:
        def _encoded() -> int:
            return _json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8").__len__()

        if _encoded() > max_bytes:
            trunc_diag = {
                "severity": "warning",
                "code": "TRUNCATED",
                "message": f"Output truncated to fit {max_bytes}-byte budget",
                "stage": "projection",
                "recoverable": True,
            }
            result["diagnostics"].append(trunc_diag)
            while len(result["objects"]) > 0 and _encoded() > max_bytes:
                result["objects"].pop()
            actual = _encoded()
            if actual > max_bytes:
                raise ValueError(
                    f"Output budget {max_bytes} bytes too small for minimal envelope ({actual} bytes)"
                )
            objects_dropped = len(selected) - len(result["objects"])
            result["truncation"] = {
                "reason": "max_bytes",
                "budget": max_bytes,
                "actual": actual,
                "objects_dropped": objects_dropped,
            }
            result["next_offset"] = offset + len(result["objects"])
```

- [x] **Step 5: Run the focused projection contract**

Run: `python -m pytest tests/test_projection_contract.py -q`

Expected: PASS, including the new `TestByteBudget` class and the existing pagination/view tests. `test_page_through_all` still passes because it only compares object counts.

- [x] **Step 6: Verify the application equality test still holds**

Run: `python -m pytest tests/test_application_contract.py::TestProjectionEquality -q`

Expected: PASS — CLI, Agent, and Python projection still produce identical object IDs and diagnostics for `limit=2, max_bytes=4096`.

- [x] **Step 7: Commit**

```powershell
git add src/uasset_read/v2/projection.py tests/test_projection_contract.py
git commit -m "fix: enforce projection byte budget and scope envelope to object page"
```

---

### Task 2: Sync the JSON schema to real projection output

Closes execution-plan Task 5 schema gate. The schema is `additionalProperties:false` but projection legitimately emits `next_offset`, `truncation`, `debug` (root) and `flags` (ObjectEntry, raw/debug). Two schema tests currently fail.

**Files:**

- Modify: `docs/designs/contract/package_document_v2.schema.json:137-192` (ObjectEntry), `:8-72` (root)
- Modify: `tests/test_schema_contract.py:32-35,44-47,56-59` (drop skips)
- Modify: `pyproject.toml` (ensure `jsonschema` is a declared test dependency)

**Interfaces:**

- Consumes: the projection output shape fixed in Task 1.
- Produces: a schema against which `semantic`, `raw`, and `debug` views all validate; a schema contract test with no `skip`.

- [x] **Step 1: Confirm the current failures**

Run: `python -m pytest tests/test_schema_contract.py -q`

Expected: `test_projection_output_validates` and `test_all_views_validate` FAIL with `jsonschema.ValidationError` (Additional properties not allowed).

- [x] **Step 2: Add optional envelope properties to the root schema**

In `package_document_v2.schema.json`, add these three optional properties inside the root `"properties": { ... }` block (alongside `"summary"`):

```json
    "next_offset": {
      "type": "integer",
      "minimum": 0,
      "description": "Continuation cursor when objects were truncated."
    },
    "truncation": {
      "type": "object",
      "description": "Truncation metadata emitted when limit or max_bytes cut the page.",
      "properties": {
        "reason": { "type": "string" },
        "total": { "type": "integer" },
        "offset": { "type": "integer" },
        "returned": { "type": "integer" },
        "truncated": { "type": "integer" },
        "budget": { "type": "integer" },
        "actual": { "type": "integer" },
        "objects_dropped": { "type": "integer" }
      },
      "additionalProperties": false
    },
    "debug": {
      "type": "object",
      "description": "Extra parse statistics for the debug view.",
      "additionalProperties": true
    }
```

- [x] **Step 3: Add optional `flags` to ObjectEntry**

Inside `ObjectEntry.properties` (after `"diagnostics"`), add:

```json
        "flags": {
          "type": "integer",
          "description": "EObjectFlags raw value (raw/debug views only)."
        }
```

- [x] **Step 4: Drop the `pytest.skip` guards in the schema test**

In `tests/test_schema_contract.py`, remove the module-level `import pytest` only if unused after the edit (it is still used by `TestSchemaValidation`? No — only the skips use it; the file has no `pytest.raises`/`fixture` decorations, so remove the `import pytest` line too). Add a hard top-level dependency instead. Replace the three `try/except ImportError: pytest.skip(...)` blocks in `test_example_validates_against_schema`, `test_projection_output_validates`, and `test_all_views_validate` by removing the try/except wrapper and calling `jsonschema.validate(...)` directly. Add at the top of the file:

```python
import jsonschema  # required test dependency; collection fails fast if missing
```

- [x] **Step 5: Ensure jsonschema is a declared test dependency**

Inspect `pyproject.toml`. If `jsonschema` is not present in the `test` (or `dev`) optional-dependency group, add it. For example, if the group is named `test`:

```toml
[project.optional-dependencies]
test = [
    # ...existing entries...
    "jsonschema>=4",
]
```

If a `requirements-dev.txt` is used instead, add `jsonschema>=4` there. Verify with `python -c "import jsonschema"` after install.

- [x] **Step 6: Run the schema contract**

Run: `python -m pytest tests/test_schema_contract.py -q`

Expected: PASS for all 5 tests, with no `skip` collected (`pytest -rs` reports no skips).

- [x] **Step 7: Commit**

```powershell
git add docs/designs/contract/package_document_v2.schema.json tests/test_schema_contract.py pyproject.toml
git commit -m "fix: sync package document schema to projection output"
```

---

### Task 3: Strengthen property contract assertions on healthy samples

Closes execution-plan Task 4's "healthy samples zero property failure" gate. Current property tests assert `obj.properties is not None`, which passes even when the failure path wrote `{`. The probe shows properties are healthy, so this task locks that invariant with real gates.

**Files:**

- Modify: `tests/test_property_contract.py:74-102` (`TestObjectDepthSelection`)

**Interfaces:**

- Consumes: `parse_package_document` at `depth="object"`.
- Produces: assertions that every healthy legacy sample yields non-empty properties for non-trivial exports and zero `EXPORT_PROPERTY_PARSE_FAILED` diagnostics.

- [x] **Step 1: Add the healthy-sample gates**

Append to `tests/test_property_contract.py`:

```python
class TestHealthySamplePropertyGates:
    """Healthy legacy samples must produce real properties, not empty failure fallbacks."""

    def test_requested_export_has_nonempty_properties(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object", object_ids=["export:1"])
        obj = doc.objects[1]
        assert obj.properties is not None
        assert len(obj.properties) > 0, "export:1 has an empty property bag — likely a silent parse failure"

    def test_healthy_sample_has_no_property_parse_failures(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object")
        failures = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_PARSE_FAILED"]
        assert failures == [], f"healthy sample produced {len(failures)} property parse failures"

    def test_all_exports_with_serial_region_get_properties(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLE, depth="object")
        for obj in doc.objects:
            if obj.serial_region and obj.serial_region.size > 0:
                assert obj.properties is not None, f"{obj.id} has no property bag"
```

Also tighten the existing `test_object_depth_all_when_no_ids` at line 93 by replacing `assert obj.properties is not None` with:

```python
            assert obj.properties is not None, f"{obj.id} should have properties at object depth"
            if obj.serial_region and obj.serial_region.size > 0:
                assert len(obj.properties) > 0, f"{obj.id} has empty property bag"
```

- [x] **Step 2: Run the property contract**

Run: `python -m pytest tests/test_property_contract.py -q`

Expected: PASS (the probe already confirmed properties are non-empty and there is exactly one non-property diagnostic on this sample). If `test_healthy_sample_has_no_property_parse_failures` fails, that reveals a real regression to investigate before proceeding — do not weaken the assertion.

- [x] **Step 3: Commit**

```powershell
git add tests/test_property_contract.py
git commit -m "test: gate healthy samples on nonempty properties and zero parse failures"
```

---

### Task 4: Delete the redundant, broken `tests/v2/` suite

Removes the slow, duplicative suite that the audit flagged. The root-level contracts are a strict, fast superset: `test_document_contract.py` already has manifest-parametrized legacy table parity (covering `test_package_document.py`'s v1-comparison and `TestAllSamples` smoke), `test_application_contract.py` covers all six agent tools + CLI/projection equality, `test_projection_contract.py` covers pagination/selection/views, and `test_handler_contract.py` covers handlers strictly via the public API. The `tests/v2/` files are either pure duplicates or carry stale assertions (e.g. `test_agent_tools.py:38` asserts a non-existent `diagnostics_count` key; `test_handlers.py` unpacks a 3-tuple as 2).

**Files:**

- Delete: `tests/v2/test_handlers.py`
- Delete: `tests/v2/test_agent_tools.py`
- Delete: `tests/v2/test_package_document.py`
- Delete: `tests/v2/test_projection.py`
- Delete: `tests/v2/test_views.py`
- Delete: `tests/v2/__init__.py` and `tests/v2/conftest.py` if present

**Interfaces:**

- Consumes: the root contract files listed above.
- Produces: a single, fast contract layer with no `tests/v2/` directory.

- [x] **Step 1: Confirm no root contract depends on tests/v2**

Run: `python -m pytest tests/test_document_contract.py tests/test_application_contract.py tests/test_projection_contract.py tests/test_handler_contract.py tests/test_payload_contract.py -q`

Expected: PASS (these are the strict supersets; they do not import from `tests/v2/`).

- [x] **Step 2: Delete the redundant files**

```powershell
Remove-Item -LiteralPath tests\v2\test_handlers.py -Force
Remove-Item -LiteralPath tests\v2\test_agent_tools.py -Force
Remove-Item -LiteralPath tests\v2\test_package_document.py -Force
Remove-Item -LiteralPath tests\v2\test_projection.py -Force
Remove-Item -LiteralPath tests\v2\test_views.py -Force
# Remove package markers if they exist and are now the only contents
if (Test-Path tests\v2\__init__.py) { Remove-Item -LiteralPath tests\v2\__init__.py -Force }
if (Test-Path tests\v2\conftest.py) { Remove-Item -LiteralPath tests\v2\conftest.py -Force }
if ((Get-ChildItem tests\v2 -Force).Count -eq 0) { Remove-Item -LiteralPath tests\v2 -Recurse -Force }
```

- [x] **Step 3: Confirm the suite still collects and the broken tests are gone**

Run: `python -m pytest --collect-only -q 2>&1 | Select-Object -Last 3`

Expected: no `tests/v2/` node IDs; the count drops by the ~114 tests that lived under `tests/v2/`; zero collection errors.

- [x] **Step 4: Commit**

```powershell
git add -A tests/v2
git commit -m "refactor: remove redundant slow tests/v2 suite in favor of root contracts"
```

---

### Task 5: Remove the dead `build_package_document()` adapter

The v1→v2 adapter at `src/uasset_read/v2/package/__init__.py:272` and its private helpers have zero callers (verified: `build_package_document` is referenced only by its own definition and the module docstring; the public `parse_package_document()` uses `LegacyPackageReader` directly via `v2/api.py`). This is not the v1 pipeline — the v1 `parse_uasset_with_linker` remains a compatibility consumer and is untouched.

**Files:**

- Modify: `src/uasset_read/v2/package/__init__.py` (delete `build_package_document` and the private helpers; keep the module as a package marker)

**Interfaces:**

- Consumes: the grep/CodeGraph confirmation that no caller references `build_package_document`.
- Produces: `v2/package/__init__.py` containing only the module docstring (package marker); `LegacyPackageReader` continues to live in `v2/package/legacy.py`.

- [x] **Step 1: Confirm zero callers one more time**

Run: `Get-ChildItem -Recurse -Path src,tests -Filter *.py | Select-String -Pattern "build_package_document" -List`

Expected: the only match is `src/uasset_read/v2/package/__init__.py` (the definition). If any other match appears, STOP — the adapter is not dead and this task is cancelled.

- [x] **Step 2: Replace the file with a minimal package marker**

Overwrite `src/uasset_read/v2/package/__init__.py` with:

```python
"""Package readers.

The direct binary reader lives in :mod:`uasset_read.v2.package.legacy`
(`LegacyPackageReader`). The former v1→v2 adapter was removed: the public
``parse_package_document()`` API builds documents directly via the reader.
"""

from __future__ import annotations
```

- [x] **Step 3: Confirm imports still resolve and ruff is clean**

Run: `python -c "import uasset_read.v2.package; import uasset_read.v2.api; import uasset_read.v2.package.legacy"` and `python -m ruff check src tests`

Expected: both exit 0; no unused-import or undefined-name errors.

- [x] **Step 4: Run the full root contract suite**

Run: `python -m pytest tests/test_document_contract.py tests/test_application_contract.py tests/test_projection_contract.py tests/test_handler_contract.py tests/test_payload_contract.py tests/test_property_contract.py tests/test_schema_contract.py tests/test_manifest_contract.py tests/test_diagnostics_contract.py tests/test_reader_contract.py -q`

Expected: PASS — nothing imported the deleted adapter.

- [x] **Step 5: Commit**

```powershell
git add src/uasset_read/v2/package/__init__.py
git commit -m "refactor: remove dead build_package_document v1-to-v2 adapter"
```

---

### Task 6: Synchronize current documentation and CI

Closes execution-plan Task 11's documentation gate. README, the manifest, the agent reference, the execution plan checkboxes, and CI all currently overstate or understate the implemented boundary.

**Files:**

- Modify: `tests/samples/manifest.json:676`
- Modify: `docs/reference/agent-dev-reference.md:28,51`
- Modify: `README.md:9,30`
- Modify: `docs/plans/2026-08-28-package-first-refactor-execution-plan.md:36-44,91`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**

- Consumes: the green gate from Tasks 1–5.
- Produces: docs that claim only what the gate proves, and a CI job that runs pytest.

- [x] **Step 1: Fix the manifest sample count**

In `tests/samples/manifest.json`, change the Zen-gap description at line 676 from `"All 47 samples"` to `"All 48 samples"` (verified: the manifest already lists 48 fixtures).

- [x] **Step 2: Update the agent dev reference to the current boundary**

In `docs/reference/agent-dev-reference.md`, change the line that frames v2 as pure target/Phase-0 (lines 28 and 51) to record the current boundary:

- Line 28: replace "目标 v2 使用 package-first `PackageDocument`" with "current v2 使用 package-first `PackageDocument`（legacy + tagged properties + sample-backed handlers 已实现；Zen/IoStore、unversioned、payload extraction 仍 deferred，见 docs/designs/README.md）".
- Line 51: keep "不要继续扩展 Semantic 1.x 测试" but append "root-level `tests/test_*_contract.py` is the strict contract layer; do not re-add a `tests/v2/` duplicate suite."

- [x] **Step 3: Correct README's test count and scope the claim**

In `README.md`:

- Line 30: replace `| v2 Tests | 250+ tests across 10+ test files |` with `| v2 Tests | ~190 root-level contract tests (no skips/xfail) |` (use the exact count recorded in Task 7 Step 1).
- Line 9: keep the "implemented" sentence but append the deferred scope: "Zen/IoStore, unversioned-with-usmap, and payload extraction remain deferred (see `docs/designs/README.md`)."

- [x] **Step 4: Update the execution plan baseline and checkboxes**

In `docs/plans/2026-08-28-package-first-refactor-execution-plan.md`:

- Lines 36–44 ("Verified Baseline"): update the baseline commit to `cec8a6b3`, change "227 items" to the count recorded in Task 7 Step 1, and note the two schema + four handler failures that this recovery plan fixed.
- Check off (`- [x]`) every step under Tasks 1–9 that the gate in Task 7 proves passing. Leave Tasks 10–11 and the deferred gates unchecked where their fixture issues (#623–#627, #615, #618, #619) still block.

- [x] **Step 5: Add a pytest job to CI**

In `.github/workflows/ci.yml`, add a new job after `ruff-check`:

```yaml
  pytest:
    runs-on: ubuntu-latest
    needs: ruff-check
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install project + test deps
        run: |
          python -m pip install --upgrade pip
          python -m pip install . jsonschema pytest
      - name: Run root contract tests
        run: |
          python -m pytest tests/ -q
```

- [x] **Step 6: Run Ruff on docs-touching Python (none expected) and commit**

Run: `python -m ruff check src tests`

Expected: clean. Then:

```powershell
git add tests/samples/manifest.json docs/reference/agent-dev-reference.md README.md docs/plans/2026-08-28-package-first-refactor-execution-plan.md .github/workflows/ci.yml
git commit -m "docs: synchronize v2 implementation status and add pytest to CI"
```

---

### Task 7: Final executable gate

Closes execution-plan Task 11's executable gate.

**Files:** none (verification only; clean up `temp/probe_v2_state.py`).

**Interfaces:**

- Consumes: Tasks 1–6.
- Produces: a clean, honest gate record.

- [x] **Step 1: Record the test count and run the full suite from a clean process**

```powershell
python --version
python -m pytest --collect-only -q 2>&1 | Select-Object -Last 3
python -m pytest -q
```

Expected: Python 3.14 on the blocking machine; no `skip`/`xfail` reported (`pytest -rs` shows none); all tests pass. Record the collected count and paste it into the README line edited in Task 6 Step 3 if the placeholder differs.

- [x] **Step 2: Run Ruff and build**

```powershell
python -m ruff check src tests
python -m build
git diff --check
git status --short
```

Expected: all exit 0; `git status --short` shows only expected committed changes.

- [x] **Step 3: Spot-check all three entry points agree**

```powershell
python -m uasset_read --v2 --depth package --limit 2 tests/samples/ABP_RifleAnimLayers.uasset
python -m uasset_read --v2 --depth asset --limit 2 tests/samples/ALS_FootstepDataTable.uasset
```

Expected: both print `uasset_read.package` JSON with consistent object IDs, status, diagnostics, truncation metadata, and no embedded blob bytes.

- [x] **Step 4: Remove the throwaway probe**

```powershell
Remove-Item -LiteralPath temp/probe_v2_state.py -Force
```

- [x] **Step 5: Commit the final cleanup if any whitespace remains**

```powershell
git add -A
git commit -m "chore: close v2 recovery gate" --allow-empty
```

---

## Self-Review Record

- **Spec coverage:** the recovery covers execution-plan Task 4 (healthy-sample gates, Task 3), Task 5 (byte budget + schema, Tasks 1–2), Task 11 (docs/CI/gate, Tasks 6–7). Tasks 1–3 of the execution plan were already complete and are only verified, not redone. Tasks 8–10 (sample-backed handlers) were verified working by the probe and are covered by existing `test_handler_contract.py`; they need no recovery work. Deferred fixture-gated work (#623–#627, #615, #618, #619) is explicitly out of scope.
- **Placeholder scan:** every step contains the actual code, file paths, line numbers, or commands the executor needs. No "TBD", "add error handling", or "similar to Task N".
- **Type consistency:** `project_document` keeps its existing signature; the new `TestByteBudget` uses the same `doc` fixture as the rest of `test_projection_contract.py`. The schema additions match the exact keys Task 1's projection emits (`next_offset`, `truncation.reason/budget/actual/objects_dropped`, `debug`).
- **Ordering risk:** Task 1 must land before Task 2 (schema matches the fixed projection). Task 5 deletes code that nothing imports (verified). Task 4 deletes tests that the root suite supersedes (verified in Step 1). No task depends on a later task's types or names.
