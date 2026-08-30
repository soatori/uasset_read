from __future__ import annotations

"""
Package Summary serialization — PackageFileSummary and related read functions.

Extracted from uasset_read.py (lines 901-2543).
UE5.7-only version — UE4 compatibility code removed.
"""

import logging
import struct
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from uasset_read.memory_safety import ResourceBudget
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from uasset_read.archive import FArchive
from uasset_read.constants import (
    PACKAGE_FILE_TAG,
    PACKAGE_FILE_TAG_SWAPPED,
    UE5_VERSION_MIN,
    UE4_LEGACY_VERSIONS,
    SUPPORTED_LEGACY_VERSIONS,
    MAX_NAME_COUNT,
    MAX_IMPORT_COUNT,
    MAX_EXPORT_COUNT,
    MAX_CUSTOM_VERSIONS,
    MAX_TOTAL_OBJECT_COUNT,
    MAX_GENERATIONS,
    MAX_COMPRESSED_CHUNKS,
    MAX_SOFT_PACKAGE_REFS,
    MAX_SAFE_COUNT,
    UE5_PACKAGE_SAVED_HASH,
    UE5_ADD_SOFTOBJECTPATH_LIST,
    UE5_VERSE_CELLS,
    UE5_METADATA_SERIALIZATION_OFFSET,
    UE5_IMPORT_TYPE_HIERARCHIES,
    UE5_NAMES_REFERENCED_FROM_EXPORT_DATA,
    UE5_PAYLOAD_TOC,
    UE5_DATA_RESOURCES,
    PKG_FilterEditorOnly,
    UE_NONE_SENTINEL,
    UE4_ADD_STRING_ASSET_REFERENCES_MAP,
    UE4_ADDED_SEARCHABLE_NAMES,
    UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID,
    UE4_SERIALIZE_TEXT_IN_PACKAGES,
    UE4_ADDED_PACKAGE_OWNER,
    UE4_NON_OUTER_PACKAGE_IMPORT,
    UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS,
)
from uasset_read.exceptions import VersionError, ParseError
from uasset_read.models.diagnostics import OffsetRangeDiagnostic
from uasset_read.constants import MIN_UASSET_SIZE

# Optional ResourceBudget (lazy import to avoid circular dependencies)
try:
    from uasset_read.memory_safety import ResourceBudget as _ResourceBudgetType
except ImportError:
    _ResourceBudgetType = None  # type: ignore[assignment,misc]


def read_validated_count_strict(
    count: int,
    max_value: int,
    stage: str,
    bytes_per_entry: int,
    budget: "ResourceBudget | None" = None,
) -> int:
    """Read and validate table count physical feasibility (strict: raises ParseError on excess).

    Args:
        count: Raw count read from archive
        max_value: Maximum allowed count for this table
        stage: Stage name (for exceptions and budget logs)
        bytes_per_entry: Bytes per record (for budget.reserve)
        budget: Optional resource budget tracker

    Returns:
        Validated count value

    Raises:
        ParseError: When count exceeds max_value
        MemoryLimitExceeded: When budget.reserve exceeds limit
    """
    if count < 0:
        raise ParseError(f"Negative {stage} count: {count}")
    if count > max_value:
        raise ParseError(f"{stage} count {count} exceeds maximum {max_value}")
    if budget is not None and count > 0:
        budget.reserve(count * bytes_per_entry, stage)
    return count


@dataclass
class GenerationInfo:
    """FGenerationInfo — version generation info."""

    export_count: int = 0
    name_count: int = 0


@dataclass
class EngineVersion:
    """FEngineVersion — engine version info."""

    major: int = 0
    minor: int = 0
    patch: int = 0
    changelist: int = 0
    branch: str = ""


@dataclass
class CustomVersion:
    """Custom version (GUID + version number)."""

    guid: str
    version: int


@dataclass
class PackageFileSummary:
    """PackageFileSummary file header."""

    tag: int
    legacy_file_version: int
    file_version_ue4: int = 0
    is_legacy: bool = False  # UE4 LegacyFileVersion (-3, -4, -5)
    file_version_ue5: int = 0
    file_version_licensee: int = 0
    saved_hash: bytes = field(default_factory=lambda: b"")
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


