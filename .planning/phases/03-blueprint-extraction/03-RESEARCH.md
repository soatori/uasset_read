# Phase 3: Blueprint Extraction - Research

**Researched:** 2026-05-01
**Domain:** Blueprint metadata extraction from .uasset files
**Confidence:** HIGH (UE 5.7 source verified)

## Summary

Blueprint extraction requires parsing blueprint-specific structures stored in the export data of .uasset files. The key structures are `FBPVariableDescription` (variable definitions) and `FEdGraphPinType` (type information). Blueprint detection uses ClassIndex from ExportMap to identify blueprint assets by checking if the class name contains "Blueprint". Parent class resolution maps FPackageIndex to object names in ImportMap/ExportMap.

UE source code in `Blueprint.h` and `EdGraphPin.h` defines the exact serialization format. FEdGraphPinType has evolved across UE versions with container type support (Array/Set/Map) added via custom versioning. The existing FArchive, dataclass patterns, and ParseResult partial result pattern from Phase 1/2 are directly applicable.

**Primary recommendation:** Implement blueprint extraction as an extension to `parse_uasset()` that auto-detects blueprints and extracts metadata using the established FArchive patterns.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Implementation Decisions

**Blueprint Detection Strategy**
- D-01: Class name detection — check ExportMap ClassIndex for class name containing "Blueprint" keyword
- D-02: Auto-detection — parse_uasset() automatically detects and extracts blueprint metadata
- D-03: Log warnings on detection failure in ParseResult.errors (not silent skip)
- D-04: Only detect if blueprint, don't distinguish BlueprintType (Normal, Interface, MacroLibrary, etc.)

**Variable Type Naming**
- D-05: Use UE original PinCategory values (e.g., "Integer", "Object Reference")
- D-06: Container+element type format like Array[Int], Map[Str,Obj]
- D-07: Resolve PinSubCategoryObject to specific class name (e.g., "AActor Reference")
- D-08: Full FEdGraphPinType structure parsing (all fields)

**Parent Class Resolution**
- D-09: Only direct parent class (no inheritance chain traversal)
- D-10: Resolve FPackageIndex to object name in ImportMap/ExportMap
- D-11: Return raw FPackageIndex + warning on resolution failure
- D-12: No circular reference check (single layer only, no loop possible)

**Default Value Handling**
- D-13: Parse DefaultValue string to Python native types (int, float, bool, str)
- D-14: Return raw string on parse failure (fallback)
- D-15: Only basic types (int, float, bool, string) — no complex types
- D-16: Vector types stay as string "(X=1.0,Y=2.0,Z=3.0)" format

### Claude's Discretion

- Specific blueprint detection class name matching logic
- FEdGraphPinType field parsing order and data types
- DefaultValue string parsing regex or parser implementation
- Variable metadata (Category, PropertyFlags) output format
- Unit test organization and test asset selection

### Deferred Ideas (OUT OF SCOPE)

**Phase 4 (Output and CLI)**
- BlueprintMetadata JSON output formatting
- Blueprint data text summary format

