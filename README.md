<!-- generated-by: gsd-doc-writer -->
# uasset_read

A Python tool for parsing Unreal Engine `.uasset` files, enabling AI agents to read blueprint content without relying on the UE editor. Focuses on unbaked/editor-saved assets (containing full blueprint data).

[中文版](README.zh-CN.md) | [English](README.md)

## Status

| Metric | Value |
|--------|-------|
| Version | **v9.0 shipped** (__version__ = 6.0.0, not yet bumped) |
| Tests | **554 tests collected** (43 v9.0-specific) |
| Modules | `src/uasset_read/` — 39 files, 150+ public API exports |
| Branch | `v2.8-dev` |

### Current Phase: v9.0 已完成

**Status**: ✅ SHIPPED 2026-05-17

**v9.0 Highlights**:
- ✅ Phase 55 — JSON 输出增强 (`function_graphs` 顶层数组, `output_version` 5.0)
- ✅ Phase 54 — 数据流追踪 (Pure 函数返回值 → 参数输入, 24 tests)
- ✅ Phase 53 — 函数内执行流追踪 (FunctionEntry → CallFunction 链)
- ✅ Phase 52 — 函数图节点解析 (K2Node_FunctionEntry 模型)

## Features

- **PackageFileSummary** — file header parsing
- **NameMap** — name table extraction
- **ImportMap** — dependency mapping
- **ExportMap** — export mapping
- **Blueprint graph parsing** — UEdGraph / Node / Pin structures
- **Advanced properties** — Struct / Map / Set / Enum / Text / Delegate
- **Blueprint variable extraction** — variables, functions, events, metadata
- **Component property parsing** — Transform / Rotation / Scale + scalar attributes (Float/Int/Bool/Byte/Enum/Struct)
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph
- **Circular dependency detection** — mutual reference detection in ImportMap
- **Execution flow tracing** — Event → CallFunction chain tracking
- **Function graph analysis** — FunctionEntry identification, execution/data flow tracing
- **Function graphs output** — Per-function call chains with data flow annotations (v9.0)
- **EnhancedInput support** — TriggerEvent type recognition (Started/Ongoing/Completed/Canceled)

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

# Output modes
uasset-read path/to/file.uasset --summary      # Summary only (no properties)
uasset-read path/to/file.uasset --markdown     # Markdown output

# Strictness
uasset-read path/to/file.uasset --strict       # Stop on warnings
uasset-read path/to/file.uasset --tolerant     # Continue on recoverable errors (default)

# Debug
uasset-read path/to/file.uasset --debug        # Enable debug logging
```

### Module-level API

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

    # Flow tracing
    build_execution_flows, build_data_flows, build_connections_map,

    # Formatters
    format_json_full, format_json_summary,
    format_text_full, format_markdown,
    format_graphs_json, format_blueprint_dict,

    # Linker (v7.0)
    parse_uasset_with_linker, PackageLinker, UObjectInstance,

    # Constants & exceptions
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    UAssetError, ParseError, VersionError,
)
```

Full API list: see `src/uasset_read/__init__.py` (`__all__` exports 150+ items).

## Architecture

FArchive pipeline pattern mirroring UE's internal structure:

```
.uasset → FArchive → Deserializer → Models → Formatters → Output
                ↓
          GraphParser
          BlueprintParser
          DependencyGraphBuilder
          PackageLinker (v7.0: two-stage object graph reconstruction)
```

### Module Structure (`src/uasset_read/`)

