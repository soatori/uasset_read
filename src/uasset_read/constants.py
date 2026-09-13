"""
uasset_read Constants Definition

Contains all version numbers, property type thresholds, and boundary constants.
Extracted from uasset_read.py (per D-11).
CLI exit codes live in cli.py, their only consumer.
"""

import uuid

# ============================================================================
# Package file tags (from UE source code)
# ============================================================================

PACKAGE_FILE_TAG = 0x9E2A83C1  # Correct byte order magic tag
PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E  # Swapped byte order magic tag

# ============================================================================
# Version constants
# ============================================================================

UE5_VERSION_MIN = 1000  # FPackageFileVersion::ToValue(): UE5 starts at ObjectVersion.h INITIAL_VERSION=1000
# -9: Fixed LegacyFileVersion for UE5.6+ files
# -8: FileVersionUE5 field added, -7: texture allocation info removed, -6: custom version serialization optimization
UE5_LEGACY_VERSIONS = frozenset({-6, -7, -8, -9})  # Supported UE5 LegacyFileVersion

# UE4 LegacyFileVersion (GUID-based custom versions)
# -3: GUID-based custom versions, has LegacyUE3Version
# -4: GUID-based custom versions, no LegacyUE3Version (removed UE3 version field)
# -5: GUID-based custom versions, has LegacyUE3Version (replaces UE3 version field)
UE4_LEGACY_VERSIONS = frozenset({-3, -4, -5})

# All supported LegacyFileVersion (UE4 + UE5)
SUPPORTED_LEGACY_VERSIONS = UE5_LEGACY_VERSIONS | UE4_LEGACY_VERSIONS

# ============================================================================
# Boundary validation constants (defensive programming)
# ============================================================================

MAX_NAME_COUNT = 10_000_000  # Maximum name table entries
MAX_IMPORT_COUNT = 1_000_000  # Maximum import table entries
MAX_EXPORT_COUNT = 1_000_000  # Maximum export table entries
MAX_TOTAL_OBJECT_COUNT = 500_000  # Maximum import + export combined entries
MAX_CUSTOM_VERSIONS = 10_000  # Maximum custom version entries
MAX_GENERATIONS = 10_000  # Maximum Generations table entries
MAX_COMPRESSED_CHUNKS = 100_000  # Maximum CompressedChunks entries
MAX_SOFT_PACKAGE_REFS = 1_000_000  # Maximum SoftPackageReferences entries
MMAP_THRESHOLD = 10 * 1024 * 1024  # 10MB - switch to mmap above this (lower threshold to reduce memory peak)
MAX_PROPERTY_COUNT = 10_000  # Property loop limit
MIN_UASSET_SIZE = 64  # Minimum legal .uasset file size (bytes)
# Contains minimum of Tag(4) + version fields(16~20) + LicenseeVer(4) + Hash(20) + HeaderSize(4)
MAX_ARRAY_COUNT = 1_000_000  # Maximum ArrayProperty elements (per HIGH-07/35d-01)
MAX_FSTRING_LENGTH = 10_000_000  # 10 MB — FString maximum length (UTF-8/UTF-16)

# ============================================================================
# PropertyTag flags
# ============================================================================

PROP_TAG_HAS_ARRAY_INDEX = 0x01  # ArrayIndex field present
PROP_TAG_HAS_PROPERTY_GUID = 0x02  # PropertyGuid field present
PROP_TAG_HAS_EXTENSIONS = 0x04  # Extension data
PROP_TAG_HAS_BINARY_OR_NATIVE = 0x08  # Binary/native serialize
PROP_TAG_BOOL_TRUE = 0x10  # Bool value is true
PROP_TAG_SKIPPED_SERIALIZE = 0x20  # Skipped serialize

# ============================================================================
# PropertyTag version thresholds
# ============================================================================

PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012  # UE5 format switch threshold

# ============================================================================
# Package Flags (EPackageFlags) — only flags with external imports kept at module level
# Source: UE source code ObjectMacros.h
# ============================================================================

