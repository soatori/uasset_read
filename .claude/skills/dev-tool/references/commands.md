# Common Commands

## Parsing

```bash
python run.py file.uasset                       # JSON (default)
python run.py file.uasset --markdown            # Markdown + Mermaid
python run.py file.uasset --strict              # Stop on warning
python run.py file.uasset --tolerant            # Tolerant mode (default)
python run.py --batch-dir path/to/dir/          # Batch export
python run.py --list-formats                    # List formats
python run.py file1.uasset --diff file2.uasset  # Diff
```

## Testing & Quality

```bash
python -m pytest --collect-only -q
python -m pytest tests/ -v
python -m pytest tests/ -v -m benchmark
python -m pytest tests/ -v -m samples
python -m pytest tests/ -v --cov=uasset_read
python -m pytest tests/test_benchmark_parse.py -v
```

pytest markers: `benchmark`, `samples`; `pytest.ini` sets `pythonpath = src`
and excludes `tests/temp/` from collection.
