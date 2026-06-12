"""UE5 PackageFileSummary 读取函数。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.constants import (
    UE5_VERSION_MIN, UE5_PACKAGE_SAVED_HASH, UE5_ADD_SOFTOBJECTPATH_LIST,
    UE5_VERSE_CELLS, UE5_METADATA_SERIALIZATION_OFFSET,
    UE5_IMPORT_TYPE_HIERARCHIES,
    UE5_NAMES_REFERENCED_FROM_EXPORT_DATA, UE5_PAYLOAD_TOC,
    UE5_DATA_RESOURCES,
    PKG_FilterEditorOnly,
    UE4_ADD_STRING_ASSET_REFERENCES_MAP,
    UE4_ADDED_SEARCHABLE_NAMES,
    UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID,
    UE4_SERIALIZE_TEXT_IN_PACKAGES,
    UE4_ADDED_PACKAGE_OWNER,
    UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS,
    MAX_NAME_COUNT, MAX_IMPORT_COUNT, MAX_EXPORT_COUNT, MAX_CUSTOM_VERSIONS,
    MAX_TOTAL_OBJECT_COUNT,
)
from uasset_read.exceptions import VersionError, ParseError
from .models import GenerationInfo, EngineVersion, CustomVersion, PackageFileSummary

logger = logging.getLogger(__name__)


def read_ue5_package_summary(
    archive: "FArchive",
    tag: int,
    legacy_file_version: int,
) -> PackageFileSummary:
    """读取 UE5 格式的 PackageFileSummary。"""
    # UE3 version
    if legacy_file_version != -4:
        legacy_ue3_version = archive.read_i32()
    else:
        legacy_ue3_version = 0

    file_version_ue4 = archive.read_i32()

    # FileVersionUE5: only present when legacy_file_version <= -8
    if legacy_file_version <= -8:
        file_version_ue5 = archive.read_i32()
    else:
        file_version_ue5 = 0

    # UE5 version check
    if legacy_file_version <= -8 and file_version_ue5 < UE5_VERSION_MIN:
        raise VersionError(f"Unsupported UE5 version: {file_version_ue5}")

    file_version_licensee = archive.read_i32()

    # SavedHash + TotalHeaderSize
    if file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        saved_hash = archive.read(20)
        total_header_size = archive.read_i32()
    else:
        saved_hash = b""
        total_header_size = 0

    # CustomVersions
    custom_versions_count = archive.read_u32()
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError(f"Custom versions count exceeds maximum")
    custom_versions = []
    for _ in range(custom_versions_count):
        guid_bytes = archive.read(16)
        version = archive.read_i32()
        custom_versions.append(CustomVersion(guid=guid_bytes.hex(), version=version))

    if file_version_ue5 < UE5_PACKAGE_SAVED_HASH:
        total_header_size = archive.read_i32()

    # PackageName 和 PackageFlags
    package_name = archive.read_fstring()
    package_flags = archive.read_u32()

    # NameCount 和 NameOffset
    name_count = archive.read_i32()
    if name_count < 0:
        raise ParseError(f"Negative name count: {name_count}")
    if name_count > MAX_NAME_COUNT:
        raise ParseError(f"Name count exceeds maximum")
    name_offset = archive.read_i32()
    archive.validate_offset(name_offset, "NameOffset")

    # SoftObjectPaths
    soft_object_paths_count = 0
    soft_object_paths_offset = 0
    if file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST:
        soft_object_paths_count = archive.read_i32()
        soft_object_paths_offset = archive.read_i32()
        if soft_object_paths_offset > 0:
            archive.validate_offset(soft_object_paths_offset, "SoftObjectPathsOffset")

    # LocalizationId
    localization_id = ""
    has_filter_editor_only = (package_flags & PKG_FilterEditorOnly) != 0
    if not has_filter_editor_only:
        if file_version_ue4 >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
            localization_id = archive.read_fstring()

    # GatherableTextData
    gatherable_text_data_count = 0
    gatherable_text_data_offset = 0
    if file_version_ue4 >= UE4_SERIALIZE_TEXT_IN_PACKAGES:
        gatherable_text_data_count = archive.read_i32()
        gatherable_text_data_offset = archive.read_i32()
        if gatherable_text_data_offset > 0:
            archive.validate_offset(gatherable_text_data_offset, "GatherableTextDataOffset")

    # ExportCount 和 ExportOffset
    export_count = archive.read_i32()
    if export_count < 0:
        raise ParseError(f"Negative export count: {export_count}")
    if export_count > MAX_EXPORT_COUNT:
        raise ParseError(f"Export count exceeds maximum")
    export_offset = archive.read_i32()
    archive.validate_offset(export_offset, "ExportOffset")

    # ImportCount 和 ImportOffset
    import_count = archive.read_i32()
    if import_count < 0:
        raise ParseError(f"Negative import count: {import_count}")
    if import_count > MAX_IMPORT_COUNT:
        raise ParseError(f"Import count exceeds maximum")
    if export_count + import_count > MAX_TOTAL_OBJECT_COUNT:
        raise ParseError(
            f"Total object count ({export_count} + {import_count} = "
            f"{export_count + import_count}) exceeds maximum {MAX_TOTAL_OBJECT_COUNT}"
        )
    import_offset = archive.read_i32()
    archive.validate_offset(import_offset, "ImportOffset")

    # CellExport/CellImport
    cell_export_count = 0
    cell_export_offset = 0
    cell_import_count = 0
    cell_import_offset = 0
    if file_version_ue5 >= UE5_VERSE_CELLS:
        cell_export_count = archive.read_i32()
        if cell_export_count < 0:
            raise ParseError(f"Negative cell export count: {cell_export_count}")
        cell_export_offset = archive.read_i32()
        if cell_export_offset > 0:
            archive.validate_offset(cell_export_offset, "CellExportOffset")
        cell_import_count = archive.read_i32()
        if cell_import_count < 0:
            raise ParseError(f"Negative cell import count: {cell_import_count}")
        cell_import_offset = archive.read_i32()
        if cell_import_offset > 0:
            archive.validate_offset(cell_import_offset, "CellImportOffset")

    # MetaDataOffset
    metadata_offset = 0
    if file_version_ue5 >= UE5_METADATA_SERIALIZATION_OFFSET:
        metadata_offset = archive.read_i32()
        if metadata_offset > 0:
            archive.validate_offset(metadata_offset, "MetadataOffset")

    # DependsOffset
    depends_offset = archive.read_i32()

    # SoftPackageReferences
    soft_package_references_count = 0
    soft_package_references_offset = 0
    if file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP:
        soft_package_references_count = archive.read_i32()
        soft_package_references_offset = archive.read_i32()

    # SearchableNames
    searchable_names_offset = 0
    if file_version_ue4 >= UE4_ADDED_SEARCHABLE_NAMES:
        searchable_names_offset = archive.read_i32()

    # ThumbnailTableOffset
    thumbnail_table_offset = archive.read_i32()
    if thumbnail_table_offset > 0:
        archive.validate_offset(thumbnail_table_offset, "ThumbnailTableOffset")

    # ImportTypeHierarchies
    if file_version_ue5 >= UE5_IMPORT_TYPE_HIERARCHIES:
        import_type_hierarchies_count = archive.read_i32()
        if import_type_hierarchies_count < 0:
            raise ParseError(f"Negative import type hierarchies count: {import_type_hierarchies_count}")
        import_type_hierarchies_offset = archive.read_i32()
        if import_type_hierarchies_offset > 0:
            archive.validate_offset(import_type_hierarchies_offset, "ImportTypeHierarchiesOffset")
    else:
        import_type_hierarchies_count = 0
        import_type_hierarchies_offset = 0

    # PersistentGuid
    persistent_guid = ""
    if not has_filter_editor_only and file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER:
        if legacy_file_version != -6:
            guid_bytes = archive.read(16)
            persistent_guid = guid_bytes.hex()

    # OwnerPersistentGuid
    owner_persistent_guid = ""
    if (
        not has_filter_editor_only
        and (
            file_version_ue4 == UE4_ADDED_PACKAGE_OWNER
            or legacy_file_version in (-8, -7)
        )
    ):
        guid_bytes = archive.read(16)
        owner_persistent_guid = guid_bytes.hex()

    # Generations
    generations_count = archive.read_i32()
    if generations_count < 0:
        raise ParseError(f"Negative generations count: {generations_count}")
    generations = []
    for _ in range(generations_count):
        gen_export_count = archive.read_i32()
        gen_name_count = archive.read_i32()
        generations.append(GenerationInfo(export_count=gen_export_count, name_count=gen_name_count))

    # SavedByEngineVersion
    saved_by_engine_version = EngineVersion(
        major=archive.read_u16(), minor=archive.read_u16(), patch=archive.read_u16(),
        changelist=archive.read_u32(), branch=archive.read_fstring()
    )

    # CompatibleWithEngineVersion
    compatible_with_engine_version = EngineVersion(
        major=archive.read_u16(), minor=archive.read_u16(), patch=archive.read_u16(),
        changelist=archive.read_u32(), branch=archive.read_fstring()
    )

    # CompressionFlags
    compression_flags = archive.read_u32()

    # CompressedChunks
    compressed_chunks_count = archive.read_i32()
    if compressed_chunks_count < 0:
        raise ParseError(f"Negative compressed chunks count: {compressed_chunks_count}")
    compressed_chunks = []
    for _ in range(compressed_chunks_count):
        chunk_data = archive.read(16)
        uncompressed_offset = int.from_bytes(chunk_data[0:4], 'little', signed=True)
        uncompressed_size = int.from_bytes(chunk_data[4:8], 'little', signed=True)
        compressed_offset = int.from_bytes(chunk_data[8:12], 'little', signed=True)
        compressed_size = int.from_bytes(chunk_data[12:16], 'little', signed=True)
        compressed_chunks.append({
            "uncompressed_offset": uncompressed_offset,
            "uncompressed_size": uncompressed_size,
            "compressed_offset": compressed_offset,
            "compressed_size": compressed_size,
        })

    # PackageSource
    package_source = archive.read_u32()

    # AdditionalPackagesToCook
    additional_packages_count = archive.read_i32()
    if additional_packages_count < 0:
        raise ParseError(f"Negative additional packages count: {additional_packages_count}")
    additional_packages_to_cook = []
    for _ in range(additional_packages_count):
        additional_packages_to_cook.append(archive.read_fstring())

    # AssetRegistryDataOffset
    asset_registry_data_offset = archive.read_i32()
    if asset_registry_data_offset > 0:
        archive.validate_offset(asset_registry_data_offset, "AssetRegistryDataOffset")

    # BulkDataStartOffset
    bulk_data_start_offset = archive.read_i64()

    # WorldTileInfoDataOffset
    world_tile_info_data_offset = archive.read_i32()
    if world_tile_info_data_offset > 0:
        archive.validate_offset(world_tile_info_data_offset, "WorldTileInfoDataOffset")

    # ChunkIDs
    chunk_ids = []
    chunk_ids_count = archive.read_i32()
    if chunk_ids_count < 0:
        raise ParseError(f"Negative chunk ids count: {chunk_ids_count}")
    for _ in range(chunk_ids_count):
        guid_bytes = archive.read(16)
        chunk_ids.append(guid_bytes.hex())

    # PreloadDependencies
    preload_dependency_count = 0
    preload_dependency_offset = 0
    if file_version_ue4 >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
        preload_dependency_count = archive.read_i32()
        preload_dependency_offset = archive.read_i32()
        if preload_dependency_offset > 0:
            archive.validate_offset(preload_dependency_offset, "PreloadDependencyOffset")

    # NamesReferencedFromExportData
    names_referenced_from_export_data_count = 0
    if file_version_ue5 >= UE5_NAMES_REFERENCED_FROM_EXPORT_DATA:
        names_referenced_from_export_data_count = archive.read_i32()

    # PayloadTocOffset
    payload_toc_offset = -1
    if file_version_ue5 >= UE5_PAYLOAD_TOC:
        payload_toc_offset = archive.read_i64()

        # Tolerant: 检查 payload_toc_offset 是否合理
        if payload_toc_offset < 0:
            if payload_toc_offset != -1:
                logger.warning(
                    "PayloadTocOffset 异常负值: %d, 设为 INDEX_NONE (-1)",
                    payload_toc_offset,
                )
                payload_toc_offset = -1
        elif payload_toc_offset > 0:
            file_size = archive.total_size()
            if file_size > 0 and payload_toc_offset > file_size * 10:
                logger.warning(
                    "PayloadTocOffset %d 明显越界（文件大小 %d），设为 0",
                    payload_toc_offset, file_size,
                )
                payload_toc_offset = 0
            elif file_size > 0 and payload_toc_offset > file_size:
                logger.debug(
                    "PayloadTocOffset %d 超过文件大小 %d，可能是 virtualized payload",
                    payload_toc_offset, file_size,
                )
            else:
                archive.validate_offset(payload_toc_offset, "PayloadTocOffset")

    # DataResourceOffset
    data_resource_offset = -1
    if file_version_ue5 >= UE5_DATA_RESOURCES:
        data_resource_offset = archive.read_i32()
        if data_resource_offset > 0:
            archive.validate_offset(data_resource_offset, "DataResourceOffset")

    return PackageFileSummary(
        tag=tag, legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5, file_version_licensee=file_version_licensee,
        saved_hash=saved_hash, total_header_size=total_header_size,
        custom_versions=custom_versions, package_name=package_name,
        package_flags=package_flags, name_count=name_count, name_offset=name_offset,
        soft_object_paths_count=soft_object_paths_count,
        soft_object_paths_offset=soft_object_paths_offset,
        localization_id=localization_id,
        gatherable_text_data_count=gatherable_text_data_count,
        gatherable_text_data_offset=gatherable_text_data_offset,
        export_count=export_count, export_offset=export_offset,
        import_count=import_count, import_offset=import_offset,
        cell_export_count=cell_export_count, cell_export_offset=cell_export_offset,
        cell_import_count=cell_import_count, cell_import_offset=cell_import_offset,
        metadata_offset=metadata_offset, depends_offset=depends_offset,
        soft_package_references_count=soft_package_references_count,
        soft_package_references_offset=soft_package_references_offset,
        searchable_names_offset=searchable_names_offset,
        thumbnail_table_offset=thumbnail_table_offset,
        import_type_hierarchies_count=import_type_hierarchies_count,
        import_type_hierarchies_offset=import_type_hierarchies_offset,
        persistent_guid=persistent_guid,
        owner_persistent_guid=owner_persistent_guid,
        generations=generations,
        saved_by_engine_version=saved_by_engine_version,
        compatible_with_engine_version=compatible_with_engine_version,
        compression_flags=compression_flags, package_source=package_source,
        compressed_chunks=compressed_chunks,
        additional_packages_to_cook=additional_packages_to_cook,
        asset_registry_data_offset=asset_registry_data_offset,
        bulk_data_start_offset=bulk_data_start_offset,
        world_tile_info_data_offset=world_tile_info_data_offset,
        chunk_ids=chunk_ids,
        preload_dependency_count=preload_dependency_count,
        preload_dependency_offset=preload_dependency_offset,
        names_referenced_from_export_data_count=names_referenced_from_export_data_count,
        payload_toc_offset=payload_toc_offset,
        data_resource_offset=data_resource_offset
    )
