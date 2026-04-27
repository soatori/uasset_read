# Requirements: uasset_read

**Defined:** 2026-04-27
**Core Value:** 让 AI agent 能直接读取 .uasset 文件内容，无需人工介入 UE 编辑器

## v1 Requirements

### Core Parsing

- [ ] **CORE-01**: Parser can read .uasset file header (PackageFileSummary) with magic tag, version info, and section offsets
- [ ] **CORE-02**: Parser detects endianness from magic tag and enables byte swapping when needed
- [ ] **CORE-03**: Parser extracts name table (NameMap) from NameOffset/NameCount
- [ ] **CORE-04**: Parser extracts import map (external dependencies) from ImportOffset
- [ ] **CORE-05**: Parser extracts export map (internal objects) from ExportOffset
- [ ] **CORE-06**: Parser identifies asset type/class from export ClassIndex
- [ ] **CORE-07**: Parser handles UE4/UE5 version numbers and custom version GUIDs
- [ ] **CORE-08**: Parser fails gracefully with clear error message on unsupported versions

### Property Parsing

- [ ] **PROP-01**: Parser reads PropertyTag structure (name, type, size, flags)
- [ ] **PROP-02**: Parser extracts IntProperty values (int32, int64)
- [ ] **PROP-03**: Parser extracts FloatProperty values (float, double)
- [ ] **PROP-04**: Parser extracts BoolProperty values
- [ ] **PROP-05**: Parser extracts StrProperty values (FString with length prefix)
- [ ] **PROP-06**: Parser extracts NameProperty values (FName resolved from NameMap)
- [ ] **PROP-07**: Parser extracts ObjectProperty values (FPackageIndex reference)
- [ ] **PROP-08**: Parser extracts ArrayProperty values (nested element parsing)
- [ ] **PROP-09**: Parser handles PropertyTag flags (HasPropertyGuid, HasPropertyExtensions)

### Blueprint Extraction

- [ ] **BLUE-01**: Parser detects Blueprint asset type from class name or package path
- [ ] **BLUE-02**: Parser extracts blueprint parent class (ParentClass reference)
- [ ] **BLUE-03**: Parser extracts blueprint variable definitions (FBPVariableDescription: name, type, default)
- [ ] **BLUE-04**: Parser extracts blueprint type (Normal, Interface, MacroLibrary)
- [ ] **BLUE-05**: Parser resolves variable types from FEdGraphPinType
- [ ] **BLUE-06**: Parser extracts variable metadata (Category, PropertyFlags)

### Output Formats

- [ ] **OUT-01**: Parser outputs structured JSON with full asset data
- [ ] **OUT-02**: Parser outputs human-readable text summary
- [ ] **OUT-03**: JSON output follows hierarchical structure (Package → Exports → Properties)
- [ ] **OUT-04**: Output includes resolved references (not raw indices)
- [ ] **OUT-05**: Output handles missing/unresolved data gracefully (null markers)

### CLI & Execution

- [ ] **CLI-01**: Tool accepts single .uasset file path as argument
- [ ] **CLI-02**: Tool supports --json flag for JSON output
- [ ] **CLI-03**: Tool supports --text flag for text output
- [ ] **CLI-04**: Tool supports --summary flag for condensed output
- [ ] **CLI-05**: Tool exits with error code and message on parse failure
- [ ] **CLI-06**: Tool runs without external dependencies (Python stdlib only)

### Performance & Safety

- [ ] **SAFE-01**: Parser validates file size before reading offsets
- [ ] **SAFE-02**: Parser checks offset bounds before seeking
- [ ] **SAFE-03**: Parser uses memory-mapped access for files > 50MB
- [ ] **SAFE-04**: Parser returns partial results on recoverable errors
- [ ] **SAFE-05**: Parser never hangs on invalid/corrupted files (timeout or size limits)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Blueprint Graphs (Advanced)

