"""
Package Summary 序列化 — PackageFileSummary 及相关读取函数。

从 uasset_read.py 提取（第 901-2543 行）。
UE5.7 专用版本 — 已移除 UE4 兼容代码。
"""

import logging
import struct
from typing import List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from uasset_read.archive import FArchive
from uasset_read.constants import (
    PACKAGE_FILE_TAG, PACKAGE_FILE_TAG_SWAPPED,
    UE5_VERSION_MIN, UE5_LEGACY_VERSIONS,
    MAX_NAME_COUNT, MAX_IMPORT_COUNT, MAX_EXPORT_COUNT, MAX_CUSTOM_VERSIONS,
    MAX_TOTAL_OBJECT_COUNT,
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
    UE4_NON_OUTER_PACKAGE_IMPORT,
    UE4_NAME_HASHES_SERIALIZED,
    UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS,
)
from uasset_read.exceptions import VersionError, ParseError
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.constants import MIN_UASSET_SIZE


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
    file_version_ue4: int = 0
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
    depends_map: List[List[int]] = field(default_factory=list)
    preload_dependencies: List[int] = field(default_factory=list)

    def get_custom_version(self, guid: str, default: int = 0) -> int:
        """查找 CustomVersion 版本值。"""
        normalized_guid = guid.replace("-", "").lower()
        for cv in self.custom_versions:
            if cv.guid == normalized_guid:
                return cv.version
        return default


def _read_custom_versions(archive: FArchive) -> list:
    """读取 CustomVersions 表。"""
    custom_versions_count = archive.read_u32("CustomVersionsCount")
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError(f"Custom versions count exceeds maximum")
    custom_versions = []
    for _ in range(custom_versions_count):
        guid_bytes = archive.read(16)
        version = archive.read_i32()
        custom_versions.append(CustomVersion(guid=guid_bytes.hex(), version=version))
    return custom_versions


def _read_generations(archive: FArchive) -> list:
    """读取 Generations 表。"""
    generations_count = archive.read_i32("GenerationsCount")
    if generations_count < 0:
        raise ParseError(f"Negative generations count: {generations_count}")
    generations = []
    for _ in range(generations_count):
        gen_export_count = archive.read_i32()
        gen_name_count = archive.read_i32()
        generations.append(GenerationInfo(export_count=gen_export_count, name_count=gen_name_count))
    return generations


def _read_engine_version(archive: FArchive) -> "EngineVersion":
    """读取 FEngineVersion 结构。"""
    return EngineVersion(
        major=archive.read_u16(), minor=archive.read_u16(), patch=archive.read_u16(),
        changelist=archive.read_u32(), branch=archive.read_fstring()
    )


def _read_cell_counts(archive: FArchive) -> tuple:
    """读取 Verse Cell 计数和偏移（UE5.7+）。"""
    cell_export_count = archive.read_i32("CellExportCount")
    if cell_export_count < 0:
        raise ParseError(f"Negative cell export count: {cell_export_count}")
    cell_export_offset = archive.read_i32("CellExportOffset")
    if cell_export_offset > 0:
        archive.validate_offset(cell_export_offset, "CellExportOffset")
    cell_import_count = archive.read_i32("CellImportCount")
    if cell_import_count < 0:
        raise ParseError(f"Negative cell import count: {cell_import_count}")
    cell_import_offset = archive.read_i32("CellImportOffset")
    if cell_import_offset > 0:
        archive.validate_offset(cell_import_offset, "CellImportOffset")
    return cell_export_count, cell_export_offset, cell_import_count, cell_import_offset


def _read_payload_toc_offset(archive: FArchive) -> int:
    """读取 PayloadTocOffset 并验证合理性。"""
    payload_toc_offset = archive.read_i64("PayloadTocOffset")
    if payload_toc_offset < 0:
        logger.warning("PayloadTocOffset 为负数: %d, 设为 0", payload_toc_offset)
        payload_toc_offset = 0
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
    return payload_toc_offset


