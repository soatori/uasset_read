"""
Package Summary 序列化 — PackageFileSummary 及相关读取函数。

从 uasset_read.py 提取（第 901-2543 行）。
UE5.7 专用版本 — 已移除 UE4 兼容代码。
"""

from typing import List
from dataclasses import dataclass, field

from uasset_read.archive import FArchive
from uasset_read.constants import (
    PACKAGE_FILE_TAG, PACKAGE_FILE_TAG_SWAPPED,
    UE5_VERSION_MIN, UE5_LEGACY_VERSION,
    MAX_NAME_COUNT, MAX_IMPORT_COUNT, MAX_EXPORT_COUNT, MAX_CUSTOM_VERSIONS,
    UE5_PACKAGE_SAVED_HASH, UE5_ADD_SOFTOBJECTPATH_LIST,
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
)
from uasset_read.exceptions import VersionError, ParseError


@dataclass
class GenerationInfo:
    """FGenerationInfo 版本世代信息。"""
    export_count: int = 0
    name_count: int = 0


@dataclass
class EngineVersion:
    """FEngineVersion 引擎版本信息。"""
    major: int = 0
    minor: int = 0
    patch: int = 0
    changelist: int = 0
    branch: str = ""


@dataclass
class CustomVersion:
    """自定义版本（GUID + 版本号）。"""
    guid: str
    version: int


@dataclass
class PackageFileSummary:
    """PackageFileSummary 文件头。"""
    tag: int
    legacy_file_version: int
    file_version_ue5: int = 0
    file_version_licensee: int = 0
    saved_hash: bytes = field(default_factory=lambda: b'')
    total_header_size: int = 0
    custom_versions: List[CustomVersion] = field(default_factory=list)
    package_name: str = ""
    package_flags: int = 0
    name_count: int = 0
    name_offset: int = 0
    soft_object_paths_count: int = 0
    soft_object_paths_offset: int = 0
    localization_id: str = ""
    gatherable_text_data_count: int = 0
    gatherable_text_data_offset: int = 0
    export_count: int = 0
    export_offset: int = 0
    import_count: int = 0
    import_offset: int = 0
    cell_export_count: int = 0
    cell_export_offset: int = 0
    cell_import_count: int = 0
    cell_import_offset: int = 0
    metadata_offset: int = 0
    depends_offset: int = 0
    soft_package_references_count: int = 0
    soft_package_references_offset: int = 0
    searchable_names_offset: int = 0
    thumbnail_table_offset: int = 0
    import_type_hierarchies_count: int = 0
    import_type_hierarchies_offset: int = 0
    persistent_guid: str = ""
    generations: List[GenerationInfo] = field(default_factory=list)
    saved_by_engine_version: EngineVersion = field(default_factory=EngineVersion)
    compatible_with_engine_version: EngineVersion = field(default_factory=EngineVersion)
    compression_flags: int = 0
    package_source: int = 0
    asset_registry_data_offset: int = 0
    bulk_data_start_offset: int = 0
    world_tile_info_data_offset: int = 0
    chunk_ids: List[str] = field(default_factory=list)
    preload_dependency_count: int = 0
    preload_dependency_offset: int = 0
    names_referenced_from_export_data_count: int = 0
    payload_toc_offset: int = 0
    data_resource_offset: int = 0

    def get_custom_version(self, guid: str, default: int = 0) -> int:
        """查找 CustomVersion 版本值。"""
        normalized_guid = guid.replace("-", "").lower()
        for cv in self.custom_versions:
            if cv.guid == normalized_guid:
                return cv.version
        return default


