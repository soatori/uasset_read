"""UE4 PackageFileSummary 读取函数。"""
from __future__ import annotations

import logging
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.constants import (
    MAX_NAME_COUNT, MAX_IMPORT_COUNT, MAX_EXPORT_COUNT, MAX_CUSTOM_VERSIONS,
    MAX_TOTAL_OBJECT_COUNT,
    PKG_FilterEditorOnly,
    UE4_ADD_STRING_ASSET_REFERENCES_MAP,
    UE4_ADDED_SEARCHABLE_NAMES,
    UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID,
    UE4_SERIALIZE_TEXT_IN_PACKAGES,
    UE4_ADDED_PACKAGE_OWNER,
    UE4_NON_OUTER_PACKAGE_IMPORT,
    VER_UE4_ENGINE_VERSION_OBJECT,
    VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION,
)
from uasset_read.exceptions import ParseError
from .models import GenerationInfo, EngineVersion, CustomVersion, PackageFileSummary

logger = logging.getLogger(__name__)


def read_ue4_package_summary(
    archive: "FArchive",
    tag: int,
    legacy_file_version: int,
) -> PackageFileSummary:
    """读取 UE4 格式的 PackageFileSummary。"""
    # UE3 version (仅 legacy > -4 时存在)
    if legacy_file_version != -4:
        legacy_ue3_version = archive.read_i32()
    else:
        legacy_ue3_version = 0

    file_version_ue4 = archive.read_i32()
    file_version_licensee = archive.read_i32()

    # CustomVersions
    custom_versions = _read_custom_versions_ue4(archive, legacy_file_version)

    total_header_size = archive.read_i32()

    # PackageName (UE4 特有)
    package_name = archive.read_fstring()

    package_flags = archive.read_u32()
    has_filter_editor_only = (package_flags & PKG_FilterEditorOnly) != 0

    # NameCount 和 NameOffset
    name_count = archive.read_i32()
    if name_count < 0:
        raise ParseError(f"Negative name count: {name_count}")
    if name_count > MAX_NAME_COUNT:
        raise ParseError(f"Name count exceeds maximum")
    name_offset = archive.read_i32()
    archive.validate_offset(name_offset, "NameOffset")

    # LocalizationId (UE4 516+)
    localization_id = ""
    if not has_filter_editor_only:
        if file_version_ue4 >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
            localization_id = archive.read_fstring()

    # GatherableTextData (UE4 517+)
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

    # DependsOffset
    depends_offset = archive.read_i32()

    # SoftPackageReferences (UE4 516+)
    soft_package_references_count = 0
    soft_package_references_offset = 0
    if file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP:
        soft_package_references_count = archive.read_i32()
        soft_package_references_offset = archive.read_i32()

    # SearchableNames (UE4 518+)
    searchable_names_offset = 0
    if file_version_ue4 >= UE4_ADDED_SEARCHABLE_NAMES:
        searchable_names_offset = archive.read_i32()

    # ThumbnailTableOffset
    thumbnail_table_offset = archive.read_i32()
    if thumbnail_table_offset > 0:
        archive.validate_offset(thumbnail_table_offset, "ThumbnailTableOffset")

    # Guid
    guid_bytes = archive.read(16)
    persistent_guid = guid_bytes.hex()

    # OwnerPersistentGuid
    owner_persistent_guid = ""
    if (
        not has_filter_editor_only
        and file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER
        and file_version_ue4 < UE4_NON_OUTER_PACKAGE_IMPORT
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
    if file_version_ue4 >= VER_UE4_ENGINE_VERSION_OBJECT:
        saved_by_engine_version = EngineVersion(
            major=archive.read_u16(), minor=archive.read_u16(), patch=archive.read_u16(),
            changelist=archive.read_u32(), branch=archive.read_fstring()
        )
    else:
        engine_changelist = archive.read_i32()
        saved_by_engine_version = EngineVersion(
            major=4, minor=0, patch=0, changelist=engine_changelist, branch=""
        )

    # CompatibleWithEngineVersion
    if file_version_ue4 >= VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION:
        compatible_with_engine_version = EngineVersion(
            major=archive.read_u16(), minor=archive.read_u16(), patch=archive.read_u16(),
            changelist=archive.read_u32(), branch=archive.read_fstring()
        )
    else:
        compatible_with_engine_version = saved_by_engine_version

    # CompressionFlags
    compression_flags = archive.read_u32()

    # CompressedChunks (已废弃)
    compressed_chunks_count = archive.read_i32()
    if compressed_chunks_count < 0:
        raise ParseError(f"Negative compressed chunks count: {compressed_chunks_count}")
    if compressed_chunks_count > 10000:
        raise ParseError(f"CompressedChunks count exceeds maximum: {compressed_chunks_count}")
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

    # AdditionalPackagesToCook (已废弃)
    additional_packages_count = archive.read_i32()
    if additional_packages_count < 0:
        raise ParseError(f"Negative additional packages count: {additional_packages_count}")
    additional_packages_to_cook = []
    for _ in range(additional_packages_count):
        additional_packages_to_cook.append(archive.read_fstring())

    # TextureAllocations
    if legacy_file_version > -7:
        num_texture_allocations = archive.read_i32()

    # AssetRegistryDataOffset
    asset_registry_data_offset = archive.read_i32()
    if asset_registry_data_offset > 0:
        archive.validate_offset(asset_registry_data_offset, "AssetRegistryDataOffset")

    # BulkDataStartOffset
    bulk_data_start_offset = archive.read_i64()

    # WorldTileInfoDataOffset (UE4 447+)
    world_tile_info_data_offset = 0
    if file_version_ue4 >= 447:
        world_tile_info_data_offset = archive.read_i32()
        if world_tile_info_data_offset > 0:
            archive.validate_offset(world_tile_info_data_offset, "WorldTileInfoDataOffset")

    # ChunkIDs (UE4 459+ 为数组格式)
    chunk_ids = []
    if file_version_ue4 >= 459:
        chunk_ids_count = archive.read_i32()
        if chunk_ids_count < 0:
            raise ParseError(f"Negative chunk ids count: {chunk_ids_count}")
        for _ in range(chunk_ids_count):
            guid_bytes = archive.read(16)
            chunk_ids.append(guid_bytes.hex())
    elif file_version_ue4 >= 443:
        chunk_id = archive.read_i32()
        if chunk_id >= 0:
            chunk_ids.append(format(chunk_id, '032x'))

    # PreloadDependencies (UE4 506+)
    preload_dependency_count = 0
    preload_dependency_offset = 0
    if file_version_ue4 >= 506:
        preload_dependency_count = archive.read_i32()
        preload_dependency_offset = archive.read_i32()
        if preload_dependency_offset > 0:
            archive.validate_offset(preload_dependency_offset, "PreloadDependencyOffset")

    return PackageFileSummary(
        tag=tag, legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=0,
        file_version_licensee=file_version_licensee,
        saved_hash=b"",
        total_header_size=total_header_size,
        custom_versions=custom_versions, package_name=package_name,
        package_flags=package_flags, name_count=name_count, name_offset=name_offset,
        soft_object_paths_count=0,
        soft_object_paths_offset=0,
        localization_id=localization_id,
        gatherable_text_data_count=gatherable_text_data_count,
        gatherable_text_data_offset=gatherable_text_data_offset,
        export_count=export_count, export_offset=export_offset,
        import_count=import_count, import_offset=import_offset,
        cell_export_count=0, cell_export_offset=0,
        cell_import_count=0, cell_import_offset=0,
        metadata_offset=0, depends_offset=depends_offset,
        soft_package_references_count=soft_package_references_count,
        soft_package_references_offset=soft_package_references_offset,
        searchable_names_offset=searchable_names_offset,
        thumbnail_table_offset=thumbnail_table_offset,
        import_type_hierarchies_count=0,
        import_type_hierarchies_offset=0,
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
        names_referenced_from_export_data_count=0,
        payload_toc_offset=-1,
        data_resource_offset=-1
    )


def _read_custom_versions_ue4(
    archive: "FArchive",
    legacy_file_version: int,
) -> List[CustomVersion]:
    """读取 UE4 格式的 CustomVersions。"""
    if legacy_file_version > -2:
        return []

    if legacy_file_version == -2:
        logger.warning("CustomVersion Enums format (legacy -2) not fully supported")
        return []
    elif -5 <= legacy_file_version <= -3:
        count = archive.read_i32()
        if count < 0 or count > MAX_CUSTOM_VERSIONS:
            return []
        versions = []
        for _ in range(count):
            guid_bytes = archive.read(16)
            version = archive.read_i32()
            versions.append(CustomVersion(guid=guid_bytes.hex(), version=version))
        return versions
    else:
        count = archive.read_u32()
        if count > MAX_CUSTOM_VERSIONS:
            return []
        versions = []
        for _ in range(count):
            guid_bytes = archive.read(16)
            version = archive.read_i32()
            versions.append(CustomVersion(guid=guid_bytes.hex(), version=version))
        return versions
