---
title: UE Source Code Reference
section: ue-reference
---

# UE Source Code Reference

This document establishes the mapping between uasset_read modules and Unreal Engine C++ source code, ensuring that every parsing logic can be traced back to its UE source definition.

## Core Principles

```
Directly reading/guessing binary formats is forbidden
├── ❌ Wrong: read binary -> guess field meaning -> implement
└── ✅ Correct: look up UE source -> understand struct definition -> implement

Output must be traceable to C++ definitions
├── Every parsed field must correspond to a UE source field
└── Documentation must note source locations
```

## UE 5.8 MCP Live Reference

The UE 5.8 official Experimental Unreal MCP server can serve as a live reference layer for Editor-visible state. It does not replace UE C++ source definitions for binary formats, but can verify that parser output matches the actual asset state in a running Editor.

Local installation reference:

| Item | Path/Value | Purpose |
|----|---------|------|
| UE 5.8 Engine | `D:\Program Files\Epic Games\Engine\UE_5.8` | Local source and plugin baseline |
| Unreal MCP server | `Engine\Plugins\Experimental\ModelContextProtocol` | MCP server within Editor/Runtime |
| MCP Client Toolset | `Engine\Plugins\Experimental\Toolsets\MCPClientToolset` | Toolset client for Editor to connect to external MCP servers |
| All Toolsets | `Engine\Plugins\Experimental\Toolsets\AllToolsets` | Aggregates and enables multiple Experimental Toolsets |
| Default endpoint | `http://127.0.0.1:8000/mcp` | Local Streamable HTTP MCP endpoint |

Key behaviors:

- `ModelContextProtocol.uplugin` is Experimental and not enabled by default.
- `ModelContextProtocolSettings` defaults to `ServerPortNumber = 8000`, `ServerUrlPath = "/mcp"`, `bAutoStartServer = false`, `bEnableToolSearch = true`.
- In tool-search mode, `tools/list` only returns `list_toolsets`, `describe_toolset`, and `call_tool`. Actual asset/Editor tools must first be discovered via `list_toolsets` and `describe_toolset`.
- `ModelContextProtocolEditor` adapts toolsets through the Toolset Registry; only enabled and registered toolsets will appear in the runtime directory.
- Official limitations include HTTP/SSE only, loopback security boundary, no authentication, and shipping toolsets do not publish MCP Resources/Prompts.

Usage guidelines for this project:

- For `.uasset` binary field implementations, UE C++ source remains the primary reference.
- For Editor-visible result verification, prefer MCP to collect live data, especially for Blueprint graphs, components, Transform, Input Action, and reference relationships.
- If the toolset is installed locally but `list_toolsets` does not show the target tool at runtime, enable `AllToolsets` or the corresponding Toolset plugin and execute `ModelContextProtocol.RefreshTools`.
- If official/existing toolsets cannot read-only export the required fields, a project-specific read-only toolset should be created; tools that modify assets must not be used as verification collection paths.
- MCP evidence must record toolset schema and call parameters to ensure the same asset can be reviewed.

## UE Class Mapping

