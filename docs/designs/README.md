# Active Design Documents

This directory contains active targets, contracts, and issue-specific evidence. Superseded repository-wide designs and executed closeout plans are physically separated under [`archive/`](archive/README.md).

## Authoritative Repository-Wide Target

- [`2026-08-26-package-first-uasset-parser-refactor.md`](2026-08-26-package-first-uasset-parser-refactor.md) — the only authoritative target architecture. It is a design baseline, not a claim that every deferred gap is implemented.

## Companion Contracts

These sit beside the canonical target on purpose. Each carries its own `status:` line. `historical` and executed plan records stay out of this directory; only binding contracts and open decisions remain.

| ID | Document | `status:` | Still binds |
| --- | --- | --- | --- |
| D1 | [`2026-08-31-v1-retirement-plan.md`](2026-08-31-v1-retirement-plan.md) | target | Gates in §3 and the §5/§6 decisions. §1/§2/§4 are pre-Phase-6 snapshots. **Gate C wiki residual closed 2026-09-13 after wiki remote push (`a10946b` + `8821779`).** |
| D2 | [`2026-08-31-semantic-handlers-boundary.md`](2026-08-31-semantic-handlers-boundary.md) | current + target | §2.1/§2.3/§2.4 and stage 3. §1 and the `semantic/` half of §2 describe a deleted package. |
| G1 | [`2026-08-31-version-context-field-contract.md`](2026-08-31-version-context-field-contract.md) | target | VersionContext field contract. Amended 2026-09-13: production-used fields only (currently `depth`); no frozen speculative payload (cites revert `280b7e09`). |
| G2 | [`2026-08-31-agent-doc-cache-contract.md`](2026-08-31-agent-doc-cache-contract.md) | implemented | Process-local `lru_cache` on `parse_package_document` (Wave B, 2026-09-13). |
| G3 | [`2026-08-31-handler-registry-thread-safety.md`](2026-08-31-handler-registry-thread-safety.md) | target | Deferred until a real multi-threaded concurrent consumer of the handler registry exists (thread pool / async workers). Single-shot CLI/library use does not trigger. MCP is not in product scope. |
| G4 | [`2026-08-31-projection-layering.md`](2026-08-31-projection-layering.md) | superseded (v3 envelope layering) | The projection → truncation → serialization split (`_project_envelope` / `_enforce_budget`, pagination/`max_bytes`) was retired with the 2026-09-28 v4 amendment: the single v4 producer has no pagination or budget layer. Historical record only. |
| S2 | [`2026-08-31-payload-extraction-path.md`](2026-08-31-payload-extraction-path.md) | implemented (partial) | Cooked sidecar extraction via BulkData mapping. Zen/`.ucas` is outside the product target; unresolvable `export_index` returns `PAYLOAD_EXTRACTION_DEFERRED`. |
| S3 | [`2026-08-31-doc-status-marking-spec.md`](2026-08-31-doc-status-marking-spec.md) | current | The status-marking rules this index follows. |
| — | [`2026-09-02-peer-corroboration-usage-scheme.md`](2026-09-02-peer-corroboration-usage-scheme.md) | current | How external parsers may be used as evidence. |
| — | [`2026-09-13-deferred-capability-bundling.md`](2026-09-13-deferred-capability-bundling.md) | current | Product decision record: Zen/IoStore full decode and cooked unversioned/SchemaProvider are outside the product target; `--diff` remains a permanent non-goal; old C++ skeleton is retired; sidecar remains single-file; G3 stays deferred. MCP transport is out of product scope. |
| — | [`2026-09-13-t15-t13-research-decision.md`](2026-09-13-t15-t13-research-decision.md) | current | Research decision only (**no implementation**). Constrains future T15/T13 work. |
| — | [`2026-09-15-parser-quality-system.md`](2026-09-15-parser-quality-system.md) | target | Diagnostic.reason taxonomy + sample quality baseline gates. |
| — | [`../superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`](../superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md) | superseded (typed C++ target / v3 envelope) + current (static Blueprint IR/CFG scope) | Typed C++ projection and `format_version: "3.0"` are retired targets (2026-09-28 v4 amendment). Static Blueprint IR/CFG/correlation requirements remain current and bind the companion Blueprint plan. Supersedes the archived S1 v2 stable-envelope freeze. |
| — | [`../superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`](../superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md) (plan `../superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md` was local-only and no longer exists) | historical / executed | Tasks 1–12 landed on `dev-0.6.0`; this is execution evidence, not an active target or an executable plan. |

## Executed plans (archive)

Ponytail / productize / byteswap / closeout plans that have already been executed live under [`archive/`](archive/README.md). They are historical evidence and must not be replayed as new work.

Execution records retained under `../superpowers/plans/` are also evidence only when their header says `completed` or `historical`. Agents must not discover or replay them during ordinary implementation, diagnosis, or documentation work. A new execution requires a new plan or an exact path explicitly named by the user.

## Active v4 implementation target

- [`2026-08-26-package-first-uasset-parser-refactor.md`](2026-08-26-package-first-uasset-parser-refactor.md) — canonical target, 2026-09-28 v4 output amendment: package output `format_version: "4.0"`, exactly `normal`/`debug` modes, single full document per package, C++ projection retired, Blueprint IR/CFG/static semantics preserved.
- [`contract/package_document_v4.schema.json`](contract/package_document_v4.schema.json) — frozen v4 output contract (Draft 2020-12). The v3 contract files were deleted at the freeze.
- [`../superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`](../superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md) — static Blueprint IR/CFG/correlation scope only (its typed C++ and v3 envelope sections are superseded).

## v3 Execution Evidence

- `../superpowers/plans/2026-09-16-complete-static-uasset-blueprint-cpp-plan.md` (local-only plan, no longer present; surviving record is [`../superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md`](../superpowers/specs/2026-09-16-complete-static-uasset-blueprint-cpp-design.md)) — Tasks 1–12 implemented on `dev-0.6.0` after merge `8727b067` (controller review pass; the recorded 444-passed full suite is historical post-merge evidence, not the current count); historical evidence only.

## Rules

1. Source and tests determine current behavior.
2. The authoritative target determines new repository-wide architecture work.
3. New designs must state `Target`, `Current-state`, `Historical`, or `Superseded` near the top.
4. Superseded repository-wide designs and executed closeout plans move to `archive/`; they do not remain beside active designs.
5. Do not add another repository-wide output architecture without updating the canonical target and this index.
6. Wiki and README pages must distinguish implemented behavior from planned behavior.
7. Do not use this index as a plan-discovery queue. Read one named document for the current request, then stop when its status is historical, executed, or complete.
