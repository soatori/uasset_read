# Research Summary

**Project:** uasset_read — Python .uasset parser for AI agents
**Synthesized:** 2026-04-27

## Executive Summary

This project builds a Python tool to parse Unreal Engine .uasset files, enabling AI agents to directly read blueprint content without UE editor dependency. The .uasset format is undocumented but can be reverse-engineered from UE 5.7 source code (available at `D:/Program Files/Epic Games/Engine/UE_5.7`).

**Key insight:** Focus on uncooked/editor-saved assets which contain full graph data. Cooked assets have stripped editor data and use different serialization (unversioned properties).

---

## Stack Summary

**Zero runtime dependencies** — Python 3.10+ with standard library only.

| Layer | Components | Pattern |
|-------|-----------|---------|
| Input | pathlib, mmap | Memory-mapped file access for large assets |
| Reader | struct, custom FArchive class | Byte-level parsing with explicit endianness |
| Model | dataclasses | Clean data structures, built-in JSON serialization |
| Output | json, text formatting | Structured JSON for agents, readable text for humans |
| CLI | argparse | Single-file execution: `python uasset_read.py file.uasset` |

**Architecture:** Layered pipeline (Reader → Deserializer → Model → Output), mirroring UE's FArchive pattern.

---

## Features Summary

### Table Stakes (Must Have)

1. **Parse .uasset header** — PackageFileSummary with magic tag, version, offsets
2. **Extract name table** — All object/property names reference this
3. **Extract export/import maps** — Objects and dependencies defined here
4. **Identify asset class** — Blueprint, Material, Texture, etc.
5. **Basic property parsing** — Int, Float, String, Bool, Array values
6. **JSON output** — Core requirement for AI agent consumption
7. **Human-readable text** — Semantic descriptions, not raw data
8. **Single-file parsing** — No UE editor or pak extraction required

### Differentiators (Value-Add)

1. **Blueprint graph extraction** — Nodes, pins, connections (HIGH complexity)
2. **Variable definitions** — Names, types, defaults (MEDIUM complexity)
3. **Function definitions** — Signatures, parameters (HIGH complexity)
4. **Dependency graph** — What other assets this uses (MEDIUM complexity)
5. **Semantic node descriptions** — "Calls function X" not "K2Node_CallFunction"

### Anti-Features (Explicitly Out of Scope)

- Binary asset export (textures, models)
- Asset modification/writing
- Blueprint bytecode decompilation
- Pak file extraction
- UE Editor integration
- Cooked asset parsing (focus on uncooked/editor-saved)

---

## Architecture Summary

### Layered Pipeline

```
.uasset file → BinaryReader → AssetDeserializer → Models → OutputFormatter
```

### Key Components

1. **FArchive** — Abstract base class for binary reading (mirrors UE pattern)
2. **PackageSummary** — Header dataclass with offsets to all sections
3. **NameTable** — String pool referenced by FName indices
4. **ImportMap/ExportMap** — Object references and definitions
5. **TypeHandlers** — Plugin registry for asset-specific parsing
6. **BlueprintHandler** — Blueprint-specific extraction logic

### Data Flow

```
1. Read header (PackageFileSummary)
2. Read name table (at NameOffset)
3. Read import map (at ImportOffset)
4. Read export map (at ExportOffset)
5. For each export:
   - Resolve class type
   - Dispatch to handler
   - Parse properties and type-specific data
6. Format output (JSON/Text/Summary)
```

### Build Order

1. Reader layer (FArchive, binary operations)
2. Model layer core (PackageSummary, PackageIndex, Import/Export)
3. Deserializer core (header, name table, import/export parsing)
4. Model layer types (UObject, Blueprint, Properties)
5. Handler layer (type registry, BlueprintHandler)
6. Output layer (JSON, Text, Summary formatters)
7. Performance/polish (mmap, lazy parsing, version handling)

---

## Pitfalls Summary

### Critical (Causes Rewrites)

1. **Endianness Detection** — Check magic tag; enable byte swapping if swapped tag detected
2. **Version Handling** — UE4/UE5/Custom versions; unversioned packages need special handling
3. **BulkData Flags** — PayloadAtEndOfFile, SeparateFile, Compression, 64-bit sizes
4. **FName Index vs String** — FName is index into NameMap, not a string; load NameMap first
5. **Offset Arithmetic** — Absolute vs relative offsets; BulkDataStartOffset base for payloads
6. **Unversioned Properties** — Schema-based serialization (no property tags); requires class layout knowledge
7. **PropertyTag Evolution** — Flags for GUID, extensions, type name; version-dependent fields
8. **UE5 Package Trailer** — Payload TOC, data resources, backwards reading from file end

