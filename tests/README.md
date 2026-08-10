# Test Suite

The test suite is organized into subdirectories by domain, with five
public-contract benchmarks and one parameterized sample test at the root.

## Structure

```
tests/
  conftest.py                  # fixtures and allocation tracking
  test_benchmark_parse.py      # parsing public contract
  test_benchmark_ir_graph.py   # IR/graph public contract
  test_benchmark_json.py       # JSON output public contract
  test_benchmark_markdown.py   # Markdown output public contract
  test_benchmark_cli_batch.py  # CLI/batch public contract
  test_samples.py              # parameterized sample parsing
  core/                        # core pipeline, JSON, batch, status, schema (15 files)
  kismet/                      # Kismet decompiler, UFunction, pipeline (6 files)
  iostore/                     # IoStore encrypted reads (1 file)
  samples/                     # tracked .uasset sample files
```

`tests/conftest.py` records elapsed time and peak Python allocations for the
benchmark cases. Measurements are informational and have no pass/fail
threshold. Child-process allocations are not included in the reported peak.

## Inventory

- **176+ test functions** across 3 subdirectories and the root
- **22 test files** in subdirectories (core, kismet, iostore)
- **6 benchmark/sample test files** at root
- **41 tracked `.uasset` samples** under `tests/samples/`

## Commands

```bash
python -m pytest --collect-only -q
python -m pytest tests -m benchmark -v
python -m pytest tests -m samples -v
python -m pytest tests -v
python -m pytest tests -v --cov=uasset_read --cov-report=xml
```
