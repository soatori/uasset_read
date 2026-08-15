"""Package bundle and provider helpers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import logging
import os

from uasset_read.archive import FArchive, ArchiveLike, ByteArchive
from uasset_read.bounded_events import BoundedEventBuffer
from uasset_read.exceptions import ParseError
from uasset_read.memory_safety import ResourceBudget

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
        self._init_archive_attrs(
            getattr(main_archive, "_path", "<package>"), tolerant, hex_view=False
        )
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
            raise ParseError(
                f"read() received negative size ({size}) at position {self.tell()}"
            )
        current_pos = self.tell()
        remaining = self._file_size - current_pos
        if size > remaining:
            raise ParseError(
                f"Cannot read {size} bytes at position {current_pos}, "
                f"only {remaining} bytes remaining"
            )
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
                    f"short read: requested {take} bytes at segment offset {segment_pos}, "
                    f"got {len(chunk)} bytes"
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
class SourceProvenance:
    """Records which source served a file read.

    Attributes:
        mount_root: Logical mount root prefix (e.g. "/Game/Content/").
        provider_label: Human-readable label for the provider (e.g. "base_pak").
        container: Provider container type (e.g. "filesystem", "pak", "iostore").
    """

    mount_root: str
    provider_label: str
    container: str

    def __str__(self) -> str:
        return f"SourceProvenance(root={self.mount_root!r}, label={self.provider_label!r}, container={self.container!r})"


@dataclass
class MountPoint:
    """A mounted source with a logical path prefix.

    Attributes:
        mount_root: Logical path prefix (e.g. "/Game/Content/").
        provider: The provider serving files from this mount.
        priority: Higher values are checked first (default 0).
        label: Human-readable source name for provenance tracking.
    """

    mount_root: str
    provider: "PackageProvider"
    priority: int = 0
    label: str = ""


@dataclass
class PackageBundle:
    """A discovered package plus sidecar payloads."""

    main_path: str
    package_kind: str
    container: str = "filesystem"
    files: Dict[str, str] = field(default_factory=dict)
    payloads: Dict[str, bytes] = field(default_factory=dict)
    provider: Optional["PackageProvider"] = None
    source: Optional[SourceProvenance] = None

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

    def read_payload(self, extension: str) -> Optional[bytes]:
        extension = _normalize_ext(extension)
        if extension in self.payloads:
            return self.payloads[extension]
        path = self.files.get(extension)
        if path is None:
            return None
        with open(path, "rb") as f:
            return f.read()

    def _open_archive_for(self, extension: str, tolerant: bool) -> ArchiveLike:
        extension = _normalize_ext(extension)
        if extension in self.payloads:
            return ByteArchive(self.payloads[extension], tolerant=tolerant, name=self.package_files[extension])
        path = self.files.get(extension)
        if path is None:
            raise ParseError(f"Package sidecar not found: {extension}")
        return FArchive(path, tolerant=tolerant)

    def close(self) -> None:
        """Close all opened resources (idempotent)."""
        # PackageBundle itself does not hold file handles, only provider references
        # Provider lifecycle is managed by the caller
        pass


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

    def open_package_bundle(self, path: str, tolerant: bool = False,
                            budget: ResourceBudget | None = None) -> PackageBundle:
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
        normalized = path.replace("\\", "/")
        if normalized in files:
            return normalized
        for ext in PACKAGE_EXTENSIONS:
            candidate = f"{normalized}{ext}"
            if candidate in files:
                return candidate
        lowered = normalized.lower()
        for candidate in files:
            candidate_normalized = candidate.replace("\\", "/")
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


class MultiSourceProvider(PackageProvider):
    """Provider that composes multiple mounted sources with priority-based resolution.

    Each mount point has a logical path prefix (mount_root) and a provider.
    When resolving a path, mounts are checked in descending priority order.
    The first mount whose provider can resolve the path wins.

    Attributes:
        container: Always "multi" for composed providers.
    """

    container = "multi"

    def __init__(self, mounts: List[MountPoint] | None = None):
        self._mounts: List[MountPoint] = []
        for m in mounts or []:
            self._mounts.append(m)
        self._mounts.sort(key=lambda m: -m.priority)

    def add_mount(self, mount: MountPoint) -> None:
        """Add a mount point and re-sort by priority."""
        self._mounts.append(mount)
        self._mounts.sort(key=lambda m: -m.priority)

    def remove_mount(self, mount_root: str) -> None:
        """Remove all mounts with the given logical root."""
        self._mounts = [m for m in self._mounts if m.mount_root != mount_root]

    @property
    def mounts(self) -> List[MountPoint]:
        """Return a copy of the current mount list (sorted by priority)."""
        return list(self._mounts)

    def list_files(self) -> List[str]:
        """List all files across all mounts as logical paths.

        Files from higher-priority mounts shadow lower-priority mounts
        with the same logical path.
        """
        seen: set[str] = set()
        result: list[str] = []
        for mount in self._mounts:
            for physical in mount.provider.list_files():
                logical = self._to_logical(physical, mount)
                if logical not in seen:
                    seen.add(logical)
                    result.append(logical)
        return result

    def read_file(self, path: str) -> bytes | None:
        """Read a file by logical path, checking mounts in priority order."""
        for mount in self._mounts:
            physical = self._to_physical(path, mount)
            if physical is not None:
                data = mount.provider.read_file(physical)
                if data is not None:
                    return data
        return None

    def open_package_bundle(
        self,
        path: str,
        tolerant: bool = False,
        budget: "ResourceBudget | None" = None,
    ) -> PackageBundle:
        """Open a package bundle by logical path with source-provenance tracking.

        The bundle's ``source`` field records which mount served it, and the
        ``provider`` field is set to this ``MultiSourceProvider`` so that
        sidecar resolution is source-consistent (sidecars come from the same
        provider that served the main file).

        Raises:
            FileNotFoundError: If no mount can resolve the logical path.
        """
        for mount in self._mounts:
            physical = self._to_physical(path, mount)
            if physical is not None:
                bundle = mount.provider.open_package_bundle(
                    physical, tolerant=tolerant, budget=budget,
                )
                # Set provenance from this mount
                bundle.source = SourceProvenance(
                    mount_root=mount.mount_root,
                    provider_label=mount.label or mount.provider.container,
                    container=mount.provider.container,
                )
                # Set provider to self so caller sees the composed provider
                bundle.provider = self
                return bundle
        raise FileNotFoundError(path)

    def resolve_source(self, path: str) -> SourceProvenance | None:
        """Resolve which source serves a given logical path.

        Returns ``None`` if no mount can resolve the path.
        """
        for mount in self._mounts:
            physical = self._to_physical(path, mount)
            if physical is not None:
                return SourceProvenance(
                    mount_root=mount.mount_root,
                    provider_label=mount.label or mount.provider.container,
                    container=mount.provider.container,
                )
        return None

    def _to_logical(self, physical_path: str, mount: MountPoint) -> str:
        """Convert a physical path (from a provider) to a logical path.

        For filesystem providers, the physical path is absolute and must be
        made relative to the provider's root before prepending the mount root.
        For other providers, the path is treated as already relative.
        """
        physical = physical_path.replace("\\", "/")
        mount_root = mount.mount_root.rstrip("/") + "/"
        # Strip provider root if present (filesystem providers return absolute paths)
        provider_root = getattr(mount.provider, "root", None)
        if provider_root is not None:
            root_str = str(provider_root).replace("\\", "/").rstrip("/") + "/"
            if physical.startswith(root_str):
                physical = physical[len(root_str):]
        # If the physical path already starts with the mount root, strip it
        if physical.startswith(mount_root):
            relative = physical[len(mount_root):]
            return mount_root + relative if relative else mount_root.rstrip("/")
        # Otherwise, just prefix with mount root
        return mount_root + physical.lstrip("/")

    def _to_physical(self, logical_path: str, mount: MountPoint) -> str | None:
        """Convert a logical path to a physical path for a given mount.

        Returns ``None`` if the logical path does not belong to this mount
        or if the mount's provider cannot resolve the physical path.

        For filesystem providers, the result is an absolute path by prepending
        the provider's root. For other providers, the result is a relative path.
        """
        logical = logical_path.replace("\\", "/")
        mount_root = mount.mount_root.rstrip("/") + "/"
        # Check if the logical path belongs to this mount's prefix
        if not logical.startswith(mount_root) and not logical.startswith(mount.mount_root):
            return None
        # Strip the mount root to get the relative path
        if logical.startswith(mount_root):
            relative = logical[len(mount_root):]
        else:
            relative = logical[len(mount.mount_root):]
        if not relative:
            return None
        # For filesystem providers, prepend root to get absolute physical path
        provider_root = getattr(mount.provider, "root", None)
        if provider_root is not None:
            root_str = str(provider_root).replace("\\", "/").rstrip("/")
            return root_str + "/" + relative
        return relative


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
            raise PermissionError(
                f"Path '{path}' resolves outside root '{root}': {resolved}"
            )
        return resolved

    def list_files(self) -> list[str]:
        current_mtime = self._get_root_mtime()
        # Check if cache is valid: exists and modification time unchanged
        if (self._list_files_cache is not None
                and self._cache_mtime == current_mtime):
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

    def refresh_file_cache(self) -> None:
        """Clear the file list cache; next list_files() call will rescan."""
        self._list_files_cache = None
        self._cache_mtime = None

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

    def open_package_bundle(self, path: str, tolerant: bool = False,
                            budget: ResourceBudget | None = None) -> PackageBundle:
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


class PakPackageProvider(PackageProvider):
    container = "pak"

    def __init__(self, reader):
        self.reader = reader

    def list_files(self) -> list[str]:
        return self.reader.list_files()

    def read_file(self, path: str) -> Optional[bytes]:
        return self.reader.extract(path)


class IoStorePackageProvider(PackageProvider):
    container = "iostore"

    def __init__(self, reader):
        self.reader = reader

    def list_files(self) -> list[str]:
        return self.reader.list_files()

    def read_file(self, path: str) -> Optional[bytes]:
        if hasattr(self.reader, "extract_path"):
            return self.reader.extract_path(path)
        chunk_id = getattr(self.reader, "_directory_index", {}).get(path)
        if chunk_id is None:
            return None
        return self.reader.extract(chunk_id.bytes)


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