### Moderate (Causes Issues)

1. **Memory Management** — Don't read entire file; use mmap for large files
2. **struct Alignment** — C++ padding differs from Python; parse field-by-field
3. **String Encoding** — UTF-8 in UE5+, UTF-16 in older; handle LengthPrefix
4. **Import/Export Structure** — Version-dependent fields; FPackageIndex signed encoding
5. **Error Recovery** — Validate sizes/offsets; return partial results, don't crash
6. **Blueprint Graph Complexity** — Undocumented; focus on metadata, accept limitations

### Minor

1. .umap vs .uasset (level packages have extra structures)
2. Generations array (historical version data)
3. Package flags (PKG_Cooked, PKG_UnversionedProperties)
4. SoftObjectPath list (UE5+ dependency tracking)

---

## Key UE Source References

| File | Purpose |
|------|---------|
| `PackageFileSummary.h` | Header structure, offsets, versions |
| `ObjectResource.h` | Import/Export structures, PackageIndex |
| `PropertyTag.h` | Property serialization format |
| `Archive.h` | FArchive abstraction pattern |
| `BulkData.cpp` | BulkData flags and payload handling |
| `Blueprint.h` | Blueprint data structures |
| `EdGraph/EdGraphPin.h` | Pin types, connections |
| `K2Node.h` | Blueprint node hierarchy |

---

## Recommended Phases

Based on research, suggest this roadmap structure:

### Phase 1: Core Parsing (Foundation)
- FArchive base class with byte swapping
- PackageFileSummary header parsing
- Name table extraction
- Import/Export map parsing
- Version detection and handling
- Error handling framework

**Success:** Can read header, name table, and identify what objects are in a .uasset file.

### Phase 2: Property Parsing (Data Extraction)
- PropertyTag parsing
- Basic property types (Int, Float, String, Bool, Name, Object)
- Array property handling
- Struct property basics
- Property value output

**Success:** Can read property values from simple exports.

### Phase 3: Blueprint Basics (Target Feature)
- Blueprint type detection
- Variable definitions extraction
- Parent class resolution
- Basic blueprint metadata
- Blueprint-focused output format

**Success:** Can list blueprint variables and parent class from a blueprint .uasset.

### Phase 4: Blueprint Graphs (Advanced)
- Graph structure parsing (UEdGraph)
- Node identification (UK2Node types)
- Pin parsing and connections
- Semantic node descriptions
- Graph visualization text output

**Success:** Can trace blueprint logic flow with node/pin descriptions.

### Phase 5: Polish & Performance
- Memory-mapped archive for large files
- Lazy export parsing
- Comprehensive error recovery
- Version compatibility matrix
- Output format refinements

**Success:** Handles edge cases, large files, and provides clean output.

---

## Confidence Assessment

| Area | Level | Notes |
|------|-------|-------|
| Package structure | HIGH | Direct from UE 5.7 source |
| Import/Export format | HIGH | Direct from UE 5.7 source |
| Property serialization | MEDIUM | Complex but documented |
| Blueprint metadata | MEDIUM | Structures known, extraction needs care |
| Blueprint graphs | LOW | Undocumented, may hit limitations |
| AI-agent output patterns | LOW | Inferred from requirements, no research |

---

## Gaps & Unknowns

1. **Cooked vs Uncooked** — Need to clarify target asset type; assume uncooked for full graph data
2. **Version Matrix** — Which UE versions to support initially? Recommend UE 5.x first
3. **Property Value Deserialization** — How to read actual values (not just metadata)
4. **Node Type Catalog** — Full UK2Node subclass list for semantic descriptions
5. **Test Files** — Need sample .uasset files for testing; create simple UE project

---

## Next Steps

1. Define formal requirements in REQUIREMENTS.md
2. Create roadmap with phase breakdown in ROADMAP.md
3. Initialize STATE.md for project memory
4. Begin Phase 1 planning via `/gsd-plan-phase 1`

---

*Synthesized from: STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md*
*Research confidence: HIGH for core parsing, MEDIUM for blueprint extraction*