def _read_custom_versions(archive: FArchive) -> list:
    """Read CustomVersions table (Optimized format, UE5 / UE4 LegacyFileVersion < -5)."""
    custom_versions_count = archive.read_u32("CustomVersionsCount")
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError("Custom versions count exceeds maximum")
    custom_versions = []
    for _ in range(custom_versions_count):
        guid_bytes = archive.read(16)
        version = archive.read_i32()
        custom_versions.append(CustomVersion(guid=guid_bytes.hex(), version=version))
    return custom_versions


def _read_custom_versions_guids(archive: FArchive) -> list:
    """Read CustomVersions table (Guids format, UE4 LegacyFileVersion -3 to -5).

    Each record: FGuid (16 bytes) + int32 Version + FString FriendlyName
    Reference: UE CustomVersion.cpp FGuidCustomVersion_DEPRECATED
    """
    custom_versions_count = archive.read_u32("CustomVersionsCount")
    if custom_versions_count > MAX_CUSTOM_VERSIONS:
        raise ParseError("Custom versions count exceeds maximum")
    custom_versions = []
    for _ in range(custom_versions_count):
        guid_bytes = archive.read(16)
        version = archive.read_i32()
        # FriendlyName: FString (i32 length + chars), included in UE4 GUID format
        archive.read_fstring("FriendlyName")
        custom_versions.append(CustomVersion(guid=guid_bytes.hex(), version=version))
    return custom_versions


def _read_generations(archive: FArchive, budget: "_ResourceBudgetType | None" = None) -> list:
    """Read Generations table."""
    generations_count = archive.read_i32("GenerationsCount")
    read_validated_count_strict(generations_count, MAX_GENERATIONS, "generations", 8, budget)
    generations = []
    for _ in range(generations_count):
        gen_export_count = archive.read_i32()
        gen_name_count = archive.read_i32()
        generations.append(GenerationInfo(export_count=gen_export_count, name_count=gen_name_count))
    return generations


def _read_engine_version(archive: FArchive) -> "EngineVersion":
    """Read FEngineVersion structure."""
    return EngineVersion(
        major=archive.read_u16(),
        minor=archive.read_u16(),
        patch=archive.read_u16(),
        changelist=archive.read_u32(),
        branch=archive.read_fstring(),
    )


def _read_cell_counts(archive: FArchive) -> tuple:
    """Read Verse Cell count and offset (UE5.7+)."""
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
    """Read PayloadTocOffset and validate reasonableness."""
    payload_toc_offset = archive.read_i64("PayloadTocOffset")
    if payload_toc_offset < 0:
        logger.debug("PayloadTocOffset is negative: %d, setting to 0", payload_toc_offset)
        payload_toc_offset = 0
    elif payload_toc_offset > 0:
        file_size = archive.total_size()
        if file_size > 0 and payload_toc_offset > file_size * 10:
            logger.debug(
                "PayloadTocOffset %d clearly out of bounds (file size %d), setting to 0",
                payload_toc_offset,
                file_size,
            )
            payload_toc_offset = 0
        elif file_size > 0 and payload_toc_offset > file_size:
            logger.debug(
                "PayloadTocOffset %d exceeds file size %d, may be virtualized payload",
                payload_toc_offset,
                file_size,
            )
        else:
            archive.validate_offset(payload_toc_offset, "PayloadTocOffset")
    return payload_toc_offset


def _validate_file_size(archive: FArchive) -> None:
    """Truncated file detection: raise error when file is too small."""
    file_size = archive.total_size()
    if file_size < MIN_UASSET_SIZE:
        archive._diagnostics.append(
            OffsetRangeDiagnostic(
                kind="truncated_file",
                module="package_summary",
                field="file_size",
                file_size=file_size,
                source="read_package_summary",
                error=(
                    f"File size {file_size} bytes, smaller than minimum valid size {MIN_UASSET_SIZE} bytes, "
                    f"file may be truncated or corrupted"
                ),
            )
        )
        raise ParseError(
            f"File too small ({file_size} bytes), cannot parse as .uasset file. "
            f"Minimum valid size is {MIN_UASSET_SIZE} bytes, file may be truncated or corrupted"
        )


