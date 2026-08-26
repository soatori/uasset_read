# uasset_read

> **Python parser for Unreal Engine .uasset files** — read blueprints, extract variables, decompile Kismet bytecode, and generate C++ skeletons — all without the UE editor.

A zero-dependency Python parser for Unreal Engine `.uasset` files that transforms binary blueprint data into structured JSON and code.

> 📦 **v0.5.5** — Zero runtime dependencies · Python 3.10+ · 200 source files · 70+ UE class types

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
| -------- | ------- |
| Version | 0.5.5 |
| Source | Python parser for Unreal Engine .uasset files |
| Modules | 200 source files across 15 subpackages |

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

- **JSON** — structured output via semantic pipeline, optimized for C++ translation reference
- **Markdown** — formatted documentation with tables and embedded Mermaid flowcharts

### Architecture

- **Renderer system** — Markdown renderer; JSON output routed through semantic pipeline (`semantic/`)
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
python run.py path/to/file.uasset --list-formats # List available formats

# Batch export (input directory + output directory)
python run.py path/to/input/dir/ --batch --batch-dir path/to/output/dir/

# Strictness
python run.py path/to/file.uasset                # Continue on recoverable errors (default)
python run.py path/to/file.uasset --strict       # Stop on warnings

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
| ----------- | --------- | ------------- |
| `--log-level` | debug | File log level: debug, info, warning, error, off |
| `--log-dir` | ./log | Log output directory |
| `--log-max-bytes` | 10000000 | Max size per log file (bytes) |
| `--log-backup-count` | 5 | Number of backup log files to keep |
| `--log-cleanup` / `--no-log-cleanup` | enabled | Enable or disable cleanup after the CLI run |
| `--log-keep-latest` | 20 | Number of latest complete runs to keep |
| `--log-max-total-mb` | 500 | Total log storage limit (MB) |
| `--log-repeat-limit` | 5 | Keep the first N repeated DEBUG templates; 0 disables aggregation |
| `--clean-logs` | false | Plan cleanup only, do not delete |

Each CLI invocation writes a separate
`uasset_read-<timestamp>-pid<PID>-<run_id>.log` file. Rotated backups remain
part of the same run family. Isolated workers forward their diagnostics to the
parent process, so they do not open or rotate the run file independently.

Or via module:

```bash
python -m uasset_read path/to/file.uasset --json
```

## Core API

Simplified high-level API for programmatic use — **recommended entry point**:

```python
from uasset_read import LogConfig, parse_single, parse_batch, diff_single, list_formats

# Parse a single file (returns formatted string)
json_str = parse_single("path/to/file.uasset", format="json")
text = parse_single("path/to/file.uasset", format="markdown")

# Batch parse a directory
results = parse_batch("path/to/directory", format="json")

# Compare two .uasset files
diff_output = diff_single("file1.uasset", "file2.uasset", format="json")

# List available output formats
formats = list_formats()

# Python APIs do not create file logs unless LogConfig is explicit.
log_config = LogConfig(level="debug", dir="./log", run_id="analysis-job")
json_str = parse_single(
    "path/to/file.uasset",
    format="json",
    log_config=log_config,
)
```

### Module-level API

Import directly from submodules for deeper access:

```python
from uasset_read import (
    parse_single, parse_batch, diff_single, list_formats,
    parse_package, parse_uasset_with_linker,
    ParseResult, ParseError, FArchive,
)

# Submodule imports for extended API
from uasset_read.models import UEdGraph, UEdGraphNode, UEdGraphPin, BlueprintMetadata
from uasset_read.blueprint import extract_blueprint_variables, extract_blueprint_metadata
from uasset_read.graph import build_execution_flow_entries, build_data_flows
from uasset_read.kismet import decompile_uasset, KismetDecompiledResult
from uasset_read.link import PackageLinker, UObjectInstance
from uasset_read.semantic import build_semantic_ir, render_semantic_json
from uasset_read.renderers import MarkdownRenderer
```

Full API list: see `src/uasset_read/__init__.py` and `wiki/07-Dev-Guide/Public-API.md`.

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
| -------- | ------ | ------------- |
| **Core** | | |
| FArchive | `archive.py` | Binary reader with byte swapping, mmap |
| Constants | `constants.py` | Version numbers, property type thresholds, CPF/PropertyTag flags |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| Config | `config.py` | `ParseConfig`, `LogConfig` dataclasses |
| Core API | `core/` | `parse_single()`, `parse_batch()`, `diff_single()`, `list_formats()` |
| Package Mgmt | `package.py` | `PackageBundle`, `PackageProvider` (filesystem/Pak/IoStore) |
| CLI | `cli.py` | argparse entry point, delegates to `core.py` API |
| Versioning | `versioning.py` | `VersionContainer`, `build_version_container`, `EUEVersion` |
| Mappings | `mappings.py` | UE type mappings (`.usmap`/`.jmap` parsing) |
| Memory Safety | `memory_safety.py` | Central memory policy, RSS measurement, parser checkpoints |
| Bounded Events | `bounded_events.py` | Bounded event buffer for diagnostics |
| Batch Worker | `batch_worker.py` | Subprocess-isolated per-asset batch worker |
| Project Logging | `project_logging.py` | Structured logging with rotation |
| Semantic | `semantic/` | Semantic IR builder, projection, validator, renderer for JSON output |
| Schemas | `schemas/` | JSON Schema definitions for semantic output |
| **Pipeline** | `pipeline/` | Parsing pipeline orchestration: stages, memory, error handling |
| **IR** | `ir_builder.py` | Package-level intermediate representation builder |
| **Serialization** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **Data Models** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult, Status, Diagnostics |
| **Parsers** | `parsers/` | 36 property type parsers + dispatcher + custom property registry + AssetRegistry parser + class serialization strategy |
| ├ Asset Types | `parsers/asset_types/` | 22 asset type parser files + opaque stubs covering 70+ UE class types |
| **Blueprint** | `blueprint/` | Variable/Transform/Component/Metadata extraction |
| **Graph** | `graph/` | Execution/data flow tracing, chain builder, graph_utils |
| **Kismet** | `kismet/` | Bytecode extractor, EExprToken → AST, C++ translator, BPGC fallback, UFunction script reader |
| ├ Expressions | `kismet/expressions/` | 15 expression types (assignments, control flow, function calls, literals, casts, delegates, etc.) |
| **Linker** | `link/` | PackageLinker two-phase object graph reconstruction, UObjectInstance |
| **CPP Gen** | `cpp_gen/` | C++ skeleton/function extraction, IR formatters, type mapping, UPROPERTY mapping, constructor formatting, body extraction |
| **Pak** | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry, PakFileReader, index parsing, compression, AES decryption |
| **IoStore** | `iostore/` | IoStore container reader, Chunk ID, offset/size structures |
| **Bulk Data** | `bulk/` | BulkData header parsing, flag definitions |
| **Renderers** | `renderers/` | Markdown renderer (JSON output via semantic pipeline) |

## Testing

```bash
python -m pytest tests/ -v           # Run all tests
python -m pytest tests/ -v --cov=uasset_read  # With coverage
```

### UE Editor Ground Truth

When Unreal Editor 5.8 is released, use the official Experimental Unreal MCP server as a live read-only ground-truth channel.

## Tech Stack

- **Language**: Python 3.10+ (match/case, type hints)
- **Dependencies**: Zero runtime dependencies
- **Build**: Direct script (src layout)
- **Testing**: pytest

## Use Cases

| Scenario | How uasset_read helps |
| ---------- | ---------------------- |
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