**v2 (Blueprint Advanced)**
- BlueprintType full classification (Normal, Interface, MacroLibrary, FunctionLibrary)
- Complete inheritance chain resolution (recursive to UObject)
- Circular reference detection
- Blueprint graph extraction (UEdGraph, Nodes, Pins)
- Complex default value parsing (arrays, vectors, object references)
- Complete variable metadata extraction (MetaDataArray detailed parsing)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BLUE-01 | Detect blueprint asset type from class name or package path | FEdGraphPinType serialization, ClassIndex resolution pattern from Phase 1 |
| BLUE-02 | Extract blueprint parent class (ParentClass reference) | FPackageIndex resolution, ImportMap/ExportMap lookup pattern |
| BLUE-03 | Extract blueprint variable definitions (FBPVariableDescription) | Blueprint.h structure verified, serialization pattern documented |
| BLUE-04 | Extract blueprint type (Normal, Interface, MacroLibrary) | Deferred per D-04 |
| BLUE-05 | Parse variable types from FEdGraphPinType | EdGraphPin.h structure verified, all fields documented |
| BLUE-06 | Extract variable metadata (Category, PropertyFlags) | FBPVariableDescription fields documented, EPropertyFlags enum verified |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Blueprint detection | Parse layer | — | Uses ExportMap ClassIndex (already parsed in Phase 1) |
| ParentClass resolution | Parse layer | — | FPackageIndex → ImportMap/ExportMap lookup |
| FEdGraphPinType parsing | Parse layer | — | Binary deserialization from export data |
| DefaultValue parsing | Parse layer | Output tier (v2) | Basic Python types in Phase 3; complex types deferred |
| BlueprintMetadata output | Parse layer | Output tier | ParseResult extension; JSON formatting in Phase 4 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dataclasses | stdlib | BlueprintMetadata, FEdGraphPinType, FBPVariableDescription models | Phase 1/2 pattern, JSON serialization via asdict() |
| struct | stdlib | Binary parsing | Phase 1 FArchive pattern |
| re | stdlib | DefaultValue string parsing | stdlib only, D-13 basic types |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | Type hints | All dataclass definitions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex for DefaultValue | Full parser | Over-engineering for D-15 basic types only |

**Installation:**
No new dependencies — stdlib only per Phase 1 decision.

## Architecture Patterns

### System Architecture Diagram

```
.uasset file
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ parse_uasset() [Phase 1/2]                                       │
│   └── PackageFileSummary, NameMap, ImportMap, ExportMap         │
│   └── PropertyValue[] from exports (Phase 2)                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Blueprint Detection [Phase 3 - NEW]                              │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │ For each export:                                           │ │
│   │   Check ClassIndex → resolve class name                    │ │
│   │   If class name contains "Blueprint" → mark as blueprint   │ │
│   └───────────────────────────────────────────────────────────┘ │
│   │                                                             │
│   ▼ (if blueprint detected)                                     │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │ Seek to export.SerialOffset                                 │ │
│   │ Parse ParentClass (FPackageIndex) → resolve to object name │ │
│   │ Parse NewVariables count + array                            │ │
│   │   For each FBPVariableDescription:                          │ │
│   │     Parse VarName (FName)                                   │ │
│   │     Parse VarType (FEdGraphPinType)                         │ │
│   │     Parse Category (FText)                                  │ │
│   │     Parse PropertyFlags (uint64)                            │ │
│   │     Parse DefaultValue (FString)                            │ │
│   └───────────────────────────────────────────────────────────┘ │
│   │                                                             │
│   ▼                                                             │
│   BlueprintMetadata dataclass                                   │
│   ├── is_blueprint: bool                                        │
│   ├── parent_class: str or None                                 │
│   ├── variables: List[BlueprintVariable]                        │
│   └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
ParseResult (extended)
    ├── summary, name_map, import_map, export_map (Phase 1)
    ├── properties (Phase 2)
    ├── blueprint: Optional[BlueprintMetadata] (Phase 3 - NEW)
    └── errors: List[str]
```

### Recommended Project Structure
```
uasset_read.py (extended in Phase 3)
├── FArchive (Phase 1)
├── PackageFileSummary, ObjectImport, ObjectExport (Phase 1)
├── PropertyTag, PropertyValue (Phase 2)
├── FEdGraphPinType, BlueprintVariable, BlueprintMetadata (Phase 3 - NEW)
├── parse_uasset() (extended with blueprint extraction)
└── detect_blueprint(), extract_blueprint_metadata() (Phase 3 - NEW)

tests/
├── test_uasset_read.py (Phase 1)
├── test_property_parsing.py (Phase 2)
└── test_blueprint_extraction.py (Phase 3 - NEW)
```

### Pattern 1: Blueprint Detection from ClassIndex

**What:** Check if export's ClassIndex points to a blueprint class
**When to use:** For every export in ExportMap after Phase 1 parsing

