"""Pinned raw reader for the ``uasset-reader-js`` JSON profile."""

import json
from typing import Any

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError


PACKAGE_FILE_TAG = 0x9E2A83C1
SUPPORTED_LEGACY_VERSIONS = frozenset({-6, -7, -8, -9})
UE4_OLDEST_LOADABLE_PACKAGE = 214
UE4_WORLD_LEVEL_INFO = 224
UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS = 326
UE4_ADDED_CHUNKID_TO_ASSETDATA_AND_UPACKAGE = 278
UE4_ENGINE_VERSION_OBJECT = 336
UE4_ADD_STRING_ASSET_REFERENCES_MAP = 384
UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION = 444
UE4_SERIALIZE_TEXT_IN_PACKAGES = 459
UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 507
UE4_ADDED_SEARCHABLE_NAMES = 510
UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 516
UE4_ADDED_PACKAGE_OWNER = 518
UE4_NON_OUTER_PACKAGE_IMPORT = 520
UE5_NAMES_REFERENCED_FROM_EXPORT_DATA = 1001
UE5_PAYLOAD_TOC = 1002
UE5_ADD_SOFTOBJECTPATH_LIST = 1008
UE5_DATA_RESOURCES = 1009
UE5_METADATA_SERIALIZATION_OFFSET = 1014
UE5_PACKAGE_SAVED_HASH = 1016
UE5_IMPORT_TYPE_HIERARCHIES = 1018


def _guid_slot_to_js(raw: bytes) -> str:
    """Render four little-endian uint32 GUID slots like uasset-reader-js."""
    if len(raw) != 16:
        raise ValueError("GUID slot must contain exactly 16 bytes")
    return "".join(raw[index:index + 4][::-1].hex() for index in range(0, 16, 4)).upper()


def _bigint_json_string(value: int) -> str:
    """Render a JavaScript BigInt using the pinned JSON string convention."""
    return f"{value}n"


def _unsupported(field: str, value: int) -> ParseError:
    return ParseError(f"Unsupported {field}: {value}")


def _read_count(archive: FArchive, field: str) -> int:
    count = archive.read_i32(field)
    if count < 0:
        raise ParseError(f"Invalid {field}: {count}")
    return count


def _read_engine_version(archive: FArchive, field: str) -> str:
    major = archive.read_u16(f"{field}.Major")
    minor = archive.read_u16(f"{field}.Minor")
    patch = archive.read_u16(f"{field}.Patch")
    changelist = archive.read_u32(f"{field}.Changelist")
    branch = archive.read_fstring(f"{field}.Branch")
    return f"{major}.{minor}.{patch}-{changelist}+{branch}"


