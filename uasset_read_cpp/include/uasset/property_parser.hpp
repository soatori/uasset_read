// property_parser.hpp - Property parsing declarations
// Translated from uasset_read.py lines 1742-2160

#ifndef UASSET_PROPERTY_PARSER_HPP
#define UASSET_PROPERTY_PARSER_HPP

#include "archive.hpp"
#include "types.hpp"
#include "constants.hpp"

#include <vector>
#include <string>

namespace uasset {

// ============================================================================
// PropertyTag Reading
// ============================================================================

// Check if UE5 complete type name format should be used
bool use_complete_type_name(int32_t legacy_version, int32_t ue5_version);

// Read PropertyTag structure
PropertyTag read_property_tag(
    FArchive& archive,
    const std::vector<std::string>& name_map,
    int32_t legacy_version,
    int32_t ue5_version
);

// ============================================================================
// Property Value Parsing
// ============================================================================

// Parse property value based on type
PropertyValueVariant parse_property_value(
    const PropertyTag& tag,
    FArchive& archive,
    const std::vector<std::string>& name_map,
    const std::vector<ObjectExport>& export_map
);

// ============================================================================
// Type-Specific Parsers
// ============================================================================

bool parse_bool_property(const PropertyTag& tag, FArchive& archive);
int64_t parse_int_property(const PropertyTag& tag, FArchive& archive);
double parse_float_property(const PropertyTag& tag, FArchive& archive);
std::string parse_str_property(const PropertyTag& tag, FArchive& archive);
std::string parse_name_property(const PropertyTag& tag, FArchive& archive, const std::vector<std::string>& name_map);
int32_t parse_object_property(const PropertyTag& tag, FArchive& archive);

// Array property (recursive, with depth limit)
PropertyValueVariant parse_array_property(
    const PropertyTag& tag,
    FArchive& archive,
    const std::vector<std::string>& name_map,
    const std::vector<ObjectExport>& export_map,
    int depth = 0
);

// ============================================================================
// Property Parsing from Export
// ============================================================================

// Parse all properties from an export
std::vector<PropertyValue> parse_properties_from_export(
    const ObjectExport& export,
    FArchive& archive,
    const PackageFileSummary& summary,
    const std::vector<std::string>& name_map,
    const std::vector<ObjectExport>& export_map
);

}  // namespace uasset

#endif  // UASSET_PROPERTY_PARSER_HPP