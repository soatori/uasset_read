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
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph
- **Circular dependency detection** — mutual reference detection
- **IR (Intermediate Representation)** — package-level IR builder for decoupled rendering pipeline

### File Format Support

- **Dedicated asset type parsers** — StaticMesh, SkeletalMesh, Texture2D, Material, MaterialInstanceConstant, TextureCube, AnimSequence, AnimBlueprint, AnimMontage, AnimBoneCompression, AnimCurveCompression, AnimationDataModel, SoundWave, SoundCue, SoundAttenuation, DataTable, CurveTable, StringTable, Skeleton, PoseAsset, LevelSequence, MovieScene, MovieSceneControlRig, FoliageType, SkeletalMeshLODSettings, SubsurfaceProfile, OpaqueStub, PropertyExtractor; broader asset categories use generic UObject/property fallback paths.
- **Bulk Data** — BulkData header parsing
- **Game version support** — Game-specific serialization constants
- **Binary/native handlers** — binary or native property serialization support

### Output Formats

- **PackageDocument v2 JSON** — one document per package covering every export, projected to a bounded page by `--depth` / `--limit` / `--max-bytes`. The Python API, CLI and Agent tools all project from this same document.

Markdown output and Semantic 1.x JSON went away with the v1 pipeline and are **wontfix** (issue #643): the v2 schema replaces the old format, and with one format there is nothing for a format registry to list.

## Installation

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
```

Zero runtime dependencies, requires Python 3.10+.

## Usage

### CLI

```bash
python -m uasset_read path/to/file.uasset              # PackageDocument v2 JSON to stdout
python -m uasset_read path/to/file.uasset --output output.json   # Save to file

# Depth control
python -m uasset_read path/to/file.uasset --depth package   # Headers only
python -m uasset_read path/to/file.uasset --depth object    # With properties
python -m uasset_read path/to/file.uasset --depth asset     # Semantic view (default)
python -m uasset_read path/to/file.uasset --depth decode     # Full decode

# Strictness
python -m uasset_read path/to/file.uasset                # Continue on recoverable errors (default)
python -m uasset_read path/to/file.uasset --strict       # Stop on warnings

# Result budgeting (applies at any depth)
python -m uasset_read path/to/file.uasset --depth decode --limit 20         # Cap objects returned
python -m uasset_read path/to/file.uasset --depth decode --max-bytes 4096   # Cap the serialized response

# Advanced options
python -m uasset_read path/to/file.uasset --mappings path/to/usmap  # Load .usmap/.jmap type mappings
python -m uasset_read path/to/file.uasset --game NAME               # Enable game-specific property readers
python -m uasset_read path/to/file.uasset --list-package-files      # List the package files discovered
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

Data flow is the v2 package-first pipeline defined in the [canonical refactor design](docs/designs/2026-08-26-package-first-uasset-parser-refactor.md):

```text
.uasset → archive → v2/package (Legacy container reader; Zen deferred, #624)
              → parsers (tagged properties; unversioned gated on #623)
              → v2/object_model + v2/handlers → PackageDocument
              → v2/projection → JSON / CLI / Agent tools (same document)
```

Shared readers behind that document: `link/` (PackageLinker two-phase object graph), `graph/` (UEdGraph/Node/Pin), `kismet/` (bytecode → C++ pseudocode, reached through `v2/package/legacy.py`; retirement open in #642), `serializers/` and `models/`.

### Module Structure (`src/uasset_read/`)

| Module | Path | Description |
| -------- | ------ | ------------- |
| **Core** | | |
| FArchive | `archive.py` | Binary reader with byte swapping, mmap |
| Constants | `constants.py` | Version numbers, property type thresholds, CPF/PropertyTag flags |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| Config | `config.py` | `ParseConfig`, `LogConfig` dataclasses |
| Package Mgmt | `package.py` | `PackageBundle`, `PackageProvider` (filesystem) |
| CLI | `cli.py` | argparse entry point; emits the v2 document page, or the retired-flag error |
| Versioning | `versioning.py` | `VersionContainer`, `build_version_container`, `EUEVersion` |
| Mappings | `mappings.py` | UE type mappings (`.usmap`/`.jmap` parsing) |
| Memory Safety | `memory_safety.py` | Central memory policy, RSS measurement, parser checkpoints |
| Bounded Events | `bounded_events.py` | Bounded event buffer for diagnostics |
| Project Logging | `project_logging.py` | Structured logging with rotation |
| **Serialization** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **Data Models** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult, Status, Diagnostics |
| **Parsers** | `parsers/` | 36 property type parsers + dispatcher + custom property registry + AssetRegistry parser + class serialization strategy |
| ├ Asset Types | `parsers/asset_types/` | 22 asset type parser files + opaque stubs covering 70+ UE class types |
| **Graph** | `graph/` | Execution/data flow tracing, chain builder, graph_utils |
| **Kismet** | `kismet/` | Bytecode extractor, EExprToken → AST, C++ translator, BPGC fallback, UFunction script reader |
| ├ Expressions | `kismet/expressions/` | 15 expression types (assignments, control flow, function calls, literals, casts, delegates, etc.) |
| **Linker** | `link/` | PackageLinker two-phase object graph reconstruction, UObjectInstance |
| **v2 Document** | `v2/` | `api.py` entry point, `document.py` PackageDocument, `object_model.py`, `properties.py`, `handlers.py`, `package/legacy.py` reader, `projection.py` paging/budget, `agent_tools.py`, `blueprint_graph.py`, `diagnostics.py` |

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
| **Dependency auditing** | *planned* — v2 lists imports/exports per package (`list_dependencies`); cross-package cycle and orphan detection are not implemented |
| **Mod development** | *planned* — reading assets from `.pak` is deferred to #625; today you must extract the `.uasset` first |
| **Asset pipeline automation** | *planned* — v1 `--batch` was removed with the v1 pipeline; parse files one at a time via `parse_package_document()` until batch driving is rebuilt (#643) |
| **Technical debt analysis** | Trace execution flows → identify deeply nested logic → find dead code |

## Current Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data
- **Limited bytecode decompilation**: Kismet EExprToken→AST→C++ implemented for known token types
- **No resource export**: Binary data too large; metadata only
- **Read-only**: Parsing only, no modification
- **UE source reference required**: No official .uasset format documentation

The v2 target removes “editor-saved only” as an architectural assumption, but it cannot restore graph data stripped during cooking. Cooked/Zen support must report the data that actually remains and mark unavailable semantics honestly.

---
