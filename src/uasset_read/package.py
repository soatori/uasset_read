"""Package bundle and provider helpers."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
import logging
import os

from uasset_read.archive import FArchive, ArchiveLike, ByteArchive
from uasset_read.bounded_events import BoundedEventBuffer
from uasset_read.exceptions import ParseError

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
        self._path = getattr(main_archive, "_path", "<package>")
        self._main_archive = main_archive
        self._uexp_archive = uexp_archive
        try:
            self._main_size = main_archive.total_size()
            self._uexp_size = uexp_archive.total_size() if uexp_archive else 0
        except Exception:
            # 初始化失败时关闭 main_archive
            main_archive.close()
            raise
        self._file_size = self._main_size + self._uexp_size
        self._pos = 0
        self._byte_swapping = False
        self._tolerant = tolerant
        self._mmap = None
        self._use_mmap = False
        self._mmap_warning = None
        self._logger = logging.getLogger(__name__)
        self._diagnostics: BoundedEventBuffer = BoundedEventBuffer(max_entries=10000)
        self._hex_view_enabled: bool = False
        self._hex_view_entries: BoundedEventBuffer = BoundedEventBuffer(max_entries=50000)
        self._hex_view_context: str = ""
        self._name_map: Optional[list] = None

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
            chunks.append(segment.read(take))
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
        # 释放诊断缓冲区以回收内存
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
        """关闭所有打开的资源（幂等）。"""
        # PackageBundle 本身不持有文件句柄，仅持有 provider 引用
        # Provider 的生命周期由调用者管理
        pass


class PackageProvider:
    """Abstract package provider used by filesystem and container readers."""

    container = "unknown"

    def list_files(self) -> list[str]:
        raise NotImplementedError

    def read_file(self, path: str) -> Optional[bytes]:
        raise NotImplementedError

    def open_file(self, path: str) -> Optional[ArchiveLike]:
        """打开文件返回 ArchiveLike，支持范围读取（推荐用于大文件）。

        默认实现：读取完整 bytes 并包装为 ByteArchive。
        子类可覆写此方法以提供更高效的实现（如 FArchive 的 mmap 支持）。
        """
        data = self.read_file(path)
        if data is None:
            return None
        return ByteArchive(data, name=path)

    def open_package_bundle(self, path: str, tolerant: bool = False) -> PackageBundle:
        path = self._resolve_package_path(path)
        ext = Path(path).suffix.lower()
        package_kind = "map" if ext == ".umap" else "asset"
        stem = path[: -len(ext)]
        files = {ext: path}
        payloads: dict[str, bytes] = {}
        main_data = self.read_file(path)
        if main_data is not None:
            payloads[ext] = main_data
        for payload_ext in PACKAGE_PAYLOAD_EXTENSIONS:
            sidecar = stem + payload_ext
            data = self.read_file(sidecar)
            if data is not None:
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


class FileSystemPackageProvider(PackageProvider):
    container = "filesystem"

    def __init__(self, root: str | os.PathLike[str] | None = None):
        self.root = Path(root).resolve() if root is not None else None
        self._list_files_cache: list[str] | None = None
        self._cache_mtime: float | None = None  # 缓存时的目录修改时间

    def _get_root_mtime(self) -> float:
        """获取 root 目录的修改时间。"""
        if self.root is None or not self.root.exists():
            return 0.0
        try:
            return self.root.stat().st_mtime
        except (OSError, OverflowError):
            return 0.0

    def list_files(self) -> list[str]:
        current_mtime = self._get_root_mtime()
        # 检查缓存是否有效：存在且修改时间未变
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
        """清除文件列表缓存，下次 list_files() 调用时重新扫描。"""
        self._list_files_cache = None
        self._cache_mtime = None

    def read_file(self, path: str) -> Optional[bytes]:
        p = Path(path)
        if not p.is_file():
            return None
        with p.open("rb") as f:
            return f.read()

    def open_file(self, path: str) -> Optional[ArchiveLike]:
        """打开文件返回 FArchive（支持 mmap 大文件）。"""
        p = Path(path)
        if not p.is_file():
            return None
        return FArchive(str(p))

    def open_package_bundle(self, path: str, tolerant: bool = False) -> PackageBundle:
        main = Path(path)
        if self.root is not None and not main.is_file() and not main.is_absolute():
            root_relative = self.root / main
            if root_relative.is_file():
                main = root_relative
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
) -> PackageBundle:
    """Discover a package bundle from a filesystem path or provider path."""

    if provider is not None:
        return provider.open_package_bundle(path, tolerant=tolerant)
    return FileSystemPackageProvider().open_package_bundle(path, tolerant=tolerant)


def _normalize_ext(extension: str) -> str:
    return extension if extension.startswith(".") else f".{extension}"

