---
title: Architecture Design
section: architecture
---

# Architecture Design

## Overall Architecture

```
.uasset / .umap    .pak    .iostore
        ↓ File Source
PackageBundle    PackageArchive    FArchive
        ↓ Binary Reading
PackageFileSummary    NameTable    ImportMap    ExportMap
        ↓ Serialization
PropertyTag    PropertyParser    TypeMappings
        ↓ Property Parsing
BlueprintParser    GraphParser    PackageLinker    KismetDecompiler
        ↓ IR Construction
PackageIR → ExportIR → GraphIR → NodeIR → PinIR
        ↓ Rendering
JSON    Markdown
```

## Parsing Pipeline

```
open_package_bundle → read_package_summary → build_version_container → read_name_table
```

```
read_import_map → read_export_map → parse_properties → post_process → build_package_ir → renderers
```

## Module Structure

| Layer | Path | Responsibility |
|-------|------|----------------|
| Core Layer | `archive.py` / `constants.py` / `exceptions.py` | Binary reading, constants, exception system |
| Package Management | `package.py` / `parse_uasset.py` | Package bundling, Provider abstraction, parsing pipeline |
| Version Management | `versioning.py` | VersionContainer, build_version_container, EUEVersion |
| Type Mapping | `mappings.py` | UE type mapping (.usmap/.jmap parsing) |
| Raw Files | `raw.py` | JSON/INI/LocRes/LocMeta/Audio non-uasset file parsing |
| Core API | `core.py` | parse_single / parse_batch / list_formats pure function entry points |
| Debug | `debug/hex_view.py` | HexView debug system |
| IR Model | `models/ir.py` | PackageIR, ExportIR, GraphIR, NodeIR, PinIR and other intermediate representations |
| IR Builder | `ir_builder.py` | build_package_ir: construct PackageIR from ParseResult |
| Renderers | `renderers/` | 2 renderers, auto-registered to RENDERER_REGISTRY |
| Serializers | `serializers/` | Summary/Import/Export/PropertyTag/graph serialization |
| Parsers | `parsers/` | 40+ property type parsers + dispatcher + custom property registry |
| ├ Asset Types | `parsers/asset_types/` | StaticMesh/SkeletalMesh/Texture2D/Material/MIC/TextureCube/AnimSequence/AnimDataModel/SoundWave/SoundAttenuation dedicated parsers |
| Data Models | `models/` | UEdGraph/Node/Pin, property values, transformations, blueprint models, ParseResult |
| Blueprint | `blueprint/` | Variable/transformation/component/metadata extraction |
| Graph Analysis | `graph/` | Execution flow/data flow/chain builders |
| Kismet | `kismet/` | Bytecode extraction, EExprToken → AST → C++ translation, BPGC fallback, structured control flow |
| ├ Expressions | `kismet/expressions/` | 15 expression types (assignment, control flow, function calls, literals, etc.) |
| Linker | `link/` | PackageLinker two-phase object graph reconstruction, UObjectInstance |
| C++ Generation | `cpp_gen/` | C++ skeleton/function extraction, IR formatters, type mapping, UPROPERTY mapping |
| Pak | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry, PakFileReader, index, compression, AES decryption |
| IoStore | `iostore/` | IoStore container reader, Chunk ID, offset/size structures |
| Bulk Data | `bulk/` | BulkData header parsing, flag definitions |
| UObject | `objects/` | UObject type system, type registry, export types |
| CLI | `cli.py` | argparse entry point, delegates to core.py core API |

> [!TIP]
> **Architecture Change (0.4.1)**: `exporter/`, `n2c/`, `agent/` modules have been removed, replaced by the IR + Renderers architecture.
> **Architecture Change (0.5.0)**: `formatters/` directory has been emptied, all formatting functionality migrated to the `renderers/` system.
>
> **Related Sections**: [[FArchive]] · [[Parsing Pipeline]] · [[Renderer System]] · [[IR Intermediate Representation]]