| UE Class | Source Location | Corresponding Module in This Package |
|-------|----------|--------------|
| `FArchive` | `Runtime/Core/Public/Serialization/Archive.h` | `archive.py` |
| `FPackageFileSummary` | `Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` | `serializers/package_file_summary.py` |
| `FLinkerLoad` | `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` | `link/linker.py` |
| `UPackage` | `Runtime/CoreUObject/Public/UObject/Package.h` | `package.py` |
| `UObject` | `Runtime/CoreUObject/Public/UObject/Object.h` | `link/` — `UObjectInstance` |
| `FName` | `Runtime/Core/Public/UObject/Name.h` | `archive.py` — `read_fstring()` / NameMap |
| `FPropertyTag` | `Runtime/CoreUObject/Public/UObject/PropertyTag.h` | `serializers/property_tag.py` |
| `UBlueprint` | `Engine/Classes/Engine/Blueprint.h` | `blueprint/` |
| `UEdGraph` | `Engine/Classes/EdGraph/EdGraph.h` | `graph/` |
| `UEdGraphNode` | `Engine/Classes/EdGraph/EdGraphNode.h` | `models/node.py` |
| `UEdGraphPin` | `Engine/Classes/EdGraph/EdGraphPin.h` | `models/pin.py` |
| `Kismet VM` | `Engine/Private/Kismet/ScriptStack.cpp` | `kismet/` |
| `FBlueprintCompileReinstancer` | `Engine/Private/Kismet2/KismetReinstanceUtilities.cpp` | `blueprint/` |
| `FPakFile` | `Runtime/PakFile/Public/IPlatformFilePak.h` | `pak/` |
| `FIoStoreReader` | `Runtime/Core/Public/Serialization/IoStoreReader.h` | `iostore/` |
| `FBulkData` | `Runtime/CoreUObject/Public/Serialization/BulkData.h` | `bulk/` |
| `FPackageFileVersion` | `Runtime/CoreUObject/Public/UObject/PackageFileSummary.h` | `versioning.py` — `FPackageFileVersion` |
| `FCustomVersion` | `Runtime/Core/Public/Serialization/CustomVersion.h` | `versioning.py` — `VersionContainer` |
| `FObjectExport` | `Runtime/CoreUObject/Public/UObject/ObjectResource.h` | `serializers/export_map.py` |
| `FObjectImport` | `Runtime/CoreUObject/Public/UObject/ObjectResource.h` | `serializers/import_map.py` |
| `FNameMap` | `Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` | `parse_uasset.py` — Built-in NameMap |

## Version Mapping

### UE5 File Version (FileVersionUE5)

| Version Value | UE Version | Key Feature | Constant Name |
|--------|---------|----------|--------|
| 1000 | UE 5.0 | Large World Coordinates (LWC) baseline | `UE5_VERSION_MIN` |
| 1001 | UE 5.1 | SoftObjectPath list, name references | `UE5_NAMES_REFERENCED_FROM_EXPORT_DATA` |
| 1002 | UE 5.2 | PayloadTOC support | `UE5_PAYLOAD_TOC` |
| 1003 | UE 5.3 | Optional resources | `UE5_OPTIONAL_RESOURCES` |
| 1004 | UE 5.4 | Large World Coordinates complete | `UE5_LARGE_WORLD_COORDINATES` |
| 1005 | UE 5.5 | Remove ObjectExport PackageGuid | `UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID` |
| 1006 | UE 5.5+ | Track ObjectExport IsInherited | `UE5_TRACK_OBJECT_EXPORT_IS_INHERITED` |
| 1007 | UE 5.5+ | FSoftObjectPath remove AssetPath FNames | `UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES` |
| 1008 | UE 5.5+ | Add SoftObjectPath List complete | `UE5_ADD_SOFTOBJECTPATH_LIST` |
| 1009 | UE 5.4+ | Data resources | `UE5_DATA_RESOURCES` |
| 1010 | UE 5.4+ | Script serialization offset | `UE5_SCRIPT_SERIALIZATION_OFFSET` |
| 1011 | UE 5.4+ | PropertyTag extension | `UE5_PROPERTY_TAG_EXTENSION` |
| 1012 | UE 5.5+ | PropertyTag complete type name | `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` |
| 1013 | UE 5.5+ | AssetRegistry PackageBuildDependencies | `UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES` |
| 1014 | UE 5.5+ | Metadata serialization offset | `UE5_METADATA_SERIALIZATION_OFFSET` |
| 1015 | UE 5.6 | Verse Cells | `UE5_VERSE_CELLS` |
| 1016 | UE 5.6+ | Package Saved Hash | `UE5_PACKAGE_SAVED_HASH` |
| 1017 | UE 5.6+ | OS Sub-Object Shadow Serialization | `UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION` |
| 1018 | UE 5.6+ | Import Type Hierarchies | `UE5_IMPORT_TYPE_HIERARCHIES` |

### UE4 File Version (FileVersionUE4)

