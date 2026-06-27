---
title: Public API
section: public-api
---

# Public API

All public symbols are exported via `__all__` in `src/uasset_read/__init__.py`. The current version exports approximately **400** public symbols.

## Import Patterns

```python
# Recommended: import on demand
from uasset_read import parse_single, parse_batch, list_formats, MemoryPolicy
from uasset_read import parse_uasset, ParseResult
from uasset_read import FArchive, BlueprintMetadata, UEdGraph
from uasset_read import PakFileReader

# New code should prefer focused imports
from uasset_read.pak import PakFileReader
from uasset_read.cpp_gen import extract_cpp_class_skeleton
from uasset_read.renderers import get_renderer, list_formats
```

> [!NOTE] Architecture Change
> **0.4.1 Change**: The `exporter/`, `n2c/`, and `agent/` modules have been removed. The old `export()` function has been replaced by `parse_single()`.
> **0.5.0 Change**: The `formatters/` module has been cleared; all formatting functionality has been migrated to the `renderers/` system.
> New code should prefer focused imports.

## Core API (Added in 0.4.1+)

| Symbol | Description |
|--------|-------------|
| `parse_single` | Parse a single file and return a formatted string |
| `parse_batch` | Batch parse all .uasset/.umap files in a directory |
| `list_formats` | Return all registered format names |
| `BatchResult` | Batch export result data class |
| `MemoryPolicy` | Memory policy that selects RSS/timeout limits based on file size |
| `ResourceLimits` | Per-asset RSS and timeout limits |
| `MemoryLimitExceeded` | Raised when in-process parsing checkpoint exceeds RSS limit |

`parse_batch()` defaults to using isolated sub-processes per asset. The root asset and its parent asset association reads are completed within the same worker; when a worker exceeds the RSS or timeout limit, the current asset is recorded as `failed`, and batch processing continues with subsequent files. Pass `isolate_assets=False` to restore in-process batch processing.

Default tiers: files <=20 MB use 1 GB/120 seconds, 20-100 MB use 2 GB/180 seconds, >100 MB use 4 GB/300 seconds. Override with `memory_policy=MemoryPolicy(...)`. The `skip_large_files` parameter is retained for compatibility only and is deprecated.

## Version Number

| Symbol | Type | Description |
|--------|------|-------------|
| `__version__` | `str` | Current library version number |

## Constants

### Basic Constants

| Symbol | Description |
|--------|-------------|
| `PACKAGE_FILE_TAG` | .uasset file magic number |
| `PACKAGE_FILE_TAG_SWAPPED` | Byte-order-swapped magic number |
| `UE5_VERSION_MIN` | Minimum UE5 version number |
| `UE5_LEGACY_VERSION` | UE5 legacy version number |
| `MAX_NAME_COUNT` | Maximum name table entries |
| `MAX_IMPORT_COUNT` | Maximum import table entries |
| `MAX_EXPORT_COUNT` | Maximum export table entries |
| `MAX_CUSTOM_VERSIONS` | Maximum custom version count |
| `MMAP_THRESHOLD` | Automatic mmap switching threshold |
| `MAX_PROPERTY_COUNT` | Maximum property count |
| `PROPERTY_TAG_COMPLETE_TYPE_NAME` | PropertyTag complete type name flag |

### Graph Parsing Boundary Constants

| Symbol | Description |
|--------|-------------|
| `MAX_PINS_PER_NODE` | Maximum pins per node |
| `MAX_NODES_PER_GRAPH` | Maximum nodes per graph |
| `MAX_LINKEDTO_PER_PIN` | Maximum LinkedTo entries per pin |

### PropertyTag Flags

| Symbol | Description |
|--------|-------------|
| `PROP_TAG_NONE` | No flags |
| `PROP_TAG_HAS_ARRAY_INDEX` | Contains array index |
| `PROP_TAG_HAS_PROPERTY_GUID` | Contains property GUID |
| `PROP_TAG_HAS_EXTENSIONS` | Contains extension data |
| `PROP_TAG_HAS_BINARY_OR_NATIVE` | Contains binary or native data |
| `PROP_TAG_BOOL_TRUE` | Boolean value is True |
| `PROP_TAG_SKIPPED_SERIALIZE` | Serialization skipped |

### Control Flow / Event Type Sets

