# tests/CMakeLists.txt - Test configuration

# Test executable
add_executable(uasset_tests
    test_archive.cpp
)

target_link_libraries(uasset_tests PRIVATE uasset_lib)

# Add test to CTest
add_test(NAME uasset_tests COMMAND uasset_tests)