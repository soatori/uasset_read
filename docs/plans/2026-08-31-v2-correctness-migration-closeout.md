# v2 Correctness & Migration Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining v2 correctness defects (handler status precedence, property-bound enforcement, Niagara coverage), switch the CLI default to PackageDocument v2, converge the test system to the two formal files with a compliant CI, and make every current-state claim in docs/issues truthful.

**Architecture:** Legacy `PackageReader → tagged properties → v2 handlers → PackageDocument → projection` is already green at HEAD `d7aa9872` (PackageIndex sign mapping, super/preload relations, truncation re-scoping all landed). This plan hardens the last known correctness gaps without touching the working reader, then executes the test-system/CLI/documentation migration defined by the canonical design's Migration Completion Gate and test-organization constraints. Zen/IoStore/USMAP/payload work stays blocked on real samples and is explicitly out of scope.

**Tech Stack:** Python 3.10+ (blocking gate: local Windows + Python 3.14), stdlib only, pytest, Ruff, jsonschema (existing test dep), GitHub Actions, `gh` CLI.

**Spec:** `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` (canonical). Key spec anchors used below: test-organization constraints (lines 755-767), Verification principle (line 789: CI/pytest policy), Core v2 / Output v2 / Agent / Migration Completion Gates (lines 791-829). Predecessors: `docs/plans/2026-08-28-package-first-refactor-execution-plan.md` (Task 11 open), `docs/plans/2026-08-28-v2-recovery-hardening.md` (fully done).

## Verified Baseline (HEAD `d7aa9872`, clean tree, branch `dev-0.6.0`)

- PackageIndex sign fix, `super_of`/`preload_of` relations, out-of-range relation diagnostics, projection re-scoping: **already committed** (do not re-fix).
- `python -m ruff check src tests`: **passes**.
- Fast gate `python -m pytest tests/test_core.py tests/test_samples.py -q`: **27 passed in ~15s** (14 core + 13 sample-parametrized).
- Full suite: 229 collected (27 fast + 150 contract defs, expanded by parametrize).
- Confirmed still open (each proven by probe at plan-writing time):
  1. `run_handlers` (src/uasset_read/v2/handlers.py:55-101): a later handler success sets `status.semantic = "complete"` even after an earlier handler failure left `HANDLER_FAILURE` — status overwrite bug.
  2. `legacy.py:509-529`: property parse uses the full archive with a catch-all `except Exception`; no post-parse serial-region bound check.
  3. `property_parser.py:1234` dispatches v1 `AssetTypeHandler`s inside the v2 path and logs `logger.warning` to **stderr** (reproduced: `AssetTypeHandler 'NiagaraScriptVariableHandler' failed ...` printed during `parse_package_document` of `NM_BPSystemEvent.uasset`).
  4. `NiagaraHandler._NIAGARA_CLASSES` misses exactly 5 classes present in `NM_BPSystemEvent.uasset`: `NiagaraNodeOutput`, `NiagaraNodeSelect`, `NiagaraNodeStaticSwitch`, `NiagaraScript`, `NiagaraScriptSource` (34/43 objects enriched; the remaining 9 are the 11 `NiagaraScriptVariable` minus 2 covered — verified miss count = 5 distinct classes). Niagara is not in `tests/test_samples.py::CAPABILITIES`.
  5. CLI still requires `--v2` (cli.py:91,429); default remains v1 Semantic 1.x JSON → Migration Completion Gate (design line 823) unmet.
  6. `tests/contract/` (10 files, 150 defs) + `tests/contract/conftest.py` violate design line 764 ("tests/ root has only two formal test files; only permanent subdirectory is `tests/samples/`").
  7. `test_core.py` collects **14** top-level functions; design line 766 caps core at **10**.
  8. CI `.github/workflows/ci.yml`: `pytest-contract` job runs `--timeout=120` without `pytest-timeout` installed (line 142 — guaranteed `unrecognized arguments` failure); `pytest-fast` job is functional.
  9. README line 30 claims "~197 root-level contract tests" (actual layer: 150 defs / 202 collected, location `tests/contract/`, not root); manifest `summary.fixture_gap_count: 5` while `fixture_gaps` has 6 entries (one `status: "covered"`).
  10. `docs/reference/UAsset_Format_Analysis.md:5` and `docs/reference/uasset_unknown_asset_handling_report.md:9-11` hardcode a developer's UE/library checkout paths (violates AGENTS.md).

## CI Decision (assessment requested)

The canonical design (line 789) says CI pauses pytest and only the local Windows+3.14 gate blocks. The current broken `pytest-contract` job forces a decision. Assessment:

- Keeping one fast pytest job on Linux costs <2 min after test convergence and catches gross regressions on push; samples run deterministically there.
- It contradicts design line 789 unless the design is amended — and AGENTS.md requires the canonical design to be updated first when a repo-wide decision changes.

**Decision adopted by this plan (Task 6):** amend design line 789 to "CI keeps a non-blocking fast-suite smoke job; the blocking full gate remains local Windows + Python 3.14; Linux results are evidence, never 'validated' claims", delete `pytest-contract`, keep one fast job. If the user later rejects the amendment, revert to removing all pytest jobs — Tasks 1-5 and 7-8 are unaffected.

## Global Constraints

- Python `>=3.10`; stdlib + existing deps only (`pytest`, `jsonschema>=4` as test deps; no `pytest-timeout` — wall-clock thresholds are banned by design line 761).
- v2 stays read-only; library code returns structured diagnostics and never configures process-global logging (no WARNING-level library logs on normal parse paths).
- Default JSON output embeds no blob bytes, no unbounded arrays; every budget is byte-bounded (`project_document(max_bytes=...)`).
- `tests/` root: exactly `test_core.py` + `test_samples.py` after Task 5; `test_core.py` contains only top-level `test_*` functions, no classes, no `pytest.mark.parametrize`, no dynamic `test_*` assignment, ≤ 10 collected items; sample parametrization is uncapped.
- Manifest is never rewritten by tests; expectation changes require checking sample bytes + UE source first (design line 760).
- Blocking local gate: Windows + Python 3.14, `python -m pytest -q`. Do not describe Linux/3.12 as validated.
- Commit messages follow existing repo style (`fix:` / `test:` / `refactor:` / `docs:` / `chore:`), PowerShell 7 command syntax.
- Preserve unrelated work in a dirty tree; the tree is clean at Task 0 and must stay so between tasks.

