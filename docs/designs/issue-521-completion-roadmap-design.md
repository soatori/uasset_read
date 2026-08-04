# Issue #521 Epic Completion Roadmap — Design

> Status: Approved design (2026-08-05)
> Related issues: #521 (Epic), #525 (node parameters / pin_references), #515 (opaque StructProperty)
> Fixture: `tests/samples/NM_BPSystemEvent.uasset`
> SHA-256: `B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF`

## Background

Issue #521 was originally filed as "parse Niagara". It was restructured into an Epic with
field-level sub-scopes (NiagaraGraph / NiagaraScript / node families). The partial-metadata
minimal slice is complete (commits `5877a423`, `0646b422`): Graph, Script, and 9 node
classes project verified tagged properties with `parse_status = partial_metadata`;
59 focused tests pass.

A 2026-08-04 contract-gap audit reopened the Epic: several original acceptance
requirements remain unmet. This roadmap defines how #521 reaches an honest close —
every original requirement ends in one of exactly three terminal states:

1. **Achieved** — requirement met with evidence.
2. **Disproven-closed** — requirement shown unreachable, with recorded evidence.
3. **Explicitly out of scope** — removed from the Epic with a recorded rationale.

No requirement may remain dangling. "Evidence-unreachable" is not a fourth state; it
must be mapped to state 2 (with evidence) or 3.

## Verified Baseline (live parse of the fixture)

- 43 exports total: 39 Niagara-class exports + 3 `EdGraphNode_Comment` + 1 `MetaData`.
- Niagara-class composition: `NiagaraGraph`×1, `NiagaraScript`×1, 25 `NiagaraNode*`
  (9 classes), `NiagaraScriptVariable`×11 (generic tagged parse, `parse_status`
  currently `None`), `NiagaraScriptSource`×1 (skipped).
- Structs inside Niagara export properties: `NiagaraVariable`×12,
  `NiagaraVariableMetaData`×11, `NiagaraVariant`×11, `NiagaraTypeDefinition`×1,
  `NiagaraParameterStore`×1, `StaticSwitchTypeData`×1, `UnknownStruct`×7
  (elements of `Outputs`/`OutputVars` arrays), `Guid`×52.
- No pin-class exports exist in the fixture.
- Uncovered Niagara classes are exactly two: `NiagaraScriptVariable` and
  `NiagaraScriptSource`. (The "23 other Niagara exports" figure quoted in older
  evidence comments was extrapolated from a pre-migration skip list and is void.)

## Redefined Epic Completion Criteria

| Original requirement | Terminal disposition |
|---|---|
| Node connections | Split: node_exports level already achieved. Pin level via Track B, gated by B0. If B0 proves pins unserializable, pin level is disproven-closed and the terminal state is node_exports references + disproval record. |
| Execution flow | Explicitly out of scope. Rationale phrased per evidence discipline: "insufficient evidence today; no assertion made". (Claiming Niagara graphs are "pure dataflow" without a version-fixed UE source reference would violate commit `db65e66f` attribution rules.) If A2 finds a version-fixed source reference (e.g. absence of exec pins in `UEdGraphSchema_Niagara`), cite it; otherwise use the weaker wording. Re-open condition recorded. |
| Parameter definitions and values | Achieved via Track B: structured `parameters` from `NiagaraVariable` decoding (B1). Independent of the B0 pin gate. |
| Script references | Disproven-closed, qualified as "the ceiling of tagged-property object references": graph↔script direct reference disproven by the 2026-08-04 audit; `NiagaraNodeFunctionCall.FunctionScript` (already projected) is the maximum reachable via tagged refs. Opaque containers (`CachedUsageInfo`, `VariableToScriptVariable`) remain open via the #515 path and are not claimed as covered. |
| Graph structure | Achieved path: node composition already projected; pin-level edges added by #525 (subject to the B0 gate). |
| Niagara type coverage | Achieved path over the live enumeration: every Niagara class in the fixture lands on an evidence-based terminal state (field-level parse / explicit opaque / evidence-backed skip), recorded in a coverage contract table. |
| (added) Lyra-wide statistics (39.3% / 1,638 exports) | Explicitly out of scope: owner confirmed on 2026-08-01 that these cannot be reproduced from repository fixtures; acceptance is redefined per-fixture. |

## Two-Track Structure

Track A has no capability dependency and starts immediately. Track B is the capability
chain gated by a source-audit spike (B0). The two tracks share no blocking dependency;
their single overlap is `NiagaraScriptVariable`'s inner structs (A3 settles routing and
status; decoding belongs to B1/#515).

