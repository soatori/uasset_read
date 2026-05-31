# uasset_read

> **Python parser for Unreal Engine .uasset files** — read blueprints, extract variables, decompile Kismet bytecode, and generate C++ skeletons — all without the UE editor.

A zero-dependency Python parser for Unreal Engine `.uasset` files that transforms binary blueprint data into structured JSON, text, and code.

[中文版](README.zh-CN.md) | [English](README.md)

## Why uasset_read?

Unreal Engine blueprints are stored as binary `.uasset` files — unreadable without the editor. uasset_read bridges this gap by extracting:

- **Blueprint graphs** — nodes, pins, execution flow, data dependencies
- **Variables & metadata** — types, defaults, categories, tooltips
- **Kismet bytecode** — decompiled to C++-like pseudo-code
- **Component properties** — transforms, materials, mesh references
- **Dependency graphs** — import/export relationships, soft object paths

Whether you're auditing blueprint dependencies, extracting class skeletons for C++ migration, or building tooling for game development, uasset_read gives you structured access to blueprint data at the file level.

## Status

| Metric | Value |
|--------|-------|
| Source | Python parser for Unreal Engine .uasset files |
| Tests | 108 tests across 10 files |

## Features

### Core Parsing
- **PackageFileSummary** — file header parsing
- **NameMap** — name table extraction
- **ImportMap / ExportMap** — dependency and export mapping
- **Advanced properties** — Struct / Map / Set / Enum / Text / Delegate

### Blueprint Analysis
- **Blueprint graph parsing** — UEdGraph / Node / Pin structures
- **Variable extraction** — variables, functions, events, metadata with type inference
- **Component properties** — Transform / Rotation / Scale + scalar attributes
- **Execution / data flow tracing** — Event → CallFunction chain tracking
- **Function graph analysis** — FunctionEntry identification, per-function call chains

### Advanced Features
- **Kismet bytecode decompiler** — EExprToken → AST → C++ pseudo-code
- **PackageLinker** — two-phase object graph reconstruction
- **N2C intermediate format** — structured JSON schema with execution chains
- **C++ skeleton extraction** — Component declarations, function signatures, UPROPERTY mapping
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph
- **Circular dependency detection** — mutual reference detection

### File Format Support
- **Pak file parsing** — FPakInfo, compression (Zlib/LZ4/Zstd/Oodle), AES-ECB decryption
- **IoStore container** — Chunk ID, offset/size structures
- **Asset type parsers** — SkeletalMesh, Texture2D, Material, MaterialInstanceConstant
- **Bulk Data** — BulkData header parsing

### Multiple Output Formats
- **JSON** — full structured output or summary
- **Text** — human-readable format
- **Markdown** — formatted documentation with tables
- **Mermaid** — interactive flowcharts and dependency graphs
- **Blueprint UE Text** — UE-editor-style format
- **C++ Skeleton** — ready-to-use class boilerplate

## Installation

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
pip install -e ".[dev]"
```

Core `.uasset` parsing has zero runtime dependencies and requires Python 3.10+.
For optional PAK AES/LZ4/Zstd support, install:

```bash
pip install -e ".[pak]"
# or, from PyPI:
pip install "uasset_read[pak]"
```

## Usage

### CLI

```bash
uasset-read path/to/file.uasset              # JSON output to stdout
uasset-read path/to/file.uasset --output output.json   # Save to file

# Output modes
uasset-read path/to/file.uasset --summary      # Summary only
uasset-read path/to/file.uasset --text         # Readable text
uasset-read path/to/file.uasset --markdown     # Markdown output
uasset-read path/to/file.uasset --blueprint-text  # Blueprint node text
uasset-read path/to/file.uasset --blueprint-ue-text  # UE-format text
uasset-read path/to/file.uasset --cpp-skeleton  # C++ class skeleton
uasset-read path/to/file.uasset --n2c           # N2C intermediate format JSON

# Batch export
uasset-read --batch-dir path/to/dir/            # Batch export directory

# Strictness
uasset-read path/to/file.uasset --strict       # Stop on warnings
uasset-read path/to/file.uasset --tolerant     # Continue on recoverable errors (default)

# Debug
uasset-read path/to/file.uasset --verbose      # Enable verbose logging
```

### Module-level API

Import parser functions directly from the package root. If you need the
`uasset_read.parse_uasset` module object, use `importlib.import_module()` to
avoid the root-level `parse_uasset` function name.

```python
import importlib