def _read_header(archive: FArchive) -> dict[str, Any]:
    header: dict[str, Any] = {}
    header["EPackageFileTag"] = archive.read_u32("EPackageFileTag")
    if header["EPackageFileTag"] != PACKAGE_FILE_TAG:
        raise ParseError(f"Invalid EPackageFileTag: {header['EPackageFileTag']}")

    legacy_version = archive.read_i32("LegacyFileVersion")
    header["LegacyFileVersion"] = legacy_version
    if legacy_version not in SUPPORTED_LEGACY_VERSIONS:
        raise _unsupported("LegacyFileVersion", legacy_version)

    header["LegacyUE3Version"] = archive.read_i32("LegacyUE3Version")
    file_version_ue4 = archive.read_i32("FileVersionUE4")
    header["FileVersionUE4"] = file_version_ue4

    file_version_ue5 = 0
    if legacy_version <= -8:
        file_version_ue5 = archive.read_i32("FileVersionUE5")
        header["FileVersionUE5"] = file_version_ue5

    licensee_version = archive.read_i32("FileVersionLicenseeUE4")
    header["FileVersionLicenseeUE4"] = licensee_version
    if file_version_ue4 == 0 and file_version_ue5 == 0 and licensee_version == 0:
        raise _unsupported("VersionProfile", 0)
    if file_version_ue5 >= UE5_IMPORT_TYPE_HIERARCHIES:
        raise _unsupported("FileVersionUE5", file_version_ue5)

    if file_version_ue5 >= UE5_PACKAGE_SAVED_HASH:
        header["SavedPackageHash"] = archive.read(20).hex()
        header["TotalHeaderSize"] = archive.read_i32("TotalHeaderSize")

    custom_version_count = _read_count(archive, "CustomVersions.Count")
    header["CustomVersions"] = [
        {
            "key": _guid_slot_to_js(archive.read(16)),
            "version": archive.read_i32(f"CustomVersions[{index}].Version"),
        }
        for index in range(custom_version_count)
    ]

    if file_version_ue5 < UE5_PACKAGE_SAVED_HASH:
        header["TotalHeaderSize"] = archive.read_i32("TotalHeaderSize")

    header["FolderName"] = archive.read_fstring("FolderName")
    header["PackageFlags"] = archive.read_u32("PackageFlags")
    header["NameCount"] = _read_count(archive, "NameCount")
    header["NameOffset"] = archive.read_i32("NameOffset")

    if file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST:
        header["SoftObjectPathsCount"] = archive.read_u32("SoftObjectPathsCount")
        header["SoftObjectPathsOffset"] = archive.read_u32("SoftObjectPathsOffset")

    if file_version_ue4 >= UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID:
        header["LocalizationId"] = archive.read_fstring("LocalizationId")

    if file_version_ue4 >= UE4_SERIALIZE_TEXT_IN_PACKAGES:
        header["GatherableTextDataCount"] = _read_count(
            archive, "GatherableTextDataCount"
        )
        header["GatherableTextDataOffset"] = archive.read_i32(
            "GatherableTextDataOffset"
        )

    header["ExportCount"] = _read_count(archive, "ExportCount")
    header["ExportOffset"] = archive.read_i32("ExportOffset")
    header["ImportCount"] = _read_count(archive, "ImportCount")
    header["ImportOffset"] = archive.read_i32("ImportOffset")

    # This deliberately mirrors the pinned JS sequence and does not consume
    # the canonical UE5 verse-cell fields.
    if file_version_ue5 >= UE5_METADATA_SERIALIZATION_OFFSET:
        header["MetadataOffset"] = archive.read_i32("MetadataOffset")

    header["DependsOffset"] = archive.read_i32("DependsOffset")
    if file_version_ue4 < UE4_OLDEST_LOADABLE_PACKAGE:
        raise _unsupported("FileVersionUE4", file_version_ue4)

    if file_version_ue4 >= UE4_ADD_STRING_ASSET_REFERENCES_MAP:
        header["SoftPackageReferencesCount"] = archive.read_i32(
            "SoftPackageReferencesCount"
        )
        header["SoftPackageReferencesOffset"] = archive.read_i32(
            "SoftPackageReferencesOffset"
        )

    if file_version_ue4 >= UE4_ADDED_SEARCHABLE_NAMES:
        header["SearchableNamesOffset"] = archive.read_i32("SearchableNamesOffset")

    header["ThumbnailTableOffset"] = archive.read_i32("ThumbnailTableOffset")
    header["Guid"] = archive.read(16).hex().upper()

    if file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER:
        header["PersistentGuid"] = archive.read(16).hex().upper()
    if (
        file_version_ue4 >= UE4_ADDED_PACKAGE_OWNER
        and file_version_ue4 < UE4_NON_OUTER_PACKAGE_IMPORT
    ):
        header["OwnerPersistentGuid"] = archive.read(16).hex().upper()

    generation_count = _read_count(archive, "Generations.Count")
    header["Generations"] = [
        {
            "exportCount": archive.read_i32(f"Generations[{index}].ExportCount"),
            "nameCount": archive.read_i32(f"Generations[{index}].NameCount"),
        }
        for index in range(generation_count)
    ]

    if file_version_ue4 >= UE4_ENGINE_VERSION_OBJECT:
        header["SavedByEngineVersion"] = _read_engine_version(
            archive, "SavedByEngineVersion"
        )
    else:
        header["EngineChangelist"] = archive.read_i32("EngineChangelist")

    if file_version_ue4 >= UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION:
        header["CompatibleWithEngineVersion"] = _read_engine_version(
            archive, "CompatibleWithEngineVersion"
        )
    else:
        header["CompatibleWithEngineVersion"] = header["SavedByEngineVersion"]

    header["CompressionFlags"] = archive.read_u32("CompressionFlags")
    compressed_chunk_count = _read_count(archive, "CompressedChunks.Count")
    if compressed_chunk_count:
        raise _unsupported("CompressedChunks.Count", compressed_chunk_count)

    header["PackageSource"] = archive.read_u32("PackageSource")
    additional_package_count = archive.read_u32("AdditionalPackagesToCook.Count")
    header["AdditionalPackagesToCook"] = []
    if additional_package_count:
        raise _unsupported(
            "AdditionalPackagesToCook.Count", additional_package_count
        )

    if legacy_version > -7:
        header["NumTextureAllocations"] = archive.read_i32("NumTextureAllocations")

    header["AssetRegistryDataOffset"] = archive.read_i32("AssetRegistryDataOffset")
    header["BulkDataStartOffset"] = _bigint_json_string(
        archive.read_i64("BulkDataStartOffset")
    )

    if file_version_ue4 >= UE4_WORLD_LEVEL_INFO:
        header["WorldTileInfoDataOffset"] = archive.read_i32(
            "WorldTileInfoDataOffset"
        )

    if file_version_ue4 >= UE4_CHANGED_CHUNKID_TO_BE_AN_ARRAY_OF_CHUNKIDS:
        chunk_count = _read_count(archive, "ChunkIDs.Count")
        header["ChunkIDs"] = []
        if chunk_count:
            raise _unsupported("ChunkIDs.Count", chunk_count)
    elif file_version_ue4 >= UE4_ADDED_CHUNKID_TO_ASSETDATA_AND_UPACKAGE:
        header["ChunkID"] = archive.read_i32("ChunkID")

    if file_version_ue4 >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:
        header["PreloadDependencyCount"] = archive.read_i32(
            "PreloadDependencyCount"
        )
        header["PreloadDependencyOffset"] = archive.read_i32(
            "PreloadDependencyOffset"
        )
    else:
        header["PreloadDependencyCount"] = -1
        header["PreloadDependencyOffset"] = 0

    if file_version_ue5 >= UE5_NAMES_REFERENCED_FROM_EXPORT_DATA:
        header["NamesReferencedFromExportDataCount"] = archive.read_i32(
            "NamesReferencedFromExportDataCount"
        )

    if file_version_ue5 >= UE5_PAYLOAD_TOC:
        payload_toc_offset = archive.read_i64("PayloadTocOffset")
    else:
        payload_toc_offset = -1
    header["PayloadTocOffset"] = _bigint_json_string(payload_toc_offset)

    if file_version_ue5 >= UE5_DATA_RESOURCES:
        header["DataResourceOffset"] = archive.read_i32("DataResourceOffset")

    return header


