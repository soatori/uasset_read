"""
PakFileReader — .pak 文件主读取器

类似 的 PakFileReader.cs，提供：
- open/close + 上下文管理器
- list_files / get_entry / extract
- 自动处理 FPakInfo 检测、索引解密、条目解析、解压缩
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
    """.pak 文件主读取器。

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
        """打开 .pak 文件并解析 FPakInfo + Primary Index。"""
        logger.debug("Opening pak file: %s", self._path)

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

    def close(self) -> None:
        """关闭文件句柄。"""
        if self._file:
            self._file.close()
            self._file = None

    def __enter__(self) -> "PakFileReader":
        self.open()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @property
    def info(self) -> FPakInfo | None:
        """已解析的 FPakInfo（未打开时为 None）。"""
        return self._info

    @property
    def entries(self) -> dict[str, FPakEntry]:
        """path -> FPakEntry 映射。"""
        return self._entries

    @property
    def mount_point(self) -> str:
        """Primary Index 中的挂载点。"""
        return self._mount_point

    def list_files(self) -> list[str]:
        """返回所有非删除条目的路径列表。"""
        return [p for p, e in self._entries.items() if not e.is_deleted]

    def get_entry(self, path: str) -> FPakEntry | None:
        """获取指定路径的 FPakEntry，找不到返回 None。"""
        resolved = self._resolve_entry_path(path)
        return self._entries.get(resolved) if resolved is not None else None

    def extract(self, path: str) -> bytes | None:
        """提取文件条目的字节数据（解压缩）。

        Args:
            path: 文件在 pak 中的路径

        Returns:
            解压后的字节数据，找不到路径时返回 None

        Raises:
            ParseError: 条目已删除或偏移无效
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

        # 路径遍历防护：拒绝包含 ".." 的路径组件
        normalized_parts = PurePosixPath(normalized).parts
        if ".." in normalized_parts:
            logger.warning("路径遍历尝试被拒绝: %r", path)
            return None

        # 验证解析后的路径不会逃逸 mount_point 边界
        if self._mount_point:
            # 使用 "/" 的 replace 而非 os.path.join 保持跨平台一致
            resolved = PurePosixPath(self._mount_point) / normalized
            resolved_str = resolved.as_posix()
            mount_str = self._mount_point.replace("\\", "/").strip("/")
            if not resolved_str.startswith(mount_str + "/") and resolved_str != mount_str:
                logger.warning("路径逃逸 mount_point 边界被拒绝: %r (mount_point=%r)",
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
