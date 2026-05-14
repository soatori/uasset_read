// archive.cpp - FArchive implementation
// Translated from uasset_read.py lines 137-405

#include "archive.hpp"
#include "constants.hpp"
#include <filesystem>
#include <sstream>
#include <cstring>

namespace uasset {

// ============================================================================
// Constructor / Destructor
// ============================================================================

FArchive::FArchive(const std::string& path)
    : path_(path), file_(path, std::ios::binary), byte_swapping_(false) {
    if (!file_.is_open()) {
        throw ParseError("Cannot open file: " + path);
    }

    // Get file size
    file_.seekg(0, std::ios::end);
    file_size_ = file_.tellg();
    file_.seekg(0, std::ios::beg);

    // mmap support (Phase 6 will add actual mmap)
    // For now, just check threshold and record warning if needed
    if (file_size_ >= MMAP_THRESHOLD) {
        mmap_warning_ = "Large file detected, mmap not yet implemented";
    }
}

FArchive::~FArchive() {
    close();
}

FArchive::FArchive(FArchive&& other) noexcept
    : path_(std::move(other.path_)),
      file_(std::move(other.file_)),
      byte_swapping_(other.byte_swapping_),
      file_size_(other.file_size_),
      use_mmap_(other.use_mmap_),
      mmap_warning_(std::move(other.mmap_warning_)) {
    other.file_size_ = 0;
    other.use_mmap_ = false;
}

FArchive& FArchive::operator=(FArchive&& other) noexcept {
    if (this != &other) {
        close();
        path_ = std::move(other.path_);
        file_ = std::move(other.file_);
        byte_swapping_ = other.byte_swapping_;
        file_size_ = other.file_size_;
        use_mmap_ = other.use_mmap_;
        mmap_warning_ = std::move(other.mmap_warning_);
        other.file_size_ = 0;
        other.use_mmap_ = false;
    }
    return *this;
}

// ============================================================================
// Basic Operations
// ============================================================================

std::vector<uint8_t> FArchive::read(size_t size) {
    int64_t current_pos = tell();
    int64_t remaining = file_size_ - current_pos;

    if (static_cast<int64_t>(size) > remaining) {
        std::ostringstream oss;
        oss << "Cannot read " << size << " bytes at position " << current_pos
            << ", only " << remaining << " bytes remaining";
        throw ParseError(oss.str());
    }

    std::vector<uint8_t> data(size);
    file_.read(reinterpret_cast<char*>(data.data()), size);

    if (!file_) {
        throw ParseError("Read failed: " + path_);
    }

    return data;
}

void FArchive::seek(int64_t pos) {
    validate_offset(pos, "seek");
    file_.seekg(pos, std::ios::beg);
}

int64_t FArchive::tell() const {
    return file_.tellg();
}

int64_t FArchive::total_size() const {
    return file_size_;
}

void FArchive::close() {
    if (file_.is_open()) {
        file_.close();
    }
    use_mmap_ = false;
}

// ============================================================================
// Byte Swapping Control
// ============================================================================

void FArchive::set_byte_swapping(bool enabled) {
    byte_swapping_ = enabled;
}

// ============================================================================
// Validation (D-10, D-11, D-14)
// ============================================================================

void FArchive::validate_offset(int64_t offset, const std::string& context) {
    if (offset < 0) {
        std::ostringstream oss;
        oss << "Invalid offset " << offset << " (negative) at " << context;
        throw ParseError(oss.str());
    }
    if (offset > file_size_) {
        std::ostringstream oss;
        oss << "Offset " << offset << " exceeds file size " << file_size_
            << " at " << context;
        throw ParseError(oss.str());
    }
}

void FArchive::validate_size(int32_t size, const std::string& context) {
    if (size < 0) {
        std::ostringstream oss;
        oss << "Invalid size " << size << " (negative) at " << context;
        throw ParseError(oss.str());
    }

    int64_t current_pos = tell();
    int64_t remaining = file_size_ - current_pos;
    if (size > remaining) {
        std::ostringstream oss;
        oss << "Size " << size << " exceeds remaining " << remaining
            << " bytes at " << context;
        throw ParseError(oss.str());
    }

    // D-16: max_reasonable check
    int64_t min_reasonable = 1024;
    int64_t max_reasonable_cap = 100 * 1024 * 1024;  // 100MB
    int64_t max_reasonable = std::max(min_reasonable,
                                       std::min(file_size_ / 10, max_reasonable_cap));

    if (size > max_reasonable) {
        std::ostringstream oss;
        oss << "Size " << size << " exceeds max_reasonable " << max_reasonable
            << " at " << context;
        throw ParseError(oss.str());
    }
}

// ============================================================================
// Typed Read Methods
// ============================================================================

uint8_t FArchive::read_u8() {
    auto data = read(1);
    return data[0];
}

int32_t FArchive::read_i32() {
    auto data = read(4);
    uint32_t val = static_cast<uint32_t>(data[0]) |
                   (static_cast<uint32_t>(data[1]) << 8) |
                   (static_cast<uint32_t>(data[2]) << 16) |
                   (static_cast<uint32_t>(data[3]) << 24);

    if (byte_swapping_) {
        val = byteswap32(val);
    }

    return static_cast<int32_t>(val);
}

uint16_t FArchive::read_u16() {
    auto data = read(2);
    uint16_t val = static_cast<uint16_t>(data[0]) |
                   (static_cast<uint16_t>(data[1]) << 8);

    if (byte_swapping_) {
        val = byteswap16(val);
    }

    return val;
}

uint32_t FArchive::read_u32() {
    auto data = read(4);
    uint32_t val = static_cast<uint32_t>(data[0]) |
                   (static_cast<uint32_t>(data[1]) << 8) |
                   (static_cast<uint32_t>(data[2]) << 16) |
                   (static_cast<uint32_t>(data[3]) << 24);

    if (byte_swapping_) {
        val = byteswap32(val);
    }

    return val;
}

int64_t FArchive::read_i64() {
    auto data = read(8);
    uint64_t val = static_cast<uint64_t>(data[0]) |
                   (static_cast<uint64_t>(data[1]) << 8) |
                   (static_cast<uint64_t>(data[2]) << 16) |
                   (static_cast<uint64_t>(data[3]) << 24) |
                   (static_cast<uint64_t>(data[4]) << 32) |
                   (static_cast<uint64_t>(data[5]) << 40) |
                   (static_cast<uint64_t>(data[6]) << 48) |
                   (static_cast<uint64_t>(data[7]) << 56);

    if (byte_swapping_) {
        val = byteswap64(val);
    }

    return static_cast<int64_t>(val);
}

uint64_t FArchive::read_u64() {
    auto data = read(8);
    uint64_t val = static_cast<uint64_t>(data[0]) |
                   (static_cast<uint64_t>(data[1]) << 8) |
                   (static_cast<uint64_t>(data[2]) << 16) |
                   (static_cast<uint64_t>(data[3]) << 24) |
                   (static_cast<uint64_t>(data[4]) << 32) |
                   (static_cast<uint64_t>(data[5]) << 40) |
                   (static_cast<uint64_t>(data[6]) << 48) |
                   (static_cast<uint64_t>(data[7]) << 56);

    if (byte_swapping_) {
        val = byteswap64(val);
    }

    return val;
}

float FArchive::read_f32() {
    uint32_t val = read_u32();
    float result;
    std::memcpy(&result, &val, sizeof(float));
    return result;
}

double FArchive::read_f64() {
    uint64_t val = read_u64();
    double result;
    std::memcpy(&result, &val, sizeof(double));
    return result;
}

// ============================================================================
// String Read Methods
// ============================================================================

std::string FArchive::read_fstring() {
    int32_t length = read_i32();

    if (length == 0) {
        return "";
    }

    if (length < 0) {
        // UTF-16 (legacy, UE5 deprecated)
        int32_t utf16_len = -length * 2;
        if (utf16_len > 10000000) {
            throw ParseError("UTF-16 string length too large");
        }
        read(utf16_len);  // Skip UTF-16 data
        return "";
    }

    // UTF-8 (UE5 standard)
    auto data = read(length);

    // Remove null terminator
    if (!data.empty() && data.back() == 0) {
        data.pop_back();
    }

    // Convert to string
    std::string result(reinterpret_cast<const char*>(data.data()), data.size());
    return result;
}

std::string FArchive::read_name(const std::vector<std::string>& name_map) {
    uint32_t index = read_u32();
    uint32_t number = read_u32();

    if (index < name_map.size()) {
        std::string base_name = name_map[index];
        if (number > 0) {
            return base_name + "_" + std::to_string(number);
        }
        return base_name;
    }

    return "None";
}

// ============================================================================
// mmap Info
// ============================================================================

FArchive::MmapInfo FArchive::get_mmap_info() const {
    return {use_mmap_, mmap_warning_};
}

}  // namespace uasset