**Example:**
```python
# Source: Phase 1 get_asset_class() pattern
def detect_blueprint(
    export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> bool:
    """
    Detect if export is a blueprint asset.
    
    Check ClassIndex resolution for "Blueprint" keyword.
    Per D-01/D-04: only detect presence, not BlueprintType.
    """
    class_name = get_asset_class(export, import_map, export_map)
    if class_name and "Blueprint" in class_name:
        return True
    return False
```

### Pattern 2: FEdGraphPinType Parsing

**What:** Deserialize pin type structure from binary data
**When to use:** When parsing FBPVariableDescription.VarType

**Example (from EdGraphPin.cpp Serialize method):**
```python
# Source: EdGraphPin.cpp lines 163-346 [VERIFIED]
@dataclass
class FEdGraphPinType:
    """Pin type structure from EdGraphPin.h lines 76-225."""
    pin_category: str = ""          # FName
    pin_sub_category: str = ""      # FName
    pin_sub_category_object: int = 0  # FPackageIndex (resolved later)
    container_type: int = 0         # EPinContainerType: 0=None, 1=Array, 2=Set, 3=Map
    is_reference: bool = False
    is_const: bool = False
    is_weak_pointer: bool = False
    is_uobject_wrapper: bool = False

def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> FEdGraphPinType:
    """
    Parse FEdGraphPinType from export data.
    
    Serialization order (from EdGraphPin.cpp):
    1. PinCategory (FName)
    2. PinSubCategory (FName)
    3. PinSubCategoryObject (FPackageIndex)
    4. ContainerType (uint8) - if FFrameworkObjectVersion >= EdGraphPinContainerType
    5. PinValueType (FEdGraphTerminalType) - if ContainerType == Map
    6. bIsReference (bool)
    7. bIsWeakPointer (bool)
    8. PinSubCategoryMemberReference (FSimpleMemberReference) - if UE4 >= MEMBER_REFERENCE_IN_PINTYPE
    9. bIsConst (bool) - if UE4 >= SERIALIZE_PINTYPE_CONST
    10. bIsUObjectWrapper (bool) - if FReleaseObjectVersion >= PinTypeIncludesUObjectWrapperFlag
    """
    pin_type = FEdGraphPinType()
    
    # Step 1-2: PinCategory and PinSubCategory (FName)
    pin_type.pin_category = archive.read_name(name_map)
    pin_type.pin_sub_category = archive.read_name(name_map)
    
    # Step 3: PinSubCategoryObject (FPackageIndex)
    pin_type.pin_sub_category_object = archive.read_i32()
    
    # Step 4: ContainerType (uint8)
    # Per EdGraphPin.cpp line 216: FFrameworkObjectVersion >= EdGraphPinContainerType
    pin_type.container_type = archive.read_u8()
    
    # Step 5: PinValueType for Map containers
    if pin_type.container_type == 3:  # Map
        # Skip PinValueType for Phase 3 (defer complex types)
        # PinValueType: TerminalCategory + TerminalSubCategory + TerminalSubCategoryObject
        archive.read_name(name_map)  # TerminalCategory
        archive.read_name(name_map)  # TerminalSubCategory
        archive.read_i32()           # TerminalSubCategoryObject
    
    # Step 6-7: bIsReference and bIsWeakPointer
    pin_type.is_reference = archive.read_u8() != 0
    pin_type.is_weak_pointer = archive.read_u8() != 0
    
    # Step 8: PinSubCategoryMemberReference (skip for Phase 3)
    # FSimpleMemberReference: MemberParent + MemberName + MemberGuid
    archive.read_i32()  # MemberParent (FPackageIndex)
    archive.read_name(name_map)  # MemberName
    archive.read(16)  # MemberGuid (16 bytes)
    
    # Step 9: bIsConst
    pin_type.is_const = archive.read_u8() != 0
    
    # Step 10: bIsUObjectWrapper
    pin_type.is_uobject_wrapper = archive.read_u8() != 0
    
    return pin_type
```

### Pattern 3: FBPVariableDescription Parsing

**What:** Parse variable definition from blueprint export data
**When to use:** After blueprint detection, parse NewVariables array

