# Minimal Test Suite

The formal suite contains exactly six `test_*.py` scripts:

- Five public-contract benchmarks for parsing, IR/graphs, JSON, Markdown,
  and CLI/batch behavior.
- One parameterized sample test that parses every tracked `.uasset` under
  `tests/samples/`.

`tests/conftest.py` records elapsed time and peak Python allocations for the
five benchmark cases. Measurements are informational and have no pass/fail
threshold. Child-process allocations are not included in the reported peak.

The current inventory is 36 tracked samples and 41 collected test cases.
Files under `tests/temp/` are experimental and excluded from collection.

## Commands

```bash
python -m pytest --collect-only -q
python -m pytest tests -m benchmark -v
python -m pytest tests -m samples -v
python -m pytest tests -v
python -m pytest tests -v --cov=uasset_read --cov-report=xml
```
