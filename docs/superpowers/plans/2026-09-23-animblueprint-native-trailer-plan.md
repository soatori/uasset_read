# AnimBlueprint Native Trailer Reclassification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reclassify AnimBlueprint generated-class CDO and generated-data export trailers from `unexpected` to `known_unimplemented` by keying `classify_trailing_reason()` on object name + Outer/generated-class relationship via the shared `TrailingContext` API, so the CI "unexpected" signal only carries genuinely unknown trailers.

**Architecture:** A sibling plan (plan-reason-quality) delivers the shared context-aware classifier in `src/uasset_read/models/diagnostics.py`: `TrailingContext(class_name, object_name, outer_name, roles, payload_kind)` plus `classify_trailing_reason(context: TrailingContext | str)` with class-name bucket rules (`SoundNode*` → `editor_only`; true-gap classes → `known_unimplemented`; `ScriptStruct` deliberately excluded per team-lead ruling), AND the emission-site wiring (`_resolve_outer_name` + full `TrailingContext` + `Diagnostic.size` — their Task 2; this plan does not touch `legacy_reader.py`). This plan layers the two object-keyed AnimBlueprint rules onto `classify_trailing_reason`, pins the three ABP fixtures, retires their temporary scope fence, then regenerates the one quality-baseline entry whose reason counts move. No new `DiagnosticReason` member, no schema change, no diagnostic suppression.

**Tech Stack:** Python 3.10+ standard library, pytest, existing `uasset_read` document API (`parse_package_document`), existing baseline tooling (`tools/gen_quality_baseline.py`).

**Spec:** `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` (authoritative target architecture: unknown data preserved as opaque region + diagnostic, layered status, structured diagnostics over logs). Reason vocabulary and baseline gating: `docs/designs/2026-09-15-parser-quality-system.md` (`status: target`, closed `DiagnosticReason` domain).

**Plan dependency:** Execute AFTER the shared trailing-classifier plan (plan-reason-quality / plan-reason-gate), which delivers `TrailingContext` and the `classify_trailing_reason(context: TrailingContext | str)` signature. This plan defines neither; it consumes them (see Interfaces per task). Team-lead ruling (2026-09-23): plan-reason-quality drops `ScriptStruct` from its class-blanket list; the 5 generated-data trailers stay keyed on object name + Outer by this plan.

**Peer coverage for AnimBlueprint generated data:** No peer parser decodes this type. (CUE4Parse `UAnimBlueprintGeneratedClass.cs` is an empty `UBlueprintGeneratedClass` subclass; UAssetAPI mentions `AnimBlueprintGeneratedConstantData`/`AnimBlueprintGeneratedMutableData` only to *skip* them at `Usmap.cs:1233-1234` under `SkipBlueprintSchemas`; uasset-rs / uasset-reader-js do not parse property values.)

## Global Constraints

- Python 3.10+, cross-platform (no drive letters or user directories in code); blocking test env is local Windows + Python 3.14 (current: 3.14.7).
- Standard library only; minimal implementation — reuse `Diagnostic`, `make_diagnostic` (`_diag`), `ObjectRecord`, `ObjectRef`, and the shared `TrailingContext`; no new abstraction layers, no new dependencies.
- Read-only parser: parse/extract only. Unknown data is preserved as opaque region + diagnostic — never silently skipped, never reclassified away (this plan changes `reason`, it never removes a diagnostic).
- Bounded reads: any index resolved against `objects` must be range-checked before use.
- Diagnostics over logs: library code returns structured `Diagnostic` records; no process-global logging.
- Tests: no `skip`/`xfail`; no `MagicMock` for UE binary structures; classification unit tests use bounded in-memory contexts, support claims use real fixtures under `tests/samples/` that are manifest SHA-256 gated (`test_manifest_matches_every_real_sample`); no wall-clock benchmark thresholds.
- UE source reference required for binary layout decisions — this plan makes **no new layout decision** (it only re-classifies bytes already surfaced as trailers from already-parsed export-table fields); the deferred native reader will require UE source evidence.
- Named peers only (`Corroborated (not proof): <Peer> <symbol>`); zero coverage stated as `No peer parser decodes this type` (see above).
- English for code, comments, and error messages. Documentation follows the language of the document (the quality design is Chinese).
- Commit format: `<type>: <summary> (#issue)` with type in `feat|fix|refactor|test|docs|chore|release`; issue number optional. Commits are made by the executor, not the planner.
- Temp/investigation scripts belong under `temp/` (untracked); none are required by this plan.
- Do not describe the deferred native reader as implemented; do not inflate warning budgets by hand — baseline numbers come from `tools/gen_quality_baseline.py` output only.

