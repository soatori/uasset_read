# uasset_read

A Python tool for parsing Unreal Engine `.uasset` files, enabling AI agents to read blueprint content without relying on the UE editor. Focuses on unbaked/editor-saved assets (containing full blueprint data).

[中文版](README.zh-CN.md) | [English](README.md)

## Status

| Metric | Value |
|--------|-------|
| Version | **dev-0.3.0** (v14, Phase 76) |
| Tests | **1646 tests** (1516 passed, 124 skipped) |
| Branch | `dev-0.3.0` |

### Current Phase: v14.0 — CUE4Parse 核心对齐

- **Phase 74 ✅**: PinReference null/non-null 主路径对齐
- **Phase 75 ✅**: EventGraph 节点字段级对齐
- **Phase 77 ✅**: Pak 解析 + 压缩 + AES-ECB（62 tests, UAT 8/8）
  - `pak/` — FPakInfo/PakEntry/FPakDirectoryEntry 数据结构 + 序列化
  - `pak/reader.py` — PakFileReader（open/extract/context manager）
  - `compression/dispatch.py` — Zlib/LZ4/Zstd/Oodle 分派 + 优雅降级
  - `crypto/aes_ecb.py` — AES-ECB 解密 + CustomEncryption 委托
  - `pak/index.py` — Legacy flat index + v10+ PathHashIndex/DirectoryIndex
- **Phase 76 ⬜**: FArchive 补齐 + COR 修复（下一个 — StructProperty 深度解析 + FAssetArchive + FCustomVersion + VersionContainer）
- **Phase 78 ⬜**: UObject 继承树 + PackageLinker 重构
- **Phase 79 ⬜**: IoStore (.utoc/.ucas) 解析
- **Phase 80 ⬜**: 输出格式 PascalCase 对齐

详见 `.planning/ROADMAP.md`。

### Latest Shipped: v13.0 — Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分

- **Phase 72 ✅**: Pin 连接修复 + BPGC 字节码导航 + FString/FName 区分（P72-A~I）
- **Phase 73 ✅**: Pin 序列化边界对齐 + PropertyTag 级联恢复 + 端到端连接验收
- **Phase 74 ✅**: PinReference 主路径对齐
- **Phase 75 ✅**: EventGraph 节点字段级对齐

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
- **FString/FName distinction** — null-termination validation replacing null_ratio heuristic (v13.0 P72-D) ✅
- **Pin serialization boundary alignment** — PropertyTag cascade recovery, end-to-end connection验收 (v13.0 P73) ✅
- **PinReference layout** — null/non-null main path alignment with UE source (v13.0 P74) ✅
- **EventGraph field-level alignment** — node field alignment with reference assets (v13.0 P75) ✅
- **Pak file parsing** — FPakInfo/PakEntry, Zlib/LZ4/Zstd/Oodle compression, AES-ECB decryption, index parsing (v14.0 P77) ✅
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
          PakFileReader (v14.0: .pak parsing, compression, AES decryption)
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
| **Pak** | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry, PakFileReader, index parsing (v14.0 P77) |
| **Compression** | `compression/` | Zlib/LZ4/Zstd/Oodle dispatch with graceful degradation (v14.0 P77) |
| **Crypto** | `crypto/` | AES-ECB decryption, CustomEncryption delegate (v14.0 P77) |
| **Formatters** | `formatters/` | JSON/Text/Markdown/Mermaid output |

## Testing

```bash
python -m pytest tests/ -v           # Run all tests
python -m pytest tests/ -v --cov=uasset_read  # With coverage
```

**Current**: 1646 tests collected.

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
| v13.0 | 2026-05-23~26 | ✅ | Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分 (P72-75) |
| v14.0 | 2026-05-26 ~ | 🔄 | CUE4Parse 核心对齐 — Pak 解析 + FArchive 补齐 + 格式对齐 (P76-80) |

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

**Last Updated**: 2026-05-26
**Version**: v14.0 in development | **Tests**: 1646
