# Batch Parse Report

Run batch parsing on a target directory, collect all errors and warnings, generate a grouped error report.

## Parameters

User may specify directory and limit; default is `E:\Develop\lib\Samples`.

## Step 1: Determine Parse Target

```python
import os, sys
from pathlib import Path

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"E:\Develop\lib\Samples")
limit = int(sys.argv[2]) if len(sys.argv) > 2 else None

files = []
for root, dirs, fnames in os.walk(target):
    for f in fnames:
        if f.endswith('.uasset'):
            files.append(os.path.join(root, f))
            if limit and len(files) >= limit:
                break
    if limit and len(files) >= limit:
        break
print(f"Found {len(files)} .uasset files")
```

## Step 2: Batch Parse

Use `parse_package()` (not `parse_single()`) to access errors/warnings attributes:

```python
from uasset_read.core import parse_package
from uasset_read.models.result import ParseResult

results = {"success": 0, "partial": 0, "failed": 0}
errors, warnings = [], []

for i, fpath in enumerate(files):
    try:
        result: ParseResult = parse_package(fpath, tolerant=True)
        results[result.status.value] += 1
        for err in result.errors:
            errors.append({"file": fpath, "error": str(err)})
        for warn in result.warnings:
            warnings.append({"file": fpath, "warning": str(warn)})
    except Exception as e:
        results["failed"] += 1
        errors.append({"file": fpath, "error": f"UNHANDLED: {e}"})
    if (i + 1) % 100 == 0:
        print(f"Progress: {i+1}/{len(files)}")
```

## Step 3: Group & Classify

```python
from collections import Counter

error_types = Counter()
for e in errors:
    msg = e["error"]
    error_type = msg.split(":")[0].strip() if ":" in msg else msg[:60]
    error_types[error_type] += 1
```

## Step 4: Generate Report

Output to `temp/batch_parse_report.md`:

```markdown
## Batch Parse Report

- **Date**: YYYY-MM-DD HH:MM
- **Target directory**: <path>
- **Total files**: N
- **Parse time**: Xs (Y files/s)

### Summary

| Status | Count | Percentage |
|--------|-------|------------|
| success | N | X% |
| partial | N | X% |
| failed | N | X% |

### Error Classification (Top 20)

| Type | Count | Sample File |
|------|-------|-------------|
| <error_type> | N | <sample_path> |

### Warning Classification (Top 10)

| Type | Count |
|------|-------|
| <warn_type> | N |
```

## Constraints

- Use `parse_package()` for full error information
- `tolerant=True` to prevent single-file failure from breaking batch
- Report saved to `temp/batch_parse_report.md`
- Show progress for > 500 files
