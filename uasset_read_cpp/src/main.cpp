// main.cpp - CLI entry point (Phase 5 complete)
// Translated from uasset_read.py lines 2614-2716

#include "uasset/archive.hpp"
#include "uasset/parser.hpp"
#include "uasset/property_parser.hpp"
#include "uasset/blueprint_parser.hpp"
#include "uasset/output.hpp"
#include "uasset/constants.hpp"
#include "uasset/types.hpp"
#include "uasset/exceptions.hpp"

#include <iostream>
#include <string>
#include <fstream>
#include <filesystem>

namespace uasset {

// Parse with property and blueprint extraction
ParseResult parse_uasset_full(const std::string& path) {
    ParseResult result;

    try {
        FArchive archive(path);

        auto mmap_info = archive.get_mmap_info();
        result.mmap_used = mmap_info.used;
        result.mmap_warning = mmap_info.warning;

        result.summary = read_package_summary(archive);
        result.name_map = read_name_table(archive, *result.summary);
        result.import_map = read_import_map(archive, *result.summary, result.name_map);
        result.export_map = read_export_map(archive, *result.summary, result.name_map);

        // Property parsing (Phase 3)
        for (auto& exp : result.export_map) {
            if (exp.serial_size > 0 && exp.serial_offset > 0) {
                try {
                    exp.properties = parse_properties_from_export(
                        exp, archive, *result.summary,
                        result.name_map, result.export_map
                    );
                } catch (const ParseError& e) {
                    result.warnings.push_back("Property parse error: " + std::string(e.what()));
                }
            }
        }

        // Blueprint extraction (Phase 4)
        for (const auto& exp : result.export_map) {
            if (detect_blueprint(exp, result.import_map, result.export_map)) {
                try {
                    auto [meta, warn] = extract_blueprint_metadata(
                        exp, archive,
                        result.import_map, result.export_map,
                        result.name_map, *result.summary
                    );
                    if (meta) {
                        result.blueprint = meta;
                        if (warn) {
                            result.warnings.push_back(*warn);
                        }
                    }
                } catch (const ParseError& e) {
                    result.errors.push_back("Blueprint extraction error: " + std::string(e.what()));
                }
                break;  // Only process first blueprint
            }
        }

        result.is_success = true;

    } catch (const VersionError& e) {
        result.errors.push_back(e.what());
        result.is_success = false;
    } catch (const ParseError& e) {
        result.errors.push_back(e.what());
        result.is_success = false;
    } catch (const std::exception& e) {
        result.errors.push_back("Unexpected error: " + std::string(e.what()));
        result.is_success = false;
    }

    return result;
}

}  // namespace uasset

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: uasset_read <file.uasset> [options]" << std::endl;
        std::cerr << "Options:" << std::endl;
        std::cerr << "  --json       Output full JSON format" << std::endl;
        std::cerr << "  --text       Output YAML-style text (default)" << std::endl;
        std::cerr << "  --summary    Output compact summary" << std::endl;
        std::cerr << "  --output F   Write output to file F" << std::endl;
        return uasset::EXIT_ARGUMENT_ERROR;
    }

    std::string file_path = argv[1];
    bool json_output = false;
    bool text_output = false;
    bool summary_output = false;
    std::string output_file;

    for (int i = 2; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--json") {
            json_output = true;
        } else if (arg == "--text") {
            text_output = true;
        } else if (arg == "--summary") {
            summary_output = true;
        } else if (arg == "--output" && i + 1 < argc) {
            output_file = argv[++i];
        }
    }

    // Check file exists
    if (!std::filesystem::exists(file_path)) {
        std::cerr << "Error: File not found: " << file_path << std::endl;
        return uasset::EXIT_FILE_NOT_FOUND;
    }

    // Parse
    uasset::ParseResult result = uasset::parse_uasset_full(file_path);

    if (!result.is_success) {
        std::cerr << "Parse errors:" << std::endl;
        for (const auto& err : result.errors) {
            std::cerr << "  - " << err << std::endl;
        }
        return uasset::EXIT_PARSE_ERROR;
    }

    // Select output format
    std::string output_str;
    if (json_output) {
        output_str = uasset::format_json_full(result);
    } else if (summary_output) {
        output_str = uasset::format_json_summary(result);
    } else {
        // Default: text output
        output_str = uasset::format_text_full(result);
    }

    // Write output
    if (!output_file.empty()) {
        std::ofstream ofs(output_file, std::ios::binary);
        if (!ofs.is_open()) {
            std::cerr << "Error: Cannot write to file: " << output_file << std::endl;
            return uasset::EXIT_ARGUMENT_ERROR;
        }
        ofs << output_str;
        ofs.close();
        std::cerr << "Output written to " << output_file << std::endl;
    } else {
        std::cout << output_str << std::endl;
    }

    return uasset::EXIT_SUCCESS;
}