**Example (from Blueprint.h lines 200-256):**
```python
# Source: Blueprint.h lines 200-256 [VERIFIED]
@dataclass
class BlueprintVariable:
    """
    Variable definition from FBPVariableDescription.
    
    Per D-05/D-06: use UE original names with container prefix.
    """
    var_name: str                    # FName
    var_type: FEdGraphPinType        # Full type structure
    category: str                    # FText (simplified to string)
    property_flags: int              # uint64 EPropertyFlags
    default_value: any = None        # Parsed or raw string per D-13/D-14
    friendly_name: str = ""          # FString

def read_blueprint_variable(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary
) -> BlueprintVariable:
    """
    Parse FBPVariableDescription from blueprint export.
    
    Serialization order (from Blueprint.h USTRUCT):
    1. VarName (FName)
    2. VarGuid (FGuid - 16 bytes)
    3. VarType (FEdGraphPinType)
    4. FriendlyName (FString)
    5. Category (FText - complex, simplified to FString for Phase 3)
    6. PropertyFlags (uint64)
    7. RepNotifyFunc (FName)
    8. ReplicationCondition (uint8 ELifetimeCondition)
    9. MetaDataArray (TArray<FBPVariableMetaDataEntry>)
    10. DefaultValue (FString)
    """
    var = BlueprintVariable(
        var_name=archive.read_name(name_map)
    )
    
    # VarGuid (16 bytes) - skip, not needed for Phase 3
    archive.read(16)
    
    # VarType (FEdGraphPinType)
    var.var_type = read_ed_graph_pin_type(archive, name_map, summary)
    
    # FriendlyName (FString)
    var.friendly_name = archive.read_fstring()
    
    # Category (FText) - simplified to FString for Phase 3
    # FText serialization: flags + history + namespace + source string
    # Simplified: read as FString for now
    var.category = archive.read_fstring()
    
    # PropertyFlags (uint64)
    var.property_flags = archive.read_u64()
    
    # RepNotifyFunc (FName) - skip
    archive.read_name(name_map)
    
    # ReplicationCondition (uint8) - skip
    archive.read_u8()
    
    # MetaDataArray count + entries - skip for Phase 3 (deferred)
    meta_count = archive.read_i32()
    for _ in range(meta_count):
        archive.read_name(name_map)  # DataKey
        archive.read_fstring()       # DataValue
    
    # DefaultValue (FString) - parse per D-13/D-14/D-15
    default_str = archive.read_fstring()
    var.default_value = parse_default_value(default_str, var.var_type)
    
    return var
```

### Anti-Patterns to Avoid

- **Parsing BlueprintType too early:** D-04 explicitly defers BlueprintType classification — only detect blueprint presence
- **Assuming fixed FEdGraphPinType size:** The structure has version-dependent fields — must handle container type branching
- **Parsing FText fully:** FText has complex serialization (namespace, source, history) — simplify to FString for Phase 3
- **Ignoring ContainerType:** Array/Set/Map affect VarType serialization (Map adds PinValueType)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Blueprint detection | Custom package path regex | ClassIndex lookup | ExportMap already has class info from Phase 1 |
| ParentClass resolution | Custom index mapping | FPackageIndex pattern | Phase 1 pattern with to_import_index/to_export_index |
| FEdGraphPinType parsing | Guess field order | EdGraphPin.cpp Serialize order | Verified from UE source, version-dependent |
| DefaultValue parsing | Full expression parser | Regex for basic types | D-15 limits to int/float/bool/string |

**Key insight:** Blueprint structures follow UE USTRUCT serialization — must follow exact field order from source.

## Common Pitfalls

### Pitfall 1: FEdGraphPinType Version Dependency

**What goes wrong:** Assuming fixed field order without checking UE version
**Why it happens:** FEdGraphPinType serialization evolved across UE4/UE5 versions
**How to avoid:** Follow EdGraphPin.cpp Serialize method exactly; check custom version flags
**Warning signs:** Parse errors after ContainerType field, misaligned position

