# uasset_read

A Python tool for parsing Unreal Engine `.uasset` files, enabling AI agents to read blueprint content without relying on the UE editor. Focuses on unbaked/editor-saved assets (containing full blueprint data).

[中文版](README.zh-CN.md) | [English](README.md)

## Status

| Metric | Value |
|--------|-------|
| Version | **v6.0** (modular refactoring complete, Phase 35 in progress) |
| Tests | **397 passed, 71 skipped, 0 failed** |
| New modules | `src/uasset_read/` — 15 modules, 50+ public API exports |
| Legacy entry | `uasset_read.py` — removed after Phase 33 (2026-05-12) |

### Current Phase: Phase 35b - Pin Connection Debug & Fix

**Status**: 🟢 PLAN.md created, P0 priority (blocking)  
**Goal**: Fix `linked_to_raw` empty root cause, restore execution_flows/data_flows  
**Timeline**: Created 2026-05-13

**Key Fixes Completed**:
- ✅ Phase 35a - Quick fixes (start_event fallback, script cleanup, logging migration)
- ✅ Phase 34 - Equivalence verification (397 passed, 0 bugs to fix)
- ✅ Phase 33 - Entry adapter + removal of old uasset_read.py
- ✅ Phase 33a - UE5 serialization fixes (FText, PropertyTag tolerants)

**Next Tasks**:
1. Phase 35b - Pin connection deep debugging (35b-01 to 35b-05)
2. Phase 35c - v6.0 milestone completion & release preparation

## Features

- **PackageFileSummary** — file header parsing
- **NameMap** — name table extraction
- **ImportMap** — dependency mapping
- **ExportMap** — export mapping
- **Blueprint graph parsing** — UEdGraph / Node / Pin structures
- **Advanced properties** — Struct / Map / Set / Enum / Text / Delegate
- **Blueprint variable extraction** — variables, functions, events, metadata
- **Component transform parsing** — Transform / Rotation / Scale
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph
- **Circular dependency detection** — mutual reference detection in ImportMap
- **Execution flow tracing** — Event → CallFunction chain tracking
- **Data flow extraction** — non-exec pin data flow relationships

## Installation

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
pip install -e ".[dev]"
```

Zero runtime dependencies, requires Python 3.10+.

## Usage

### CLI (legacy entry, until Phase 33)

```bash
python uasset_read.py path/to/file.uasset
```

### Python API

```python
from uasset_read import parse_uasset, FORMAT_CONFIG

# Parse a .uasset file
result = parse_uasset('BP_FirstPersonCharacter.uasset')

# Access parsed data
print(result.name_map)          # Name table
print(result.import_map)        # Import dependencies
print(result.export_map)        # Export table
print(result.blueprint)         # Blueprint info
print(result.graphs)            # Blueprint graph structures
print(result.dependencies)      # Dependency graph

# Output formats
print(result.format_json())     # Full JSON output
print(result.format_text())     # Human-readable text
print(result.format_markdown()) # Markdown with Mermaid flowchart

# Custom output config
print(result.format_json(summary=True))     # Summary JSON (no properties)
print(result.format_markdown(graphs_only=True))  # Graphs only Markdown
```

### Module-level API (v6.0)

```python
from uasset_read import (
    # Data models
    UEdGraph, UEdGraphNode, UEdGraphPin,
    ParseResult, BlueprintMetadata, BlueprintVariable,
    PropertyTag, PropertyValue, StructValue, MapValue, EnumValue,

    # Parsers
    parse_property_value, parse_properties_from_export,
    parse_array_property, parse_struct_property, parse_map_property,

    # Blueprint
    extract_blueprint_variables, extract_blueprint_metadata,
    parse_component_transform, extract_component_transforms,

    # Flow tracing (Phase 35)
    build_execution_flows, build_data_flows, build_connections_map,

    # Formatters (Phase 32)
    format_json_full, format_json_summary,
    format_text_full, format_markdown,
    format_graphs_json, format_blueprint_dict,

    # Constants & exceptions
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    UAssetError, ParseError, VersionError,
)
```

Full API list: see `src/uasset_read/__init__.py` (`__all__` exports 50+ items).

## CLI Options

```bash
# Basic usage
uasset-read path/to/file.uasset           # JSON output to stdout
uasset-read path/to/file.uasset --output output.json   # Save to file

# Output modes
uasset-read path/to/file.uasset --summary      # Summary only (no properties)
uasset-read path/to/file.uasset --graphs       # Graphs only
uasset-read path/to/file.uasset --output-md    # Markdown output

# Strictness
uasset-read path/to/file.uasset --strict       # Stop on warnings
uasset-read path/to/file.uasset --tolerant     # Continue on recoverable errors (default)

# Debug
uasset-read path/to/file.uasset --debug        # Enable debug logging
```

## Testing

```bash
# Run all tests (397 passed, 71 skipped)
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_graph_parsing.py -v

# Run a single test function
python -m pytest tests/test_graph_parsing.py::test_blueprint_graph_parsed -v

