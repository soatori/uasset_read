# uasset_read

> **Python parser for Unreal Engine .uasset files** — read blueprints, extract variables, decompile Kismet bytecode, and generate C++ skeletons — all without the UE editor.

A zero-dependency Python parser for Unreal Engine `.uasset` files that transforms binary blueprint data into structured JSON and code.

[中文版](README.zh-CN.md) | [English](README.md)

> 📦 **v0.5.3.23** — 23 issues fixed since v0.5.2.31: graph safety, EventGraph offset protection, FText bounds, memory safety, AnimSequence/MovieScene parsing, security hardening, and more.

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
| Version | 0.5.3.23 |
| Source | Python parser for Unreal Engine .uasset files |
| Tests | 492 collected (integration tests skip when sample assets unavailable) |
| Modules | 175 source files across 21 subpackages |

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
- **Dedicated asset type parsers** — StaticMesh, SkeletalMesh, Texture2D, Material, MaterialInstanceConstant, TextureCube, AnimSequence, AnimBlueprint, AnimMontage, AnimBoneCompression, AnimCurveCompression, AnimationDataModel, SoundWave, SoundCue, SoundAttenuation, DataTable, CurveTable, StringTable, Skeleton, PoseAsset, LevelSequence, MovieScene, MovieSceneControlRig, FoliageType, SkeletalMeshLODSettings, SubsurfaceProfile, OpaqueStub, PropertyExtractor; broader asset categories use generic UObject/property fallback paths. Pak/IoStore parsing lacks real `.pak/.utoc/.ucas` sample coverage.
- **Bulk Data** — BulkData header parsing
- **Game version support** — Game-specific serialization constants
- **Binary/native handlers** — binary or native property serialization support

### Output Formats
- **JSON** — structured output optimized for C++ translation reference
- **Markdown** — formatted documentation with tables and embedded Mermaid flowcharts
- **Text** — human-readable text summary

### Architecture
- **Renderer system** — pluggable `IRenderer` ABC with format registry (JSON, Markdown, Text)
- **Core API** — `parse_single()`, `parse_batch()`, `diff_single()`, `list_formats()` for simplified programmatic access
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
python run.py path/to/file.uasset --json         # JSON output (default)
python run.py path/to/file.uasset --markdown     # Markdown + Mermaid
python run.py path/to/file.uasset --text         # Human-readable text summary
python run.py path/to/file.uasset --list-formats # List available formats

# Batch export (input directory + output directory)
python run.py path/to/input/dir/ --batch --batch-dir path/to/output/dir/

# Strictness
python run.py path/to/file.uasset --strict       # Stop on warnings
python run.py path/to/file.uasset --tolerant     # Continue on recoverable errors (default)

# Debug
python run.py path/to/file.uasset --verbose      # Enable verbose logging
python run.py path/to/file.uasset --hex-view     # Enable HexView binary inspection
python run.py path/to/file.uasset --full-parse   # Force full parse for large blueprints

# Diff comparison
python run.py path/to/file1.uasset --diff path/to/file2.uasset  # Compare two files

# Advanced options
python run.py path/to/file.uasset --export 0     # Output only specific export by index
python run.py path/to/file.uasset --schema        # Include field semantic annotations
python run.py path/to/file.uasset --function-graphs  # Include function_graphs array
python run.py path/to/file.uasset --mappings path/to/usmap  # Load type mappings
python run.py path/to/file.uasset --output-level debug   # Output verbosity level
```

### Logging Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--log-level` | debug | File log level: debug, info, warning, error, off |
| `--log-dir` | ./log | Log output directory |
| `--log-max-bytes` | 10000000 | Max size per log file (bytes) |
| `--log-backup-count` | 5 | Number of backup log files to keep |
| `--log-cleanup` | false | Clean old logs on startup |
| `--log-keep-latest` | 5 | Number of latest log files to keep |
| `--log-max-total-mb` | none | Total log size limit (MB) |
| `--clean-logs` | false | Plan cleanup only, do not delete |

Or via module:

```bash
python -m uasset_read path/to/file.uasset --json
```

## Core API

Simplified high-level API for programmatic use — **recommended entry point**:

