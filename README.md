# uasset_read

> **Python parser for Unreal Engine .uasset files** — read blueprints, extract variables, decompile Kismet bytecode, and generate C++ skeletons — all without the UE editor.

A zero-dependency Python parser for Unreal Engine `.uasset` files that transforms binary blueprint data into structured JSON, text, and code.

[中文版](README.zh-CN.md) | [English](README.md)

> 📦 **v0.4.5-dev** — UE fidelity improvements: unified status model (success|partial|failed), UE-style loading lifecycle, class serialization strategy table, SoftObjectPath index-based resolution, DependsMap FPackageIndex semantics. With 8 dedicated asset-type parsers (StaticMesh, SkeletalMesh, Texture2D, Material, MaterialInstanceConstant, TextureCube, AnimSequence, SoundWave); broader asset categories are partially supported via generic UObject/property fallback paths. Some UE4 legacy assets may have limited support.

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
| Version | 0.4.5-dev |
| Source | Python parser for Unreal Engine .uasset files |
| Tests | 1389 passed, 2 skipped, 2 xfailed |
| Modules | 145 source files across 14 subpackages |

## Features

### Core Parsing
- **PackageFileSummary** — file header parsing
- **NameMap** — name table extraction
- **ImportMap / ExportMap** — dependency and export mapping
- **Advanced properties** — Struct / Map / Set / Enum / Text / Delegate
- **Property fallback system** — unknown properties return `PropertyFallback` with diagnostic info instead of failing
- **Class handler registry** — per-class serialization with configurable fallback policies
- **Error recovery** — tolerant mode with offset range diagnostics

### Blueprint Analysis
- **Blueprint graph parsing** — UEdGraph / Node / Pin structures with typed node models
- **Variable extraction** — variables, functions, events, metadata with type inference
- **Component properties** — Transform / Rotation / Scale + scalar attributes
- **Execution / data flow tracing** — Event → CallFunction chain tracking
- **Function graph analysis** — FunctionEntry identification, per-function call chains

### Advanced Features
- **Kismet bytecode decompiler** — EExprToken → AST → C++ pseudo-code with structured control flow
- **PackageLinker** — two-phase object graph reconstruction
- **C++ skeleton extraction** — Component declarations, function signatures, UPROPERTY mapping, constructor formatting, default value generation, identifier sanitization
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph
- **Circular dependency detection** — mutual reference detection
- **IR (Intermediate Representation)** — package-level IR builder for decoupled rendering pipeline

### File Format Support
- **Pak file parsing** — FPakInfo, Zlib compression via the standard library, optional LZ4/Zstd/AES-ECB support when `lz4`, `zstandard`, or `cryptography` are installed; Oodle reports a clear unsupported error
- **IoStore container** — Chunk ID, offset/size structures
- **Dedicated asset type parsers** — StaticMesh, SkeletalMesh, Texture2D, Material, MaterialInstanceConstant, TextureCube, AnimSequence, SoundWave; broader asset categories use generic UObject/property fallback paths. Pak/IoStore parsing lacks real `.pak/.utoc/.ucas` sample coverage.
- **Bulk Data** — BulkData header parsing
- **Game version support** — Game-specific serialization constants
- **Binary/native handlers** — binary or native property serialization support

### Multiple Output Formats
- **JSON** — full structured output or summary (renderer-based, no blueprint wrapper)
- **Text** — human-readable format
- **Markdown** — formatted documentation with tables and embedded Mermaid flowcharts
- **Blueprint UE Text** — UE-editor-style format
- **C++ Skeleton** — ready-to-use class boilerplate with constructor init lists

### Architecture
- **Renderer system** — pluggable `IRenderer` ABC with format registry (JSON/Text/Markdown/BlueprintText/BlueprintUE/CppSkeleton)
- **Core API** — `parse_single()`, `parse_batch()`, `list_formats()` for simplified programmatic access
- **CLI delegation** — lightweight CLI delegates to `core.py`
## Installation

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
```

Zero runtime dependencies, requires Python 3.10+.

## Usage

### CLI

```bash
python run.py path/to/file.uasset              # JSON output to stdout
python run.py path/to/file.uasset --output output.json   # Save to file

# Output modes
python run.py path/to/file.uasset --summary      # Summary only
python run.py path/to/file.uasset --text         # Readable text
python run.py path/to/file.uasset --markdown     # Markdown + Mermaid
python run.py path/to/file.uasset --blueprint-text  # Blueprint node text
python run.py path/to/file.uasset --blueprint-ue-text  # UE-format text
python run.py path/to/file.uasset --cpp-skeleton  # C++ class skeleton

# Batch export
python run.py --batch-dir path/to/dir/            # Batch export directory

# Strictness
python run.py path/to/file.uasset --strict       # Stop on warnings
python run.py path/to/file.uasset --tolerant     # Continue on recoverable errors (default)

