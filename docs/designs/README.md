# Active Design Documents

This directory contains active targets, contracts, and issue-specific evidence. Superseded repository-wide designs and executed closeout plans are physically separated under [`archive/`](archive/README.md).

## Authoritative Repository-Wide Target

- [`2026-08-26-package-first-uasset-parser-refactor.md`](2026-08-26-package-first-uasset-parser-refactor.md) — the only authoritative target architecture. It is a design baseline, not a claim that every deferred gap is implemented.

## Companion Contracts

These sit beside the canonical target on purpose. Each carries its own `status:` line. `historical` and executed plan records stay out of this directory; only binding contracts and open decisions remain.

| ID | Document | `status:` | Still binds |
| --- | --- | --- | --- |
| D1 | [`2026-08-31-v1-retirement-plan.md`](2026-08-31-v1-retirement-plan.md) | target | Gates in §3 and the §5/§6 decisions. §1/§2/§4 are pre-Phase-6 snapshots. **Gate C wiki residual committed locally 2026-09-13 (`wiki` `a10946b`); closes on wiki remote push only.** |
| D2 | [`2026-08-31-semantic-handlers-boundary.md`](2026-08-31-semantic-handlers-boundary.md) | current + target | §2.1/§2.3/§2.4 and stage 3. §1 and the `semantic/` half of §2 describe a deleted package. |
| G1 | [`2026-08-31-version-context-field-contract.md`](2026-08-31-version-context-field-contract.md) | target | VersionContext field contract. Amended 2026-09-13: production-used fields only (currently `depth`); no frozen speculative payload (cites revert `280b7e09`). |
| G2 | [`2026-08-31-agent-doc-cache-contract.md`](2026-08-31-agent-doc-cache-contract.md) | implemented | Process-local `lru_cache` on `parse_package_document` (Wave B, 2026-09-13). |
| G3 | [`2026-08-31-handler-registry-thread-safety.md`](2026-08-31-handler-registry-thread-safety.md) | target | Deferred until a real multi-threaded concurrent consumer of the handler registry exists (thread pool / async workers). Single-shot CLI/library use does not trigger. MCP is not in product scope. |
| G4 | [`2026-08-31-projection-layering.md`](2026-08-31-projection-layering.md) | target | Projection → truncation → serialization boundary. |
| S1 | [`2026-08-31-v2-contract-stability.md`](2026-08-31-v2-contract-stability.md) | current | Stable-field freeze of `format_version: "2.0"` (2026-09-13); experimental keys marked in schema; breaking stable changes bump major. |
| S2 | [`2026-08-31-payload-extraction-path.md`](2026-08-31-payload-extraction-path.md) | implemented (partial) | Cooked sidecar extraction via BulkData mapping. Zen/`.ucas` and unresolvable `export_index` still return `PAYLOAD_EXTRACTION_DEFERRED`. |
| S3 | [`2026-08-31-doc-status-marking-spec.md`](2026-08-31-doc-status-marking-spec.md) | current | The status-marking rules this index follows. |
| — | [`2026-09-02-peer-corroboration-usage-scheme.md`](2026-09-02-peer-corroboration-usage-scheme.md) | current | How external parsers may be used as evidence. |
| — | [`2026-09-13-deferred-capability-bundling.md`](2026-09-13-deferred-capability-bundling.md) | current | Bundle map for still-deferred work: Zen/IoStore chunk extract, SchemaProvider, `--diff`. Evaluation record only — no implementation. MCP transport is out of product scope. |
| — | [`2026-09-13-t15-t13-research-decision.md`](2026-09-13-t15-t13-research-decision.md) | current | Research decision only (**no implementation**). Constrains future T15/T13 work. |

## Executed plans (archive)

Ponytail / productize / byteswap / closeout plans that have already been executed live under [`archive/`](archive/README.md). They are historical evidence and must not be replayed as new work.

## Rules

1. Source and tests determine current behavior.
2. The authoritative target determines new repository-wide architecture work.
3. New designs must state `Target`, `Current-state`, `Historical`, or `Superseded` near the top.
4. Superseded repository-wide designs and executed closeout plans move to `archive/`; they do not remain beside active designs.
5. Do not add another repository-wide output architecture without updating the canonical target and this index.
6. Wiki and README pages must distinguish implemented behavior from planned behavior.
