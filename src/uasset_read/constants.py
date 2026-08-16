"""
uasset_read Constants Definition

Contains all version numbers, property type thresholds, and boundary constants.
Extracted from uasset_read.py (per D-11).
"""

# ============================================================================
# CLI Exit Codes
# ============================================================================

EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3

# ============================================================================
# Package file tags (from UE source code)
# ============================================================================

PACKAGE_FILE_TAG = 0x9E2A83C1       # Correct byte order magic tag
PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E  # Swapped byte order magic tag

# ============================================================================
# Version constants
# ============================================================================

UE5_VERSION_MIN = 0                # UE5 version minimum
UE5_LEGACY_VERSION = -9            # Fixed LegacyFileVersion for UE5.6+ files
# -8: FileVersionUE5 field added, -7: texture allocation info removed, -6: custom version serialization optimization
UE5_LEGACY_VERSIONS = frozenset({-6, -7, -8, UE5_LEGACY_VERSION})  # Supported UE5 LegacyFileVersion

# UE4 LegacyFileVersion (GUID-based custom versions)
# -3: GUID-based custom versions, has LegacyUE3Version
# -4: GUID-based custom versions, no LegacyUE3Version (removed UE3 version field)
# -5: GUID-based custom versions, has LegacyUE3Version (replaces UE3 version field)
UE4_LEGACY_VERSIONS = frozenset({-3, -4, -5})

# All supported LegacyFileVersion (UE4 + UE5)
SUPPORTED_LEGACY_VERSIONS = UE5_LEGACY_VERSIONS | UE4_LEGACY_VERSIONS

# ============================================================================
# CustomVersion GUIDs
# ============================================================================

FFRAMEWORK_OBJECT_VERSION_GUID = "CFFC743F-43B04480-939114DF-171D2073"

# ============================================================================
# Boundary validation constants (defensive programming)
# ============================================================================

MAX_NAME_COUNT = 10_000_000        # Maximum name table entries
MAX_IMPORT_COUNT = 1_000_000       # Maximum import table entries
MAX_EXPORT_COUNT = 1_000_000       # Maximum export table entries
MAX_TOTAL_OBJECT_COUNT = 500_000   # Maximum import + export combined entries
MAX_CUSTOM_VERSIONS = 10_000       # Maximum custom version entries
MAX_GENERATIONS = 10_000           # Maximum Generations table entries
MAX_COMPRESSED_CHUNKS = 100_000    # Maximum CompressedChunks entries
MAX_SOFT_PACKAGE_REFS = 1_000_000  # Maximum SoftPackageReferences entries
MMAP_THRESHOLD = 10 * 1024 * 1024  # 10MB - switch to mmap above this (lower threshold to reduce memory peak)
MAX_PROPERTY_COUNT = 10_000        # Property loop limit
MAX_RECURSION_DEPTH = 50           # Maximum property nesting recursion depth (prevents stack overflow from malicious/malformed assets)
MIN_UASSET_SIZE = 64               # Minimum legal .uasset file size (bytes)
                                      # Contains minimum of Tag(4) + version fields(16~20) + LicenseeVer(4) + Hash(20) + HeaderSize(4)
MAX_ARRAY_COUNT = 1_000_000       # Maximum ArrayProperty elements (per HIGH-07/35d-01)
MAX_ARRAY_DIM = 256               # Maximum array dimension in mapping property info
MAX_FSTRING_LENGTH = 10_000_000   # 10 MB — FString maximum length (UTF-8/UTF-16)

# ============================================================================
# PropertyTag flags
# ============================================================================

PROP_TAG_NONE = 0x00
PROP_TAG_HAS_ARRAY_INDEX = 0x01      # ArrayIndex field present
PROP_TAG_HAS_PROPERTY_GUID = 0x02    # PropertyGuid field present
PROP_TAG_HAS_EXTENSIONS = 0x04       # Extension data
PROP_TAG_HAS_BINARY_OR_NATIVE = 0x08 # Binary/native serialize
PROP_TAG_BOOL_TRUE = 0x10            # Bool value is true
PROP_TAG_SKIPPED_SERIALIZE = 0x20    # Skipped serialize