## File Responsibility Map

| File | Change |
| --- | --- |
| `src/uasset_read/v2/handlers.py` | Task 1: failure-wins status precedence |
| `src/uasset_read/v2/package/legacy.py` | Task 2: post-parse bound check, narrowed exceptions, v1 dispatch suppression flag |
| `src/uasset_read/parsers/property_parser.py` | Task 2: accept `run_class_handlers: bool = True` |
| `src/uasset_read/v2/handlers.py` (`NiagaraHandler`) | Task 3: +5 class names |
| `tests/test_samples.py` | Tasks 3/5: Niagara capabilities; becomes the real-sample contract home |
| `tests/contract/test_handler_contract.py` | Task 1: status-precedence test (later folded by Task 5) |
| `tests/contract/test_property_contract.py` | Task 2: bound + stderr-quiet tests (later folded by Task 5) |
| `src/uasset_read/cli.py` | Task 4: default v2, `--legacy-json` opt-in, `--v2` deprecated no-op |
| `tests/test_core.py` | Task 4: CLI-default test; Task 5: reduced to ≤10 consolidated functions + AST gate |
| `tests/contract/*` (all 10 files) + `tests/contract/conftest.py` | Task 5: coverage folded into the two formal files, then deleted |
| `tests/conftest.py` | Task 5: single shared fixture module |
| `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` | Task 6: amend line 789 CI decision |
| `.github/workflows/ci.yml` | Task 6: one fast smoke job, contract job deleted |
| `README.md`, `wiki/`, `docs/reference/agent-dev-reference.md` | Task 7: truthful current-state claims, default-v2 usage |
| `tests/samples/manifest.json` | Task 7: `fixture_gap_count` semantics fix (description only — never counts/tests) |
| `docs/plans/2026-08-28-package-first-refactor-execution-plan.md` | Task 8: check off Task 11 items this plan proves |
| GitHub issues #621, #605, #602, #603, #620, #623-#627 | Task 8: status sync + sample-request guidance |

## Dependency Order

`Task 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8`. Tasks 1-4 add tests to the layer that currently owns the topic (contract files); Task 5 performs the one-time fold of all contract coverage (including Tasks 1-4 additions) into the two formal files, so nothing is written twice except the fold itself.

---

### Task 0: Freeze the tree

**Files:** none.

- [ ] **Step 1: Confirm the baseline is exactly as documented above**

```powershell
git status --short                      # expect: empty
git rev-parse --short HEAD              # expect: d7aa9872 (or a descendant already containing it)
python -m ruff check src tests          # expect: All checks passed!
python -m pytest tests/test_core.py tests/test_samples.py -q   # expect: 27 passed
```

If any command disagrees, STOP and re-derive the baseline before touching later tasks. No concurrent edits are permitted until Task 8 is committed.

---

### Task 1: Handler failure must not be masked by a later success

**Files:**
- Modify: `src/uasset_read/v2/handlers.py:55-101` (`run_handlers`)
- Test: `tests/contract/test_handler_contract.py` (append class)

**Interfaces:**
- Consumes: `run_handlers(obj, context, all_objects, package_data) -> tuple[dict|None, list[CoverageEntry], list[Diagnostic]]`; `ObjectStatus` (field `semantic: str`).
- Produces: same signature; new guarantee — after `run_handlers`, `obj.status.semantic == "partial"` iff any matched handler raised OR (nothing failed and at least one handler matched with `semantic` produced → `"complete"`); no handler mutates status inside the loop.

- [ ] **Step 1: Write the failing test**

Append to `tests/contract/test_handler_contract.py` (construction pattern matches `TestHandlerFailureIsolation` already in that file):

```python
class TestHandlerStatusPrecedence:
    def test_later_success_does_not_mask_earlier_failure(self):
        from uasset_read.v2 import handlers as H
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus

        class Boom:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                raise RuntimeError("boom")

        class Ok:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return {"kind": "ok"}

        obj = ObjectRecord(
            id="export:9", table_index=0, name="X", class_name="Foo",
            status=ObjectStatus(parse="success", semantic="not_requested"),
        )
        saved = H._HANDLERS[:]
        try:
            H._HANDLERS[:] = [Boom(), Ok()]
            semantic, _cov, diags = H.run_handlers(obj, H.VersionContext(), [], None)
        finally:
            H._HANDLERS[:] = saved
        assert semantic == {"kind": "ok"}
        assert obj.status.semantic == "partial"
        assert any(d.code == "HANDLER_FAILURE" for d in diags)

    def test_clean_success_still_marks_complete(self):
        from uasset_read.v2 import handlers as H
        from uasset_read.v2.object_model import ObjectRecord, ObjectStatus

        class Ok:
            def supports(self, obj, ctx):
                return True

            def enrich(self, obj, ctx, all_objs, data):
                return {"kind": "ok"}

        obj = ObjectRecord(
            id="export:9", table_index=0, name="X", class_name="Foo",
            status=ObjectStatus(parse="success", semantic="not_requested"),
        )
        saved = H._HANDLERS[:]
        try:
            H._HANDLERS[:] = [Ok()]
            H.run_handlers(obj, H.VersionContext(), [], None)
        finally:
            H._HANDLERS[:] = saved
        assert obj.status.semantic == "complete"
```

- [ ] **Step 2: Run to verify the first test fails**

Run: `python -m pytest tests/contract/test_handler_contract.py::TestHandlerStatusPrecedence -q`
Expected: `test_later_success_does_not_mask_earlier_failure` FAIL (`'complete' == 'partial'`); `test_clean_success_still_marks_complete` PASS.

- [ ] **Step 3: Fix `run_handlers`**

Replace the body of `run_handlers` (lines 66-101) with loop-scoped status assignment:

