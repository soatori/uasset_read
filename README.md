# uasset_read

A Python tool for parsing Unreal Engine `.uasset` files, enabling AI agents to read blueprint content without relying on the UE editor. Focuses on unbaked/editor-saved assets (containing full blueprint data).

[中文版](README.zh-CN.md) | [English](README.md)

## Status

| Metric | Value |
|--------|-------|
| Version | v6.0 (modular refactoring in progress) |
| Tests | 411 passed, 47 skipped, 0 failed |
| New modules | `src/uasset_read/` — 19 files, 50+ public API exports |
| Legacy entry | `uasset_read.py` — 8100+ line single file, to be removed after Phase 33 |

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
from uasset_read import parse_uasset

# Parse a .uasset file
result = parse_uasset('BP_FirstPersonCharacter.uasset')

# Access parsed data
print(result.name_map)          # Name table
print(result.import_map)        # Import dependencies
print(result.export_map)        # Export table
print(result.blueprint)         # Blueprint info
print(result.graphs)            # Blueprint graph structures
print(result.dependencies)      # Dependency graph
```

### Modular API (v6.0)

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
    parse_component_transform,

    # Constants & exceptions
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    UAssetError, ParseError,
)
```

Full API list: see `src/uasset_read/__init__.py` (`__all__` exports 50+ items).

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_graph_parsing.py -v

# Run a single test function
python -m pytest tests/test_graph_parsing.py::test_blueprint_graph_parsed -v
```

Test coverage: boundary validation, blueprint extraction, dependency analysis, graph parsing, advanced properties (411 test cases).

## Architecture

FArchive pipeline pattern mirroring UE's internal structure:

```
.uasset → FArchive → Deserializer → Models → OutputFormatter
                ↓  Extension components
          GraphParser (Phase 7/31)
          AdvancedPropParser (Phase 9/30)
          DependencyGraphBuilder (Phase 10)
```

### New module structure (`src/uasset_read/`)

| Module | Path | Description |
|--------|------|-------------|
| FArchive | `archive.py` | Binary reader with byte swapping, mmap, bounds checking |
| Constants | `constants.py` | Version numbers, property type thresholds, MMAP_THRESHOLD |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| Serializers | `serializers/` | PackageFileSummary, ObjectImport/Export, PackageIndex, PropertyTag |
| Data models | `models/` | UEdGraph/Node/Pin, node type subclasses, ParseResult, blueprint metadata, property data classes |
| Parsers | `parsers/` | 14 property type parse functions + dispatcher |
| Blueprint | `blueprint/` | Variable extraction, component transform parsing, metadata extraction |

### Legacy single file (`uasset_read.py`)

Complete parsing pipeline with all components. Will be removed after Phase 33 (entry adapter + equivalence verification).

## Tech Stack

- **Language**: Python 3.10+ (match/case, type hints)
- **Dependencies**: Zero runtime dependencies — standard library only (struct, mmap, dataclasses, json, argparse)
- **Build**: setuptools (src layout), pyproject.toml configured
- **Testing**: pytest (optional dev dependency)

## Limitations

Focuses on unbaked/editor-saved assets (containing full blueprint data). Baked assets contain only cooked data with no blueprint source code.

## Planning

- `.planning/ROADMAP.md` — version roadmap (50 phases)
- `.planning/STATE.md` — current milestone status
- `.planning/REQUIREMENTS.md` — requirements traceability
- `.planning/PROJECT.md` — project overview