def _read_version_and_tag(archive: FArchive) -> tuple[int, int, int, int, bytes, int, list]:
    """Read magic number, version, SavedHash, CustomVersions.

    Returns (tag, legacy_file_version, file_version_ue4, file_version_ue5,
           saved_hash, total_header_size, custom_versions)。
    """
    # Magic number
    tag = archive.read_u32("Tag")
    if tag == PACKAGE_FILE_TAG_SWAPPED:
        archive.set_byte_swapping(True)
        tag = PACKAGE_FILE_TAG
    elif tag != PACKAGE_FILE_TAG:
        raise VersionError(f"Invalid package tag: {hex(tag)}")

    legacy_file_version = archive.read_i32("LegacyFileVersion")
    if legacy_file_version not in SUPPORTED_LEGACY_VERSIONS:
        supported_versions = ", ".join(str(v) for v in sorted(SUPPORTED_LEGACY_VERSIONS))
        raise VersionError(
            f"Unsupported legacy_file_version {legacy_file_version}. Supported versions: {supported_versions}"
        )

    is_ue4_legacy = legacy_file_version in UE4_LEGACY_VERSIONS

    # LegacyUE3Version: exists because legacy_file_version != -4
    if legacy_file_version != -4:
        _legacy_ue3_version = archive.read_i32("LegacyUE3Version")  # noqa: F841 - protocol read
    file_version_ue4 = archive.read_i32("FileVersionUE4")

    # FileVersionUE5: only present when legacy_file_version <= -8
    if legacy_file_version <= -8:
        file_version_ue5 = archive.read_i32("FileVersionUE5")
    else:
        file_version_ue5 = 0

    if legacy_file_version <= -8 and file_version_ue5 < UE5_VERSION_MIN:
        raise VersionError(f"Unsupported UE5 version: {file_version_ue5}")

    file_version_licensee = archive.read_i32("FileVersionLicensee")

    # SavedHash + TotalHeaderSize BEFORE CustomVersions (UE5 >= PACKAGE_SAVED_HASH)
    # Older versions: no SavedHash, TotalHeaderSize comes AFTER CustomVersions
    if file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        saved_hash = archive.read(20)
        total_header_size = archive.read_i32("TotalHeaderSize")
        custom_versions = _read_custom_versions(archive)
    else:
        saved_hash = b""
        # UE4 LegacyFileVersion -3 to -5 uses Guids format (with FriendlyName)
        # UE5 LegacyFileVersion -6 to -8 uses Optimized format
        if is_ue4_legacy:
            custom_versions = _read_custom_versions_guids(archive)
        else:
            custom_versions = _read_custom_versions(archive)
        total_header_size = archive.read_i32("TotalHeaderSize")

    return (
        tag,
        legacy_file_version,
        file_version_ue4,
        file_version_ue5,
        file_version_licensee,
        saved_hash,
        total_header_size,
        custom_versions,
    )


def _read_package_identity(archive: FArchive) -> tuple[str, int]:
    """Read PackageName and PackageFlags."""
    package_name = archive.read_fstring("PackageName")
    if package_name == UE_NONE_SENTINEL:
        package_name = ""
    package_flags = archive.read_u32("PackageFlags")
    return package_name, package_flags


def _read_name_table_offsets(archive: FArchive) -> tuple[int, int]:
    """Read NameCount and NameOffset."""
    name_count = archive.read_i32("NameCount")
    if name_count < 0:
        raise ParseError(f"Negative name count: {name_count}")
    if name_count > MAX_NAME_COUNT:
        raise ParseError("Name count exceeds maximum")
    name_offset = archive.read_i32("NameOffset")
    archive.validate_offset(name_offset, "NameOffset")
    return name_count, name_offset