| Version Value | UE Version | Key Feature | Constant Name |
|--------|---------|----------|--------|
| 516 | UE 4.23 | Package summary localization ID, string asset reference mapping | `UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID` |
| 517 | UE 4.24 | In-package text serialization | `UE4_SERIALIZE_TEXT_IN_PACKAGES` |
| 518 | UE 4.25 | Searchable names | `UE4_ADDED_SEARCHABLE_NAMES` |
| 519 | UE 4.26 | Package owner | `UE4_ADDED_PACKAGE_OWNER` |
| 520 | UE 4.27 | Non-outer package import | `UE4_NON_OUTER_PACKAGE_IMPORT` |

### CustomVersion Stream

| Stream | GUID | Description |
|--------|------|------|
| Framework | `CFFC743F-43B04480-939114DF-171D2073` | Graph/pin serialization version |
| UE5 Mainstream | `697DD581-E64F41AB-AA4A51EC-BEB7B628` | UE5 main flow version |
| Release | `9C54D522-A8264FBE-94210746-61B482D0` | Release stream |
| UE5 Release Stream | `D89B5E42-24BD4D46-8412ACA8-DF641779` | UE5 release stream |
| Blueprints | `B0D832E4-1F89-4D06-B39A-8F1B5E1B2A4B` | Blueprint subsystem version |
| Core | `371EC2EE-4CD7-4C38-AEB1-B7D6F539A54B` | Core subsystem version |
| Editor | `E4B068ED-F494-42E9-A231-DA0B0E4C5E56` | Editor version |
| Anim | `29E575DD-E0A3-4682-9C20-D1CF1B5E8DEF` | Animation subsystem version |
| Physics | `78F01B33-BEA0-46A0-8BAF-6C4F4E23F8C1` | Physics subsystem version |
| Rendering | `645F75DB-7F54-4C64-A1E2-2F6F3B4B8A5E` | Rendering subsystem version |

### Key Version Thresholds

| Constant | Value | Description |
|------|-----|------|
| `UE5_LEGACY_VERSION` | -9 | Fixed LegacyFileVersion for UE5.6+ files |
| `PROPERTY_TAG_COMPLETE_TYPE_NAME` | 1012 | Threshold for PropertyTag to use complete type names |
| `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE` | 15 | Pin container type serialization version |
| `FFRAMEWORK_VERSION_PINS_STORE_FNAME` | 19 | Pin FName storage version |
| `FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX` | 50 | Pin SourceIndex version |
| `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` | 10 | Pin type UObjectWrapper version |

## Package Flags

| Flag | Value | UE Source | Description |
|------|-----|---------|------|
| `PKG_Cooked` | `0x200` | `EPackageFlags::PKG_Cooked` | Cooked package (data has been stripped) |
| `PKG_UnversionedProperties` | `0x2000` | `EPackageFlags::PKG_UnversionedProperties` | Uses unversioned property serialization |
| `PKG_FilterEditorOnly` | `0x80000000` | `EPackageFlags::PKG_FilterEditorOnly` | Filter editor-only objects |

## PropertyTag Flags

| Flag | Value | Description |
|------|-----|------|
| `PROP_TAG_NONE` | `0x00` | No flags |
| `PROP_TAG_HAS_ARRAY_INDEX` | `0x01` | ArrayIndex field present |
| `PROP_TAG_HAS_PROPERTY_GUID` | `0x02` | PropertyGuid field present |
| `PROP_TAG_HAS_EXTENSIONS` | `0x04` | Extension data present |
| `PROP_TAG_HAS_BINARY_OR_NATIVE` | `0x08` | Binary/native serialization |
| `PROP_TAG_BOOL_TRUE` | `0x10` | Bool value is true |
| `PROP_TAG_SKIPPED_SERIALIZE` | `0x20` | Serialization skipped |

## File Magic Tags

| Constant | Value | Description |
|------|-----|------|
| `PACKAGE_FILE_TAG` | `0x9E2A83C1` | Correct byte-order magic tag |
| `PACKAGE_FILE_TAG_SWAPPED` | `0xC1832A9E` | Byte-swapped magic tag |

## UE Loading Pipeline