| Symbol | Description |
|--------|-------------|
| `CONTROL_FLOW_NODES` | Control flow node type set |
| `START_EVENT_TYPES` | Start event type set |
| `BRANCH_TYPE_MAP` | Branch type mapping |

### Package Flags

| Symbol | Description |
|--------|-------------|
| `PKG_Cooked` | Cooked flag |
| `PKG_UnversionedProperties` | Unversioned properties flag |
| `PKG_FilterEditorOnly` | Filter editor-only data flag |

### UE5 Version Flags

| Symbol | Description |
|--------|-------------|
| `UE5_SCRIPT_SERIALIZATION_OFFSET` | Script serialization offset |
| `UE5_PROPERTY_TAG_EXTENSION` | Property tag extension |
| `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` | Complete type name |
| `UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID` | Remove object export package GUID |
| `UE5_TRACK_OBJECT_EXPORT_IS_INHERITED` | Track object export inheritance |
| `UE5_OPTIONAL_RESOURCES` | Optional resources |
| `UE5_NAMES_REFERENCED_FROM_EXPORT_DATA` | Names referenced from export data |
| `UE5_PAYLOAD_TOC` | Payload table of contents |
| `UE5_LARGE_WORLD_COORDINATES` | Large world coordinates |
| `UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES` | SoftObjectPath remove asset path FNames |
| `UE5_ADD_SOFTOBJECTPATH_LIST` | Add SoftObjectPath list |
| `UE5_DATA_RESOURCES` | Data resources |
| `UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES` | Asset registry package build dependencies |
| `UE5_METADATA_SERIALIZATION_OFFSET` | Metadata serialization offset |
| `UE5_VERSE_CELLS` | Verse Cells |
| `UE5_PACKAGE_SAVED_HASH` | Package saved hash |
| `UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION` | Sub-object shadow serialization |
| `UE5_IMPORT_TYPE_HIERARCHIES` | Import type hierarchies |

### Framework / UE5MainStream / Release Version GUIDs

| Symbol | Description |
|--------|-------------|
| `FFRAMEWORK_OBJECT_VERSION_GUID` | Framework object version GUID |
| `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE` | Graph pin container type version |
| `FFRAMEWORK_VERSION_PINS_STORE_FNAME` | Pins store FName version |
| `FUE5_MAINSTREAM_VERSION_GUID` | UE5 main stream version GUID |
| `FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX` | Graph pin source index version |
| `FRELEASE_OBJECT_VERSION_GUID` | Release object version GUID |
| `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` | Pin type UObject wrapper version |

### Output Configuration

| Symbol | Description |
|--------|-------------|
| `FORMAT_CONFIG` | Output format configuration |

### CPF Property Flags

| Symbol | Description |
|--------|-------------|
| `CPF_Edit` | Editable |
| `CPF_BlueprintVisible` | Blueprint visible |
| `CPF_InstancedReference` | Instanced reference |
| `CPF_EditAnywhere` | Editable anywhere |
| `CPF_EditInstanceOnly` | Editable on instances only |
| `CPF_BlueprintReadWrite` | Blueprint read/write |
| `CPF_BlueprintReadOnly` | Blueprint read-only |
| `CPF_Transient` | Transient |
| `CPF_SaveGame` | Save game |
| `CPF_ExposeOnSpawn` | Expose on spawn |

## Exception Classes

| Symbol | Description |
|--------|-------------|
| `UAssetError` | Base exception class |
| `VersionError` | Version-related exception |
| `ErrorContext` | Exception with context |
| `ParseError` | Parse exception |

## FArchive Binary Reader

| Symbol | Description |
|--------|-------------|
| `FArchive` | UE FArchive binary reader with mmap, byte swapping, and error tolerance support |

## Serialization Modules (serializers)

### Package Structure

| Symbol | Description |
|--------|-------------|
| `PackageFileSummary` | Package file summary structure |
| `PackageIndex` | Package index |
| `ObjectImport` | Object import entry |
| `ObjectExport` | Object export entry |
| `EngineVersion` | Engine version |
| `CustomVersion` | Custom version |
| `GenerationInfo` | Generation info |

### Read Functions

| Symbol | Description |
|--------|-------------|
| `read_package_summary` | Read package summary |
| `read_name_table` | Read name table |
| `read_import_map` | Read import map |
| `read_export_map` | Read export map |
| `detect_blueprint` | Detect blueprint |