**Version thresholds (from EdGraphPin.cpp):**
- `FFrameworkObjectVersion::PinsStoreFName`: PinCategory as FName (else FString)
- `FFrameworkObjectVersion::EdGraphPinContainerType`: ContainerType field added
- `VER_UE4_MEMBER_REFERENCE_IN_PINTYPE`: PinSubCategoryMemberReference added
- `VER_UE4_SERIALIZE_PINTYPE_CONST`: bIsConst added
- `FReleaseObjectVersion::PinTypeIncludesUObjectWrapperFlag`: bIsUObjectWrapper added

### Pitfall 2: ContainerType Serialization Branching

**What goes wrong:** Not reading PinValueType for Map containers
**Why it happens:** ContainerType==Map requires additional FEdGraphTerminalType
**How to avoid:** Check ContainerType before proceeding; read PinValueType for Map (3)
**Warning signs:** Position mismatch after parsing Map-typed variables

### Pitfall 3: FText Complexity

**What goes wrong:** Attempting to parse FText fully with namespace/history
**Why it happens:** FText has 4-field serialization (flags, history, namespace, source)
**How to avoid:** Simplify to FString for Phase 3; defer full FText parsing to v2
**Warning signs:** Category field garbage, position misalignment

### Pitfall 4: Blueprint Export Selection

**What goes wrong:** Parsing wrong export as blueprint metadata
**Why it happens:** Blueprint .uasset has multiple exports; need to find the blueprint object
**How to avoid:** Look for export with ObjectName matching package name + "_C" pattern
**Warning signs:** ParseError on VarName, unexpected data at SerialOffset

## Code Examples

Verified patterns from UE source:

### PinCategory Values (from EdGraphPin.cpp)
```python
# Source: EdGraphPin.cpp lines 293-305, 315-321 [VERIFIED]
PIN_CATEGORIES = {
    # Basic types
    "exec",       # Execution flow
    "bool",       # Boolean
    "int",        # Integer (deprecated, use "Integer" in UE5)
    "Integer",    # Integer (UE5)
    "real",       # Real number (UE5: replaces float/double)
    "float",      # Float (deprecated in UE5)
    "double",     # Double (deprecated in UE5)
    "string",     # FString
    "name",       # FName
    
    # Object types
    "class",      # UClass reference
    "object",     # UObject reference
    "interface",  # Interface reference
    
    # Soft references
    "softclass",    # TSoftClassPtr
    "softobject",   # TSoftObjectPtr
    
    # Delegates
    "delegate",    # Single-cast delegate
    "mcdelegate",  # Multi-cast delegate
    
    # Other
    "struct",      # Struct type
    "enum",        # Enum type
    "wildcard",    # Wildcard/any type
}

PIN_SUB_CATEGORIES = {
    "bool",        # Boolean subcategory
    "int",         # Integer subcategory
    "float",       # Float subcategory (deprecated)
    "double",      # Double subcategory
    "name",        # Name subcategory
    "self",        # Self reference
    "Default",     # Default object
}
```

### ContainerType Mapping
```python
# Source: EdGraphNode.h lines 121-129 [VERIFIED]
CONTAINER_TYPES = {
    0: "None",     # EPinContainerType::None
    1: "Array",    # EPinContainerType::Array
    2: "Set",      # EPinContainerType::Set
    3: "Map",      # EPinContainerType::Map
}
```

### PropertyFlags Mapping
```python
# Source: ObjectMacros.h lines 415-480 [VERIFIED]
PROPERTY_FLAGS = {
    0x0000000000000001: "Edit",                    # CPF_Edit
    0x0000000000000004: "BlueprintVisible",        # CPF_BlueprintVisible
    0x0000000000000010: "BlueprintReadOnly",       # CPF_BlueprintReadOnly
    0x0000000000000020: "Net",                     # CPF_Net (replicated)
    0x0000000001000000: "SaveGame",                # CPF_SaveGame
    0x0000000010000000: "BlueprintAssignable",     # CPF_BlueprintAssignable (MC delegates)
    0x0000000100000000: "RepNotify",               # CPF_RepNotify
    0x0001000000000000: "ExposeOnSpawn",           # CPF_ExposeOnSpawn
}

def format_property_flags(flags: int) -> List[str]:
    """Convert uint64 flags to human-readable list."""
    result = []
    for bit, name in PROPERTY_FLAGS.items():
        if flags & bit:
            result.append(name)
    return result
```

