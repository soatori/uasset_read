# T15 / T13 Research Decision Record

> **Status:** current (research decision only; **no implementation**)
> Date: 2026-09-13
> Branch context: post Wave A+B productize; plan `2026-09-13-next-phase-closeout-and-deferred-gates.md`

## Scope

Wave A left two optional follow-ups that this phase researched before any code change:

1. **T15** — replace `tests/test_core.py::_run_cases` with native pytest collection.
2. **T13 residual** — second test-tree dedupe pass after `71ab2b7b`.

## Decision

| Item | Decision |
| --- | --- |
| T15 `_run_cases` | **DEFER** |
| T13 residual tightening | **DEFER** (leaning **NO-GO**) |

**Neither item authorizes production or test-structure refactors in this phase.**

## T15 rationale

- 8 call sites / 120 cases; fail-fast + `"{case_name}: {exc}"` message prefix are load-bearing.
- `test_test_suite_structure_gate` (`tests/test_core.py` ~2959–2994) requires exactly 14 top-level `test_*` functions and **bans decorators** on them — `@pytest.mark.parametrize` cannot land without a prior, deliberate gate amendment.
- High order risk at export-failure (stacked monkeypatch re-patches) and medium risk at handler-registry (live `_HANDLERS` reads before isolation cases).
- A later **scoped GO** may cover only pure/read-only sites (reader boundaries, property bag, package document, projection views/budget, schema) **after** a separate design amendment. Sites 4–5 stay on `_run_cases`.

## T13 residual rationale

- Sliding-window scan: **0** hits at 10-line/≥3 and 8-line/≥3 true duplicates.
- Residual 6-line near-shapes in `tests/test_blueprint_decode.py` are intentional isolation scaffolds with different assertions.
- `tests_python` headroom ≈ 933 lines under `tests/size-baseline.json` — no ratchet pressure.
- Further “boilerplate extraction” would re-shape contract-local scaffolds, not remove waste.

## Evidence (scratch, not committed)

- `temp/c1-run-cases-survey.md`
- `temp/c2-test-tree-survey.md`

## Non-goals

- Does not change `_run_cases`, structure gate, or any test file.
- Does not reopen Wave A T15 execution without a new implementation plan.