# ============================================================================
# PropertyTag version thresholds
# ============================================================================

PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012  # UE5 format switch threshold

# ============================================================================
# Package Flags (EPackageFlags)
# Source: UE source code ObjectMacros.h
# ============================================================================

PKG_None                        = 0x00000000  # No flags — only used in decode_package_flags
PKG_NewlyCreated                = 0x00000001  # Newly created package, not saved yet. In editor only.
PKG_ClientOptional              = 0x00000002  # Purely optional for clients.
PKG_ServerSideOnly              = 0x00000004  # Only needed on the server side.
PKG_CompiledIn                  = 0x00000010  # This package is from "compiled in" classes.
PKG_ForDiffing                  = 0x00000020  # This package was loaded just for the purposes of diffing
PKG_EditorOnly                  = 0x00000040  # This is editor-only package (for example: editor module script package)
PKG_Developer                   = 0x00000080  # Developer module
PKG_UncookedOnly                = 0x00000100  # Loaded only in uncooked builds (i.e. runtime in editor)
PKG_Cooked                      = 0x00000200  # Package is cooked
PKG_ContainsNoAsset             = 0x00000400  # Package doesn't contain any asset object (although asset tags can be present)
PKG_NotExternallyReferenceable  = 0x00000800  # Objects in this package cannot be referenced in a different plugin or mount point (i.e /Game -> /Engine)
PKG_AccessSpecifierEpicInternal = 0x00001000  # Objects in this package can only be referenced in a different plugin or mount point by Epic
PKG_UnversionedProperties       = 0x00002000  # Uses unversioned property serialization instead of versioned tagged property serialization
PKG_ContainsMapData             = 0x00004000  # Contains map data (UObjects only referenced by a single ULevel) but is stored in a different package
PKG_IsSaving                    = 0x00008000  # Temporarily set on a package while it is being saved.
PKG_Compiling                   = 0x00010000  # package is currently being compiled
PKG_ContainsMap                 = 0x00020000  # Set if the package contains a ULevel/ UWorld object
PKG_RequiresLocalizationGather  = 0x00040000  # Set if the package contains any data to be gathered by localization
PKG_LoadUncooked                = 0x00080000  # This package must be loaded uncooked from IoStore/ZenStore
PKG_PlayInEditor                = 0x00100000  # Set if the package was created for the purpose of PIE
PKG_ContainsScript              = 0x00200000  # Package is allowed to contain UClass objects
PKG_DisallowExport              = 0x00400000  # Editor should not export asset in this package
# 0x00800000, 0x01000000, 0x02000000, 0x04000000 — reserved/unused
PKG_CookGenerated               = 0x08000000  # This package was generated by the cooker and does not exist in the WorkspaceDomain
PKG_DynamicImports              = 0x10000000  # Obsolete (deprecated in UE 5.8)
PKG_RuntimeGenerated            = 0x20000000  # This package contains elements that are runtime generated, and may not follow standard loading order rules
PKG_ReloadingForCooker          = 0x40000000  # This package is reloading in the cooker, try to avoid getting data we will never need.
PKG_FilterEditorOnly            = 0x80000000  # Package has editor-only data filtered out

# Combined flag bits (UE source macro definitions)
PKG_TransientFlags = PKG_NewlyCreated | PKG_IsSaving | PKG_ReloadingForCooker
PKG_InMemoryOnly = PKG_CompiledIn | PKG_NewlyCreated