```python
    semantic: dict[str, Any] = {}
    coverage: list[CoverageEntry] = []
    diagnostics: list[Diagnostic] = []
    matched = False
    failed = False

    for handler in _HANDLERS:
        try:
            if handler.supports(obj, context):
                matched = True
                result = handler.enrich(obj, context, all_objects, package_data)
                if result is not None:
                    semantic.update(result)
        except Exception as e:
            # Handler failure must not affect other objects
            matched = True
            failed = True
            handler_name = type(handler).__name__
            coverage.append(
                CoverageEntry(
                    feature=f"handler.{handler_name}",
                    status="missing",
                    detail=f"Handler error: {e}",
                )
            )
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="HANDLER_FAILURE",
                    message=f"{handler_name} failed for {obj.id}: {e}",
                    stage="semantic.handler",
                    object_id=obj.id,
                    recoverable=True,
                )
            )

    if matched:
        obj.status.semantic = "partial" if failed else "complete"

    if not semantic:
        return None, coverage, diagnostics
    return semantic, coverage, diagnostics
```

- [ ] **Step 4: Run the handler contract + fast gate**

Run: `python -m pytest tests/contract/test_handler_contract.py tests/test_core.py tests/test_samples.py -q`
Expected: all PASS. (If any sample's semantic flips `complete → partial`, that exposes a *real* silently-swallowed handler bug — investigate, do not weaken the test.)

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/v2/handlers.py tests/contract/test_handler_contract.py
git commit -m "fix: handler failure no longer masked by later success"
```

---

### Task 2: Bound the property-parse trust boundary

Three coupled defects at one boundary (`legacy.py:_parse_object_properties` → `parse_properties_from_export`): unbounded post-parse position, catch-all `except Exception`, and v1 `AssetTypeHandler` dispatch leaking `logger.warning` to stderr inside the v2 path (design invariant "Legacy package 读取不依赖 Semantic 1.x" + "library code never configures process-global logging" — Python's `logging.lastResort` makes any WARNING print by default).

**Files:**
- Modify: `src/uasset_read/v2/package/legacy.py:509-542` (try/except/bounds)
- Modify: `src/uasset_read/parsers/property_parser.py` (signature of `parse_properties_from_export`, ~line 1140; dispatch block ~line 1234)
- Test: `tests/contract/test_property_contract.py` (append class)

**Interfaces:**
- Consumes: `parse_properties_from_export(export, archive, summary, name_map, export_map, import_map, mappings=..., game=..., tolerant=...)` — gains keyword `run_class_handlers: bool = True`; `ObjectExport.serial_offset`/`.serial_size`; `archive.tell()`.
- Produces: v2 calls it with `run_class_handlers=False`; new diagnostic code `EXPORT_PROPERTY_BOUNDS_EXCEEDED` (stage `properties.tagged`, severity `warning`, `effect="semantic_loss"`, `recoverable=True`); failure diagnostics now only from the narrowed exception tuple.

- [ ] **Step 1: Write the failing tests**

Append to `tests/contract/test_property_contract.py` (module already defines `SAMPLE` for a healthy legacy fixture; reuse it):

```python
class TestPropertyBoundEnforcement:
    def test_parse_past_serial_end_is_flagged_not_silent(self, monkeypatch):
        import uasset_read.parsers.property_parser as pp
        from uasset_read.v2.api import parse_package_document

        def fake_overrun(**kwargs):
            export = kwargs["export"]
            kwargs["archive"].seek(export.serial_offset + export.serial_size + 8)
            return []

        monkeypatch.setattr(pp, "parse_properties_from_export", fake_overrun)
        doc = parse_package_document(SAMPLE, depth="object")
        overrun = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_BOUNDS_EXCEEDED"]
        assert overrun, "property parse exceeded the serial region with no diagnostic"
        assert all(d.object_id and d.stage == "properties.tagged" for d in overrun)

    def test_v2_path_emits_no_handler_warnings(self, capfd):
        from uasset_read.v2.api import parse_package_document

        parse_package_document(
            SAMPLES / "NM_BPSystemEvent.uasset", depth="object"
        )
        captured = capfd.readouterr()
        assert captured.err == "", f"v2 parse leaked stderr: {captured.err[:200]}"
```

(`SAMPLES` is exported by the existing module or `tests/conftest.py`; add `SAMPLES = Path(__file__).parent.parent / "samples"` next to `SAMPLE` if the file only has a single-sample constant.)

- [ ] **Step 2: Run to verify both fail**

Run: `python -m pytest tests/contract/test_property_contract.py::TestPropertyBoundEnforcement -q`
Expected: FAIL #1 (`EXPORT_PROPERTY_BOUNDS_EXCEEDED` diagnostics missing — the monkeypatch target must also be patched where legacy.py imports it; see Step 3 note), FAIL #2 (stderr shows `AssetTypeHandler ... failed`).

- [ ] **Step 3: Implement the parser flag**

In `src/uasset_read/parsers/property_parser.py`, add `run_class_handlers: bool = True` to `parse_properties_from_export`'s keyword parameters. Guard the asset-type handler dispatch block (~line 1234) with `if run_class_handlers:` — keep v1 behavior byte-identical when the parameter is not passed. In `src/uasset_read/v2/package/legacy.py:511-521` pass `run_class_handlers=False`. Note for the test: `legacy.py` imports the function inside the method (`from ...parsers.property_parser import parse_properties_from_export`), so patching `uasset_read.parsers.property_parser.parse_properties_from_export` takes effect at call time — no extra change needed.

- [ ] **Step 4: Implement the bound check + narrowed exceptions**

Replace `legacy.py:509-542` with:

```python
            try:
                # Absolute-offset parser over the full archive, bounded by the
                # post-parse position check below (recovery plan: do not rebase).
                raw_props = parse_properties_from_export(
                    export=export_map[i],
                    archive=archive,
                    summary=summary,
                    name_map=name_map,
                    export_map=export_map,
                    import_map=import_map,
                    mappings=self._mappings_path,
                    game=self._game,
                    tolerant=self._tolerant,
                    run_class_handlers=False,
                )
                serial_end = export_map[i].serial_offset + export_map[i].serial_size
                overrun = archive.tell() - serial_end
                obj.properties = normalize_property_bag(raw_props)
                if overrun > 0:
                    obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
                    diagnostics.append(
                        Diagnostic(
                            severity="warning",
                            code="EXPORT_PROPERTY_BOUNDS_EXCEEDED",
                            message=(
                                f"Export {i} ({obj.name}) property parse ran "
                                f"{overrun} bytes past serial_end {serial_end}"
                            ),
                            stage="properties.tagged",
                            object_id=obj.id,
                            effect="semantic_loss",
                            recoverable=True,
                        )
                    )
                else:
                    obj.status = ObjectStatus(
                        parse=obj.status.parse,
                        semantic=obj.status.semantic,
                    )

            except (ParseError, EOFError, struct.error, ValueError, UnicodeError) as e:
                obj.properties = {}
                obj.status = ObjectStatus(parse="partial", semantic=obj.status.semantic)
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="EXPORT_PROPERTY_PARSE_FAILED",
                        message=f"Export {i} ({obj.name}) property parse failed: {type(e).__name__}: {e}",
                        stage="properties.tagged",
                        object_id=obj.id,
                        effect="semantic_loss",
                        recoverable=True,
                    )
                )