def _read_export_import_offsets(archive: FArchive) -> tuple[int, int, int, int]:
    """Read Export/Import table count and offset."""
    export_count = archive.read_i32("ExportCount")
    if export_count < 0:
        raise ParseError(f"Negative export count: {export_count}")
    if export_count > MAX_EXPORT_COUNT:
        raise ParseError("Export count exceeds maximum")
    export_offset = archive.read_i32("ExportOffset")
    archive.validate_offset(export_offset, "ExportOffset")

    import_count = archive.read_i32("ImportCount")
    if import_count < 0:
        raise ParseError(f"Negative import count: {import_count}")
    if import_count > MAX_IMPORT_COUNT:
        raise ParseError("Import count exceeds maximum")
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
    """Read version-gated fields between NameOffset and ExportCount."""
    # SoftObjectPaths（UE5 >= 1011）
    soft_object_paths_count = 0
    soft_object_paths_offset = 0
    if file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST:
        soft_object_paths_count = archive.read_i32("SoftObjectPathsCount")
        soft_object_paths_offset = archive.read_i32("SoftObjectPathsOffset")
        if soft_object_paths_offset > 0:
            archive.validate_offset(soft_object_paths_offset, "SoftObjectPathsOffset")

    # LocalizationId (non FilterEditorOnly, UE4 >= 516)
    localization_id = ""
    if not has_filter_editor_only and file_version_ue4 >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
        localization_id = archive.read_fstring("LocalizationId")

    # GatherableTextData（UE4 >= 513）
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
    """Read version-gated fields between ImportOffset and DependsOffset."""
    # CellExport/CellImport (UE5 >= cell version)
    cell_export_count = 0
    cell_export_offset = 0
    cell_import_count = 0
    cell_import_offset = 0
    if file_version_ue5 >= UE5_VERSE_CELLS:
        cell_export_count, cell_export_offset, cell_import_count, cell_import_offset = _read_cell_counts(archive)

    # MetaDataOffset (UE5 >= meta version)
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
    budget: "_ResourceBudgetType | None" = None,
) -> dict:
    """Read DependsOffset, SoftPackageReferences, SearchableNames, ThumbnailTable."""
    depends_offset = archive.read_i32("DependsOffset")

    soft_package_references_count = 0
    soft_package_references_offset = 0
    if file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP:
        soft_package_references_count = archive.read_i32("SoftPackageReferencesCount")
        read_validated_count_strict(
            soft_package_references_count,
            MAX_SOFT_PACKAGE_REFS,
            "soft_package_references",
            4,
            budget,
        )
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
    """Read ImportTypeHierarchies (UE5 >= 1015)."""
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
    """Read LegacyGuid / PersistentGuid / OwnerPersistentGuid."""
    # LegacyGuid (exists when UE5 < 1016)
    if file_version_ue5 < UE5_PACKAGE_SAVED_HASH:
        archive.read(16)

    # PersistentGuid (UE source: PackageFileSummary.cpp:357)
    # Only read from file when FileVersionUE >= VER_UE4_ADDED_PACKAGE_OWNER (518)
    # Older versions derive via SavedHash, no need to read from file
    persistent_guid = ""
    if not has_filter_editor_only and file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER:
        guid_bytes = archive.read(16)
        persistent_guid = guid_bytes.hex()

    # OwnerPersistentGuid (only UE4 519 exact value)
    if (
        not has_filter_editor_only
        and file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER
        and file_version_ue4 < UE4_NON_OUTER_PACKAGE_IMPORT
    ):
        archive.read(16)

    return persistent_guid


def _read_compression_and_source(
    archive: FArchive,
    budget: "_ResourceBudgetType | None" = None,
) -> tuple[int, int]:
    """Read CompressionFlags, CompressedChunks, PackageSource."""
    compression_flags = archive.read_u32("CompressionFlags")

    compressed_chunks_count = archive.read_i32("CompressedChunksCount")
    read_validated_count_strict(
        compressed_chunks_count,
        MAX_COMPRESSED_CHUNKS,
        "compressed_chunks",
        12,
        budget,
    )
    for _ in range(compressed_chunks_count):
        archive.read(12)

    package_source = archive.read_u32("PackageSource")
    return compression_flags, package_source


def _read_additional_packages(archive: FArchive, legacy_file_version: int) -> None:
    """Read AdditionalPackagesToCook and NumTextureAllocations (legacy -6)."""
    additional_packages_count = archive.read_i32("AdditionalPackagesCount")
    if additional_packages_count < 0:
        raise ParseError(f"Negative additional packages count: {additional_packages_count}")
    for _ in range(additional_packages_count):
        archive.read_fstring()

    if legacy_file_version > -7:
        archive.read_i32("NumTextureAllocations")


