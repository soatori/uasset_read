# Task 2 Report: Debug Evidence Isolation

## Change

- `src/uasset_read/projection.py`: debug `semantic_source_ranges` now receives a deep copy of each region-shaped semantic evidence value, including nested `source_slices`. Normal projection does not incur the copy.
- `tests/test_samples.py`: the v4 public output contract now calls `_check_debug_evidence_is_detached()`. The helper queries `Helm_BP.uasset` twice through `inspect_package(..., mode="debug")`, checks `export:0` at `/declaration/source_range` starts at `141365`, mutates `start` and the first physical slice's `source_start` in the first result, then confirms the second result equals the pre-mutation deep copy. The parse cache is cleared in `finally`.

## Evidence

- RED: with the helper added before the implementation, `PYTHONPATH=src python -c "from tests.test_samples import _check_debug_evidence_is_detached; _check_debug_evidence_is_detached()"` failed at `assert find_region(second) == before`, as expected.
- GREEN: `python -m pytest -q tests/test_samples.py::test_v4_public_output_contract` passed: `1 passed in 91.10s`.
- `git diff --check` passed.
- Full suite was not run; integration is responsible for whole-suite verification.

## Commit

`95e7432020280c9e9a5fc4c05c90e1e9b4d5a9dd` (`fix: detach debug evidence from cached packages`).
