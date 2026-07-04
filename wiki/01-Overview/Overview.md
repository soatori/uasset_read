---
title: Project Overview
section: overview
---

# Project Overview

> [!NOTE] Project Positioning
>
> **uasset_read** is a pure Python parser for Unreal Engine `.uasset` files, enabling AI agents and developers to read blueprints, asset data, and graph structures without launching the UE editor. It focuses on **uncooked/editor-saved** assets.

## Basic Information

| Item | Details |
|------|---------|
| Version | `0.5.1.31` · Python 3.10+ (match/case, type annotations) · Zero runtime dependencies |
| Build System | Direct script (src layout) · `python run.py file.uasset` invocation · PAK optional dependency |
| Supported Assets | 10 specialized asset types (StaticMesh, SkeletalMesh, Material, MaterialInstance, Texture2D, TextureCube, AnimSequence, AnimDataModel, SoundWave, SoundAttenuation) + Blueprint/Map general parsing · Containers: Filesystem / PAK / IoStore |

## Core Capabilities

- **Binary Parsing**: Complete FArchive serialization pipeline, byte-order swapping, mmap large file optimization
- **Blueprint Extraction**: Variables, transforms, components, metadata, execution flow, data flow
- **Kismet Decompilation**: Bytecode -> AST -> C++ code translation, structured control flow
- **Object Linker**: Two-phase object graph reconstruction, cross-package reference resolution
- **IR Intermediate Representation**: Unified data structure layer (PackageIR/ExportIR/GraphIR/NodeIR/PinIR), renderers receive IR only and do not access ParseResult
- **Renderer System**: 2 auto-registered renderers (JSON/Markdown), dispatched via RENDERER_REGISTRY
- **Container Support**: PAK (AES decryption, LZ4/Zstd compression), IoStore containers
- **Core API**: `parse_single`, `parse_batch`, `list_formats` pure function entry points, no argparse/sys.exit/print

## Architecture Evolution

| Version | Architecture | Description |
|---------|-------------|-------------|
| ≤ 0.3.8 | ParseResult -> Exporter -> Output | Exporters access ParseResult directly |
| 0.4.1 | ParseResult -> IR Builder -> PackageIR -> Renderers -> Output | IR layer introduced, parsing decoupled from output |
| **0.4.2** | IR + 2 renderers, Kismet decompilation improvements, C++ skeleton quality, PropertyFallback system | First stable release |
| 0.5.0 | Core/Extras layered architecture, streamlined public API, parser modules split into independent subpackages | |
| **0.5.1.31** | 31 issues fixed since v0.5.1.19: graph output chain, UEdGraph offset, Map Pin terminal types, CPF_* flags, pak/ioStore format, etc. | Current version |

## Key Constraints

> [!IMPORTANT] Important Limitations
>
> - **Uncooked/editor-saved assets only**: Cooked assets have their graph data stripped
> - **Read-only**: Parsing only, no modification or writing supported
> - **Zero runtime dependencies**: No third-party packages added to dependencies
> - **Must reference UE source code**: Format understanding traced back to UE C++ source code, no guessing allowed