# Debug
python run.py path/to/file.uasset --verbose      # Enable verbose logging
```

Or via module:

```bash
python -m uasset_read path/to/file.uasset --text
```

## Core API

Simplified high-level API for programmatic use — **recommended entry point**:

```python
from uasset_read import parse_single, parse_batch, list_formats

# Parse a single file (returns formatted string)
json_str = parse_single("path/to/file.uasset", format="json")
summary = parse_single("path/to/file.uasset", format="json_summary")
text = parse_single("path/to/file.uasset", format="markdown")

# Batch parse a directory
results = parse_batch("path/to/directory", format="json")

# List available output formats
formats = list_formats()
```

### Legacy formatters (deprecated)

The following formatter functions are still exported for backward compatibility
but are considered legacy. **Use `parse_single()` / `parse_batch()` instead** —
they go through the unified IR → Renderer pipeline and produce the most complete
output.

```python
from uasset_read import format_json_full, format_json_summary, format_text_full, format_markdown
# ⚠️ Legacy — prefer parse_single(format="json") over format_json_full()
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

    # Formatters (legacy — prefer parse_single(format=...))
    format_json_full, format_json_summary,
    format_text_full, format_markdown,

    # Linker
    parse_uasset_with_linker, PackageLinker, UObjectInstance,

    # Kismet
    decompile_uasset, KismetDecompiledResult,
    KismetTranslator, to_function_body,

    # Fallback models
    PropertyFallback, StructFallback, GenericUObject,

    # Class registry
    ClassHandlerRegistry, ClassHandler, HandlerResult, FallbackPolicy,

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
          PakFileReader
          IR Builder → Renderers
```

### Module Structure (`src/uasset_read/`)

| Module | Path | Description |
|--------|------|-------------|
| **Core** | | |
| FArchive | `archive.py` | Binary reader with byte swapping, mmap |
| Constants | `constants.py` | Version numbers, property type thresholds, CPF/PropertyTag flags |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| Main Parser | `parse_uasset.py` | `parse_package()`, `parse_uasset()`, `parse_uasset_with_linker()` |
| Core API | `core.py` | `parse_single()`, `parse_batch()`, `list_formats()` |
| Package Mgmt | `package.py` | `PackageBundle`, `PackageProvider` (filesystem/Pak/IoStore) |
| Raw Files | `raw.py` | JSON/INI/LocRes/LocMeta/Audio non-uasset parsing |
| CLI | `cli.py` | argparse 入口点，委托 `core.py` API |
| Versioning | `versioning.py` | `VersionContainer`, `build_version_container`, `EUEVersion` |
| Mappings | `mappings.py` | UE type mappings (`.usmap`/`.jmap` parsing) |
| **IR** | `ir_builder.py` | Package-level intermediate representation builder |
| **Serialization** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **Data Models** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult |
| **Parsers** | `parsers/` | 40+ property type parsers + dispatcher + custom property registry |
| ├ 资产类型 | `parsers/asset_types/` | StaticMesh, SkeletalMesh, Texture2D, Material, MaterialInstanceConstant, TextureCube, AnimSequence, SoundWave |
| **Blueprint** | `blueprint/` | Variable/Transform/Component/Metadata extraction |
| **Graph** | `graph/` | Execution/data flow tracing, chain builder, pin tracing |
| **Kismet** | `kismet/` | Bytecode extractor, EExprToken → AST, C++ translator, BPGC fallback |
| ├ 表达式 | `kismet/expressions/` | 16 expression types (assignment, control flow, function calls, literals) |
| **Linker** | `link/` | PackageLinker two-phase object graph reconstruction, UObjectInstance |
| **CPP Gen** | `cpp_gen/` | C++ skeleton/function extraction, IR formatters, type mapping, UPROPERTY mapping, constructor formatting |
| **Pak** | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry, PakFileReader, index parsing, compression, AES decryption |
| **IoStore** | `iostore/` | IoStore container reader, Chunk ID, offset/size structures |
| **Bulk Data** | `bulk/` | BulkData header parsing, flag definitions |
| **UObject** | `objects/` | UObject type system, type registry, export types (StaticMesh/SkeletalMesh/Texture2D/Material) |
| **Renderers** | `renderers/` | Pluggable IRenderer ABC with format registry (6 renderers) |
| **Formatters** | `formatters/` | JSON/Text/Markdown(with Mermaid)/Blueprint text/UE format output generation |

## Testing

```bash
python -m pytest tests/ -v           # Run all tests
python -m pytest tests/ -v --cov=uasset_read  # With coverage
```

## Tech Stack

- **Language**: Python 3.10+ (match/case, type hints)
- **Dependencies**: Zero runtime dependencies
- **Build**: Direct script (src layout)
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
