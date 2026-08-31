"""Package bundle and provider helpers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
import logging
import os

from uasset_read.archive import FArchive, ArchiveLike, ByteArchive
from uasset_read.exceptions import ParseError, ExportBoundsExceeded
from uasset_read.memory_safety import ResourceBudget

logger = logging.getLogger(__name__)


def _normalize_path(s: str) -> str:
    """Normalize Windows backslashes to forward slashes and strip trailing slashes."""
    return s.replace(chr(92), "/").rstrip("/")


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
            self._uexp_size = uexp_archive.total_size() if uexp_archive else 0
        except Exception:
            # Close all opened archives on initialization failure (#464)
            if uexp_archive is not None:
                uexp_archive.close()
            main_archive.close()
            raise
        self._file_size = self._main_size + self._uexp_size
        self._pos = 0

    def read(self, size: int) -> bytes:
        if size < 0:
            raise ParseError(f"read() received negative size ({size}) at position {self.tell()}")
        current_pos = self.tell()
        if self._read_bound is not None and current_pos + size > self._read_bound:
            raise ExportBoundsExceeded(
                f"Read of {size} bytes at position {current_pos} exceeds export read bound {self._read_bound}"
            )
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

    def get_mmap_info(self) -> Dict:
        main_info = {}
        if hasattr(self._main_archive, "get_mmap_info"):
            main_info = self._main_archive.get_mmap_info()
        return {"used": bool(main_info.get("used")), "warning": main_info.get("warning")}


@dataclass
class PackageBundle:
    """A discovered package plus sidecar payloads."""

    main_path: str
    package_kind: str
    container: str = "filesystem"
    files: Dict[str, str] = field(default_factory=dict)
    payloads: Dict[str, bytes] = field(default_factory=dict)
    provider: Optional["PackageProvider"] = None

    @property
    def package_files(self) -> Dict[str, str]:
        out = dict(self.files)
        for ext in self.payloads:
            out.setdefault(ext, f"<{self.container}:{Path(self.main_path).with_suffix(ext).name}>")
        return out

    def open_archive(self, tolerant: bool = False) -> PackageArchive:
        main_ext = ".umap" if self.package_kind == "map" else ".uasset"
        main = self._open_archive_for(main_ext, tolerant)
        uexp = self._open_archive_for(".uexp", tolerant) if ".uexp" in self.package_files else None
        return PackageArchive(main, uexp, tolerant=tolerant)

    def _open_archive_for(self, extension: str, tolerant: bool) -> ArchiveLike:
        extension = _normalize_ext(extension)
        if extension in self.payloads:
            return ByteArchive(self.payloads[extension], tolerant=tolerant, name=self.package_files[extension])
        path = self.files.get(extension)
        if path is None:
            raise ParseError(f"Package sidecar not found: {extension}")
        return FArchive(path, tolerant=tolerant)

class PackageProvider(ABC):
    """Abstract package provider used by filesystem and container readers."""

    container = "unknown"

    @abstractmethod
    def list_files(self) -> list[str]:
        """List all files available from this provider."""
        ...

    @abstractmethod
    def read_file(self, path: str) -> Optional[bytes]:
        """Read the contents of a file by path, returning None if not found."""
        ...

    def open_file(self, path: str) -> Optional[ArchiveLike]:
        """Open file and return ArchiveLike, supporting range reads (recommended for large files).

        Default implementation: reads the full bytes and wraps as ByteArchive.
        Subclasses can override this method for more efficient implementations (e.g., FArchive's mmap support).
        """
        data = self.read_file(path)
        if data is None:
            return None
        return ByteArchive(data, name=path)

    def open_package_bundle(
        self, path: str, tolerant: bool = False, budget: ResourceBudget | None = None
    ) -> PackageBundle:
        path = self._resolve_package_path(path)
        ext = Path(path).suffix.lower()
        package_kind = "map" if ext == ".umap" else "asset"
        stem = path[: -len(ext)]
        files = {ext: path}
        payloads: dict[str, bytes] = {}
        main_data = self.read_file(path)
        if main_data is not None:
            if budget is not None:
                budget.reserve(len(main_data), f"bundle_main:{Path(path).name}")
            payloads[ext] = main_data
        for payload_ext in PACKAGE_PAYLOAD_EXTENSIONS:
            sidecar = stem + payload_ext
            data = self.read_file(sidecar)
            if data is not None:
                if budget is not None:
                    budget.reserve(len(data), f"bundle_sidecar:{Path(sidecar).name}")
                payloads[payload_ext] = data
        return PackageBundle(
            main_path=path,
            package_kind=package_kind,
            container=self.container,
            files=files,
            payloads=payloads,
            provider=self,
        )

    def _resolve_package_path(self, path: str) -> str:
        files = set(self.list_files())
        if path in files:
            return path
        normalized = _normalize_path(path)
        if normalized in files:
            return normalized
        for ext in PACKAGE_EXTENSIONS:
            candidate = f"{normalized}{ext}"
            if candidate in files:
                return candidate
        lowered = normalized.lower()
        for candidate in files:
            candidate_normalized = _normalize_path(candidate)
            if candidate_normalized.lower() == lowered:
                return candidate
            for ext in PACKAGE_EXTENSIONS:
                if candidate_normalized.lower() == f"{lowered}{ext}":
                    return candidate
            if candidate_normalized.lower().endswith(f"/{lowered}"):
                return candidate
            for ext in PACKAGE_EXTENSIONS:
                if candidate_normalized.lower().endswith(f"/{lowered}{ext}"):
                    return candidate
        raise FileNotFoundError(path)


class FileSystemPackageProvider(PackageProvider):
    container = "filesystem"

    def __init__(self, root: str | os.PathLike[str] | None = None):
        self.root = Path(root).resolve() if root is not None else None
        self._list_files_cache: list[str] | None = None
        self._cache_mtime: float | None = None  # Directory modification time when cached

    def _get_root_mtime(self) -> float:
        """Get the modification time of the root directory."""
        if self.root is None or not self.root.exists():
            return 0.0
        try:
            return self.root.stat().st_mtime
        except (OSError, OverflowError):
            return 0.0

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

    def list_files(self) -> list[str]:
        current_mtime = self._get_root_mtime()
        # Check if cache is valid: exists and modification time unchanged
        if self._list_files_cache is not None and self._cache_mtime == current_mtime:
            return self._list_files_cache
        if self.root is None or self.root.is_file():
            return []
        result = [
            str(path)
            for path in self.root.rglob("*")
            if path.is_file() and path.suffix.lower() in (*PACKAGE_EXTENSIONS, *PACKAGE_PAYLOAD_EXTENSIONS)
        ]
        self._list_files_cache = result
        self._cache_mtime = current_mtime
        return result

    def read_file(self, path: str) -> Optional[bytes]:
        p = Path(path)
        if self.root is not None:
            p = self._assert_within_root(p, self.root)
        if not p.is_file():
            return None
        with p.open("rb") as f:
            return f.read()

    def open_file(self, path: str) -> Optional[ArchiveLike]:
        """Open file and return FArchive (supports mmap for large files)."""
        p = Path(path)
        if self.root is not None:
            p = self._assert_within_root(p, self.root)
        if not p.is_file():
            return None
        return FArchive(str(p))

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
    provider: Optional[PackageProvider] = None,
    tolerant: bool = False,
    budget: ResourceBudget | None = None,
) -> PackageBundle:
    """Discover a package bundle from a filesystem path or provider path."""

    if provider is not None:
        return provider.open_package_bundle(path, tolerant=tolerant, budget=budget)
    return FileSystemPackageProvider().open_package_bundle(path, tolerant=tolerant, budget=budget)


def _normalize_ext(extension: str) -> str:
    return extension if extension.startswith(".") else f".{extension}"
