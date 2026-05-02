// types.hpp - Data structures for uasset parsing
// Translated from uasset_read.py lines 410-755

#ifndef UASSET_TYPES_HPP
#define UASSET_TYPES_HPP

#include <string>
#include <vector>
#include <optional>
#include <variant>
#include <array>
#include <cstdint>

namespace uasset {

// ============================================================================
// PackageIndex (FPackageIndex)
// ============================================================================

struct PackageIndex {
    int32_t index = 0;  // Raw signed value

    // Computed properties (mirroring Python @property)
    bool is_import() const { return index < 0; }
    bool is_export() const { return index > 0; }
    bool is_null() const { return index == 0; }

    int32_t to_import_index() const { return -index - 1; }
    int32_t to_export_index() const { return index - 1; }
};

// ============================================================================
// GenerationInfo
// ============================================================================

struct GenerationInfo {
    int32_t export_count = 0;
    int32_t name_count = 0;
};

// ============================================================================
// EngineVersion
// ============================================================================

struct EngineVersion {
    uint16_t major = 0;
    uint16_t minor = 0;
    uint16_t patch = 0;
    uint32_t changelist = 0;
    std::string branch;
};

// ============================================================================
// CustomVersion
// ============================================================================

struct CustomVersion {
    std::string guid;   // GUID hex string (16 bytes)
    int32_t version = 0;
};

// ============================================================================
// PackageFileSummary (~45 fields)
// ============================================================================

struct PackageFileSummary {
    // Core version fields
    uint32_t tag = 0;
    int32_t legacy_file_version = 0;
    int32_t file_version_ue4 = 0;
    int32_t legacy_ue3_version = 0;
    int32_t file_version_ue5 = 0;
    int32_t file_version_licensee = 0;

    // SavedHash (UE5 >= 1016)
    std::vector<uint8_t> saved_hash;  // FIoHash = 20 bytes

    // Header size
    int32_t total_header_size = 0;

    // Custom versions
    std::vector<CustomVersion> custom_versions;

    // Package info
    std::string package_name;
    uint32_t package_flags = 0;

    // Name table
    int32_t name_count = 0;
    int32_t name_offset = 0;

    // Soft object paths (UE5 >= 1008)
    int32_t soft_object_paths_count = 0;
    int32_t soft_object_paths_offset = 0;

    // Localization (UE4 >= 385)
    std::string localization_id;
    int32_t gatherable_text_data_count = 0;
    int32_t gatherable_text_data_offset = 0;

    // Export table (Export before Import!)
    int32_t export_count = 0;
    int32_t export_offset = 0;

    // Import table
    int32_t import_count = 0;
    int32_t import_offset = 0;

    // Cell Export/Import (UE5 >= 1015)
    int32_t cell_export_count = 0;
    int32_t cell_export_offset = 0;
    int32_t cell_import_count = 0;
    int32_t cell_import_offset = 0;

    // MetaData (UE5 >= 1014)
    int32_t metadata_offset = 0;

    // Depends
    int32_t depends_offset = 0;

    // Soft Package References (UE4 >= 382)
    int32_t soft_package_references_count = 0;
    int32_t soft_package_references_offset = 0;

    // Searchable Names (UE4 >= 508)
    int32_t searchable_names_offset = 0;

    // Thumbnail Table
    int32_t thumbnail_table_offset = 0;

    // Import Type Hierarchies (UE5 >= 1018)
    int32_t import_type_hierarchies_count = 0;
    int32_t import_type_hierarchies_offset = 0;

    // Persistent Guid (UE4 >= 516)
    std::string persistent_guid;

    // Generations
    std::vector<GenerationInfo> generations;

    // Engine versions
    EngineVersion saved_by_engine_version;
    EngineVersion compatible_with_engine_version;

    // Compression
    uint32_t compression_flags = 0;
    uint32_t package_source = 0;

    // Asset Registry
    int32_t asset_registry_data_offset = 0;

    // Bulk Data
    int64_t bulk_data_start_offset = 0;

    // World Tile Info (UE4 >= 223)
    int32_t world_tile_info_data_offset = 0;

