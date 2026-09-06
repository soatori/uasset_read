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
| D1 | [`2026-08-31-v1-retirement-plan.md`](2026-08-31-v1-retirement-plan.md) | target | Gates in §3 and the §5/§6 decisions. §1/§2/§4 are pre-Phase-6 snapshots. **Gate C doc-sync rewritten to v2 in the wiki working tree (2026-09-05); closes on wiki commit+push.** |
| D2 | [`2026-08-31-semantic-handlers-boundary.md`](2026-08-31-semantic-handlers-boundary.md) | current + target | §2.1/§2.3/§2.4 and stage 3. §1 and the `semantic/` half of §2 describe a deleted package. |
| G1 | [`2026-08-31-version-context-field-contract.md`](2026-08-31-version-context-field-contract.md) | target | VersionContext field contract. |
| G2 | [`2026-08-31-agent-doc-cache-contract.md`](2026-08-31-agent-doc-cache-contract.md) | target | Deferred: shared-`PackageDocument` cache contract. |
| G3 | [`2026-08-31-handler-registry-thread-safety.md`](2026-08-31-handler-registry-thread-safety.md) | target | Deferred until multi-threaded MCP consumption is real. |
| G4 | [`2026-08-31-projection-layering.md`](2026-08-31-projection-layering.md) | target | Projection → truncation → serialization boundary. |
| S1 | [`2026-08-31-v2-contract-stability.md`](2026-08-31-v2-contract-stability.md) | target | Contract stability tiers; the `format_version` freeze declaration it requires is not yet emitted. |
| S2 | [`2026-08-31-payload-extraction-path.md`](2026-08-31-payload-extraction-path.md) | target | `PAYLOAD_EXTRACTION_DEFERRED` shape and the two future optimization routes. |
| S3 | [`2026-08-31-doc-status-marking-spec.md`](2026-08-31-doc-status-marking-spec.md) | current | The status-marking rules this index follows. |
| — | [`2026-09-02-peer-corroboration-usage-scheme.md`](2026-09-02-peer-corroboration-usage-scheme.md) | current | How external parsers may be used as evidence. |

## Archive

- [`archive/README.md`](archive/README.md) — superseded output, IR, Semantic 1.x, scope, test-suite, comparison, Core/Extras designs, and completed Phase 6 migration plan.

## Rules

1. Source and tests determine current behavior.
2. The authoritative target determines new repository-wide architecture work.
3. New designs must state `Target`, `Current-state`, `Historical`, or `Superseded` near the top.
4. Superseded repository-wide designs move to `archive/`; they do not remain beside active designs.
5. Do not add another repository-wide output architecture without updating the canonical target and this index.
6. Wiki and README pages must distinguish implemented behavior from planned behavior.
