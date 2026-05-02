# CMakeLists.txt - Main build configuration
cmake_minimum_required(VERSION 3.20)
project(uasset_read_cpp VERSION 1.0.0 LANGUAGES CXX)

# C++20 required
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Compiler warnings
if(MSVC)
    add_compile_options(/W4 /permissive- /utf-8)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Options
option(UASSET_BUILD_TESTS "Build unit tests" ON)
option(UASSET_USE_MMAP "Enable memory-mapped file support" OFF)

# Header files
set(UASSET_HEADERS
    include/uasset/constants.hpp
    include/uasset/exceptions.hpp
    include/uasset/types.hpp
    include/uasset/archive.hpp
    include/uasset/parser.hpp
    include/uasset/property_parser.hpp
    include/uasset/blueprint_parser.hpp
    include/uasset/output.hpp
)

# Source files
set(UASSET_SOURCES
    src/archive.cpp
    src/parser.cpp
    src/property_parser.cpp
    src/blueprint_parser.cpp
    src/output.cpp
)

# Main library
add_library(uasset_lib STATIC ${UASSET_HEADERS} ${UASSET_SOURCES})
target_include_directories(uasset_lib PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# CLI executable
add_executable(uasset_read src/main.cpp)
target_link_libraries(uasset_read PRIVATE uasset_lib)

# Installation
install(TARGETS uasset_read RUNTIME DESTINATION bin)
install(DIRECTORY include/uasset DESTINATION include)

# Tests
if(UASSET_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()