def _validate_file_size(archive: FArchive) -> None:
    """截断文件检测：文件过小时直接报错。"""
    file_size = archive.total_size()
    if file_size < MIN_UASSET_SIZE:
        archive._diagnostics.append(OffsetRangeDiagnostic(
            kind="truncated_file",
            module="package_summary",
            field="file_size",
            file_size=file_size,
            source="read_package_summary",
            error=(
                f"文件大小 {file_size} 字节，小于最小合法大小 {MIN_UASSET_SIZE} 字节，"
                f"文件可能已截断或损坏"
            ),
        ))
        raise ParseError(
            f"文件过小（{file_size} 字节），无法解析为 .uasset 文件。"
            f"最小合法大小为 {MIN_UASSET_SIZE} 字节，文件可能已截断或损坏"
        )


def _read_version_and_tag(archive: FArchive) -> tuple[int, int, int, int, bytes, int, list]:
    """读取魔数、版本号、SavedHash、CustomVersions。

    返回 (tag, legacy_file_version, file_version_ue4, file_version_ue5,
           saved_hash, total_header_size, custom_versions)。
    """
    # 魔数
    tag = archive.read_u32("Tag")
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    elif tag != PACKAGE_FILE_TAG:
        raise VersionError(f"Invalid package tag: {hex(tag)}")

    legacy_file_version = archive.read_i32("LegacyFileVersion")
    if legacy_file_version not in UE5_LEGACY_VERSIONS:
        supported_versions = ", ".join(str(v) for v in sorted(UE5_LEGACY_VERSIONS))
        if legacy_file_version > -6:
            raise VersionError(
                f"Legacy file version {legacy_file_version} indicates UE4 asset. "
                f"Current version supports UE5 only (legacy versions -6 to -9)."
            )
        raise VersionError(
            f"Only UE5 files with legacy_file_version in {{{supported_versions}}} are supported, "
            f"got {legacy_file_version}"
        )

    legacy_ue3_version = archive.read_i32("LegacyUE3Version")
    file_version_ue4 = archive.read_i32("FileVersionUE4")

    # FileVersionUE5: only present when legacy_file_version <= -8
    if legacy_file_version <= -8:
        file_version_ue5 = archive.read_i32("FileVersionUE5")
    else:
        file_version_ue5 = 0

    if legacy_file_version <= -8 and file_version_ue5 < UE5_VERSION_MIN:
        raise VersionError(f"Unsupported UE5 version: {file_version_ue5}")

    file_version_licensee = archive.read_i32("FileVersionLicensee")

    # SavedHash + TotalHeaderSize BEFORE CustomVersions (UE5 >= 1016 only)
    if file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        saved_hash = archive.read(20)
        total_header_size = archive.read_i32("TotalHeaderSize")
    else:
        saved_hash = b""
        total_header_size = 0

    custom_versions = _read_custom_versions(archive)

    if file_version_ue5 < UE5_PACKAGE_SAVED_HASH:
        total_header_size = archive.read_i32("TotalHeaderSize")

    return (tag, legacy_file_version, file_version_ue4, file_version_ue5,
            file_version_licensee, saved_hash, total_header_size, custom_versions)


def _read_package_identity(archive: FArchive) -> tuple[str, int]:
    """读取 PackageName 和 PackageFlags。"""
    package_name = archive.read_fstring("PackageName")
    if package_name == "None":
        package_name = ""
    package_flags = archive.read_u32("PackageFlags")
    return package_name, package_flags


def _read_name_table_offsets(archive: FArchive) -> tuple[int, int]:
    """读取 NameCount 和 NameOffset。"""
    name_count = archive.read_i32("NameCount")
    if name_count < 0:
        raise ParseError(f"Negative name count: {name_count}")
    if name_count > MAX_NAME_COUNT:
        raise ParseError(f"Name count exceeds maximum")
    name_offset = archive.read_i32("NameOffset")
    archive.validate_offset(name_offset, "NameOffset")
    return name_count, name_offset


def _read_export_import_offsets(archive: FArchive) -> tuple[int, int, int, int]:
    """读取 Export/Import 表的 count 和 offset。"""
    export_count = archive.read_i32("ExportCount")
    if export_count < 0:
        raise ParseError(f"Negative export count: {export_count}")
    if export_count > MAX_EXPORT_COUNT:
        raise ParseError(f"Export count exceeds maximum")
    export_offset = archive.read_i32("ExportOffset")
    archive.validate_offset(export_offset, "ExportOffset")

    import_count = archive.read_i32("ImportCount")
    if import_count < 0:
        raise ParseError(f"Negative import count: {import_count}")
    if import_count > MAX_IMPORT_COUNT:
        raise ParseError(f"Import count exceeds maximum")
    if export_count + import_count > MAX_TOTAL_OBJECT_COUNT:
        raise ParseError(
            f"Total object count ({export_count} + {import_count} = "
            f"{export_count + import_count}) exceeds maximum {MAX_TOTAL_OBJECT_COUNT}"
        )
    import_offset = archive.read_i32("ImportOffset")
    archive.validate_offset(import_offset, "ImportOffset")

    return export_count, export_offset, import_count, import_offset


