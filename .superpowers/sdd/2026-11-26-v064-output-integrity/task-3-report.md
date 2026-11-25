# Task 3 report: strict JSON non-finite handling

## RED

Command: `python -m pytest -q tests/test_samples.py::test_critical_boundary_guards`

Exit code: 1. The new non-finite assertion failed before implementation because `project_document` did not raise for the injected NaN. Pytest result: `1 failed` (the test failure was the intended missing behavior).

## GREEN

Command: `python -m pytest -q tests/test_samples.py::test_critical_boundary_guards`

```text
.                                                                        [100%]
1 passed in 2.78s
```

Command: `python -m pytest -q tests/test_samples.py::test_critical_boundary_guards tests/test_samples.py::test_v4_public_output_contract`

```text
..                                                                       [100%]
2 passed in 187.79s (0:03:07)
```

`git diff --check` exited 0.

## Change

Added recursive finite-float validation for mapping/list/tuple JSON values, validating object records before embedded projection generation and the completed envelope afterward. The writer and CLI JSON serialization now set `allow_nan=False`; CLI maps the dedicated projection error to exit 1; Agent inspection returns the existing `PACKAGE_PARSE_FAILED` envelope with the projection stage and JSON Pointer message. The focused test covers NaN, positive/negative infinity, nested tuple paths, writer preservation, CLI and Agent behavior, and finite output.

Commit: `fix: reject non-finite values in v4 JSON output`
