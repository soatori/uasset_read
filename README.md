# uasset_read

> **Python parser for Unreal Engine .uasset files** — read blueprints, extract variables, decompile Kismet bytecode, and generate C++ skeletons — all without the UE editor.

A zero-dependency Python parser for Unreal Engine `.uasset` files that transforms binary blueprint data into structured JSON and code.

> 📦 **v0.6.0-dev** — Zero runtime dependencies · Python 3.10+ · 200 source files · 70+ UE class types

> **Refactor status:** v2 package-first architecture: default CLI/API output is `PackageDocument v2` (legacy packages; tagged properties parsed within export bounds; sample-backed handlers incl. lightweight Niagara kind coverage (semantic status partial until domain fields land), no Semantic 1.x handler dependency). Payload descriptors are reserved for cooked containers: Legacy v2 emits no top-level payloads and `extract_payload` is a stable deferred interface (`PAYLOAD_EXTRACTION_DEFERRED`, reads nothing) until redistributable `.uexp/.ubulk/.utoc/.ucas` samples exist (#621). Default `semantic` view excludes raw offsets/property trees; they are opt-in via `raw`/`debug` views. Zen/IoStore, unversioned-with-usmap, and external-container (ubulk/ucas) extraction remain deferred (see `docs/designs/README.md`); Semantic 1.x JSON is no longer available — the v1 pipeline was removed.

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
| Version | 0.5.5 (stable) / 0.6.0-dev (v2 default) |
| Source | Python parser for Unreal Engine .uasset files |
| Modules | 200 source files across 15 subpackages |
| v2 Tests | test_core (≤10 functions) + manifest-driven test_samples (99 collected total, no skips/xfail) |
| Tracked samples | 48 legacy fixtures with manifest validation |

## Features

### v2 Architecture (package-first)

> Default output is PackageDocument v2: `python -m uasset_read file.uasset` or `parse_package_document()`. The v1 pipeline (Semantic 1.x JSON, `--legacy-json`, `--markdown`, `--batch`, `--diff`, `--list-formats`) was removed; those flags are rejected as unsupported. See `tests/samples/manifest.json` for tracked fixtures.

- **PackageDocument** — one document per .uasset, all exports as first-class objects
- **LegacyPackageReader** — direct binary reader, no v1 pipeline dependency
- **Multi-asset support** — all exports preserved, no `_select_primary_export()` filtering
- **Tagged properties** — parsed at `depth="object"` with bounded slices
- **v2 JSON contract** — `uasset_read.package` format with view/depth/selection/pagination/byte-budget
- **Agent tools** — `inspect_package`, `list_objects`, `get_object`, `list_dependencies`, `get_diagnostics`, `extract_payload`
- **Projection** — semantic/raw/debug views, depth filtering, max_bytes enforcement
- **Handlers** — DataTable, UserDefinedEnum, UserDefinedStruct, Texture2D, TextureCube, SoundWave, Skeleton, StaticMesh, Material, Niagara, Blueprint/AnimBlueprint (decode depth: graph/node/pin decode + declaration + SCS components + NewVariables names on editor-saved fixtures; VarType typing and Kismet decompilation not implemented)
- **SchemaProvider** — interface for unversioned property schema lookup

**UE source-audit fixes (v0.6.0-dev):** 35 binary-format mismatches resolved against UE 5.8-dev C++ source — FString UTF-16 byte-swap, FColor B/G/R/A order, FRotator Pitch/Yaw/Roll, FName external number, unversioned header fragment decode, ELifetimeCondition table, mcdelegate PinCategory, FGuid display, dead CppType reads, ImportedSize X/Y, material input variants, anim node table verified against Engine/Source headers. StringTable (#615) partially fixed (FString keys + trailer). 102/102 tests passing.

```python
from uasset_read.v2.api import parse_package_document
doc = parse_package_document("file.uasset")
print(doc.to_dict())  # PackageDocument v2 JSON

# Or use CLI
# python -m uasset_read file.uasset
```

### Core Parsing (v0.5.5 — current stable)

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
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph
- **Circular dependency detection** — mutual reference detection
- **IR (Intermediate Representation)** — package-level IR builder for decoupled rendering pipeline

### File Format Support

- **Dedicated asset type parsers** — StaticMesh, SkeletalMesh, Texture2D, Material, MaterialInstanceConstant, TextureCube, AnimSequence, AnimBlueprint, AnimMontage, AnimBoneCompression, AnimCurveCompression, AnimationDataModel, SoundWave, SoundCue, SoundAttenuation, DataTable, CurveTable, StringTable, Skeleton, PoseAsset, LevelSequence, MovieScene, MovieSceneControlRig, FoliageType, SkeletalMeshLODSettings, SubsurfaceProfile, OpaqueStub, PropertyExtractor; broader asset categories use generic UObject/property fallback paths.
- **Bulk Data** — BulkData header parsing
- **Game version support** — Game-specific serialization constants
- **Binary/native handlers** — binary or native property serialization support

### Output Formats

- **JSON** — structured output via semantic pipeline, optimized for C++ translation reference

### Current v0.5.5 Architecture

- **Renderer system** — Markdown renderer; JSON output routed through semantic pipeline (`semantic/`)

## Installation

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
```

Zero runtime dependencies, requires Python 3.10+.

## Usage

### CLI

```bash
python -m uasset_read path/to/file.uasset              # JSON output to stdout
python -m uasset_read path/to/file.uasset --output output.json   # Save to file

# Output modes
python -m uasset_read path/to/file.uasset --json         # JSON output (default)

# Depth control
python -m uasset_read path/to/file.uasset --depth package   # Headers only
python -m uasset_read path/to/file.uasset --depth object    # With properties
python -m uasset_read path/to/file.uasset --depth asset     # Semantic view (default)
python -m uasset_read path/to/file.uasset --depth decode     # Full decode

# Strictness
python -m uasset_read path/to/file.uasset                # Continue on recoverable errors (default)
python -m uasset_read path/to/file.uasset --strict       # Stop on warnings

# Debug
python -m uasset_read path/to/file.uasset --verbose      # Enable verbose logging
python -m uasset_read path/to/file.uasset --hex-view     # Enable HexView binary inspection
python -m uasset_read path/to/file.uasset --full-parse   # Force full parse for large blueprints

# Advanced options
python -m uasset_read path/to/file.uasset --schema        # Include field semantic annotations
python -m uasset_read path/to/file.uasset --mappings path/to/usmap  # Load type mappings
python -m uasset_read path/to/file.uasset --output-level debug   # Output verbosity level
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
| `--clean-logs` | false | Plan cleanup only, do not delete |

The current implementation intends one run-scoped log family per CLI invocation.
Logging is part of the v2 refactor because nested API configuration can currently
replace handlers. The target library will emit structured diagnostics by default
and create file logs only when the application explicitly requests them.

Or via module:

```bash
python -m uasset_read path/to/file.uasset --json
```

## Core API

The v2 package-document API is the only parse entry point (v1 pipeline was removed):

```python
from uasset_read import parse_package_document, LogConfig

# Parse a .uasset file → PackageDocument v2
doc = parse_package_document("path/to/file.uasset")

# With options
doc = parse_package_document(
    "path/to/file.uasset",
    tolerant=True,
    depth="asset",       # package | object | asset | decode
    mappings_path="path/to.usmap",
    game="SomeGame",
)

# JSON serialization
import json
print(json.dumps(doc.to_dict(), indent=2))

# CLI usage
# python -m uasset_read file.uasset
# python -m uasset_read file.uasset --depth decode
```

### Module-level API

Import directly from submodules for deeper access:

```python
from uasset_read import (
    parse_package_document,
    ParseConfig, LogConfig,
    ParseError, FArchive,
)

from uasset_read.v2.document import PackageDocument
from uasset_read.v2.projection import project_document
from uasset_read.v2.handlers import run_handlers
```

Full API list: see `src/uasset_read/__init__.py` and `wiki/07-Dev-Guide/Public-API.md`.

## Architecture

The following diagram documents the current v0.5.5 implementation, not the v2 target. The target data flow and migration gates are defined in the [package-first refactor report](docs/designs/2026-08-26-package-first-uasset-parser-refactor.md).

FArchive pipeline pattern mirroring UE's internal structure:

```
.uasset → FArchive → Serializers → Parsers → Linker → IR Builder → Renderers → Output
                ↓
          GraphParser
          BlueprintParser
          DependencyGraphBuilder
          PackageLinker
          KismetDecompiler
```

### Module Structure (`src/uasset_read/`)

| Module | Path | Description |
| -------- | ------ | ------------- |
| **Core** | | |
| FArchive | `archive.py` | Binary reader with byte swapping, mmap |
| Constants | `constants.py` | Version numbers, property type thresholds, CPF/PropertyTag flags |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| Config | `config.py` | `ParseConfig`, `LogConfig` dataclasses |
| Core API | `core/` | removed with the v1 pipeline - use `parse_package_document()` from `v2/api.py` |
| Package Mgmt | `package.py` | `PackageBundle`, `PackageProvider` (filesystem) |
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

## Current v0.5.5 Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data
- **Limited bytecode decompilation**: Kismet EExprToken→AST→C++ implemented for known token types
- **No resource export**: Binary data too large; metadata only
- **Read-only**: Parsing only, no modification
- **UE source reference required**: No official .uasset format documentation

The v2 target removes “editor-saved only” as an architectural assumption, but it cannot restore graph data stripped during cooking. Cooked/Zen support must report the data that actually remains and mark unavailable semantics honestly.

---
