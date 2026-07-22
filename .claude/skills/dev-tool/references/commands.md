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
python -m pytest tests/ -v
python -m pytest tests/ -v -m "not slow"
python -m pytest tests/ -v --cov=uasset_read
python -m pytest tests/{module}/test_x.py::test_y -v
python -m pytest tests/ -v -m quality
```

pytest markers: `integration`, `quality`, `regression`, `slow`; `pytest.ini` sets `pythonpath = src`.
