# uasset_read

A Python tool for parsing Unreal Engine `.uasset` files, enabling AI agents to read blueprint content without relying on the UE editor. Focuses on unbaked/editor-saved assets (containing full blueprint data).

[中文版](README.zh-CN.md) | [English](README.md)

## Status

| Metric | Value |
|--------|-------|
| Version | **v13.0 in development** (`__version__` = 9.0.0) |
| Tests | **1443 tests** (1319 passed, 122 skipped) |
| Branch | `2.11-dev` |

### Current Phase: v13.0 — Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分（开发中）

- **Phase 72-A ✅**: Pin 连接二进制诊断（2 bugs 定位：history_type signed / ParentPin conditional read）
- **Phase 72-B ✅**: Pin 连接修复 + 回归测试通过（762 tests）
- **Phase 72-C ✅**: Kismet 字节码导航 — BPGC fallback extraction module（295 lines）
- **Phase 72-UAT ✅**: UAT 验证（1319 tests passed, 0 regressions）
- **Phase 72-D ⬜**: FString/FName 区分（pending — 35 处空字符串误报）
- **Phase 72-E 🔴**: EventGraph 节点解析修复（inserted — 覆盖率 ~56% → 目标 >90%）
- **Phase 72-F 🔴**: BPGC 缓存隔离修复（inserted — 多文件 parse 缓存串扰）

### Next: v14.0 — EventGraph 解析完善 + FString/FName 精确区分

详见 `.planning/ROADMAP.md`。

### Latest Shipped: v12.0 — 序列化修复 + N2C 中间格式 + 节点分类体系 + 处理器架构

- **Phase 67 ✅**: UE5.4+ PropertyTag 兼容 + FString 健壮性
- **Phase 68 ✅**: N2CNodeTypeRegistry — 126 种 K2Node 语义类型注册表
- **Phase 69 ✅**: 节点处理器架构 — Processor 模式拆分
- **Phase 70 ✅**: N2CStruct JSON Schema — Agent 可理解的结构化输出
- **Phase 71 ✅**: 执行流链式表达（N2C 风格 `N1->N2->N3`）

### Previously Shipped: v11.0 — Kismet 反编译器 + 图解析修复 + Agent 翻译管线

- **Phase 61-63 ✅**: Kismet 字节码反编译（EExprToken → AST → C++ 伪代码）
- **Phase 64 ✅**: Pipeline 集成 + 端到端测试
- **Phase 65 ✅**: 图解析器修复（FMemberReference + Pin 连接 + Struct 映射）
- **Phase 66 ✅**: Agent 翻译管线 — AgentTranslationPipeline + CppFileWriter

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
- **Kismet bytecode decompiler** — EExprToken → KismetExpression AST → C++ pseudo-code (v11.0 P61-63) ✅
- **Kismet pipeline integration** — decompile_uasset() with golden-path tests (v11.0 P64) ✅
- **Graph parser fixes** — FMemberReference, Pin connections, Struct mapping (v11.0 P65) ✅
- **Agent translation pipeline** — AgentTranslationPipeline + CppFileWriter (v11.0 P66) ✅
- **N2C intermediate format** — N2CStruct JSON Schema, execution chain format (v12.0 P67-71) ✅
- **Pin connection fixes** — history_type signed conversion, ParentPin conditional read (v13.0 P72-A/B) ✅
- **BPGC bytecode navigation** — Cooked blueprint fallback bytecode extraction (v13.0 P72-C) ✅
- **PackageLinker** — Two-stage object graph reconstruction (v7.0)

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
    build_execution_chains,  # v12.0 N2C-style chain format

    # Formatters
    format_json_full, format_json_summary,
    format_text_full, format_markdown,

    # Linker (v7.0)
    parse_uasset_with_linker, PackageLinker, UObjectInstance,

    # Kismet (v11.0)
    decompile_uasset, KismetDecompiledResult,
    KismetTranslator, to_function_body,

    # N2C intermediate format (v12.0)
    N2CStruct, N2CGraph, to_n2c_json, from_n2c_json,

    # Agent translation (v11.0)
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
          PackageLinker (v7.0: two-stage object graph reconstruction)
          KismetDecompiler (v11.0: bytecode → AST → C++)
          N2C Format (v12.0: Agent-optimized JSON schema)
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
| **Graph** | `graph/` | Execution/data flow tracing, chain builder (v12.0) |
| **Kismet** | `kismet/` | Bytecode extractor, EExprToken → AST, C++ translator, BPGC fallback (v11.0/v13.0) |
| **Linker** | `link/` | PackageLinker, UObjectInstance (v7.0) |
| **CPP Gen** | `cpp_gen/` | C++ skeleton/function extraction, IR formatters (v10.0) |
| **Agent** | `agent/` | AgentTranslationPipeline + CppFileWriter (v11.0 P66) |
| **N2C** | `n2c/` | N2CStruct/Graph/Node/Pin models, JSON schema, validators (v12.0) |
| **Formatters** | `formatters/` | JSON/Text/Markdown/Mermaid output |

## Testing

```bash
python -m pytest tests/ -v           # Run all tests
python -m pytest tests/ -v --cov=uasset_read  # With coverage
```

**Current**: 1443 tests collected.

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
| v11.0 | 2026-05-20 | ✅ | Kismet 反编译器 + 图解析修复 + Agent 翻译管线 (P61-66) |
| v12.0 | 2026-05-21~22 | ✅ | 序列化修复 + N2C 中间格式 + 节点分类 + 执行流链式 (P67-71) |
| v13.0 | 2026-05-23 | 🔄 | Pin 连接修复 + Kismet 字节码导航 (P72-A/B/C) |

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
- **Limited bytecode decompilation**: Kismet EExprToken→AST→C++ implemented for known token types; full coverage in progress
- **No resource export**: Binary data too large; metadata only
- **Read-only**: Parsing only, no modification
- **UE source reference required**: No official .uasset format documentation

---

**Last Updated**: 2026-05-23
**Version**: v13.0 in development | **Tests**: 1443
