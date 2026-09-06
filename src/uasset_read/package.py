"""Package bundle and provider helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Literal, Optional
import logging
import os

from uasset_read.archive import FArchive, ArchiveLike
from uasset_read.exceptions import ParseError
from uasset_read.memory_safety import ResourceBudget
from uasset_read.models.document import PackageDocument

logger = logging.getLogger(__name__)


PACKAGE_EXTENSIONS = (".uasset", ".umap")
PACKAGE_PAYLOAD_EXTENSIONS = (".uexp", ".ubulk", ".uptnl")


class PackageArchive(FArchive):
    """Virtual archive spanning .uasset/.umap plus optional .uexp."""

    def __init__(
        self,
        main_archive: ArchiveLike,
        uexp_archive: Optional[ArchiveLike] = None,
        tolerant: bool = False,
    ):
        self._init_archive_attrs(getattr(main_archive, "_path", "<package>"), tolerant, hex_view=False)
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
        # Release diagnostic buffers to reclaim memory
        self._diagnostics.clear()
        self._hex_view_entries.clear()

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

    def get_mmap_info(self) -> Dict:
        getter = getattr(self._main_archive, "get_mmap_info", None)
        main_info = getter() if getter is not None else {}
        return {"used": bool(main_info.get("used")), "warning": main_info.get("warning")}


@dataclass
class PackageBundle:
    """A discovered package plus its sidecar files."""

    main_path: str
    package_kind: str
    container: str = "filesystem"
    files: Dict[str, str] = field(default_factory=dict)
    provider: Optional["FileSystemPackageProvider"] = None

    @property
    def main_path_obj(self) -> Path:
        """Return main_path as a Path object."""
        return Path(self.main_path)

    @property
    def uexp_path(self) -> Optional[Path]:
        """Return .uexp sidecar path if it exists, else None."""
        path = self.files.get(".uexp")
        return Path(path) if path is not None else None

    @property
    def ubulk_path(self) -> Optional[Path]:
        """Return .ubulk sidecar path if it exists, else None."""
        path = self.files.get(".ubulk")
        return Path(path) if path is not None else None

    @property
    def uptnl_path(self) -> Optional[Path]:
        """Return .uptnl sidecar path if it exists, else None."""
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

    def _open_archive_for(self, extension: str, tolerant: bool) -> ArchiveLike:
        extension = _normalize_ext(extension)
        path = self.files.get(extension)
        if path is None:
            raise ParseError(f"Package sidecar not found: {extension}")
        return FArchive(path, tolerant=tolerant)


class FileSystemPackageProvider:
    """Filesystem package provider: discovers and opens .uasset/.umap bundles."""

    container = "filesystem"

    def __init__(self, root: str | os.PathLike[str] | None = None):
        self.root = Path(root).resolve() if root is not None else None

    @staticmethod
    def _assert_within_root(path: Path, root: Path | None) -> Path:
        """Validate that the path is within root, return resolved path."""
        if root is None:
            return path.resolve()
        resolved = (root / path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            raise PermissionError(f"Path '{path}' resolves outside root '{root}': {resolved}")
        return resolved

    def open_package_bundle(
        self, path: str, tolerant: bool = False, budget: ResourceBudget | None = None
    ) -> PackageBundle:
        main = Path(path)
        if self.root is not None and not main.is_file() and not main.is_absolute():
            root_relative = self.root / main
            if root_relative.is_file():
                main = root_relative
        if self.root is not None:
            main = self._assert_within_root(main, self.root)
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
        if budget is not None:
            budget.reserve(main.stat().st_size, f"bundle_main:{main.name}")
        return PackageBundle(
            main_path=str(main),
            package_kind=package_kind,
            container=self.container,
            files=files,
            provider=self,
        )


def open_package_bundle(
    path: str,
    provider: Optional["FileSystemPackageProvider"] = None,
    tolerant: bool = False,
    budget: ResourceBudget | None = None,
) -> PackageBundle:
    """Discover a package bundle from a filesystem path or provider path."""

    if provider is not None:
        return provider.open_package_bundle(path, tolerant=tolerant, budget=budget)
    return FileSystemPackageProvider().open_package_bundle(path, tolerant=tolerant, budget=budget)


def _normalize_ext(extension: str) -> str:
    return extension if extension.startswith(".") else f".{extension}"


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
    """
    from .parsers.legacy_reader import LegacyPackageReader

    bundle = open_package_bundle(str(file_path), tolerant=tolerant)
    archive = bundle.open_archive(tolerant=tolerant)
    try:
        reader = LegacyPackageReader(
            tolerant=tolerant,
            mappings_path=mappings_path,
            game=game,
        )
        doc = reader.read(
            depth=depth,
            object_ids=object_ids,
            archive=archive,
            main_path=bundle.main_path,
        )
        return doc
    finally:
        archive.close()