```
User double-clicks asset in Content Browser
        |
        v
SContentBrowser::OnItemsActivated()
        |
        v
IAssetTypeActions::OpenAssetEditor() / AssetDefinition::OpenAssets()
        |
        v
FAssetData::GetAsset() or LoadPackage()
        |
        v
LoadPackageInternal() -> FLinkerLoad::CreateLinkerAsync()
        |
        v
FLinkerLoad::ProcessPackageSummary()  <- Read file header, verify version
        |
        v
FLinkerLoad::Tick() -> LoadAllObjects() -> Serialize export table
        |
        v
FinalizeCreation() -> PostLoad() -> Asset ready
```

### Loading Phase Details

| Phase | UE Function | Description |
|------|---------|------|
| 1. Package summary processing | `ProcessPackageSummary()` | Read and verify package file header, engine version, file format |
| 2. Import table loading | — | Load all import table entries (referenced external objects) |
| 3. Export table processing | — | Read export table entries (objects stored in this package), create UObject instances |
| 4. Object serialization | `Tick()` / `LoadAllObjects()` | Serialize all object data, call `Preload()` to serialize properties |
| 5. Creation complete | `FinalizeCreation()` | Connect object graph, mark package as fully loaded |

## Key Source File Path Index

| File | UE Source Path | Description |
|------|-------------|------|
| PackageFileSummary.h | `Runtime/CoreUObject/Public/UObject/` | File header structure |
| ObjectVersion.h | `Runtime/Core/Public/UObject/` | Version number definitions |
| ObjectResource.h | `Runtime/CoreUObject/Public/UObject/` | Import/Export table structures |
| LinkerLoad.h | `Runtime/CoreUObject/Public/UObject/` | Loading logic |
| LinkerLoad.cpp | `Runtime/CoreUObject/Private/UObject/` | 274KB core implementation |
| PropertyTag.h | `Runtime/CoreUObject/Public/UObject/` | Property tags |
| BulkData.h | `Runtime/CoreUObject/Public/Serialization/` | BulkData structures |
| Archive.h | `Runtime/Core/Public/Serialization/` | FArchive base class |
| CustomVersion.h | `Runtime/Core/Public/Serialization/` | Custom version system |
| Package.h | `Runtime/CoreUObject/Public/UObject/` | UPackage definition |
| Blueprint.h | `Engine/Classes/Engine/` | UBlueprint definition |
| EdGraph.h | `Engine/Classes/EdGraph/` | UEdGraph definition |
| EdGraphPin.h | `Engine/Classes/EdGraph/` | UEdGraphPin definition |
| ScriptStack.cpp | `Engine/Private/Kismet/` | Kismet VM execution |

## Safety Boundary Constants

| Constant | Value | Description |
|------|-----|------|
| `MAX_NAME_COUNT` | 10,000,000 | Maximum name table entries |
| `MAX_IMPORT_COUNT` | 1,000,000 | Maximum import table entries |
| `MAX_EXPORT_COUNT` | 1,000,000 | Maximum export table entries |
| `MAX_CUSTOM_VERSIONS` | 10,000 | Maximum custom version entries |
| `MAX_PROPERTY_COUNT` | 10,000 | Property iteration limit |
| `MAX_ARRAY_COUNT` | 1,000,000 | Maximum ArrayProperty elements |
| `MAX_FSTRING_LENGTH` | 10 MB | Maximum FString length |
| `MAX_PINS_PER_NODE` | 1,000 | Maximum pins per node |
| `MAX_NODES_PER_GRAPH` | 5,000 | Maximum nodes per graph |
| `MAX_LINKEDTO_PER_PIN` | 100 | Maximum connections per pin |
| `MAX_TYPENODE_NODES` | 20 | Maximum FPropertyTypeName nodes |

## External References

- `docs/formats/uasset/` — UE .uasset format documentation (60+ Markdown files), `Index.md` is the main index
- `docs/formats/uasset/serialization/` — Serialization mechanism reference
- `docs/formats/uasset/cooked/` — Cooked format reference
- `docs/formats/uasset/version/` — Version evolution reference
- `docs/formats/uasset/assets/` — Asset type reference
- `docs/reference/` — Blueprint node text reference, UE loading pipeline, Blueprint-to-C++ guide
- `external/CUE4Parse/` — C# reference implementation for cross-validation of parsing logic
