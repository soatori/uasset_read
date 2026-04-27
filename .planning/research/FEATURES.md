# Feature Landscape

**Domain:** Unreal Engine .uasset file parsing for AI agent consumption
**Researched:** 2026-04-27

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Parse .uasset header** | Required to identify file structure, version, and offsets | Low | FPackageFileSummary contains magic tag, version info, offsets to name/import/export tables |
| **Extract name table** | All object/property names reference this table; fundamental for interpreting any data | Low | NameCount + NameOffset in header; name entries are FName with number index |
| **Extract export map** | Lists all objects defined within this package (blueprints, graphs, nodes) | Low | FObjectExport: ObjectName, ClassIndex, OuterIndex, SerialOffset, SerialSize |
| **Extract import map** | Lists external dependencies (other packages this asset references) | Low | FObjectImport: ObjectName, ClassName, ClassPackage - critical for understanding asset dependencies |
| **Identify asset class/type** | User needs to know what kind of asset they're reading | Medium | ClassIndex in export map points to asset class (Blueprint, Material, Texture, etc.) |
| **Extract basic property values** | Assets contain data - integers, floats, strings, bools, arrays must be readable | Medium | FPropertyTag + FEdGraphPinType define value types; DefaultValue stored as string |
| **JSON output format** | Standard structured output for programmatic consumption | Low | Core requirement per PROJECT.md |
| **Human-readable text output** | User/AI needs to understand content without deep UE knowledge | Medium | Core requirement per PROJECT.md; semantic descriptions, not raw data |
| **Single-file parsing** | Must read one .uasset without requiring full project context | Low | Per PROJECT.md constraint; cannot require UE editor or pak extraction |
| **Version identification** | UE versions differ; must know what version file was saved with | Low | FileVersionUE + FileVersionLicenseeUE in header; determines serialization format |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Blueprint graph extraction** | AI agents need to understand blueprint logic - nodes, connections, flow | High | UEdGraph contains Nodes array; each UK2Node has Pins with LinkedTo connections. Critical for understanding blueprint behavior. |
| **Variable definitions extraction** | Know what data blueprint stores - names, types, defaults, metadata | Medium | FBPVariableDescription in Blueprint: VarName, VarType (FEdGraphPinType), DefaultValue, MetaDataArray, PropertyFlags |
| **Function definitions extraction** | Know what functions blueprint exposes - name, parameters, return type | High | FunctionGraphs array in Blueprint; UEdGraph with nodes representing function signature |
| **Reference dependency graph** | AI needs to know what other assets this asset uses/depends on | Medium | ImportMap + SoftObjectPathsCount; combine with property values that reference external assets |
| **Property type interpretation** | AI needs semantic understanding of types (not just "IntProperty" but "integer") | Medium | FEdGraphPinType: PinCategory, PinSubCategory, ContainerType (Array/Set/Map), bIsReference, bIsConst |
| **Node type identification** | AI needs to know what each blueprint node does | High | UK2Node class hierarchy - K2Node_CallFunction, K2Node_VariableGet, K2Node_Event, etc. Each has specific data fields. |
| **Pin connection mapping** | AI needs to trace data flow through blueprint | Medium | UEdGraphPin.LinkedTo array connects output pins to input pins; trace execution/data flow |
| **Hierarchical structure output** | Package -> Exports -> Graphs -> Nodes -> Pins - nested JSON for clarity | Medium | Matches UE's object hierarchy; AI can navigate logically |
| **Error recovery & partial parsing** | If unknown property type encountered, continue parsing and flag it | High | UE has many property types; some may be version-specific or custom. Cannot fail entire parse on one unknown type. |
| **Semantic node descriptions** | Instead of raw node class, output human-readable description ("Calls function X") | High | Requires understanding node semantics; e.g., K2Node_CallFunction with FunctionReference -> "Calls [FunctionName]" |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Binary asset export** | Out of scope per PROJECT.md; textures/models are complex binary formats that require specialized handling | Focus on structured data extraction; let dedicated tools handle binary exports |
| **Asset modification/writing** | Out of scope per PROJECT.md; modifying .uasset requires understanding of serialization, cooking, dependencies - extremely complex | Read-only parsing only |
| **Blueprint bytecode decompilation** | Compiled blueprints use Kismet VM bytecode; decompilation is extremely complex and not needed for reading editor-saved assets | Focus on extracting editor-time graph data (UEdGraph/UK2Node) from uncooked assets |
| **Pak file extraction** | Different domain; .pak is an archive format, not asset format | User provides extracted .uasset; pak extraction is separate problem (u4pak handles this) |
| **Real-time parsing/monitoring** | Out of scope per PROJECT.md; adds complexity without core value | Single-file parse with clear output |
| **UE Editor integration** | Out of scope per PROJECT.md; would require running UE, not standalone Python | Standalone Python tool, no UE dependency |
| **Asset preview/visualization** | Complex UI work; AI agents don't need visual preview | Structured text/JSON output only |
| **Asset conversion/transcoding** | Different domain; converting UE assets to other formats requires understanding target formats | Read and output structure, not convert |
| **Cooked asset parsing** | Cooked assets have stripped editor data; different serialization format | Focus on uncooked/editor-saved assets which contain full graph data |
| **Custom property type handlers** | Game-specific custom property types require game-specific knowledge | Generic handling; flag unknown types rather than try to interpret |

## Feature Dependencies

