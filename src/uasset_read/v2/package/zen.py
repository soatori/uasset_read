"""Zen package reader — stub for Phase 5.

Target: Read FZenPackageSummary and export bundle headers/entries
to build the same PackageTables model as LegacyPackageReader.

Blocked on: real Zen package fixtures (UE5.1+ cooked packages).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..source import Source
from ..version import VersionContext


@dataclass(frozen=True)
class ZenPackageSummary:
    """FZenPackageSummary — Zen package header."""

    package_flags: int = 0
    engine_version: str = ""
    package_name: str = ""
    total_header_size: int = 0
    name_map_hash: bytes = b""
    import_map_hash: bytes = b""
    export_map_hash: bytes = b""
    exported_package_names_hash: bytes = b""
    data_resources_hash: bytes = b""
    mesh_package_indices_hash: bytes = b""

    # Additional fields from Zen format
    compressed_header_size: int = 0
    uncompressed_header_size: int = 0


@dataclass(frozen=True)
class ExportBundleEntry:
    """Export bundle entry — Zen format export descriptor."""

    object_name: str = ""
    class_index: int = 0
    outer_index: int = 0
    serial_offset: int = 0
    serial_size: int = 0
    cooked_header_size: int = 0


class ZenPackageReader:
    """Read a Zen package from a Source.

    Phase 5 stub — requires real FZenPackageSummary fixtures.
    """

    def __init__(self, source: Source, context: VersionContext):
        self._source = source
        self._context = context
        self._summary: ZenPackageSummary | None = None

    def read_summary(self) -> ZenPackageSummary:
        """Read FZenPackageSummary from source.

        TODO: Implement based on UE source:
        Engine/Source/Runtime/CoreUObject/Private/Serialization/AsyncLoading2.cpp
        """
        raise NotImplementedError(
            "ZenPackageReader.read_summary requires real Zen package fixtures. "
            "See docs/designs/2026-08-26-package-first-uasset-parser-refactor.md Phase 5."
        )

    def read_objects(self) -> list[ExportBundleEntry]:
        """Read export bundle headers.

        TODO: Implement Zen export bundle reading.
        """
        raise NotImplementedError("ZenPackageReader.read_objects requires fixtures")

    def to_document(self) -> Any:
        """Build PackageDocument from Zen package.

        TODO: Bridge to v2 PackageDocument.
        """
        raise NotImplementedError("ZenPackageReader.to_document requires fixtures")
