// output.hpp - Output formatting declarations
// Translated from uasset_read.py lines 2265-2615
// Note: Uses manual JSON generation to avoid external dependencies

#ifndef UASSET_OUTPUT_HPP
#define UASSET_OUTPUT_HPP

#include "types.hpp"
#include "parser.hpp"

#include <string>
#include <vector>
#include <sstream>

namespace uasset {

// ============================================================================
// JSON Output (Manual Generation)
// ============================================================================

// Format full JSON output (OUT-01, OUT-03)
std::string format_json_full(const ParseResult& result);

// Format compact JSON summary (OUT-03)
std::string format_json_summary(const ParseResult& result);

// ============================================================================
// Text Output (YAML-style)
// ============================================================================

// Format full YAML-style text (OUT-02)
std::string format_text_full(const ParseResult& result);

// Format compact text summary (OUT-02)
std::string format_text_summary(const ParseResult& result);

// ============================================================================
// Helper Functions
// ============================================================================

// Resolve FPackageIndex for output
std::string resolve_fpackage_index_json(const PackageIndex& idx, const ParseResult& result);

// Format blueprint as JSON
std::string format_blueprint_json(const BlueprintMetadata& blueprint);

// Format exports list for JSON
std::string format_exports_json(const ParseResult& result);

// Format properties list for JSON
std::string format_properties_json(const std::vector<PropertyValue>& properties);

// ============================================================================
// JSON Utilities (Manual Generation)
// ============================================================================

// Escape string for JSON
std::string json_escape(const std::string& str);

// Convert variant to JSON string
std::string variant_to_json(const PropertyValueVariant& value);

}  // namespace uasset

#endif  // UASSET_OUTPUT_HPP