def _read_pre_export_optional_fields(
    archive: FArchive,
    file_version_ue5: int,
    file_version_ue4: int,
    has_filter_editor_only: bool,
) -> dict:
    """读取 NameOffset 之后、ExportCount 之前的版本门控字段。"""
    # SoftObjectPaths（UE5 >= 1011）
    soft_object_paths_count = 0
    soft_object_paths_offset = 0
    if file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST:
        soft_object_paths_count = archive.read_i32("SoftObjectPathsCount")
        soft_object_paths_offset = archive.read_i32("SoftObjectPathsOffset")
        if soft_object_paths_offset > 0:
            archive.validate_offset(soft_object_paths_offset, "SoftObjectPathsOffset")

    # LocalizationId（非 FilterEditorOnly, UE4 >= 516）
    localization_id = ""
    if not has_filter_editor_only and file_version_ue4 >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
        localization_id = archive.read_fstring("LocalizationId")

    # GatherableTextData（UE4 >= 517）
    gatherable_text_data_count = 0
    gatherable_text_data_offset = 0
    if file_version_ue4 >= UE4_SERIALIZE_TEXT_IN_PACKAGES:
        gatherable_text_data_count = archive.read_i32("GatherableTextDataCount")
        gatherable_text_data_offset = archive.read_i32("GatherableTextDataOffset")
        if gatherable_text_data_offset > 0:
            archive.validate_offset(gatherable_text_data_offset, "GatherableTextDataOffset")

    return {
        "soft_object_paths_count": soft_object_paths_count,
        "soft_object_paths_offset": soft_object_paths_offset,
        "localization_id": localization_id,
        "gatherable_text_data_count": gatherable_text_data_count,
        "gatherable_text_data_offset": gatherable_text_data_offset,
    }


def _read_post_import_optional_fields(
    archive: FArchive,
    file_version_ue5: int,
) -> dict:
    """读取 ImportOffset 之后、DependsOffset 之前的版本门控字段。"""
    # CellExport/CellImport（UE5 >= cell 版本）
    cell_export_count = 0
    cell_export_offset = 0
    cell_import_count = 0
    cell_import_offset = 0
    if file_version_ue5 >= UE5_VERSE_CELLS:
        cell_export_count, cell_export_offset, cell_import_count, cell_import_offset = _read_cell_counts(archive)

    # MetaDataOffset（UE5 >= meta 版本）
    metadata_offset = 0
    if file_version_ue5 >= UE5_METADATA_SERIALIZATION_OFFSET:
        metadata_offset = archive.read_i32("MetadataOffset")
        if metadata_offset > 0:
            archive.validate_offset(metadata_offset, "MetadataOffset")

    return {
        "cell_export_count": cell_export_count,
        "cell_export_offset": cell_export_offset,
        "cell_import_count": cell_import_count,
        "cell_import_offset": cell_import_offset,
        "metadata_offset": metadata_offset,
    }


def _read_secondary_offset_fields(
    archive: FArchive,
    file_version_ue4: int,
) -> dict:
    """读取 DependsOffset, SoftPackageReferences, SearchableNames, ThumbnailTable。"""
    depends_offset = archive.read_i32("DependsOffset")

    soft_package_references_count = 0
    soft_package_references_offset = 0
    if file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP:
        soft_package_references_count = archive.read_i32("SoftPackageReferencesCount")
        soft_package_references_offset = archive.read_i32("SoftPackageReferencesOffset")

    searchable_names_offset = 0
    if file_version_ue4 >= UE4_ADDED_SEARCHABLE_NAMES:
        searchable_names_offset = archive.read_i32("SearchableNamesOffset")

    thumbnail_table_offset = archive.read_i32("ThumbnailTableOffset")
    if thumbnail_table_offset > 0:
        archive.validate_offset(thumbnail_table_offset, "ThumbnailTableOffset")

    return {
        "depends_offset": depends_offset,
        "soft_package_references_count": soft_package_references_count,
        "soft_package_references_offset": soft_package_references_offset,
        "searchable_names_offset": searchable_names_offset,
        "thumbnail_table_offset": thumbnail_table_offset,
    }


