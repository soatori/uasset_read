---
title: Contributing Guidelines
section: contributing
---

# Contributing Guidelines

## Code Style

- **Python Version**: 3.10+, using `match/case`, type annotations
- **Code Comments**: Use English
- **Error Messages**: Use English
- **Documentation Format**: Unified English Markdown format
- **Layout Convention**: Follow src layout (`src/uasset_read/`)

## Project Structure

The parser mirrors UE's internal `FArchive` serialization pipeline:

```
.uasset → FArchive → Serializers → Parsers → Models → IR Builder → Renderers → Output
                ↓
          GraphParser · BlueprintParser · DependencyGraphBuilder
          PackageLinker · KismetDecompiler · PakFileReader
```

### Module Responsibilities

| Module | Path | Responsibility |
|--------|------|----------------|
| FArchive | `archive.py` | Binary reader, supports byte swapping, mmap |
| Constants | `constants.py` | Version numbers, property type thresholds, CPF/PropertyTag flags |
| Exceptions | `exceptions.py` | `UAssetError`, `VersionError`, `ParseError`, `ErrorContext` |
| Main Parser | `parse_uasset.py` | `parse_package()`, `parse_uasset()` entry points |
| Package | `package.py` | `PackageBundle`, `PackageProvider` (filesystem/Pak/IoStore) |
| Serializers | `serializers/` | `PackageFileSummary`, `ImportMap`, `ExportMap`, `PropertyTag` |
| Data Models | `models/` | `UEdGraph/Node/Pin`, property value models, `ParseResult`, IR intermediate representation |
| Property Parsers | `parsers/` | 40+ property type parsers + dispatcher + custom property registry + 10 asset type specialized parsers |
| Blueprint | `blueprint/` | Variable/transform/component/metadata extraction |
| Graph Analysis | `graph/` | Execution/data flow tracing, chain builders |
| Kismet | `kismet/` | Bytecode extractor, `EExprToken` → AST → C++ translator |
| Linker | `link/` | `PackageLinker` two-phase object graph reconstruction |
| C++ Generation | `cpp_gen/` | C++ skeleton/function extraction, IR formatters, type mapping |
| PAK | `pak/` | `FPakInfo/PakEntry`, `PakFileReader`, AES decryption |
| IoStore | `iostore/` | IoStore container reader, Chunk ID, offset/size structures |
| Debug | `debug/hex_view.py` | HexView debug system |
| IR | `ir_builder.py`, `models/ir.py` | Package-level intermediate representation builder |
| Renderers | `renderers/` | Pluggable `IRenderer` ABC + format registry (JSON, Markdown) |

## Temporary Files

> [!IMPORTANT]
> Temporary files must be placed in the `temp/` directory; placing them in the project root is prohibited. The root directory should only contain project source code, configuration files, and documentation.

## Git Workflow

- **Development branch**: `develop`
- **Main branch**: `master`
- **Before committing**: Run `python -m pytest tests/ -v` to ensure tests pass
- **PR Requirements**: Include test coverage

## Dependency Management

- **Runtime Dependencies**: Zero dependencies
- **PAK Support**: AES decryption requires `cryptography`, LZ4/Zstd decompression requires `lz4`/`zstandard` (both optional)
- **Prohibited**: Do not add third-party packages to the main `dependencies`

## Development Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run tests with coverage report
python -m pytest tests/ -v --cov=uasset_read

# Run integration tests only
python -m pytest tests/ -v -m integration
```

## CodeGraph Usage Guidelines

This project uses the CodeGraph MCP server for intelligent code retrieval.

| Question | Tool |
|----------|------|
| "Where is X defined?" | `codegraph_search` |
| "Who calls Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "How does X reach Y?" | `codegraph_trace` |
| "What would break if I changed Z?" | `codegraph_impact` |
| "Show me Y's signature/source" | `codegraph_node` |
| "View multiple related symbols at once" | `codegraph_explore` |
| "Get context for a task/area" | `codegraph_context` |

**Usage Principles:**
- For structural questions, use `codegraph_context` first, then one `codegraph_explore` to get source code
- For call chain tracing, use `codegraph_trace` (returns the complete path in one call)
- Do not re-verify confirmed codegraph results with grep
- When index is stale, read specific files rather than guessing

## External References

- `docs/formats/uasset/` — UE .uasset format documentation (60+ Markdown files)
- `external/CUE4Parse/` — Reference C# implementation for cross-validation of parsing logic
- `docs/reference/` — Blueprint node text reference, UE loading flow, CUE4Parse comparison index

## Key Constraints

> [!WARNING]
> - **Uncooked/editor-saved assets only**: Cooked assets have their graph data stripped
> - **Read-only**: Parsing only, no modification or writing supported
> - **Must reference UE source code**: Format understanding must be traced back to UE C++ source code; guessing binary formats is prohibited