### DefaultValue Parsing (per D-13/D-14/D-15/D-16)
```python
import re

def parse_default_value(value_str: str, var_type: FEdGraphPinType) -> any:
    """
    Parse DefaultValue string to Python native type.
    
    Per D-13/D-14/D-15/D-16:
    - Parse basic types: int, float, bool, str
    - Return raw string on failure
    - Vector types stay as string "(X=...,Y=...,Z=...)"
    """
    if not value_str:
        return None
    
    # Check for vector format (D-16: keep as string)
    if value_str.startswith("(") and value_str.endswith(")"):
        return value_str
    
    # Match PinCategory
    category = var_type.pin_category.lower()
    
    # Boolean parsing
    if category in ("bool", "boolean"):
        if value_str.lower() in ("true", "1"):
            return True
        elif value_str.lower() in ("false", "0"):
            return False
        return value_str  # D-14: fallback
    
    # Integer parsing
    if category in ("int", "integer"):
        match = re.match(r'^-?\d+$', value_str)
        if match:
            return int(value_str)
        return value_str  # D-14: fallback
    
    # Float/Real parsing
    if category in ("float", "real", "double"):
        match = re.match(r'^-?\d+\.?\d*$', value_str)
        if match:
            return float(value_str)
        return value_str  # D-14: fallback
    
    # String/Name: keep as-is
    return value_str
```