def decode_package_flags(flags: int) -> list[str]:
    """Decode PackageFlags bitmask into a list of human-readable flag names.

    Returns a list of set flag bit names, with unknown bits marked as 'Unknown_<hex>'.
    """
    result = []
    known_flags = [
        (PKG_NewlyCreated, "PKG_NewlyCreated"),
        (PKG_ClientOptional, "PKG_ClientOptional"),
        (PKG_ServerSideOnly, "PKG_ServerSideOnly"),
        (PKG_CompiledIn, "PKG_CompiledIn"),
        (PKG_ForDiffing, "PKG_ForDiffing"),
        (PKG_EditorOnly, "PKG_EditorOnly"),
        (PKG_Developer, "PKG_Developer"),
        (PKG_UncookedOnly, "PKG_UncookedOnly"),
        (PKG_Cooked, "PKG_Cooked"),
        (PKG_ContainsNoAsset, "PKG_ContainsNoAsset"),
        (PKG_NotExternallyReferenceable, "PKG_NotExternallyReferenceable"),
        (PKG_AccessSpecifierEpicInternal, "PKG_AccessSpecifierEpicInternal"),
        (PKG_UnversionedProperties, "PKG_UnversionedProperties"),
        (PKG_ContainsMapData, "PKG_ContainsMapData"),
        (PKG_IsSaving, "PKG_IsSaving"),
        (PKG_Compiling, "PKG_Compiling"),
        (PKG_ContainsMap, "PKG_ContainsMap"),
        (PKG_RequiresLocalizationGather, "PKG_RequiresLocalizationGather"),
        (PKG_LoadUncooked, "PKG_LoadUncooked"),
        (PKG_PlayInEditor, "PKG_PlayInEditor"),
        (PKG_ContainsScript, "PKG_ContainsScript"),
        (PKG_DisallowExport, "PKG_DisallowExport"),
        (PKG_CookGenerated, "PKG_CookGenerated"),
        (PKG_DynamicImports, "PKG_DynamicImports"),
        (PKG_RuntimeGenerated, "PKG_RuntimeGenerated"),
        (PKG_ReloadingForCooker, "PKG_ReloadingForCooker"),
        (PKG_FilterEditorOnly, "PKG_FilterEditorOnly"),
    ]
    remaining = flags
    for flag_value, flag_name in known_flags:
        if flag_value != 0 and (flags & flag_value) == flag_value:
            result.append(flag_name)
            remaining &= ~flag_value
    if remaining:
        result.append(f"Unknown_{remaining:#010x}")
    return result if result else ["PKG_None"]

# ============================================================================
# Blueprint graph parsing safety constants
# ============================================================================

MAX_PINS_PER_NODE = 1000               # Maximum pins per node
MAX_NODES_PER_GRAPH = 5000             # Maximum nodes per graph
MAX_SUBGRAPHS = 1000                   # Maximum subgraphs per graph (corrupted asset defense)
MAX_LINKEDTO_PER_PIN = 100             # Maximum connections per pin
MAX_FTEXT_CONSUMPTION = 10_240         # 10 KB — FText parsing safety net maximum byte consumption

# ============================================================================
# Lightweight tolerant parse threshold
# ============================================================================

LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD = 300  # Enable lightweight tolerant parse when export_count exceeds this value

# Special threshold for large asset files like ControlRig
# These files naturally have large export counts (RigVM nodes, RigHierarchy elements, etc.),
# and the default 300 threshold would falsely trigger lightweight parsing, causing blueprint data loss
# Reference: UE ControlRig.cpp / RigVM related modules
CONTROL_RIG_LARGE_FILE_THRESHOLD = 50000  # Lightweight parse threshold for ControlRig class files

# Known large file class name substrings — use high threshold when export class name contains any of these substrings
CONTROL_RIG_LARGE_FILE_CLASSES = frozenset({
    "ControlRig",
    "RigHierarchy",
    "RigVM",
    "RigUnit",
})

# ============================================================================
# FPropertyTypeName type node read limit
# ============================================================================

MAX_PROPERTY_TYPE_NODES = 50  # Max nodes in _read_property_type_name

# ============================================================================
# PropertyTag extension flags
# ============================================================================

PROP_EXT_SERIALIZE_CONTROL = 0x02  # SerializeControl bit in property extensions

# ============================================================================
# UE5 version constants (EUnrealEngineObjectUE5Version)
# ============================================================================

UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID = 1005
UE5_TRACK_OBJECT_EXPORT_IS_INHERITED = 1006
UE5_OPTIONAL_RESOURCES = 1003
UE5_NAMES_REFERENCED_FROM_EXPORT_DATA = 1001
UE5_PAYLOAD_TOC = 1002
UE5_LARGE_WORLD_COORDINATES = 1004
UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES = 1007
UE5_ADD_SOFTOBJECTPATH_LIST = 1008
UE5_DATA_RESOURCES = 1009
UE5_SCRIPT_SERIALIZATION_OFFSET = 1010
UE5_PROPERTY_TAG_EXTENSION = 1011
UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = PROPERTY_TAG_COMPLETE_TYPE_NAME  # alias (same value 1012)
UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES = 1013
UE5_METADATA_SERIALIZATION_OFFSET = 1014
UE5_VERSE_CELLS = 1015
UE5_PACKAGE_SAVED_HASH = 1016
UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION = 1017
UE5_IMPORT_TYPE_HIERARCHIES = 1018

# ============================================================================
# UE4 version constants (corresponding to EUnrealEngineObjectUE4Version)
# ============================================================================

UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 516
UE4_ADD_STRING_ASSET_REFERENCES_MAP = 384
UE4_SERIALIZE_TEXT_IN_PACKAGES = 459
UE4_ADDED_SEARCHABLE_NAMES = 510
UE4_ADDED_PACKAGE_OWNER = 518
UE4_NON_OUTER_PACKAGE_IMPORT = 520
UE4_NAME_HASHES_SERIALIZED = 504  # VER_UE4_NAME_HASHES_SERIALIZED: Add 4-byte hash after name table entries (UE 4.14+)
UE4_LOAD_FOR_EDITOR_GAME = 365
UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT = 485
UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 507
UE4_TemplateIndex_IN_COOKED_EXPORTS = 508
UE4_64BIT_EXPORTMAP_SERIALSIZES = 511

# ============================================================================
# Additional CustomVersion GUIDs
# ============================================================================
FUE5_MAINSTREAM_VERSION_GUID = "697DD581-E64F41AB-AA4A51EC-BEB7B628"
FRELEASE_OBJECT_VERSION_GUID = "9C54D522-A8264FBE-94210746-61B482D0"
FUE5RELEASESTREAM_OBJECT_VERSION_GUID = "D89B5E42-24BD4D46-8412ACA8-DF641779"

# Subsystem version GUIDs (extended version system coverage)
# UE source: Engine/Source/Runtime/Core/Private/UObject/DevObjectVersion.cpp (lines 174-357)
FBLUEPRINTS_OBJECT_VERSION_GUID = "B0D832E4-1F894F0D-ACCF7EB7-36FD4AA2"
FCORE_OBJECT_VERSION_GUID = "375EC13C-06E448FB-B50084F0-262A717E"
FEDITOR_OBJECT_VERSION_GUID = "E4B068ED-F49442E9-A231DA0B-2E46BB41"
FANIM_OBJECT_VERSION_GUID = "AF43A65D-7FD34947-98733E8E-D9C1BB05"
FPHYSICS_OBJECT_VERSION_GUID = "78F01B33-EBEA4F98-B9B484EA-CCB95AA2"
FRENDERING_OBJECT_VERSION_GUID = "12F88B9F-88754AFC-A67CD90C-383ABD29"

# Phase 1: High-priority missing version streams (LevelSequence/animation/destruction/physics and other common asset type dependencies)
FSEQUENCER_OBJECT_VERSION_GUID = "7B5AE74C-D2704C10-A9585798-0B212A5A"
FANIMPHYS_OBJECT_VERSION_GUID = "29E575DD-E0A34627-9D10D276-232CDCEA"
FDESTRUCTION_OBJECT_VERSION_GUID = "174F1F0B-B4C645A5-B13F2EE8-D0FB917D"
FEXTERNAL_PHYSICS_OBJECT_VERSION_GUID = "35F94A83-E258406C-A31809F5-9610247C"
FENTERPRISE_OBJECT_VERSION_GUID = "9DFFBCD6-494F0158-E2211282-3C92A888"
FVR_OBJECT_VERSION_GUID = "D7296918-1DD64BDD-9DE264A8-3CC13884"
FMOBILE_OBJECT_VERSION_GUID = "B02B49B5-BB2044E9-A30432B7-52E40360"
FCINECAMERA_OBJECT_VERSION_GUID = "B2E18506-4273CFC2-A54EF4BB-758BBA07"
FNIAGARA_OBJECT_VERSION_GUID = "F2AED0AC-9AFE416F-8664AA7F-FA26D6FC"

