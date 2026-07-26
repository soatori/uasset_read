"""
PakFileReader -- Main .pak file reader

Similar to PakFileReader.cs, provides:
- open/close + context manager
- list_files / get_entry / extract
- Automatic FPakInfo detection, index decryption, entry parsing, decompression
"""
import logging
from pathlib import PurePosixPath
from typing import BinaryIO

from uasset_read.exceptions import ParseError
from uasset_read.pak.structures import FPakInfo, FPakEntry
from uasset_read.pak.index import parse_primary_index
from uasset_read.pak.decompress import decompress_entry

logger = logging.getLogger(__name__)


class PakFileReader:
    """.pak file main reader.

    Usage:
        reader = PakFileReader("game.pak")
        info = reader.info  # FPakInfo
        entries = reader.entries  # dict[path, FPakEntry]
        files = reader.list_files()  # list[str]
        data = reader.extract("path/to/file.txt")  # bytes
    """

    def __init__(
        self,
        path: str,
        aes_key: bytes | None = None,
        tolerant: bool = False,
    ):
        self._path = path
        self._aes_key = aes_key
        self._tolerant = tolerant
        self._file: BinaryIO | None = None
        self._file_size: int = 0
        self._info: FPakInfo | None = None
        self._entries: dict[str, FPakEntry] = {}
        self._mount_point: str = ""
        self._directory_index: dict = {}
        self._encoded_entries: list[FPakEntry] = []
        self._path_hash_seed: int = 0
        self._path_hash_index: dict[int, tuple[int, int]] = {}

    def open(self) -> None:
        """Open .pak file and parse FPakInfo + Primary Index."""
        logger.debug("Opening pak file: %s", self._path)

        try:
            self._file = open(self._path, 'rb')
            self._file.seek(0, 2)
            self._file_size = self._file.tell()
            self._file.seek(0)

            # Read FPakInfo
            self._info = FPakInfo.deserialize(self._file, self._file_size)
            logger.debug("Detected FPakInfo version=%d, index_offset=%d, index_size=%d",
                         self._info.version, self._info.index_offset, self._info.index_size)

            # Parse primary index
            mount_point, entries, extra = parse_primary_index(
                self._file, self._info, self._aes_key
            )

            self._mount_point = mount_point
            self._entries = entries

            # Extract v10+ extra info
            if extra:
                self._directory_index = extra.get("directory_index", {})
                self._encoded_entries = extra.get("encoded_entries", [])
                self._path_hash_seed = extra.get("path_hash_seed", 0)
                self._path_hash_index = extra.get("path_hash_index", {})

            logger.debug("PakFileReader: %d entries, mount_point='%s'",
                         len(self._entries), self._mount_point)
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        """Close the file handle."""
        if self._file:
            self._file.close()
            self._file = None

    def __del__(self) -> None:
        """Safety net: ensure the file handle is released."""
        try:
            self.close()
        except Exception:
            logger.debug("PakFileReader.__del__ cleanup failed", exc_info=True)

    def __enter__(self) -> "PakFileReader":
        self.open()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @property
    def info(self) -> FPakInfo | None:
        """Parsed FPakInfo (None if not opened)."""
        return self._info

    @property
    def entries(self) -> dict[str, FPakEntry]:
        """path -> FPakEntry mapping."""
        return self._entries

    @property
    def mount_point(self) -> str:
        """Mount point from the Primary Index."""
        return self._mount_point

    def list_files(self) -> list[str]:
        """Return a list of paths for all non-deleted entries."""
        return [p for p, e in self._entries.items() if not e.is_deleted]

    def get_entry(self, path: str) -> FPakEntry | None:
        """Get the FPakEntry for a given path, or None if not found."""
        resolved = self._resolve_entry_path(path)
        return self._entries.get(resolved) if resolved is not None else None

    def extract(self, path: str) -> bytes | None:
        """Extract file entry byte data (decompressed).

        Args:
            path: File path within the pak

        Returns:
            Decompressed byte data, or None if path not found

        Raises:
            ParseError: Entry is deleted or offset is invalid
        """
        resolved = self._resolve_entry_path(path)
        entry = self._entries.get(resolved) if resolved is not None else None
        if entry is None:
            return None

        if entry.is_deleted:
            raise ParseError(f"Entry is deleted: {resolved}")

        if self._file is None:
            raise ParseError("PakFileReader not opened — call open() first")

        # Validate offset bounds
        read_offset = entry.offset
        if read_offset < 0 or read_offset >= self._file_size:
            raise ParseError(
                f"Entry offset {read_offset} out of bounds (file size: {self._file_size})"
            )

        compression_method = self._get_compression_method(entry)

        self._file.seek(read_offset)
        return decompress_entry(
            self._file, entry,
            compression_method=compression_method,
            encryption_key=self._aes_key if entry.is_encrypted else None,
        )

    def _resolve_entry_path(self, path: str) -> str | None:
        """Resolve full, mount-relative, case-insensitive, and stem paths."""
        normalized = path.replace("\\", "/").strip("/")

        # Path traversal protection: reject path components containing ".."
        normalized_parts = PurePosixPath(normalized).parts
        if ".." in normalized_parts:
            logger.warning("Path traversal attempt rejected: %r", path)
            return None

        # Verify resolved path does not escape mount_point boundary
        if self._mount_point:
            # Use "/" replace instead of os.path.join to keep cross-platform consistency
            resolved = PurePosixPath(self._mount_point) / normalized
            resolved_str = resolved.as_posix()
            mount_str = self._mount_point.replace("\\", "/").strip("/")
            if not resolved_str.startswith(mount_str + "/") and resolved_str != mount_str:
                logger.warning("Path escaping mount_point boundary rejected: %r (mount_point=%r)",
                               path, self._mount_point)
                return None

        if path in self._entries:
            return path

        if normalized in self._entries:
            return normalized

        candidates = [normalized]
        if "." not in normalized.rsplit("/", 1)[-1]:
            candidates.extend(
                f"{normalized}{suffix}" for suffix in (".uasset", ".uexp", ".ubulk", ".umap")
            )

        lowered_candidates = [candidate.lower() for candidate in candidates]
        for entry_path in self._entries:
            lowered = entry_path.lower().strip("/")
            for candidate in lowered_candidates:
                if lowered == candidate or lowered.endswith(f"/{candidate}"):
                    return entry_path
        return None

    def _get_compression_method(self, entry: FPakEntry) -> str:
        if entry.compression_method_index == 0:
            return "None"

        if self._info and self._info.compression_methods:
            method_index = entry.compression_method_index - 1
            if 0 <= method_index < len(self._info.compression_methods):
                return self._info.compression_methods[method_index]
            raise ParseError(
                "Compression method index "
                f"{entry.compression_method_index} out of range "
                f"(methods: {len(self._info.compression_methods)})"
            )

        return "Zlib"
