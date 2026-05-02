// archive.hpp - FArchive binary reader class
// Translated from uasset_read.py lines 137-405

#ifndef UASSET_ARCHIVE_HPP
#define UASSET_ARCHIVE_HPP

#include <string>
#include <vector>
#include <cstdint>
#include <fstream>
#include <optional>
#include "exceptions.hpp"

namespace uasset {

// ============================================================================
// FArchive - Binary Reader with Byte Swapping
// ============================================================================

class FArchive {
public:
    // Constructor - opens file
    explicit FArchive(const std::string& path);

    // Destructor - closes file (RAII)
    ~FArchive();

    // Disallow copying
    FArchive(const FArchive&) = delete;
    FArchive& operator=(const FArchive&) = delete;

    // Allow moving
    FArchive(FArchive&&) noexcept;
    FArchive& operator=(FArchive&&) noexcept;

    // ========================================================================
    // Basic Operations
    // ========================================================================

    // Read raw bytes (no byte swap)
    std::vector<uint8_t> read(size_t size);

    // Seek to position (with bounds validation)
    void seek(int64_t pos);

    // Get current position
    int64_t tell() const;

    // Get total file size
    int64_t total_size() const;

    // Close file and mmap
    void close();

    // ========================================================================
    // Byte Swapping Control
    // ========================================================================

    void set_byte_swapping(bool enabled);
    bool is_byte_swapping() const { return byte_swapping_; }

    // ========================================================================
    // Validation (D-10, D-11, D-14)
    // ========================================================================

    void validate_offset(int64_t offset, const std::string& context = "");
    void validate_size(int32_t size, const std::string& context = "");

    // ========================================================================
    // Typed Read Methods (with byte swap support)
    // ========================================================================

    uint8_t read_u8();    // No swap needed
    int32_t read_i32();
    uint16_t read_u16();
    uint32_t read_u32();
    int64_t read_i64();
    uint64_t read_u64();
    float read_f32();
    double read_f64();

    // ========================================================================
    // String Read Methods
    // ========================================================================

    // FString - length-prefixed UTF-8 string
    std::string read_fstring();

    // FName - name table index + instance number
    std::string read_name(const std::vector<std::string>& name_map);

    // ========================================================================
    // mmap Info (D-02, D-03)
    // ========================================================================

    struct MmapInfo {
        bool used = false;
        std::optional<std::string> warning;
    };

    MmapInfo get_mmap_info() const;

private:
    // ========================================================================
    // Private Members
    // ========================================================================

    std::string path_;
    std::ifstream file_;
    bool byte_swapping_ = false;
    int64_t file_size_ = 0;

    // mmap support (Windows: CreateFileMapping, POSIX: mmap)
    // For Phase 1, using simple ifstream; mmap added in Phase 6
    bool use_mmap_ = false;
    std::optional<std::string> mmap_warning_;

    // ========================================================================
    // Byte Swap Helpers
    // ========================================================================

    static constexpr uint16_t byteswap16(uint16_t v) {
        return (v >> 8) | (v << 8);
    }

    static constexpr uint32_t byteswap32(uint32_t v) {
        return ((v >> 24) & 0x000000FF) |
               ((v >> 8)  & 0x0000FF00) |
               ((v << 8)  & 0x00FF0000) |
               ((v << 24) & 0xFF000000);
    }

    static constexpr uint64_t byteswap64(uint64_t v) {
        return ((v >> 56) & 0x00000000000000FF) |
               ((v >> 40) & 0x000000000000FF00) |
               ((v >> 24) & 0x0000000000FF0000) |
               ((v >> 8)  & 0x00000000FF000000) |
               ((v << 8)  & 0x000000FF00000000) |
               ((v << 24) & 0x0000FF0000000000) |
               ((v << 40) & 0x00FF000000000000) |
               ((v << 56) & 0xFF00000000000000);
    }
};

}  // namespace uasset

#endif  // UASSET_ARCHIVE_HPP