# Phase 2: P1 core version streams (LevelSequence/MorphTarget/RigVM/ControlRig)
FUE5_SPECIAL_PROJECT_STREAM_OBJECT_VERSION_GUID = "59DA5D52-12324948-B8785978-70B8E98B"
FRIGVM_OBJECT_VERSION_GUID = "DC49959B-53C04DE7-9156EA88-5E7C5D39"
FCONTROL_RIG_OBJECT_VERSION_GUID = "A7820CFB-20A74359-8C542C14-9623CF50"

# Phase 2: P2 specific asset type version streams
FNANITE_RESEARCH_STREAM_OBJECT_VERSION_GUID = "30D58BE3-95EA4282-A6E3B159-D8EBB06A"

# Phase 2: P3 plugin-level versions
FSKELETAL_MESH_CUSTOM_VERSION_GUID = "D78A4A00-E8584697-BAA819B5-487D46B4"
FNIAGARA_CUSTOM_VERSION_GUID = "FCF57AFA-50764283-B9A9E658-FFA02D32"
FINTERCHANGE_CUSTOM_VERSION_GUID = "92738C43-29884D9C-9A3D9BBE-6EFF9FC0"
FASSET_REGISTRY_VERSION_GUID = "717F9EE7-E9B0493A-88B39132-1B388107"
FCURVE_EXPRESSION_CUSTOM_VERSION_GUID = "A26D36AE-26935388-A8C5CB96-2B95B4AF"

# ============================================================================
# Blueprint metadata keys (UE editor internal fields)
# ============================================================================

BLUEPRINT_METADATA_KEYS = frozenset({
    "BlueprintSystemVersion",
    "GeneratedClass",
    "SimpleConstructionScript",
    "bCanEverTick",
    "bCanEverRender",
    "bStartWithTickEnabled",
    "bReplicates",
    "NetUpdateFrequency",
    "MinNetUpdateFrequency",
    "NetPriority",
})

# ============================================================================
# Control flow node set (used in blueprint graph parsing)
# ============================================================================

CONTROL_FLOW_NODES = frozenset({
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # Loop macros
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    # Multi-gate
    "K2Node_Sequence",
    "K2Node_MultiGate",
    # Selection
    "K2Node_Select",
    "K2Node_ExecutionSequence",
})

# ============================================================================
# Start event type set
# ============================================================================

START_EVENT_TYPES = frozenset({
    "K2Node_Event",
    "K2Node_EnhancedInputAction",
    "K2Node_VariableSet",
    "K2Node_CustomEvent",
    "K2Node_FunctionEntry",  # Function graph execution flow start point
})

# ============================================================================
# Data flow boundary node set
# ============================================================================

DATA_BOUNDARY_NODES = frozenset({
    "K2Node_FunctionEntry",  # Function parameter output as data flow start point
    "K2Node_VariableSet",    # Local variable definition (boundary)
})

# ============================================================================
# EnhancedInput TriggerEvent pin mapping
# ============================================================================

ETRIGGER_EVENT_PIN_MAP = {
    "Started": "Started",
    "Triggered": "Triggered",
    "Completed": "Completed",
    "Exited": "Exited",
}

# ============================================================================
# Branch type mapping
# ============================================================================

