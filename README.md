# uasset_read

A Python tool for parsing Unreal Engine `.uasset` files, enabling AI agents to read blueprint content without relying on the UE editor. Focuses on unbaked/editor-saved assets (containing full blueprint data).

[中文版](README.zh-CN.md) | [English](README.md)

## Status

| Metric | Value |
|--------|-------|
| Version | **v7.0** (UE FLinkerLoad 对象图重建完成) |
| Tests | **432 passed, 20 pre-existing, 68 skipped** |
| Modules | `src/uasset_read/` — 15+ modules, 50+ public API exports |
| Next | **v8.0** — BP→C++ JSON 可翻译性 (Phase 47-50 规划中) |

### Current Phase: Phase 47 — Pin LinkedTo 修复 (规划中)

**Status**: 🔴 未开始  
**Goal**: 修复 `linked_to_raw` 为空，使 Pin 连接关系可追踪  
**范围**: Phase 47–50 聚焦于补全 JSON 中缺失的结构信息，不生成 C++ 代码

**Recent Work (v7.0 已完成)**:
- ✅ Phase 46 — UE5.6 资产端到端验证 (12/12 UAT 通过)
- ✅ Phase 45 — 图序列化 linker 变体 (`from_archive_with_linker()`)
- ✅ Phase 44a/44b/44c — 技术债清理 (UE4 兼容代码、struct.unpack、测试工具)
- ✅ Phase 41–44 — UObjectInstance 对象图重建

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

### CLI

```bash
uasset-read path/to/file.uasset           # JSON output to stdout
uasset-read path/to/file.uasset --output output.json   # Save to file

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
# Run all tests
python -m pytest tests/ -v

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

| Module | Path | Description |
|--------|------|-------------|
| **Core** | | |
| FArchive | `archive.py` | Binary reader with byte swapping, mmap, bounds checking |
| Constants | `constants.py` | Version numbers, property type thresholds, MMAP_THRESHOLD |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| **Serialization** | | |
| Serializers | `serializers/` | PackageFileSummary, ObjectImport/Export, PropertyTag |
| **Data Models** | | |
| Core Models | `models/core.py` | UEdGraph/Node/Pin, node type subclasses |
| Blueprint Models | `models/blueprint.py` | ParseResult, blueprint metadata, property data classes |
| Transforms | `models/transforms.py` | VectorValue, RotatorValue, ScaleValue |
| **Parsers** | | |
| Property Parsers | `parsers/` | 14 property type parse functions + dispatcher |
| **Blueprint** | | |
| Variable Extraction | `blueprint/variable_extractor.py` | Variables, functions, events extraction |
| Transform Parser | `blueprint/transform_parser.py` | Component Transform/Rotation/Scale |
| Metadata Extraction | `blueprint/metadata_extractor.py` | Blueprint metadata |
| **Graph** | | |
| From Archive | `graph/from_archive.py` | UEdGraph/Node/Pin parsing from FArchive |
| Flow Builder | `graph/flow_builder.py` | Execution flow & data flow tracing |
| Summary Builder | `graph/summary_builder.py` | Graph summary generation |
| **Formatters** | | |
| JSON Formatter | `formatters/json.py` | Full/summary JSON output |
| Text Formatter | `formatters/text.py` | Human-readable text output |
| Markdown Formatter | `formatters/markdown.py` | Markdown with Mermaid flowchart |
| **Main Pipeline** | | |
| Main Parser | `parse_uasset.py` | Top-level parse function |
| CLI | `cli.py` | Command-line interface |

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
| v6.0 | 2026-05-10 | ✅ Released | Modular refactoring, 373 tests passing |
| v7.0 | 2026-05-14 | ✅ Released | UObjectInstance 对象图重建, UE5.6 适配, 432 tests |
| v8.0 | 📋 Planned | - | BP→C++ JSON 可翻译性 (Phase 47-50) |

## Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data with different serialization format
- **No bytecode decompilation**: Compiled blueprints use bytecode format; focuses on editor-saved assets
- **No resource export**: Binary data (textures, models) is too large; only metadata extracted
- **Read-only**: Only supports parsing; no modification capability
- **UE source reference required**: .uasset format has no official documentation; requires UE source code as reference

## Planning

- `.planning/ROADMAP.md` — 版本路线图
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/MILESTONES.md` — 历史里程碑
- `.planning/milestones/v8.0.md` — v8.0 详细规划
- `.planning/research/` — UE 参考研究
- `.planning/archive/` — 已归档的历史版本文档

---

**Last Updated**: 2026-05-15  
**Version**: v7.0 (v8.0 Phase 47 planning)  
**Tests**: 432 passed, 20 pre-existing, 68 skipped
