# Documentation Map

Use this page to avoid mixing current implementation documentation with the target refactor.

## Start Here

| Need | Authoritative source |
|---|---|
| Current user-facing behavior | [`README.md`](../README.md), then source and tests |
| Target parser architecture | [`designs/2026-08-26-package-first-uasset-parser-refactor.md`](designs/2026-08-26-package-first-uasset-parser-refactor.md) |
| Active design status | [`designs/README.md`](designs/README.md) |
| Archived designs and executed plans | [`designs/archive/README.md`](designs/archive/README.md) |
| Current output contract (v2 `uasset_read.package`) | [`formats/output/README.md`](formats/output/README.md) |
| Agent development rules | [`AGENTS.md`](../AGENTS.md) and [`reference/agent-dev-reference.md`](reference/agent-dev-reference.md) |
| Unreal package format facts | [`formats/uasset/Index.md`](formats/uasset/Index.md) plus UE source |
| Historical Semantic JSON 1.x format record | [`formats/uasset/semantic-json.md`](formats/uasset/semantic-json.md) — **not current**; v1 pipeline removed |
| Release history | [`release-notes/`](release-notes/) |
| Developer wiki | [`wiki/`](../wiki/) (separate git repository; describes the shipped v2 implementation) |

## Status Vocabulary

- **Current:** verified in the checked-out source/tests.
- **Target:** approved direction, not yet implemented.
- **Historical:** records an earlier implementation or decision.
- **Superseded:** must not guide new architecture work.

If documents disagree, use source/tests for current behavior and the canonical refactor design for future work.