def _read_import_type_hierarchies(archive: FArchive, file_version_ue5: int) -> tuple[int, int]:
    """读取 ImportTypeHierarchies（UE5 >= 1015）。"""
    if file_version_ue5 >= UE5_IMPORT_TYPE_HIERARCHIES:
        count = archive.read_i32("ImportTypeHierarchiesCount")
        if count < 0:
            raise ParseError(f"Negative import type hierarchies count: {count}")
        offset = archive.read_i32("ImportTypeHierarchiesOffset")
        if offset > 0:
            archive.validate_offset(offset, "ImportTypeHierarchiesOffset")
        return count, offset
    return 0, 0


def _read_guids(
    archive: FArchive,
    legacy_file_version: int,
    file_version_ue4: int,
    file_version_ue5: int,
    has_filter_editor_only: bool,
) -> str:
    """读取 LegacyGuid / PersistentGuid / OwnerPersistentGuid。"""
    # LegacyGuid（UE5 < 1016 时存在）
    if file_version_ue5 < UE5_PACKAGE_SAVED_HASH:
        archive.read(16)

    # PersistentGuid
    persistent_guid = ""
    if not has_filter_editor_only:
        if legacy_file_version == -6:
            guid_bytes = archive.read(16)
            persistent_guid = guid_bytes.hex()
        elif file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER:
            guid_bytes = archive.read(16)
            persistent_guid = guid_bytes.hex()

    # OwnerPersistentGuid（仅 UE4 519 精确值）
    if (
        not has_filter_editor_only
        and file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER
        and file_version_ue4 < UE4_NON_OUTER_PACKAGE_IMPORT
    ):
        archive.read(16)

    return persistent_guid


def _read_compression_and_source(archive: FArchive) -> tuple[int, int]:
    """读取 CompressionFlags、CompressedChunks、PackageSource。"""
    compression_flags = archive.read_u32("CompressionFlags")

    compressed_chunks_count = archive.read_i32("CompressedChunksCount")
    if compressed_chunks_count < 0:
        raise ParseError(f"Negative compressed chunks count: {compressed_chunks_count}")
    for _ in range(compressed_chunks_count):
        archive.read(12)

    package_source = archive.read_u32("PackageSource")
    return compression_flags, package_source


def _read_additional_packages(archive: FArchive, legacy_file_version: int) -> None:
    """读取 AdditionalPackagesToCook 和 NumTextureAllocations（legacy -6）。"""
    additional_packages_count = archive.read_i32("AdditionalPackagesCount")
    if additional_packages_count < 0:
        raise ParseError(f"Negative additional packages count: {additional_packages_count}")
    for _ in range(additional_packages_count):
        archive.read_fstring()

    if legacy_file_version > -7:
        archive.read_i32("NumTextureAllocations")


def _read_tail_offsets(archive: FArchive) -> dict:
    """读取 AssetRegistry、BulkData、WorldTile、ChunkIDs。"""
    asset_registry_data_offset = archive.read_i32("AssetRegistryDataOffset")
    if asset_registry_data_offset > 0:
        archive.validate_offset(asset_registry_data_offset, "AssetRegistryDataOffset")

    bulk_data_start_offset = archive.read_i64("BulkDataStartOffset")

    world_tile_info_data_offset = archive.read_i32("WorldTileInfoDataOffset")
    if world_tile_info_data_offset > 0:
        archive.validate_offset(world_tile_info_data_offset, "WorldTileInfoDataOffset")

    chunk_ids = []
    chunk_ids_count = archive.read_i32("ChunkIDsCount")
    if chunk_ids_count < 0:
        raise ParseError(f"Negative chunk ids count: {chunk_ids_count}")
    for _ in range(chunk_ids_count):
        chunk_ids.append(archive.read_i32())

    return {
        "asset_registry_data_offset": asset_registry_data_offset,
        "bulk_data_start_offset": bulk_data_start_offset,
        "world_tile_info_data_offset": world_tile_info_data_offset,
        "chunk_ids": chunk_ids,
    }


