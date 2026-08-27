"""Zen package reader — Phase 5 implementation plan and stub.

Target: Read FZenPackageSummary and export bundle headers/entries
to build the same PackageTables model as LegacyPackageReader.

Blocked on: real Zen package fixtures (UE5.1+ cooked packages).

UE Source References:
- FZenPackageSummary: Engine/Source/Runtime/CoreUObject/Public/Serialization/ZenPackageVisitor.h
- FZenPackageSummary serialization: Engine/Source/Runtime/CoreUObject/Private/Serialization/AsyncLoading2.cpp
  (FPackageSummarySummary::SerializeZenPackage / LoadIntoMemory)
- Export bundle: FExportBundleHeader / FExportBundleEntry in AsyncLoading2.cpp
- Name map: FName::LoadAsync (hashed name map, not sequential like legacy)
- Import map: Serialized as FZenImportInfo[]
- Package trailer: FPackageTrailer (Engine/Source/Runtime/CoreUObject/Public/Serialization/PackageTrailer.h)

Format layout (UE5.1+):
  [FZenPackageSummary]  — header with hashes, not offsets
  [Compressed name map] — zlib/zstd compressed FName entries
  [Compressed import map]
  [Compressed export map]
  [Export bundle headers + entries]
  [Export payloads]     — inline or referenced from bulk regions
  [Package trailer]     — optional, contains bulk data offsets

Key differences from legacy:
- No sequential offset-based tables; uses hash-based lookup
- Name map is compressed and hashed (not a simple index array)
- Export headers are grouped in bundles (FBulkDataSource)
- Package trailer provides external payload routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..source import Source
from ..version import VersionContext


@dataclass(frozen=True)
class ZenPackageSummary:
    """FZenPackageSummary — Zen package header.

    UE Source: ZenPackageVisitor.h lines 30-60 (approximate)

    Fields:
        package_flags: EPackageFlags
        total_header_size: Total size of the header region
        name_map_hash: Hash of the compressed name map (for dedup)
        import_map_hash: Hash of the compressed import map
        export_map_hash: Hash of the compressed export map
        exported_package_names_hash: Hash of exported package names
        data_resources_hash: Hash of data resources
        mesh_package_indices_hash: Hash of mesh package indices
        compressed_header_size: Size of compressed header data
        uncompressed_header_size: Size after decompression
    """

    package_flags: int = 0
    total_header_size: int = 0
    name_map_hash: bytes = b""
    import_map_hash: bytes = b""
    export_map_hash: bytes = b""
    exported_package_names_hash: bytes = b""
    data_resources_hash: bytes = b""
    mesh_package_indices_hash: bytes = b""
    compressed_header_size: int = 0
    uncompressed_header_size: int = 0


@dataclass(frozen=True)
class ZenImportEntry:
    """FZenImportInfo — single import entry in Zen format."""

    class_package_index: int = 0  # Package index (negative = import)
    object_name_index: int = 0  # Name map index
    outer_index: int = 0  # Outer import index


@dataclass(frozen=True)
class ExportBundleHeader:
    """FExportBundleHeader — batch header for export entries."""

    batch_index: int = 0
    entry_count: int = 0
    first_export_index: int = 0


@dataclass(frozen=True)
class ExportBundleEntry:
    """FExportBundleEntry — single export in Zen bundle format.

    UE Source: AsyncLoading2.cpp FExportBundleEntry
    """

    object_name_index: int = 0  # Name map index
    class_index: int = 0  # Import index (negative = import)
    outer_index: int = 0  # Import index
    serial_offset: int = 0  # Offset within the package
    serial_size: int = 0
    cooked_header_size: int = 0  # Size of the cooked header data


class ZenPackageReader:
    """Read a Zen package from a Source.

    Phase 5 stub — requires real FZenPackageSummary fixtures.
    Once fixtures are available, implement by following UE's
    AsyncLoading2.cpp deserialization path.

    Implementation plan:
    1. Read FZenPackageSummary (fixed-size header)
    2. Decompress name map (zlib/zstd)
    3. Decompress import map, parse FZenImportInfo[]
    4. Decompress export map, parse FExportBundleHeader + FExportBundleEntry[]
    5. For each export: read serial data from Source at (offset, size)
    6. Build PackageTables → ObjectRecord[] → PackageDocument
    """

    def __init__(self, source: Source, context: VersionContext):
        self._source = source
        self._context = context
        self._summary: ZenPackageSummary | None = None
        self._name_map: list[str] = []
        self._imports: list[ZenImportEntry] = []
        self._export_bundles: list[ExportBundleHeader] = []
        self._export_entries: list[ExportBundleEntry] = []

    def read_summary(self) -> ZenPackageSummary:
        """Read FZenPackageSummary from source.

        UE Reference: AsyncLoading2.cpp FPackageSummarySummary::SerializeZenPackage

        When implemented, this will:
        - Read the fixed-size ZenPackageSummary from offset 0
        - Validate the tag and version
        - Return the parsed summary
        """
        raise NotImplementedError(
            "ZenPackageReader.read_summary requires real Zen package fixtures. "
            "Expected fixture: a .uasset file produced by UE5.1+ with "
            "FZenPackageSummary header (detectable by version >= 522 and "
            "hash-based table layout instead of offset-based). "
            "See: Engine/Source/Runtime/CoreUObject/Private/Serialization/AsyncLoading2.cpp"
        )

    def read_name_map(self) -> list[str]:
        """Decompress and parse the name map.

        UE Reference: FName::LoadAsync / FZenNameMap serialization

        The Zen name map is compressed (zlib/zstd) and uses hash-based
        lookup instead of sequential indexing. Must decompress first.
        """
        raise NotImplementedError("ZenPackageReader.read_name_map requires fixtures")

    def read_imports(self) -> list[ZenImportEntry]:
        """Decompress and parse the import map.

        UE Reference: AsyncLoading2.cpp ZenImportInfo deserialization

        Each import is a FZenImportInfo with class package index,
        object name index, and outer index.
        """
        raise NotImplementedError("ZenPackageReader.read_imports requires fixtures")

    def read_export_bundles(self) -> list[ExportBundleEntry]:
        """Parse export bundle headers and entries.

        UE Reference: AsyncLoading2.cpp FExportBundleHeader/FExportBundleEntry

        Exports are grouped in bundles. Each bundle has a header
        with batch_index, entry_count, and first_export_index.
        """
        raise NotImplementedError("ZenPackageReader.read_export_bundles requires fixtures")

    def to_document(self) -> Any:
        """Build PackageDocument from Zen package.

        TODO: Bridge to v2 PackageDocument after reading all tables.
        """
        raise NotImplementedError("ZenPackageReader.to_document requires fixtures")
