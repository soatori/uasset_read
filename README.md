# uasset_read

> **Python parser for Unreal Engine .uasset files** — read blueprints, extract variables, decompile Kismet bytecode, and inspect asset structures — all without the UE editor.

A zero-dependency Python parser for Unreal Engine `.uasset` files that transforms binary blueprint data into structured JSON and code.

> 📦 **v0.6.0-dev** — Zero runtime dependencies · Python 3.10+ · 72 source files · 21 registered semantic asset handlers

> **Refactor status:** package-first architecture; current output is the v4 package document — one canonical envelope with `format_version: "4.0"` (`projection.FORMAT_VERSION`; frozen contract `docs/designs/contract/package_document_v4.schema.json`), exactly two modes (`normal` default, `debug` adds evidence only), one full document per package with no pagination or byte budget. Static Blueprint graph / Kismet instruction IR / CFG / correlation live under `objects[].semantic` (dict at the document boundary). Embedded type-aware `projections[]` cover Material editor-builder, DataTable/CurveTable/struct/enum data, and physical asset metadata/payload references (typed Blueprint C++ projection was retired by the 2026-09-28 v4 amendment). Payload extraction from cooked sidecars remains available via `extract_payload`. Zen/IoStore full package decoding is outside the current product target; existing TOC metadata only reports the boundary truthfully. Editor `.usmap` unversioned fixtures remain a bounded partial path, while cooked/Zen unversioned is outside the product target. Semantic 1.x JSON remains removed. The structure/size/quality baselines are gated by `tests/`.

## Why uasset_read?

Unreal Engine blueprints are stored as binary `.uasset` files — unreadable without the editor. uasset_read bridges this gap by extracting:

- **Blueprint graphs** — pin-level links, exec-pin edge chains, allow-listed tag-derived `node_data`, Kismet expressions (`semantic.functions[]` / `exec_chains`)
- **Variables & metadata** — types, defaults, categories, tooltips
- **Kismet bytecode** — expression trees with structured diagnostics (`semantic.functions[]`; C++ pseudocode retired 2026-09-10)
- **Component properties** — transforms, materials, mesh references
- **Dependency graphs** — import/export relationships, soft object paths

Whether you're auditing blueprint dependencies, building tooling for game development, or extracting structured asset data, uasset_read gives you structured access to blueprint data at the file level.

## Status

| Metric | Value |
| -------- | ------- |
| Version | v0.5.4.45 (last tagged) / 0.6.0-dev (v4 default) |
| Source | Python parser for Unreal Engine .uasset files |
| Modules | package-first modules incl. `kismet`, `models`, `parsers`, `projections`, `serializers` |
| Tests | current full suite and quality gates pass; structure/size/quality baselines gated |
| Tracked samples | 66 legacy fixtures with manifest validation |

## Features

### v4 Architecture (package-first)

> Default output is the package document with `format_version: "4.0"`: `python -m uasset_read file.uasset` or `parse_package_document()`. The v1 pipeline (Semantic 1.x JSON, `--legacy-json`, `--markdown`, `--diff`, `--list-formats`) was removed; those flags are rejected as unsupported. Output has exactly two modes: `normal` (default) and `--debug`. See `tests/samples/manifest.json` for tracked fixtures.

- **PackageDocument** — one document per .uasset, all exports as first-class objects
- **Legacy / Zen readers** — separate format boundaries; Zen/IoStore package-body decoding is outside the current product target, while TOC metadata remains a truthful boundary check
- **Multi-asset support** — all exports preserved, no `_select_primary_export()` filtering
- **Tagged / unversioned properties** — separate sole-entry readers; unversioned is schema-backed / explicit opaque
- **v4 JSON contract** — `uasset_read.package` envelope with `format_version: "4.0"`, exactly `normal`/`debug` modes, one full document per package (no pagination or byte budget)
- **Static Blueprint analysis** — graph IR, Kismet instruction IR + CFG, correlation (`entrypoints`/`calls`/`variable_accesses`/`control_flow`) under `objects[].semantic` (dict)
- **Type-aware projections** — embedded material editor-builder, table/curve/struct/enum data, asset metadata/payload refs via `ProjectorRegistry`
- **Agent tools** — `inspect_package`, `extract_payload`
- **Projection** — `project_document(document, mode=...)` is the sole envelope producer (`normal` / `debug`); `write_projected_document` writes it to disk; parse depth is a `parse_package_document(depth=...)` input, not an output surface
- **Handlers** — DataTable, UserDefinedEnum, UserDefinedStruct, Texture2D, TextureCube, SoundWave, Skeleton, StaticMesh, Material, Niagara, Blueprint/AnimBlueprint (graph/node/pin + declaration + SCS + VarType + Kismet IR/CFG on editor-saved fixtures; native C++ bodies are never recovered)
- **Unversioned properties** — editor-only mapping-driven path: `LegacyPackageReader(mappings_path=...usmap)` plus `BP_UnversionedTest` / `DA_UnversionedTest`. Unmapped or unreliable tails become explicit `UnversionedOpaque`; cooked/Zen unversioned and a general `SchemaProvider` are outside the product target.