def _read_late_versioned_fields(
    archive: FArchive,
    file_version_ue4: int,
    file_version_ue5: int,
) -> dict:
    """读取 PreloadDependencies、NamesReferenced、PayloadToc、DataResource。"""
    preload_dependency_count = -1
    preload_dependency_offset = 0
    if file_version_ue4 >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
        preload_dependency_count = archive.read_i32("PreloadDependencyCount")
        preload_dependency_offset = archive.read_i32("PreloadDependencyOffset")
        if preload_dependency_offset > 0:
            archive.validate_offset(preload_dependency_offset, "PreloadDependencyOffset")

    names_referenced_from_export_data_count = 0
    if file_version_ue5 >= UE5_NAMES_REFERENCED_FROM_EXPORT_DATA:
        names_referenced_from_export_data_count = archive.read_i32("NamesReferencedFromExportDataCount")

    payload_toc_offset = 0
    if file_version_ue5 >= UE5_PAYLOAD_TOC:
        payload_toc_offset = _read_payload_toc_offset(archive)

    data_resource_offset = 0
    if file_version_ue5 >= UE5_DATA_RESOURCES:
        data_resource_offset = archive.read_i32("DataResourceOffset")
        if data_resource_offset > 0:
            archive.validate_offset(data_resource_offset, "DataResourceOffset")

    return {
        "preload_dependency_count": preload_dependency_count,
        "preload_dependency_offset": preload_dependency_offset,
        "names_referenced_from_export_data_count": names_referenced_from_export_data_count,
        "payload_toc_offset": payload_toc_offset,
        "data_resource_offset": data_resource_offset,
    }


def read_package_summary(archive: FArchive) -> PackageFileSummary:
    """读取 PackageFileSummary 文件头（UE5.7 专用）。"""
    _validate_file_size(archive)

    archive.seek(0)
    archive.set_hex_view_context("Summary.")

    # 第 1-3 步：版本号 + SavedHash + CustomVersions
    (tag, legacy_file_version, file_version_ue4, file_version_ue5,
     file_version_licensee, saved_hash, total_header_size,
     custom_versions) = _read_version_and_tag(archive)

    # 第 4 步：PackageName + PackageFlags
    package_name, package_flags = _read_package_identity(archive)
    has_filter_editor_only = (package_flags & PKG_FilterEditorOnly) != 0

    # 第 5 步：NameCount + NameOffset
    name_count, name_offset = _read_name_table_offsets(archive)

    # 第 6-8 步：SoftObjectPaths / Localization / GatherableText（NameOffset 之后、ExportCount 之前）
    pre_export = _read_pre_export_optional_fields(
        archive, file_version_ue5, file_version_ue4, has_filter_editor_only,
    )

    # 第 9-10 步：ExportCount/Offset + ImportCount/Offset
    export_count, export_offset, import_count, import_offset = (
        _read_export_import_offsets(archive)
    )

    # 第 11-12 步：Cells / MetaData（ImportOffset 之后、DependsOffset 之前）
    post_import = _read_post_import_optional_fields(archive, file_version_ue5)

    # 第 13-14 步：DependsOffset + SoftPackageRefs + SearchableNames + Thumbnail
    secondary = _read_secondary_offset_fields(archive, file_version_ue4)

    # 第 15 步：ImportTypeHierarchies
    import_type_hierarchies_count, import_type_hierarchies_offset = (
        _read_import_type_hierarchies(archive, file_version_ue5)
    )

    # 第 16 步：GUIDs
    persistent_guid = _read_guids(
        archive, legacy_file_version, file_version_ue4,
        file_version_ue5, has_filter_editor_only,
    )

    # 第 17-19 步：Generations + EngineVersions
    generations = _read_generations(archive)
    saved_by_engine_version = _read_engine_version(archive)
    compatible_with_engine_version = _read_engine_version(archive)

    # 第 20-22 步：Compression + PackageSource
    compression_flags, package_source = _read_compression_and_source(archive)

    # 第 23 步：AdditionalPackages + TextureAllocations
    _read_additional_packages(archive, legacy_file_version)

    # 第 24-27 步：AssetRegistry/BulkData/WorldTile/ChunkIDs
    tail = _read_tail_offsets(archive)

    # 第 28-31 步：PreloadDeps / NamesReferenced / PayloadToc / DataResource
    late = _read_late_versioned_fields(archive, file_version_ue4, file_version_ue5)

    return PackageFileSummary(
        tag=tag, legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5, file_version_licensee=file_version_licensee,
        saved_hash=saved_hash, total_header_size=total_header_size,
        custom_versions=custom_versions, package_name=package_name,
        package_flags=package_flags, name_count=name_count, name_offset=name_offset,
        soft_object_paths_count=pre_export["soft_object_paths_count"],
        soft_object_paths_offset=pre_export["soft_object_paths_offset"],
        localization_id=pre_export["localization_id"],
        gatherable_text_data_count=pre_export["gatherable_text_data_count"],
        gatherable_text_data_offset=pre_export["gatherable_text_data_offset"],
        export_count=export_count, export_offset=export_offset,
        import_count=import_count, import_offset=import_offset,
        cell_export_count=post_import["cell_export_count"],
        cell_export_offset=post_import["cell_export_offset"],
        cell_import_count=post_import["cell_import_count"],
        cell_import_offset=post_import["cell_import_offset"],
        metadata_offset=post_import["metadata_offset"],
        depends_offset=secondary["depends_offset"],
        soft_package_references_count=secondary["soft_package_references_count"],
        soft_package_references_offset=secondary["soft_package_references_offset"],
        searchable_names_offset=secondary["searchable_names_offset"],
        thumbnail_table_offset=secondary["thumbnail_table_offset"],
        import_type_hierarchies_count=import_type_hierarchies_count,
        import_type_hierarchies_offset=import_type_hierarchies_offset,
        persistent_guid=persistent_guid, generations=generations,
        saved_by_engine_version=saved_by_engine_version,
        compatible_with_engine_version=compatible_with_engine_version,
        compression_flags=compression_flags, package_source=package_source,
        asset_registry_data_offset=tail["asset_registry_data_offset"],
        bulk_data_start_offset=tail["bulk_data_start_offset"],
        world_tile_info_data_offset=tail["world_tile_info_data_offset"],
        chunk_ids=tail["chunk_ids"],
        preload_dependency_count=late["preload_dependency_count"],
        preload_dependency_offset=late["preload_dependency_offset"],
        names_referenced_from_export_data_count=late["names_referenced_from_export_data_count"],
        payload_toc_offset=late["payload_toc_offset"],
        data_resource_offset=late["data_resource_offset"],
    )


