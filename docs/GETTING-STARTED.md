<!-- generated-by: gsd-doc-writer -->
# Getting Started

This guide walks you from zero to your first successful `.uasset` parse. It covers prerequisites, installation, the fastest way to see output, and the most common workflows for working with Unreal Engine blueprint assets.

## 1. Prerequisites

Before you begin, make sure you have the following installed on your system:

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | >= 3.10 | Uses `match/case` syntax and modern type hints |
| **pip** | >= 22.0 | Comes with Python 3.10+ |
| **git** | any | For cloning the repository |

Verify your Python version:

```bash
python --version   # Should report Python 3.10.x or higher
```

No other runtime dependencies are required. The parser uses only the Python standard library (`struct`, `mmap`, `dataclasses`, `json`, `argparse`).

## 2. Installation

### Clone and install

```bash
# Clone the repository
git clone https://github.com/soatori/uasset_read.git
cd uasset_read

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

The `-e` flag installs the package in editable (development) mode, so changes to source files take effect immediately without reinstalling. The `[dev]` extra pulls in `pytest` and `pytest-cov` for running tests.

### Verify the installation

```bash
# Check that the CLI is available
uasset-read --help

# Quick smoke test — should show usage information
uasset-read --help | head -3
```

Expected output begins with:

```
usage: uasset_read [-h] [--json] [--text] [--summary] ...
```

## 3. Quick Start

### CLI: Parse your first file

```bash
uasset-read path/to/file.uasset
```

This reads the `.uasset` file and prints a human-readable YAML-style text representation to stdout. The parser runs in tolerant mode by default, continuing past recoverable serialization issues.

### Python API: Parse from a script

```python
from uasset_read import parse_uasset

result = parse_uasset("path/to/file.uasset")

if result.is_success:
    print(f"Package: {result.summary}")
    print(f"Exports: {len(result.export_map)}")
    print(f"Imports: {len(result.import_map)}")
else:
    for error in result.errors:
        print(f"Error: {error}")
```

The `parse_uasset()` function returns a `ParseResult` object containing:

- `summary` — PackageFileSummary (file header with version, name count, etc.)
- `name_map` — List of string names used throughout the file
- `import_map` — List of ObjectImport entries (external dependencies)
- `export_map` — List of ObjectExport entries (objects defined in this package)
- `errors` — Any parse errors or warnings
- `is_success` — Boolean: `True` if no errors occurred

## 4. Common Workflows

### Parse to JSON file

For programmatic consumption or inspection, output full JSON:

```bash
uasset-read path/to/file.uasset --json --output output.json
```

The `--json` flag produces the complete parsed structure, and `--output` writes it to a file instead of stdout.

### Compact summary only

When you only need the high-level package information without full property data:

```bash
uasset-read path/to/file.uasset --summary
```

Outputs a compact JSON with summary, name map, import/export names — but skips detailed property parsing. Useful for asset inventory scripts.

### Parse with PackageLinker

For object graph reconstruction using UE's FLinkerLoad-style two-phase loading:

```python
from uasset_read import parse_uasset_with_linker

result = parse_uasset_with_linker("path/to/file.uasset")

# Access the linker's object graph
for obj in result.linker._export_objects:
    print(f"Export: {obj.get_full_name()}")
```

Key differences from `parse_uasset()`:

| Feature | `parse_uasset()` | `parse_uasset_with_linker()` |
|---------|------------------|------------------------------|
| Return type | `ParseResult` | `LinkerParseResult` |
| Object graph | Flat export list | `UObjectInstance` shells with outer relationships |
| Lazy loading | All properties parsed eagerly | `preload(index)` for on-demand deserialization |
| Root objects | Not tracked | `_root_objects` collected from outer tree |

The linker mode is useful when you need to resolve cross-object references or explore the package's object hierarchy the way the UE editor does.

### Extract blueprint graphs

Blueprint graph data (nodes, pins, connections) is included by default in the full JSON output. To extract only graph data:

```bash
uasset-read path/to/file.uasset --graph
```

For graph data within full JSON output:

```bash
uasset-read path/to/file.uasset --graph --json --output graphs.json
```

The graph data contains:

- **Execution flows**: Event → Sequence → CallFunction chains
- **Data flows**: Non-execution pin connections (variable reads, function arguments)
- **Node details**: K2NodeCallFunction, K2NodeEvent, K2NodeKnot, K2NodeEnhancedInputAction, etc.

You can also extract graphs programmatically:

```python
from uasset_read import extract_blueprint_graphs, build_execution_flows

