// property_parser.cpp - Property parsing implementation
// Translated from uasset_read.py lines 1742-2160

#include "property_parser.hpp"
#include "archive.hpp"
#include "exceptions.hpp"
#include "constants.hpp"

#include <algorithm>
#include <sstream>
#include <functional>

namespace uasset {

// ============================================================================
// Constants
// ============================================================================

constexpr int MAX_DEPTH = 10;  // D-18: nesting depth limit

// ============================================================================
// PropertyTag Reading
// ============================================================================

bool use_complete_type_name(int32_t legacy_version, int32_t ue5_version) {
    return legacy_version <= -8 && ue5_version >= PROPERTY_TAG_COMPLETE_TYPE_NAME;
}

PropertyTag read_property_tag(
    FArchive& archive,
    const std::vector<std::string>& name_map,
    int32_t legacy_version,
    int32_t ue5_version
) {
    PropertyTag tag;
    tag.name = archive.read_name(name_map);

    if (use_complete_type_name(legacy_version, ue5_version)) {
        // UE5 new format
        tag.type = archive.read_fstring();
        tag.size = archive.read_i32();
        archive.validate_size(tag.size, tag.name);
        tag.flags = archive.read_u8();

        if (tag.flags & PROP_TAG_HAS_ARRAY_INDEX) {
            tag.array_index = archive.read_i32();
        }

        if (tag.flags & PROP_TAG_HAS_PROPERTY_GUID) {
            auto guid_bytes = archive.read(16);
            std::array<uint8_t, 16> guid_arr;
            std::copy(guid_bytes.begin(), guid_bytes.end(), guid_arr.begin());
            tag.property_guid = guid_arr;
        }

        if (tag.flags & PROP_TAG_BOOL_TRUE) {
            tag.bool_val = 1;
        }
    } else {
        // UE4 legacy format
        tag.type = archive.read_name(name_map);
        tag.size = archive.read_i32();
        archive.validate_size(tag.size, tag.name);
        tag.array_index = archive.read_i32();

        if (tag.type == "BoolProperty") {
            tag.bool_val = archive.read_u8();
        }
    }

    return tag;
}

// ============================================================================
// Type-Specific Parsers
// ============================================================================

bool parse_bool_property(const PropertyTag& tag, FArchive& archive) {
    return tag.bool_val != 0;
}

int64_t parse_int_property(const PropertyTag& tag, FArchive& archive) {
    if (tag.type == "Int64Property") {
        return archive.read_i64();
    } else if (tag.type == "Int16Property") {
        auto data = archive.read(2);
        return static_cast<int64_t>(
            static_cast<int16_t>(data[0] | (data[1] << 8))
        );
    } else if (tag.type == "Int8Property" || tag.type == "ByteProperty") {
        return archive.read_u8();
    }
    // IntProperty (default)
    return archive.read_i32();
}

double parse_float_property(const PropertyTag& tag, FArchive& archive) {
    if (tag.type == "DoubleProperty") {
        return archive.read_f64();
    }
    // FloatProperty (default)
    return archive.read_f32();
}

std::string parse_str_property(const PropertyTag& tag, FArchive& archive) {
    return archive.read_fstring();
}

std::string parse_name_property(const PropertyTag& tag, FArchive& archive, const std::vector<std::string>& name_map) {
    return archive.read_name(name_map);
}

int32_t parse_object_property(const PropertyTag& tag, FArchive& archive) {
    return archive.read_i32();
}

// ============================================================================
// Array Property Parsing (D-16)
// ============================================================================

// Helper to get inner type from array type (simplified)
std::string get_inner_type(const std::string& array_type) {
    // Phase 3 simplified: assume IntProperty
    // Complete implementation would parse TypeName parameter
    return "IntProperty";
}

PropertyValueVariant parse_array_property(
    const PropertyTag& tag,
    FArchive& archive,
    const std::vector<std::string>& name_map,
    const std::vector<ObjectExport>& export_map,
    int depth
) {
    if (depth > MAX_DEPTH) {
        throw ParseError("ArrayProperty nesting depth " + std::to_string(depth) +
                        " exceeds maximum " + std::to_string(MAX_DEPTH));
    }

    int32_t count = archive.read_i32();
    std::vector<PropertyValueVariant> elements;

    for (int32_t i = 0; i < count; ++i) {
        // Simplified: assume basic type elements
        PropertyTag inner_tag;
        inner_tag.name = tag.name + "[" + std::to_string(i) + "]";
        inner_tag.type = get_inner_type(tag.type);
        inner_tag.size = count > 0 ? tag.size / count : 0;

        auto inner_value = parse_property_value(inner_tag, archive, name_map, export_map);
        elements.push_back(inner_value);
    }

    return elements;
}

// ============================================================================
// Property Value Parsing
// ============================================================================

PropertyValueVariant parse_property_value(
    const PropertyTag& tag,
    FArchive& archive,
    const std::vector<std::string>& name_map,
    const std::vector<ObjectExport>& export_map
) {
    // Type dispatch table
    if (tag.type == "BoolProperty") {
        return parse_bool_property(tag, archive);
    }
    if (tag.type == "IntProperty" || tag.type == "Int64Property" ||
        tag.type == "Int16Property" || tag.type == "Int8Property" ||
        tag.type == "ByteProperty") {
        return parse_int_property(tag, archive);
    }
    if (tag.type == "FloatProperty" || tag.type == "DoubleProperty") {
        return parse_float_property(tag, archive);
    }
    if (tag.type == "StrProperty") {
        return parse_str_property(tag, archive);
    }
    if (tag.type == "NameProperty") {
        return parse_name_property(tag, archive, name_map);
    }
    if (tag.type == "ObjectProperty") {
        return parse_object_property(tag, archive);
    }
    if (tag.type == "ArrayProperty") {
        return parse_array_property(tag, archive, name_map, export_map);
    }

    // Unknown type: return null
    return std::monostate{};
}

// ============================================================================
// Property Parsing from Export
// ============================================================================

std::vector<PropertyValue> parse_properties_from_export(
    const ObjectExport& export,
    FArchive& archive,
    const PackageFileSummary& summary,
    const std::vector<std::string>& name_map,
    const std::vector<ObjectExport>& export_map
) {
    archive.seek(export.serial_offset);

    std::vector<PropertyValue> properties;
    int32_t property_count = 0;

    while (property_count < MAX_PROPERTY_COUNT) {
        ++property_count;

        try {
            PropertyTag tag = read_property_tag(
                archive, name_map,
                summary.legacy_file_version,
                summary.file_version_ue5
            );

            // Sentinel: Name == "None"
            if (tag.name == "None") {
                break;
            }

            int64_t start_pos = archive.tell();

            // Parse value
            PropertyValueVariant value = parse_property_value(tag, archive, name_map, export_map);

            // Boundary validation
            int64_t expected_end = start_pos + tag.size;
            int64_t current_pos = archive.tell();
            if (current_pos != expected_end) {
                archive.seek(expected_end);
            }

            PropertyValue prop;
            prop.name = tag.name;
            prop.type = tag.type;
            prop.value = value;
            prop.array_index = tag.array_index;
            properties.push_back(prop);

        } catch (const ParseError& e) {
            // D-19: Smart continue - record warning
            PropertyValue prop;
            prop.name = "ParseError";
            prop.type = "Warning";
            prop.value = "Property skipped: " + std::string(e.what());
            properties.push_back(prop);
            break;
        }
    }

    return properties;
}

}  // namespace uasset