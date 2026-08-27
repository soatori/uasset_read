"""IoStore chunk source — stub for Phase 5.

Target: Read individual package objects from IoStore containers
(.utoc/.ucas) via chunk-based range reading.

Blocked on: real IoStore container fixtures (.utoc/.ucas files).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..source import Source, SourceInfo


@dataclass(frozen=True)
class IoChunkInfo:
    """IoStore chunk descriptor."""

    chunk_id: bytes  # 12-byte FIoChunkId
    offset: int = 0
    size: int = 0
    compression_block_offset: int = 0
    compression_block_size: int = 0
    is_compressed: bool = False
    is_encrypted: bool = False


class IoStoreChunkSource:
    """Read individual chunks from an IoStore container.

    Phase 5 stub — requires real .utoc/.ucas fixture files.
    Wraps the existing IoStoreReader (src/uasset_read/iostore/reader.py)
    but adapts it to the v2 Source protocol for package-level reading.
    """

    def __init__(self, toc_path: str, cas_path: str):
        self._toc_path = toc_path
        self._cas_path = cas_path
        self._reader: Any = None  # IoStoreReader instance

    def open(self) -> None:
        """Open the IoStore container.

        TODO: Wire to existing IoStoreReader.open()
        """
        raise NotImplementedError(
            "IoStoreChunkSource.open requires real .utoc/.ucas fixtures. "
            "See docs/designs/2026-08-26-package-first-uasset-parser-refactor.md Phase 5."
        )

    def list_packages(self) -> list[str]:
        """List all package names in the container.

        TODO: Use directory index from IoStore TOC.
        """
        raise NotImplementedError("IoStoreChunkSource.list_packages requires fixtures")

    def read_chunk(self, chunk_id: bytes) -> bytes:
        """Read a raw chunk by its FIoChunkId.

        TODO: Delegate to IoStoreReader.extract().
        """
        raise NotImplementedError("IoStoreChunkSource.read_chunk requires fixtures")

    def get_package_source(self, package_name: str) -> Source | None:
        """Get a Source for reading a specific package from the container.

        TODO: Resolve package name to chunk IDs, return a Source that
        reads the package bytes from the container.
        """
        raise NotImplementedError("IoStoreChunkSource.get_package_source requires fixtures")

    def describe(self) -> SourceInfo:
        return SourceInfo(
            kind="iostore",
            name=self._toc_path.rsplit("/", 1)[-1],
            size=0,  # Unknown until opened
        )

    def close(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None


class IoStoreContainerInfo:
    """Summary of an opened IoStore container."""

    version: int = 0
    toc_entry_count: int = 0
    compression_method_count: int = 0
    compression_block_size: int = 0
    is_encrypted: bool = False
    is_compressed: bool = False
    partition_count: int = 1
    package_count: int = 0  # Number of .uasset packages in container
