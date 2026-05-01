// blueprint_parser.hpp - Blueprint metadata extraction declarations
// Translated from uasset_read.py lines 1365-1737

#ifndef UASSET_BLUEPRINT_PARSER_HPP
#define UASSET_BLUEPRINT_PARSER_HPP

#include "archive.hpp"
#include "types.hpp"
#include "parser.hpp"

#include <vector>
#include <string>
#include <optional>
#include <utility>

namespace uasset {

// ============================================================================
// FEdGraphPinType Parsing (BLUE-05)
// ============================================================================

FEdGraphPinType read_ed_graph_pin_type(
    FArchive& archive,
    const std::vector<std::string>& name_map,
    const PackageFileSummary& summary
);

// ============================================================================
// Blueprint Variable Parsing (BLUE-03)
// ============================================================================

BlueprintVariable read_blueprint_variable(
    FArchive& archive,
    const std::vector<std::string>& name_map,
    const PackageFileSummary& summary
);

// ============================================================================
// Default Value Parsing (BLUE-03, D-13-D-16)
// ============================================================================

// Parse default value string to variant type
PropertyValueVariant parse_default_value(const std::string& value_str, const FEdGraphPinType& var_type);

// ============================================================================
// Blueprint Metadata Extraction (BLUE-06)
// ============================================================================

// Extract blueprint metadata from export
// Returns pair of (metadata, warning_if_any)
std::pair<std::optional<BlueprintMetadata>, std::optional<std::string>>
extract_blueprint_metadata(
    const ObjectExport& export,
    FArchive& archive,
    const std::vector<ObjectImport>& import_map,
    const std::vector<ObjectExport>& export_map,
    const std::vector<std::string>& name_map,
    const PackageFileSummary& summary
);

}  // namespace uasset

#endif  // UASSET_BLUEPRINT_PARSER_HPP