---

## Background (verified against the codebase on 2026-09-23)

Two stacked problems on Anim / AnimBlueprint native trailers:

1. AnimBlueprint generated-class / generated-data objects carry native serialization bytes after the tagged-property stream that this parser does not decode. The bytes surface as `EXPORT_TRAILING_BYTES_UNCONSUMED`.
2. The classifier historically received only `class_name`, so these objects fell through to `unexpected`: CDOs have `class_name = <Asset>_C` (matches no bucket) and generated-data objects have `class_name = ScriptStruct` (matches no bucket).

Verified evidence (3 fixtures, 8 `unexpected` entries, 692,268 bytes total):

| Fixture | Object | class_name | Relation | Bytes |
|---|---|---|---|---|
| `ALS_AnimBP.uasset` | `export:0` `Default__ALS_AnimBP_C` | `ALS_AnimBP_C` | `class_ref=export:281` (`AnimBlueprintGeneratedClass`) | 605,230 |
| `ALS_AnimBP.uasset` | `export:3393` `AnimBlueprintGeneratedConstantData` | `ScriptStruct` | `outer_ref=export:281`, outer name `ALS_AnimBP_C`, roles `()` | 63,227 |
| `ALS_AnimBP.uasset` | `export:3394` `AnimBlueprintGeneratedMutableData` | `ScriptStruct` | `outer_ref=export:281`, outer name `ALS_AnimBP_C`, roles `()` | 4,162 |
| `LevelDesign_ABP_Manny.uasset` | `export:0` `Default__ABP_Manny_C` | `ABP_Manny_C` | `class_ref=export:24` (`AnimBlueprintGeneratedClass`) | 16,494 |
| `LevelDesign_ABP_Manny.uasset` | `export:153` `AnimBlueprintGeneratedConstantData` | `ScriptStruct` | `outer_ref=export:24`, outer name `ABP_Manny_C`, roles `()` | 3,044 |
| `LevelDesign_ABP_Manny.uasset` | `export:154` `AnimBlueprintGeneratedMutableData` | `ScriptStruct` | `outer_ref=export:24`, outer name `ABP_Manny_C`, roles `()` | 75 |
| `ABP_RifleAnimLayers.uasset` | `export:0` `Default__ABP_RifleAnimLayers_C` | `ABP_RifleAnimLayers_C` | `class_ref=export:2` (`AnimBlueprintGeneratedClass`) | 12 |
| `ABP_RifleAnimLayers.uasset` | `export:9` `AnimBlueprintGeneratedConstantData` | `ScriptStruct` | `outer_ref=export:2`, outer name `ABP_RifleAnimLayers_C`, roles `()` | 24 |

Also verified:

- Emission site: single `_diag("EXPORT_TRAILING_BYTES_UNCONSUMED", ...)` in `_parse_requested_object_properties` (`legacy_reader.py:1336-1347`), `remaining` computed at `:1333`, `reason=classify_trailing_reason(cn)` at `:1345`, object loop begins `:1260`. Exactly **one** production call site (import at `:40`).
- `depth="asset"` and `depth="decode"` produce **identical** full diagnostic lists on all three fixtures — decode only adds graph/static semantic results. Therefore "extend the AnimGraph handler to eliminate these warnings" is the wrong fix and is explicitly out of scope.
- The generated class export itself (e.g. `ABP_RifleAnimLayers_C`, class `AnimBlueprintGeneratedClass`) already classifies as `editor_only` via the `"AnimBlueprint"` prefix — that bucket is untouched.
- `objects` is export-only and index-aligned (`objects[i].id == "export:{i}"`), so export-ref resolution is a bounds check against `len(objects)`. Import refs are not resolvable from `objects` and resolve to `None` (in-package generated-class outers are always exports).
- `ObjectRecord.roles` vocabulary (built in `_build_object_record_direct`, `legacy_reader.py:275-282`): `asset` (b_is_asset), `class_default_object` (name starts `Default__`), `generated_class` (name ends `_C`, not `Default__`). Real values: CDO `('class_default_object',)`, generated class `('asset', 'generated_class')`, generated data `()`.
- Corpus-wide there are **28** `unexpected` trailer entries (698,361 B — re-derived across all 66 manifest samples by plan-reason-quality; the earlier "23" was a miscount): the 8 AnimBlueprint entries above (692,268 B) and 20 others (Model x3, SoundNodeWavePlayer x3, BodySetup x2, Polys x2, UserDefinedEnum x2, SoundNodeModulator x2, SoundNodeMixer x1, Level x1, World x1, MovieScene x1, NavCollision x1, PoseAsset x1 — 6,093 B) that belong to plan-reason-quality's class rules. All 5 `ScriptStruct` trailers corpus-wide ARE the AnimBlueprint generated-data objects above (any `ScriptStruct` trailer currently falls to `unexpected`; full scan confirmed) — per team-lead ruling their plan does not blanket `ScriptStruct`, this plan owns those 5 via object name + Outer.
- Quality baseline coupling: only `ALS_AnimBP.uasset` among gated samples has these trailers, as an **opt-in** entry (`UASSET_QUALITY_OPT_IN=1`) at `tests/samples/quality_baseline.json:137` with `known_unimplemented max 1251`, `unexpected max 3`, `forbid_unlisted: true`. Reclassifying moves 3 entries `unexpected -> known_unimplemented` (1251 -> 1254, verified current actuals 1251/3/577), which **exceeds** the stored max — the baseline must be regenerated or the opt-in gate fails. The other 10 baseline seeds were scanned: none has a `Default__*_C` or generated-data trailer, and plan-reason-quality's class rules touch zero baseline seeds, so after both plans the only baseline diff is this ALS entry (identical under either execution order).
- Size ratchet (`tests/size-baseline.json`) is currently **at ceiling** for all three areas (`src_python 28936/28936`, `tests_python 10986/10986`, `docs_markdown 58603/58603`) — this plan's code, tests, and this document itself will exceed it; Task 3 raises the ceilings from measured pytest output as a deliberate reviewable diff.
- Reason vocabulary stays closed: `known_unimplemented` already exists in `DiagnosticReason` and in the contract schema enum (`docs/designs/contract/package_document_v3.schema.json:629-641`). **No new `DiagnosticReason` literal is added by this plan** (confirmed with plan-reason-quality before their schema task).
- Byte opacity is already provided independently of `reason`: `_attach_byte_accounting` tiles each export serial range with opaque gap leaves (`tile_export_scope`, `gap_reason="unconsumed"`). This plan does not touch byte accounting.
- Existing tests covering trailer classification: `tests/test_diagnostics_reason.py::test_classify_trailing_reason_mapping` (single-argument str calls — must stay green through the shared API's str shorthand), `::test_bp_combat_character_trailing_diagnostics_carry_reason` (fixture reasons non-null; BP_CombatCharacter has no CDO trailer so its reasons are unchanged), `tests/test_samples.py::test_quality_baseline_diagnostics` (per-reason counts, opt-in for ALS), PhysicsAsset/PhysicalMaterial trailer-presence asserts at `test_samples.py:514/524` (unaffected — PhysicsAsset hits `_KNOWN_UNIMPLEMENTED_CLASSES`; PhysicalMaterial emits no trailer by design (`test_samples.py:522-525`) and reclassification never changes diagnostic presence), `test_parse_hardening.py:48-55` (message content, unaffected).

## Explicitly Deferred (not in this plan)

Implementing the AnimBlueprint generated-data / generated-class **native reader** — actually decoding the 692,268 trailer bytes across the three fixtures — is OUT OF SCOPE. Boundary: this plan only re-classifies the existing `EXPORT_TRAILING_BYTES_UNCONSUMED` diagnostic while keeping the bytes as opaque trailer (diagnostic + byte-accounting gap leaves) exactly as today. A future reader plan must trace layout to UE C++ source, add real-fixture structural assertions, and restate peer coverage (currently `No peer parser decodes this type`). This plan must NOT extend AnimGraph handlers to swallow these bytes, must NOT suppress any diagnostic, and must NOT hand-raise warning budgets — baseline numbers come from the generator only. Also out of scope: the `CachedPoseIndices` name-index issue (already fixed, unrelated).

---

### Task 1: Add the two object-keyed AnimBlueprint rules to the shared classifier

**Files:**
- Modify: `src/uasset_read/models/diagnostics.py` — add `_ANIM_GENERATED_DATA_OBJECTS` frozenset next to the existing bucket tuples (`_KNOWN_UNIMPLEMENTED_PREFIXES` area, ~:104-112); insert two rules immediately before the final `return "unexpected"` inside `classify_trailing_reason` (function delivered by the shared-API plan)
- Modify: `tests/test_samples.py` — delete `test_abp_cdo_trailers_remain_unexpected_for_sibling_plan` (temporary scope fence from plan-reason-quality Task 4; retired in the same commit as the rules so no red window exists)
- Modify: `docs/designs/2026-09-15-parser-quality-system.md:22` — trailing wiring bullet covers both class-bucket and object-keyed rules
- Test: `tests/test_diagnostics_reason.py` — append new tests after `test_classify_trailing_reason_mapping` (ends at line 85)

**Interfaces:**
- Consumes (from the shared-API plan): `@dataclass(frozen=True) class TrailingContext(class_name: str, object_name: str = "", outer_name: str | None = None, roles: tuple[str, ...] = (), payload_kind: str = "native_serial")` and `classify_trailing_reason(context: TrailingContext | str) -> DiagnosticReason`, both in `src/uasset_read/models/diagnostics.py`. The shared function already maps `str` to `TrailingContext(class_name=...)` and applies bulk / editor_only / known_unimplemented buckets plus plan-reason-quality's class rules.
- Produces: the same `classify_trailing_reason(context: TrailingContext | str) -> DiagnosticReason` additionally returns `"known_unimplemented"` for (a) `object_name.startswith("Default__") and class_name.endswith("_C")` and (b) `object_name in {"AnimBlueprintGeneratedConstantData", "AnimBlueprintGeneratedMutableData"} and outer_name.endswith("_C")`; str-shorthand and every other bucket unchanged. Task 2 consumes this via the call-site context build.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_diagnostics_reason.py` (after `test_classify_trailing_reason_mapping`):

```python
def test_classify_trailing_reason_native_cdo_and_generated_data():
    from uasset_read.models.diagnostics import TrailingContext, classify_trailing_reason

    # CDO: Default__ instance whose class is the *_C blueprint generated class
    # (UBlueprint::GetBlueprintClassName naming; ALS_AnimBP fixture shape).
    assert (
        classify_trailing_reason(
            TrailingContext(class_name="ALS_AnimBP_C", object_name="Default__ALS_AnimBP_C")
        )
        == "known_unimplemented"
    )
    assert (
        classify_trailing_reason(
            TrailingContext(class_name="BP_Foo_C", object_name="Default__BP_Foo_C")
        )
        == "known_unimplemented"
    )
    # Generated data: AnimBlueprint generated-data structs outered to the *_C class.
    assert (
        classify_trailing_reason(
            TrailingContext(
                class_name="ScriptStruct",
                object_name="AnimBlueprintGeneratedConstantData",
                outer_name="ALS_AnimBP_C",
            )
        )
        == "known_unimplemented"
    )
    assert (
        classify_trailing_reason(
            TrailingContext(
                class_name="ScriptStruct",
                object_name="AnimBlueprintGeneratedMutableData",
                outer_name="ABP_Manny_C",
            )
        )
        == "known_unimplemented"
    )
    # Contract test (team-lead 2026-09-23 ruling): a class-name-alone ScriptStruct
    # blanket must NOT classify generated data — keying is object name + Outer.
    assert (
        classify_trailing_reason(
            TrailingContext(class_name="ScriptStruct", object_name="AnimBlueprintGeneratedConstantData")
        )
        == "unexpected"
    )
    # Outer that is not a *_C generated class does not fire the rule.
    assert (
        classify_trailing_reason(
            TrailingContext(
                class_name="ScriptStruct",
                object_name="AnimBlueprintGeneratedConstantData",
                outer_name="SomeActor",
            )
        )
        == "unexpected"
    )
    # A *_C object that is not a Default__ instance is not a CDO.
    assert (
        classify_trailing_reason(
            TrailingContext(class_name="ABP_Foo_C", object_name="ABP_Foo_C")
        )
        == "unexpected"
    )
    # str shorthand keeps class-name-only behavior (no object/outer context).
    assert classify_trailing_reason("SomeUnknownClass") == "unexpected"
    assert classify_trailing_reason("ALS_AnimBP_C") == "unexpected"


def test_animbp_samples_reclassify_native_trailers_to_known_unimplemented():
    from uasset_read.package import parse_package_document

    expected = {
        "ALS_AnimBP.uasset": ("export:0", "export:3393", "export:3394"),
        "LevelDesign_ABP_Manny.uasset": ("export:0", "export:153", "export:154"),
        "ABP_RifleAnimLayers.uasset": ("export:0", "export:9"),
    }
    for name, object_ids in expected.items():
        doc = parse_package_document(f"tests/samples/{name}", depth="asset")
        trailing = {
            d.object_id: d
            for d in doc.diagnostics
            if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED"
        }
        for oid in object_ids:
            assert oid in trailing, f"{name}:{oid} missing EXPORT_TRAILING_BYTES_UNCONSUMED"
            assert trailing[oid].reason == "known_unimplemented", (
                f"{name}:{oid} reason={trailing[oid].reason}"
            )
        unexpected = [
            d.object_id
            for d in doc.diagnostics
            if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED" and d.reason == "unexpected"
        ]
        assert unexpected == [], f"{name}: unexpected trailers remain {unexpected}"

    # The largest native body keeps its disclosed byte count (reclassified, not suppressed).
    als = parse_package_document("tests/samples/ALS_AnimBP.uasset", depth="asset")
    cdo = next(
        d
        for d in als.diagnostics
        if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED" and d.object_id == "export:0"
    )
    assert "leaves 605230 undecoded bytes" in (cdo.message or "")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_diagnostics_reason.py::test_classify_trailing_reason_native_cdo_and_generated_data tests/test_diagnostics_reason.py::test_animbp_samples_reclassify_native_trailers_to_known_unimplemented -v`
Expected: FAIL with `AssertionError` on the first positive assert — `'unexpected' == 'known_unimplemented'` (shared API, str shorthand, and the emission-site context wiring from plan-reason-quality all exist, but the two object-keyed rules do not; the fixture test fails on `reason=unexpected`; the negative asserts already pass and do not mask the red)

- [ ] **Step 3: Write minimal implementation**

3a. In `src/uasset_read/models/diagnostics.py`, add below the existing bucket tuples (next to `_KNOWN_UNIMPLEMENTED_PREFIXES`):

```python
_ANIM_GENERATED_DATA_OBJECTS = frozenset(
    {
        "AnimBlueprintGeneratedConstantData",
        "AnimBlueprintGeneratedMutableData",
    }
)
```

3b. Inside `classify_trailing_reason`, insert immediately before the final `return "unexpected"` (after every class-bucket and plan-reason-quality class rule, so these rules only convert what would otherwise stay `unexpected`):

```python
    if context.object_name.startswith("Default__") and context.class_name.endswith("_C"):
        return "known_unimplemented"
    if (
        context.object_name in _ANIM_GENERATED_DATA_OBJECTS
        and context.outer_name is not None
        and context.outer_name.endswith("_C")
    ):
        return "known_unimplemented"
    return "unexpected"
```

Note: the shared implementation binds only `cn = context.class_name`; the predicates therefore read `context.object_name` / `context.class_name` / `context.outer_name` directly off the context object.

3c. In `tests/test_samples.py`, delete the whole `test_abp_cdo_trailers_remain_unexpected_for_sibling_plan` function (added by plan-reason-quality Task 4 as a temporary scope fence). Its assertion — `Default__*_C` trailers stay `unexpected` — is inverted by the rules above, so it must be removed in this same commit (no red window). The permanent contract lives in `test_animbp_samples_reclassify_native_trailers_to_known_unimplemented` (zero `unexpected` on the three ABP fixtures) plus the unit negatives.

3d. In `docs/designs/2026-09-15-parser-quality-system.md:22`, replace the `- trailing:` wiring bullet with:

```markdown
- trailing: `legacy_reader` EXPORT_TRAILING_BYTES_UNCONSUMED + `TrailingContext` 上下文分类（class 桶规则 + `Default__*_C` CDO / AnimBlueprint generated-data 按 object name + Outer 归 known_unimplemented）
```

The final text must mention both the class-bucket rules and the object-name/Outer keyed rules (plan-reason-quality does not touch this file).

- [ ] **Step 4: Run the classification file**

Run: `python -m pytest tests/test_diagnostics_reason.py -v`
Expected: all passed — both new tests green (rules + the already-wired call site reclassify the 8 fixture trailers); the mapping test's str-shorthand calls take empty `object_name`/`outer_name`, hit only the unchanged buckets, and stay green

- [ ] **Step 5: Run the samples file to confirm the fence retirement**

Run: `python -m pytest tests/test_samples.py -v`
Expected: all passed — the temporary fence is gone in this commit, so no red window exists; ALS_AnimBP opt-in gate is excluded without `UASSET_QUALITY_OPT_IN` and its regeneration follows in Task 2

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/models/diagnostics.py tests/test_diagnostics_reason.py tests/test_samples.py docs/designs/2026-09-15-parser-quality-system.md
git commit -m "feat: key AnimBlueprint trailer rules on object and outer context"
```

---

### Task 2: Regenerate the quality baseline for the moved reason counts

**Files:**
- Modify: `tests/samples/quality_baseline.json:137-160` (the `ALS_AnimBP.uasset` entry only — via the generator, never by hand)
- Tool (run, not modified): `tools/gen_quality_baseline.py` (`SEED` at `:19-31`, `OPT_IN_SEED` at `:33-35`)
- Test (gate): `tests/test_samples.py::test_quality_baseline_diagnostics` (`:1145-1156`), assertion helper `_assert_quality_baseline` (`:1018-1058`)

**Interfaces:**
- Consumes: reclassified diagnostics produced by Task 1 (the generator parses each seed at `depth="asset"` and counts `(code, reason)` pairs). Order note: this plan runs after plan-reason-quality (API dependency); their class rules touch no baseline seed, so the per-sample diff is ALS-only — the top-level `aggregate` section (their Task 6) will also move and is expected in the same regeneration.
- Produces: updated `tests/samples/quality_baseline.json` where the `ALS_AnimBP.uasset` entry's `EXPORT_TRAILING_BYTES_UNCONSUMED.known_unimplemented.max` becomes `1254` and the `unexpected` block is removed; every other sample entry byte-identical (the `aggregate` section updates in the same regeneration).

- [ ] **Step 1: Observe the red opt-in gate (proves the baseline drift is detected)**

Run (PowerShell): `$env:UASSET_QUALITY_OPT_IN = "1"; python -m pytest "tests/test_samples.py::test_quality_baseline_diagnostics[ALS_AnimBP.uasset]" -v`
Expected: FAIL with message containing `known_unimplemented count 1254 > baseline max 1251` (f-string shape: `{name}: {code}/{reason_key} count {actual} > baseline max {rule['max']}`)
(Keep `$env:UASSET_QUALITY_OPT_IN` set for Step 4; or re-set it there.)

- [ ] **Step 2: Regenerate the baseline with the existing tool**

Run: `python tools/gen_quality_baseline.py`
Expected: exits 0, rewrites `tests/samples/quality_baseline.json`

- [ ] **Step 3: Verify the diff touches only the ALS entry (plus `aggregate`)**

Run: `git diff tests/samples/quality_baseline.json`
Expected: within `"ALS_AnimBP.uasset"` — `"known_unimplemented": { "max": 1251 }` becomes `{ "max": 1254 }`, and the `"unexpected": { "max": 3 }` block is deleted. The top-level `aggregate` section (plan-reason-quality Task 6) also moves (the 8 AnimBlueprint entries shift from `unexpected` to `known_unimplemented`: `by_reason.unexpected` drops to zero entries, `known_unimplemented` gains 8 entries / 692,268 B) — expected in the same regeneration. **No other sample entry changes.** If any other sample entry differs, stop and investigate before committing (a widening diff means some other sample's diagnostics moved, which this plan did not intend).

- [ ] **Step 4: Run the opt-in gate to verify it passes**

Run (PowerShell): `$env:UASSET_QUALITY_OPT_IN = "1"; python -m pytest tests/test_samples.py -k quality_baseline -v`
Expected: all passed (11 samples including ALS)

- [ ] **Step 5: Run the default (non-opt-in) gate**

Run (PowerShell): `Remove-Item Env:UASSET_QUALITY_OPT_IN -ErrorAction SilentlyContinue; python -m pytest tests/test_samples.py -k quality_baseline -v`
Expected: all passed (10 samples, ALS excluded)

- [ ] **Step 6: Commit**

```bash
git add tests/samples/quality_baseline.json
git commit -m "test: regenerate quality baseline after trailer reclassification"
```

---

### Task 3: Full-suite verification and size-baseline bump

**Files:**
- Modify (only if the ratchet fires, which this plan guarantees it will): `tests/size-baseline.json` — raise `src_python.max_lines`, `tests_python.max_lines`, and `docs_markdown.max_lines` to the values printed by the failing test; append one sentence to the existing `_note` string naming this plan as the reason
- Test (gate): `tests/test_size_baseline.py` (ceilings read from `tests/size-baseline.json`; failure output prints measured values)

**Interfaces:**
- Consumes: all changes from Tasks 1-2, the shared-API plan's changes, plus this plan document (counted under `docs_markdown` once tracked).
- Produces: green full suite on the blocking environment (local Windows + Python 3.14); updated ratchet ceilings as a deliberate reviewable diff.

- [ ] **Step 1: Force-track the plan document, then run the full suite**

Run: `git add -f docs/superpowers/plans/2026-09-23-animblueprint-native-trailer-plan.md`
(The path is ignored by `.gitignore:109`; force-add matches how prior plan docs entered the `docs_markdown` count. Without this the "plan doc" wording in the size `_note` is false — `test_size_baseline.py` counts `git ls-files` only.)

Run: `python -m pytest tests/ -v`
Expected: everything passes **except** `tests/test_size_baseline.py::test_source_tree_within_baseline` and/or `::test_tests_tree_within_baseline` and/or `::test_docs_tree_within_baseline`, each FAIL with output of the form `"src_python: <measured> tracked lines exceeds baseline 28936 (files=<n>)"`. Any non-size failure means stop and investigate — this plan does not absorb unrelated regressions.

- [ ] **Step 2: Raise the ceilings from the measured failure output**

Edit `tests/size-baseline.json`: set each failing area's `max_lines` to the measured value printed in Step 1, and append to `_note`:

`Raised 2026-09-23 animblueprint trailer reclassification plan (object-keyed classifier rules, fixture pin, fence retirement, baseline regen, plan doc) from measured pytest size-baseline failure output.`

Do not raise a ceiling that did not fail. Do not add slack beyond the measured value.

- [ ] **Step 3: Run the ratchet to verify it passes**

Run: `python -m pytest tests/test_size_baseline.py -v`
Expected: all passed

- [ ] **Step 4: Run the full suite once more**

Run: `python -m pytest tests/ -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add tests/size-baseline.json
git commit -m "chore: raise size baseline for animblueprint trailer reclassification"
```

---

## Acceptance

- The 8 verified entries (`Default__*_C` CDOs and `AnimBlueprintGeneratedConstantData`/`AnimBlueprintGeneratedMutableData` with `*_C` outer) classify as `known_unimplemented`; zero `unexpected` trailers remain on the three ABP fixtures; every diagnostic still emitted with its byte count intact.
- The contract test proves a class-name-alone `ScriptStruct` blanket does NOT fire on generated data (team-lead ruling: keying is object name + Outer); all pre-existing reason assertions and the other 20 corpus `unexpected` entries (plan-reason-quality's class scope) are unchanged; closed `DiagnosticReason` domain and contract schema untouched — no new literal.
- `UASSET_QUALITY_OPT_IN=1 python -m pytest tests/ -k quality_baseline` and the default suite are green; full `python -m pytest tests/ -v` green on Windows + Python 3.14; size ratchet green at explicitly raised ceilings.
- The AnimBlueprint native reader remains deferred with a stated boundary; no AnimGraph handler changes; no warning-budget hand-raising.