def _read_names(archive: FArchive, header: dict[str, Any]) -> list[dict[str, Any]]:
    archive.seek(header["NameOffset"])
    return [
        {
            "Name": archive.read_fstring(f"Names[{index}].Name"),
            "NonCasePreservingHash": archive.read_u16(
                f"Names[{index}].NonCasePreservingHash"
            ),
            "CasePreservingHash": archive.read_u16(
                f"Names[{index}].CasePreservingHash"
            ),
        }
        for index in range(header["NameCount"])
    ]


def _read_zero_metadata(archive: FArchive, field: str) -> dict[str, Any]:
    value_count = archive.read_i32(f"{field}.ValueCount")
    if value_count != 0:
        raise _unsupported(f"{field}.ValueCount", value_count)
    return {"ValueCount": value_count, "Values": []}


def _read_gatherable_text_data(
    archive: FArchive, header: dict[str, Any]
) -> list[dict[str, Any]]:
    count = header.get("GatherableTextDataCount", 0)
    archive.seek(header.get("GatherableTextDataOffset", 0))
    records: list[dict[str, Any]] = []
    for record_index in range(count):
        record_field = f"GatherableTextData[{record_index}]"
        namespace_name = archive.read_fstring(f"{record_field}.NamespaceName")
        source_string = archive.read_fstring(f"{record_field}.SourceData.SourceString")
        source_metadata = _read_zero_metadata(
            archive, f"{record_field}.SourceData.SourceStringMetaData"
        )

        context_count = _read_count(
            archive, f"{record_field}.SourceSiteContexts.Count"
        )
        contexts = []
        for context_index in range(context_count):
            context_field = f"{record_field}.SourceSiteContexts[{context_index}]"
            contexts.append({
                "KeyName": archive.read_fstring(f"{context_field}.KeyName"),
                "SiteDescription": archive.read_fstring(
                    f"{context_field}.SiteDescription"
                ),
                "IsEditorOnly": archive.read_u32(f"{context_field}.IsEditorOnly"),
                "IsOptional": archive.read_u32(f"{context_field}.IsOptional"),
                "InfoMetaData": _read_zero_metadata(
                    archive, f"{context_field}.InfoMetaData"
                ),
                "KeyMetaData": _read_zero_metadata(
                    archive, f"{context_field}.KeyMetaData"
                ),
            })

        records.append({
            "NamespaceName": namespace_name,
            "SourceData": {
                "SourceString": source_string,
                "SourceStringMetaData": source_metadata,
            },
            "SourceSiteContexts": contexts,
        })
    return records


def _read_uasset_reader_js_payload(archive: FArchive) -> dict[str, Any]:
    header = _read_header(archive)
    return {
        "header": header,
        "names": _read_names(archive, header),
        "gatherableTextData": _read_gatherable_text_data(archive, header),
    }


def render_uasset_reader_js(file_path: str) -> str:
    """Render the pinned uasset-reader-js header/name/text JSON subset."""
    archive = FArchive(file_path, tolerant=False)
    try:
        return json.dumps(
            _read_uasset_reader_js_payload(archive), indent=2, ensure_ascii=False
        )
    finally:
        archive.close()
