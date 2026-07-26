# Test Script Rules

## Formal Suite

The `tests/` root contains exactly six formal `test_*.py` scripts:

1. Five stable public-contract benchmarks.
2. One parameterized test for every tracked asset in `tests/samples/`.

Benchmark changes require user approval. Prefer semantic assertions over
golden snapshots and private implementation details. Performance measurements
are informational unless the user explicitly approves a threshold.

## File Placement

| Scenario | Location | Rule |
|----------|----------|------|
| Benchmark change | Existing `tests/test_benchmark_*.py` | Explain and obtain approval first |
| Sample contract change | `tests/test_samples.py` | Keep dynamic coverage of every tracked sample |
| Test asset | `tests/samples/*.uasset` | Binary assets only; no Python files |
| Experimental test | `tests/temp/test_*.py` | Excluded from default pytest collection |

Do not create a seventh formal script. Merge durable public-contract coverage
into the closest existing benchmark. Delete experimental tests when the task
ends or promote their essential assertion into an approved benchmark change.
