# Deferred Capability Bundling Record

> **Status:** current（evaluation record；**no implementation**）
> Date: 2026-09-13
> Branch context: post Wave A+B productize on `docs/productize-unversioned` / `dev-0.6.0`
> Scope: Phase D of the archived [next-phase closeout](archive/2026-09-13-next-phase-closeout-and-deferred-gates.md). Evaluation only — this record does not authorize implementation of any deferred capability.

## Capabilities evaluated

| ID | Capability | Anchor | Status per docs |
| --- | --- | --- | --- |
| D-ZEN | `ZenPackageReader` + IoStore package body | #624; canonical Phase 5 | **not required (2026-09-27 product decision)**; retain only existing TOC metadata/truthful-unavailability regression |
| D-PAK | Pak container full product path | #625 | target; callers extract `.uasset` today |
| D-SCHEMA | Full `SchemaProvider` / cooked unversioned | canonical Phase 2 / Property System | **not required (2026-09-27 product decision)**; editor `.usmap` path remains partial/current, cooked/Zen unversioned is outside the product target |
| D-PLA | Payload-only parse (route A) | [`2026-08-31-payload-extraction-path.md`](2026-08-31-payload-extraction-path.md) | target; gated on real descriptors, not on perf demand |
| D-G2 | Shared `PackageDocument` cache | [`2026-08-31-agent-doc-cache-contract.md`](2026-08-31-agent-doc-cache-contract.md) (G2) | target; contract frozen; free-standing |
| D-BATCH | CLI `--batch` | [`2026-08-31-v1-retirement-plan.md`](2026-08-31-v1-retirement-plan.md) §5 | **current (v2 live)** — directory walk + `uasset_read.batch` report; v1 `batch_worker` orchestration is not rebuilt |
| D-DIFF | CLI `--diff` | same | **decided 2026-09-22:** not a product CLI target (F-D); remains unsupported |
| D-CPP | Blueprint C++ skeleton | Gate K retired the C++ pseudocode chain; Phase 4.5 list keeps skeleton unmigrated | **decided 2026-09-22:** old string-chain skeleton **permanently retired (C-A)**; v3 typed C++ projection is current; any future increment needs a **new** emission design |

## Edge table (verified against designs and README)

Coupling values: `hard` (same fixtures, same trust boundary), `soft` (shared protocol or consumer only), `none`.

| Edge | Coupling | Evidence / correction vs seed hypothesis |
| --- | --- | --- |
| D-ZEN ↔ D-PAK | soft | Canonical §Source defines `PakEntrySource` and `IoStoreChunkSource` as separate first-batch Sources; fixtures differ (`.pak` vs `.utoc/.ucas`); pack index is not the IoStore package-body trust path. Share only the `read_at()` protocol and compression/encryption capability reporting. **Seed confirmed.** |
| D-ZEN ↔ D-PLA | soft (hard only for the Zen-descriptor variant of route A) | **Correction.** S2's hard bind is "real descriptors" (#623–#627 era), not Zen per se. Legacy cooked packages carry `FPackageTrailer` + sidecars (partially implemented since 2026-09-07); Zen layout carries descriptors inside the container. Route A joins Bundle 1 only when the target fixtures are Zen/IoStore payloads; a loose-sidecar variant would ride legacy fixtures instead. Doing A early against fabricated descriptors is exactly what S2 forbids. |
| D-ZEN ↔ D-SCHEMA | none | SchemaProvider is the property-schema boundary (canonical Property System §Unversioned); layout-orthogonal. No shared fixtures, no shared trust boundary. **Seed confirmed.** |
| D-SCHEMA ↔ D-PAK | none | Property schema vs pack index. **Seed confirmed.** |
| D-G2 ↔ D-PLA | soft | S2 Route B: G2 accelerates repeat `extract_payload` calls with zero new parser code; does not create descriptors; key includes `depth`/`object_ids`, so no first-parse speedup. **Seed confirmed.** |
| D-G2 ↔ all | soft | Pure parse-layer performance contract; no API change; no fixtures. **Seed confirmed.** |
| D-BATCH ↔ D-DIFF | soft | CLI surface adjacency only. **2026-09-13 correction:** D-BATCH is live on the v2 CLI (`cli.py` `--batch`/`--batch-format`); only D-DIFF remains deferred. No shared orchestration module. |
| D-CPP ↔ D-ZEN | none | Rule 4. **Seed confirmed.** |
| D-CPP ↔ Wave B blueprint work | soft | Consumes the existing `BlueprintFamilyHandler` object model; because Gate K retired the pseudocode chain, D-CPP would be a new emission design, not a migration. **Seed confirmed.** |
| D-PLA ↔ D-SCHEMA | none | Route A maps trailer/BulkData byte regions; unversioned field schemas would change which bytes are properties, a different trust boundary. (Not in seed; added for completeness.) |

