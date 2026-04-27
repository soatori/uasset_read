# Phase 1: Core Parsing - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Parse .uasset file header, name table, import map, and export map; identify asset structure and type. This phase delivers the foundation layer that all subsequent phases depend on.

**Fixed scope (from ROADMAP.md):**
- PackageFileSummary header parsing
- Name table extraction (NameMap)
- Import map parsing (FObjectImport)
- Export map parsing (FObjectExport)
- Asset class identification from ClassIndex
- Version handling (UE4/UE5/Custom versions)
- Error handling framework

</domain>

<decisions>
## Implementation Decisions

### Architecture Design
- **D-01:** Single FArchive class — all read methods in one class (not layered FArchive + FileReader + MemoryReader)
- **D-02:** Phase 1 single-file implementation; Phase 5 adds MappedArchive for large file support
- **Rationale:** Simpler for initial implementation, matches zero-dependency philosophy

### Version Support
- **D-03:** UE 5.x only — focus on UE 5.x format (stable, matches UE 5.7 source reference)
- **D-04:** Strict version validation with clear error messages — UE5 version >= 1000, LegacyFileVersion in [-2, -9]
- **D-05:** Custom Versions GUID — read and store, but no validation of specific subsystem versions
- **Rationale:** Reduces initial complexity; UE 5.x format aligns with source reference at D:/Program Files/Epic Games/Engine/UE_5.7

### Data Model
- **D-06:** Use dataclasses for all parsed structures (PackageFileSummary, ObjectImport, ObjectExport, etc.)
- **D-07:** PackageIndex stored as raw signed int32 — delayed resolution (Phase 1 stores indices, Phase 3+ resolves names)
- **Rationale:** Python 3.10+ native dataclasses, asdict() → JSON directly; delayed resolution keeps Phase 1 focused

### Header Parsing
- **D-08:** Read ALL PackageFileSummary fields — complete header for downstream phases
- **D-09:** Name Table format — version-adaptive (handle both UTF-8 and FNameEntry structure variants)
- **D-10:** FString encoding — UTF-8 only (UE 5.x standard)
- **D-11:** Endianness detection via Magic Tag — compare first u32 against PACKAGE_FILE_TAG (0x9E2A83C1) and PACKAGE_FILE_TAG_SWAPPED (0xC1832A9E)
- **D-12:** PackageFlags — store raw value only (no flag interpretation in Phase 1)
- **Rationale:** Complete header enables all downstream phases; UTF-8 simplifies string handling

### BulkData Handling
- **D-13:** Skip BulkData in Phase 1 — no embedded payload parsing
- **Rationale:** BulkData is complex; defer to later phases or v2

### Error Handling
- **D-14:** Validate offsets/sizes before seeking — return partial results with error info on recoverable errors
- **D-15:** Never crash on invalid/corrupted files — graceful degradation
- **Rationale:** Matches SAFE-04 requirement; AI agents need partial data, not exceptions

### Testing Strategy
- **D-16:** Combined approach — unit tests with synthetic data + integration tests with real .uasset
- **D-17:** Integration test samples provided by user — user has UE environment for sample files
- **Rationale:** Synthetic data validates edge cases; real files validate actual format

### File Layout
- **D-18:** Progressive split — Phase 1 single file, later phases can modularize
- **Rationale:** Start simple; refactor when needed

### Claude's Discretion
- Exact struct.unpack format strings
- FArchive method naming conventions
- Error message format and detail level
- Unit test organization

</decisions>

<specifics>
## Specific Ideas

- "让 AI agent 能直接读取 .uasset 文件内容，无需人工介入 UE 编辑器" — core value from PROJECT.md
- UE 5.7 source at `D:/Program Files/Epic Games/Engine/UE_5.7` is authoritative reference
- Focus on uncooked/editor-saved assets (full blueprint data available)

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UE Source Reference
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` — Header structure, all fields, offsets
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h` — Import/Export structures, FPackageIndex encoding
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/Serialization/Archive.h` — FArchive pattern reference

### Project Planning
- `.planning/PROJECT.md` — Project context, core value, constraints
- `.planning/REQUIREMENTS.md` — CORE-01 through CORE-08 requirements
- `.planning/ROADMAP.md` — Phase 1 success criteria, key work, risks
- `.planning/research/STACK.md` — Python stack decisions, struct/mmap patterns
- `.planning/research/ARCHITECTURE.md` — Layered pipeline pattern, FArchive implementation example
- `.planning/research/PITFALLS.md` — Critical pitfalls (endianness, version, offsets, FName)

</canonical_refs>

<code_context>
## Existing Code Insights

### No Existing Project Code
This is a new project. No reusable assets exist yet.

### UE Source Patterns
- FArchive pattern with read_u8, read_u32, read_fstring, read_name methods
- PackageFileSummary structure with NameOffset, ExportOffset, ImportOffset
- FPackageIndex signed encoding: >0 export, <0 import, 0 null
- FName = index into NameMap + instance number

### External References
- CUE4Parse (C#): Handler registry pattern, version-aware parsing
- FModel: Layered architecture, output formatters

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

**Future phases will handle:**
- Property parsing (Phase 2)
- Blueprint extraction (Phase 3)
- Output formatters (Phase 4)
- Performance/mmap (Phase 5)

</deferred>

---

*Phase: 01-core-parsing*
*Context gathered: 2026-04-28*