```python
from uasset_read import parse_single, parse_batch, diff_single, list_formats

# Parse a single file (returns formatted string)
json_str = parse_single("path/to/file.uasset", format="json")
text = parse_single("path/to/file.uasset", format="markdown")

# Batch parse a directory
results = parse_batch("path/to/directory", format="json")

# Compare two .uasset files
diff_output = diff_single("file1.uasset", "file2.uasset", format="json")

# List available output formats
formats = list_formats()
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
.uasset → FArchive → Serializers → Parsers → Linker → IR Builder → Renderers → Output
                ↓
          GraphParser
          BlueprintParser
          DependencyGraphBuilder
          PackageLinker
          KismetDecompiler
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
| Core API | `core/` | `parse_single()`, `parse_batch()`, `diff_single()`, `list_formats()` |
| Package Mgmt | `package.py` | `PackageBundle`, `PackageProvider` (filesystem/Pak/IoStore) |
| Raw Files | `raw.py` | JSON/INI/LocRes/LocMeta/Audio non-uasset parsing |
| CLI | `cli.py` | argparse entry point, delegates to `core.py` API |
| Versioning | `versioning.py` | `VersionContainer`, `build_version_container`, `EUEVersion` |
| Mappings | `mappings.py` | UE type mappings (`.usmap`/`.jmap` parsing) |
| Memory Safety | `memory_safety.py` | Central memory policy, RSS measurement, parser checkpoints |
| Bounded Events | `bounded_events.py` | Bounded event buffer for diagnostics |
| Parse Stages | `parse_stages.py` | Core table reading, secondary table reading, export property parsing |
| Post Process | `parse_post_process.py` | Post-processing: Kismet decompilation, graph extraction, dependency analysis |
| Batch Worker | `batch_worker.py` | Subprocess-isolated per-asset batch worker |
| Providers | `providers.py` | GameDirectoryProvider for game asset scanning |
| Project Logging | `project_logging.py` | Structured logging with rotation |
| Debug | `debug/hex_view.py` | HexView debug system for binary field inspection |
| **IR** | `ir_builder.py` | Package-level intermediate representation builder |
| **Serialization** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **Data Models** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult, Status, Diagnostics |
| **Parsers** | `parsers/` | 40+ property type parsers + dispatcher + custom property registry + AssetRegistry parser + class serialization strategy |
| ├ Asset Types | `parsers/asset_types/` | 28 asset type parsers including StaticMesh, SkeletalMesh, AnimBlueprint, AnimMontage, DataTable, LevelSequence, MovieScene |
| **Blueprint** | `blueprint/` | Variable/Transform/Component/Metadata extraction |
| **Graph** | `graph/` | Execution/data flow tracing, chain builder, graph_utils |
| **Kismet** | `kismet/` | Bytecode extractor, EExprToken → AST, C++ translator, BPGC fallback |
| ├ Expressions | `kismet/expressions/` | 16 expression types (assignment, control flow, function calls, literals) |
| ├ CFG | `kismet/cfg/` | Control flow graph: build, dom, emitter, region, stmt |
| **Linker** | `link/` | PackageLinker two-phase object graph reconstruction, UObjectInstance |
| **CPP Gen** | `cpp_gen/` | C++ skeleton/function extraction, IR formatters, type mapping, UPROPERTY mapping, constructor formatting, body extraction |
| **Pak** | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry, PakFileReader, index parsing, compression, AES decryption |
| **IoStore** | `iostore/` | IoStore container reader, Chunk ID, offset/size structures |
| **Bulk Data** | `bulk/` | BulkData header parsing, flag definitions |
| **UObject** | `objects/` | UObject type system, type registry, export types (StaticMesh/SkeletalMesh/Texture2D/Material/MaterialInstance) |
| **Renderers** | `renderers/` | Pluggable IRenderer ABC with format registry (JSON, Markdown, Text) |

## Testing

```bash
python -m pytest tests/ -v           # Run all tests
python -m pytest tests/ -v --cov=uasset_read  # With coverage
```

### UE Editor Ground Truth

For parser changes that claim UE fidelity, do not rely only on pytest or static
C++ references. When Unreal Editor 5.8 is available, use the official
Experimental Unreal MCP server as a live read-only ground-truth channel:

1. Enable `ModelContextProtocol` and, when broader toolsets are needed, enable
   `AllToolsets` in the UE 5.8 editor project.
2. Start the server with `ModelContextProtocol.StartServer` or launch the
   editor with `-ModelContextProtocolStartServer`; the default endpoint is
   `http://127.0.0.1:8000/mcp`.
3. Record `tools/list`, `list_toolsets`, and the `describe_toolset` schema for
   the toolset used to inspect the asset.
4. Compare parser JSON/Markdown against editor live data for asset class,
   export object names, Blueprint variables, graph names, nodes, pins,
   component hierarchy, transforms, input bindings, soft references, and asset
   load/compile status.
5. Keep MCP-derived evidence as test artifacts or issue evidence. Do not make
   the normal test suite fail when the editor or MCP endpoint is unavailable.

MCP evidence is authoritative for editor-visible state, while `.uasset` parsing
remains the source under test. If the two disagree, document whether the gap is
caused by cooked/editor-only stripping, unresolved binary serialization, or an
actual parser defect.

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