## Bundles

| Bundle | Members | Why together | Preconditions | fixture_gaps | Suggested order |
| --- | --- | --- | --- | --- | --- |
| 1 — Container body | D-ZEN; D-PLA **only** the Zen/IoStore-descriptor variant | **Not scheduled.** Existing TOC metadata remains a truthful boundary; no Zen package-body or chunk decoder will be developed in the current product scope. | None | No further Zen/IoStore body acquisition | Closed |
| 2 — Property schema | D-SCHEMA alone | **Not scheduled.** Editor-`.usmap` path remains partial/current; cooked-unversioned and generic `SchemaProvider` are outside the product target. | None | No further cooked-unversioned fixture acquisition | Closed |
| 3 — Workflow CLI | D-DIFF only (D-BATCH is already current) | Pure workflow; never blocks format work (rule 2). | Explicit user product need for schema-compare diff | None (works on existing loose fixtures) | Whenever product asks |
| 4 — Perf | D-G2 | Free-standing cheap win (rule 3); S2 Route B rides it for free; contract already frozen with no API change. | A real multi-extract consumer path (long-lived process or multi-file session; already present via G2 + `--batch`) | None | Anytime; may land before or after Bundle 1 |
| 5 — Blueprint depth | D-CPP — only on explicit product revival | Rule 4: bundles only with Blueprint semantic-depth work, never with containers or schema. Gate K already retired the C++ pseudocode chain, so revival means a new design. | Explicit product request; a separate emission design | Blueprint fixtures already exist; the missing input is the design, not samples | Lowest priority |
| Own project | D-PAK | Pack-index trust path ≠ package-body trust path; different fixtures; no shared IoStore trust path appears in docs. Revisit only if a Pak source review finds one. | Pak format source review; `PakEntrySource` implementation; compression/encryption capability reporting | Redistributable `.pak` fixtures | After or independent of Bundle 1 |

## Explicit non-bundles

- **D-PAK ∉ Bundle 1** by default; promoted into Bundle 1 only if a source review demonstrates a shared IoStore trust path (current docs show them separate).
- **D-SCHEMA ∉ Bundle 1**; it may run in parallel but must never gate Zen.
- **D-BATCH / D-DIFF ∉ any format bundle** (rule 2: pure workflow never blocks format work). D-BATCH needs no further product decision for the existing directory-walk mode; only richer orchestration would.
- **D-CPP ∉ any container or schema bundle** (rule 4).
- **No sample acquisition inside any bundle** (rule 5); every fixture gap above is a precondition, not a bundle task.

## Non-goals of this record

- Does not authorize Zen / Pak / SchemaProvider / diff / C++ skeleton implementation. (D-BATCH is already current on the v2 CLI; this record does not expand it.)
- Does not change `fixture_gaps` or README feature claims.
- Does not schedule work or pick dates; ordering above is dependency-driven, not a roadmap commitment.

## Next execution trigger

A new implementation plan is required before any Bundle N code lands, and it must name: (a) the bundle and its preconditions status, (b) UE-source evidence paths for the trust boundaries involved, (c) fixture provenance for every gap being closed, and (d) explicit user authorization. Bundle 4 (D-G2) may ship as its own small plan at any time because its contract is already frozen in the G2 document.

## Open questions for the user