```
Parse Header
  |-- Extract Name Table (requires header offsets)
  |-- Extract Export Map (requires header offsets)
  |-- Extract Import Map (requires header offsets)

Extract Export Map
  |-- Identify Asset Class (requires ClassIndex resolution via Import/Export)
  |-- Parse Export Data (requires SerialOffset + SerialSize)

Parse Export Data
  |-- Extract Properties (requires property type knowledge)
  |-- Extract Blueprint Graphs (if asset is Blueprint)
      |-- Extract Nodes (requires UEdGraph.Nodes)
          |-- Extract Node Pins (requires UK2Node.Pins)
              |-- Map Pin Connections (requires LinkedTo)

Blueprint-specific extraction:
  |-- Variables (FBPVariableDescription)
  |-- Functions (FunctionGraphs)
  |-- Event Graphs (UbergraphPages)
  |-- Interfaces (ImplementedInterfaces)
```

## MVP Recommendation

Prioritize:
1. **Parse .uasset header** - Entry point for all parsing
2. **Extract name/import/export tables** - Foundation for understanding content
3. **Identify asset class** - Determines what extraction path to take
4. **JSON output format** - Core output requirement
5. **Blueprint type detection** - Know if file contains blueprint data
6. **Variable definitions extraction** - Most valuable blueprint data, moderate complexity

Defer to Phase 2:
- **Blueprint graph extraction** - High complexity, requires deep node/pin understanding
- **Function definitions** - High complexity, needs graph parsing foundation
- **Semantic node descriptions** - Requires node type catalog

Defer to Phase 3:
- **Error recovery & partial parsing** - Requires handling many edge cases
- **Pin connection mapping** - Requires full graph parsing

## Data Structure Reference

Key structures discovered from UE 5.7 source:

### Package File Summary (Header)
- `FPackageFileSummary` in `PackageFileSummary.h`
- Contains: Tag (magic), FileVersionUE, NameCount/Offset, ExportCount/Offset, ImportCount/Offset, PackageFlags

### Name Table Entry
- Each name: FName (string + number index for disambiguation)
- All object/property names come from this table

### Export Map Entry
- `FObjectExport`: ObjectName, ClassIndex, OuterIndex, SuperIndex, TemplateIndex, ObjectFlags, SerialSize, SerialOffset

### Import Map Entry
- `FObjectImport`: ObjectName, ClassPackage, ClassName, OuterIndex

### Blueprint Structure
- `UBlueprint` in `Blueprint.h`
- Key fields:
  - `ParentClass` - What class this blueprint extends
  - `BlueprintType` - BPTYPE_Normal, Interface, MacroLibrary, etc.
  - `NewVariables` - TArray<FBPVariableDescription>
  - `FunctionGraphs` - TArray<UEdGraph>
  - `UbergraphPages` - TArray<UEdGraph> (event graphs)
  - `ImplementedInterfaces` - TArray<FBPInterfaceDescription>
  - `ComponentTemplates` - TArray<UActorComponent>

### Variable Definition
- `FBPVariableDescription`: VarName, VarGuid, VarType, FriendlyName, Category, PropertyFlags, DefaultValue, MetaDataArray

### Graph Structure
- `UEdGraph`: Schema, Nodes (TArray<UEdGraphNode>), GraphGuid, bEditable
- `UEdGraphNode`: Pins, NodePosX/Y, NodeComment, NodeGuid, EnabledState

### Node Structure
- `UK2Node` (extends UEdGraphNode): Base class for all blueprint nodes
- Subclasses: K2Node_CallFunction, K2Node_VariableGet, K2Node_Event, K2Node_MacroInstance, etc.

### Pin Structure
- `UEdGraphPin`: PinId, PinName, Direction, PinType, DefaultValue, LinkedTo (connections), SubPins, ParentPin
- `FEdGraphPinType`: PinCategory, PinSubCategory, ContainerType (None/Array/Set/Map), bIsReference, bIsConst

### Property Types (FPropertyTag.Type)
- BoolProperty, IntProperty, FloatProperty, StrProperty, NameProperty
- ObjectProperty, ClassProperty, StructProperty, ArrayProperty
- MapProperty, SetProperty, EnumProperty, ByteProperty
- DelegateProperty, MulticastDelegateProperty
- TextProperty, SoftObjectProperty, WeakObjectProperty

## Sources

- UE 5.7 Source Code: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h`
- UE 5.7 Source Code: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`
- UE 5.7 Source Code: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Engine/Classes/Engine/Blueprint.h`
- UE 5.7 Source Code: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph.h`
- UE 5.7 Source Code: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphNode.h`
- UE 5.7 Source Code: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphPin.h`
- UE 5.7 Source Code: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Editor/BlueprintGraph/Classes/K2Node.h`
- UE 5.7 Source Code: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/PropertyTag.h`
- PROJECT.md: `E:\Develop\uasset_read\.planning\PROJECT.md` (requirements context)

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Package structure | HIGH | Directly read from UE 5.7 source code; authoritative |
| Blueprint data structures | HIGH | Directly read from UE 5.7 source code; authoritative |
| Graph/Node/Pin structures | HIGH | Directly read from UE 5.7 source code; authoritative |
| Existing tools features | MEDIUM | Web search results; tools like FModel, UE Viewer confirmed |
| AI-agent-friendly output patterns | LOW | No direct research on AI agent consumption patterns; inferred from requirements |

## Gaps to Address

- **Blueprint bytecode vs editor data**: Need to clarify whether target assets are cooked (bytecode) or uncooked (editor graphs). PROJECT.md implies uncooked since "blueprint nodes" are mentioned.
- **Version compatibility matrix**: UE versions 4.x through 5.7 have different serialization; need to identify which versions to support initially.
- **Property value deserialization**: Understanding how to actually read property values (not just metadata) requires deeper serialization research.
- **Node type catalog**: For semantic descriptions, need catalog of all UK2Node subclasses and their specific data fields.
- **Error handling patterns**: Need research on common parsing failures and how to recover gracefully.