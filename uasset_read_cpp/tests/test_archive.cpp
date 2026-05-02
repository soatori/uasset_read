// test_archive.cpp - FArchive unit tests
// Simple test framework without external dependencies

#include "uasset/archive.hpp"
#include "uasset/constants.hpp"
#include "uasset/exceptions.hpp"

#include <iostream>
#include <vector>
#include <cstring>
#include <filesystem>

namespace uasset {
namespace test {

// Test framework macros
#define TEST(name) void name()
#define ASSERT_TRUE(expr) if (!(expr)) { std::cerr << "FAIL: " << #expr << std::endl; failures++; }
#define ASSERT_EQ(a, b) if ((a) != (b)) { std::cerr << "FAIL: " << #a << " != " << #b << std::endl; failures++; }
#define ASSERT_THROW(expr, exc) try { expr; std::cerr << "FAIL: no exception thrown" << std::endl; failures++; } catch (const exc&) {} catch (...) { std::cerr << "FAIL: wrong exception" << std::endl; failures++; }

static int failures = 0;

// Helper to create synthetic .uasset data
std::vector<uint8_t> create_minimal_uasset() {
    std::vector<uint8_t> data;

    // Magic tag (little-endian)
    uint32_t tag = PACKAGE_FILE_TAG;
    data.push_back(tag & 0xFF);
    data.push_back((tag >> 8) & 0xFF);
    data.push_back((tag >> 16) & 0xFF);
    data.push_back((tag >> 24) & 0xFF);

    // LegacyFileVersion (-8 for UE5)
    int32_t legacy = -8;
    data.push_back(legacy & 0xFF);
    data.push_back((legacy >> 8) & 0xFF);
    data.push_back((legacy >> 16) & 0xFF);
    data.push_back((legacy >> 24) & 0xFF);

    // UE4 version (522)
    int32_t ue4 = 522;
    data.push_back(ue4 & 0xFF);
    data.push_back((ue4 >> 8) & 0xFF);
    data.push_back((ue4 >> 16) & 0xFF);
    data.push_back((ue4 >> 24) & 0xFF);

    // UE5 version (1016)
    int32_t ue5 = 1016;
    data.push_back(ue5 & 0xFF);
    data.push_back((ue5 >> 8) & 0xFF);
    data.push_back((ue5 >> 16) & 0xFF);
    data.push_back((ue5 >> 24) & 0xFF);

    // Licensee version (0)
    for (int i = 0; i < 4; ++i) data.push_back(0);

    // SavedHash (20 bytes) - UE5 >= 1016
    for (int i = 0; i < 20; ++i) data.push_back(0);

    // TotalHeaderSize (placeholder)
    int32_t header_size = 100;
    data.push_back(header_size & 0xFF);
    data.push_back((header_size >> 8) & 0xFF);
    data.push_back((header_size >> 16) & 0xFF);
    data.push_back((header_size >> 24) & 0xFF);

    // CustomVersions count (0)
    for (int i = 0; i < 4; ++i) data.push_back(0);

    // PackageName (empty FString)
    for (int i = 0; i < 4; ++i) data.push_back(0);

    // PackageFlags
    for (int i = 0; i < 4; ++i) data.push_back(0);

    // NameCount (2)
    int32_t name_count = 2;
    data.push_back(name_count & 0xFF);
    data.push_back((name_count >> 8) & 0xFF);
    data.push_back((name_count >> 16) & 0xFF);
    data.push_back((name_count >> 24) & 0xFF);

    // NameOffset (point to end of header)
    int32_t name_offset = static_cast<int32_t>(data.size()) + 4;
    data.push_back(name_offset & 0xFF);
    data.push_back((name_offset >> 8) & 0xFF);
    data.push_back((name_offset >> 16) & 0xFF);
    data.push_back((name_offset >> 24) & 0xFF);

    // Padding to reach name_offset
    while (static_cast<int32_t>(data.size()) < name_offset) {
        data.push_back(0);
    }

    // Name table (2 names: "None" and "Test")
    // Name 1: "None"
    int32_t len1 = 5;  // "None" + null
    data.push_back(len1 & 0xFF);
    data.push_back((len1 >> 8) & 0xFF);
    data.push_back((len1 >> 16) & 0xFF);
    data.push_back((len1 >> 24) & 0xFF);
    data.push_back('N'); data.push_back('o'); data.push_back('n'); data.push_back('e'); data.push_back(0);
    // Hash (4 bytes)
    for (int i = 0; i < 4; ++i) data.push_back(0);

    // Name 2: "Test"
    int32_t len2 = 5;  // "Test" + null
    data.push_back(len2 & 0xFF);
    data.push_back((len2 >> 8) & 0xFF);
    data.push_back((len2 >> 16) & 0xFF);
    data.push_back((len2 >> 24) & 0xFF);
    data.push_back('T'); data.push_back('e'); data.push_back('s'); data.push_back('t'); data.push_back(0);
    // Hash (4 bytes)
    for (int i = 0; i < 4; ++i) data.push_back(0);

    return data;
}

// Write test file
std::string write_test_file(const std::vector<uint8_t>& data, const std::string& name) {
    std::string path = "test_" + name + ".uasset";
    std::ofstream ofs(path, std::ios::binary);
    ofs.write(reinterpret_cast<const char*>(data.data()), data.size());
    ofs.close();
    return path;
}

// ============================================================================
// Tests
// ============================================================================

TEST(test_magic_tag) {
    auto data = create_minimal_uasset();
    std::string path = write_test_file(data, "magic");

    FArchive ar(path);
    uint32_t tag = ar.read_u32();

    ASSERT_EQ(tag, PACKAGE_FILE_TAG);

    std::filesystem::remove(path);
}

TEST(test_byte_swap_detection) {
    // Create swapped magic tag
    std::vector<uint8_t> data;
    uint32_t swapped = PACKAGE_FILE_TAG_SWAPPED;
    data.push_back(swapped & 0xFF);
    data.push_back((swapped >> 8) & 0xFF);
    data.push_back((swapped >> 16) & 0xFF);
    data.push_back((swapped >> 24) & 0xFF);
    // Minimal padding
    for (int i = 0; i < 100; ++i) data.push_back(0);

    std::string path = write_test_file(data, "swap");

    FArchive ar(path);
    uint32_t tag = ar.read_u32();

    ASSERT_EQ(tag, PACKAGE_FILE_TAG_SWAPPED);
    ASSERT_TRUE(!ar.is_byte_swapping());  // Not set until explicitly called

    ar.set_byte_swapping(true);
    ASSERT_TRUE(ar.is_byte_swapping());

    std::filesystem::remove(path);
}

TEST(test_invalid_tag) {
    std::vector<uint8_t> data;
    for (int i = 0; i < 100; ++i) data.push_back(0xFF);  // Invalid data

    std::string path = write_test_file(data, "invalid");

    bool caught = false;
    try {
        FArchive ar(path);
        ar.read_u32();  // Just read, don't validate tag here
    } catch (...) {
        caught = true;
    }
    ASSERT_TRUE(!caught);  // Archive opens fine, validation is in parser

    std::filesystem::remove(path);
}

TEST(test_bounds_validation) {
    auto data = create_minimal_uasset();
    std::string path = write_test_file(data, "bounds");

    FArchive ar(path);

    // Valid seek
    ar.seek(0);
    ASSERT_EQ(ar.tell(), 0);

    // Invalid seek (negative)
    bool caught_neg = false;
    try {
        ar.seek(-1);
    } catch (const ParseError&) {
        caught_neg = true;
    }
    ASSERT_TRUE(caught_neg);

    // Invalid seek (exceeds file size)
    bool caught_over = false;
    try {
        ar.seek(ar.total_size() + 1000);
    } catch (const ParseError&) {
        caught_over = true;
    }
    ASSERT_TRUE(caught_over);

    std::filesystem::remove(path);
}

TEST(test_read_types) {
    std::vector<uint8_t> data;

    // Write test values
    uint8_t u8_val = 0xAB;
    data.push_back(u8_val);

    uint16_t u16_val = 0x1234;
    data.push_back(u16_val & 0xFF);
    data.push_back((u16_val >> 8) & 0xFF);

    uint32_t u32_val = 0x12345678;
    data.push_back(u32_val & 0xFF);
    data.push_back((u32_val >> 8) & 0xFF);
    data.push_back((u32_val >> 16) & 0xFF);
    data.push_back((u32_val >> 24) & 0xFF);

    int32_t i32_val = -12345;
    data.push_back(i32_val & 0xFF);
    data.push_back((i32_val >> 8) & 0xFF);
    data.push_back((i32_val >> 16) & 0xFF);
    data.push_back((i32_val >> 24) & 0xFF);

    // Padding
    for (int i = 0; i < 50; ++i) data.push_back(0);

    std::string path = write_test_file(data, "types");

    FArchive ar(path);

    ASSERT_EQ(ar.read_u8(), u8_val);
    ASSERT_EQ(ar.read_u16(), u16_val);
    ASSERT_EQ(ar.read_u32(), u32_val);
    ASSERT_EQ(ar.read_i32(), i32_val);

    std::filesystem::remove(path);
}

TEST(test_fstring) {
    std::vector<uint8_t> data;

    // FString: "Hello" (length=6 including null)
    int32_t len = 6;
    data.push_back(len & 0xFF);
    data.push_back((len >> 8) & 0xFF);
    data.push_back((len >> 16) & 0xFF);
    data.push_back((len >> 24) & 0xFF);
    data.push_back('H'); data.push_back('e'); data.push_back('l');
    data.push_back('l'); data.push_back('o'); data.push_back(0);

    // Padding
    for (int i = 0; i < 50; ++i) data.push_back(0);

    std::string path = write_test_file(data, "fstring");

    FArchive ar(path);
    std::string str = ar.read_fstring();

    ASSERT_EQ(str, "Hello");

    std::filesystem::remove(path);
}

// ============================================================================
// Main
// ============================================================================

void run_all_tests() {
    std::cout << "Running FArchive tests..." << std::endl;

    failures = 0;

    test_magic_tag();
    test_byte_swap_detection();
    test_invalid_tag();
    test_bounds_validation();
    test_read_types();
    test_fstring();

    std::cout << "Tests completed: " << failures << " failures" << std::endl;
}

}  // namespace test
}  // namespace uasset

int main() {
    uasset::test::run_all_tests();
    return uasset::test::failures > 0 ? 1 : 0;
}