# Run with coverage
python -m pytest tests/ --cov=uasset_read --cov-report=html
```

Test coverage: boundary validation, blueprint extraction, dependency analysis, graph parsing, flow tracing, advanced properties (397 test cases).

### Test Results by Phase

| Phase | Tests | Status | Description |
|-------|-------|--------|-------------|
| Phase 35a | 397 | ✅ Complete | UAT fixes, start_event fallback, logging migration |
| Phase 34 | 397 | ✅ Complete | Equivalence verification (0 bugs to fix) |
| Phase 33 | 397 | ✅ Complete | Entry adapter + old uasset_read.py removal |
| Phase 33a | 383 | ✅ Complete | UE5 FText/PropertyTag tolerance fixes |
| Phase 28a | 411 | ✅ Complete | UE5 NodePosX/NodeGuid extraction fixes |

## Architecture

FArchive pipeline pattern mirroring UE's internal structure:

```
.uasset → FArchive → Deserializer → Models → Formatters → Output
                ↓
          GraphParser (Phase 31)
          BlueprintParser (Phase 30)
          DependencyGraphBuilder (Phase 10)
```

### Module Structure (`src/uasset_read/`)

| Module | Path | Phase | Description |
|--------|------|-------|-------------|
| **Core** | | | |
| FArchive | `archive.py` | 28 | Binary reader with byte swapping, mmap, bounds checking |
| Constants | `constants.py` | 27 | Version numbers, property type thresholds, MMAP_THRESHOLD |
| Exceptions | `exceptions.py` | 27 | UAssetError, VersionError, ParseError, ErrorContext |
| **Serialization** | | | |
| Serializers | `serializers/` | 28 | PackageFileSummary, ObjectImport/Export, PropertyTag |
| **Data Models** | | | |
| Core Models | `models/core.py` | 29 | UEdGraph/Node/Pin, node type subclasses |
| Blueprint Models | `models/blueprint.py` | 29 | ParseResult, blueprint metadata, property data classes |
| Transforms | `models/transforms.py` | 33 | VectorValue, RotatorValue, ScaleValue |
| **Parsers** | | | |
| Property Parsers | `parsers/` | 30 | 14 property type parse functions + dispatcher |
| **Blueprint** | | | |
| Variable Extraction | `blueprint/variable_extractor.py` | 30 | Variables, functions, events extraction |
| Transform Parser | `blueprint/transform_parser.py` | 33 | Component Transform/Rotation/Scale |
| Metadata Extraction | `blueprint/metadata_extractor.py` | 30 | Blueprint metadata |
| **Graph** | | | |
| From Archive | `graph/from_archive.py` | 31 | UEdGraph/Node/Pin parsing from FArchive |
| Flow Builder | `graph/flow_builder.py` | 32 | Execution flow & data flow tracing |
| Summary Builder | `graph/summary_builder.py` | 32 | Graph summary generation |
| **Formatters** | | | |
| JSON Formatter | `formatters/json.py` | 32 | Full/summary JSON output |
| Text Formatter | `formatters/text.py` | 32 | Human-readable text output |
| Markdown Formatter | `formatters/markdown.py` | 32 | Markdown with Mermaid flowchart |
| **Main Pipeline** | | | |
| Main Parser | `parse_uasset.py` | 33 | Top-level parse function |
| CLI | `cli.py` | 33 | Command-line interface |

### Legacy (Removed)

- `uasset_read.py` — 8100+ line single file **removed after Phase 33** (2026-05-12)

## Tech Stack

- **Language**: Python 3.10+ (match/case, type hints)
- **Dependencies**: Zero runtime dependencies — standard library only (struct, mmap, dataclasses, json, argparse)
- **Build**: setuptools (src layout), pyproject.toml configured
- **Testing**: pytest (optional dev dependency)
- **Workflow**: GSD (Guided Software Development)

## Version History

| Version | Date | Status | Highlights |
|---------|------|--------|------------|
| v1.0 | 2026-05-02 | ✅ Released | Core parsing, basic properties, blueprint metadata |
| v2.0 | 2026-05-02 | ✅ Released | Blueprint graph parsing, advanced properties, dependency analysis |
| v3.x | 2026-05-04 | ✅ Released | Property value extraction, output optimization, skill封装 |
| v4.0 | 2026-05-05 | ✅ Released | Node property deep parsing, execution flows, connection verification |
| v5.0 | 2026-05-06 | ✅ Released | Blueprint compilation research, metadata enhancement |
| v5.1 | 2026-05-07 | ✅ Released | Project structure initialization (constants.py, exceptions.py) |
| v6.0 | 2026-05-10 | 🟢 In Progress | Modular refactoring (Phase 27-35), 397 tests passing |
| v6.1 | 📋 Planned | - | Phase 35b completion, v6.0 release |

## Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data with different serialization format
- **No bytecode decompilation**: Compiled blueprints use bytecode format; focuses on editor-saved assets
- **No resource export**: Binary data (textures, models) is too large; only metadata extracted
- **Read-only**: Only supports parsing; no modification capability
- **UE source reference required**: .uasset format has no official documentation; requires UE source code as reference

## Planning

- `.planning/ROADMAP.md` — version roadmap (50 phases)
- `.planning/STATE.md` — current milestone status
- `.planning/REQUIREMENTS.md` — requirements traceability
- `.planning/PROJECT.md` — project overview
- `.planning/phases/35b-pin-connection-debug/` — Phase 35b debugging documentation

---

**Last Updated**: 2026-05-13  
**Version**: v6.0 (Phase 35b in progress)  
**Tests**: 397 passed, 71 skipped, 0 failed
