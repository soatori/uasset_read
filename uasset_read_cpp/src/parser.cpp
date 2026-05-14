// parser.cpp - Core parsing implementation
// Translated from uasset_read.py lines 761-1363

#include "parser.hpp"
#include "archive.hpp"
#include "exceptions.hpp"
#include "constants.hpp"

#include <algorithm>
#include <sstream>

namespace uasset {

// ============================================================================
// PackageFileSummary Parsing (~37 steps)
// ============================================================================

PackageFileSummary read_package_summary(FArchive& archive) {
    archive.seek(0);

    PackageFileSummary summary;

    // === Step 1: Magic tag and version ===
    summary.tag = archive.read_u32();

    if (summary.tag == PACKAGE_FILE_TAG_SWAPPED) {
        archive.set_byte_swapping(true);
        summary.tag = PACKAGE_FILE_TAG;
    } else if (summary.tag != PACKAGE_FILE_TAG) {
        throw VersionError("Invalid package tag: " + std::to_string(summary.tag));
    }

    summary.legacy_file_version = archive.read_i32();

    if (summary.legacy_file_version < LEGACY_FILE_VERSION_MIN ||
        summary.legacy_file_version > LEGACY_FILE_VERSION_MAX) {
        throw VersionError("Unsupported legacy version: " +
                          std::to_string(summary.legacy_file_version));
    }

    // LegacyUE3Version (only if legacy != -4)
    if (summary.legacy_file_version != -4) {
        summary.legacy_ue3_version = archive.read_i32();
    }

    // UE4 version
    summary.file_version_ue4 = archive.read_i32();

    // UE5 version (only if legacy <= -8)
    if (summary.legacy_file_version <= -8) {
        summary.file_version_ue5 = archive.read_i32();
        if (summary.file_version_ue5 < UE5_VERSION_MIN) {
            throw VersionError("Unsupported UE5 version: " +
                              std::to_string(summary.file_version_ue5));
        }
    }

    // Licensee version
    summary.file_version_licensee = archive.read_i32();

    // === Step 2: SavedHash (UE5 >= 1016) ===
    const bool is_ue4_file = summary.legacy_file_version > -8;

    if (!is_ue4_file && summary.file_version_ue5 >= UE5_PACKAGE_SAVED_HASH) {
        summary.saved_hash = archive.read(20);  // FIoHash = 20 bytes
        summary.total_header_size = archive.read_i32();
    }

    // === Step 3: CustomVersions ===
    uint32_t custom_versions_count = archive.read_u32();
    if (custom_versions_count > MAX_CUSTOM_VERSIONS) {
        throw ParseError("Custom versions count exceeds maximum");
    }
    for (uint32_t i = 0; i < custom_versions_count; ++i) {
        auto guid_bytes = archive.read(16);
        int32_t version = archive.read_i32();
        CustomVersion cv;
        cv.guid = std::string(guid_bytes.begin(), guid_bytes.end());
        cv.version = version;
        summary.custom_versions.push_back(cv);
    }

    // === Step 4: TotalHeaderSize (UE4 files) ===
    if (is_ue4_file) {
        summary.total_header_size = archive.read_i32();
    }

    // === Step 5: PackageName and PackageFlags ===
    summary.package_name = archive.read_fstring();
    summary.package_flags = archive.read_u32();

    // === Step 6: NameCount and NameOffset ===
    summary.name_count = archive.read_i32();
    if (summary.name_count > MAX_NAME_COUNT) {
        throw ParseError("Name count exceeds maximum");
    }
    summary.name_offset = archive.read_i32();
    archive.validate_offset(summary.name_offset, "NameOffset");

    // === Step 7: SoftObjectPaths (UE5 >= 1008) ===
    if (!is_ue4_file && summary.file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST) {
        summary.soft_object_paths_count = archive.read_i32();
        summary.soft_object_paths_offset = archive.read_i32();
    }

    // === Step 8: LocalizationId (uncooked files) ===
    const bool is_cooked = (summary.package_flags & PKG_Cooked) != 0;
    if (!is_cooked) {
        if (is_ue4_file && summary.file_version_ue4 >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID) {
            summary.localization_id = archive.read_fstring();
        } else if (!is_ue4_file) {
            summary.localization_id = archive.read_fstring();
        }
    }

    // === Step 9: GatherableTextData ===
    if (summary.file_version_ue4 >= UE4_SERIALIZE_TEXT_IN_PACKAGES || !is_ue4_file) {
        summary.gatherable_text_data_count = archive.read_i32();
        summary.gatherable_text_data_offset = archive.read_i32();
    }

    // === Step 10: ExportCount and ExportOffset ===
    summary.export_count = archive.read_i32();
    if (summary.export_count > MAX_EXPORT_COUNT) {
        throw ParseError("Export count exceeds maximum");
    }
    summary.export_offset = archive.read_i32();
    archive.validate_offset(summary.export_offset, "ExportOffset");

    // === Step 11: ImportCount and ImportOffset ===
    summary.import_count = archive.read_i32();
    if (summary.import_count > MAX_IMPORT_COUNT) {
        throw ParseError("Import count exceeds maximum");
    }
    summary.import_offset = archive.read_i32();
    archive.validate_offset(summary.import_offset, "ImportOffset");

    // === Step 12: CellExport/CellImport (UE5 >= 1015) ===
    if (!is_ue4_file && summary.file_version_ue5 >= UE5_VERSE_CELLS) {
        summary.cell_export_count = archive.read_i32();
        summary.cell_export_offset = archive.read_i32();
        summary.cell_import_count = archive.read_i32();
        summary.cell_import_offset = archive.read_i32();
    }

    // === Step 13: MetaDataOffset (UE5 >= 1014) ===
    if (!is_ue4_file && summary.file_version_ue5 >= UE5_METADATA_SERIALIZATION_OFFSET) {
        summary.metadata_offset = archive.read_i32();
    }

    // === Step 14: DependsOffset ===
    summary.depends_offset = archive.read_i32();

    // === Step 15: SoftPackageReferences (UE4 >= 382) ===
    if (summary.file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP) {
        summary.soft_package_references_count = archive.read_i32();
        summary.soft_package_references_offset = archive.read_i32();
    }

    // === Step 16: SearchableNames (UE4 >= 508) ===
    if (summary.file_version_ue4 >= UE4_ADDED_SEARCHABLE_NAMES) {
        summary.searchable_names_offset = archive.read_i32();
    }

    // === Step 17: ThumbnailTableOffset ===
    summary.thumbnail_table_offset = archive.read_i32();

    // === Step 18: ImportTypeHierarchies (UE5 >= 1018) ===
    if (!is_ue4_file && summary.file_version_ue5 >= UE5_IMPORT_TYPE_HIERARCHIES) {
        summary.import_type_hierarchies_count = archive.read_i32();
        summary.import_type_hierarchies_offset = archive.read_i32();
    }

    // === Step 19: Legacy Guid (UE5 < 1016 or UE4) ===
    if (!is_ue4_file && summary.file_version_ue5 < UE5_PACKAGE_SAVED_HASH) {
        archive.read(16);  // Skip Legacy Guid
    } else if (is_ue4_file) {
        archive.read(16);  // Skip Legacy Guid
    }

    // === Step 20: PersistentGuid (UE4 >= 516) ===
    if (!is_cooked && summary.file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER) {
        auto guid_bytes = archive.read(16);
        summary.persistent_guid = std::string(guid_bytes.begin(), guid_bytes.end());

        // OwnerPersistentGuid (UE4 >= 516 and < 518)
        if (summary.file_version_ue4 < UE4_NON_OUTER_PACKAGE_IMPORT) {
            archive.read(16);  // Skip OwnerPersistentGuid
        }
    }

    // === Step 21: Generations ===
    int32_t generations_count = archive.read_i32();
    for (int32_t i = 0; i < generations_count; ++i) {
        GenerationInfo gen;
        gen.export_count = archive.read_i32();
        gen.name_count = archive.read_i32();
        summary.generations.push_back(gen);
    }

    // === Step 22: SavedByEngineVersion ===
    if (summary.file_version_ue4 >= UE4_ENGINE_VERSION_OBJECT) {
        summary.saved_by_engine_version.major = archive.read_u16();
        summary.saved_by_engine_version.minor = archive.read_u16();
        summary.saved_by_engine_version.patch = archive.read_u16();
        summary.saved_by_engine_version.changelist = archive.read_u32();
        summary.saved_by_engine_version.branch = archive.read_fstring();
    } else {
        int32_t engine_changelist = archive.read_i32();
        if (engine_changelist != 0) {
            summary.saved_by_engine_version.major = 4;
            summary.saved_by_engine_version.minor = 0;
            summary.saved_by_engine_version.patch = 0;
            summary.saved_by_engine_version.changelist = engine_changelist;
        }
    }

    // === Step 23: CompatibleWithEngineVersion ===
    if (summary.file_version_ue4 >= UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION) {
        summary.compatible_with_engine_version.major = archive.read_u16();
        summary.compatible_with_engine_version.minor = archive.read_u16();
        summary.compatible_with_engine_version.patch = archive.read_u16();
        summary.compatible_with_engine_version.changelist = archive.read_u32();
        summary.compatible_with_engine_version.branch = archive.read_fstring();
    } else {
        summary.compatible_with_engine_version = summary.saved_by_engine_version;
    }

    // === Step 24: CompressionFlags ===
    summary.compression_flags = archive.read_u32();

    // === Step 25: CompressedChunks (deprecated) ===
    int32_t compressed_chunks_count = archive.read_i32();
    for (int32_t i = 0; i < compressed_chunks_count; ++i) {
        archive.read(12);  // Skip FCompressedChunk = 12 bytes
    }

    // === Step 26: PackageSource ===
    summary.package_source = archive.read_u32();

    // === Step 27: AdditionalPackagesToCook (deprecated) ===
    int32_t additional_packages_count = archive.read_i32();
    for (int32_t i = 0; i < additional_packages_count; ++i) {
        archive.read_fstring();  // Skip
    }

    // === Step 28: NumTextureAllocations (legacy) ===
    if (summary.legacy_file_version > -7) {
        archive.read_i32();  // Skip
    }

    // === Step 29: AssetRegistryDataOffset ===
    summary.asset_registry_data_offset = archive.read_i32();

    // === Step 30: BulkDataStartOffset ===
    summary.bulk_data_start_offset = archive.read_i64();

    // === Step 31: WorldTileInfoDataOffset (UE4 >= 223) ===
    if (summary.file_version_ue4 >= UE4_WORLD_LEVEL_INFO) {
        summary.world_tile_info_data_offset = archive.read_i32();
    }

    // === Step 32: ChunkIDs (UE4 >= 277) ===
    if (summary.file_version_ue4 >= UE4_CHANGED_CHUNKID_TO_ARRAY) {
        int32_t chunk_ids_count = archive.read_i32();
        for (int32_t i = 0; i < chunk_ids_count; ++i) {
            auto guid_bytes = archive.read(16);
            summary.chunk_ids.push_back(std::string(guid_bytes.begin(), guid_bytes.end()));
        }
    } else if (summary.file_version_ue4 >= UE4_ADDED_CHUNKID) {
        int32_t chunk_id = archive.read_i32();
        if (chunk_id >= 0) {
            summary.chunk_ids.push_back(std::to_string(chunk_id));
        }
    }

    // === Step 33: PreloadDependencies (UE4 >= 505) ===
    if (summary.file_version_ue4 >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS) {
        summary.preload_dependency_count = archive.read_i32();
        summary.preload_dependency_offset = archive.read_i32();
    } else {
        summary.preload_dependency_count = -1;
    }

    // === Step 34: NamesReferencedFromExportDataCount (UE5 >= 1001) ===
    if (!is_ue4_file && summary.file_version_ue5 >= UE5_NAMES_REFERENCED_FROM_EXPORT_DATA) {
        summary.names_referenced_from_export_data_count = archive.read_i32();
    } else {
        summary.names_referenced_from_export_data_count = summary.name_count;
    }

    // === Step 35: PayloadTocOffset (UE5 >= 1002) ===
    if (!is_ue4_file && summary.file_version_ue5 >= UE5_PAYLOAD_TOC) {
        summary.payload_toc_offset = archive.read_i64();
    } else {
        summary.payload_toc_offset = -1;
    }

    // === Step 36: DataResourceOffset (UE5 >= 1009) ===
    if (!is_ue4_file && summary.file_version_ue5 >= UE5_DATA_RESOURCES) {
        summary.data_resource_offset = archive.read_i32();
    } else {
        summary.data_resource_offset = -1;
    }

    // === Step 37: TotalHeaderSize (UE5 < 1016) ===
    if (!is_ue4_file && summary.file_version_ue5 < UE5_PACKAGE_SAVED_HASH) {
        summary.total_header_size = archive.read_i32();
    }

    return summary;
}

// ============================================================================
// Name Table Parsing
// ============================================================================

std::vector<std::string> read_name_table(FArchive& archive, const PackageFileSummary& summary) {
    archive.seek(summary.name_offset);

    const bool is_ue4_file = summary.legacy_file_version > -8;
    const bool has_name_hashes = (is_ue4_file && summary.file_version_ue4 >= UE4_NAME_HASHES_SERIALIZED) || !is_ue4_file;

    std::vector<std::string> name_map;
    name_map.reserve(summary.name_count);

    for (int32_t i = 0; i < summary.name_count; ++i) {
        std::string name = archive.read_fstring();
        name_map.push_back(name);

        if (has_name_hashes) {
            archive.read(4);  // Skip hash bytes (NonCasePreservingHash + CasePreservingHash)
        }
    }

    return name_map;
}

// ============================================================================
// Import Map Parsing
// ============================================================================

std::vector<ObjectImport> read_import_map(
    FArchive& archive,
    const PackageFileSummary& summary,
    const std::vector<std::string>& name_map
) {
    archive.seek(summary.import_offset);

    std::vector<ObjectImport> import_map;
    import_map.reserve(summary.import_count);

    for (int32_t i = 0; i < summary.import_count; ++i) {
        ObjectImport imp;
        imp.class_package = archive.read_name(name_map);
        imp.class_name = archive.read_name(name_map);
        imp.outer_index.index = archive.read_i32();
        imp.object_name = archive.read_name(name_map);
        import_map.push_back(imp);
    }

    return import_map;
}

// ============================================================================
// Export Map Parsing
// ============================================================================

std::vector<ObjectExport> read_export_map(
    FArchive& archive,
    const PackageFileSummary& summary,
    const std::vector<std::string>& name_map
) {
    archive.seek(summary.export_offset);

    const bool is_ue5_file = summary.legacy_file_version <= -8;

    std::vector<ObjectExport> export_map;
    export_map.reserve(summary.export_count);

    for (int32_t i = 0; i < summary.export_count; ++i) {
        ObjectExport exp;
        exp.class_index.index = archive.read_i32();
        exp.super_index.index = archive.read_i32();
        exp.outer_index.index = archive.read_i32();
        exp.object_name = archive.read_name(name_map);
        exp.object_flags = archive.read_u32();
        exp.serial_size = archive.read_i64();
        exp.serial_offset = archive.read_i64();

        if (is_ue5_file) {
            exp.script_serial_size = archive.read_i64();
            exp.script_serial_offset = archive.read_i64();
        }

        export_map.push_back(exp);
    }

    return export_map;
}

// ============================================================================
// Asset Class Resolution
// ============================================================================

std::optional<std::string> get_asset_class(
    const ObjectExport& export,
    const std::vector<ObjectImport>& import_map,
    const std::vector<ObjectExport>& export_map
) {
    if (export.class_index.is_import()) {
        int32_t import_idx = export.class_index.to_import_index();
        if (import_idx >= 0 && import_idx < static_cast<int32_t>(import_map.size())) {
            return import_map[import_idx].class_name;
        }
    } else if (export.class_index.is_export()) {
        int32_t export_idx = export.class_index.to_export_index();
        if (export_idx >= 0 && export_idx < static_cast<int32_t>(export_map.size())) {
            return export_map[export_idx].object_name;
        }
    }
    return std::nullopt;
}

// ============================================================================
// Blueprint Detection
// ============================================================================

bool detect_blueprint(
    const ObjectExport& export,
    const std::vector<ObjectImport>& import_map,
    const std::vector<ObjectExport>& export_map
) {
    auto class_name = get_asset_class(export, import_map, export_map);
    if (class_name && class_name->find("Blueprint") != std::string::npos) {
        return true;
    }
    return false;
}

// ============================================================================
// Parent Class Resolution
// ============================================================================

std::pair<std::optional<std::string>, std::optional<std::string>>
resolve_parent_class(
    const PackageIndex& super_index,
    const std::vector<ObjectImport>& import_map,
    const std::vector<ObjectExport>& export_map
) {
    if (super_index.is_null()) {
        return {std::nullopt, std::nullopt};
    }

    if (super_index.is_import()) {
        int32_t import_idx = super_index.to_import_index();
        if (import_idx >= 0 && import_idx < static_cast<int32_t>(import_map.size())) {
            return {import_map[import_idx].object_name, std::nullopt};
        }
        return {std::nullopt, "ParentClass import index " + std::to_string(super_index.index) + " out of range"};
    }

    if (super_index.is_export()) {
        int32_t export_idx = super_index.to_export_index();
        if (export_idx >= 0 && export_idx < static_cast<int32_t>(export_map.size())) {
            return {export_map[export_idx].object_name, std::nullopt};
        }
        return {std::nullopt, "ParentClass export index " + std::to_string(super_index.index) + " out of range"};
    }

    return {std::nullopt, "ParentClass invalid FPackageIndex: " + std::to_string(super_index.index)};
}

// ============================================================================
// Main Entry Point
// ============================================================================

ParseResult parse_uasset(const std::string& path) {
    ParseResult result;

    try {
        FArchive archive(path);

        // Get mmap info
        auto mmap_info = archive.get_mmap_info();
        result.mmap_used = mmap_info.used;
        result.mmap_warning = mmap_info.warning;

        // Read header
        result.summary = read_package_summary(archive);

        // Read name table
        result.name_map = read_name_table(archive, *result.summary);

        // Read import map
        result.import_map = read_import_map(archive, *result.summary, result.name_map);

        // Read export map
        result.export_map = read_export_map(archive, *result.summary, result.name_map);

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