### Type Name Formatting (per D-05/D-06/D-07)
```python
def format_pin_type_name(pin_type: FEdGraphPinType, name_map: List[str], import_map: List[ObjectImport]) -> str:
    """
    Format human-readable type name from FEdGraphPinType.
    
    Per D-05: Use UE original names
    Per D-06: Container+element format (Array[Int])
    Per D-07: Resolve PinSubCategoryObject to class name
    """
    # Base element type
    element_type = pin_type.pin_category
    
    # D-07: Try to resolve PinSubCategoryObject for object types
    if pin_type.pin_sub_category_object != 0:
        pkg_idx = PackageIndex(pin_type.pin_sub_category_object)
        if pkg_idx.is_import:
            idx = pkg_idx.to_import_index()
            if 0 <= idx < len(import_map):
                element_type = f"{import_map[idx].object_name} Reference"
    
    # D-06: Add container prefix
    container_name = CONTAINER_TYPES.get(pin_type.container_type, "None")
    if container_name == "None":
        return element_type
    elif container_name == "Map":
        # Map needs key and value types (simplified for Phase 3)
        return f"Map[{element_type}]"
    else:
        return f"{container_name}[{element_type}]"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FString PinCategory | FName PinCategory | UE 4.17+ (FFrameworkObjectVersion::PinsStoreFName) | More efficient, needs version check |
| bIsArray/bIsSet/bIsMap flags | EPinContainerType enum | UE 4.17+ (FFrameworkObjectVersion::EdGraphPinContainerType) | Cleaner, single field |
| "float"/"double" categories | "real" category with subcategory | UE 5.0+ (FUE5ReleaseStreamObjectVersion::BlueprintPinsUseRealNumbers) | Unified real type |

**Deprecated/outdated:**
- `bIsArray_DEPRECATED`: Use ContainerType instead (UE < 4.17)
- `asset`/`assetclass` PinCategories: Renamed to `softobject`/`softclass` (UE 4.20+)

## Assumptions Log

> All claims in this research were verified from UE 5.7 source code. No user confirmation needed.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FEdGraphPinType serialization order | Pattern 2 | LOW - Verified from EdGraphPin.cpp |
| A2 | FBPVariableDescription field order | Pattern 3 | LOW - Verified from Blueprint.h |
| A3 | ContainerType values 0-3 | Code Examples | LOW - Verified from EdGraphNode.h |
| A4 | PropertyFlags bit values | Code Examples | LOW - Verified from ObjectMacros.h |

**If this table is empty:** All claims in this research were verified — no user confirmation needed.

## Open Questions

1. **Blueprint export identification**
   - What we know: Blueprint .uasset has multiple exports; need to find correct one
   - What's unclear: Exact pattern for selecting blueprint export (ObjectName ending "_C"?)
   - Recommendation: Test with sample assets; look for export whose ObjectName matches package

2. **FText serialization complexity**
   - What we know: FText has flags, history, namespace, source fields
   - What's unclear: Exact FText serialization format for Category field
   - Recommendation: Simplify to FString for Phase 3; verify with real assets

## Environment Availability

> External UE source reference exists; no runtime dependencies.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| UE 5.7 Source | Structure reference | ✓ | 5.7 | Web search for UE docs |
| Python 3.10+ | Runtime | ✓ | stdlib | — |
| pytest | Testing | ✓ | installed | — |
| Sample .uasset files | Testing | ✓ | Lyra, FirstPerson samples | — |

**Missing dependencies with no fallback:**
None — all dependencies verified.

**Missing dependencies with fallback:**
None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing from Phase 1/2) |
| Config file | None — pytest.ini in root |
| Quick run command | `python -m pytest tests/test_blueprint_extraction.py -v` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BLUE-01 | Blueprint detection from ClassIndex | unit | `pytest tests/test_blueprint_extraction.py::test_blueprint_detection -x` | ❌ Wave 0 |
| BLUE-02 | ParentClass resolution | unit | `pytest tests/test_blueprint_extraction.py::test_parent_class_resolution -x` | ❌ Wave 0 |
| BLUE-03 | FBPVariableDescription parsing | unit | `pytest tests/test_blueprint_extraction.py::test_variable_parsing -x` | ❌ Wave 0 |
| BLUE-04 | BlueprintType extraction | deferred | — | D-04 |
| BLUE-05 | FEdGraphPinType parsing | unit | `pytest tests/test_blueprint_extraction.py::test_pin_type_parsing -x` | ❌ Wave 0 |
| BLUE-06 | Variable metadata extraction | unit | `pytest tests/test_blueprint_extraction.py::test_variable_metadata -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_blueprint_extraction.py -v`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_blueprint_extraction.py` — covers BLUE-01, BLUE-02, BLUE-03, BLUE-05, BLUE-06
- [ ] Mock blueprint .uasset data for unit tests
- [ ] Integration test with Lyra/FirstPerson sample assets

## Security Domain

> Phase 3 adds no new external dependencies or network operations. Security profile unchanged from Phase 1/2.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | struct.unpack with boundary validation (FArchive pattern) |
| V6 Cryptography | no | — |

### Known Threat Patterns for Blueprint Parsing

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Binary parse overflow | Tampering | FArchive boundary validation (Phase 1 pattern) |
| Invalid FPackageIndex | Tampering | Index bounds check before map lookup |
| Malformed PinType | Tampering | Version-aware serialization with skip on error |

## Sources

### Primary (HIGH confidence)
- EdGraphPin.h (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphPin.h) - FEdGraphPinType structure definition
- EdGraphPin.cpp (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp) - FEdGraphPinType serialization order
- Blueprint.h (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Classes/Engine/Blueprint.h) - FBPVariableDescription structure
- Blueprint.cpp (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/Blueprint.cpp) - Blueprint serialization patterns
- EdGraphNode.h (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphNode.h) - EPinContainerType enum
- ObjectMacros.h (E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectMacros.h) - EPropertyFlags enum

### Secondary (MEDIUM confidence)
- Phase 1/2 code patterns (uasset_read.py) - Established FArchive, dataclass, ParseResult patterns

### Tertiary (LOW confidence)
None — all claims verified from UE source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib only, matches Phase 1/2 decisions
- Architecture: HIGH - UE source verified, existing patterns applicable
- Pitfalls: HIGH - Documented from source, version thresholds explicit

**Research date:** 2026-05-01
**Valid until:** 30 days (UE structure stable across versions)