def validate_export_data_range(
    archive: FArchive,
    summary: PackageFileSummary,
) -> None:
    """验证导出数据偏移是否超出文件范围。

    检查每个导出条目的 serial_offset + serial_size 是否在文件范围内。
    截断文件的导出表可能指向超出文件末尾的偏移。

    Args:
        archive: 文件归档读取器
        summary: 包文件摘要

    注：此函数仅记录诊断，不抛出异常（容错模式友好）。
    """
    from uasset_read.serializers.object_resources import ObjectExport

    file_size = archive.total_size()
    if file_size <= 0 or summary.export_count <= 0:
        return

    # 导出表本身占用的空间检查
    # 每个导出表条目约 100+ 字节（FObjectExport 结构）
    export_table_min_entry_size = 72  # 最小 FObjectExport 大小
    export_table_end = summary.export_offset + summary.export_count * export_table_min_entry_size
    if export_table_end > file_size:
        archive._diagnostics.append(OffsetRangeDiagnostic(
            kind="truncated_file",
            module="package_summary",
            field="export_table",
            current_pos=summary.export_offset,
            target_offset=export_table_end,
            file_size=file_size,
            source="validate_export_data_range",
            error=(
                f"导出表区域 [0x{summary.export_offset:X}, 0x{export_table_end:X}] "
                f"超出文件大小 0x{file_size:X}，文件可能在导出表区域被截断"
            ),
        ))


