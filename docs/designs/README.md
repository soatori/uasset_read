# Active Design Documents

This directory contains active targets and issue-specific evidence. Superseded repository-wide designs are physically separated under `archive/`.

## Authoritative Repository-Wide Target

- [`2026-08-26-package-first-uasset-parser-refactor.md`](2026-08-26-package-first-uasset-parser-refactor.md) — the only authoritative target architecture. It is a design baseline, not a claim that the refactor has been implemented.

## Issue-Specific Documents

Files named `issue-*` contain focused evidence, gates, or execution plans. Their status is local to that issue and does not override the repository-wide target. Verify implementation claims in source, tests, real samples, and the live issue state.

## Companion Contracts (`2026-08-31-*`, `2026-09-02-*`)

These sit beside the canonical target on purpose. Each carries its own `status:` line and, where a migration has since landed, a dated execution record naming which sections are snapshots and which still bind. `historical` documents stay in place by design; only `superseded` repository-wide designs move to `archive/` (rule 4).

| ID | Document | `status:` | Still binds |
| --- | --- | --- | --- |
| D1 | [`2026-08-31-v1-retirement-plan.md`](2026-08-31-v1-retirement-plan.md) | target | Gates in §3 and the §5/§6 decisions. §1/§2/§4 are pre-Phase-6 snapshots. **Gate C wiki residual committed locally 2026-09-13 (`wiki` `a10946b`); closes on wiki remote push only.** |
| D2 | [`2026-08-31-semantic-handlers-boundary.md`](2026-08-31-semantic-handlers-boundary.md) | current + target | §2.1/§2.3/§2.4 and stage 3. §1 and the `semantic/` half of §2 describe a deleted package. |
| G1 | [`2026-08-31-version-context-field-contract.md`](2026-08-31-version-context-field-contract.md) | target | VersionContext field contract. Amended 2026-09-13: production-used fields only (currently `depth`); no frozen speculative payload (cites revert `280b7e09`). |
| G2 | [`2026-08-31-agent-doc-cache-contract.md`](2026-08-31-agent-doc-cache-contract.md) | implemented | Process-local `lru_cache` on `parse_package_document` (Wave B, 2026-09-13). |
| G3 | [`2026-08-31-handler-registry-thread-safety.md`](2026-08-31-handler-registry-thread-safety.md) | target | Deferred until multi-threaded MCP consumption is real. |
| G4 | [`2026-08-31-projection-layering.md`](2026-08-31-projection-layering.md) | target | Projection → truncation → serialization boundary. |
| S1 | [`2026-08-31-v2-contract-stability.md`](2026-08-31-v2-contract-stability.md) | current | Stable-field freeze of `format_version: "2.0"` (2026-09-13); experimental keys marked in schema; breaking stable changes bump major. |
| S2 | [`2026-08-31-payload-extraction-path.md`](2026-08-31-payload-extraction-path.md) | target | `PAYLOAD_EXTRACTION_DEFERRED` shape and the two future optimization routes. |
| S3 | [`2026-08-31-doc-status-marking-spec.md`](2026-08-31-doc-status-marking-spec.md) | current | The status-marking rules this index follows. |
| — | [`2026-09-02-peer-corroboration-usage-scheme.md`](2026-09-02-peer-corroboration-usage-scheme.md) | current | How external parsers may be used as evidence. |
| — | [`2026-09-10-codebase-slimming-plan.md`](2026-09-10-codebase-slimming-plan.md) | target | Reviewed slimming plan. Phase A, Gate G (parent_resolver), Gate K (C++ pseudocode), and Gate L (log cleanup) executed 2026-09-10. Remaining Gate G items (agent_tools/iostore/mappings) stay keep/tidy-only. |
| — | [`2026-09-12-ponytail-residual-cuts.md`](2026-09-12-ponytail-residual-cuts.md) | current | Residual ponytail cuts after audit waves 0–13: identity map, false import mirror, write-only fields, CubeBuilder skip-list contradiction. Executed 2026-09-12 (`f55b2d1e`/`4bface99`); suite 220 passed. |
| — | [`2026-09-12-ponytail-evaluation-fix-plan.md`](2026-09-12-ponytail-evaluation-fix-plan.md) | current | Adversarially reviewed ponytail subtraction + two real defects (CI ruff, decode dropping Kismet bodies). Wave A executed 2026-09-12 (T1–T14/T16; T15 deferred). |
| — | [`2026-09-12-post-refactor-productize-plan.md`](2026-09-12-post-refactor-productize-plan.md) | current | Merged master sequencer: Wave A = ponytail plan; Wave B = productize (state_count, exec edges, tag-only node_data, unversioned partial). **Executed** on `docs/productize-unversioned` (Wave A + Wave B + review hardening through `2419de4e`); T15 `_run_cases` intentionally out of scope. |
| — | [`2026-09-13-next-phase-closeout-and-deferred-gates.md`](2026-09-13-next-phase-closeout-and-deferred-gates.md) | current | A1–D1 executed; merged to `dev-0.6.0`. Follow-on: residual docs/gates + G2 + Bundle 1/2 plan below. |
| — | [`2026-09-13-deferred-capability-bundling.md`](2026-09-13-deferred-capability-bundling.md) | current | Bundle map for Zen/Schema/G2/diff. **D-BATCH is current** on the v2 CLI (2026-09-13); only `--diff` remains deferred among the old workflow pair. |
| — | [`2026-09-13-residual-closeout-g2-zen-schema-plan.md`](2026-09-13-residual-closeout-g2-zen-schema-plan.md) | current | **Wave A + B executed** (S1 freeze, batch口径, wiki Gate C local commit, G2 cache). **Wave C/D deferred** (Zen/IoStore, SchemaProvider). No push; product-deferred (diff/Pak/C++) out of scope. |

## Archive

- [`archive/README.md`](archive/README.md) — superseded output, IR, Semantic 1.x, scope, test-suite, comparison, Core/Extras designs, and completed Phase 6 migration plan.

## Rules

1. Source and tests determine current behavior.
2. The authoritative target determines new repository-wide architecture work.
3. New designs must state `Target`, `Current-state`, `Historical`, or `Superseded` near the top.
4. Superseded repository-wide designs move to `archive/`; they do not remain beside active designs.
5. Do not add another repository-wide output architecture without updating the canonical target and this index.
6. Wiki and README pages must distinguish implemented behavior from planned behavior.