**UE source-audit fixes (v0.6.0-dev):** 35 binary-format mismatches resolved against UE 5.8-dev C++ source — FString UTF-16 byte-swap, FColor B/G/R/A order, FRotator Pitch/Yaw/Roll, FName external number, unversioned header fragment decode, ELifetimeCondition table, mcdelegate PinCategory, FGuid display, dead CppType reads, ImportedSize X/Y, material input variants, anim node table verified against Engine/Source headers. StringTable (#615) partially fixed (FString keys + trailer).

```python
from uasset_read import parse_package_document
from uasset_read.projection import project_document

doc = parse_package_document("file.uasset")
print(project_document(doc))  # PackageDocument JSON dict

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
- **Execution / data flow** — `exec_chains` from pin `category=exec` + `linked` (experimental; unique undirected edges, pin-id endpoints); not full Event→CallFunction chain tracking
- **Function graph analysis** — FunctionEntry identification; pin keys frozen to `id`/`name`/`direction`/`category`/`linked` (Wave A contract)

### Advanced Features

- **Kismet bytecode decompiler** — EExprToken → expression tree (`expression_count` / `expression_types` at asset depth; full `expressions` at decode)
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph

### File Format Support

- **Dedicated asset type parsers** — 21 semantic handler instances in `handlers_impl.py` (registered by UE class name / family) plus tagged-property fallback for the rest of the export map.
- **Payload extraction** — cooked payload extraction from sidecar files (.uexp/.ubulk) with sidecar discovery and BulkData header mapping
- **Game version support** — Game-specific serialization constants
- **Binary/native handlers** — binary or native property serialization support

### Output Formats

- **Package document JSON (`format_version: "4.0"`)** — one document per package covering every export, produced in exactly two modes: `normal` (default) and `debug` (adds an evidence block; stripping it reproduces `normal`). Embedded type-aware `projections[]` ride in the same document. The Python API, CLI and Agent tools all project from this same `PackageDocument`.

Markdown output and Semantic 1.x JSON went away with the v1 pipeline and are **wontfix** (issue #643): the package document schema replaces the old format, and with one format there is nothing for a format registry to list.

## Installation

```bash
pip install -e .
```

This is required for `python -m uasset_read` to resolve the package entry point. Zero runtime dependencies, requires Python 3.10+.

## Usage

### CLI

```bash
python -m uasset_read path/to/file.uasset              # package document JSON (format_version 4.0) to stdout
python -m uasset_read path/to/file.uasset -o out.json  # canonical file via write_projected_document
python -m uasset_read path/to/file.uasset --debug      # debug evidence mode (normal + evidence block)

# Strictness
python -m uasset_read path/to/file.uasset                # Continue on recoverable errors (default)
python -m uasset_read path/to/file.uasset --strict       # Stop on warnings

# Parse controls (not output surfaces)
python -m uasset_read path/to/file.uasset --mappings path/to/usmap  # Load .usmap type mappings
python -m uasset_read path/to/file.uasset --game NAME               # Enable game-specific property readers
```

### Logging Parameters

The library never configures process-global logging, and the CLI neither writes per-run log files nor cleans up leftover `log/` directories (file logging left with the v1 pipeline; cleanup was retired 2026-09-10, Gate L). Delete old `log/` directories yourself if they remain from earlier releases.

## Core API

The package-document API is the only parse entry point (v1 pipeline was removed):

```python
from uasset_read import parse_package_document

# Parse a .uasset file → PackageDocument (format_version 4.0 envelope)
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
from uasset_read.projection import project_document
print(json.dumps(project_document(doc), indent=2))

# CLI usage (the CLI always parses at depth="decode")
# python -m uasset_read file.uasset
# python -m uasset_read file.uasset --debug
```

### Module-level API

Import directly from submodules for deeper access:

```python
from uasset_read import (
    parse_package_document,
    ParseError, FArchive,
)

from uasset_read.models.document import PackageDocument
from uasset_read.projection import project_document
from uasset_read.parsers.asset_types.registry import run_handlers
```

Full API list: see `src/uasset_read/__init__.py` and `wiki/07-Dev-Guide/Public-API.md`.

## Architecture

Data flow is the package-first pipeline defined in the [canonical refactor design](docs/designs/2026-08-26-package-first-uasset-parser-refactor.md):

```text
.uasset → archive → parsers/legacy_reader (Legacy container reader; Zen/IoStore full decode outside product target)
              → parsers (tagged properties; editor usmap path only)
              → models/object_model + parsers/asset_types/registry → PackageDocument
              → projection → JSON / CLI / Agent tools (same document)
```

Shared readers behind that document: `kismet/` (bytecode → expressions + diagnostics, reached through `parsers/legacy_reader.py` at asset/decode), `serializers/` and `models/`.

### Module Structure (`src/uasset_read/`)

| Module | Path | Description |
| -------- | ------ | ------------- |
| **Core** | | |
| FArchive | `archive.py` | Little-endian binary reader, mmap |
| Constants | `constants.py` | Version numbers, property type thresholds, PropertyTag flags |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| Package Mgmt | `package.py` | `PackageBundle`, `FileSystemPackageProvider`, `PackageArchive`, `open_package_bundle` |
| CLI | `cli.py` | argparse entry point; emits the v4 package document (`normal`/`debug`), or the retired-flag error |
| Versioning | `versioning.py` | `VersionContext`, `build_version_context_from_summary` |
| Mappings | `mappings.py` | UE type mappings (`.usmap` parsing; `.jmap` removed 2026-09-10) |
| Memory Safety | `memory_safety.py` | `ResourceBudget` read/decompress checkpoints, `MemoryLimitExceeded` |
| **Serialization** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **Data Models** | `models/` | UEdGraph/Node/Pin, FEdGraphPinType, PropertyTag/PropertyValue, Anim IR, structured diagnostics, property fallback |
| **Parsers** | `parsers/` | 28 tagged-property parse functions + dispatcher, custom property registry, class handler registry, BinaryOrNative handlers |
| ├ Asset Types | `parsers/asset_types/` | `handlers_impl.py` — 21 registered semantic handler instances |
| **Kismet** | `kismet/` | Bytecode extractor, EExprToken → expressions, decompile bridge, BPGC fallback, UFunction script reader (C++ translator retired 2026-09-10) |
| ├ Expressions | `kismet/expressions/` | 15 expression types (assignments, control flow, function calls, literals, casts, delegates, etc.) |
| **Package Document** | `package.py`, `models/`, `projection.py`, `agent_tools.py` | `parse_package_document` entry, `PackageDocument` / `ObjectRecord`, `normal`/`debug` mode projection, agent tools (no `v2/` subpackage — flattened) |

## Testing

The tracked baseline is intentionally small: two test modules
(`tests/test_samples.py`, `tests/test_size_baseline.py`) and at most 100
collected pytest items (enforced during collection by `tests/conftest.py`).
The sample driver also gates the v4 normal/debug public contract, manifest raw
version/layout metadata, and the mandatory bounded-reader/error paths; broader
experiments remain untracked under `temp/`.

```bash
python -m pytest tests/ -v           # Run all tests
python -m pytest tests/ -v --cov=uasset_read  # With coverage

# Quality baseline (default seeds; skips large opt-in fixtures)
python -m pytest tests/test_samples.py -k quality_baseline

# Include ALS_AnimBP opt-in quality entry (~10MB; slower)
UASSET_QUALITY_OPT_IN=1 python -m pytest tests/test_samples.py -k quality_baseline
```

On Windows PowerShell:

```powershell
$env:UASSET_QUALITY_OPT_IN="1"
python -m pytest tests/test_samples.py -k quality_baseline
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
| **Blueprint → C++ migration** | typed declaration/migration projections were retired by the 2026-09-28 v4 amendment; the old string-based C++ skeleton generator remains permanently retired |
| **Dependency auditing** | each package document lists its imports/exports (`objects[]` + `dependencies`); cross-package cycle and orphan detection are *planned* |
| **Mod development** | *planned* — #625 Pak fixture intake is complete, but container extraction remains a separate unsupported capability; today you must extract the `.uasset` first |
| **Asset pipeline automation** | *planned* — the v4 CLI parses one package per invocation; loop over files yourself (e.g. over `tests/samples/manifest.json`) |
| **Technical debt analysis** | Trace execution flows → identify deeply nested logic → find dead code |

## Current Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data
- **Limited bytecode coverage**: Kismet EExprToken → expressions for known token types; C++ pseudocode generation retired 2026-09-10
- **Limited binary data export**: Large payloads (textures, audio) require sidecar files; `extract_payload` reads from `.uexp/.ubulk` when available
- **Read-only**: Parsing only, no modification
- **UE source reference required**: No official .uasset format documentation

The package-first target removes “editor-saved only” as an architectural assumption, but it cannot restore graph data stripped during cooking. Cooked/Zen support must report the data that actually remains and mark unavailable semantics honestly.

---
