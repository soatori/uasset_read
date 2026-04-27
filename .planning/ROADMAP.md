# Roadmap: uasset_read

**Created:** 2026-04-27
**Project:** Python .uasset parser for AI agents
**Total Phases:** 5
**Granularity:** Standard (5-8 phases, balanced size)

## Phase Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|-------------------|
| 1 | Core Parsing | Parse .uasset header, name table, and maps; detect asset structure | CORE-01 through CORE-08 | 4 criteria |
| 2 | Property Parsing | Read and extract property values from exports | PROP-01 through PROP-09 | 4 criteria |
| 3 | Blueprint Extraction | Extract blueprint-specific metadata (variables, parent class) | BLUE-01 through BLUE-06 | 4 criteria |
| 4 | Output & CLI | JSON/text output formats, command-line interface | OUT-01 through OUT-06, CLI-01 through CLI-06 | 4 criteria |
| 5 | Polish & Safety | Performance optimization, error handling, safety checks | SAFE-01 through SAFE-05 | 3 criteria |

---

## Phase 1: Core Parsing

**Goal:** Parse .uasset file header, name table, import map, and export map; identify asset structure and type.

**Requirements:** CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06, CORE-07, CORE-08

**Duration Estimate:** Medium (foundation layer, sets up all subsequent work)

### Success Criteria

1. **Given** any valid .uasset file, **When** parser reads header, **Then** PackageFileSummary contains correct magic tag, version numbers, and offsets.
2. **Given** a file with swapped endianness magic tag, **When** parser detects it, **Then** byte swapping is enabled and all subsequent reads are correct.
3. **Given** a valid .uasset file, **When** parser reads name table and maps, **Then** NameMap, ImportMap, and ExportMap contain all entries with correct values.
4. **Given** an unsupported version .uasset, **When** parser detects version, **Then** clear error message is returned without crash.

### Key Work

- FArchive base class with read methods (u8, u32, u64, f32, fstring)
- Byte swapping detection and handling (PACKAGE_FILE_TAG vs PACKAGE_FILE_TAG_SWAPPED)
- PackageFileSummary parsing (all header fields)
- Name table extraction (NameOffset, NameCount, FString entries)
- Import map parsing (FObjectImport structure)
- Export map parsing (FObjectExport structure)
- Asset class identification from ClassIndex
- Version handling (UE4/UE5/Custom versions)
- Error handling framework (custom exceptions)

### Dependencies

None — foundation phase.

### Risks

- **Endianness edge cases:** Files saved on different platforms may have unexpected byte order
- **Version complexity:** UE version system is multi-layered (UE4, UE5, custom, legacy)
- **Offset arithmetic:** Mixing absolute vs relative offsets causes misreads

### UE Source References

- `PackageFileSummary.h` — Header structure
- `ObjectResource.h` — Import/Export structures
- `Archive.h` — FArchive pattern
- `PackageFileSummary.cpp` — Summary serialization

---

## Phase 2: Property Parsing

**Goal:** Parse PropertyTag and extract basic property values (int, float, bool, string, name, object, array).

**Requirements:** PROP-01, PROP-02, PROP-03, PROP-04, PROP-05, PROP-06, PROP-07, PROP-08, PROP-09

**Duration Estimate:** Medium (property types are diverse, need systematic handling)

### Success Criteria

1. **Given** an export with properties, **When** parser reads PropertyTag, **Then** tag contains correct name, type, size, and flags.
2. **Given** properties of basic types (Int, Float, Bool, String, Name), **When** parser extracts values, **Then** values match expected content.
3. **Given** an ArrayProperty, **When** parser reads elements, **Then** all elements are correctly parsed.
4. **Given** PropertyTag with HasPropertyGuid flag, **When** parser reads full tag, **Then** GUID field is extracted correctly.

### Key Work

- PropertyTag parsing (name, type, array index, size, flags, GUID, extensions)
- IntProperty parsing (int32, int64)
- FloatProperty parsing (float, double)
- BoolProperty parsing (inline bool byte)
- StrProperty parsing (FString with length prefix)
- NameProperty parsing (FName resolved from NameMap)
- ObjectProperty parsing (FPackageIndex reference)
- ArrayProperty parsing (count + element loop)
- PropertyTag flags handling (HasPropertyGuid, HasPropertyExtensions)

### Dependencies

- Phase 1 (needs PackageFileSummary, NameMap, ExportMap, FArchive)

### Risks

- **PropertyTag evolution:** Flags and fields differ between UE versions
- **FString encoding:** UTF-8 vs UTF-16 depends on version
- **Array nesting:** Nested arrays or arrays of complex types increase complexity

### UE Source References

- `PropertyTag.h` — Property tag structure
- `PropertyTag.cpp` — Serialization
- `UnrealString.h` — FString format

---

## Phase 3: Blueprint Extraction

**Goal:** Detect blueprint assets and extract blueprint-specific metadata (variables, parent class, blueprint type).

**Requirements:** BLUE-01, BLUE-02, BLUE-03, BLUE-04, BLUE-05, BLUE-06

**Duration Estimate:** Medium (blueprint structures are known, extraction needs care)

### Success Criteria

