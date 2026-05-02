// constants.hpp - UE version constants and magic tags
// Translated from uasset_read.py lines 28-95

#ifndef UASSET_CONSTANTS_HPP
#define UASSET_CONSTANTS_HPP

#include <cstdint>

namespace uasset {

// ============================================================================
// Magic Tags (PackageFileSummary.h)
// ============================================================================

constexpr uint32_t PACKAGE_FILE_TAG = 0x9E2A83C1;        // Correct byte order magic
constexpr uint32_t PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E; // Swapped byte order magic

// ============================================================================
// Version Ranges
// ============================================================================

constexpr int32_t UE5_VERSION_MIN = 0;           // UE5 minimum version
constexpr int32_t LEGACY_FILE_VERSION_MIN = -9;  // LegacyFileVersion lower bound
constexpr int32_t LEGACY_FILE_VERSION_MAX = -2;  // LegacyFileVersion upper bound

// ============================================================================
// Bounds Validation Constants (WR-01 mitigation)
// ============================================================================

constexpr int32_t MAX_NAME_COUNT = 10000000;       // Maximum name table entries
constexpr int32_t MAX_IMPORT_COUNT = 1000000;      // Maximum import table entries
constexpr int32_t MAX_EXPORT_COUNT = 1000000;      // Maximum export table entries
constexpr int32_t MAX_CUSTOM_VERSIONS = 10000;     // Maximum custom version entries
constexpr int32_t MAX_PROPERTY_COUNT = 10000;      // D-09: property loop limit

// ============================================================================
// Memory-mapped File Threshold (SAFE-03, D-01)
// ============================================================================

constexpr size_t MMAP_THRESHOLD = 50 * 1024 * 1024;  // 50MB - switch to mmap above this

// ============================================================================
// PropertyTag Flags (PropertyTag.h lines 17-26)
// ============================================================================

constexpr uint8_t PROP_TAG_NONE = 0x00;
constexpr uint8_t PROP_TAG_HAS_ARRAY_INDEX = 0x01;      // ArrayIndex field present
constexpr uint8_t PROP_TAG_HAS_PROPERTY_GUID = 0x02;    // PropertyGuid field present
constexpr uint8_t PROP_TAG_HAS_EXTENSIONS = 0x04;       // Extension data
constexpr uint8_t PROP_TAG_HAS_BINARY_OR_NATIVE = 0x08; // Binary/native serialize
constexpr uint8_t PROP_TAG_BOOL_TRUE = 0x10;            // Bool value is true
constexpr uint8_t PROP_TAG_SKIPPED_SERIALIZE = 0x20;    // Skipped serialize

// ============================================================================
// PropertyTag Version Thresholds (PropertyTag.cpp)
// ============================================================================

constexpr int32_t PROPERTY_TAG_COMPLETE_TYPE_NAME = 1000;  // UE5 format switch
constexpr int32_t VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG = 500;
constexpr int32_t VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG = 510;

// ============================================================================
// Package Flags (ObjectMacros.h)
// ============================================================================

constexpr uint32_t PKG_Cooked = 0x200;  // Package is cooked

// ============================================================================
// UE5 Version Constants (EUnrealEngineObjectUE5Version)
// ============================================================================

constexpr int32_t UE5_NAMES_REFERENCED_FROM_EXPORT_DATA = 1001;
constexpr int32_t UE5_PAYLOAD_TOC = 1002;
constexpr int32_t UE5_LARGE_WORLD_COORDINATES = 1004;
constexpr int32_t UE5_ADD_SOFTOBJECTPATH_LIST = 1008;
constexpr int32_t UE5_DATA_RESOURCES = 1009;
constexpr int32_t UE5_SCRIPT_SERIALIZATION_OFFSET = 1010;
constexpr int32_t UE5_PROPERTY_TAG_EXTENSION = 1011;
constexpr int32_t UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012;
constexpr int32_t UE5_ASSETREGISTRY_PACKAGEBUILDDEPENDENCIES = 1013;
constexpr int32_t UE5_METADATA_SERIALIZATION_OFFSET = 1014;
constexpr int32_t UE5_VERSE_CELLS = 1015;
constexpr int32_t UE5_PACKAGE_SAVED_HASH = 1016;
constexpr int32_t UE5_OS_SUB_OBJECT_SHADOW_SERIALIZATION = 1017;
constexpr int32_t UE5_IMPORT_TYPE_HIERARCHIES = 1018;

// ============================================================================
// UE4 Version Constants (EUnrealEngineObjectUE4Version)
// ============================================================================

constexpr int32_t UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 385;
constexpr int32_t UE4_SERIALIZE_TEXT_IN_PACKAGES = 401;
constexpr int32_t UE4_WORLD_LEVEL_INFO = 223;
constexpr int32_t UE4_ADDED_CHUNKID = 277;
constexpr int32_t UE4_CHANGED_CHUNKID_TO_ARRAY = 341;
constexpr int32_t UE4_ENGINE_VERSION_OBJECT = 334;
constexpr int32_t UE4_ADD_STRING_ASSET_REFERENCES_MAP = 382;
constexpr int32_t UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION = 442;
constexpr int32_t UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 505;
constexpr int32_t UE4_ADDED_SEARCHABLE_NAMES = 508;
constexpr int32_t UE4_ADDED_PACKAGE_OWNER = 516;
constexpr int32_t UE4_NON_OUTER_PACKAGE_IMPORT = 518;
constexpr int32_t UE4_NAME_HASHES_SERIALIZED = 502;

// ============================================================================
// CLI Exit Codes
// ============================================================================

constexpr int EXIT_SUCCESS = 0;
constexpr int EXIT_PARSE_ERROR = 1;
constexpr int EXIT_FILE_NOT_FOUND = 2;
constexpr int EXIT_ARGUMENT_ERROR = 3;

}  // namespace uasset

#endif  // UASSET_CONSTANTS_HPP