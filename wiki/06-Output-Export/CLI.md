---
title: CLI Interface
section: cli
---

# CLI Interface

Provides parsing and multi-format output capabilities for `.uasset`/`.umap` files via `python run.py` or `python -m uasset_read`.

## Architecture Changes (0.4.1)

CLI was refactored in 0.4.1, delegating core logic to the pure-function API in `core.py`. CLI is only responsible for argument parsing and output writing.

```
CLI (cli.py) → core.py (parse_single/parse_batch) → IR → Renderers → Output
```

The `--n2c` and `--cpp-json-ir` flags have been removed (N2C module entirely deleted).

## Module Information

| Item | Value |
|------|------|
| File path | `src/uasset_read/cli.py` |
| Entry function | `main()` |
| Argument parsing | `create_parser()` |
| Format routing | `resolve_format()` |
| Core delegation | `core.py` (parse_single / parse_batch / list_formats) |

## Basic Usage

```bash
python run.py path/to/file.uasset              # JSON output (default)
python run.py path/to/file.uasset --markdown   # Markdown + Mermaid diagrams
```

## Command-Line Arguments

### Positional Arguments

| Argument | Description |
|----------|-------------|
| `file` | Path to a `.uasset`/`.umap` file (required; in batch mode, this is a directory path) |

### Output Format Flags (Mutually Exclusive)

The following flags are in a mutually exclusive group -- only one may be used at a time:

| Flag | Format Name | Description |
|------|-------------|-------------|
| `--json` | `json` | Structured JSON output (C++ translation reference, default) |
| `--markdown` | `markdown` | Markdown + Mermaid flowcharts |

### Removed Flags

| Flag | Description |
|------|-------------|
| `--n2c` | N2C module entirely deleted |
| `--cpp-json-ir` | Merged into cpp_skeleton |
| `--validate` | N2C validation removed |
| `--graph` | Legacy compatibility flag removed |
| `--json-summary` | Removed during output format streamlining |
| `--text` | Removed during output format streamlining |
| `--text-summary` | Removed during output format streamlining |
| `--summary` | Removed during output format streamlining |
| `--blueprint-text` | Removed during output format streamlining |
| `--blueprint-ue-text` | Removed during output format streamlining |
| `--cpp-skeleton` | Removed during output format streamlining |

### Parse Control Flags

| Flag | Description |
|------|-------------|
| `--verbose` | Output additional detailed fields |
| `--function-graphs` | Include `function_graphs` in output |
| `--tolerant` | Tolerant mode (enabled by default) |
| `--strict` | Disable tolerant mode: serialization issues raise ParseError |
| `--export INDEX` | Output only the export at the specified index |
| `--schema` | Include field semantic annotations |

### Resource Parsing Flags

| Flag | Description |
|------|-------------|
| `--asset-root DIR` | Root directory for searching parent `.uasset` files (can be repeated) |
| `--include-parent-assets` | Parse and include parent Blueprint assets |
| `--mappings FILE` | Load `.usmap`/`.jmap`/`.jmap.gz` type mappings |
| `--game NAME` | Enable game-specific property readers (e.g., `Borderlands4`) |

### Batch Mode Flags

| Flag | Description |
|------|-------------|
| `--batch` | Enable batch mode: treat the positional argument as a directory of `.uasset` files |
| `--batch-dir DIR` | Batch mode output directory (default: `{input_dir}/output`) |

### Debug and Utility Flags

| Flag | Description |
|------|-------------|
| `--output FILE` | Write output to a file instead of stdout |
| `--list-formats` | List all available export formats and exit |
| `--list-package-files` | List discovered package sidecar/payload files and exit |
| `--full-parse` | Full parse (includes Blueprint decompilation, Kismet bytecode extraction) |
| `--hex-view` | Hex view debug mode |

## Exit Codes

| Code | Constant | Description |
|------|----------|-------------|
| `0` | `EXIT_SUCCESS` | Success |
| `1` | `EXIT_PARSE_ERROR` | Parse error |
| `2` | `EXIT_FILE_NOT_FOUND` | File does not exist or is not a file |
| `3` | `EXIT_ARGUMENT_ERROR` | Argument error |

## Format Routing Logic

The `resolve_format()` function maps CLI flags to internal format names:

```
--markdown        → markdown
--json            → json
(no flag)         → json (default)
```

> [!WARNING]
> The following legacy routes have been removed: `--n2c`, `--cpp-json-ir`, `--graph`, `--text`, `--summary`, `--blueprint-text`, `--blueprint-ue-text`, `--cpp-skeleton`

## Parse Path

CLI parses via `core.py`'s `parse_single()`:

1. Determine whether a linker is needed based on format (current formats do not require one)
2. Call `parse_single()` → internally performs: parsing → IR construction → rendering
3. Write to stdout or file

## Batch Mode

```bash
# Process all .uasset/.umap files in a directory
python run.py /path/to/assets/ --batch

# Specify output directory
python run.py /path/to/assets/ --batch --batch-dir /path/to/output/

# Batch export as JSON
python run.py /path/to/assets/ --batch --json
```

Batch result reports are output to stderr:

```
Batch export complete: 10 files
  Success: 8
  Failed: 2
    - BP_Error.uasset: ParseError: ...
```

## Complete Examples

```bash
# 1. Parse a single file, output to stdout
python run.py MyBlueprint.uasset

# 2. JSON output
python run.py MyBlueprint.uasset --json

# 3. Output to file
python run.py MyBlueprint.uasset --json --output result.json

# 4. Markdown + Mermaid documentation
python run.py MyBlueprint.uasset --markdown --output report.md

# 5. Include parent asset parsing
python run.py MyBlueprint.uasset --json --include-parent-assets --asset-root /Game/Content

# 6. Use type mappings
python run.py MyBlueprint.uasset --json --mappings mappings.usmap

# 7. List package files
python run.py MyBlueprint.uasset --list-package-files

# 8. List all available formats
python run.py --list-formats
```

## Invocation Methods

CLI can be invoked via:

- **Script**: `python run.py ...` (from project root)
- **Module**: `python -m uasset_read ...` (`__main__.py` entry point)

Both call the same `main()` function.

## Output Stream Conventions

- **stdout**: Data output only
- **stderr**: Error messages, status information, and batch reports

This allows users to pipe data to other tools while retaining human-readable error messages.

**Related Sections**: [[Renderer System]] · [[IR Intermediate Representation]]
