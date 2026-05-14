// blueprint_parser.cpp - Blueprint metadata extraction implementation
// Translated from uasset_read.py lines 1365-1737

#include "blueprint_parser.hpp"
#include "archive.hpp"
#include "exceptions.hpp"
#include "constants.hpp"

#include <regex>
#include <algorithm>
#include <sstream>

namespace uasset {

// ============================================================================
// FEdGraphPinType Parsing (BLUE-05)
// ============================================================================

FEdGraphPinType read_ed_graph_pin_type(
    FArchive& archive,
    const std::vector<std::string>& name_map,
    const PackageFileSummary& summary
) {
    FEdGraphPinType pin_type;

    // Step 1-2: PinCategory and PinSubCategory (FName)
    pin_type.pin_category = archive.read_name(name_map);
    pin_type.pin_sub_category = archive.read_name(name_map);

    // Step 3: PinSubCategoryObject (FPackageIndex as int32)
    pin_type.pin_sub_category_object = archive.read_i32();

    // Step 4: ContainerType (uint8)
    pin_type.container_type = archive.read_u8();

    // Step 5: PinValueType for Map containers
    if (pin_type.container_type == 3) {  // Map
        archive.read_name(name_map);  // TerminalCategory
        archive.read_name(name_map);  // TerminalSubCategory
        archive.read_i32();           // TerminalSubCategoryObject
    }

    // Step 6-7: bIsReference and bIsWeakPointer
    pin_type.is_reference = archive.read_u8() != 0;
    pin_type.is_weak_pointer = archive.read_u8() != 0;

    // Step 8: PinSubCategoryMemberReference (skip)
    archive.read_i32();  // MemberParent
    archive.read_name(name_map);  // MemberName
    archive.read(16);  // MemberGuid

    // Step 9: bIsConst
    pin_type.is_const = archive.read_u8() != 0;

    // Step 10: bIsUObjectWrapper
    pin_type.is_uobject_wrapper = archive.read_u8() != 0;

    return pin_type;
}

// ============================================================================
// Default Value Parsing (D-13-D-16)
// ============================================================================

PropertyValueVariant parse_default_value(const std::string& value_str, const FEdGraphPinType& var_type) {
    if (value_str.empty()) {
        return std::monostate{};
    }

    // D-16: Vector types stay as string
    if (value_str.front() == '(' && value_str.back() == ')') {
        return value_str;
    }

    // Match PinCategory for type detection
    std::string category = var_type.pin_category;
    std::transform(category.begin(), category.end(), category.begin(), ::tolower);

    // Boolean parsing (D-13)
    if (category == "bool" || category == "boolean") {
        std::string lower_val = value_str;
        std::transform(lower_val.begin(), lower_val.end(), lower_val.begin(), ::tolower);
        if (lower_val == "true" || lower_val == "1") {
            return true;
        }
        if (lower_val == "false" || lower_val == "0") {
            return false;
        }
        return value_str;  // D-14: fallback
    }

    // Integer parsing (D-13)
    if (category == "int" || category == "integer") {
        try {
            return std::stoll(value_str);
        } catch (...) {
            return value_str;  // D-14: fallback
        }
    }

    // Float parsing (D-13)
    if (category == "float" || category == "real" || category == "double") {
        try {
            return std::stod(value_str);
        } catch (...) {
            return value_str;  // D-14: fallback
        }
    }

    // String/Name: keep as-is (D-15)
    if (category == "string" || category == "name" || category == "text") {
        return value_str;
    }

    // Unknown category: fallback to string (D-14)
    return value_str;
}

// ============================================================================
// Blueprint Variable Parsing (BLUE-03)
// ============================================================================

BlueprintVariable read_blueprint_variable(
    FArchive& archive,
    const std::vector<std::string>& name_map,
    const PackageFileSummary& summary
) {
    BlueprintVariable var;

    // VarName (FName)
    var.var_name = archive.read_name(name_map);

    // VarGuid (16 bytes) - skip
    archive.read(16);

    // VarType (FEdGraphPinType)
    var.var_type = read_ed_graph_pin_type(archive, name_map, summary);

    // FriendlyName (FString)
    var.friendly_name = archive.read_fstring();

    // Category (FText) - simplified to FString
    var.category = archive.read_fstring();

    // PropertyFlags (uint64)
    var.property_flags = archive.read_u64();

    // RepNotifyFunc (FName) - skip
    archive.read_name(name_map);

    // ReplicationCondition (uint8) - skip
    archive.read_u8();

    // MetaDataArray - skip for Phase 3
    int32_t meta_count = archive.read_i32();
    for (int32_t i = 0; i < meta_count; ++i) {
        archive.read_name(name_map);  // DataKey
        archive.read_fstring();       // DataValue
    }

    // DefaultValue (FString)
    std::string default_str = archive.read_fstring();
    var.default_value = parse_default_value(default_str, var.var_type);

    return var;
}

// ============================================================================
// Blueprint Metadata Extraction (BLUE-06)
// ============================================================================

std::pair<std::optional<BlueprintMetadata>, std::optional<std::string>>
extract_blueprint_metadata(
    const ObjectExport& export,
    FArchive& archive,
    const std::vector<ObjectImport>& import_map,
    const std::vector<ObjectExport>& export_map,
    const std::vector<std::string>& name_map,
    const PackageFileSummary& summary
) {
    // Step 1: Detect blueprint
    if (!detect_blueprint(export, import_map, export_map)) {
        return {std::nullopt, std::nullopt};
    }

    // Step 2: Resolve parent class
    auto [parent_class, parent_warning] = resolve_parent_class(export.super_index, import_map, export_map);

    // Step 3: Seek to export data
    archive.seek(export.serial_offset);

    // Step 4: Read NewVariables
    BlueprintMetadata metadata;
    metadata.is_blueprint = true;
    metadata.parent_class = parent_class;

    try {
        int32_t var_count = archive.read_i32();

        // D-04: sanity check
        if (var_count > 1000) {
            std::string warning = "NewVariables count " + std::to_string(var_count) +
                                 " exceeds reasonable limit";
            metadata.detection_warning = warning;
            return {metadata, warning};
        }

        for (int32_t i = 0; i < var_count; ++i) {
            BlueprintVariable var = read_blueprint_variable(archive, name_map, summary);
            metadata.variables.push_back(var);
        }

    } catch (const ParseError& e) {
        std::string warning = "Variable extraction failed: " + std::string(e.what());
        metadata.detection_warning = warning;
        return {metadata, warning};
    }

    metadata.detection_warning = parent_warning;
    return {metadata, std::nullopt};
}

}  // namespace uasset