BRANCH_TYPE_MAP = {
    "K2Node_IfThenElse": "if_then_else",
    "K2Node_Switch": "switch",
    "K2Node_SwitchString": "switch_string",
    "K2Node_SwitchEnum": "switch_enum",
    "K2Node_SwitchInteger": "switch_integer",
    "K2Node_MacroInstance": "macro_instance",
    "K2Node_ForLoop": "for_loop",
    "K2Node_WhileLoop": "while_loop",
    "K2Node_DoOnce": "do_once",
    "K2Node_Sequence": "sequence",
    "K2Node_ExecutionSequence": "execution_sequence",
    "K2Node_MultiGate": "multi_gate",
    "K2Node_Select": "select",
}

# ============================================================================
# Output format configuration
# ============================================================================

FORMAT_CONFIG = {
    "pin_reference_mode": "name",
}

# ============================================================================
# Graph type mapping
# ============================================================================

GRAPH_TYPE_MAP = {
    "EdGraph": "event",
    "UberEdGraph": "uber",
}

# ============================================================================
# EPropertyFlags — CPF_* property flag constants
# Aligned with UE5 ObjectMacros.h EPropertyFlags enum (64-bit)
# Source: Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectMacros.h
# ============================================================================

CPF_Edit = 0x0000000000000001          # L434
CPF_ConstParm = 0x0000000000000002     # L435
CPF_BlueprintVisible = 0x0000000000000004  # L436
CPF_ExportObject = 0x0000000000000008  # L437
CPF_BlueprintReadOnly = 0x0000000000000010  # L438
CPF_Net = 0x0000000000000020          # L439
CPF_EditFixedSize = 0x0000000000000040  # L440
CPF_Parm = 0x0000000000000080         # L441
CPF_OutParm = 0x0000000000000100      # L442
CPF_ZeroConstructor = 0x0000000000000200  # L443
CPF_ReturnParm = 0x0000000000000400   # L444
CPF_DisableEditOnTemplate = 0x0000000000000800  # L445
CPF_NonNullable = 0x0000000000001000  # L446
CPF_Transient = 0x0000000000002000    # L447
CPF_Config = 0x0000000000004000       # L448
CPF_RequiredParm = 0x0000000000008000  # L449
CPF_DisableEditOnInstance = 0x0000000000010000  # L450
CPF_EditConst = 0x0000000000020000    # L451
CPF_GlobalConfig = 0x0000000000040000  # L452
CPF_InstancedReference = 0x0000000000080000  # L453
# L454: CPF_ExperimentalExternalObjects omitted — UE5 experimental, no UPROPERTY semantic mapping
CPF_DuplicateTransient = 0x0000000000200000  # L455
CPF_SaveGame = 0x0000000001000000     # L458
CPF_NoClear = 0x0000000002000000      # L459
CPF_Virtual = 0x0000000004000000      # L460
CPF_ReferenceParm = 0x0000000008000000  # L461
CPF_BlueprintAssignable = 0x0000000010000000  # L462
CPF_Deprecated = 0x0000000020000000   # L463
CPF_IsPlainOldData = 0x0000000040000000  # L464
CPF_RepSkip = 0x0000000080000000      # L465
CPF_RepNotify = 0x0000000100000000    # L466
CPF_Interp = 0x0000000200000000       # L467
CPF_NonTransactional = 0x0000000400000000  # L468
CPF_EditorOnly = 0x0000000800000000   # L469
CPF_NoDestructor = 0x0000001000000000  # L470
CPF_AutoWeak = 0x0000004000000000     # L472
CPF_ContainsInstancedReference = 0x0000008000000000  # L473
CPF_AssetRegistrySearchable = 0x0000010000000000  # L474
CPF_SimpleDisplay = 0x0000020000000000  # L475
CPF_AdvancedDisplay = 0x0000040000000000  # L476
CPF_Protected = 0x0000080000000000    # L477
CPF_BlueprintCallable = 0x0000100000000000  # L478
CPF_BlueprintAuthorityOnly = 0x0000200000000000  # L479
CPF_TextExportTransient = 0x0000400000000000  # L480
CPF_NonPIEDuplicateTransient = 0x0000800000000000  # L481
CPF_ExposeOnSpawn = 0x0001000000000000  # L482
CPF_PersistentInstance = 0x0002000000000000  # L483
CPF_UObjectWrapper = 0x0004000000000000  # L484
CPF_HasGetValueTypeHash = 0x0008000000000000  # L485
CPF_NativeAccessSpecifierPublic = 0x0010000000000000  # L486
CPF_NativeAccessSpecifierProtected = 0x0020000000000000  # L487
CPF_NativeAccessSpecifierPrivate = 0x0040000000000000  # L488
CPF_SkipSerialization = 0x0080000000000000  # L489
CPF_TObjectPtr = 0x0100000000000000   # L490
CPF_ExperimentalOverridableLogic = 0x0200000000000000  # L491
CPF_ExperimentalAlwaysOverriden = 0x0400000000000000  # L492
CPF_ExperimentalNeverOverriden = 0x0800000000000000  # L493
CPF_AllowSelfReference = 0x1000000000000000  # L494
CPF_ForcePostConstructLink = 0x2000000000000000  # L495

