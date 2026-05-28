# uasset_read

A Python tool for parsing Unreal Engine `.uasset` files, enabling AI agents to read blueprint content without relying on the UE editor. Focuses on unbaked/editor-saved assets (containing full blueprint data).

[中文版](README.zh-CN.md) | [English](README.md)

## Status

| Metric | Value |
|--------|-------|
| Source | Python parser for Unreal Engine .uasset files |
| Tests | 56 tests |

## Features

- **PackageFileSummary** — file header parsing
- **NameMap** — name table extraction
- **ImportMap / ExportMap** — dependency and export mapping
- **Blueprint graph parsing** — UEdGraph / Node / Pin structures
- **Advanced properties** — Struct / Map / Set / Enum / Text / Delegate
- **Blueprint variable extraction** — variables, functions, events, metadata
- **Component property parsing** — Transform / Rotation / Scale + scalar attributes
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph
- **Circular dependency detection** — mutual reference detection
- **Execution / data flow tracing** — Event → CallFunction chain tracking
- **Function graph analysis** — FunctionEntry identification, per-function call chains
- **PackageLinker** — 两阶段对象图重建
- **Kismet bytecode decompiler** — EExprToken → AST → C++ pseudo-code
- **N2C intermediate format** — Agent-optimized JSON schema, execution chains
- **C++ skeleton extraction** — Component declarations, function signatures
- **Pak file parsing** — FPakInfo, compression (Zlib/LZ4/Zstd/Oodle), AES-ECB
- **Asset type parsers** — SkeletalMesh, Texture2D, Material, MaterialInstanceConstant attribute extraction
- **Multiple output formats** — JSON, Text, Markdown, Mermaid graphs

## Installation

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
pip install -e ".[dev]"
```

Zero runtime dependencies, requires Python 3.10+.

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

# Strictness
uasset-read path/to/file.uasset --strict       # Stop on warnings
uasset-read path/to/file.uasset --tolerant     # Continue on recoverable errors (default)

# Debug
uasset-read path/to/file.uasset --verbose      # Enable verbose logging
```

### Module-level API

```python
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
    build_execution_flows, build_data_flows, build_connections_map,
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
| Constants | `constants.py` | Version numbers, property type thresholds, CPF flags |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError |
| Main Parser | `parse_uasset.py` | `parse_uasset()` and `parse_uasset_with_linker()` |
| CLI | `cli.py` | argparse entry point (`uasset-read`) |
| Exporter | `exporter/` | IExporter interface and registry |
| **Serialization** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **Data Models** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult |
| **Parsers** | `parsers/` | 14 property type parsers + dispatcher |
| **Asset Types** | `parsers/asset_types/` | SkeletalMesh, Texture2D, Material, MaterialInstanceConstant |
| **Blueprint** | `blueprint/` | Variable/Transform/Component/Metadata extraction |
| **Graph** | `graph/` | Execution/data flow tracing, chain builder |
| **Kismet** | `kismet/` | Bytecode extractor, EExprToken → AST, C++ translator, BPGC fallback |
| **Linker** | `link/` | PackageLinker, UObjectInstance |
| **CPP Gen** | `cpp_gen/` | C++ skeleton/function extraction, IR formatters |
| **Agent** | `agent/` | AgentTranslationPipeline + CppFileWriter |
| **N2C** | `n2c/` | N2CStruct/Graph/Node/Pin models, JSON schema, validators |
| **Pak** | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry, PakFileReader, index parsing |
| **Compression** | `compression/` | Zlib/LZ4/Zstd/Oodle dispatch with graceful degradation |
| **Crypto** | `crypto/` | AES-ECB decryption, CustomEncryption delegate |
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

## Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data
- **Limited bytecode decompilation**: Kismet EExprToken→AST→C++ implemented for known token types
- **No resource export**: Binary data too large; metadata only
- **Read-only**: Parsing only, no modification
- **UE source reference required**: No official .uasset format documentation

---