| Module | Path | Description |
|--------|------|-------------|
| **Core** | | |
| FArchive | `archive.py` | Binary reader with byte swapping, mmap, bounds checking |
| Constants | `constants.py` | Version numbers, property type thresholds, CPF flags |
| Exceptions | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| Main Parser | `parse_uasset.py` | Top-level `parse_uasset()` and `parse_uasset_with_linker()` |
| CLI | `cli.py` | argparse entry point (`uasset-read`) |
| **Serialization** | `serializers/` | |
| Package Summary | `serializers/package_summary.py` | PackageFileSummary, NameMap parsing |
| Object Resources | `serializers/object_resources.py` | ImportMap, ExportMap, SoftObjectPaths |
| Property Tags | `serializers/property_tags.py` | PropertyTag reading |
| Graph Serialization | `serializers/graph.py` | UEdGraph/Node/Pin from FArchive |
| **Data Models** | `models/` | |
| Core Models | `models/core.py` | UEdGraph/Node/Pin, FEdGraphPinType, FMemberReference |
| Node Types | `models/node_types.py` | K2NodeCallFunction, K2NodeEvent, K2NodeKnot, K2NodeEnhancedInputAction |
| Blueprint Models | `models/blueprint.py` | ParseResult, BlueprintMetadata, Variable, Function, Event |
| Properties | `models/properties.py` | PropertyValue, StructValue, MapValue, EnumValue, etc. |
| Transforms | `models/transforms.py` | VectorValue, RotatorValue, ScaleValue |
| Results | `models/result.py` | ParseResult, StatusInfo |
| **Parsers** | `parsers/` | |
| Property Parser | `parsers/property_parser.py` | Dispatcher + 14 property type parsers |
| Property Types | `parsers/property_types.py` | parse_default_value, format_variable_type |
| **Blueprint** | `blueprint/` | |
| Variable Extractor | `blueprint/variable_extractor.py` | Variables, functions, events extraction |
| Transform Parser | `blueprint/transform_parser.py` | Component Transform/Rotation/Scale |
| Component Extractor | `blueprint/component_extractor.py` | SCS component discovery + scalar properties (Phase 48) |
| Metadata Extractor | `blueprint/metadata_extractor.py` | Blueprint metadata |
| **Graph** | `graph/` | |
| Flow Builder | `graph/flow_builder.py` | Execution flow & data flow tracing |
| Graph Parser | `graph/parser.py` | Blueprint graph extraction |
| **Linker** | `link/` | |
| Package Linker | `link/linker.py` | PackageLinker — FLinkerLoad-style two-stage loading (v7.0) |
| Object Instance | `link/object_instance.py` | UObjectInstance — UE object representation |
| Linker Result | `link/result.py` | LinkerParseResult |
| **Formatters** | `formatters/` | |
| JSON Formatter | `formatters/json_formatter.py` | Full/summary JSON output |
| Text Formatter | `formatters/text_formatter.py` | Human-readable text output |
| Markdown Formatter | `formatters/markdown_formatter.py` | Markdown with Mermaid flowchart |
| Helpers | `formatters/helpers.py` | Shared formatting utilities |
| **Main Pipeline** | | |
| Main Parser | `parse_uasset.py` | Top-level parse function |
| CLI | `cli.py` | Command-line interface |

### Legacy (Removed)

- `uasset_read.py` — 8100+ line single file **removed after Phase 33** (2026-05-12)

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=uasset_read
```

**Current**: 554 tests collected.

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
| v7.0 | 2026-05-14 | ✅ Released | UObjectInstance 对象图重建, PackageLinker, UE5.6 适配, 432 tests |
| v8.0 | 📋 2026-05-17 | ✅ Released | BP→C++ JSON 可翻译性 (Pin LinkedTo, 组件属性, 函数调用引脚, EnhancedInput, 二进制清理) |
| v9.0 | 📋 2026-05-17 | ✅ Released | 函数调用链解析 (FunctionEntry 模型, 执行流/数据流追踪, function_graphs 输出) |

## Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data with different serialization format
- **No bytecode decompilation**: Compiled blueprints use bytecode format; focuses on editor-saved assets
- **No resource export**: Binary data (textures, models) is too large; only metadata extracted
- **Read-only**: Only supports parsing; no modification capability
- **UE source reference required**: .uasset format has no official documentation; requires UE source code as reference

## Planning

- `.planning/ROADMAP.md` — 版本路线图
- `.planning/STATE.md` — 当前里程碑状态
- `.planning/REQUIREMENTS.md` — 需求追溯
- `.planning/PROJECT.md` — 项目概览
- `.planning/MILESTONES.md` — 历史里程碑
- `.planning/milestones/` — 已归档的里程碑（v7.0, v8.0, v9.0）

---

**Last Updated**: 2026-05-18
**Version**: v9.0 shipped (Phases 52-55 complete)
**Tests**: 554 tests collected
**__version__**: 6.0.0 (pending bump)
