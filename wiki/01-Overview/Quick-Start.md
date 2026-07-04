---
title: Quick Start
section: quick-start
---

# Quick Start

## Installation

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
```

Zero runtime dependencies, Python 3.10+.

## Direct Invocation

```bash
python run.py file.uasset                  # JSON output to stdout
python run.py file.uasset --markdown       # Markdown + Mermaid
python run.py file.uasset --output out.json  # Save to file
python run.py file.uasset --verbose        # Debug logging
python run.py file.uasset --full-parse     # Full parse (including blueprint decompilation)
python run.py file.uasset --hex-view       # Hex view debugging
python run.py --batch-dir path/to/dir/     # Batch mode
python run.py file.uasset --strict         # Strict mode (tolerant by default)
python run.py --list-formats               # List all available formats
```

All arguments also apply to `python -m uasset_read`.

## Python API

### Recommended API

```python
from uasset_read import parse_single, parse_batch

# Parse a single file
output = parse_single("path/to/MyBlueprint.uasset", format="json")
print(output)  # JSON string

# Batch parse
result = parse_batch("path/to/assets/", format="json")
print(f"Success: {len(result.success)}, Failed: {len(result.failed)}")

# View available formats
from uasset_read import list_formats
print(list_formats())  # ['json', 'markdown']
```

### Low-level API

```python
from uasset_read import parse_uasset
result = parse_uasset("path/to/MyBlueprint.uasset")
print(result.exports)      # Export list
print(result.blueprint)    # Blueprint data
print(result.graphs)       # Graph structure
```

## PAK Parsing

```python
from uasset_read import parse_package
from uasset_read.pak import PakFileReader
reader = PakFileReader("game.pak")
result = parse_package("Game/Content/MyAsset.uasset", provider=reader)
```
