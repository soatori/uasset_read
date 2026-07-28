# Remove Compact Output Mode Design

## Context

The public output contract has exactly two levels: `standard` and `debug`.
The CLI already enforces that choice, but the Python API still accepts
`output_level="compact"`. The JSON renderer, JSON Schema, and acceptance tests
therefore contain a hidden third contract based on `node_summary`.

Issue #509 must no longer use a third output mode as its solution. Its target is
revised to reduce unsafe or redundant standard output while preserving the
existing `graphs[].nodes` contract.

## Decision

- Remove `compact` immediately; there is no deprecation period.
- Do not move `node_summary` into `debug`.
- `standard` continues to emit `graphs[].nodes` with its existing omission of
  editor-only and default-valued details.
- `debug` continues to emit `graphs[].nodes` with the full node and pin fields.
- Any Python API call or direct `RenderOptions` construction with an output
  level other than `standard` or `debug` fails with `ValueError`.

`node_summary` is intentionally deleted because every value it contains can be
derived from the full node data. Keeping it in `debug` would create duplicate
data and a second graph-shape contract without adding parsing fidelity.

## Components

### Output-level contract

`RenderOptions` is the single validation boundary. It accepts only
`standard` and `debug`, so single-file parsing, batch parsing, isolated workers,
and direct renderer use share the same behavior. CLI choices remain unchanged.

The exception message must name the invalid value and the two accepted values.
This makes the deliberate removal visible to Python API consumers instead of
silently treating an unknown level as standard output.

### JSON rendering

Graph rendering always produces a `nodes` array. The existing standard/debug
field filtering remains unchanged. Remove the compact-only branch and the
aggregation helpers `_aggregate_nodes()` and `_pin_semantic_key()`.

No unrelated renderer refactor belongs in this change.

### JSON Schema

`GraphEntry` requires `nodes`. Remove the `node_summary` property,
`NodeSummary` definition, and the `oneOf` branch that allowed two mutually
exclusive graph shapes. Standard and debug outputs validate against the same
graph structure.

### Tests

Tests must prove all of the following:

1. `RenderOptions`, `parse_single`, and `parse_batch` reject `compact` and any
   other unknown output level.
2. Standard and debug JSON for every bundled sample validate against the schema.
3. Every emitted graph contains `nodes` and never contains `node_summary`.
4. The schema rejects a graph without `nodes`.
5. The CLI help continues to advertise only `standard` and `debug`.

Compact-specific tests are deleted or rewritten around the two-level contract;
they are not retained as skipped compatibility tests.

## Revised Issue #509 Scope

After compact removal, #509 covers only changes that preserve the two public
levels:

- retain corrupted `serial_size` filtering and accurate omission accounting;
- keep safe standard-mode removal of editor-only/default-valued fields;
- measure named real-sample output sizes and document why ALS remains large;
- do not add truncation, pagination, `--max-lines`, export-summary modes, or a
  third graph representation in this change.

The issue is ready to close only after standard/debug schema checks, the full
test suite, and named real-sample output inspection pass on the current branch.

## Compatibility and Rollback

Standard and debug JSON consumers retain their current `graphs[].nodes` shape.
Only callers that used the undocumented Python-level compact value break, and
they receive an explicit validation error. Reverting the resulting cleanup
commit restores the hidden mode without affecting unrelated #507/#510 work.

## Acceptance Criteria

- Repository source, schema, active tests, and user documentation contain no
  output-level support for `compact` or `node_summary`.
- `python run.py --help` lists `--output-level {standard,debug}`.
- `parse_single(..., output_level="compact")` raises `ValueError`.
- Standard/debug JSON for ALS AnimBP, FirstPerson Blueprint, and StackOBot GI
  validates against `schemas/package.schema.json` and contains graph `nodes`
  only.
- Focused tests, the default test suite, Ruff, compileall, and real-sample
  inspection all pass before #509 is updated.