def read_package_summary(archive: FArchive) -> PackageFileSummary:
    """读取 PackageFileSummary 文件头（UE5.7 专用）。"""
    archive.seek(0)

    # 第 1 步：魔数和版本号
    tag = archive.read_u32()
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    elif tag != PACKAGE_FILE_TAG:
        raise VersionError(f"Invalid package tag: {hex(tag)}")

    legacy_file_version = archive.read_i32()
    if legacy_file_version != UE5_LEGACY_VERSION:
        raise VersionError(
            f"Only UE5 files (legacy_file_version={UE5_LEGACY_VERSION}) are supported, "
            f"got {legacy_file_version}"
        )

    legacy_ue3_version = archive.read_i32()
    file_version_ue4 = archive.read_i32()  # kept for internal reference only
    file_version_ue5 = archive.read_i32()

    if file_version_ue5 < UE5_VERSION_MIN:
        raise VersionError(f"Unsupported UE5 version: {file_version_ue5}")

    file_version_licensee = archive.read_i32()

    # 第 2 步：SavedHash + TotalHeaderSize（UE5.7 始终存在）
    saved_hash = archive.read(20)
    total_header_size = archive.read_i32()

    # 第 3 步：CustomVersions
    custom_versions_count = archive.read_u32()
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError(f"Custom versions count exceeds maximum")
    custom_versions = []
    for _ in range(custom_versions_count):
        guid_bytes = archive.read(16)
        version = archive.read_i32()
        custom_versions.append(CustomVersion(guid=guid_bytes.hex(), version=version))

    # 第 4 步：PackageName 和 PackageFlags
    package_name = archive.read_fstring()
    package_flags = archive.read_u32()

    # 第 5 步：NameCount 和 NameOffset
    name_count = archive.read_i32()
    if name_count < 0:
        raise ParseError(f"Negative name count: {name_count}")
    if name_count > MAX_NAME_COUNT:
        raise ParseError(f"Name count exceeds maximum")
    name_offset = archive.read_i32()
    archive.validate_offset(name_offset, "NameOffset")

    # 第 6 步：SoftObjectPaths（UE5.7 始终存在）
    soft_object_paths_count = archive.read_i32()
    soft_object_paths_offset = archive.read_i32()
    if soft_object_paths_offset > 0:
        archive.validate_offset(soft_object_paths_offset, "SoftObjectPathsOffset")

    # 第 7 步：LocalizationId（非 FilterEditorOnly 文件，UE4 516+）
    localization_id = ""
    has_filter_editor_only = (package_flags & PKG_FilterEditorOnly) != 0
    if not has_filter_editor_only:
        if file_version_ue4 >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
            localization_id = archive.read_fstring()

    # 第 8 步：GatherableTextData（UE4 517+，无 filter 检查）
    gatherable_text_data_count = 0
    gatherable_text_data_offset = 0
    if file_version_ue4 >= UE4_SERIALIZE_TEXT_IN_PACKAGES:
        gatherable_text_data_count = archive.read_i32()
        gatherable_text_data_offset = archive.read_i32()
        if gatherable_text_data_offset > 0:
            archive.validate_offset(gatherable_text_data_offset, "GatherableTextDataOffset")

    # 第 9 步：ExportCount 和 ExportOffset
    export_count = archive.read_i32()
    if export_count < 0:
        raise ParseError(f"Negative export count: {export_count}")
    if export_count > MAX_EXPORT_COUNT:
        raise ParseError(f"Export count exceeds maximum")
    export_offset = archive.read_i32()
    archive.validate_offset(export_offset, "ExportOffset")

    # 第 10 步：ImportCount 和 ImportOffset
    import_count = archive.read_i32()
    if import_count < 0:
        raise ParseError(f"Negative import count: {import_count}")
    if import_count > MAX_IMPORT_COUNT:
        raise ParseError(f"Import count exceeds maximum")
    import_offset = archive.read_i32()
    archive.validate_offset(import_offset, "ImportOffset")

    # 第 11 步：CellExport/CellImport（UE5.7 始终存在）
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

    # 第 12 步：MetaDataOffset（UE5 始终存在）
    metadata_offset = archive.read_i32()
    if metadata_offset > 0:
        archive.validate_offset(metadata_offset, "MetadataOffset")

    # 第 13 步：DependsOffset
    depends_offset = archive.read_i32()

    # 第 13.5 步：SoftPackageReferences（UE4 516+）
    soft_package_references_count = 0
    soft_package_references_offset = 0
    if file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP:
        soft_package_references_count = archive.read_i32()
        soft_package_references_offset = archive.read_i32()

    # 第 13.6 步：SearchableNames（UE4 518+）
    searchable_names_offset = 0
    if file_version_ue4 >= UE4_ADDED_SEARCHABLE_NAMES:
        searchable_names_offset = archive.read_i32()

    # 第 14 步：ThumbnailTableOffset
    thumbnail_table_offset = archive.read_i32()
    if thumbnail_table_offset > 0:
        archive.validate_offset(thumbnail_table_offset, "ThumbnailTableOffset")

    # 第 15 步：ImportTypeHierarchies
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

    # 第 16 步：PersistentGuid（非 FilterEditorOnly 文件，UE4 519+）
    persistent_guid = ""
    if not has_filter_editor_only and file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER:
        guid_bytes = archive.read(16)
        persistent_guid = guid_bytes.hex()

    # 第 16b 步：OwnerPersistentGuid（仅 UE4 519，后续版本已移除）
    if not has_filter_editor_only and file_version_ue4 == UE4_ADDED_PACKAGE_OWNER:
        archive.read(16)  # 跳过 OwnerPersistentGuid

    # 第 17 步：Generations
    generations_count = archive.read_i32()
    if generations_count < 0:
        raise ParseError(f"Negative generations count: {generations_count}")
    generations = []
    for _ in range(generations_count):
        gen_export_count = archive.read_i32()
        gen_name_count = archive.read_i32()
        generations.append(GenerationInfo(export_count=gen_export_count, name_count=gen_name_count))

    # 第 18 步：SavedByEngineVersion（UE5.7 始终为 FEngineVersion 结构）
    saved_by_engine_version = EngineVersion(
        major=archive.read_u16(), minor=archive.read_u16(), patch=archive.read_u16(),
        changelist=archive.read_u32(), branch=archive.read_fstring()
    )

    # 第 19 步：CompatibleWithEngineVersion（UE5.7 始终存在）
    compatible_with_engine_version = EngineVersion(
        major=archive.read_u16(), minor=archive.read_u16(), patch=archive.read_u16(),
        changelist=archive.read_u32(), branch=archive.read_fstring()
    )

    # 第 20 步：CompressionFlags
    compression_flags = archive.read_u32()

    # 第 21 步：CompressedChunks（已废弃）
    compressed_chunks_count = archive.read_i32()
    if compressed_chunks_count < 0:
        raise ParseError(f"Negative compressed chunks count: {compressed_chunks_count}")
    for _ in range(compressed_chunks_count):
        archive.read(12)

    # 第 22 步：PackageSource
    package_source = archive.read_u32()

    # 第 23 步：AdditionalPackagesToCook
    additional_packages_count = archive.read_i32()
    if additional_packages_count < 0:
        raise ParseError(f"Negative additional packages count: {additional_packages_count}")
    for _ in range(additional_packages_count):
        archive.read_fstring()

    # 第 24 步：AssetRegistryDataOffset
    asset_registry_data_offset = archive.read_i32()
    if asset_registry_data_offset > 0:
        archive.validate_offset(asset_registry_data_offset, "AssetRegistryDataOffset")

    # 第 25 步：BulkDataStartOffset
    bulk_data_start_offset = archive.read_i64()

    # 第 26 步：WorldTileInfoDataOffset
    world_tile_info_data_offset = archive.read_i32()
    if world_tile_info_data_offset > 0:
        archive.validate_offset(world_tile_info_data_offset, "WorldTileInfoDataOffset")

    # 第 27 步：ChunkIDs（UE5 始终为数组格式）
    chunk_ids = []
    chunk_ids_count = archive.read_i32()
    if chunk_ids_count < 0:
        raise ParseError(f"Negative chunk ids count: {chunk_ids_count}")
    for _ in range(chunk_ids_count):
        guid_bytes = archive.read(16)
        chunk_ids.append(guid_bytes.hex())

    # 第 28 步：PreloadDependencies（UE5.7 始终存在）
    preload_dependency_count = archive.read_i32()
    preload_dependency_offset = archive.read_i32()
    if preload_dependency_offset > 0:
        archive.validate_offset(preload_dependency_offset, "PreloadDependencyOffset")

    # 第 29 步：NamesReferencedFromExportData（UE5.7 始终存在）
    names_referenced_from_export_data_count = archive.read_i32()

    # 第 30 步：PayloadTocOffset（UE5.7 始终存在）
    payload_toc_offset = archive.read_i64()
    if payload_toc_offset > 0:
        archive.validate_offset(payload_toc_offset, "PayloadTocOffset")

    # 第 31 步：DataResourceOffset（UE5.7 始终存在）
    data_resource_offset = archive.read_i32()
    if data_resource_offset > 0:
        archive.validate_offset(data_resource_offset, "DataResourceOffset")

    return PackageFileSummary(
        tag=tag, legacy_file_version=legacy_file_version,
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
        persistent_guid=persistent_guid, generations=generations,
        saved_by_engine_version=saved_by_engine_version,
        compatible_with_engine_version=compatible_with_engine_version,
        compression_flags=compression_flags, package_source=package_source,
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


def read_name_table(archive: FArchive, summary: PackageFileSummary) -> List[str]:
    """读取名称表（UE5.7 专用）。"""
    archive.seek(summary.name_offset)

    name_map = []
    for _ in range(summary.name_count):
        name = archive.read_fstring()
        name_map.append(name)
        # UE5 始终有 name hashes (4 bytes)
        archive.read(4)
    return name_map