from uasset_read import (
    # Data models
    UEdGraph, UEdGraphNode, UEdGraphPin,
    ParseResult, BlueprintMetadata, BlueprintVariable,

    # Parsers
    parse_property_value, parse_properties_from_export,

    # Blueprint
    extract_blueprint_variables, extract_blueprint_metadata,
    parse_component_transform, extract_component_transforms,

    # Flow tracing
    build_execution_flow_entries, build_data_flows, build_connections_map,
    build_execution_chains,

    # Formatters
    format_json_full, format_json_summary,
    format_text_full, format_markdown,

    # Linker
    parse_uasset_with_linker, PackageLinker, UObjectInstance,

    # Kismet
    decompile_uasset, KismetDecompiledResult,
    KismetTranslator, to_function_body,

    # N2C
    N2CStruct, N2CGraph, to_n2c_json, from_n2c_json,

    # Agent translation
    AgentTranslationPipeline, translate_blueprint_to_cpp,
    CppFileWriter, write_cpp_class_files,

    # Constants & exceptions
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    UAssetError, ParseError, VersionError,
)

parse_module = importlib.import_module("uasset_read.parse_uasset")
```

Full API list: see `src/uasset_read/__init__.py`.

## Architecture

FArchive pipeline pattern mirroring UE's internal structure:

```
.uasset → FArchive → Deserializer → Models → Formatters → Output
                ↓
          GraphParser
          BlueprintParser
          DependencyGraphBuilder
          PackageLinker
          KismetDecompiler
          N2C Format
          PakFileReader
```

### Module Structure (`src/uasset_read/`)

| Module | Path | Description |
|--------|------|-------------|
| **Core** | | |
| FArchive | `archive.py` | Binary reader with byte swapping, mmap |
| Constants | `constants.py` | Version numbers, property type thresholds, CPF/PropertyTag flags |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| Main Parser | `parse_uasset.py` | `parse_package()`, `parse_uasset()`, `parse_uasset_with_linker()` |
| Package Mgmt | `package.py` | `PackageBundle`, `PackageProvider` (filesystem/Pak/IoStore) |
| Raw Files | `raw.py` | JSON/INI/LocRes/LocMeta/Audio non-uasset parsing |
| CLI | `cli.py` | argparse entry point (`uasset-read`) |
| Exporter | `exporter/` | IExporter interface, registry, batch export |
| Versioning | `versioning.py` | `VersionContainer`, `build_version_container`, `EUEVersion` |
| Mappings | `mappings.py` | UE type mappings (`.usmap`/`.jmap` parsing) |
| **Serialization** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **Data Models** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult |
| **Parsers** | `parsers/` | 40+ property type parsers + dispatcher + custom property registry |
| **Asset Types** | `parsers/asset_types/` | SkeletalMesh, Texture2D, Material, MaterialInstanceConstant |
| **Blueprint** | `blueprint/` | Variable/Transform/Component/Metadata extraction |
| **Graph** | `graph/` | Execution/data flow tracing, chain builder |
| **Kismet** | `kismet/` | Bytecode extractor, EExprToken → AST, C++ translator, BPGC fallback |
| **Linker** | `link/` | PackageLinker, UObjectInstance |
| **CPP Gen** | `cpp_gen/` | C++ skeleton/function extraction, IR formatters |
| **Agent** | `agent/` | AgentTranslationPipeline + CppFileWriter |
| **N2C** | `n2c/` | N2CStruct/Graph/Node/Pin models, JSON schema, validators |
| **Pak** | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry, PakFileReader, index parsing |
| **Compression** | `pak/decompress.py` | Zlib/LZ4/Zstd/Oodle dispatch with graceful degradation |
| **Crypto** | `pak/crypto.py` | AES-ECB decryption helpers |
| **Formatters** | `formatters/` | JSON/Text/Markdown/Mermaid output |

## Testing

```bash
python -m pytest tests/ -v           # Run all tests
python -m pytest tests/ -v --cov=uasset_read  # With coverage
```

## Tech Stack

- **Language**: Python 3.10+ (match/case, type hints)
- **Dependencies**: Zero runtime dependencies
- **Build**: setuptools (src layout), pyproject.toml
- **Testing**: pytest

## Use Cases

| Scenario | How uasset_read helps |
|----------|----------------------|
| **Programmatic blueprint analysis** | Parse blueprint data → extract structure → automate inspections |
| **Blueprint → C++ migration** | Extract class structure, variables, functions → generate C++ skeleton |
| **Dependency auditing** | Build import/export graphs → detect circular references → find orphaned assets |
| **Mod development** | Read blueprint variables from `.pak` files → understand mod behavior without source |
| **Asset pipeline automation** | Batch-parse thousands of `.uasset` files → extract metadata → build searchable index |
| **Technical debt analysis** | Trace execution flows → identify deeply nested logic → find dead code |

## Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data
- **Limited bytecode decompilation**: Kismet EExprToken→AST→C++ implemented for known token types
- **No resource export**: Binary data too large; metadata only
- **Read-only**: Parsing only, no modification
- **UE source reference required**: No official .uasset format documentation

---