```
Track A:  A1 ─┬─> A2                     Track B:  B0a ─> B0b ─> gate decision
              └─> A3 ······┐                          ┌──> pin path ──────> B2 (pin half)
                           │        B1-pre ──> B1 ────┤   (in parallel with B0)
        (ScriptVariable    │                          └──> parameters path ─> B2 (parameters half)
         inner-struct overlap from A3 to B1)
                           ▼
                 Convergence gate (below)
```

### Track A

**A1 — Epic acceptance-criteria rewrite** (documentation only)

- Deliverables: #521 issue body rewritten as an "original requirement → terminal state"
  mapping table; `docs/designs/issue-521-niagara-export-parsing-plan.md` fixed (stale
  counts 26/28/23 corrected) and updated with the Lyra-statistics disposition row;
  a new independent issue created for test promotion + `constraints.md` desync, linked
  from the Epic.
- Acceptance: issue body / plan doc / field-contract doc are mutually consistent; every
  original requirement has exactly one terminal state.
- Not done: any code change.

**A2 — Execution-flow disposition record**

- Deliverables: new "Execution flow" section in
  `docs/designs/issue-521-niagara-field-contracts.md` — out of scope, rationale per
  evidence discipline (wording above), re-open condition; version-fixed UE source
  citation only if obtainable.
- Acceptance: section exists; no assertion without a source reference.
- Not done: any execution-order inference.

**A3 — Coverage inventory slice**

- Deliverables: live enumeration confirming the two uncovered classes
  (`NiagaraScriptVariable`×11, `NiagaraScriptSource`×1); per-class version-fixed source
  audit; per-class terminal state (field-level parse / explicit opaque / evidence-backed
  skip); an explicit `parse_status` defined for `NiagaraScriptVariable` (its current
  `None` violates the status-model constraint) — the value is an audit output, chosen
  from `ExportParseStatus` with the expected candidate being `partial_metadata` via
  `OPAQUE_CLASS_PAYLOAD` handler projection, mirroring the Graph/Script precedent;
  coverage contract table added to the
  field-contract doc; independent issues created for any class qualifying for parsing.
- Acceptance: every Niagara export belongs to a terminal state; the inner opaque structs
  of `NiagaraScriptVariable` (`NiagaraVariableMetaData` / `NiagaraVariant`) are marked
  as owned by the B1/#515 path, not decoded in A3; the existing 59 Niagara tests show
  no regression.
- Not done: parsing without fixture + source evidence; bulk prefix-routing changes.

### Track B

**B0a — Fixture-level pin existence proof** (diagnostic; must not change parse output)

- Deliverables: per-node-class inspection of native-tail bytes (offset/size already
  recorded by handlers) locating pin markers (FNames / GUIDs / reference patterns);
  identification of the actual types of the 7 `UnknownStruct` elements
  (`Outputs`/`OutputVars`); evidence document.
- Acceptance/branching: pin structures found → proceed to B0b. Not found → B0b's
  source conclusion decides between fixture expansion and disproven-closed for the pin
  scope.
- Not done: decoding; output-format changes.

**B0b — UE source audit** (the gate)

- Deliverables: version-fixed source references for the pin serialization layout
  (`UNiagaraNode` / pin `Serialize` paths) and `LinkedTo` boundaries; the gate decision
  recorded.
