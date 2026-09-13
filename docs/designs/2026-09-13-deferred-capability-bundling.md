# Deferred Capability Bundling Record

> **Status:** current（evaluation record；**no implementation**）
> Date: 2026-09-13
> Branch context: post Wave A+B productize on `docs/productize-unversioned` / `dev-0.6.0`
> Scope: Phase D of the archived [next-phase closeout](archive/2026-09-13-next-phase-closeout-and-deferred-gates.md). Evaluation only — this record does not authorize implementation of any deferred capability.

## Capabilities evaluated

| ID | Capability | Anchor | Status per docs |
| --- | --- | --- | --- |
| D-ZEN | `ZenPackageReader` + IoStore package body | #624; canonical Phase 5 | target; `.utoc/.ucas` fixtures missing |
| D-PAK | Pak container full product path | #625 | target; callers extract `.uasset` today |
| D-SCHEMA | Full `SchemaProvider` / cooked unversioned | canonical Phase 2 / Property System | partial (editor `.usmap`); cooked deferred; no full `SchemaProvider` in `src/` |
| D-PLA | Payload-only parse (route A) | [`2026-08-31-payload-extraction-path.md`](2026-08-31-payload-extraction-path.md) | target; gated on real descriptors, not on perf demand |
| D-G2 | Shared `PackageDocument` cache | [`2026-08-31-agent-doc-cache-contract.md`](2026-08-31-agent-doc-cache-contract.md) (G2) | target; contract frozen; free-standing |
| D-BATCH | CLI `--batch` | [`2026-08-31-v1-retirement-plan.md`](2026-08-31-v1-retirement-plan.md) §5 | **current (v2 live)** — directory walk + `uasset_read.batch` report; v1 `batch_worker` orchestration is not rebuilt |
| D-DIFF | CLI `--diff` | same | deferred; awaits product decision |
| D-CPP | Blueprint C++ skeleton | Gate K retired the C++ pseudocode chain; Phase 4.5 list keeps skeleton unmigrated | unmigrated; needs explicit product revival |

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
| 1 — Container body | D-ZEN; D-PLA **only** the Zen/IoStore-descriptor variant | Same trust boundary: container package body + trailer→region mapping. Payload-only without real Zen descriptors would just re-fabricate a second fake descriptor (S2's explicit warning). | UE source evidence: `FZenPackageSummary` / `ExportBundleData` / IoStore TOC write path; `IoStoreChunkSource` in the Source layer; bounded-read invariants | Redistributable `.utoc/.ucas` Zen packages entering `tests/samples/` with manifest hashes (the two known ucas test failures mark this gap; **no sample acquisition inside the bundle**) | 1 |
| 2 — Property schema | D-SCHEMA alone | Orthogonal trust boundary (export-serial property bytes); editor-`.usmap` unversioned path is already partial and independent of layout work. | UE `SchemaProvider` / unversioned serialization evidence; cooked-unversioned fixtures; explicit opaque-tail behavior preserved | Cooked unversioned fixtures with matching schema sources | Parallel after Bundle 1 lands, or whenever cooked fixtures become available |
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
2. What is `--diff`'s comparison target — two `PackageDocument`s, or document vs golden?
3. Is the Blueprint C++ skeleton ever a wanted product feature, or permanently retired alongside Gate K?
4. Should the known-missing `.ucas` gap (#624 test failures) become the formal Bundle 1 fixture goal, or wait for a separately redistributable Zen package?
5. Is a loose-sidecar (legacy cooked, no Zen) variant of route A worth a small separate slice, or should route A fold entirely under "real descriptors + Zen"?

**Residual note 2026-09-13:** product answers above remain open except batch live-mode. Residual plan executed Waves A–B only (S1 freeze, batch口径, wiki Gate C local commit, G2 cache); **Wave C/D (Zen/IoStore, SchemaProvider) deferred by user**; diff/Pak/C++ not implemented.

**Out of product scope (2026-09-13):** MCP as an agent transport/server is **not** a repository target. Agent tools remain a bounded in-library API. G3’s trigger is generic multi-threaded registry concurrency, not MCP.
