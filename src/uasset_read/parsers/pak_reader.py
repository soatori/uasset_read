"""Read-only traditional Pak (``.pak``) index reader.

Parses the trailing ``FPakInfo`` footer and the file index so a pak's contained
files become enumerable, and serves plain (uncompressed, unencrypted) entry
payloads by range. It never decompresses or decrypts: compression and
encryption are *capability-reported* as unavailable via the same
``Capability`` protocol shape ``uasset_read.containers`` uses for IoStore.
Shared protocol only — the trust path is deliberately separate (D-PAK): every
pak index blob (primary and each secondary) is SHA-1 validated against the
hash stored beside its own footer span before it is trusted, whereas the
IoStore TOC carries no per-blob hash.

Layout authority (UE 5.8 sources, paths relative to the engine root):

- ``Engine/Source/Runtime/PakFile/Public/IPlatformFilePak.h:147-366``
  ``FPakInfo``: magic ``PakFile_Magic = 0x5A6F12E1``; version enum 1-12
  (``PakFile_Version_FrozenIndex`` = 9 is unsupported, UE fatals on it);
  serialized order is EncryptionKeyGuid (v7+), bEncryptedIndex, Magic,
  Version, IndexOffset, IndexSize, IndexHash, [bIndexIsFrozen, v9 only],
  then for v8+ five 32-byte compression method slots.
- same header ``FPakEntry`` (:405) / ``FPakCompressedBlock`` (:368):
  Offset, Size, UncompressedSize, [Timestamp, v1 only], Hash[20],
  CompressionMethodIndex, [CompressionBlocks int32 count + N x 2 int64,
  only when method != 0 and v3+], Flags, CompressionBlockSize (v3+).
  ``Flag_Encrypted = 0x01``, ``Flag_Deleted = 0x02``.
- same header ``FPakEntryLocation`` (:609): int32; 0..0x7FFFFFFE is an offset
  into EncodedPakEntries, -1..-0x7FFFFFFF is a Files-list index
  (``-(Index + 1)``), 0x7FFFFFFF and 0x80000000 are invalid.
- ``Engine/Source/Runtime/PakFile/Private/PakFile.cpp:272-345``
  ``FPakFile::Initialize`` probes footer serialized sizes per version from EOF.
- ``PakFile.cpp:404-700`` ``LoadIndexInternal``: primary index is MountPoint,
  NumEntries, PathHashSeed, path-hash span, full-directory span,
  EncodedPakEntries, then the non-encodable ``FPakEntry`` list; each secondary
  index is hashed (and optionally decrypted) individually.
- ``PakFile.cpp:700-779`` ``LoadIndexInternal_DirectoryIndex``: directory map;
  file names serialize as FUtf8String from ``PakFile_Version_Utf8PakDirectory``
  (12), FString before it. Full paths are ``MountPoint + DirectoryName + FileName``.
- ``PakFile.cpp:782-890`` ``LoadLegacyIndex``: versions < 10 store
  MountPoint, NumEntries, then ``(Filename, FPakEntry)`` pairs.
- ``PakFile.cpp:1594-1865`` ``EncodePakEntry`` / ``DecodePakEntry``: the
  bit-packed encoded entry layout used by EncodedPakEntries.
- ``Engine/Source/Developer/PakFileUtilities/Private/PakFileUtilities.cpp:3180-3255``
  the on-disk write order of primary + secondary index blobs and the footer.

Scope: index mechanics only. No redistributable ``.pak`` fixture exists yet
(#625 closed without one), so the tests are synthetic bytes and make no
real-asset support claims. This module is a standalone reader capability: it
is not wired into the public package document output or projection.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, replace
from pathlib import Path

from uasset_read.containers import Capability
from uasset_read.exceptions import ParseError
from uasset_read.sources import FileSource

PAK_MAGIC = 0x5A6F12E1  # FPakInfo::PakFile_Magic (IPlatformFilePak.h:150)

VERSION_INITIAL = 1
VERSION_COMPRESSION_ENCRYPTION = 3
VERSION_INDEX_ENCRYPTION = 4
VERSION_ENCRYPTION_KEY_GUID = 7
VERSION_FNAME_COMPRESSION_METHOD = 8
VERSION_FROZEN_INDEX = 9  # unsupported: UE fatals, "Regenerate Paks"
VERSION_PATH_HASH_INDEX = 10
VERSION_UTF8_PAK_DIRECTORY = 12
VERSION_LATEST = VERSION_UTF8_PAK_DIRECTORY

_FLAG_ENCRYPTED = 0x01  # FPakEntry::Flag_Encrypted
_FLAG_DELETED = 0x02  # FPakEntry::Flag_Deleted

_COMPRESSION_METHOD_NAME_LEN = 32  # FPakInfo::CompressionMethodNameLen
_MAX_COMPRESSION_METHODS = 5  # FPakInfo::MaxNumCompressionMethods
_MAX_INDEX_BYTES = 512 * 1024 * 1024
_MAX_ENTRIES = 10_000_000
_MAX_STRING_CHARS = 65536
_LOCATION_INVALID = -(1 << 31)  # FPakEntryLocation::Invalid (MIN_int32)
_LOCATION_MAX_INDEX = (1 << 31) - 2  # FPakEntryLocation::MaxIndex

# Pre-v8 paks index methods implicitly (FPakInfo::Serialize < v8 branch):
# None, Zlib, Gzip, Oodle.
_LEGACY_METHODS = ("None", "Zlib", "Gzip", "Oodle")


class PakError(Exception):
    """The pak is malformed, encrypted, or asserts an index it cannot honour."""


@dataclass(frozen=True)
class PakEntry:
    """One contained file: where its payload lives and how it is described."""

    path: str
    offset: int  # absolute pak offset of the serialized FPakEntry header
    size: int  # stored payload size (compressed when compressed)
    uncompressed_size: int
    compression_method_index: int
    compression_method: str | None
    compression_block_size: int
    flags: int
    payload_offset: int  # absolute offset of the payload bytes (header + offset)

    @property
    def encrypted(self) -> bool:
        return bool(self.flags & _FLAG_ENCRYPTED)

    @property
    def deleted(self) -> bool:
        return bool(self.flags & _FLAG_DELETED)

    @property
    def compressed(self) -> bool:
        return self.compression_method_index != 0


@dataclass(frozen=True)
class PakIndex:
    """Parsed pak footer + index. ``files`` lists non-deleted entries."""

    path: str
    version: int
    mount_point: str
    num_entries: int
    index_offset: int
    index_size: int
    index_encrypted: bool
    encryption_key_guid: str
    compression_methods: tuple[str, ...]
    files: tuple[PakEntry, ...]

    @property
    def capabilities(self) -> dict[str, Capability]:
        """Capability protocol shared with ``uasset_read.containers``."""
        return {
            "toc_entries": "available",
            "entry_bytes": "available",
            "compression": "unavailable",
            "encryption": "unavailable",
        }


class _Cursor:
    """Bounds-checked little-endian cursor over one in-memory index blob."""

    def __init__(self, blob: bytes, label: str, pos: int = 0):
        if pos < 0 or pos > len(blob):
            raise PakError(f"{label}: start offset {pos} escapes the {len(blob)}-byte blob")
        self._blob = blob
        self._pos = pos
        self._label = label

    @property
    def pos(self) -> int:
        return self._pos

    def _need(self, n: int) -> None:
        if n < 0 or self._pos + n > len(self._blob):
            raise PakError(f"{self._label}: truncated at offset {self._pos} (need {n} bytes)")

    def u8(self) -> int:
        self._need(1)
        value = self._blob[self._pos]
        self._pos += 1
        return value

    def i32(self) -> int:
        self._need(4)
        (value,) = struct.unpack_from("<i", self._blob, self._pos)
        self._pos += 4
        return value

    def u32(self) -> int:
        self._need(4)
        (value,) = struct.unpack_from("<I", self._blob, self._pos)
        self._pos += 4
        return value

    def i64(self) -> int:
        self._need(8)
        (value,) = struct.unpack_from("<q", self._blob, self._pos)
        self._pos += 8
        return value

    def u64(self) -> int:
        self._need(8)
        (value,) = struct.unpack_from("<Q", self._blob, self._pos)
        self._pos += 8
        return value

    def raw(self, n: int) -> bytes:
        self._need(n)
        value = self._blob[self._pos : self._pos + n]
        self._pos += n
        return value

    def count(self, what: str, limit: int = _MAX_ENTRIES) -> int:
        n = self.i32()
        if n < 0 or n > limit:
            raise PakError(f"{self._label}: {what} count {n} escapes the index")
        return n

    def fstring(self) -> str:
        """FString: int32 length; >0 ANSI with the NUL counted, <0 UTF-16-LE with the NUL counted."""
        n = self.i32()
        if n == 0:
            return ""
        if n > _MAX_STRING_CHARS:
            raise PakError(f"{self._label}: FString length {n} exceeds {_MAX_STRING_CHARS} chars")
        if n > 0:
            return self.raw(n).split(b"\x00", 1)[0].decode("utf-8", "replace")
        units = -n
        if units > _MAX_STRING_CHARS:
            raise PakError(f"{self._label}: UTF-16 FString length {units} exceeds {_MAX_STRING_CHARS} chars")
        return self.raw(units * 2).decode("utf-16-le", "replace").rstrip("\x00")

    def utf8string(self) -> str:
        """FUtf8String: int32 positive length with the NUL counted, then UTF-8 bytes."""
        n = self.i32()
        if n == 0:
            return ""
        if n > _MAX_STRING_CHARS:
            raise PakError(f"{self._label}: FUtf8String length {n} exceeds {_MAX_STRING_CHARS} chars")
        return self.raw(n).split(b"\x00", 1)[0].decode("utf-8", "replace")


def _footer_size(version: int) -> int:
    """FPakInfo::GetSerializedSize for one version (IPlatformFilePak.h:219-226)."""
    size = 4 + 4 + 8 + 8 + 20 + 1  # Magic, Version, IndexOffset, IndexSize, IndexHash, bEncryptedIndex
    if version >= VERSION_ENCRYPTION_KEY_GUID:
        size += 16  # EncryptionKeyGuid
    if version >= VERSION_FNAME_COMPRESSION_METHOD:
        size += _COMPRESSION_METHOD_NAME_LEN * _MAX_COMPRESSION_METHODS
    if version == VERSION_FROZEN_INDEX:
        size += 1  # bIndexIsFrozen
    return size


def _entry_header_size(version: int, method_index: int, block_count: int) -> int:
    """FPakEntry::GetSerializedSize for one version (IPlatformFilePak.h:443-468)."""
    size = 8 + 8 + 8 + 20  # Offset, Size, UncompressedSize, Hash
    size += 4  # CompressionMethodIndex (int32 legacy, uint32 current)
    if version <= VERSION_INITIAL:
        size += 8  # Timestamp (FDateTime)
    if version >= VERSION_COMPRESSION_ENCRYPTION:
        size += 1 + 4  # Flags, CompressionBlockSize
        if method_index != 0:
            size += 4 + 16 * block_count  # block count prefix + FPakCompressedBlock[N]
    return size


def _read_footer(source: FileSource, path: Path, file_size: int) -> dict:
    """Probe FPakInfo from EOF the way ``FPakFile::Initialize`` does."""
    for version in range(VERSION_LATEST, VERSION_INITIAL - 1, -1):
        footer_size = _footer_size(version)
        start = file_size - footer_size
        if start < 0:
            continue
        try:
            raw = source.read_at(start, footer_size)
        except ParseError:
            continue
        cur = _Cursor(raw, f"{path.name}: FPakInfo v{version}")
        guid = b""
        if version >= VERSION_ENCRYPTION_KEY_GUID:
            guid = cur.raw(16)
        encrypted = cur.u8() != 0
        if cur.u32() != PAK_MAGIC:
            continue
        parsed_version = cur.i32()
        if parsed_version != version:
            continue
        if parsed_version == VERSION_FROZEN_INDEX:
            raise PakError(f"{path.name}: frozen pak index (version 9) is unsupported; regenerate the pak")
        index_offset = cur.i64()
        index_size = cur.i64()
        index_hash = cur.raw(20)
        if index_offset < 0 or index_size < 0 or index_offset + index_size > file_size:
            raise PakError(
                f"{path.name}: index span {index_offset}+{index_size} escapes the {file_size}-byte file"
            )
        if index_size > _MAX_INDEX_BYTES:
            raise PakError(f"{path.name}: index claims {index_size} bytes (> {_MAX_INDEX_BYTES})")
        if version < VERSION_INDEX_ENCRYPTION:
            encrypted = False  # FPakInfo::Serialize forces bEncryptedIndex off below v4
        methods: list[str] = ["None"]
        if version >= VERSION_FNAME_COMPRESSION_METHOD:
            slots = cur.raw(_COMPRESSION_METHOD_NAME_LEN * _MAX_COMPRESSION_METHODS)
            for i in range(_MAX_COMPRESSION_METHODS):
                name = slots[i * _COMPRESSION_METHOD_NAME_LEN : (i + 1) * _COMPRESSION_METHOD_NAME_LEN]
                text = name.split(b"\x00", 1)[0]
                if text:
                    methods.append(text.decode("ascii", "replace"))
        else:
            methods.extend(_LEGACY_METHODS[1:])
        return {
            "version": parsed_version,
            "index_offset": index_offset,
            "index_size": index_size,
            "index_hash": index_hash,
            "index_encrypted": encrypted,
            "encryption_key_guid": guid.hex(),
            "compression_methods": tuple(methods),
        }
    raise PakError(f"{path.name}: no FPakInfo footer with {PAK_MAGIC:#010x} magic found at EOF")


def _load_index_blob(
    source: FileSource, path: Path, offset: int, size: int, expected_hash: bytes, label: str
) -> bytes:
    """D-PAK trust path: bounds-check, read, SHA-1-validate one index blob before trusting it."""
    if offset < 0 or size < 0 or offset + size > source.size():
        raise PakError(f"{path.name}: {label} span {offset}+{size} escapes the file")
    if size > _MAX_INDEX_BYTES:
        raise PakError(f"{path.name}: {label} claims {size} bytes (> {_MAX_INDEX_BYTES})")
    try:
        blob = source.read_at(offset, size)
    except ParseError as exc:
        raise PakError(f"{path.name}: {label} read failed ({exc})") from exc
    if hashlib.sha1(blob).digest() != expected_hash:
        raise PakError(f"{path.name}: {label} SHA-1 does not match the stored index hash")
    return blob


def _make_entry(
    path: str,
    version: int,
    offset: int,
    size: int,
    uncompressed: int,
    method: int,
    block_size: int,
    flags: int,
    block_count: int,
    methods: tuple[str, ...],
) -> PakEntry:
    return PakEntry(
        path=path,
        offset=offset,
        size=size,
        uncompressed_size=uncompressed,
        compression_method_index=method,
        compression_method=methods[method] if method != 0 else None,
        compression_block_size=block_size,
        flags=flags,
        payload_offset=offset + _entry_header_size(version, method, block_count),
    )


def _parse_entry(cur: _Cursor, version: int, methods: tuple[str, ...], path: str) -> PakEntry:
    """Parse one serialized ``FPakEntry`` (``FPakEntry::Serialize``)."""
    offset = cur.i64()
    size = cur.i64()
    uncompressed = cur.i64()
    if version <= VERSION_INITIAL:
        cur.i64()  # Timestamp (FDateTime)
    cur.raw(20)  # Hash: write-only for this read-only surface
    if version < VERSION_FNAME_COMPRESSION_METHOD:
        legacy_method = cur.i32()
        if legacy_method == 0:
            method = 0
        elif legacy_method & 0x02:  # COMPRESS_ZLIB_DEPRECATED (FPakEntry::Serialize legacy branch)
            method = 1
        elif legacy_method & 0x04:  # COMPRESS_GZIP_DEPRECATED
            method = 2
        else:
            method = 3
    else:
        method = cur.u32()
    if method >= len(methods):
        raise PakError(f"{cur._label}: compression method index {method} escapes the method table")
    block_count = 0
    block_size = 0
    flags = 0
    if version >= VERSION_COMPRESSION_ENCRYPTION:
        if method != 0:
            block_count = cur.count("compression block", limit=1 << 16)
            for _ in range(block_count):
                cur.i64()  # CompressedStart
                cur.i64()  # CompressedEnd
        flags = cur.u8()
        block_size = cur.u32()
    return _make_entry(path, version, offset, size, uncompressed, method, block_size, flags, block_count, methods)


def _decode_encoded_entry(
    cur: _Cursor, version: int, methods: tuple[str, ...], path: str
) -> PakEntry:
    """Decode one bit-packed ``EncodedPakEntries`` record (``FPakFile::DecodePakEntry``)."""
    value = cur.u32()
    if (value & 0x3F) == 0x3F:
        block_size = cur.u32()
    else:
        block_size = (value & 0x3F) << 11
    method = (value >> 23) & 0x3F
    if method >= len(methods):
        raise PakError(f"{cur._label}: encoded entry compression method {method} escapes the method table")
    offset = cur.u32() if value & (1 << 31) else cur.i64()
    uncompressed = cur.u32() if value & (1 << 30) else cur.i64()
    if method != 0:
        size = cur.u32() if value & (1 << 29) else cur.i64()
    else:
        size = uncompressed  # DecodePakEntry: Size mirrors UncompressedSize when uncompressed
    flags = _FLAG_ENCRYPTED if value & (1 << 22) else 0
    block_count = (value >> 6) & 0xFFFF
    if block_count > 1 or (block_count == 1 and flags & _FLAG_ENCRYPTED):
        for _ in range(block_count):
            cur.u32()  # per-block stored size
    if block_count == 1:
        block_size = uncompressed  # DecodePakEntry: single block uses UncompressedSize
    return _make_entry(path, version, offset, size, uncompressed, method, block_size, flags, block_count, methods)


def _parse_directory(
    cur: _Cursor,
    version: int,
    mount: str,
    encoded: bytes,
    files_list: list[PakEntry],
    methods: tuple[str, ...],
) -> tuple[PakEntry, ...]:
    """Walk a serialized ``FDirectoryIndex`` (``LoadIndexInternal_DirectoryIndex``)."""
    out: list[PakEntry] = []
    seen: set[str] = set()
    for _ in range(cur.count("directory")):
        directory = cur.fstring().replace("\\", "/")
        for _ in range(cur.count("file")):
            if version >= VERSION_UTF8_PAK_DIRECTORY:
                name = cur.utf8string()
            else:
                name = cur.fstring()
            location = cur.i32()
            if location == _LOCATION_INVALID or location == _LOCATION_MAX_INDEX + 1:
                raise PakError(f"{cur._label}: invalid FPakEntryLocation {location} for {directory}{name}")
            full = f"{mount}{directory}{name}"
            if location >= 0:
                entry = _decode_encoded_entry(_Cursor(encoded, "EncodedPakEntries", location), version, methods, full)
            else:
                list_index = -(location + 1)
                if not 0 <= list_index < len(files_list):
                    raise PakError(f"{cur._label}: Files-list index {list_index} out of range for {full}")
                # Reuse the parsed entry as-is: its payload_offset already accounts
                # for the compression-block array in the header.
                entry = replace(files_list[list_index], path=full)
            if entry.path in seen:
                raise PakError(f"{cur._label}: duplicate index path {entry.path!r}")
            seen.add(entry.path)
            if not entry.deleted:
                out.append(entry)
    return tuple(out)


def read_pak_index(path: str | Path) -> PakIndex:
    """Parse a pak footer + index. Raises ``PakError`` instead of guessing on damage."""
    path = Path(path)
    try:
        source = FileSource(path)
    except OSError as exc:
        raise PakError(f"{path}: cannot open pak ({exc.strerror})") from exc
    file_size = source.size()
    if file_size < _footer_size(VERSION_INITIAL):
        raise PakError(f"{path.name}: {file_size} bytes is smaller than a pak footer")
    footer = _read_footer(source, path, file_size)
    if footer["index_encrypted"]:
        raise PakError(
            f"{path.name}: encrypted index (guid {footer['encryption_key_guid']}); no key support"
        )

    version = footer["version"]
    methods = footer["compression_methods"]

    if version >= VERSION_PATH_HASH_INDEX:
        blob = _load_index_blob(
            source, path, footer["index_offset"], footer["index_size"], footer["index_hash"], "primary index"
        )
        cur = _Cursor(blob, f"{path.name}: primary index")
        mount = cur.fstring().replace("\\", "/")
        num_entries = cur.count("entry")
        cur.u64()  # PathHashSeed: needed for hash lookup, not for directory listing
        has_path_hash = cur.u8() != 0
        if has_path_hash:
            cur.i64()  # PathHashIndexOffset
            cur.i64()  # PathHashIndexSize
            cur.raw(20)  # PathHashIndexHash
        has_full_dir = cur.u8() != 0
        full_dir_span: tuple[int, int, bytes] | None = None
        if has_full_dir:
            full_dir_span = (cur.i64(), cur.i64(), cur.raw(20))
        encoded = cur.raw(cur.count("encoded entries", limit=_MAX_INDEX_BYTES))
        files_list = [_parse_entry(cur, version, methods, "") for _ in range(cur.count("non-encodable entry"))]
        if full_dir_span is None:
            # UE can serve lookups from the path-hash index alone, but that map is
            # keyed by FNV-64 path hashes: without a directory blob there are no
            # filenames to list. Refuse honestly instead of inventing names.
            raise PakError(
                f"{path.name}: path-hash-only index; full filename listing is not available"
            )
        dir_blob = _load_index_blob(
            source, path, full_dir_span[0], full_dir_span[1], full_dir_span[2], "full directory index"
        )
        files = _parse_directory(_Cursor(dir_blob, f"{path.name}: full directory index"),
                                 version, mount, encoded, files_list, methods)
    else:
        blob = _load_index_blob(
            source, path, footer["index_offset"], footer["index_size"], footer["index_hash"], "legacy index"
        )
        cur = _Cursor(blob, f"{path.name}: legacy index")
        mount = cur.fstring().replace("\\", "/")
        num_entries = cur.count("entry")
        entries: list[PakEntry] = []
        seen: set[str] = set()
        for _ in range(num_entries):
            name = cur.fstring().replace("\\", "/")
            entry = _parse_entry(cur, version, methods, f"{mount}{name}")
            if entry.path in seen:
                raise PakError(f"{cur._label}: duplicate index path {entry.path!r}")
            seen.add(entry.path)
            if not entry.deleted:
                entries.append(entry)
        files = tuple(entries)

    return PakIndex(
        path=str(path),
        version=version,
        mount_point=mount,
        num_entries=num_entries,
        index_offset=footer["index_offset"],
        index_size=footer["index_size"],
        index_encrypted=footer["index_encrypted"],
        encryption_key_guid=footer["encryption_key_guid"],
        compression_methods=methods,
        files=files,
    )


class PakEntrySource:
    """List a pak's contained files and range-read plain entry payloads.

    ``read_at`` serves only uncompressed, unencrypted entries; compressed and
    encrypted entries are refused with ``PakError`` because no codec or key
    support is bundled (the index reports ``compression`` / ``encryption`` as
    ``unavailable``).
    """

    def __init__(self, path: str | Path):
        self._path = Path(path)
        try:
            self._file = FileSource(self._path)
        except OSError as exc:
            raise PakError(f"{self._path}: cannot open pak ({exc.strerror})") from exc
        self.index = read_pak_index(self._path)
        self._by_path = {entry.path: entry for entry in self.index.files}

    @property
    def capabilities(self) -> dict[str, Capability]:
        return self.index.capabilities

    def list_files(self) -> tuple[str, ...]:
        return tuple(entry.path for entry in self.index.files)

    def read_at(self, path: str, offset: int, size: int) -> bytes:
        entry = self._by_path.get(path)
        if entry is None:
            raise PakError(f"{self._path.name}: no contained file {path!r}")
        if entry.deleted:
            raise PakError(f"{path}: entry is a delete record")
        if entry.encrypted:
            raise PakError(f"{path}: entry is encrypted; no key support")
        if entry.compressed:
            raise PakError(f"{path}: entry is compressed ({entry.compression_method}); no codec bundled")
        if offset < 0 or size < 0 or offset + size > entry.uncompressed_size:
            raise PakError(
                f"{path}: range {offset}+{size} escapes the {entry.uncompressed_size}-byte entry"
            )
        try:
            return self._file.read_at(entry.payload_offset + offset, size)
        except ParseError as exc:
            raise PakError(f"{path}: payload read failed ({exc})") from exc


__all__ = [
    "PAK_MAGIC",
    "PakEntry",
    "PakEntrySource",
    "PakError",
    "PakIndex",
    "read_pak_index",
]