```

Add `import struct` to legacy.py's import block if absent (`ParseError` is already imported at line 13).

- [ ] **Step 5: Run focused, then the whole suite**

Run: `python -m pytest tests/contract/test_property_contract.py tests/contract/test_document_contract.py tests/test_core.py tests/test_samples.py -q` then `python -m pytest -q`
Expected: all PASS. Any `EXPORT_PROPERTY_PARSE_FAILED` that previously came from an out-of-tuple exception (e.g. `KeyError`, `AttributeError`) now surfaces as a traceback — that is intended (unexpected bugs must not hide as data). If a *malformed-fixture* test fails on a new exception type, add only that concrete type to the tuple with a code comment naming the fixture — never re-widen to `Exception`.

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/v2/package/legacy.py src/uasset_read/parsers/property_parser.py tests/contract/test_property_contract.py
git commit -m "fix: enforce property serial-region bound and stop v1 handler dispatch in v2"
```

---

### Task 3: Complete Niagara lightweight coverage and capability gate

**Files:**
- Modify: `src/uasset_read/v2/handlers.py:964-976` (`NiagaraHandler._NIAGARA_CLASSES`)
- Modify: `tests/test_samples.py:15-40` (`CAPABILITIES`)

**Interfaces:**
- Consumes: existing `NiagaraHandler` lightweight enrichment (`{"kind": "niagara", "niagara_type": <class>, "name": ...}`) and `test_real_sample_proves_claimed_capability` subset-matching (`expected` keys must appear in `obj.semantic`).
- Produces: `NM_BPSystemEvent.uasset` yields `semantic.kind == "niagara"` for all 43 objects; 5 new capability rows.

- [ ] **Step 1: Write the failing capability rows**

Add to `CAPABILITIES` in `tests/test_samples.py`:

```python
    ("NM_BPSystemEvent.uasset", "NiagaraGraph", {"kind": "niagara", "niagara_type": "NiagaraGraph"}),
    ("NM_BPSystemEvent.uasset", "NiagaraScript", {"kind": "niagara", "niagara_type": "NiagaraScript"}),
    ("NM_BPSystemEvent.uasset", "NiagaraScriptSource", {"kind": "niagara", "niagara_type": "NiagaraScriptSource"}),
    ("NM_BPSystemEvent.uasset", "NiagaraNodeOutput", {"kind": "niagara", "niagara_type": "NiagaraNodeOutput"}),
    ("NM_BPSystemEvent.uasset", "NiagaraNodeSelect", {"kind": "niagara", "niagara_type": "NiagaraNodeSelect"}),
    ("NM_BPSystemEvent.uasset", "NiagaraNodeStaticSwitch", {"kind": "niagara", "niagara_type": "NiagaraNodeStaticSwitch"}),
```

(`NiagaraGraph` already enriches today — it is included because the class was never capability-gated. Class names verified against the fixture: exactly these 5 were missing.)

- [ ] **Step 2: Run to verify the 5 new rows fail**

Run: `python -m pytest tests/test_samples.py -q -k Niagara`
Expected: 5 FAIL (`StopIteration` from the `next(...)` finder for missing classes).

- [ ] **Step 3: Extend the handler**

Edit `_NIAGARA_CLASSES` to the full set (existing 8 + 5):

```python
    _NIAGARA_CLASSES = (
        "NiagaraScript",
        "NiagaraScriptSource",
        "NiagaraScriptVariable",
        "NiagaraGraph",
        "NiagaraNodeFunctionCall",
        "NiagaraNodeInput",
        "NiagaraNodeOutput",
        "NiagaraNodeOp",
        "NiagaraNodeParameterMapGet",
        "NiagaraNodeParameterMapSet",
        "NiagaraNodeReroute",
        "NiagaraNodeSelect",
        "NiagaraNodeStaticSwitch",
    )
```

- [ ] **Step 4: Verify full coverage of the fixture**

Run:
```powershell
python -m pytest tests/test_samples.py -q
python -c "from uasset_read.v2.api import parse_package_document as p; d=p('tests/samples/NM_BPSystemEvent.uasset', depth='asset'); print('complete', sum(o.status.semantic=='complete' for o in d.objects), '/', len(d.objects))"
```
Expected: tests PASS; probe prints `complete 43 / 43`.

- [ ] **Step 5: Commit**

```powershell
git add src/uasset_read/v2/handlers.py tests/test_samples.py
git commit -m "feat: complete Niagara lightweight handler coverage with capability gates"
```

---

### Task 4: Default CLI output becomes PackageDocument v2

Migration Completion Gate item (design line 823): legacy Semantic 1.x is no longer the default JSON. The v1 pipeline stays a compatibility consumer behind an explicit flag (removal is a later milestone — Blueprint/Kismet decode-parity is not yet v2-native).

**Files:**
- Modify: `src/uasset_read/cli.py:89-91` (argument group), `:420-453` (dispatch)
- Test: `tests/contract/test_application_contract.py` (invert + add), `tests/test_core.py:131` (`test_cli_python_and_agent_return_the_same_page` must already pass without `--v2` after this change — adjust its invocation if it passes `--v2` explicitly)

