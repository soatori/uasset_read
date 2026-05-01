// exceptions.hpp - Custom exception hierarchy
// Translated from uasset_read.py lines 100-131

#ifndef UASSET_EXCEPTIONS_HPP
#define UASSET_EXCEPTIONS_HPP

#include <stdexcept>
#include <string>
#include <optional>
#include <cstdint>

namespace uasset {

// ============================================================================
// Error Context (D-15/D-18)
// ============================================================================

struct ErrorContext {
    int64_t offset;          // File offset position
    std::string phase;       // Parse phase: header/name_table/import_map/export_map/properties/blueprint
    std::string operation;   // Operation type: read_i32/read_name/seek etc
    std::string context_name; // Related object or property name
};

// ============================================================================
// Base Exception
// ============================================================================

class UAssetError : public std::runtime_error {
public:
    explicit UAssetError(const std::string& message)
        : std::runtime_error(message) {}
};

// ============================================================================
// Version Error
// ============================================================================

class VersionError : public UAssetError {
public:
    explicit VersionError(const std::string& message)
        : UAssetError(message) {}
};

// ============================================================================
// Parse Error (with partial result and context)
// ============================================================================

class ParseError : public UAssetError {
public:
    explicit ParseError(const std::string& message,
                        std::optional<ErrorContext> context = std::nullopt)
        : UAssetError(message), context_(context) {}

    std::optional<ErrorContext> context() const { return context_; }

private:
    std::optional<ErrorContext> context_;
};

}  // namespace uasset

#endif  // UASSET_EXCEPTIONS_HPP