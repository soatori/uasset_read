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
  archive/                     # FArchive read/write tests
  asset/                       # asset metadata and export tests
  blueprint/                   # Blueprint graph and node tests
  core/                        # core pipeline, JSON, batch, status, schema
  graph/                       # graph traversal and pin tests
  integration/                 # cross-module integration tests
  iostore/                     # IoStore encrypted reads
  ir/                          # IR representation tests
  kismet/                      # Kismet decompiler, UFunction, pipeline
  link/                        # linker and reference resolution tests
  linker/                      # linker load tests
  misc/                        # miscellaneous tests
  pak/                         # PAK archive tests
  parsers/                     # format-specific parser tests
  renderers/                   # JSON/Markdown renderer tests
  serialization/               # property tag and serialization tests
  structs/                     # struct decode and opaque struct tests
  unit/                        # isolated unit tests
  samples/                     # tracked .uasset sample files
  fixtures/                    # test fixture data
```

`tests/conftest.py` records elapsed time and peak Python allocations for the
benchmark cases. Measurements are informational and have no pass/fail
threshold. Child-process allocations are not included in the reported peak.

## Inventory

- **176+ test functions** across 17 subdirectories and the root
- **28 test files** covering core pipeline, Kismet, IoStore, and benchmarks
- **41 tracked `.uasset` samples** under `tests/samples/`
- No `tests/temp/` directory -- all experimental tests have been promoted

## Commands

```bash
python -m pytest --collect-only -q
python -m pytest tests -m benchmark -v
python -m pytest tests -m samples -v
python -m pytest tests -v
python -m pytest tests -v --cov=uasset_read --cov-report=xml
```