    // Chunk IDs (UE4 >= 277)
    std::vector<std::string> chunk_ids;

    // Preload Dependencies (UE4 >= 505)
    int32_t preload_dependency_count = 0;
    int32_t preload_dependency_offset = 0;

    // NamesReferenced (UE5 >= 1001, at end!)
    int32_t names_referenced_from_export_data_count = 0;

    // Payload Toc (UE5 >= 1002)
    int64_t payload_toc_offset = 0;

    // Data Resource (UE5 >= 1009)
    int32_t data_resource_offset = 0;
};

// ============================================================================
// ObjectImport
// ============================================================================

struct ObjectImport {
    std::string class_package;
    std::string class_name;
    PackageIndex outer_index;
    std::string object_name;
};

// ============================================================================
// ObjectExport
// ============================================================================

struct ObjectExport {
    PackageIndex class_index;
    PackageIndex super_index;
    PackageIndex outer_index;
    std::string object_name;
    uint32_t object_flags = 0;
    int64_t serial_size = 0;
    int64_t serial_offset = 0;

    // UE5+ fields
    int64_t script_serial_size = 0;
    int64_t script_serial_offset = 0;

    // Properties (Phase 2)
    std::vector<struct PropertyValue> properties;
};

// Forward declare for PropertyValue
struct PropertyTag;

// ============================================================================
// PropertyValue Variant Type
// ============================================================================

// Using std::variant for type-safe property values
using PropertyValueVariant = std::variant<
    std::monostate,                              // null/unknown
    int64_t,                                     // IntProperty, Int64Property, ByteProperty
    double,                                      // FloatProperty, DoubleProperty
    bool,                                        // BoolProperty
    std::string,                                 // StrProperty, NameProperty
    int32_t,                                     // ObjectProperty (raw FPackageIndex)
    std::vector<PropertyValueVariant>           // ArrayProperty (nested)
>;

// ============================================================================
// PropertyValue
// ============================================================================

struct PropertyValue {
    std::string name;
    std::string type;
    PropertyValueVariant value;
    int32_t array_index = 0;
};

// ============================================================================
// PropertyTag
// ============================================================================

struct PropertyTag {
    std::string name;
    std::string type;
    int32_t size = 0;
    int32_t array_index = 0;
    uint8_t flags = 0;
    std::optional<std::array<uint8_t, 16>> property_guid;
    uint8_t bool_val = 0;
};

// ============================================================================
// FEdGraphPinType (Blueprint Pin Type)
// ============================================================================

struct FEdGraphPinType {
    std::string pin_category;
    std::string pin_sub_category;
    int32_t pin_sub_category_object = 0;
    uint8_t container_type = 0;  // 0=None, 1=Array, 2=Set, 3=Map
    bool is_reference = false;
    bool is_const = false;
    bool is_weak_pointer = false;
    bool is_uobject_wrapper = false;
};

// ============================================================================
// BlueprintVariable
// ============================================================================

struct BlueprintVariable {
    std::string var_name;
    FEdGraphPinType var_type;
    std::string category;
    uint64_t property_flags = 0;
    PropertyValueVariant default_value;
    std::string friendly_name;
};

// ============================================================================
// BlueprintMetadata
// ============================================================================

struct BlueprintMetadata {
    bool is_blueprint = false;
    std::optional<std::string> parent_class;
    std::vector<BlueprintVariable> variables;
    std::optional<std::string> detection_warning;
};

// ============================================================================
// ParseResult
// ============================================================================

struct ParseResult {
    std::optional<PackageFileSummary> summary;
    std::vector<std::string> name_map;
    std::vector<ObjectImport> import_map;
    std::vector<ObjectExport> export_map;
    std::vector<std::string> errors;
    std::optional<BlueprintMetadata> blueprint;
    bool is_success = false;

    // mmap tracking
    bool mmap_used = false;
    std::optional<std::string> mmap_warning;
    std::vector<std::string> warnings;
};

}  // namespace uasset

#endif  // UASSET_TYPES_HPP