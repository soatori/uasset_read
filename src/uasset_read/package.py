"""Package bundle and provider helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Literal
import logging

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.models.document import PackageDocument

logger = logging.getLogger(__name__)


PACKAGE_EXTENSIONS = (".uasset", ".umap")
PACKAGE_PAYLOAD_EXTENSIONS = (".uexp", ".ubulk", ".uptnl")


class PackageArchive(FArchive):
    """Virtual archive spanning .uasset/.umap plus optional .uexp."""

    def __init__(
        self,
        main_archive: FArchive,
        uexp_archive: FArchive | None = None,
        tolerant: bool = False,
    ):
        self._init_archive_attrs(getattr(main_archive, "_path", "<package>"), tolerant)
        self._main_archive = main_archive
        self._uexp_archive = uexp_archive
        try:
            self._main_size = main_archive.total_size()
            uexp_size = uexp_archive.total_size() if uexp_archive else 0
        except Exception:
            # Close all opened archives on initialization failure (#464)
            if uexp_archive is not None:
                uexp_archive.close()
            main_archive.close()
            raise
        self._file_size = self._main_size + uexp_size
        self._pos = 0

    def read(self, size: int) -> bytes:
        if size < 0:
            raise ParseError(f"read() received negative size ({size}) at position {self.tell()}")
        current_pos = self.tell()
        self._check_read_range(current_pos, size)
        remaining = self._file_size - current_pos
        if size > remaining:
            raise ParseError(f"Cannot read {size} bytes at position {current_pos}, only {remaining} bytes remaining")
        chunks: list[bytes] = []
        to_read = size
        while to_read:
            if self._pos < self._main_size:
                segment = self._main_archive
                segment_pos = self._pos
                segment_remaining = self._main_size - self._pos
            elif self._uexp_archive is not None:
                segment = self._uexp_archive
                segment_pos = self._pos - self._main_size
                segment_remaining = self._file_size - self._pos
            else:
                raise ParseError(f"No payload archive available at position {self._pos}")

            take = min(to_read, segment_remaining)
            segment.seek(segment_pos)
            chunk = segment.read(take)
            if len(chunk) < take:
                raise ParseError(
                    f"short read: requested {take} bytes at segment offset {segment_pos}, got {len(chunk)} bytes"
                )
            chunks.append(chunk)
            self._pos += take
            to_read -= take
        return b"".join(chunks)

    def seek(self, pos: int) -> None:
        self.validate_offset(pos, "package seek")
        self._pos = pos

    def tell(self) -> int:
        return self._pos

    def close(self) -> None:
        self._main_archive.close()
        if self._uexp_archive is not None:
            self._uexp_archive.close()
        self._use_mmap = False

    def set_byte_swapping(self, enabled: bool) -> None:
        self._byte_swapping = enabled
        self._main_archive.set_byte_swapping(enabled)
        if self._uexp_archive is not None:
            self._uexp_archive.set_byte_swapping(enabled)

    def total_size(self) -> int:
        return self._file_size

    @property
    def main_size(self) -> int:
        """Byte length of the main (.uasset/.umap) segment."""
        return self._main_size

    @property
    def has_uexp(self) -> bool:
        """Whether a .uexp segment is currently spliced into the address space."""
        return self._uexp_archive is not None

    def reject_uexp_region(self) -> None:
        """Detach the .uexp segment and shrink the address space to the main file.

        Call this when the UE split-file invariant does not hold, so that an
        export ``SerialOffset`` cannot silently resolve into the wrong bytes.
        Idempotent; safe to call when no .uexp is present.

        UE basis: ``SavePackage2.cpp:3767`` rebases ``Export.SerialOffset +=
        Summary.TotalHeaderSize`` and ``FilePackageWriterUtil.cpp:164-176``
        writes .uexp from that offset, so the splice is only address-correct when
        the main file is exactly ``TotalHeaderSize`` bytes long
        (``AsyncLoading.cpp:605-611`` uses the same condition to auto-detect).
        """
        if self._uexp_archive is not None:
            self._uexp_archive.close()
            self._uexp_archive = None
        self._file_size = self._main_size

    def set_property_version_gates(self, ue4: int, ue5: int) -> None:
        """Publish the file versions that gate FProperty tag decoding downstream."""
        self._file_version_ue4 = ue4
        self._file_version_ue5 = ue5


@dataclass
class PackageBundle:
    """A discovered package plus its sidecar files."""

    main_path: str
    package_kind: str
    container: str = "filesystem"
    files: dict[str, str] = field(default_factory=dict)

    @cached_property
    def uexp_path(self) -> Path | None:
        """Return .uexp sidecar path if it exists, else None (cached)."""
        path = self.files.get(".uexp")
        return Path(path) if path is not None else None

    @cached_property
    def ubulk_path(self) -> Path | None:
        """Return .ubulk sidecar path if it exists, else None (cached)."""
        path = self.files.get(".ubulk")
        return Path(path) if path is not None else None

    @cached_property
    def uptnl_path(self) -> Path | None:
        """Return .uptnl sidecar path if it exists, else None (cached)."""
        path = self.files.get(".uptnl")
        return Path(path) if path is not None else None

    def open_archive(self, tolerant: bool = False) -> PackageArchive:
        main_ext = ".umap" if self.package_kind == "map" else ".uasset"
        main = self._open_archive_for(main_ext, tolerant)
        try:
            uexp = self._open_archive_for(".uexp", tolerant) if ".uexp" in self.files else None
        except Exception:
            main.close()
            raise
        return PackageArchive(main, uexp, tolerant=tolerant)

    def _open_archive_for(self, extension: str, tolerant: bool) -> FArchive:
        # Callers pass dotted literals (".uasset" / ".umap" / ".uexp").
        path = self.files.get(extension)
        if path is None:
            raise ParseError(f"Package sidecar not found: {extension}")
        return FArchive(path, tolerant=tolerant)


def open_package_bundle(path: str) -> PackageBundle:
    """Discover a package bundle from a filesystem path."""
    main = Path(path)
    if main.suffix.lower() not in PACKAGE_EXTENSIONS:
        for ext in PACKAGE_EXTENSIONS:
            candidate = main.with_suffix(ext)
            if candidate.is_file():
                main = candidate
                break
    if not main.is_file():
        raise FileNotFoundError(path)
    ext = main.suffix.lower()
    package_kind = "map" if ext == ".umap" else "asset"
    files = {ext: str(main)}
    for payload_ext in PACKAGE_PAYLOAD_EXTENSIONS:
        sidecar = main.with_suffix(payload_ext)
        if sidecar.is_file():
            files[payload_ext] = str(sidecar)
    return PackageBundle(
        main_path=str(main),
        package_kind=package_kind,
        container="filesystem",
        files=files,
    )


@lru_cache(maxsize=8)
def _parse_cached(
    resolved: str,
    _mtime_ns: int,
    _size: int,
    depth: Literal["package", "object", "asset", "decode"],
    ids_key: tuple[str, ...] | None,
    tolerant: bool,
    mappings_path: str | None,
    game: str | None,
) -> PackageDocument:
    """Process-local parse cache body (G2). Unused key fields force invalidation."""
    from .parsers.legacy_reader import LegacyPackageReader

    bundle = open_package_bundle(resolved)
    archive = bundle.open_archive(tolerant=tolerant)
    try:
        reader = LegacyPackageReader(
            tolerant=tolerant,
            mappings_path=mappings_path,
            game=game,
        )
        object_ids = None if ids_key is None else list(ids_key)
        return reader.read(
            depth=depth,
            object_ids=object_ids,
            archive=archive,
            main_path=bundle.main_path,
        )
    finally:
        archive.close()


def parse_package_document(
    file_path: str | Path,
    *,
    tolerant: bool = True,
    mappings_path: str | None = None,
    game: str | None = None,
    depth: Literal["package", "object", "asset", "decode"] = "asset",
    object_ids: list[str] | None = None,
) -> PackageDocument:
    """Parse a .uasset/.umap and return a PackageDocument.

    Reads the binary format directly using LegacyPackageReader.
    Discovers sidecar files (.uexp, .ubulk, .uptnl) via PackageBundle
    so that the reader receives an archive spanning main + .uexp.

    Repeated calls with the same resolved path, mtime_ns, size, depth,
    object_ids, tolerant, mappings_path, and game return the same document
    object (G2). Callers must treat the returned document as read-only.
    """
    bundle = open_package_bundle(str(file_path))
    main = Path(bundle.main_path).resolve()
    st = main.stat()
    ids_key = None if object_ids is None else tuple(sorted(object_ids))
    return _parse_cached(
        str(main),
        st.st_mtime_ns,
        st.st_size,
        depth,
        ids_key,
        tolerant,
        mappings_path,
        game,
    )