### Helper Functions

| Symbol | Description |
|--------|-------------|
| `build_imports_list` | Build imports list |
| `get_asset_class` | Get asset class name |
| `resolve_class_name` | Resolve class name |
| `detect_blueprint_generated_class` | Detect blueprint generated class |
| `detect_circular_deps` | Detect circular dependencies |
| `validate_package_index` | Validate package index |

### Graph Serialization

| Symbol | Description |
|--------|-------------|
| `read_ue_graph` | Read UE graph |
| `read_ue_graph_node` | Read graph node |
| `read_ue_graph_pin` | Read graph pin |
| `read_ed_graph_pin_type` | Read ED graph pin type |
| `read_fmember_reference` | Read FMemberReference |
| `create_node_from_archive` | Create node from archive |

### Node Type Readers

| Symbol | Description |
|--------|-------------|
| `read_k2node_call_function` | Read function call node |
| `read_k2node_event` | Read event node |
| `read_k2node_knot` | Read knot node |
| `read_edgraph_node_comment` | Read node comment |
| `read_k2node_enhanced_input` | Read enhanced input node |
| `read_k2node_functionentry` | Read function entry node |

### PropertyTag Reading

| Symbol | Description |
|--------|-------------|
| `read_property_tag` | Read PropertyTag |
| `parse_ctrl_flags` | Parse control flags |
| `parse_ue511_ctrl_flags` | Parse UE5.11 control flags |

### Object Resource Helpers

| Symbol | Description |
|--------|-------------|
| `find_main_blueprint_generated_class` | Find main blueprint generated class |
| `resolve_parent_class` | Resolve parent class |
| `resolve_class_name_with_linker` | Resolve class name with linker |
| `get_asset_class_with_linker` | Get asset class with linker |
| `detect_blueprint_with_linker` | Detect blueprint with linker |
| `resolve_parent_class_with_linker` | Resolve parent class with linker |
| `read_soft_object_paths` | Read soft object paths |

## Core Data Models (models)

### Graph Models

| Symbol | Description |
|--------|-------------|
| `FEdGraphPinType` | Graph pin type structure |
| `UEdGraphPin` | Graph pin data model |
| `UEdGraphNode` | Graph node data model |
| `UEdGraph` | Graph data model |
| `FMemberReference` | Member reference structure |

### Node Types

| Symbol | Description |
|--------|-------------|
| `K2NodeCallFunction` | Function call node |
| `K2NodeEvent` | Event node |
| `K2NodeKnot` | Knot node |
| `EdGraphNodeComment` | Comment node |
| `K2NodeEnhancedInputAction` | Enhanced input action node |
| `K2NodeFunctionEntry` | Function entry node |

### Parse Results

| Symbol | Description |
|--------|-------------|
| `ParseResult` | Parse result container |
| `StatusInfo` | Status info |

### Blueprint Metadata

| Symbol | Description |
|--------|-------------|
| `BlueprintMetadata` | Blueprint metadata |
| `BlueprintVariable` | Blueprint variable |
| `BlueprintFunction` | Blueprint function |
| `BlueprintEvent` | Blueprint event |
| `FunctionParameter` | Function parameter |
| `MulticastDelegate` | Multicast delegate |

### Property Data Models

| Symbol | Description |
|--------|-------------|
| `PropertyTag` | Property tag |
| `PropertyTypeName` | Property type name enum |
| `PropertyValue` | Property value base class |
| `SoftObjectPathValue` | Soft object path value |
| `AdvancedPropertyValue` | Advanced property value |
| `StructValue` | Struct value |
| `MapValue` | Map value |
| `SetValue` | Set value |
| `EnumValue` | Enum value |
| `TextValue` | Text value |
| `DelegateValue` | Delegate value |

### Transform Data

| Symbol | Description |
|--------|-------------|
| `VectorValue` | Vector value |
| `RotatorValue` | Rotator value |
| `ScaleValue` | Scale value |
| `format_transform_value` | Format transform value |

## Mappings Module (mappings)

