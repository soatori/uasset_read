"""Read-only IoStore container index (``.utoc``) parser.

Parses the Table Of Contents so a container's chunks and the file names that address them
become enumerable. It reads *no* ``.ucas`` bytes and decompresses nothing: chunk extraction is
a separate slice (#621 Phase 5), and this module stops at "which chunks exist, where they
start, which names point at them".

Layout authority (UE 5.8 sources, paths relative to the engine root):

- ``Engine/Source/Runtime/Core/Internal/IO/IoStore.h``
  ``FIoStoreTocHeader`` (magic ``-==--==--==--==--``, 144 bytes), ``FIoStoreTocEntryMeta``,
  ``FIoStoreTocCompressedBlockEntry`` (12 bytes), ``EIoStoreTocVersion``.
- ``Engine/Source/Runtime/Core/Private/IO/IoStore.cpp:1274-1420``
  ``FIoStoreTocResourceView::Read`` fixes the on-disk order after the header and the version /
  flag gates: perfect-hash arrays from ``PerfectHash``/``PerfectHashWithOverflow``, signature
  block when ``Signed``, directory index when ``Indexed``, entry metas last.
- ``Engine/Source/Runtime/Core/Internal/IO/IoOffsetLength.h``
  ``FIoOffsetAndLength`` is two *big-endian* 5-byte fields: offset first, then length.
- ``Engine/Source/Runtime/Core/Public/IO/IoChunkId.h:27-44,132``
  ``EIoChunkType`` and ``GetChunkType() == Id[11]``.
- ``Engine/Source/Runtime/Core/Public/IO/IoDispatcher.h:435-444`` ``EIoContainerFlags``.
- ``Engine/Source/Runtime/Core/Private/IO/IoDirectoryIndex.cpp:135-161,407-442``
  ``FIoDirectoryIndexResource`` serialises ``MountPoint``, directory entries (4 x uint32), file
  entries (3 x uint32) and a string table; ``IterateDirectoryIndex`` yields
  ``MountPoint + Path + Name`` with ``FileEntry.UserData`` carrying the TOC entry index.

Entry metas are version-dependent, not one width: from
``EIoStoreTocVersion::ReplaceIoChunkHashWithIoHash`` (8) the entry is ``FIoStoreTocEntryMeta``
(20-byte ``FIoHash`` + flags + 3 pad = 24 bytes); before it ``FIoStoreTocEntryMetaOld`` is
``uint8 ChunkHash[32]`` + flags = 33 bytes, of which UE copies the first 20
(``IoStore.cpp:1405-1434``). Both widths are handled here; ``hash`` always carries 20 bytes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

TOC_MAGIC = b"-==--==--==--==-"  # FIoStoreTocHeader::TocMagicImg (IoStore.h:48)
TOC_HEADER_SIZE = 144
COMPRESSED_BLOCK_ENTRY_SIZE = 12
CHUNK_ID_SIZE = 12
CHUNK_META_SIZE = 24  # FIoStoreTocEntryMeta from TOC version 8
CHUNK_META_SIZE_LEGACY = 33  # FIoStoreTocEntryMetaOld (uint8[32] + flags) before version 8
CHUNK_HASH_SIZE = 20
OFFSET_LENGTH_SIZE = 10
DIRECTORY_ENTRY_SIZE = 16
FILE_ENTRY_SIZE = 12

TOC_VERSION_MIN = 2  # EIoStoreTocVersion::DirectoryIndex (IoStore.h:27-41)
TOC_VERSION_MAX = 8  # EIoStoreTocVersion::ReplaceIoChunkHashWithIoHash
VERSION_PERFECT_HASH = 4
VERSION_PERFECT_HASH_OVERFLOW = 5
VERSION_IOHASH_METAS = 8

# EIoContainerFlags (IoDispatcher.h:435-444).
FLAG_COMPRESSED = 1 << 0
FLAG_ENCRYPTED = 1 << 1
FLAG_SIGNED = 1 << 2
FLAG_INDEXED = 1 << 3
FLAG_ON_DEMAND = 1 << 4

_FLAG_NAMES = {
    FLAG_COMPRESSED: "Compressed",
    FLAG_ENCRYPTED: "Encrypted",
    FLAG_SIGNED: "Signed",
    FLAG_INDEXED: "Indexed",
    FLAG_ON_DEMAND: "OnDemand",
}

META_COMPRESSED = 1 << 0  # FIoStoreTocEntryMetaFlags (IoStore.h:81-85)
META_MEMORY_MAPPED = 1 << 1

# EIoChunkType (IoChunkId.h:27-44). Unlisted numbers stay numeric rather than being
# coerced onto a nearby name.
CHUNK_TYPES = {
    1: "ExportBundleData",
    2: "BulkData",
    3: "OptionalBulkData",
    4: "MemoryMappedBulkData",
    5: "ScriptObjects",
    6: "ContainerHeader",
    7: "ExternalFile",
    8: "ShaderCodeLibrary",
    9: "ShaderCode",
    10: "PackageStoreEntry",
    11: "DerivedData",
    12: "EditorDerivedData",
    13: "PackageResource",
}

_NO_ENTRY = 0xFFFFFFFF
_MAX_ARRAY_BYTES = 512 * 1024 * 1024
_MAX_ENTRIES = 10_000_000


class IoStoreTocError(Exception):
    """The TOC is malformed, unsupported, or asserts a count it cannot honour."""


@dataclass(frozen=True)
class IoStoreChunk:
    """One TOC entry: where the chunk lives and how it is described."""

    index: int
    chunk_id: bytes
    type_id: int
    offset: int
    length: int
    hash: bytes
    meta_flags: int

    @property
    def type_name(self) -> str:
        return CHUNK_TYPES.get(self.type_id, f"Unknown({self.type_id})")

    @property
    def compressed(self) -> bool:
        return bool(self.meta_flags & META_COMPRESSED)

    @property
    def memory_mapped(self) -> bool:
        return bool(self.meta_flags & META_MEMORY_MAPPED)


@dataclass(frozen=True)
class IoStoreBlock:
    """One ``FIoStoreTocCompressedBlockEntry``: where a chunk's bytes physically sit.

    A TOC entry's ``offset``/``length`` are the *logical* (uncompressed) range, so on a
    compressed container they can exceed the ``.ucas`` size. The physical mapping is this
    block table (``IoStore.h:102-160``: 40-bit LE offset, 24-bit compressed size, 24-bit
    uncompressed size, 8-bit method index, packed into 12 bytes).
    """

    offset: int
    compressed_size: int
    uncompressed_size: int
    method_index: int


@dataclass(frozen=True)
class IoStoreFile:
    """A directory-index name bound to the TOC entry that holds its data."""

    path: str
    chunk_index: int


@dataclass(frozen=True)
class IoStoreToc:
    """Parsed ``.utoc`` index. ``data_path`` is the sibling ``.ucas`` when one is on disk."""

    path: str
    version: int
    header_size: int
    entry_count: int
    compression_block_count: int
    compression_block_size: int
    compression_methods: tuple[str, ...]
    container_flags: int
    container_id: int
    encryption_key_guid: str
    partition_count: int
    partition_size: int
    perfect_hash_seed_count: int
    chunks_without_perfect_hash_count: int
    directory_index_size: int
    mount_point: str
    chunks: tuple[IoStoreChunk, ...]
    blocks: tuple[IoStoreBlock, ...]
    files: tuple[IoStoreFile, ...]
    data_path: str | None

    @property
    def physical_bytes(self) -> int:
        """Bytes the block table claims on disk."""
        return sum(b.compressed_size for b in self.blocks)

    @property
    def flag_names(self) -> tuple[str, ...]:
        return tuple(name for bit, name in _FLAG_NAMES.items() if self.container_flags & bit)

    @property
    def encrypted(self) -> bool:
        return bool(self.container_flags & FLAG_ENCRYPTED)

    @property
    def signed(self) -> bool:
        return bool(self.container_flags & FLAG_SIGNED)

    def chunks_of_type(self, type_name: str) -> tuple[IoStoreChunk, ...]:
        return tuple(c for c in self.chunks if c.type_name == type_name)

    @property
    def package_chunks(self) -> tuple[IoStoreChunk, ...]:
        """ExportBundle chunks: one per cooked (Zen) package in the container."""
        return self.chunks_of_type("ExportBundleData")

    def files_for(self, chunk_index: int) -> tuple[IoStoreFile, ...]:
        return tuple(f for f in self.files if f.chunk_index == chunk_index)

    def package_files(self) -> tuple[IoStoreFile, ...]:
        """Directory-index names that address an ExportBundle chunk (i.e. packages)."""
        bundles = {c.index for c in self.package_chunks}
        return tuple(f for f in self.files if f.chunk_index in bundles)


def _array_count(blob: bytes, pos: int, element_size: int, what: str, limit: int) -> int:
    if pos + 4 > limit:
        raise IoStoreTocError(f"{what} count runs past the directory index")
    (count,) = struct.unpack_from("<i", blob, pos)
    if count < 0 or count * element_size > limit - pos - 4:
        raise IoStoreTocError(f"{what} count {count} escapes the directory index")
    return count


def _read_fstring(blob: bytes, pos: int, limit: int) -> tuple[str, int]:
    """FString: int32 length; >0 ANSI with the NUL counted, <0 UTF-16 with the NUL counted."""
    if pos + 4 > limit:
        raise IoStoreTocError("truncated FString in directory index")
    (n,) = struct.unpack_from("<i", blob, pos)
    pos += 4
    if n == 0:
        return "", pos
    if n > 0:
        end = pos + n
        if end > limit:
            raise IoStoreTocError("directory index FString length escapes the buffer")
        return blob[pos:end].split(b"\x00", 1)[0].decode("utf-8", "replace"), end
    end = pos + (-n) * 2
    if end > limit:
        raise IoStoreTocError("directory index UTF-16 FString length escapes the buffer")
    return blob[pos:end].decode("utf-16-le", "replace").rstrip("\x00"), end


def _parse_directory_index(blob: bytes) -> tuple[str, tuple[IoStoreFile, ...]]:
    """Walk ``FIoDirectoryIndexResource`` the way ``IterateDirectoryIndex`` does."""
    limit = len(blob)
    mount, pos = _read_fstring(blob, 0, limit)

    dir_count = _array_count(blob, pos, DIRECTORY_ENTRY_SIZE, "directory entry", limit)
    pos += 4
    dirs = [struct.unpack_from("<4I", blob, pos + i * DIRECTORY_ENTRY_SIZE) for i in range(dir_count)]
    pos += dir_count * DIRECTORY_ENTRY_SIZE

    file_count = _array_count(blob, pos, FILE_ENTRY_SIZE, "file entry", limit)
    pos += 4
    files = [struct.unpack_from("<3I", blob, pos + i * FILE_ENTRY_SIZE) for i in range(file_count)]
    pos += file_count * FILE_ENTRY_SIZE

    str_count = _array_count(blob, pos, 4, "string table", limit)
    pos += 4
    strings: list[str] = []
    for _ in range(str_count):
        value, pos = _read_fstring(blob, pos, limit)
        strings.append(value)

    def name(index: object) -> str:
        if index == _NO_ENTRY:
            return ""
        if not isinstance(index, int) or not 0 <= index < len(strings):
            raise IoStoreTocError(f"directory index string reference {index!r} out of range")
        return strings[index]

    out: list[IoStoreFile] = []

    def walk(directory: int, prefix: str) -> None:
        if not 0 <= directory < len(dirs):
            raise IoStoreTocError(f"directory entry index {directory} out of range")
        _, first_child, _, first_file = dirs[directory]
        steps = 0
        file = first_file
        while file != _NO_ENTRY:
            if not 0 <= file < len(files):
                raise IoStoreTocError(f"file entry index {file} out of range")
            entry_name, next_file, user_data = files[file]
            out.append(IoStoreFile(f"{mount}{prefix}{name(entry_name)}", user_data))
            file = next_file
            steps += 1
            if steps > len(files):  # a malformed sibling chain must not spin forever
                raise IoStoreTocError("file sibling chain cycles in the directory index")
        steps = 0
        child = first_child
        while child != _NO_ENTRY:
            child_name, _, next_sibling, _ = dirs[child]
            walk(child, f"{prefix}{name(child_name)}/")
            child = next_sibling
            steps += 1
            if steps > len(dirs):
                raise IoStoreTocError("directory sibling chain cycles in the directory index")

    if dirs:
        walk(0, "")
    return mount, tuple(out)


def read_toc(path: str | Path) -> IoStoreToc:
    """Parse a ``.utoc`` index. Raises ``IoStoreTocError`` instead of guessing on damage."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise IoStoreTocError(f"{path}: cannot read TOC ({exc.strerror})") from exc
    size = len(data)
    if size < TOC_HEADER_SIZE:
        raise IoStoreTocError(f"{path.name}: {size} bytes is smaller than a TOC header")
    if data[:16] != TOC_MAGIC:
        raise IoStoreTocError(f"{path.name}: not an IoStore TOC (magic {data[:16]!r})")

    (
        version,
        _reserved0,
        _reserved1,
        header_size,
        entry_count,
        block_count,
        block_entry_size,
        method_count,
        method_name_length,
        compression_block_size,
        directory_index_size,
        partition_count,
    ) = struct.unpack_from("<BBH" + "I" * 9, data, 16)
    container_id = struct.unpack_from("<Q", data, 56)[0]
    encryption_key_guid = data[64:80].hex()
    (container_flags,) = struct.unpack_from("<B", data, 80)
    perfect_hash_seeds = struct.unpack_from("<I", data, 84)[0]
    partition_size = struct.unpack_from("<Q", data, 88)[0]
    chunks_without_perfect_hash = struct.unpack_from("<I", data, 96)[0]

    if header_size != TOC_HEADER_SIZE:
        raise IoStoreTocError(f"{path.name}: header size {header_size} != sizeof(FIoStoreTocHeader)")
    if not TOC_VERSION_MIN <= version <= TOC_VERSION_MAX:
        raise IoStoreTocError(f"{path.name}: unsupported TOC version {version}")
    if block_entry_size != COMPRESSED_BLOCK_ENTRY_SIZE:
        raise IoStoreTocError(f"{path.name}: block entry size {block_entry_size} != 12")
    if method_name_length <= 0 or method_count > 64 or entry_count > _MAX_ENTRIES:
        raise IoStoreTocError(f"{path.name}: implausible method/entry table {method_count}x{method_name_length}")
    if container_flags & FLAG_SIGNED:
        raise IoStoreTocError(f"{path.name}: signed container; signature key validation is not implemented")
    if container_flags & FLAG_ENCRYPTED:
        raise IoStoreTocError(f"{path.name}: encrypted container (guid {encryption_key_guid}); no key support")

    # Order of the arrays after the header, per FIoStoreTocResourceView::Read.
    spans: list[tuple[str, int]] = [("chunk ids", entry_count * CHUNK_ID_SIZE)]
    spans.append(("chunk offset/length", entry_count * OFFSET_LENGTH_SIZE))
    if version >= VERSION_PERFECT_HASH:
        spans.append(("perfect hash seeds", perfect_hash_seeds * 4))
    if version >= VERSION_PERFECT_HASH_OVERFLOW:
        spans.append(("chunks without perfect hash", chunks_without_perfect_hash * 4))
    spans.append(("compression blocks", block_count * COMPRESSED_BLOCK_ENTRY_SIZE))
    spans.append(("compression method names", method_count * method_name_length))
    spans.append(("directory index", directory_index_size))
    meta_size = CHUNK_META_SIZE if version >= VERSION_IOHASH_METAS else CHUNK_META_SIZE_LEGACY
    spans.append(("chunk metas", entry_count * meta_size))
    total = TOC_HEADER_SIZE
    for label, needed in spans:
        if needed > _MAX_ARRAY_BYTES:
            raise IoStoreTocError(f"{path.name}: {label} claims {needed} bytes")
        total += needed
    if total != size:
        raise IoStoreTocError(f"{path.name}: TOC layout needs {total} bytes but the file holds {size}")

    pos = TOC_HEADER_SIZE
    chunk_ids = [data[pos + i * CHUNK_ID_SIZE : pos + (i + 1) * CHUNK_ID_SIZE] for i in range(entry_count)]
    pos += entry_count * CHUNK_ID_SIZE
    offset_lengths = [
        data[pos + i * OFFSET_LENGTH_SIZE : pos + (i + 1) * OFFSET_LENGTH_SIZE] for i in range(entry_count)
    ]
    pos += entry_count * OFFSET_LENGTH_SIZE
    pos += perfect_hash_seeds * 4 + chunks_without_perfect_hash * 4
    block_start = pos
    pos += block_count * COMPRESSED_BLOCK_ENTRY_SIZE
    blocks = []
    for i in range(block_count):
        raw = data[block_start + i * COMPRESSED_BLOCK_ENTRY_SIZE : block_start + (i + 1) * COMPRESSED_BLOCK_ENTRY_SIZE]
        word1 = struct.unpack_from("<I", raw, 4)[0]
        word2 = struct.unpack_from("<I", raw, 8)[0]
        blocks.append(
            IoStoreBlock(
                offset=struct.unpack_from("<Q", raw, 0)[0] & ((1 << 40) - 1),
                compressed_size=(word1 >> 8) & ((1 << 24) - 1),
                uncompressed_size=word2 & ((1 << 24) - 1),
                method_index=word2 >> 24,
            )
        )
    stored_methods = [
        data[pos + i * method_name_length : pos + (i + 1) * method_name_length].split(b"\x00", 1)[0]
        for i in range(method_count)
    ]
    # UE's method table reserves index 0 for NAME_None and stores the names from index 1
    # (IoStore.cpp:1355-1365), so "None" is re-added here for caller-facing indices.
    methods = ("None",) + tuple(m.decode("ascii", "replace") for m in stored_methods if m and m != b"None")
    pos += method_count * method_name_length
    directory_start = pos
    pos += directory_index_size
    metas = [
        (
            data[pos + i * meta_size : pos + i * meta_size + CHUNK_HASH_SIZE],
            data[pos + i * meta_size + (CHUNK_HASH_SIZE if version >= VERSION_IOHASH_METAS else 32)],
        )
        for i in range(entry_count)
    ]

    chunks = []
    for i in range(entry_count):
        ol = offset_lengths[i]
        chunk_id = chunk_ids[i]
        hash_bytes, meta_flags = metas[i]
        chunks.append(
            IoStoreChunk(
                index=i,
                chunk_id=chunk_id,
                type_id=chunk_id[11],  # FIoChunkId::GetChunkType() (IoChunkId.h:132)
                # FIoOffsetAndLength: two big-endian 5-byte fields (IoOffsetLength.h).
                offset=int.from_bytes(ol[:5], "big"),
                length=int.from_bytes(ol[5:], "big"),
                hash=hash_bytes,
                meta_flags=meta_flags & (META_COMPRESSED | META_MEMORY_MAPPED),
            )
        )

    mount_point = ""
    files: tuple[IoStoreFile, ...] = ()
    if directory_index_size:
        if not container_flags & FLAG_INDEXED:
            raise IoStoreTocError(f"{path.name}: directory index present without the Indexed flag")
        mount_point, files = _parse_directory_index(data[directory_start : directory_start + directory_index_size])
        for entry in files:
            if not 0 <= entry.chunk_index < entry_count:
                raise IoStoreTocError(f"{path.name}: file {entry.path!r} points at TOC entry {entry.chunk_index}")

    stem = path.name[: -len(".utoc")] if path.name.endswith(".utoc") else path.stem
    sibling = path.with_name(stem + ".ucas")
    return IoStoreToc(
        path=str(path),
        version=version,
        header_size=header_size,
        entry_count=entry_count,
        compression_block_count=block_count,
        compression_block_size=compression_block_size,
        compression_methods=methods,
        container_flags=container_flags,
        container_id=container_id,
        encryption_key_guid=encryption_key_guid,
        partition_count=partition_count,
        partition_size=partition_size,
        perfect_hash_seed_count=perfect_hash_seeds,
        chunks_without_perfect_hash_count=chunks_without_perfect_hash,
        directory_index_size=directory_index_size,
        mount_point=mount_point,
        chunks=tuple(chunks),
        blocks=tuple(blocks),
        files=files,
        data_path=str(sibling) if sibling.exists() else None,
    )


__all__ = ["IoStoreBlock", "IoStoreChunk", "IoStoreFile", "IoStoreToc", "IoStoreTocError", "read_toc"]
