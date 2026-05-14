// output.cpp - Output formatting implementation
// Translated from uasset_read.py lines 2265-2615

#include "output.hpp"
#include "property_parser.hpp"

#include <sstream>
#include <iomanip>
#include <variant>

namespace uasset {

// ============================================================================
// JSON Utilities
// ============================================================================

std::string json_escape(const std::string& str) {
    std::ostringstream oss;
    for (char c : str) {
        switch (c) {
            case '"':  oss << "\\\""; break;
            case '\\': oss << "\\\\"; break;
            case '\b': oss << "\\b";  break;
            case '\f': oss << "\\f";  break;
            case '\n': oss << "\\n";  break;
            case '\r': oss << "\\r";  break;
            case '\t': oss << "\\t";  break;
            default:
                if (c >= 0 && c < 32) {
                    oss << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                        << static_cast<int>(c);
                } else {
                    oss << c;
                }
        }
    }
    return oss.str();
}

std::string variant_to_json(const PropertyValueVariant& value) {
    if (std::holds_alternative<std::monostate>(value)) {
        return "null";
    }
    if (std::holds_alternative<int64_t>(value)) {
        return std::to_string(std::get<int64_t>(value));
    }
    if (std::holds_alternative<double>(value)) {
        std::ostringstream oss;
        oss << std::get<double>(value);
        return oss.str();
    }
    if (std::holds_alternative<bool>(value)) {
        return std::get<bool>(value) ? "true" : "false";
    }
    if (std::holds_alternative<std::string>(value)) {
        return "\"" + json_escape(std::get<std::string>(value)) + "\"";
    }
    if (std::holds_alternative<int32_t>(value)) {
        return std::to_string(std::get<int32_t>(value));
    }
    if (std::holds_alternative<std::vector<PropertyValueVariant>>(value)) {
        const auto& arr = std::get<std::vector<PropertyValueVariant>>(value);
        std::ostringstream oss;
        oss << "[";
        for (size_t i = 0; i < arr.size(); ++i) {
            if (i > 0) oss << ", ";
            oss << variant_to_json(arr[i]);
        }
        oss << "]";
        return oss.str();
    }
    return "null";
}

// ============================================================================
// Resolve FPackageIndex
// ============================================================================

std::string resolve_fpackage_index_json(const PackageIndex& idx, const ParseResult& result) {
    std::ostringstream oss;
    oss << "{";

    if (idx.is_null()) {
        oss << "\"raw\":0,\"resolved\":null,\"kind\":\"null\"";
    } else if (idx.is_import()) {
        int32_t import_idx = idx.to_import_index();
        oss << "\"raw\":" << idx.index << ",";
        if (import_idx >= 0 && import_idx < static_cast<int32_t>(result.import_map.size())) {
            oss << "\"resolved\":\"" << json_escape(result.import_map[import_idx].object_name) << "\"";
        } else {
            oss << "\"resolved\":null";
        }
        oss << ",\"kind\":\"import\"";
    } else if (idx.is_export()) {
        int32_t export_idx = idx.to_export_index();
        oss << "\"raw\":" << idx.index << ",";
        if (export_idx >= 0 && export_idx < static_cast<int32_t>(result.export_map.size())) {
            oss << "\"resolved\":\"" << json_escape(result.export_map[export_idx].object_name) << "\"";
        } else {
            oss << "\"resolved\":null";
        }
        oss << ",\"kind\":\"export\"";
    } else {
        oss << "\"raw\":" << idx.index << ",\"resolved\":null,\"kind\":\"unknown\"";
    }

    oss << "}";
    return oss.str();
}

// ============================================================================
// Format Properties
// ============================================================================

std::string format_properties_json(const std::vector<PropertyValue>& properties) {
    if (properties.empty()) {
        return "[]";
    }

    std::ostringstream oss;
    oss << "[";
    for (size_t i = 0; i < properties.size(); ++i) {
        if (i > 0) oss << ", ";
        const auto& prop = properties[i];
        oss << "{";
        oss << "\"name\":\"" << json_escape(prop.name) << "\",";
        oss << "\"type\":\"" << json_escape(prop.type) << "\",";
        oss << "\"value\":" << variant_to_json(prop.value) << ",";
        oss << "\"array_index\":" << prop.array_index;
        oss << "}";
    }
    oss << "]";
    return oss.str();
}

// ============================================================================
// Format Blueprint
// ============================================================================

std::string format_blueprint_json(const BlueprintMetadata& blueprint) {
    std::ostringstream oss;
    oss << "{";

    // Parent class
    if (blueprint.parent_class) {
        oss << "\"parent_class\":\"" << json_escape(*blueprint.parent_class) << "\",";
    } else {
        oss << "\"parent_class\":null,";
    }

    // Variables
    oss << "\"variables\":[";
    for (size_t i = 0; i < blueprint.variables.size(); ++i) {
        if (i > 0) oss << ", ";
        const auto& var = blueprint.variables[i];
        oss << "{";
        oss << "\"name\":\"" << json_escape(var.var_name) << "\",";
        oss << "\"type\":{";
        oss << "\"pin_category\":\"" << json_escape(var.var_type.pin_category) << "\",";
        oss << "\"pin_sub_category\":\"" << json_escape(var.var_type.pin_sub_category) << "\",";
        oss << "\"container_type\":" << static_cast<int>(var.var_type.container_type) << ",";
        oss << "\"is_reference\":" << (var.var_type.is_reference ? "true" : "false") << ",";
        oss << "\"is_const\":" << (var.var_type.is_const ? "true" : "false");
        oss << "},";
        oss << "\"category\":\"" << json_escape(var.category) << "\",";
        oss << "\"property_flags\":" << var.property_flags << ",";
        oss << "\"default_value\":" << variant_to_json(var.default_value) << ",";
        oss << "\"friendly_name\":\"" << json_escape(var.friendly_name) << "\"";
        oss << "}";
    }
    oss << "],";

    // Detection warning
    if (blueprint.detection_warning) {
        oss << "\"detection_warning\":\"" << json_escape(*blueprint.detection_warning) << "\"";
    } else {
        oss << "\"detection_warning\":null";
    }

    oss << "}";
    return oss.str();
}

// ============================================================================
// Format Exports
// ============================================================================

std::string format_exports_json(const ParseResult& result) {
    std::ostringstream oss;
    oss << "[";

    for (size_t i = 0; i < result.export_map.size(); ++i) {
        if (i > 0) oss << ", ";

        const auto& exp = result.export_map[i];
        auto class_name = get_asset_class(exp, result.import_map, result.export_map);

        oss << "{";
        oss << "\"index\":" << i << ",";
        oss << "\"name\":\"" << json_escape(exp.object_name) << "\",";
        oss << "\"class\":";
        if (class_name) {
            oss << "\"" << json_escape(*class_name) << "\"";
        } else {
            oss << "null";
        }
        oss << ",\"serial_size\":" << exp.serial_size << ",";
        oss << "\"properties\":" << format_properties_json(exp.properties) << ",";
        oss << "\"outer_index\":" << resolve_fpackage_index_json(exp.outer_index, result) << ",";
        oss << "\"super_index\":" << resolve_fpackage_index_json(exp.super_index, result);

        // Parent class from blueprint
        if (result.blueprint && result.blueprint->is_blueprint) {
            oss << ",\"parent_class\":";
            if (result.blueprint->parent_class) {
                oss << "\"" << json_escape(*result.blueprint->parent_class) << "\"";
            } else {
                oss << "null";
            }
        }

        oss << "}";
    }

    oss << "]";
    return oss.str();
}

// ============================================================================
// Format Full JSON
// ============================================================================

std::string format_json_full(const ParseResult& result) {
    std::ostringstream oss;
    oss << "{";

    // Summary
    oss << "\"summary\":{";
    if (result.summary) {
        const auto& s = *result.summary;
        oss << "\"version_ue4\":" << s.file_version_ue4 << ",";
        oss << "\"version_ue5\":" << s.file_version_ue5 << ",";
        oss << "\"legacy_version\":" << s.legacy_file_version << ",";
        oss << "\"package_flags\":" << s.package_flags << ",";
        oss << "\"package_name\":\"" << json_escape(s.package_name) << "\"";
    } else {
        oss << "\"version_ue4\":0,\"version_ue5\":0,\"legacy_version\":0,";
        oss << "\"package_flags\":0,\"package_name\":\"\"";
    }
    oss << "},";

    // Exports
    oss << "\"exports\":" << format_exports_json(result) << ",";

    // Blueprint metadata
    oss << "\"blueprint_metadata\":";
    if (result.blueprint) {
        oss << format_blueprint_json(*result.blueprint);
    } else {
        oss << "null";
    }
    oss << ",";

    // Errors
    oss << "\"errors\":[";
    for (size_t i = 0; i < result.errors.size(); ++i) {
        if (i > 0) oss << ", ";
        oss << "\"" << json_escape(result.errors[i]) << "\"";
    }
    oss << "]";

    oss << "}";
    return oss.str();
}

// ============================================================================
// Format Summary JSON
// ============================================================================

std::string format_json_summary(const ParseResult& result) {
    std::ostringstream oss;
    oss << "{";

    // Version
    oss << "\"version\":{";
    if (result.summary) {
        const auto& s = *result.summary;
        oss << "\"ue4\":" << s.file_version_ue4 << ",";
        oss << "\"ue5\":" << (s.file_version_ue5 || s.legacy_file_version) << ",";
        oss << "\"legacy\":" << s.legacy_file_version;
    } else {
        oss << "\"ue4\":0,\"ue5\":0,\"legacy\":0";
    }
    oss << "},";

    // Package name
    oss << "\"package_name\":\"";
    if (result.summary) {
        oss << json_escape(result.summary->package_name);
    }
    oss << "\",";

    // Exports summary
    oss << "\"exports\":[";
    for (size_t i = 0; i < result.export_map.size(); ++i) {
        if (i > 0) oss << ", ";
        const auto& exp = result.export_map[i];
        auto class_name = get_asset_class(exp, result.import_map, result.export_map);

        oss << "{";
        oss << "\"name\":\"" << json_escape(exp.object_name) << "\",";
        oss << "\"class\":";
        if (class_name) {
            oss << "\"" << json_escape(*class_name) << "\"";
        } else {
            oss << "null";
        }
        oss << ",\"properties\":[";

        for (size_t j = 0; j < exp.properties.size(); ++j) {
            if (j > 0) oss << ", ";
            const auto& p = exp.properties[j];
            oss << "{\"name\":\"" << json_escape(p.name) << "\",";
            oss << "\"type\":\"" << json_escape(p.type) << "\",";
            oss << "\"value\":" << variant_to_json(p.value) << "}";
        }

        oss << "]";
        oss << "}";
    }
    oss << "],";

    // Blueprint
    oss << "\"blueprint_metadata\":";
    if (result.blueprint) {
        oss << format_blueprint_json(*result.blueprint);
    } else {
        oss << "null";
    }
    oss << ",";

    // Errors
    oss << "\"errors\":[";
    for (size_t i = 0; i < result.errors.size(); ++i) {
        if (i > 0) oss << ", ";
        oss << "\"" << json_escape(result.errors[i]) << "\"";
    }
    oss << "]";

    oss << "}";
    return oss.str();
}

// ============================================================================
// Format Full Text (YAML-style)
// ============================================================================

std::string format_text_full(const ParseResult& result) {
    std::ostringstream oss;

    // Package header
    if (result.summary) {
        const auto& s = *result.summary;
        oss << "Package: " << s.package_name << std::endl;
        oss << "  Version: UE4=" << s.file_version_ue4
            << ", UE5=" << s.file_version_ue5 << std::endl;
        oss << "  Flags: 0x" << std::hex << std::setw(8) << std::setfill('0')
            << s.package_flags << std::dec << std::endl;
        oss << "  Imports: " << result.import_map.size() << std::endl;
        oss << "  Exports: " << result.export_map.size() << std::endl;
        oss << std::endl;
    } else {
        oss << "Package: Unknown" << std::endl;
        oss << "  Version: Unknown" << std::endl;
        oss << "  Imports: 0" << std::endl;
        oss << "  Exports: 0" << std::endl;
        oss << std::endl;
    }

    // Exports
    oss << "Exports:" << std::endl;
    for (const auto& exp : result.export_map) {
        auto class_name = get_asset_class(exp, result.import_map, result.export_map);
        oss << "  - Name: " << exp.object_name << std::endl;
        oss << "    Class: " << (class_name ? *class_name : "None") << std::endl;
        oss << "    SerialSize: " << exp.serial_size << std::endl;

        if (!exp.properties.empty()) {
            oss << "    Properties:" << std::endl;
            for (const auto& prop : exp.properties) {
                oss << "      - Name: " << prop.name << std::endl;
                oss << "        Type: " << prop.type << std::endl;
                oss << "        Value: " << variant_to_json(prop.value) << std::endl;
            }
        }
        oss << std::endl;
    }

    // Blueprint
    if (result.blueprint && result.blueprint->is_blueprint) {
        oss << "Blueprint:" << std::endl;
        oss << "  ParentClass: " << (result.blueprint->parent_class ? *result.blueprint->parent_class : "Unknown") << std::endl;
        oss << "  Variables: " << result.blueprint->variables.size() << std::endl;

        for (const auto& var : result.blueprint->variables) {
            oss << "  - Name: " << var.var_name << std::endl;
            oss << "    Type: " << var.var_type.pin_category << std::endl;
            oss << "    Default: " << variant_to_json(var.default_value) << std::endl;
            oss << "    Category: " << (var.category.empty() ? "Default" : var.category) << std::endl;
        }
        oss << std::endl;
    }

    // Errors
    oss << "ERRORS:" << std::endl;
    if (result.errors.empty()) {
        oss << "  (none)" << std::endl;
    } else {
        for (const auto& err : result.errors) {
            oss << "  - " << err << std::endl;
        }
    }

    return oss.str();
}

// ============================================================================
// Format Summary Text
// ============================================================================

std::string format_text_summary(const ParseResult& result) {
    std::ostringstream oss;

    // Package header
    oss << "Package: ";
    if (result.summary) {
        oss << result.summary->package_name;
    } else {
        oss << "Unknown";
    }
    oss << std::endl;

    oss << "Exports: " << result.export_map.size() << std::endl;
    oss << std::endl;

    // One line per export
    for (const auto& exp : result.export_map) {
        auto class_name = get_asset_class(exp, result.import_map, result.export_map);
        oss << "  - " << exp.object_name << " (" << (class_name ? *class_name : "None") << ")" << std::endl;
    }

    // Blueprint summary
    if (result.blueprint && result.blueprint->is_blueprint) {
        oss << std::endl;
        oss << "Blueprint:" << std::endl;
        oss << "  Parent: " << (result.blueprint->parent_class ? *result.blueprint->parent_class : "Unknown") << std::endl;
        oss << "  Variables: " << result.blueprint->variables.size() << std::endl;
    }

    return oss.str();
}

}  // namespace uasset