- **GRAPH-01**: Parser extracts blueprint graph structure (UEdGraph: Nodes, Schema)
- **GRAPH-02**: Parser identifies node types (UK2Node subclasses: CallFunction, VariableGet, Event, etc.)
- **GRAPH-03**: Parser extracts node pins (UEdGraphPin: Name, Direction, Type, DefaultValue)
- **GRAPH-04**: Parser maps pin connections (LinkedTo array → source-to-destination)
- **GRAPH-05**: Parser generates semantic node descriptions ("Calls function X", "Gets variable Y")
- **GRAPH-06**: Parser extracts function graphs (FunctionGraphs array)
- **GRAPH-07**: Parser extracts event graphs (UbergraphPages array)

### Advanced Properties

- **ADVP-01**: Parser extracts StructProperty values (nested struct parsing)
- **ADVP-02**: Parser extracts MapProperty values (key-value pairs)
- **ADVP-03**: Parser extracts SetProperty values (unique element set)
- **ADVP-04**: Parser extracts EnumProperty values (enum name + value)
- **ADVP-05**: Parser extracts TextProperty values (FText with locale)
- **ADVP-06**: Parser extracts DelegateProperty values (function references)

### Dependency Analysis

- **DEPS-01**: Parser builds full dependency graph from ImportMap + SoftObjectPaths
- **DEPS-02**: Parser outputs dependency list with package paths
- **DEPS-03**: Parser identifies circular dependencies

### Other Asset Types

- **TYPE-01**: Parser handles Material assets (basic property extraction)
- **TYPE-02**: Parser handles Texture assets (metadata only, no binary data)
- **TYPE-03**: Parser handles .umap files (level packages)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Binary asset export | Out of scope per PROJECT.md; textures/models are complex binary formats |
| Asset modification/writing | Out of scope per PROJECT.md; read-only parsing only |
| Blueprint bytecode decompilation | Compiled blueprints use different format; focus on editor-saved assets |
| Pak file extraction | Different domain; .pak is archive format, not asset format |
| Real-time parsing/monitoring | Out of scope per PROJECT.md; single-file parsing only |
| UE Editor integration | Out of scope per PROJECT.md; standalone Python tool |
| Cooked asset parsing | Cooked assets have stripped editor data; different serialization format |
| Asset preview/visualization | Complex UI work; AI agents don't need visual preview |
| Asset conversion/transcoding | Different domain; read and output structure, not convert formats |
| Custom property type handlers | Game-specific custom types require game-specific knowledge |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Pending |
| CORE-02 | Phase 1 | Pending |
| CORE-03 | Phase 1 | Pending |
| CORE-04 | Phase 1 | Pending |
| CORE-05 | Phase 1 | Pending |
| CORE-06 | Phase 1 | Pending |
| CORE-07 | Phase 1 | Pending |
| CORE-08 | Phase 1 | Pending |
| PROP-01 | Phase 2 | Pending |
| PROP-02 | Phase 2 | Pending |
| PROP-03 | Phase 2 | Pending |
| PROP-04 | Phase 2 | Pending |
| PROP-05 | Phase 2 | Pending |
| PROP-06 | Phase 2 | Pending |
| PROP-07 | Phase 2 | Pending |
| PROP-08 | Phase 2 | Pending |
| PROP-09 | Phase 2 | Pending |
| BLUE-01 | Phase 3 | Pending |
| BLUE-02 | Phase 3 | Pending |
| BLUE-03 | Phase 3 | Pending |
| BLUE-04 | Phase 3 | Pending |
| BLUE-05 | Phase 3 | Pending |
| BLUE-06 | Phase 3 | Pending |
| OUT-01 | Phase 4 | Pending |
| OUT-02 | Phase 4 | Pending |
| OUT-03 | Phase 4 | Pending |
| OUT-04 | Phase 4 | Pending |
| OUT-05 | Phase 4 | Pending |
| CLI-01 | Phase 4 | Pending |
| CLI-02 | Phase 4 | Pending |
| CLI-03 | Phase 4 | Pending |
| CLI-04 | Phase 4 | Pending |
| CLI-05 | Phase 4 | Pending |
| CLI-06 | Phase 4 | Pending |
| SAFE-01 | Phase 5 | Pending |
| SAFE-02 | Phase 5 | Pending |
| SAFE-03 | Phase 5 | Pending |
| SAFE-04 | Phase 5 | Pending |
| SAFE-05 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-27*
*Last updated: 2026-04-27 after initial definition*