**Interfaces:**
- Consumes: existing v2 block at `cli.py:428-453` (`parse_package_document` + `project_document`), `resolve_format`, `args.depth/limit/max_bytes`.
- Produces: `python -m uasset_read FILE` emits `uasset_read.package` v2 JSON; `--legacy-json` selects the previous v1 pipeline output; `--v2` accepted as a deprecated no-op (kept so existing scripts/CI spot checks don't hard-fail during rollout).

- [ ] **Step 1: Write the failing tests**

In `tests/contract/test_application_contract.py`, replace `test_cli_no_v2_defaults_to_legacy` with:

```python
def test_cli_defaults_to_v2_package_document(run_cli_json, healthy_sample):
    out = run_cli_json(str(healthy_sample))
    assert out["format"] == "uasset_read.package"
    assert "objects" in out and out["package"]["name"]

def test_cli_v2_flag_is_accepted_as_noop(run_cli_json, healthy_sample):
    plain = run_cli_json(str(healthy_sample))
    with_flag = run_cli_json("--v2", str(healthy_sample))
    assert plain == with_flag

def test_cli_legacy_json_opt_in(run_cli_json, healthy_sample):
    out = run_cli_json("--legacy-json", str(healthy_sample))
    assert out["format"] != "uasset_read.package" or "objects" not in out
```

Match the existing helper names in that file for CLI invocation (the file's 14 tests already call the CLI through one shared helper — reuse it; if no `healthy_sample` fixture exists, use the module's existing sample path constant).

- [ ] **Step 2: Run to verify failures**

Run: `python -m pytest tests/contract/test_application_contract.py -q -k "defaults_to_v2 or noop or legacy_json_opt_in"`
Expected: `test_cli_defaults_to_v2_package_document` FAIL (default output is v1 shape); others may fail on unknown `--legacy-json` argument (exit 2).

- [ ] **Step 3: Implement the switch**

In the argument group, change line 91 to a deprecation no-op and add the opt-in:

```python
    group.add_argument(
        "--v2",
        action="store_true",
        help="(deprecated, no-op) PackageDocument v2 is now the default output",
    )
    group.add_argument(
        "--legacy-json",
        action="store_true",
        help="Emit the legacy Semantic 1.x JSON via the v1 pipeline (deprecated compatibility mode)",
    )
```

In `run`/main dispatch, replace `if args.v2:` (line 429) with `if not args.legacy_json:` so the existing v2 block becomes the default; everything below (v1 pipeline) runs only with `--legacy-json`. Do not otherwise modify the v1 code path.

- [ ] **Step 4: Update the remaining CLI tests**

Sweep `tests/contract/test_application_contract.py` and `tests/test_core.py` for CLI invocations that pass `"--v2"` and drop the flag (it still works, but the parity tests should prove the *default* path). `test_cli_agent_python_share_projection` must compare the no-flag CLI against the Python/agent projections.

Run: `python -m pytest tests/contract/test_application_contract.py tests/test_core.py -q`
Expected: PASS.

- [ ] **Step 5: Full gate + manual smoke**

Run: `python -m pytest -q` then
```powershell
python -m uasset_read tests/samples/ALS_FootstepDataTable.uasset | Select-String '"format"' | Select-Object -First 1
python -m uasset_read --legacy-json tests/samples/ALS_FootstepDataTable.uasset | Select-String '"format"' | Select-Object -First 1
```
Expected: first prints `"format": "uasset_read.package"`; second prints the legacy format string.

- [ ] **Step 6: Commit**

```powershell
git add src/uasset_read/cli.py tests/contract/test_application_contract.py tests/test_core.py
git commit -m "feat!: default CLI output is PackageDocument v2; legacy JSON behind --legacy-json"
```

---

### Task 5: Converge the test system to the two formal files

Fold the entire `tests/contract/` layer (150 defs) plus the current 14-function `test_core.py` into the design-mandated shape: `test_core.py` (≤10 synthetic top-level functions) + `test_samples.py` (manifest-driven, uncapped). The disposition tables below are the authoritative mapping — check off every name.

**Files:**
- Rewrite: `tests/test_core.py`
- Rewrite: `tests/test_samples.py`
- Modify: `tests/conftest.py`
- Delete: `tests/contract/` (11 files incl. `__init__.py`, `conftest.py`)
- Modify: `pyproject.toml` only if `testpaths`/addopts need nothing (verify; expected: no change — `python_files = test_*.py` already selects exactly the two files once `tests/contract/` is gone)

**Interfaces:**
- Consumes: everything Tasks 1-4 proved.
- Produces: final gate command `python -m pytest -q` = the full suite (core ≤10 + sample matrix), and `test_test_suite_structure_gate()` enforcing the design's AST constraints.

#### 5a. Final `test_core.py` — exactly these 10 functions (top-level only, no classes/parametrize)

| # | Function | Absorbs |
| --- | --- | --- |
| 1 | `test_reader_boundaries_reject_malformed_access` | core:1 + all 17 `test_reader_contract.py` defs as a table of crafted `bytes`/`SliceReader` cases (each case: call + expected raise class) |
| 2 | `test_property_bag_normalization_is_bounded_lossless` | `test_property_contract.py` synthetic six: `test_empty_list_returns_empty_dict`, `test_unknown_property_is_descriptor_not_blob`, `test_known_property_preserves_value`, `test_struct_property_normalizes`, `test_bytes_value_serializes`, `test_properties_are_json_serializable` — table-driven loop over `normalize_property_bag` |
| 3 | `test_package_document_preserves_every_export_and_role` | core:2 + document: `test_all_exports_present`, `test_ids_are_export_prefix`, `test_stable_id_across_calls`, `test_to_dict_roundtrip`, `test_summary_fields` (in-memory `PackageDocument` builder, no fixture files) |
| 4 | `test_export_failure_isolated_and_diagnostics_typed` | core:4 + diagnostics_contract all 3 + document: `test_no_critical_on_healthy`, `test_diagnostics_have_stage` + Task 1 status-precedence tests + Task 2 `test_parse_past_serial_end_is_flagged_not_silent` (monkeypatched synthetic archive) |
| 5 | `test_handler_registry_supports_enriches_and_isolates` | handler_contract supports/rejects/enrichment unit defs for DataTable, UserDefinedEnum, UserDefinedStruct, Texture, Skeleton, Mesh, Material, MaterialInstance, AnimBlueprint, Blueprint (loop: (handler_factory, good_obj, bad_obj, expected_subset) table) + `test_handlers_registered`, `test_expected_handlers`, `test_handler_exception_doesnt_crash`, both `test_handler_exception_becomes_object_diagnostic` |
| 6 | `test_projection_views_depths_pagination_table` | projection_contract non-budget defs (`test_semantic_default` … `test_select_all_when_no_filters`, `test_all_views_json`) + core:5 — table over one synthetic doc |
| 7 | `test_projection_byte_budget_and_fields_filter` | core:9 + core:10 + projection `TestByteBudget` (5 defs incl. `test_truncated_page_rescopes_relations_and_dependencies`) |
| 8 | `test_schema_contract_statics` | schema: `test_example_validates_against_schema`, `test_schema_has_required_fields`, `test_schema_enums_match_code` |
| 9 | `test_cli_python_agent_share_default_projection_and_logging_inert` | core:7 + core:8 + application: `test_json_serializable`, `test_disabled_logging_no_files`, `test_root_logger_not_modified`, Task 4 `test_cli_v2_flag_is_accepted_as_noop` |
| 10 | `test_test_suite_structure_gate` | new — code below |

Implementation of #10:

```python
def test_test_suite_structure_gate():
    import ast

    root = Path(__file__).parent
    test_files = sorted(p.name for p in root.glob("test_*.py"))
    assert test_files == ["test_core.py", "test_samples.py"]
    subdirs = {p.name for p in root.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert subdirs == {"samples"}
    tree = ast.parse((root / "test_core.py").read_text(encoding="utf-8"))
    funcs = [
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
    assert len(funcs) <= 10
    assert not any(isinstance(n, ast.ClassDef) for n in tree.body)
    assert all(not n.decorator_list for n in tree.body if isinstance(n, ast.FunctionDef))
    assigned = {
        t.id
        for n in tree.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id.startswith("test_")
    }
    assert not assigned
```

#### 5b. Final `test_samples.py` — manifest-driven home for every fixture-touching contract test

Keep existing `test_manifest_matches_every_real_sample` and `test_real_sample_proves_claimed_capability` (+Niagara rows). Absorb the rest as follows:

1. **Fixture matrix** — one parametrized function over all 48 manifest entries (uncapped by design):

```python
@lru_cache(maxsize=None)
def _object_document(sample: str):
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(SAMPLES / sample, depth="object")


def _fixture_entries():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [entry["name"] for entry in manifest["samples"]]


@pytest.mark.parametrize("sample", _fixture_entries())
def test_every_real_sample_forms_a_valid_package_document(sample: str):
    doc = _object_document(sample)
    ids = [o.id for o in doc.objects]
    assert ids == [f"export:{i}" for i in range(len(ids))]          # export prefix + all exports
    assert all(d.stage for d in doc.diagnostics)                    # stage on every diagnostic
    for rel in doc.relations:
        assert rel.from_id in ids
        assert any(rel.to_id == o.id for o in doc.objects) or rel.to_id.startswith("import:")
    from uasset_read.v2.projection import project_document

    for view in ("semantic", "raw", "debug"):
        page = project_document(doc, view=view)                     # raises on schema drift if validated below
    import jsonschema

    schema_path = (
        Path(__file__).parent.parent / "docs" / "designs" / "contract" / "package_document_v2.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(project_document(doc, view="semantic"), schema)
    blob_free = json.dumps(project_document(doc, view="semantic"))
    assert "raw_data" not in blob_free or "raw_data_truncated" in blob_free
    failures = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_BOUNDS_EXCEEDED"]
    if MANIFEST_ENTRY[sample].get("healthy"):
        assert not failures and not [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_PARSE_FAILED"]
```

(Adjust `healthy` per fixture from the manifest's existing status/version fields; where the manifest lacks a health flag, use the current zero-failure list recorded in `docs/plans/2026-08-28-v2-recovery-hardening.md` Verified Baseline as an explicit module-level set `UNHEALTHY_FIXTURES` — a test must never guess.)

Absorbed into the matrix: `test_document_contract.py` (per-sample: `test_no_dangling_relations`, `test_relation_to_valid`, `test_relation_from_references_export`, `test_relations_present`, `test_legacy_reader_matches_manifest_tables`, `test_bisasset_does_not_filter`, `test_multiple_asset_roles`, `test_exports_survive_without_asset_role`), `test_property_contract.py` healthy trio, `test_schema_contract.py` `test_projection_output_validates` / `test_all_views_validate`, `test_manifest_contract.py` `test_all_samples_exist`/`test_sha256_matches`/`test_size_matches`/`test_no_extra_files`/`test_sample_parseable` (hash/size already in `test_manifest_matches_every_real_sample`; drop duplicates), `test_diagnostics_contract.py` sample defs.

2. **Moved from `test_core.py` (the four fixture-driven relation defs, current lines 219-303)** — keep as-is top-level functions in `test_samples.py`: `test_preload_relations_use_ue_ranges_and_sign_semantics`, `test_relation_targets_out_of_range_are_dropped_with_diagnostic`, `test_depends_map_validates_package_index_sign_per_ue_convention`, `test_preload_relations_report_invalid_ranges_without_crashing`.

3. **Named capability expansions** — fold `test_handler_contract.py` sample-backed defs into `CAPABILITIES` rows / the capability function's per-class branches where already patterned (DataTable row-count invariant, Skeleton bone consistency, StaticMesh lod consistency, texture dimensions, sound coverage, AnimBlueprint heavy-array omission, decode graph node refs — `test_asset_depth_omits_heavy_graph_arrays`, `test_decode_graph_references_existing_nodes` become `depth="decode"` checks in their class branches), plus `test_payload_contract.py` all 5 (payload coverage assertions keyed to `FirstPerson_T_GridChecker_A.uasset`, `MutableSample_GrayLightTextureCube.uasset`, `ALS_Concrete_Step_01_SoundWave.uasset`).

4. **Remaining one-off fixtures** stay plain functions in `test_samples.py`: `test_large_sample_all_exports`, `test_zero_asset_role_fixture_is_manifested` (uses `uasset_rs_UE410_SimpleRefsSoftRef.uasset`), `test_v2_api_does_not_call_v1_pipeline` (import-probe; core-eligible but sample-API-focused — it imports no fixture, so place here as a function per the handler-free import check), `test_expected_handlers`-driven Niagara full-coverage check `def test_niagara_fixture_fully_enriched(): ...` asserting `all(o.status.semantic == "complete" for o in _asset_document("NM_BPSystemEvent.uasset").objects)`.

- [ ] **Step 1: Copy the disposition tables above into the task checklist and mark each name as it moves** (executor tracking only — do not commit a copy)

- [ ] **Step 2: Write the new `test_core.py` and `test_samples.py`**

Port assertion *bodies* from the contract files, keeping every original assertion verbatim inside the consolidated loops (sub-test context = case/sample name in the assert message per design line 758). Shared fixtures move to `tests/conftest.py`: merge `tests/contract/conftest.py` content into `tests/conftest.py` (single `samples_dir`/`sample_path`/`multi_asset_sample` set), delete the duplicate.

- [ ] **Step 3: Verify structure gate and counts**

Run: `python -m pytest tests/test_core.py --collect-only -q`
Expected: ≤10 items. Run: `python -m pytest -q`
Expected: all PASS, no skips; total collected < 300 (48-fixture matrix + capabilities + ~10 core + named one-offs).

- [ ] **Step 4: Delete the old layer and re-verify**

```powershell
Remove-Item -LiteralPath tests\contract -Recurse -Force
python -m pytest -q
python -m ruff check src tests
```
Expected: green; `tests/` contains only `conftest.py`, `test_core.py`, `test_samples.py`, `samples/` (plus ignored `__pycache__`).

- [ ] **Step 5: Commit**

```powershell
git add -A tests
git commit -m "refactor!: converge test system into test_core + manifest-driven test_samples"
```

---

### Task 6: CI convergence (amend canonical design first)

**Files:**
- Modify: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md:789`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Amend the design decision**

Replace the CI sentence at line 789 with: "GitHub CI 只运行非阻塞的 fast-suite smoke job（`python -m pytest -q`，无墙钟阈值）作为回归证据；阻断性全量门禁仍是本机 Windows + Python 3.14。Linux/3.12 结果不得被描述为已验证环境。coverage 与 Codecov 仍暂停。" Add the same sentence's English gloss to the Decisions list (line ~859) so index readers see one policy.

- [ ] **Step 2: Rewrite the pytest jobs**

In `.github/workflows/ci.yml`: delete the entire `pytest-contract` job (lines ~126-142). Rename `pytest-fast` → `pytest-smoke`, keep `runs-on: ubuntu-latest` + `python-version: "3.12"`, and change its command to `python -m pytest -q` (after Task 5 the default collection *is* the two formal files). No `--timeout`. Add step comment: `# non-blocking smoke evidence; blocking gate is local Windows + 3.14`.

- [ ] **Step 3: Validate workflow syntax and local equivalence**

Run: `python -c "import yaml,io; yaml.safe_load(io.open('.github/workflows/ci.yml', encoding='utf-8')); print('yaml ok')"` (if PyYAML is unavailable, use `python -m uasset_read --help` smoke plus `git diff`; do not add a dependency).
Run locally: `python -m pytest -q`
Expected: PASS in <60s (fast corpus already proven ~15s; the 48-fixture matrix dominates but was <8 min at the full-suite baseline and runs in CI only as evidence).

- [ ] **Step 4: Commit**

```powershell
git add docs/designs/2026-08-26-package-first-uasset-parser-refactor.md .github/workflows/ci.yml
git commit -m "ci: replace broken contract job with non-blocking fast-suite smoke"
```

---

### Task 7: Documentation and manifest truthfulness

**Files:**
- Modify: `README.md:9,27,30,37,57`
- Modify: `docs/reference/agent-dev-reference.md`
- Modify: `wiki/` CLI/API examples (grep for `--v2`)
- Modify: `tests/samples/manifest.json:671`
- Modify: `docs/reference/UAsset_Format_Analysis.md:5`, `docs/reference/uasset_unknown_asset_handling_report.md:9-11`

- [ ] **Step 1: README — claims that match the post-Task-5 gate**

- Line 9 status banner: keep scope list but change to "v2 package-first architecture: default CLI/API output is `PackageDocument v2` (legacy packages; tagged properties; sample-backed handlers incl. full lightweight Niagara coverage). Zen/IoStore, unversioned-with-usmap, payload extraction remain deferred (see `docs/designs/README.md`); Semantic 1.x JSON is opt-in via `--legacy-json`."
- Line 27 table: `Version | 0.5.5 (stable) / 0.6.0-dev (v2 default)`.
- Line 30 table: replace `~197 root-level contract tests` with the exact count recorded in Task 8 Step 1, phrased `test_core (<=10) + manifest-driven test_samples (<N> collected, no skips/xfail)`.
- Line 37 usage note and line 57 example: remove `--v2` (now default); show `--legacy-json` in a "legacy" sub-line.

- [ ] **Step 2: Agent dev reference** — append to the current-boundary section: v2 is the default projection for all three entry points; `extract_payload` remains descriptor-level (extraction blocked on Phase 5 containers); v1 pipeline is legacy-only behind `--legacy-json` and slated for removal after decode-parity; the two formal test files are the contract layer (`tests/contract/` no longer exists).

- [ ] **Step 3: Wiki examples** — run `Get-ChildItem wiki -Recurse -Filter *.md | Select-String --v2` (as PowerShell: `Select-String -Pattern '\-\-v2'`); replace `--v2` usages with plain invocations and note the deprecation once per page.

- [ ] **Step 4: Manifest gap semantics (description only)** — edit `fixture_gap_count` region at `tests/samples/manifest.json:671` so the field means what it counts: change to `"fixture_gap_count": 5` **plus** a sibling `"fixture_gaps_total": 6, "fixture_gaps_note": "one of the six entries (no_b_is_asset_package) is status=covered"`. This is an expectation-metadata change reviewed against the six existing entries; no sample bytes change. Verify `python -m pytest tests/test_samples.py -q -k manifest` still passes (the manifest test asserts sample tables, not gap counts).

- [ ] **Step 5: Strip hardcoded developer paths** — replace `E:\Develop\lib\UnrealEngine` with `<UnrealEngine source root>` in `UAsset_Format_Analysis.md:5` and the three path lines in `uasset_unknown_asset_handling_report.md:9-11` with repo-relative descriptions per AGENTS.md.

- [ ] **Step 6: Ruff + commit**

```powershell
python -m ruff check src tests
git add README.md wiki docs tests/samples/manifest.json
git commit -m "docs: synchronize v2 default-status claims with the green gate"
```

---

### Task 8: Atomic final gate, issue sync, push

**Files:**
- Modify: `docs/plans/2026-08-28-package-first-refactor-execution-plan.md` (Task 11 checkboxes)

- [ ] **Step 1: Atomic full gate from one clean process on the frozen tree**

```powershell
git status --short                       # expect empty
python --version                         # record exact (3.14.x expected)
python -m pytest --collect-only -q 2>&1 | Select-Object -Last 3    # record count
python -m pytest -q                      # expect: all passed, no skips/xfail
python -m ruff check src tests
python -m build
git diff --check
```

Record `python --version`, collected count, pass count and duration in the execution-plan Task 11 note. Paste the count into README (Task 7 Step 1 placeholder phrasing).

- [ ] **Step 2: Entry-point spot checks (default paths)**

```powershell
python -m uasset_read tests/samples/ABP_RifleAnimLayers.uasset --depth package --limit 2
python -m uasset_read tests/samples/ALS_FootstepDataTable.uasset --depth asset --limit 2
python -m uasset_read --legacy-json tests/samples/ALS_FootstepDataTable.uasset
```
Expected: first two print `uasset_read.package` JSON (consistent ids/status/diagnostics/truncation, no blob); third prints legacy shape.

- [ ] **Step 3: Execution plan Task 11 checkboxes** — check off Steps 1-3; Step 4 stays unchecked until Step 5 below completes. Commit:

```powershell
git add README.md docs/plans/2026-08-28-package-first-refactor-execution-plan.md
git commit -m "docs: record atomic v2 closeout gate results"
```

- [ ] **Step 4: Issue synchronization (via `gh`)**

```powershell
gh issue comment 621 --body "Closeout plan docs/plans/2026-08-31-v2-correctness-migration-closeout.md completed through Task 8. Gate: HEAD <sha>, Python <ver>, <N> passed (core <=10 + manifest matrix), ruff clean, wheel built. Package-first v2 legacy path is the CLI/API default. Remaining OPEN scope: Zen/IoStore/USMAP/payload (blocked on re-distributable samples, see #623-#627), deeper per-asset semantics, v1 pipeline removal after decode parity."
gh issue comment 605 --body "Strict acceptance re-run green at <sha>; closing." ; gh issue close 605
gh issue comment 602 --body "v2 default path landed: descriptor-level payload coverage gated in test_samples. Real extraction stays blocked on sidecar/IoStore fixtures (#624); texture payload descriptor top-level promotion tracked here."
gh issue comment 603 --body "Skeleton semantics still NameMap-derived; parent/hierarchy and lod-completeness gating need cooked samples (#625). Stays OPEN."
gh issue comment 620 --body "Material summary gated; target material-expression coverage requires real cooked samples (#626). Stays OPEN."
gh issue edit 623 624 625 626 627 --repo <owner>/<repo> 2>$null
```

and comment on each of #623-#627: "Sample acquisition guidance change: do NOT create throwaway UE projects. Request re-distributable real .uasset/.utoc/.ucas/.pak samples (and matching UE editor version metadata) from users/projects with redistribution permission; attach SHA-256 + license note when provided." (One `gh issue comment` per issue with the respective gap name from `fixture_gaps`.)

- [ ] **Step 5: Push**

```powershell
git push -u origin dev-0.6.0
```
Expected: remote branch created; record the URL in #621's closing comment context.

---

## Self-Review Record

- **Report coverage:** every open item of the unified report maps to a task — PackageIndex/dangling relations/preload/super/truncation (already fixed at baseline; regression-gated by matrix in 5b), handler-status overwrite (T1), bounded property path + broad except + stderr v1 dispatch (T2), Niagara 5 types + capability table (T3), CLI/API default migration (T4), two-file test convergence incl. the 14>10 core violation and the two conftest duplicates (T5), CI contract job + `--timeout=120` (T6), README/reference/wiki overclaims, `fixture_gap_count` 5-vs-6, hardcoded UE paths (T7), Issue sync incl. sample-request process, push (T8). Explicitly deferred (blocked, not forgotten): Zen/IoStore/USMAP/payload/sidecar extraction, #602/#603/#620 deep semantics, v1 pipeline removal.
- **Placeholder scan:** all new code is inline; conditional steps (adding an exception type, `UNHEALTHY_FIXTURES` source, PyYAML fallback) name their concrete fallback values and where to obtain them — none say "handle appropriately".
- **Type consistency:** `run_class_handlers` keyword used identically in T2 signature and call site; `EXPORT_PROPERTY_BOUNDS_EXCEEDED` spelling identical in legacy.py, tests, and matrix; `obj.status.semantic` values (`"not_requested"|"partial"|"complete"`) match existing `ObjectStatus` usage; CLI helper names in T4 Step 1 defer to the actual shared helpers in the contract file (T5 folds those files anyway, so the T4 tests only need to run before deletion).
- **Risk ordering:** T5 deletes the layer T1-T4 extend — hence T5 comes last among code tasks and its disposition tables include the T1/T2/T4 additions explicitly.