| Symbol | Description |
|--------|-------------|
| `TypeMappingsProvider` | Type mappings provider interface |
| `UsmapParser` | .usmap file parser |
| `JmapParser` | .jmap file parser |
| `TypeMappings` | Type mappings container |
| `StructMapping` | Struct mapping |
| `PropertyType` | Property type enum |
| `PropertyInfo` | Property info |

## Parser Module (parsers)

### Property Parsing Functions

| Symbol | Description |
|--------|-------------|
| `parse_property_value` | Generic property value parse dispatch |
| `parse_properties_from_export` | Parse property list from export |
| `parse_bool_property` | Boolean property |
| `parse_int_property` | Integer property |
| `parse_float_property` | Float property |
| `parse_str_property` | String property |
| `parse_name_property` | Name property |
| `parse_object_property` | Object property |
| `parse_soft_object_property` | Soft object property |
| `parse_array_property` | Array property |
| `parse_struct_property` | Struct property |
| `parse_map_property` | Map property |
| `parse_set_property` | Set property |
| `parse_enum_property` | Enum property |
| `parse_text_property` | Text property |
| `parse_delegate_property` | Delegate property |

### New Property Type Parsers

| Symbol | Description |
|--------|-------------|
| `parse_uint16_property` | UInt16 property |
| `parse_uint32_property` | UInt32 property |
| `parse_uint64_property` | UInt64 property |
| `parse_utf8_str_property` | UTF-8 string property |
| `parse_weak_object_property` | Weak object property |
| `parse_lazy_object_property` | Lazy object property |
| `parse_class_property` | Class property |
| `parse_soft_class_property` | Soft class property |
| `parse_asset_object_property` | Asset object property |
| `parse_multicast_delegate_property` | Multicast delegate property |
| `parse_multicast_inline_delegate_property` | Inline multicast delegate property |
| `parse_multicast_sparse_delegate_property` | Sparse multicast delegate property |
| `parse_interface_property` | Interface property |
| `parse_field_path_property` | Field path property |
| `parse_optional_property` | Optional property |
| `parse_verse_string_property` | Verse string property |
| `parse_verse_class_property` | Verse class property |
| `parse_verse_function_property` | Verse function property |
| `parse_verse_dynamic_property` | Verse dynamic property |
| `parse_verse_cell_property` | Verse cell property |
| `parse_verse_value_property` | Verse value property |
| `parse_ansi_str_property` | ANSI string property |
| `parse_double_property` | Double property |
| `parse_guid_property` | GUID property |

### Custom Property Registry

| Symbol | Description |
|--------|-------------|
| `CUSTOM_PROPERTY_HANDLERS` | Custom property handler registry |
| `CustomPropertyContext` | Custom property context |
| `register_custom_property` | Register custom property handler |
| `handle_custom_property` | Handle custom property |

### Helper Functions

| Symbol | Description |
|--------|-------------|
| `get_struct_size` | Get struct size |
| `_extract_struct_type_from_tag` | Extract struct type from tag |
| `_extract_map_types_from_tag` | Extract map types from tag |
| `_extract_set_type_from_tag` | Extract set type from tag |
| `_extract_enum_type_from_tag` | Extract enum type from tag |
| `resolve_name_from_index` | Resolve name from index |
| `read_validated_count` | Read validated count |
| `make_enum_value` | Create enum value |
| `extract_inner_from_tag` | Extract inner type from tag |

### Blueprint Helpers

| Symbol | Description |
|--------|-------------|
| `parse_property_flags_to_labels` | Parse property flags to labels |
| `read_blueprint_variable` | Read blueprint variable |
| `parse_default_value` | Parse default value |
| `format_variable_type` | Format variable type |

## Blueprint Module (blueprint)

| Symbol | Description |
|--------|-------------|
| `extract_blueprint_variables` | Extract blueprint variables |
| `parse_component_transform` | Parse component transform |
| `extract_blueprint_metadata` | Extract blueprint metadata |
| `extract_components` | Extract components |
| `extract_component_transforms` | Extract component transforms list |
| `parse_vector_value` | Parse vector value |
| `parse_rotator_value` | Parse rotator value |
| `parse_scale_value` | Parse scale value |

## Main Parse Pipeline

| Symbol | Description |
|--------|-------------|
| `parse_package` | Parse package entry point |
| `parse_uasset` | Parse .uasset entry point |
| `parse_uasset_with_linker` | Parse with linker entry point |

## Package Management (package)

