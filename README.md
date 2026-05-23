# uasset_read

A Python tool for parsing Unreal Engine `.uasset` files, enabling AI agents to read blueprint content without relying on the UE editor. Focuses on unbaked/editor-saved assets (containing full blueprint data).

[中文版](README.zh-CN.md) | [English](README.md)

## Status

| Metric | Value |
|--------|-------|
| Version | **v10.0 shipped** (`__version__` = 6.0.0, not yet bumped) |
| Tests | **554 tests** |
| Branch | `2.10-dev` |

### Current Phase: v11.0 — Kismet 字节码反编译器（计划中）

参考 CUE4Parse 设计，实现从函数体字节码到可读 C++ 伪代码的完整反编译流程。详见 `.planning/STATE.md`。

### Latest Shipped: v10.0 — Blueprint-to-C++ 代码生成参考

从蓝图 JSON 输出提取 C++ 类骨架、函数签名、输入绑定、执行流、函数调用链、组件初始化代码。

## Features

- **PackageFileSummary** — file header parsing
- **NameMap** — name table extraction
- **ImportMap** — dependency mapping
- **ExportMap** — export mapping
- **Blueprint graph parsing** — UEdGraph / Node / Pin structures
- **Advanced properties** — Struct / Map / Set / Enum / Text / Delegate
- **Blueprint variable extraction** — variables, functions, events, metadata
- **Component property parsing** — Transform / Rotation / Scale + scalar attributes
- **Dependency analysis** — ImportMap + SoftObjectPaths dependency graph
- **Circular dependency detection** — mutual reference detection in ImportMap
- **Execution flow tracing** — Event → CallFunction chain tracking
- **Function graph analysis** — FunctionEntry identification, execution/data flow tracing
- **Function graphs output** — Per-function call chains with data flow annotations (v9.0)
- **EnhancedInput support** — TriggerEvent type recognition
- **C++ skeleton extraction** — Component declarations, function signatures, transforms (v10.0)
- **C++ header formatting** — .h/.cpp text output from blueprint (v10.0)
- **Kismet bytecode decompiler** — Planned (v11.0)

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
uasset-read path/to/file.uasset --markdown     # Markdown output

# C++ skeleton (v10.0)
uasset-read path/to/file.uasset --cpp-skeleton  # Extract C++ class skeleton

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

    # Parsers
    parse_property_value, parse_properties_from_export,

    # Blueprint
    extract_blueprint_variables, extract_blueprint_metadata,
    parse_component_transform, extract_component_transforms,

    # Flow tracing
    build_execution_flows, build_data_flows, build_connections_map,

    # Formatters
    format_json_full, format_json_summary,
    format_text_full, format_markdown,

    # Linker (v7.0)
    parse_uasset_with_linker, PackageLinker, UObjectInstance,

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
          PackageLinker (v7.0: two-stage object graph reconstruction)
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
| **Serialization** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **Data Models** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult |
| **Parsers** | `parsers/` | 14 property type parsers + dispatcher |
| **Blueprint** | `blueprint/` | Variable/Transform/Component/Metadata extraction |
| **Graph** | `graph/` | Execution/data flow tracing, function graphs |
| **Linker** | `link/` | PackageLinker, UObjectInstance (v7.0) |
| **Formatters** | `formatters/` | JSON/Text/Markdown output |

## Testing

```bash
python -m pytest tests/ -v           # Run all tests
python -m pytest tests/ -v --cov=uasset_read  # With coverage
```

**Current**: 554 tests collected.

## Tech Stack

- **Language**: Python 3.10+ (match/case, type hints)
- **Dependencies**: Zero runtime dependencies
- **Build**: setuptools (src layout), pyproject.toml
- **Testing**: pytest
- **Workflow**: GSD (Guided Software Development)

## Version History

| Version | Date | Status | Highlights |
|---------|------|--------|------------|
| v1.0 | 2026-04-28 | ✅ | Core parsing, basic properties |
| v2.0 | 2026-05-02 | ✅ | Blueprint graph parsing, advanced properties |
| v5.1 | 2026-05-07 | ✅ | src layout + pyproject.toml |
| v6.0 | 2026-05-13 | ✅ | Modular refactoring, 373 tests |
| v7.0 | 2026-05-14 | ✅ | UObjectInstance 对象图重建, PackageLinker |
| v8.0 | 2026-05-17 | ✅ | BP→C++ JSON 可翻译性 (P47-51) |
| v9.0 | 2026-05-17 | ✅ | 函数调用链解析 (P52-55), function_graphs |
| v10.0 | 2026-05-18 | ✅ | Blueprint-to-C++ 代码生成参考 (P56-60) |
| v11.0 | — | 📋 | Kismet 字节码反编译器 (P61-64) |

## Documentation

| Document | Path |
|----------|------|
| Getting Started | [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Configuration | [docs/CONFIGURATION.md](docs/CONFIGURATION.md) |
| Development | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| Testing | [docs/TESTING.md](docs/TESTING.md) |
| Contributing | [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) |
| Security | [docs/SECURITY.md](docs/SECURITY.md) |
| Reference Docs | [docs/reference/](docs/reference/) |
| Roadmap | [.planning/ROADMAP.md](.planning/ROADMAP.md) |
| Project Overview | [.planning/PROJECT.md](.planning/PROJECT.md) |
| Archive | [.planning/archive/](.planning/archive/) |

## Limitations

- **Only unbaked/editor-saved assets**: Cooked assets have stripped graph data
- **No bytecode decompilation**: Planned for v11.0 (Kismet decompiler)
- **No resource export**: Binary data too large; metadata only
- **Read-only**: Parsing only, no modification
- **UE source reference required**: No official .uasset format documentation

---

**Last Updated**: 2026-05-19
**Version**: v10.0 shipped | **Tests**: 554
