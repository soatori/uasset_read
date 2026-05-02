// parser.hpp - Core parsing function declarations
// Translated from uasset_read.py lines 761-1363

#ifndef UASSET_PARSER_HPP
#define UASSET_PARSER_HPP

#include "archive.hpp"
#include "types.hpp"
#include "constants.hpp"

#include <string>
#include <vector>
#include <optional>

namespace uasset {

// ============================================================================
// Core Parsing Functions
// ============================================================================

// Read PackageFileSummary (CORE-01, CORE-02, CORE-08)
// ~37 sequential version-dependent steps
PackageFileSummary read_package_summary(FArchive& archive);

// Read Name Table (NameMap)
std::vector<std::string> read_name_table(FArchive& archive, const PackageFileSummary& summary);

// Read Import Map (CORE-04)
std::vector<ObjectImport> read_import_map(
    FArchive& archive,
    const PackageFileSummary& summary,
    const std::vector<std::string>& name_map
);

// Read Export Map (CORE-05, CORE-06)
std::vector<ObjectExport> read_export_map(
    FArchive& archive,
    const PackageFileSummary& summary,
    const std::vector<std::string>& name_map
);

// ============================================================================
// Asset Class Resolution (CORE-06)
// ============================================================================

// Get asset class name from export
std::optional<std::string> get_asset_class(
    const ObjectExport& export,
    const std::vector<ObjectImport>& import_map,
    const std::vector<ObjectExport>& export_map
);

// ============================================================================
// Blueprint Detection (BLUE-01)
// ============================================================================

bool detect_blueprint(
    const ObjectExport& export,
    const std::vector<ObjectImport>& import_map,
    const std::vector<ObjectExport>& export_map
);

// ============================================================================
// Parent Class Resolution (BLUE-02)
// ============================================================================

// Returns pair of (resolved_name, warning_if_any)
std::pair<std::optional<std::string>, std::optional<std::string>>
resolve_parent_class(
    const PackageIndex& super_index,
    const std::vector<ObjectImport>& import_map,
    const std::vector<ObjectExport>& export_map
);

// ============================================================================
// Main Entry Point
// ============================================================================

// Parse .uasset file - main function
ParseResult parse_uasset(const std::string& path);

}  // namespace uasset

#endif  // UASSET_PARSER_HPP