1. **Given** a blueprint .uasset file, **When** parser detects asset type, **Then** asset is identified as Blueprint with correct blueprint type.
2. **Given** a blueprint export, **When** parser reads ParentClass, **Then** parent class name is resolved correctly.
3. **Given** a blueprint with variables, **When** parser extracts NewVariables, **Then** all variables have correct name, type, and default value.
4. **Given** variable types, **When** parser reads FEdGraphPinType, **Then** type string is human-readable (e.g., "Integer", "Object Reference").

### Key Work

- Blueprint type detection (class name contains "Blueprint" or package path pattern)
- Parent class resolution (ParentClass FPackageIndex → ImportMap or ExportMap)
- Blueprint type extraction (BlueprintType enum)
- Variable definitions parsing (FBPVariableDescription array)
- FEdGraphPinType interpretation (PinCategory, PinSubCategory, ContainerType)
- Variable metadata extraction (Category, PropertyFlags, MetaDataArray)

### Dependencies

- Phase 1 (needs PackageFileSummary, NameMap, ExportMap, ImportMap)
- Phase 2 (needs property parsing for variable values)

### Risks

- **Blueprint serialization variants:** Different blueprint types may have different structures
- **Variable type complexity:** FEdGraphPinType has many variants (Array, Map, Set, Reference, Const)
- **Default value parsing:** DefaultValue stored as string may need conversion

### UE Source References

- `Blueprint.h` — Blueprint structure
- `EdGraphPin.h` — FEdGraphPinType
- `K2Node.h` — Node hierarchy (for type detection)

---

## Phase 4: Output & CLI

**Goal:** Produce JSON and text output formats; implement command-line interface for tool execution.

**Requirements:** OUT-01, OUT-02, OUT-03, OUT-04, OUT-05, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06

**Duration Estimate:** Medium (output format design, CLI argument handling)

### Success Criteria

1. **Given** parsed asset data, **When** output formatter generates JSON, **Then** JSON is valid, hierarchical, and contains all parsed data.
2. **Given** parsed asset data, **When** output formatter generates text, **Then** text is human-readable with semantic descriptions.
3. **Given** blueprint data, **When** JSON output is generated, **Then** structure follows Package → Exports → Properties → Variables hierarchy.
4. **Given** CLI arguments, **When** tool runs with --json flag, **Then** JSON output is written to stdout.

### Key Work

- JSON output formatter (dataclasses.asdict + json.dumps)
- Text output formatter (semantic descriptions, not raw data)
- Summary output formatter (condensed overview)
- Hierarchical structure design (Package → Exports → Properties)
- Reference resolution in output (FPackageIndex → resolved name)
- CLI argument parsing (argparse)
- Output format flags (--json, --text, --summary)
- Error handling and exit codes
- Single-file execution support

### Dependencies

- Phase 1 (needs PackageFileSummary, NameMap, ExportMap)
- Phase 2 (needs property data)
- Phase 3 (needs blueprint data)

### Risks

- **Output size:** Large assets may produce huge JSON; need summary format
- **Missing data handling:** Unresolved references need null markers
- **CLI ergonomics:** Need clear help text and error messages

---

## Phase 5: Polish & Safety

**Goal:** Optimize for large files, add comprehensive error handling, implement safety checks.

**Requirements:** SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05

**Duration Estimate:** Medium (performance tuning, edge case handling)

### Success Criteria

1. **Given** a .uasset file > 50MB, **When** parser reads file, **Then** memory usage is bounded (mmap used, not full read).
2. **Given** a file with invalid offset, **When** parser attempts to seek, **Then** error is caught and partial results returned.
3. **Given** a corrupted/truncated file, **When** parser reads, **Then** parser returns error without hanging or crashing.

### Key Work

- Memory-mapped archive (FMappedArchive for large files)
- File size validation before reading offsets
- Offset bounds checking before seeking
- Partial results on recoverable errors
- Timeout or size limits for safety
- Comprehensive error messages
- Edge case handling (truncated files, corrupted sections)

### Dependencies

- Phase 1 (needs FArchive base class)
- Phase 2 (needs property parsing)
- Phase 3 (needs blueprint extraction)
- Phase 4 (needs output handling)

### Risks

- **Memory limit edge cases:** mmap may fail on very large files or certain platforms
- **Error recovery complexity:** Many edge cases need specific handling
- **Performance vs correctness:** mmap is fast but needs careful position tracking

---

## Milestone Summary

| Milestone | Phases | Deliverable |
|-----------|--------|-------------|
| **v1.0** | 1-5 | Complete Python .uasset parser with blueprint extraction, JSON/text output, CLI |

---

## Requirement Coverage

| Category | Total | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|----------|-------|---------|---------|---------|---------|---------|
| Core Parsing | 8 | 8 | - | - | - | - |
| Property Parsing | 9 | - | 9 | - | - | - |
| Blueprint Extraction | 6 | - | - | 6 | - | - |
| Output Formats | 5 | - | - | - | 5 | - |
| CLI & Execution | 6 | - | - | - | 6 | - |
| Performance & Safety | 5 | - | - | - | - | 5 |
| **Total** | 37 | 8 | 9 | 6 | 11 | 5 |

---

## Notes

- Research files in `.planning/research/` provide detailed context for each phase
- UE 5.7 source at `D:/Program Files/Epic Games/Engine/UE_5.7` is authoritative reference
- Focus on uncooked/editor-saved assets (cooked assets have stripped editor data)
- Blueprint graph extraction (Phase 4 in research) deferred to v2 due to complexity

---
*Roadmap created: 2026-04-27*
*Last updated: 2026-04-27 after initial creation*