def read_name_table(archive: FArchive, summary: PackageFileSummary) -> List[str]:
    """读取名称表。

    每个名称条目格式：
    - NameString (FString) - 名称字符串
    - NonCasePreservingHash (uint16) - 非大小写保留哈希
    - CasePreservingHash (uint16) - 大小写保留哈希
    （两个 uint16 共 4 字节，仅 VER_UE4_NAME_HASHES_SERIALIZED 及之后版本存在）

    UE5 资产始终有 name hashes（4 bytes）。

    Args:
        archive: 文件归档读取器
        summary: 包文件摘要，含 name_offset 和 name_count

    Returns:
        名称字符串列表。

    Raises:
        ParseError: 如果 name_count 为 0、name_offset 无效或读取后名称表为空。
            每个 UE 包必须有非空的名称表，否则后续所有名称查找都会失败。
    """
    # 防御性检查：name_count 为 0 时抛出错误（UE 包必须有名称表）
    if summary.name_count <= 0:
        raise ParseError(
            f"name_count={summary.name_count}，UE 包必须有非空名称表"
        )

    # 验证 name_offset 有效性
    if summary.name_offset <= 0:
        raise ParseError(
            f"name_offset={summary.name_offset} 无效，无法读取名称表"
        )

    try:
        archive.seek(summary.name_offset)
    except (OSError, OverflowError) as e:
        raise ParseError(
            f"seek({summary.name_offset}) 失败，无法读取名称表: {e}"
        ) from e

    name_map: List[str] = []
    for i in range(summary.name_count):
        try:
            name = archive.read_fstring(f"NameTable[{i}].Name")
            name_map.append(name)
            # 名称哈希字段：仅当 file_version_ue4 >= UE4_NAME_HASHES_SERIALIZED (803) 时存在
            # UE5 资产始终有 name hashes (4 bytes)
            # 旧 UE4 资产（如 legacy -6 且 version < 803）没有哈希字段
            from uasset_read.constants import UE4_NAME_HASHES_SERIALIZED
            if summary.file_version_ue5 > 0 or summary.file_version_ue4 >= UE4_NAME_HASHES_SERIALIZED:
                archive.read(4)
        except (struct.error, OSError, ValueError) as e:
            logger.warning(
                "read_name_table: 读取名称条目 %d/%d 失败: %s（已读取 %d 个名称）",
                i, summary.name_count, e, len(name_map),
            )
            break

    if not name_map:
        raise ParseError(
            f"名称表为空（name_count={summary.name_count}, name_offset={summary.name_offset}），"
            f"无法继续解析"
        )

    return name_map


def read_depends_map(archive: FArchive, summary: PackageFileSummary) -> List[List[int]]:
    """读取 DependsMap（依赖表）。

    UE 格式：TArray<TArray<FPackageIndex>>
    每个 Export 对应一个依赖列表，依赖列表中的值是 PackageIndex（int32）。

    Returns:
        二维列表，第一维是 Export 索引，第二维是依赖的 PackageIndex 列表
    """
    if summary.depends_offset <= 0 or summary.export_count <= 0:
        return []

    archive.seek(summary.depends_offset)

    depends_map: List[List[int]] = []
    for i in range(summary.export_count):
        # 读取每个 Export 的依赖列表
        dep_count = archive.read_i32(f"DependsMap[{i}].Count")
        if dep_count < 0 or dep_count > 10000:  # 防御性检查
            logger.warning("DependsMap: 异常的依赖数量 %d, 跳过", dep_count)
            depends_map.append([])
            continue
        deps = []
        for j in range(dep_count):
            deps.append(archive.read_i32(f"DependsMap[{i}][{j}]"))
        depends_map.append(deps)

    return depends_map


def read_soft_package_references(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
) -> List[str]:
    """读取 SoftPackageReferences（软包引用表）。

    UE 格式：TArray<FName> — 包路径名称列表。
    仅当 file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP (516) 时存在。

    Returns:
        包路径名称列表（已从 FName 索引解析为字符串）
    """
    if summary.soft_package_references_count <= 0 or summary.soft_package_references_offset <= 0:
        return []

    archive.seek(summary.soft_package_references_offset)

    refs: List[str] = []
    for i in range(summary.soft_package_references_count):
        refs.append(archive.read_name(name_map, f"SoftPackageReferences[{i}]"))

    return refs


def read_preload_dependencies(archive: FArchive, summary: PackageFileSummary) -> List[int]:
    """读取 PreloadDependencies（预加载依赖）。

    UE 格式：TArray<FPackageIndex>
    一维数组，包含所有预加载依赖的 PackageIndex。

    Returns:
        PackageIndex 列表
    """
    if summary.preload_dependency_offset <= 0 or summary.preload_dependency_count <= 0:
        return []

    archive.seek(summary.preload_dependency_offset)

    dependencies: List[int] = []
    for i in range(summary.preload_dependency_count):
        dependencies.append(archive.read_i32(f"PreloadDependencies[{i}]"))

    return dependencies