| Symbol | Description |
|--------|-------------|
| `PackageBundle` | Package bundle container |
| `PackageProvider` | Package provider base class |
| `FileSystemPackageProvider` | File system package provider |
| `PakPackageProvider` | PAK package provider |
| `IoStorePackageProvider` | IoStore package provider |
| `open_package_bundle` | Open package bundle |

## Raw File Parsing (raw)

| Symbol | Description |
|--------|-------------|
| `RawFileResult` | Raw file parse result |
| `parse_raw_file` | Parse raw file |
| `parse_json_descriptor` | Parse JSON descriptor |
| `parse_ini_file` | Parse INI file |
| `parse_locres` | Parse LocRes localization resource |
| `parse_locmeta` | Parse LocMeta localization metadata |
| `parse_audio_metadata` | Parse audio metadata |

## Graph Parsing Module (graph)

| Symbol | Description |
|--------|-------------|
| `extract_blueprint_graphs` | Extract blueprint graph data |
| `build_execution_flow_entries` | Build execution flow entries |
| `build_data_flows` | Build data flows |
| `build_connections_map` | Build connections map |
| `format_graphs_json` | Format graphs as JSON |
| `build_execution_chains` | Build execution chains |
| `format_pin_ref` | Format pin reference |
| `_derive_node_name` | Derive node name |
| `build_function_graphs` | Build function graphs |

## ~~Formatters Module~~ (formatters) -- Deprecated

> [!WARNING] Deprecated
> The `formatters/` directory was cleared in 0.5.0; all formatting functionality has been migrated to the `renderers/` system.
> Use `parse_single(format="json")` or `parse_single(format="markdown")` instead.

## Kismet Bytecode Module (kismet)

### Enums

| Symbol | Description |
|--------|-------------|
| `EExprToken` | Expression token enum |
| `ECastToken` | Cast token enum |
| `EScriptInstrumentationType` | Script instrumentation type |
| `EBlueprintTextLiteralType` | Blueprint text literal type |
| `EAutoRtfmStopTransactMode` | Auto RTFM stop transaction mode |

### Core Types

| Symbol | Description |
|--------|-------------|
| `KismetExpression` | Kismet expression base class |
| `KismetExpressionT` | Kismet expression generic |
| `EXPR_CLASS_MAP` | Expression class mapping |
| `FKismetPropertyPointer` | Kismet property pointer |
| `FFieldPath` | Field path |
| `FKismetArchive` | Kismet bytecode archive |
| `USTRUCT_TYPES` | Struct type set |
| `reset_bpgc_cache` | Reset BPGC cache |

### Bytecode Extraction

| Symbol | Description |
|--------|-------------|
| `extract_bytecode_bytes` | Extract bytecode bytes |
| `parse_bytecode_stream` | Parse bytecode stream |
| `extract_and_parse` | Extract and parse |

### Translators

| Symbol | Description |
|--------|-------------|
| `KismetTranslator` | Kismet to C++ translator |
| `MathFunctionCleaner` | Math function cleaner |
| `TypeRegistry` | Type registry |
| `line_cpp` | Generate C++ code line |
| `UE_TYPE_MAP` | UE type mapping |
| `FunctionBodyBuilder` | Function body builder |
| `to_function_body` | Convert to function body |
| `StructuredControlFlow` | Structured control flow |
| `StructuredBlock` | Structured block |

### Decompilation Pipeline

| Symbol | Description |
|--------|-------------|
| `KismetDecompiledResult` | Decompiled result |
| `decompile_uasset` | Decompile entire uasset |
| `decompile_single_function` | Decompile single function |

## ~~Removed Modules~~

> [!WARNING] Removed
> The following modules were entirely removed in 0.4.1 and do not exist in the current version:
> - `agent/` -- Use `parse_single(format="cpp_skeleton")` to obtain C++ output
> - `n2c/` -- N2C intermediate format is no longer provided
> - `exporter/` -- Use `parse_single()` + renderer system
>
> The following modules were cleared in 0.5.0:
> - `formatters/` -- All functionality migrated to the `renderers/` system

## C++ Code Generation (cpp_gen)

### IR Types