PKG_Cooked = 0x00000200  # Package is cooked
PKG_UnversionedProperties = 0x00002000  # Uses unversioned property serialization
PKG_FilterEditorOnly = 0x80000000  # Package has editor-only data filtered out


# ============================================================================
# Blueprint graph parsing safety constants
# ============================================================================

MAX_PINS_PER_NODE = 1000  # Maximum pins per node
MAX_NODES_PER_GRAPH = 5000  # Maximum nodes per graph
MAX_SUBGRAPHS = 1000  # Maximum subgraphs per graph (corrupted asset defense)
MAX_LINKEDTO_PER_PIN = 100  # Maximum connections per pin
MAX_FTEXT_CONSUMPTION = 10_240  # 10 KB — FText parsing safety net maximum byte consumption

# ============================================================================
# FPropertyTypeName type node read limit
# ============================================================================

MAX_PROPERTY_TYPE_NODES = 50  # Max nodes in _read_property_type_name

# ============================================================================
# PropertyTag extension flags
# ============================================================================

PROP_EXT_SERIALIZE_CONTROL = 0x02  # SerializeControl bit in property extensions
PROP_EXT_HAS_EXTERNAL_OBJECTS = 0x04  # EPropertyTagExtension::HasExternalsObjects (PropertyTag.cpp:44-53)

# ============================================================================
# UE5 version constants (EUnrealEngineObjectUE5Version)
# ============================================================================

UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID = 1005
UE5_TRACK_OBJECT_EXPORT_IS_INHERITED = 1006
UE5_OPTIONAL_RESOURCES = 1003
UE5_NAMES_REFERENCED_FROM_EXPORT_DATA = 1001
UE5_PAYLOAD_TOC = 1002
UE5_LARGE_WORLD_COORDINATES = 1004
UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES = 1007  # Replace FName asset path with FTopLevelAssetPath
UE5_ADD_SOFTOBJECTPATH_LIST = 1008
UE5_DATA_RESOURCES = 1009
UE5_SCRIPT_SERIALIZATION_OFFSET = 1010
UE5_PROPERTY_TAG_EXTENSION = 1011
UE5_METADATA_SERIALIZATION_OFFSET = 1014
UE5_VERSE_CELLS = 1015
UE5_PACKAGE_SAVED_HASH = 1016
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
UE4_WORLD_LEVEL_INFO = 224
UE4_ADDED_CHUNKID_TO_ASSETDATA_AND_UPACKAGE = 278
UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS = 326
UE4_ENGINE_VERSION_OBJECT = 335
UE4_ADDED_COMPATIBLE_WITH_ENGINE_VERSION = 443

FIXED_UNVERSIONED_SIZES: dict[str, int] = {
    "BoolProperty": 1,  # PropertyBool.cpp SerializeItem: unversioned bool is one uint8
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
    text = str(uuid.UUID(bytes=bytes(data[:16])))
    return text.upper() if uppercase else text


# ============================================================================
# UE5 large property type thresholds (#404)
# ============================================================================

MAX_REASONABLE_CAP = 100 * 1024 * 1024  # 100 MB — Standard property size cap

UE5_LARGE_PROPERTY_TYPES = frozenset(
    {
        "BoneAnimationTracks",
        "PoseContainer",
        "ArrayConnectionMap",
        "RigVM",
        "MapProperty",
    }
)

UE5_LARGE_PROPERTY_MAX_REASONABLE = 500 * 1024 * 1024  # 500 MB — UE5 large property size cap

# ============================================================================
# UE5 large property size cap selection
# ============================================================================


def get_max_reasonable(property_type: str) -> int:
    """Return reasonable size cap based on property type.

    UE5 known large property types relax to the 500MB cap; everything else
    stays at the standard 100MB cap.
    """
    if property_type in UE5_LARGE_PROPERTY_TYPES:
        return UE5_LARGE_PROPERTY_MAX_REASONABLE
    return MAX_REASONABLE_CAP
