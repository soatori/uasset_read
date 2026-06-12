"""
Package Summary 序列化 — PackageFileSummary 及相关读取函数。

从 uasset_read.py 提取（第 901-2543 行）。
UE5.7 专用版本 — 已移除 UE4 兼容代码。
"""

import logging
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
    UE4_NAME_HASHES_SERIALIZED,
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


def read_package_summary(archive: FArchive) -> PackageFileSummary:
    """读取 PackageFileSummary 文件头（UE5.7 专用）。"""
    # 截断文件检测：文件过小时直接报错
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

    archive.seek(0)

    # 第 1 步：魔数和版本号
    tag = archive.read_u32()
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    elif tag != PACKAGE_FILE_TAG:
        raise VersionError(f"Invalid package tag: {hex(tag)}")

    legacy_file_version = archive.read_i32()
    if legacy_file_version not in UE5_LEGACY_VERSIONS:
        supported_versions = ", ".join(str(v) for v in sorted(UE5_LEGACY_VERSIONS))
        # 根据 legacy_file_version 提供更精确的错误提示
        if legacy_file_version > -6:
            raise VersionError(
                f"Legacy file version {legacy_file_version} indicates UE4 asset. "
                f"Current version supports UE5 only (legacy versions -6 to -9)."
            )
        raise VersionError(
            f"Only UE5 files with legacy_file_version in {{{supported_versions}}} are supported, "
            f"got {legacy_file_version}"
        )

    legacy_ue3_version = archive.read_i32()
    file_version_ue4 = archive.read_i32()  # kept for internal reference only

    # FileVersionUE5: only present when legacy_file_version <= -8
    # legacy -6/-7 files do NOT have this field (CUE4Parse reference: legacyFileVersion <= -8)
    if legacy_file_version <= -8:
        file_version_ue5 = archive.read_i32()
    else:
        file_version_ue5 = 0  # not present in file

    # UE5 version check: skip for legacy -6/-7 (no FileVersionUE5 field)
    if legacy_file_version <= -8 and file_version_ue5 < UE5_VERSION_MIN:
        raise VersionError(f"Unsupported UE5 version: {file_version_ue5}")

    file_version_licensee = archive.read_i32()

    # SavedHash + TotalHeaderSize BEFORE CustomVersions (UE5 >= 1016 only)
    # For legacy -6/-7, file_version_ue5=0 < 1016, so these are NOT read here
    if file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        saved_hash = archive.read(20)
        total_header_size = archive.read_i32()
    else:
        saved_hash = b""
        total_header_size = 0  # will be read AFTER CustomVersions below

    # 第 3 步：CustomVersions
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

    # 第 6 步：SoftObjectPaths
    soft_object_paths_count = 0
    soft_object_paths_offset = 0
    if file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST:
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
    if export_count + import_count > MAX_TOTAL_OBJECT_COUNT:
        raise ParseError(
            f"Total object count ({export_count} + {import_count} = "
            f"{export_count + import_count}) exceeds maximum {MAX_TOTAL_OBJECT_COUNT}"
        )
    import_offset = archive.read_i32()
    archive.validate_offset(import_offset, "ImportOffset")

    # 第 11 步：CellExport/CellImport
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

    # 第 12 步：MetaDataOffset
    metadata_offset = 0
    if file_version_ue5 >= UE5_METADATA_SERIALIZATION_OFFSET:
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
    # For legacy -6, the Guid field is at a different position. Skip for -6 only.
    persistent_guid = ""
    if not has_filter_editor_only and file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER:
        if legacy_file_version != -6:
            guid_bytes = archive.read(16)
            persistent_guid = guid_bytes.hex()
        # else: legacy -6: Guid is at a different position, skip here

    # 第 16b 步：OwnerPersistentGuid
    # For legacy -7, both PersistentGuid and OwnerPersistentGuid are present
    # (same as legacy -8 format, just without FileVersionUE5)
    if (
        not has_filter_editor_only
        and (
            file_version_ue4 == UE4_ADDED_PACKAGE_OWNER
            or legacy_file_version in (-8, -7)
        )
    ):
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

    # 第 18 步：SavedByEngineVersion（UE5 始终为 FEngineVersion 结构）
    saved_by_engine_version = EngineVersion(
        major=archive.read_u16(), minor=archive.read_u16(), patch=archive.read_u16(),
        changelist=archive.read_u32(), branch=archive.read_fstring()
    )

    # 第 19 步：CompatibleWithEngineVersion（UE5 始终存在）
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

    # 第 28 步：PreloadDependencies
    preload_dependency_count = archive.read_i32()
    preload_dependency_offset = archive.read_i32()
    if preload_dependency_offset > 0:
        archive.validate_offset(preload_dependency_offset, "PreloadDependencyOffset")

    # 第 29 步：NamesReferencedFromExportData（UE5.7 始终存在）
    names_referenced_from_export_data_count = archive.read_i32()

    # 第 30 步：PayloadTocOffset（UE5.7 始终存在，但值可能无效）
    payload_toc_offset = archive.read_i64()

    # Tolerant: 检查 payload_toc_offset 是否合理
    if payload_toc_offset < 0:
        logger.warning(
            "PayloadTocOffset 为负数: %d, 设为 0",
            payload_toc_offset,
        )
        payload_toc_offset = 0
    elif payload_toc_offset > 0:
        file_size = archive.total_size()
        # 超过文件大小 10 倍说明值明显无效
        if file_size > 0 and payload_toc_offset > file_size * 10:
            logger.warning(
                "PayloadTocOffset %d 明显越界（文件大小 %d），设为 0",
                payload_toc_offset, file_size,
            )
            payload_toc_offset = 0
        elif file_size > 0 and payload_toc_offset > file_size:
            # 在文件大小之外但不极端，可能是 virtualized payload
            logger.debug(
                "PayloadTocOffset %d 超过文件大小 %d，可能是 virtualized payload",
                payload_toc_offset, file_size,
            )
            # 不 validate，留给后续逻辑处理
        else:
            archive.validate_offset(payload_toc_offset, "PayloadTocOffset")

    # 第 31 步：DataResourceOffset
    data_resource_offset = 0
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
    except Exception as e:
        raise ParseError(
            f"seek({summary.name_offset}) 失败，无法读取名称表: {e}"
        ) from e

    name_map: List[str] = []
    for i in range(summary.name_count):
        try:
            name = archive.read_fstring()
            name_map.append(name)
            # 名称哈希字段：仅当 file_version_ue4 >= UE4_NAME_HASHES_SERIALIZED (803) 时存在
            # UE5 资产始终有 name hashes (4 bytes)
            # 旧 UE4 资产（如 legacy -6 且 version < 803）没有哈希字段
            from uasset_read.constants import UE4_NAME_HASHES_SERIALIZED
            if summary.file_version_ue5 > 0 or summary.file_version_ue4 >= UE4_NAME_HASHES_SERIALIZED:
                archive.read(4)
        except Exception as e:
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
    for _ in range(summary.export_count):
        # 读取每个 Export 的依赖列表
        dep_count = archive.read_i32()
        if dep_count < 0 or dep_count > 10000:  # 防御性检查
            logger.warning("DependsMap: 异常的依赖数量 %d, 跳过", dep_count)
            depends_map.append([])
            continue
        deps = []
        for _ in range(dep_count):
            deps.append(archive.read_i32())
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
    for _ in range(summary.soft_package_references_count):
        refs.append(archive.read_name(name_map))

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
    for _ in range(summary.preload_dependency_count):
        dependencies.append(archive.read_i32())

    return dependencies