| Symbol | Description |
|--------|-------------|
| `CppProperty` | C++ property IR |
| `CppHeaderMeta` | C++ header metadata |
| `CppClassIR` | C++ class IR |
| `CppMethodIR` | C++ method IR |
| `CppCallParameter` | C++ call parameter |
| `CppCallStatement` | C++ call statement |

### Formatting Functions

| Symbol | Description |
|--------|-------------|
| `format_cpp_class_json` | Format C++ class as JSON |
| `format_cpp_header` | Format C++ header file |
| `format_cpp_call_statements` | Format C++ call statements |
| `format_cpp_default_value` | Format C++ default value |
| `format_cpp_transform` | Format C++ transform |
| `format_cpp_component_init` | Format C++ component initialization |
| `format_cpp_input_action_load` | Format C++ input action loading |
| `build_constructor_sections` | Build constructor sections |
| `format_cpp_constructor` | Format C++ constructor |
| `extract_cpp_class_skeleton` | Extract C++ class skeleton |
| `extract_cpp_constructor` | Extract C++ constructor |

### Type Mappings

| Symbol | Description |
|--------|-------------|
| `UE_TO_CPP_TYPE_MAP` | UE to C++ type mapping |
| `ENGINE_CLASS_PATHS` | Engine class paths |
| `ue_path_to_cpp_type` | UE path to C++ type |
| `ue_package_path_to_cpp_class` | UE package path to C++ class |
| `CPF_TO_UPROPERTY_MAP` | CPF to UPROPERTY mapping |
| `cpf_flags_to_uproperty_marks` | CPF flags to UPROPERTY marks |

## Versioning

| Symbol | Description |
|--------|-------------|
| `VersionContainer` | Version container |
| `build_version_container` | Build version container |
| `EUEVersion` | UE version enum |

## Linker Module (link)

| Symbol | Description |
|--------|-------------|
| `PackageLinker` | Package linker (two-phase object graph reconstruction) |
| `UObjectInstance` | UObject instance |
| `LinkerParseResult` | Linker parse result |

## PAK Module (pak)

### Constants and Flags

| Symbol | Description |
|--------|-------------|
| `PAK_FILE_MAGIC` | PAK file magic number |
| `PakFileVersion` | PAK file version enum |
| `ECompressionFlags` | Compression flags enum |
| `Flag_Encrypted` | Encrypted flag |
| `Flag_Deleted` | Deleted flag |
| `MaxNumCompressionMethods` | Maximum compression method count |
| `PAK_INFO_SIZES` | PAK info size constants |

### Data Structures

| Symbol | Description |
|--------|-------------|
| `FPakCompressedBlock` | Compressed block |
| `FPakEntry` | PAK entry |
| `FPakInfo` | PAK info header |
| `FPakDirectoryEntry` | PAK directory entry |

### Reading and Decompression

| Symbol | Description |
|--------|-------------|
| `read_fstring` | Read FString |
| `decompress_block` | Decompress block |
| `decompress_entry` | Decompress entry |
| `PakFileReader` | PAK file reader |

## IoStore Module (iostore)

| Symbol | Description |
|--------|-------------|
| `IoStoreReader` | IoStore container reader |
| `FIoChunkId` | Io Chunk ID structure |
| `FIoOffsetAndSize` | Offset and size structure |

## Bulk Data Module (bulk)

| Symbol | Description |
|--------|-------------|
| `FBulkDataHeader` | BulkData header structure |
| `BulkDataFlags` | BulkData flags enum |

## UObject Type Hierarchy (objects)

> [!WARNING] Deprecated
> The `bulk/` and `objects/` modules are deprecated; removed from the public API in 0.3.6 (backward-compatible exports retained).

| Symbol | Description |
|--------|-------------|
| `UObject` | UObject base class |
| `ObjectTypeRegistry` | Object type registry |
| `UStaticMesh` | StaticMesh export type |
| `USkeletalMesh` | SkeletalMesh export type |
| `UTexture2D` | Texture2D export type |
| `UMaterial` | Material export type |
| `UMaterialInstance` | MaterialInstance export type |

## Deprecated Modules

| Module | Status | Description |
|--------|--------|-------------|
| `bulk/` | Deprecated | Removed from public API in 0.3.6 |
| `objects/` | Deprecated | Removed from public API in 0.3.6 |
| `formatters/` | Deprecated | Cleared in 0.5.0; functionality migrated to `renderers/` |
