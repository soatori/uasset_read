# Sample-First Test Baseline

status: target

## Summary

Replace the current broad unit/integration test tree with a small, sample-first
baseline. The tracked Unreal samples remain the primary evidence. The baseline
contains only two test modules and no more than 100 collected pytest items.
Temporary probes remain local under `temp/` and are never part of the tracked
baseline or CI.

This is a test-architecture change. It does not change parser behavior,
production APIs, or the sample corpus.

## Current state

The checkout currently has:

- 36 `test_*.py` files, including `tests/serialization/test_package_summary_tag.py`.
- 477 collected pytest items.
- `tests/test_core.py` and `tests/test_samples.py` as large mixed test homes.
- Synthetic byte fixtures, direct parser unit tests, CLI tests, contract tests,
  and real-sample tests mixed across the tree.
- A size baseline that limits source, test, and documentation lines, but does
  not enforce a maximum number of test files or collected items.
- A canonical design rule that requires `test_core.py`, `test_samples.py`, and
  `test_size_baseline.py`, and explicitly allows a serialization test subtree.

The existing `tests/samples/` corpus is the authoritative tracked fixture set:
its manifest has 66 package samples plus container metadata, sidecars,
quality limits, and golden references.

## Target structure

The tracked test tree will contain only these pytest test modules:

```text
tests/
  conftest.py                 # collection-budget hook only
  test_samples.py             # manifest-driven real-sample baseline
  test_size_baseline.py       # repository and test-suite budget baseline
  samples/                    # existing samples and sample metadata
```

`tests/serialization/` and every other existing `test_*.py` module are removed.
`tests/fixtures.py` is removed unless the final sample driver still needs a
small helper that cannot live locally in `test_samples.py`; no general fixture
library is retained.

The hard limits are:

- At most 2 tracked `tests/test_*.py` files.
- At most 100 collected pytest items, including parameterized items.
- Existing source, documentation, wheel, and test-tree size ceilings remain
  active; the test-tree ceiling is tightened to the measured post-cleanup
  value rather than carrying the old 11k-line allowance.
- No permanent pytest test subtree other than `tests/samples/`.

The collection budget is enforced during pytest collection so `python -m
pytest -q` and CI cannot silently run an overgrown suite. The size baseline
also checks the tracked test-file count and reports the configured limits.

## Sample test design

`tests/test_samples.py` is the only behavior-oriented baseline module. It uses
`tests/samples/manifest.json` and the existing sample metadata as its input;
it does not manufacture UE package bytes or use mocks to stand in for package
objects.

The driver contains a small number of aggregate checks plus one parameterized
parse item per manifest package. The intended budget is 66 parse items and
fewer than 34 aggregate items.

The checks are:

1. Manifest closure: every manifest sample exists, its SHA-256 and size match,
   declared sidecars exist, and no tracked `.uasset`/`.umap` is omitted.
2. Package parse: every manifest package produces a `PackageDocument` with the
   declared layout, version, export count, and `bIsAsset` count. Recoverable
   diagnostics remain structured; fatal parse failure fails the named sample.
3. Selected depth/semantic checks: only checks backed by real samples and
   existing sample metadata remain. They are aggregate checks over the
   selected samples, not a new per-function unit-test matrix.
4. Output checks: existing golden files and the package-document schema are
   validated from the sample directory.
5. Quality checks: `quality_baseline.json` remains the source of diagnostic
   ceilings, forbidden codes, and aggregate trailing-byte limits.
6. Container and sidecar checks: committed `.pak`/`.utoc` metadata and package
   sidecars are tested only through their real files under `tests/samples/`.

If a semantic expectation is not already represented by manifest, quality, or
golden metadata, it must either be reduced to a sample-backed aggregate
assertion or be treated as a temporary probe. It must not create another
permanent test module merely to preserve a historical unit-test shape.

## Baseline and temporary probes

`tests/test_size_baseline.py` retains the existing source/test/docs line and
tracked-file ratchets and adds the two test-suite limits. It does not parse
synthetic package bytes or duplicate sample assertions.

`tests/conftest.py` contains only the collection-budget hook. It must not grow
domain fixtures, sample parsers, or compatibility aliases.

Temporary investigations, malformed-byte experiments, one-off CLI checks,
performance probes, and regression reproductions go under untracked `temp/`.
They may import the package and use real samples, but they are not collected by
pytest, are not included in `tests/size-baseline.json`, and are not run by CI.
The existing CI directory-compliance rule continues to keep `temp/` out of the
tracked default branch.

## Migration and documentation

The implementation must update the canonical and user-facing rules together:

- Update `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` to
  replace the old three-file/core-AST policy with the two-file sample-first
  policy and the 2-file/100-item limits.
- Update `docs/reference/agent-dev-reference.md` so the formal test contract
  points to the sample driver and size baseline, not `test_core.py`.
- Update the README test commands and quality-baseline examples.
- Keep `.github/workflows/ci.yml` running the normal pytest command; the
  collection hook makes the item limit apply in CI without a second test
  runner. Ruff continues to lint the reduced `tests/` tree.
- Update `tests/size-baseline.json` with the measured post-cleanup ceilings.

No production source file is changed as part of this migration. The sample
files, manifest hashes, golden files, and quality baseline are preserved unless
an existing expectation is proven stale by the new sample driver; such a change
must be a separate reviewable data update.

## Alternatives considered

### Keep the current tests and add a non-default marker

Rejected. It leaves the maintenance and collection burden in place and allows
the non-default suite to become an unowned second baseline.

### Consolidate all current tests into two large modules

Rejected. It would meet the file count but retain synthetic/unit coverage as
the dominant test method and would require deleting or hiding hundreds of
items. The desired simplification is a change in evidence source, not only a
file move.

### Sample baseline plus a permanent critical-unit module

Not selected for this migration. It would protect more malformed-input and CLI
contracts, but it conflicts with the approved sample-first scope and leaves a
second permanent behavior suite. A later request can add a narrowly defined
critical gate with a separate item budget.

## Acceptance criteria

The migration is complete when all of the following are true:

- `tests/samples/` sample and metadata files remain present and unchanged in
  content unless an explicitly reviewed expectation update is required.
- `git ls-files 'tests/test_*.py'` reports exactly two files.
- `python -m pytest --collect-only -q` collects no more than 100 items and the
  collection hook fails if the limit is exceeded.
- `python -m pytest -q` passes using only the sample driver and necessary
  baseline checks.
- No deleted test behavior is silently reintroduced through a permanent
  helper, marker, or hidden collection path.
- `python -m ruff check src/uasset_read tests/` passes.
- `git diff --check` passes.
- The canonical design, Agent reference, README, and size baseline describe
  the same current target.
- `src/` has no diff from this migration.

The old 477-item result is historical evidence only; it is not an acceptance
target for the new baseline.