def _read_tail_offsets(archive: FArchive) -> dict:
    """Read AssetRegistry, BulkData, WorldTile, ChunkIDs."""
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
    """Read PreloadDependencies, NamesReferenced, PayloadToc, DataResource."""
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


def read_package_summary(
    archive: FArchive,
    budget: "_ResourceBudgetType | None" = None,
) -> PackageFileSummary:
    """Read PackageFileSummary header (UE5.7-only)."""
    _validate_file_size(archive)

    archive.seek(0)
    archive.set_hex_view_context("Summary.")

    # Step 1-3: Version + SavedHash + CustomVersions
    (
        tag,
        legacy_file_version,
        file_version_ue4,
        file_version_ue5,
        file_version_licensee,
        saved_hash,
        total_header_size,
        custom_versions,
    ) = _read_version_and_tag(archive)

    # Step 4: PackageName + PackageFlags
    package_name, package_flags = _read_package_identity(archive)
    has_filter_editor_only = (package_flags & PKG_FilterEditorOnly) != 0

    # Step 5: NameCount + NameOffset
    name_count, name_offset = _read_name_table_offsets(archive)

    # Step 6-8: SoftObjectPaths / Localization / GatherableText (between NameOffset and ExportCount)
    pre_export = _read_pre_export_optional_fields(
        archive,
        file_version_ue5,
        file_version_ue4,
        has_filter_editor_only,
    )

    # Step 9-10: ExportCount/Offset + ImportCount/Offset
    export_count, export_offset, import_count, import_offset = _read_export_import_offsets(archive)

    # Step 11-12: Cells / MetaData (between ImportOffset and DependsOffset)
    post_import = _read_post_import_optional_fields(archive, file_version_ue5)

    # Step 13-14: DependsOffset + SoftPackageRefs + SearchableNames + Thumbnail
    secondary = _read_secondary_offset_fields(archive, file_version_ue4, budget)

    # Step 15: ImportTypeHierarchies
    import_type_hierarchies_count, import_type_hierarchies_offset = _read_import_type_hierarchies(
        archive, file_version_ue5
    )

    # Step 16: GUIDs
    persistent_guid = _read_guids(
        archive,
        legacy_file_version,
        file_version_ue4,
        file_version_ue5,
        has_filter_editor_only,
    )

    # Step 17-19: Generations + EngineVersions
    generations = _read_generations(archive, budget)
    saved_by_engine_version = _read_engine_version(archive)
    compatible_with_engine_version = _read_engine_version(archive)

    # Step 20-22: Compression + PackageSource
    compression_flags, package_source = _read_compression_and_source(archive, budget)

    # Step 23: AdditionalPackages + TextureAllocations
    _read_additional_packages(archive, legacy_file_version)

    # Step 24-27: AssetRegistry/BulkData/WorldTile/ChunkIDs
    tail = _read_tail_offsets(archive)

    # Step 28-31: PreloadDeps / NamesReferenced / PayloadToc / DataResource
    late = _read_late_versioned_fields(archive, file_version_ue4, file_version_ue5)

    return PackageFileSummary(
        tag=tag,
        legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
        file_version_licensee=file_version_licensee,
        is_legacy=legacy_file_version in UE4_LEGACY_VERSIONS,
        saved_hash=saved_hash,
        total_header_size=total_header_size,
        custom_versions=custom_versions,
        package_name=package_name,
        package_flags=package_flags,
        name_count=name_count,
        name_offset=name_offset,
        soft_object_paths_count=pre_export["soft_object_paths_count"],
        soft_object_paths_offset=pre_export["soft_object_paths_offset"],
        localization_id=pre_export["localization_id"],
        gatherable_text_data_count=pre_export["gatherable_text_data_count"],
        gatherable_text_data_offset=pre_export["gatherable_text_data_offset"],
        export_count=export_count,
        export_offset=export_offset,
        import_count=import_count,
        import_offset=import_offset,
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
        persistent_guid=persistent_guid,
        generations=generations,
        saved_by_engine_version=saved_by_engine_version,
        compatible_with_engine_version=compatible_with_engine_version,
        compression_flags=compression_flags,
        package_source=package_source,
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
    """Validate export data offsets against file bounds.

    Checks whether each export entry's serial_offset + serial_size is within file range.
    Truncated files may have export table entries pointing past end of file.

    Args:
        archive: File archive reader
        summary: Package file summary

    Note: This function only logs diagnostics, does not raise exceptions (fault-tolerant).
    """

    file_size = archive.total_size()
    if file_size <= 0 or summary.export_count <= 0:
        return

    # Export table space check
    # Each export table entry ~100+ bytes (FObjectExport structure)
    export_table_min_entry_size = 72  # Minimum FObjectExport size
    export_table_end = summary.export_offset + summary.export_count * export_table_min_entry_size
    if export_table_end > file_size:
        archive._diagnostics.append(
            OffsetRangeDiagnostic(
                kind="truncated_file",
                module="package_summary",
                field="export_table",
                current_pos=summary.export_offset,
                target_offset=export_table_end,
                file_size=file_size,
                source="validate_export_data_range",
                error=(
                    f"Export table region [0x{summary.export_offset:X}, 0x{export_table_end:X}] "
                    f"exceeds file size 0x{file_size:X}, file may be truncated in export table region"
                ),
            )
        )


def read_name_table(archive: FArchive, summary: PackageFileSummary) -> List[str]:
    """Read name table.

    Each name entry format:
    - NameString (FString) - name string
    - NonCasePreservingHash (uint16) - non-case-preserving hash
    - CasePreservingHash (uint16) - case-preserving hash
    (two uint16s = 4 bytes total, only present in VER_UE4_NAME_HASHES_SERIALIZED and later)

    UE5 assets always have name hashes (4 bytes).

    Args:
        archive: File archive reader
        summary: Package file summary with name_offset and name_count

    Returns:
        List of name strings.

    Raises:
        ParseError: If name_count is 0, name_offset is invalid, or name table is empty after reading.
            Every UE package must have a non-empty name table, otherwise all subsequent name lookups will fail.
    """
    # Defensive check: raise error when name_count is 0 (UE package must have name table)
    if summary.name_count <= 0:
        raise ParseError(f"name_count={summary.name_count}, UE package must have non-empty name table")

    # Validate name_offset
    if summary.name_offset <= 0:
        raise ParseError(f"name_offset={summary.name_offset} invalid, cannot read name table")

    try:
        archive.seek(summary.name_offset)
    except (OSError, OverflowError) as e:
        raise ParseError(f"seek({summary.name_offset}) failed, cannot read name table: {e}") from e

    name_map: List[str] = []
    for i in range(summary.name_count):
        try:
            name = archive.read_fstring(f"NameTable[{i}].Name")
            name_map.append(name)
            # Name hash fields: only present when file_version_ue4 >= UE4_NAME_HASHES_SERIALIZED (803)
            # UE5 assets always have name hashes (4 bytes)
            # Old UE4 assets (e.g. legacy -6 with version < 803) don't have hash fields
            from uasset_read.constants import UE4_NAME_HASHES_SERIALIZED

            if summary.file_version_ue5 > 0 or summary.file_version_ue4 >= UE4_NAME_HASHES_SERIALIZED:
                archive.read(4)
        except (struct.error, OSError, ValueError) as e:
            logger.debug(
                "read_name_table: failed to read name entry %d/%d: %s (read %d names so far)",
                i,
                summary.name_count,
                e,
                len(name_map),
            )
            break

    if not name_map:
        raise ParseError(
            f"Name table is empty (name_count={summary.name_count}, name_offset={summary.name_offset}), "
            f"cannot continue parsing"
        )

    return name_map


def read_depends_map(
    archive: FArchive,
    summary: PackageFileSummary,
    budget: "_ResourceBudgetType | None" = None,
    warnings: "List[str] | None" = None,
) -> List[List[int]]:
    """Read DependsMap (dependency table).

    UE format: TArray<TArray<FPackageIndex>>
    Each export has a dependency list, values are PackageIndex (int32).

    PackageIndex encoding (UE FPackageIndex, ObjectResource.h):
        0       -> null (no reference)
        > 0     -> Export reference (1-based: PackageIndex 1 = export 0)
        < 0     -> Import reference (negated 0-based: PackageIndex -1 = import 0)

    Args:
        archive: File archive reader
        summary: Package file summary
        budget: Optional resource budget tracker
        warnings: Optional warnings list for collecting degradation info (e.g. invalid entries)

    Returns:
        2D list: first dimension is export index, second dimension is dependency PackageIndex list
    """
    if summary.depends_offset <= 0 or summary.export_count <= 0:
        return []

    archive.seek(summary.depends_offset)

    depends_map: List[List[int]] = []
    skipped_entries = 0
    invalid_indices = 0

    for i in range(summary.export_count):
        # Read dependency list for each export
        dep_count = archive.read_i32(f"DependsMap[{i}].Count")
        # Fault-tolerant: skip invalid entries (preserve empty list) instead of aborting entire table parse
        if dep_count < 0 or dep_count > MAX_SAFE_COUNT:
            logger.debug("DependsMap: abnormal dependency count %d at export %d, skipping", dep_count, i)
            depends_map.append([])
            skipped_entries += 1
            continue
        if budget is not None and dep_count > 0:
            budget.reserve(dep_count * 4, f"DependsMap[{i}]")
        deps = []
        for j in range(dep_count):
            pkg_index = archive.read_i32(f"DependsMap[{i}][{j}]")
            # Validate PackageIndex range (UE FPackageIndex: >0 export, <0 import):
            #   0 → null (valid)
            #   > 0 → export reference (1-based), valid if pkg_index <= export_count
            #   < 0 → import reference (negated 0-based), valid if |pkg_index| <= import_count
            if pkg_index > 0 and pkg_index > summary.export_count:
                invalid_indices += 1
                logger.debug(
                    "DependsMap: out-of-range export index %d at export %d dep %d (export_count=%d)",
                    pkg_index,
                    i,
                    j,
                    summary.export_count,
                )
            elif pkg_index < 0 and abs(pkg_index) > summary.import_count:
                invalid_indices += 1
                logger.debug(
                    "DependsMap: out-of-range import index %d at export %d dep %d (import_count=%d)",
                    pkg_index,
                    i,
                    j,
                    summary.import_count,
                )
            deps.append(pkg_index)
        depends_map.append(deps)

    # Surface degradation as warnings
    if warnings is not None:
        if skipped_entries > 0:
            warnings.append(
                f"DependsMap: {skipped_entries}/{summary.export_count} entries skipped due to invalid dependency count"
            )
        if invalid_indices > 0:
            warnings.append(
                f"DependsMap: {invalid_indices} PackageIndex value(s) reference non-existent imports/exports"
            )

    return depends_map


def read_soft_package_references(
    archive: FArchive,
    summary: PackageFileSummary,
    name_map: List[str],
) -> List[str]:
    """Read SoftPackageReferences (soft package reference table).

    UE format: TArray<FName> — package path name list.
    Only present when file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP (516).

    Returns:
        Package path name list (resolved from FName index to strings)
    """
    if summary.soft_package_references_count <= 0 or summary.soft_package_references_offset <= 0:
        return []

    archive.seek(summary.soft_package_references_offset)

    refs: List[str] = []
    for i in range(summary.soft_package_references_count):
        refs.append(archive.read_name(name_map, f"SoftPackageReferences[{i}]"))

    return refs


def read_preload_dependencies(archive: FArchive, summary: PackageFileSummary) -> List[int]:
    """Read PreloadDependencies (preload dependencies).

    UE format: TArray<FPackageIndex>
    1D array containing all preload dependency PackageIndex values.

    Returns:
        List of PackageIndex
    """
    if summary.preload_dependency_offset <= 0 or summary.preload_dependency_count <= 0:
        return []

    archive.seek(summary.preload_dependency_offset)

    dependencies: List[int] = []
    for i in range(summary.preload_dependency_count):
        dependencies.append(archive.read_i32(f"PreloadDependencies[{i}]"))

    return dependencies