# ============================================================================
# Property type name → unversioned size mapping (property_parser._fixed_unversioned_size)
# ============================================================================

FIXED_UNVERSIONED_SIZES: dict[str, int] = {
    "BoolProperty": 4,
    "IntProperty": 4,
    "UInt32Property": 4,
    "FloatProperty": 4,
    "DoubleProperty": 8,
    "Int64Property": 8,
    "UInt64Property": 8,
    "Int16Property": 2,
    "UInt16Property": 2,
    "Int8Property": 1,
    "ByteProperty": 1,
    "ObjectProperty": 4,
    "ClassProperty": 4,
    "NameProperty": 8,
    "GuidProperty": 16,
}

# ============================================================================
# EPinContainerType integer → string mapping
# ============================================================================

CONTAINER_TYPE_MAP: dict[int, str] = {0: "None", 1: "Array", 2: "Set", 3: "Map"}
CONTAINER_TYPE_PREFIX: dict[int, str] = {1: "TArray", 2: "TSet", 3: "TMap"}

# ============================================================================
# UE PropertyTag sentinel value
# ============================================================================

UE_NONE_SENTINEL = "None"

# ============================================================================
# General safety count limits
# ============================================================================

MAX_SAFE_COUNT = 10_000  # Used for FText args / MulticastDelegate / FieldPath sub-element count validation

# ============================================================================
# GUID byte formatting
# ============================================================================

def format_guid_bytes(data: bytes, uppercase: bool = True) -> str:
    """Format 16 raw FGuid bytes into a stable 8-4-4-4-12 string."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 16:
        raise ValueError(
            f"GUID requires exactly 16 bytes, got {type(data).__name__} of length "
            f"{len(data) if isinstance(data, (bytes, bytearray)) else 'N/A'}"
        )
    text = (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )
    return text.upper() if uppercase else text


# ============================================================================
# UE5 large property type thresholds (#404)
# ============================================================================

MAX_REASONABLE_CAP = 100 * 1024 * 1024  # 100 MB — Standard property size cap

UE5_LARGE_PROPERTY_TYPES = frozenset({
    "BoneAnimationTracks",
    "PoseContainer",
    "ArrayConnectionMap",
    "RigVM",
    "MapProperty",
})

UE5_LARGE_PROPERTY_MAX_REASONABLE = 500 * 1024 * 1024  # 500 MB — UE5 large property size cap


def get_max_reasonable(property_type: str, engine_version: int) -> int:
    """Return reasonable size cap based on property type and engine version.

    For UE5 known large property types (BoneAnimationTracks, PoseContainer,
    ArrayConnectionMap, RigVM), relax threshold to 500MB.

    Args:
        property_type: Property type name (e.g., "IntProperty", "StructProperty")
        engine_version: Engine version (4 or 5)

    Returns:
        Maximum reasonable size (bytes) allowed for this property type
    """
    if engine_version >= 5 and property_type in UE5_LARGE_PROPERTY_TYPES:
        return UE5_LARGE_PROPERTY_MAX_REASONABLE
    return MAX_REASONABLE_CAP