- Acceptance: every layout claim carries a version-fixed source citation.
- Failure branches (decision tree):
  - Pins absent from this fixture but serialized per UE source → Phase 1.5-style
    fixture expansion, then re-enter B0a.
  - Pins not serialized by UE → pin half disproven-closed; **the parameters path
    continues unaffected** (#525 narrows to its pin half only).

**B1-pre — #515 candidate-intake extension** (may run in parallel with B0)

- Deliverables: `tests/temp/scan_opaque_structs.py` extended to also collect structs
  inside `partial_metadata` exports (the current scan only covers `parse_status ==
  "opaque"` exports and structurally misses these); re-scan;
  `NiagaraVariable` / `NiagaraVariableMetaData` / `NiagaraVariant` /
  `NiagaraTypeDefinition` / `StaticSwitchTypeData` plus B0a-identified `Outputs`
  element types added to `docs/designs/issue-515-candidates.md` with fixture /
  SHA-256 / UE version / source references; one issue per struct passing the
  selection gate.
- Acceptance: the re-scan changes no parse output; candidate list updated; #515 roadmap
  doc notes the intake fix.

**B1 — Niagara struct decoding** (depends on B1-pre; the `NiagaraVariable` branch is
independent of B0, the `Outputs`-element branch waits for B0a identification)

- Order: `NiagaraVariable` (needed for parameters, first) → `Outputs`/`OutputVars`
  element structs → `NiagaraVariableMetaData` / `NiagaraVariant` (overlap with A3) →
  `NiagaraParameterStore` (already a #515 candidate; its source attribution must be
  version-fixed before use).
- Discipline: per the #515 roadmap — tagged fallback first; a native parser only when
  its trigger conditions are met; 4 test scenarios per parser (normal / truncated /
  unknown version / malformed) in `tests/temp/`.
- Acceptance: fields proven by evidence; malformed data keeps the opaque fallback; no
  regression.
- Not done: speculative layouts; promoting `opaque` status without evidence.

**B2 — #525 projection** (depends on B1; pin half depends on the B0 gate)

- Deliverables: node-handler extension with `parameters` (name/type) and
  `pin_references` (pin_name only when evidence supports it); `connected_to` projected
  only when `LinkedTo` evidence exists; the contract doc's "Deferred Fields" section
  replaced with the evidence-verified schema; #525 acceptance criteria closed one by one.
- Not done: consuming unproven tail bytes; fabricating `connected_to`.

### Convergence Gate (Epic close-out)

All of the following must hold before #521 closes:

1. Every Track A disposition recorded (A1/A2/A3 deliverables complete).
2. #525 closed.
3. Coverage table complete — no Niagara class undecided.
4. Niagara focused suite run manually and fully green (see Test Strategy for why CI
   does not cover it yet).
5. CI full suite green excluding the known pre-existing #518 failure.
6. Both `issue-521-niagara-export-parsing-plan.md` and
   `issue-521-niagara-field-contracts.md` reflect the final state.

Close #521 with a summary comment mapping each original requirement to its final
disposition.

## Failure Handling and Fallback

- **B0 gate failure**: follow the decision tree above; no sunk cost — `NiagaraVariable`
  decoding (B1) is useful in both branches.
- **Insufficient evidence anywhere**: stop decoding, keep `opaque`/skip, record the
  evidence gap; never guess binary layouts.
- **Regression**: routing changes are isolated per class migration; any regression
  rolls back that slice.
- **Status model**: `partial_metadata` only for handler-projected exports; `opaque`
  never promoted without evidence; unproven bytes always recorded as offset/size and
  left opaque.

## Test Strategy

- All new tests go to `tests/temp/` first (constraint), with pinned fixture SHA-256.
- Four scenarios per new parser: normal / truncated / unknown version / malformed.
- Baseline guards: the 59 Niagara tests stay green; full suite stays at 118 passed +
  the known #518 failure; export counts never regress (evidence tests assert counts).
- Diagnostic scans must not change parse output.
- Test promotion out of `tests/temp/` is NOT part of this roadmap — it belongs to the
  independent issue created in A1 (covering also the `constraints.md` "exactly 6 root
  test files" desync). During this roadmap, the convergence gate runs the Niagara suite
  manually.

## Effort Estimate

| Slice | Estimate |
|---|---|
| A1 / A2 / A3 | 0.5 d / 0.5 d / 1-2 d |
| B0a / B0b | 1 d / 1-2 d |
| B1-pre | 0.5-1 d |
| B1 (~5 structs, per-struct slices) | 1-2 d each, 5-10 d total |
| B2 | 2-3 d |
| **Total** | **~12-20 d**, dominated by B1; B0 branches may add or remove work. Heavily dependent on UE source audit results. |

## Document and Issue Update List

Documents:

- `docs/designs/issue-521-niagara-export-parsing-plan.md` — stale counts fixed, status
  updated, roadmap appended.
- `docs/designs/issue-521-niagara-field-contracts.md` — execution-flow section (A2),
  coverage table (A3), "Deferred Fields" replaced after B2.
- `docs/designs/issue-515-candidates.md` — B1-pre intake additions.
- `docs/designs/issue-515-opaque-structproperty-roadmap.md` — intake-fix note.

Issues:

- #521 body rewrite (A1).
- New issue: test promotion + `constraints.md` sync (A1).
- One #515 child issue per struct passing the selection gate (B1-pre).
- Independent issues for A3 classes qualifying for parsing.
- #525 updated and closed (B2).

## Plan Splitting

This spec is an umbrella roadmap. The first implementation plan covers the immediately
actionable work: A1, A2, A3, B0a, B0b, B1-pre. B1/B2 plans are written after the B0
gate result is known.

## Explicitly Out of Scope

- The pre-existing #518 JSON root-field test failure (separate issue).
- Test promotion / CI acceptance-test placement (separate issue, created in A1).
- VM bytecode / HLSL decoding.
- `NiagaraDataInterface*` and other Niagara classes absent from the fixture.
- Lyra-wide statistics (39.3% / 1,638) — not reproducible from repository fixtures.
