---
title: Constants and Configuration
section: constants
---

# Constants and Configuration

**Module path**: `src/uasset_read/constants.py`

> Defines all version numbers, property type thresholds, boundary validation constants, PropertyTag flags, CPF flags, etc. Migrated from UE source code. Guessing binary behavior is prohibited.

## Package File Magic Tags

| Constant | Value | Description |
|----------|-------|-------------|
| `PACKAGE_FILE_TAG` | `0x9E2A83C1` | UE package file magic tag (correct byte order) |
| `PACKAGE_FILE_TAG_SWAPPED` | `0xC1832A9E` | UE package file magic tag (swapped byte order) |

## Boundary Validation Constants

Defensive programming constants used to prevent infinite loops / memory exhaustion caused by malicious or corrupted files.

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_NAME_COUNT` | 10,000,000 | Maximum name table entries |
| `MAX_IMPORT_COUNT` | 1,000,000 | Maximum import table entries |
| `MAX_EXPORT_COUNT` | 1,000,000 | Maximum export table entries |
| `MAX_CUSTOM_VERSIONS` | 10,000 | Maximum custom version entries |
| `MMAP_THRESHOLD` | 50 MB | File size threshold to enable mmap |
| `MAX_PROPERTY_COUNT` | 10,000 | Property loop limit |
| `MAX_ARRAY_COUNT` | 1,000,000 | Array element limit |
| `MAX_FSTRING_LENGTH` | 10 MB | Maximum FString length (UTF-8/UTF-16) |
| `MAX_PINS_PER_NODE` | 1,000 | Maximum pins per node |
| `MAX_NODES_PER_GRAPH` | 5,000 | Maximum nodes per graph |
| `MAX_LINKEDTO_PER_PIN` | 100 | Maximum connections per pin |
| `MAX_TYPENODE_NODES` | 20 | Maximum FPropertyTypeName nodes |

## PropertyTag Flags

| Flag | Value | Description |
|------|-------|-------------|
| `PROP_TAG_NONE` | `0x00` | No flag |
| `PROP_TAG_HAS_ARRAY_INDEX` | `0x01` | Has array index |
| `PROP_TAG_HAS_PROPERTY_GUID` | `0x02` | Has property GUID |
| `PROP_TAG_HAS_EXTENSIONS` | `0x04` | Extension data |
| `PROP_TAG_HAS_BINARY_OR_NATIVE` | `0x08` | Binary / native serialization |
| `PROP_TAG_BOOL_TRUE` | `0x10` | Boolean value is true |
| `PROP_TAG_SKIPPED_SERIALIZE` | `0x20` | Serialization skipped |

## PropertyTag Version Thresholds

| Constant | Value | Description |
|----------|-------|-------------|
| `PROPERTY_TAG_COMPLETE_TYPE_NAME` | 1012 | UE5 format switch threshold |

## UE5 Version Constants

Corresponds to `EUnrealEngineObjectUE5Version`.

| Constant | Value | Description |
|----------|-------|-------------|
| `UE5_VERSION_MIN` | 0 | UE5 minimum version |
| `UE5_LEGACY_VERSION` | -9 | Fixed LegacyFileVersion for UE5.6+ files |
| `UE5_NAMES_REFERENCED_FROM_EXPORT_DATA` | 1001 | Names referenced from export data |
| `UE5_PAYLOAD_TOC` | 1002 | Payload table of contents |
| `UE5_OPTIONAL_RESOURCES` | 1003 | Optional resources |
| `UE5_LARGE_WORLD_COORDINATES` | 1004 | Large World Coordinates (LWC) |
| `UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID` | 1005 | Remove object export package GUID |
| `UE5_TRACK_OBJECT_EXPORT_IS_INHERITED` | 1006 | Track object export inheritance |
| `UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES` | 1007 | Remove asset path FNames |
| `UE5_ADD_SOFTOBJECTPATH_LIST` | 1008 | Add soft object path list |
| `UE5_DATA_RESOURCES` | 1009 | Data resources |
| `UE5_SCRIPT_SERIALIZATION_OFFSET` | 1010 | Script serialization offset |
| `UE5_PROPERTY_TAG_EXTENSION` | 1011 | PropertyTag extension |
| `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` | 1012 | Complete type name (alias) |
| `UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES` | 1013 | Asset registry package build dependencies |
| `UE5_METADATA_SERIALIZATION_OFFSET` | 1014 | Metadata serialization offset |
| `UE5_VERSE_CELLS` | 1015 | Verse cells |
| `UE5_PACKAGE_SAVED_HASH` | 1016 | Package saved hash |
| `UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION` | 1017 | Sub-object shadow serialization |
| `UE5_IMPORT_TYPE_HIERARCHIES` | 1018 | Import type hierarchies |

## UE4 Version Constants

Corresponds to `EUnrealEngineObjectUE4Version`.

| Constant | Value | Description |
|----------|-------|-------------|
| `UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID` | 516 | Added package summary localization ID |
| `UE4_ADD_STRING_ASSET_REFERENCES_MAP` | 516 | Added string asset references map |
| `UE4_SERIALIZE_TEXT_IN_PACKAGES` | 517 | Serialize text in packages |
| `UE4_ADDED_SEARCHABLE_NAMES` | 518 | Added searchable names |
| `UE4_ADDED_PACKAGE_OWNER` | 519 | Added package owner |
| `UE4_NON_OUTER_PACKAGE_IMPORT` | 520 | Non-outer package import |

## CustomVersion GUIDs

| GUID | Name |
|------|------|
| `CFFC743F-43B04480-939114DF-171D2073` | `FFRAMEWORK_OBJECT_VERSION_GUID` |
| `697DD581-E64F41AB-AA4A51EC-BEB7B628` | `FUE5_MAINSTREAM_VERSION_GUID` |
| `9C54D522-A8264FBE-94210746-61B482D0` | `FRELEASE_OBJECT_VERSION_GUID` |
| `D89B5E42-24BD4D46-8412ACA8-DF641779` | `FUE5RELEASESTREAM_OBJECT_VERSION_GUID` |
| `B0D832E4-1F89-4D06-B39A-8F1B5E1B2A4B` | `FBLUEPRINTS_OBJECT_VERSION_GUID` |
| `371EC2EE-4CD7-4C38-AEB1-B7D6F539A54B` | `FCORE_OBJECT_VERSION_GUID` |
| `E4B068ED-F494-42E9-A231-DA0B0E4C5E56` | `FEDITOR_OBJECT_VERSION_GUID` |
| `29E575DD-E0A3-4682-9C20-D1CF1B5E8DEF` | `FANIM_OBJECT_VERSION_GUID` |
| `78F01B33-BEA0-46A0-8BAF-6C4F4E23F8C1` | `FPHYSICS_OBJECT_VERSION_GUID` |
| `645F75DB-7F54-4C64-A1E2-2F6F3B4B8A5E` | `FRENDERING_OBJECT_VERSION_GUID` |

## Subsystem Version Thresholds

### FrameworkObjectVersion

| Constant | Value | Description |
|----------|-------|-------------|
| `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE` | 15 | Graph pin container type |
| `FFRAMEWORK_VERSION_PINS_STORE_FNAME` | 19 | Pins store FName |

### FUE5MainStreamObjectVersion

| Constant | Value | Description |
|----------|-------|-------------|
| `FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX` | 50 | Graph pin source index |

### FReleaseObjectVersion

| Constant | Value | Description |
|----------|-------|-------------|
| `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` | 10 | Pin type UObject wrapper |

### FUE5ReleaseStreamObjectVersion

| Constant | Value | Description |
|----------|-------|-------------|
| `FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION` | 36 | Float pin defaults serialized as single precision |

## Package Flags

| Constant | Value | Description |
|----------|-------|-------------|
| `PKG_Cooked` | `0x200` | Package is cooked |
| `PKG_UnversionedProperties` | `0x2000` | Uses unversioned property serialization |
| `PKG_FilterEditorOnly` | `0x80000000` | Filter editor-only objects |

## CPF_* Property Flags

Class Property Flags, used for property metadata.

| Constant | Value (hex) | Description |
|----------|-------------|-------------|
| `CPF_Edit` | `0x0000000000000001` | Editable |
| `CPF_ConstParm` | `0x0000000000000002` | Constant parameter |
| `CPF_BlueprintVisible` | `0x0000000000000004` | Blueprint visible |
| `CPF_ExportObject` | `0x0000000000000008` | Exportable object |
| `CPF_BlueprintReadOnly` | `0x0000000000000010` | Blueprint read-only |
| `CPF_BlueprintAuthorityOnly` | `0x0000000000000020` | Blueprint authority only |
| `CPF_EditFixedSize` | `0x0000000000000040` | Edit fixed size |
| `CPF_Parm` | `0x0000000000000080` | Parameter |
| `CPF_OutParm` | `0x0000000000000100` | Output parameter |
| `CPF_ZeroConstructor` | `0x0000000000000200` | Zero constructor |
| `CPF_ReturnParm` | `0x0000000000000400` | Return parameter |
| `CPF_Net` | `0x0000000000000800` | Network replication |
| `CPF_EditAnywhere` | `0x0000000000001000` | Edit anywhere |
| `CPF_Transient` | `0x0000000000002000` | Transient |
| `CPF_Config` | `0x0000000000004000` | Config |
| `CPF_DisableEditOnTemplate` | `0x0000000000008000` | Disable edit on template |
| `CPF_BlueprintReadWrite` | `0x0000000000010000` | Blueprint read-write |
| `CPF_DuplicateTransient` | `0x0000000000020000` | Duplicate transient |
| `CPF_NonPIEDuplicateTransient` | `0x0000000000040000` | Non-PIE duplicate transient |
| `CPF_EditConst` | `0x0000000000080000` | Edit const |
| `CPF_NoClear` | `0x0000000000200000` | No clear |
| `CPF_ReferencePersisted` | `0x0000000000400000` | Reference persisted |
| `CPF_SaveGame` | `0x0000000001000000` | Save game |
| `CPF_BlueprintAssignable` | `0x0000000002000000` | Blueprint assignable |
| `CPF_BlueprintCallable` | `0x0000000004000000` | Blueprint callable |
| `CPF_BlueprintPure` | `0x0000000008000000` | Blueprint pure |
| `CPF_BlueprintCompilerGenerated` | `0x0000000010000000` | Blueprint compiler generated |
| `CPF_NetSerialize` | `0x0000000020000000` | Network serialize |
| `CPF_RepNotify` | `0x0000000040000000` | Rep notify |
| `CPF_RepRetry` | `0x0000000080000000` | Rep retry |
| `CPF_Interp` | `0x0000000100000000` | Interpolation |
| `CPF_Constructed` | `0x0000000200000000` | Constructed |
| `CPF_Protected` | `0x0000000400000000` | Protected |
| `CPF_AdvancedDisplay` | `0x0000000800000000` | Advanced display |
| `CPF_AssetRegistrySearchable` | `0x0000001000000000` | Asset registry searchable |
| `CPF_ContainsInstancedReference` | `0x0000002000000000` | Contains instanced reference |
| `CPF_Deprecated` | `0x0000004000000000` | Deprecated |
| `CPF_IsPlainOldData` | `0x0000008000000000` | Plain old data type |
| `CPF_NoDestructor` | `0x0000010000000000` | No destructor |
| `CPF_HasGetValueTypeHash` | `0x0000020000000000` | Has GetValue hash |
| `CPF_NativeAccessSpecifierPublic` | `0x0000040000000000` | Native public access |
| `CPF_NativeAccessSpecifierProtected` | `0x0000080000000000` | Native protected access |
| `CPF_NativeAccessSpecifierPrivate` | `0x0000100000000000` | Native private access |
| `CPF_SkipSerialization` | `0x0000200000000000` | Skip serialization |
| `CPF_TextExportTransient` | `0x0000400000000000` | Text export transient |
| `CPF_NonTransactional` | `0x0000800000000000` | Non-transactional |
| `CPF_Required` | `0x0001000000000000` | Required |
| `CPF_ExposeOnSpawn` | `0x0002000000000000` | Expose on spawn |
| `CPF_PersistentInstance` | `0x0004000000000000` | Persistent instance |
| `CPF_TObjectPtr` | `0x0008000000000000` | TObjectPtr |
| `CPF_UObjectWrapper` | `0x0010000000000000` | UObject wrapper |
| `CPF_NaturalizePropertyIndex` | `0x0020000000000000` | Naturalize property index |
| `CPF_InstancedReference` | `0x0040000000000000` | Instanced reference |

### CPF Aliases

| Alias | Maps To | Description |
|-------|---------|-------------|
| `CPF_EditInstanceOnly` | `CPF_EditAnywhere` | Edit instance only (legacy API) |
| `CPF_ReferenceOnly` | `CPF_ReferencePersisted` | Reference only (legacy API) |
| `CPF_Replicated` | `CPF_Net` | Replicated (legacy API) |

## Blueprint Graph Parsing Collections

### Control Flow Nodes

```python
CONTROL_FLOW_NODES = frozenset({
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
})
```

### Start Event Types

```python
START_EVENT_TYPES = frozenset({
    "K2Node_Event",
    "K2Node_EnhancedInputAction",
    "K2Node_VariableSet",
    "K2Node_CustomEvent",
    "K2Node_FunctionEntry",
})
```

### Data Boundary Nodes

```python
DATA_BOUNDARY_NODES = frozenset({
    "K2Node_FunctionEntry",
    "K2Node_VariableSet",
})
```

## Mappings and Configuration

### EnhancedInput TriggerEvent Pin Mapping

```python
ETRIGGER_EVENT_PIN_MAP = {
    "Started": "Started",
    "Triggered": "Ongoing",
    "Completed": "Completed",
    "Exited": "Exited",
}
```

### Branch Type Mapping

```python
BRANCH_TYPE_MAP = {
    "K2Node_IfThenElse": "if_then_else",
    "K2Node_Switch": "switch",
    "K2Node_SwitchString": "switch_string",
    "K2Node_SwitchEnum": "switch_enum",
    "K2Node_SwitchInteger": "switch_integer",
    "K2Node_MacroInstance": "macro_instance",
}
```

### Graph Type Mapping

```python
GRAPH_TYPE_MAP = {
    "EdGraph": "event",
    "UberEdGraph": "uber",
}
```

### Output Format Configuration

```python
FORMAT_CONFIG = {
    "pin_reference_mode": "name",
}
```

## CLI Exit Codes

| Constant | Value | Description |
|----------|-------|-------------|
| `EXIT_SUCCESS` | 0 | Success |
| `EXIT_PARSE_ERROR` | 1 | Parse error |
| `EXIT_FILE_NOT_FOUND` | 2 | File not found |
| `EXIT_ARGUMENT_ERROR` | 3 | Argument error |