1. ~~Is there a real multi-file orchestration consumer today for `--batch`?~~ Partially answered 2026-09-13: simple directory-walk `--batch` is **live**; the open question is only whether richer orchestration (isolation, resume, formats beyond jsonl) is ever wanted.
2. ~~What is `--diff`'s comparison target — two `PackageDocument`s, or document vs golden?~~ **Closed 2026-09-22:** `--diff` is **not** a product CLI target (permanent non-goal F-D). Do not implement.
3. ~~Is the Blueprint C++ skeleton ever a wanted product feature, or permanently retired alongside Gate K?~~ **Closed 2026-09-22:** old skeleton **permanently retired**; see residual decisions.
4. ~~Should the known-missing `.ucas` gap (#624 test failures) become the formal Bundle 1 fixture goal, or wait for a separately redistributable Zen package?~~ **Closed 2026-09-27:** Zen/IoStore package-body work is outside the product target.
5. ~~Is a loose-sidecar (legacy cooked, no Zen) variant of route A worth a small separate slice, or should route A fold entirely under "real descriptors + Zen"?~~ **Closed 2026-09-27:** no new route-A work is scheduled.

**Residual note:** product answers are closed for the current scope: Zen/IoStore package-body/chunk decoding and cooked unversioned/SchemaProvider are outside the product target; diff is a permanent non-goal and the old C++ skeleton is retired.

**Out of product scope (2026-09-13):** MCP as an agent transport/server is **not** a repository target. Agent tools remain a bounded in-library API. G3’s trigger is generic multi-threaded registry concurrency, not MCP.

## Residual product decisions (2026-09-22)

Recorded after v3 Tasks 1–12 closeout. These decisions **do not authorize implementation** of deferred capabilities; any later code still requires a separate plan meeting “Next execution trigger”.

| ID | Decision | Rationale |
| --- | --- | --- |
| D-SCHEMA | **S-C — outside product target.** No Bundle 2 and no cooked-unversioned fixture acquisition. The editor `.usmap` mapping path remains supported as a bounded partial capability; cooked/Zen unversioned and a general `SchemaProvider` are not scheduled. | Avoids acquiring/installing mapping dumpers and maintaining a cooked schema contract that is not needed by the current product. Existing editor fixtures continue to protect the supported partial path. |
| D-DIFF | **F-D — permanent non-goal.** CLI remains without `--diff`. | No live product need; comparison target never specified; Gate A already limits golden use to regression ID, not schema constraint. |
| D-CPP (old skeleton) | **C-A — permanently retired.** Gate K string `cpp_code` chain stays retired. v3 typed C++ projection (`projections/`) is current and sufficient until a **new** emission design is explicitly requested. | Avoids second parallel C++ output path; bundling rule 4. |
| Automatic output sidecar | **Keep single-file canonical writer** (`sidecars[]` empty; oversize → `OutputBudgetError`). Measured size/safety probe in `temp/` remains optional follow-up, **not** scheduled. | Plan invariant: physical sidecars only after a measured hard boundary. |
| G3 handler registry concurrency | **G-B — remain deferred** until a quantified multi-threaded registry consumer exists (thread pool / async workers / long-lived concurrent service). Single-shot CLI/library use does not trigger. MCP is not in product scope. | Design README G3; no such consumer in-tree. |
| Bundle 1 Zen/IoStore fixtures | **Closed:** no further Zen/IoStore body fixture acquisition or reader work in the current product scope. | Existing TOC metadata remains only for boundary regression. |
| `docs/superpowers/` / `docs/compose/` tracking | **Keep tracked** on `dev-0.6.0` for the v3 delivery push (planning materials already in history). | Delivery decision; untrack cleanup would be a separate explicit change. |

**Delivery (2026-09-22):** package A design-status docs committed (`2f6aed8c`). Release strategy **A** selected — normal `git push origin dev-0.6.0` (no force; remote `origin` = soatori). Strategy analysis: `temp/C-release-strategy.md` (not committed; `temp/` is ignored). Decision brief evidence: `temp/B-product-decision-brief.md` (ignored).