graphs = extract_blueprint_graphs(result)
for graph_name, graph_data in graphs.items():
    flows = build_execution_flows(graph_data)
    print(f"Graph: {graph_name}")
    for flow in flows:
        print(f"  {flow}")
```

### Markdown output

For human-readable documentation generation:

```bash
uasset-read path/to/file.uasset --markdown --output blueprint.md
```

Produces a Markdown document with section headings for summary, imports, exports, and (if detected) a Mermaid flowchart of the blueprint execution graph.

### Strict vs tolerant mode

```bash
# Tolerant mode (default): continue on recoverable errors
uasset-read path/to/file.uasset

# Strict mode: throw ParseError on any serialization issue
uasset-read path/to/file.uasset --strict
```

Tolerant mode is recommended for most use cases, as UE serialization can have minor anomalies that do not affect the overall parse result.

## 5. Understanding the Output

### JSON output structure

A full JSON parse (`--json`) produces a document with these top-level sections:

```json
{
  "summary": {
    "package_tag": "55123030",
    "file_version": 839,
    "licensee_version": 130,
    "name_count": 1234,
    "export_count": 56,
    "import_count": 89,
    ...
  },
  "name_map": ["MyBlueprint_C", "EventBeginPlay", ...],
  "import_map": [
    {
      "class_package": "/Script/CoreUObject",
      "class_name": "Class",
      "object_name": "Actor",
      ...
    }
  ],
  "export_map": [
    {
      "class_index": 42,
      "object_name": "Default__MyBlueprint_C",
      "serial_size": 12345,
      "serial_offset": 67890,
      "properties": [...]
    }
  ],
  "graphs": {
    "EventGraph": {
      "nodes": [...],
      "execution_flows": [...],
      ...
    }
  },
  "blueprint_metadata": {
    "variables": [...],
    "functions": [...],
    "events": [...],
    "components": [...]
  },
  "dependencies": {
    "import_paths": [...],
    "soft_object_paths": [...],
    "circular_deps": []
  }
}
```

### Key fields to look for

| Section | What it tells you |
|---------|-------------------|
| `summary.file_version` | UE engine version the asset was saved with |
| `import_map` | External packages this asset depends on (e.g., `/Script/Engine`) |
| `export_map[].object_name` | Names of objects defined in this package |
| `export_map[].properties` | Parsed property data (type, value, CPF flags) |
| `graphs` | Blueprint node/pin/connection data (only for blueprint assets) |
| `blueprint_metadata` | Extracted variables, functions, events, components |
| `dependencies.circular_deps` | Detected circular references in ImportMap |

### Text output format

The default text output (`--text`, no flag needed) uses an indented YAML-style format:

```
=== Package Summary ===
  File Version: 839
  Licensee Version: 130
  Name Count: 1234
  ...

=== Import Map (3 items) ===
  [0] /Script/CoreUObject:Class /Script/Engine.Actor
  [1] /Script/CoreUObject:Class /Script/Engine.Blueprint
  ...

=== Export Map (5 items) ===
  [0] Default__MyBlueprint_C (Class)
      Properties: ...
  ...
```

## 6. Finding Test Assets

To try the parser on real assets, you need Unreal Engine `.uasset` files. The project uses the following location for test assets:

```
E:\Develop\lib\UnrealEngine\Samples\FirstPerson
```

This directory contains blueprint assets from the Unreal Engine First Person sample project. You can parse any `.uasset` file from this directory:

```bash
uasset-read "E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\Blueprints\*.uasset"
```

> **Note**: This path is specific to the current development environment. If you do not have access to the Unreal Engine source repository, you can find `.uasset` files in any UE project's `Content/` directory. Only **unbaked** (editor-saved) assets contain full blueprint graph data — cooked/baked assets have stripped serialization.

The project's test suite at `tests/` also uses sample assets to verify parser correctness. Run the tests to ensure your environment is working:

```bash
python -m pytest tests/ -v
```

## 7. Next Steps

Now that you can parse assets, explore further:

- **[Architecture](ARCHITECTURE.md)** — System design, component diagram, data flow, and key abstractions
- **[Configuration](CONFIGURATION.md)** — Environment variables, config file formats, and per-environment overrides
- **Run the test suite** — `python -m pytest tests/ -v` (554 tests, zero runtime deps)
- **Explore the Python API** — `from uasset_read import parse_uasset, PackageLinker, UEdGraph, ...` — see `src/uasset_read/__init__.py` for the full export list (150+ public symbols)
- **Read the roadmap** — `.planning/ROADMAP.md` tracks 50 phases of incremental feature development
