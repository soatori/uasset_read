"""Synthetic-bytes tests for the traditional Pak index reader (issue #651).

Every pak here is hand-assembled from struct-packed bytes that mirror the UE
5.8 layouts cited in ``uasset_read.parsers.pak_reader``. They prove index
parsing *mechanics* only — footer probe, hash-validated index load, legacy
and v10+ directory walks, encoded-entry decode, capability reporting and the
bounded-read refusals. There is no redistributable real ``.pak`` fixture yet
(#625 closed without one), so nothing here is a real-asset support claim.
"""

from __future__ import annotations

import hashlib
import struct

import pytest

from uasset_read.parsers.pak_reader import (
    PAK_MAGIC,
    VERSION_FROZEN_INDEX,
    VERSION_UTF8_PAK_DIRECTORY,
    PakEntrySource,
    PakError,
    read_pak_index,
)

# --- byte builders mirroring FPakInfo / FPakEntry / index serialization ---

_HEADER_UNCOMPRESSED_V3PLUS = 53  # Offset+Size+Uncompressed+Hash+Method+Flags+BlockSize


def _fstring(text: str) -> bytes:
    if not text:
        return struct.pack("<i", 0)
    data = text.encode("utf-8") + b"\x00"
    return struct.pack("<i", len(data)) + data


def _utf8string(text: str) -> bytes:
    data = text.encode("utf-8") + b"\x00"
    return struct.pack("<i", len(data)) + data


def _entry(
    offset: int,
    size: int,
    uncompressed: int,
    *,
    version: int = VERSION_UTF8_PAK_DIRECTORY,
    method: int = 0,
    flags: int = 0,
    block_size: int = 0,
    blocks: tuple[tuple[int, int], ...] = (),
) -> bytes:
    """One serialized FPakEntry (FPakEntry::Serialize)."""
    out = struct.pack("<qqq", offset, size, uncompressed)
    if version <= 1:
        out += struct.pack("<q", 0)  # Timestamp
    out += b"\x00" * 20  # Hash
    if version < 8:
        out += struct.pack("<i", method)  # legacy int32 compression method
    else:
        out += struct.pack("<I", method)
    if version >= 3:
        if method != 0:
            out += struct.pack("<i", len(blocks))
            for start, end in blocks:
                out += struct.pack("<qq", start, end)
        out += struct.pack("<B", flags)
        out += struct.pack("<I", block_size)
    return out


def _encoded_uncompressed(offset: int, uncompressed: int) -> bytes:
    """Bit-packed record for a plain, 32-bit-safe entry (FPakFile::EncodePakEntry)."""
    flags = (1 << 31) | (1 << 30) | (1 << 29)  # offset/size/uncompressed 32-bit safe
    return struct.pack("<III", flags, offset, uncompressed)


def _encoded_compressed(
    offset: int, uncompressed: int, stored: int, *, method: int = 1, encrypted: bool = False
) -> bytes:
    """Bit-packed record for a compressed entry with zero blocks (mechanics only)."""
    flags = (
        (1 << 31) | (1 << 30) | (1 << 29)
        | (method << 23)
        | ((1 << 22) if encrypted else 0)
    )
    return struct.pack("<IIII", flags, offset, uncompressed, stored)


def _footer(
    index_offset: int,
    index_size: int,
    index_hash: bytes,
    *,
    version: int = VERSION_UTF8_PAK_DIRECTORY,
    encrypted: bool = False,
    method_names: tuple[str, ...] = (),
) -> bytes:
    """One FPakInfo footer in Serialize order (guid, encrypted, magic, ...)."""
    out = b""
    if version >= 7:
        out += b"\x11" * 16  # EncryptionKeyGuid
    out += struct.pack("<B", 1 if encrypted else 0)
    out += struct.pack("<II", PAK_MAGIC, version)
    out += struct.pack("<qq", index_offset, index_size)
    out += index_hash
    if version == VERSION_FROZEN_INDEX:
        out += struct.pack("<B", 0)  # bIndexIsFrozen
    if version >= 8:
        slots = b"".join(name.encode("ascii")[:31].ljust(32, b"\x00") for name in method_names)
        out += slots.ljust(5 * 32, b"\x00")[: 5 * 32]
    return out


def _build_legacy_pak(path, files: list[tuple[str, bytes, int]], *, version: int = 8, num_entries_override=None):
    """Layout: [per-file header+payload ...][legacy index][footer]."""
    mount = "../../../SyntheticGame/Content/"
    body = b""
    index_entries = b""
    count = 0
    for name, payload, flags in files:
        header_offset = len(body)
        entry = _entry(header_offset, len(payload), len(payload), version=version, flags=flags)
        body += entry + payload
        index_entries += _fstring(name) + entry
        count += 1
    if num_entries_override is not None:
        count = num_entries_override
    index = _fstring(mount) + struct.pack("<i", count) + index_entries
    index_offset = len(body)
    pak = body + index + _footer(index_offset, len(index), hashlib.sha1(index).digest(), version=version)
    path.write_bytes(pak)
    return mount


def _build_v12_pak(
    tmp_path,
    *,
    plain: dict[str, bytes] | None = None,
    compressed: dict[str, bytes] | None = None,
    encrypted: tuple[str, ...] = (),
    path_hash_only: bool = False,
    method_names: tuple[str, ...] = ("Oodle",),
):
    """Layout: [payloads][primary index][full directory index][footer], v12, UTF-8 names."""
    plain = plain or {}
    compressed = compressed or {}
    mount = "../../../SyntheticGame/Content/"
    body = b""
    encoded = b""
    locations: dict[str, int] = {}

    for name, payload in plain.items():
        header_offset = len(body)
        body += _entry(header_offset, len(payload), len(payload)) + payload
        locations[name] = len(encoded)
        encoded += _encoded_uncompressed(header_offset, len(payload))
    for name, payload in compressed.items():
        header_offset = len(body)
        body += _entry(header_offset, len(payload), len(payload) // 2, method=1) + payload
        locations[name] = len(encoded)
        encoded += _encoded_compressed(
            header_offset, len(payload) // 2, len(payload) // 2, encrypted=name in encrypted
        )

    # Full directory index: one directory holding every file (flat synthetic tree).
    directory = struct.pack("<i", 1) + _fstring("") + struct.pack("<i", len(locations))
    for name in locations:
        directory += _utf8string(name) + struct.pack("<i", locations[name])

    index_offset = len(body)
    # Primary index with a placeholder directory span, rebuilt once its length is known.
    def primary_with(dir_offset: int, dir_hash: bytes) -> bytes:
        out = _fstring(mount)
        out += struct.pack("<i", len(locations))  # NumEntries
        out += struct.pack("<Q", 0x1234)  # PathHashSeed
        out += struct.pack("<B", 1 if path_hash_only else 0)  # bHasPathHashIndex
        if path_hash_only:
            out += struct.pack("<qq", index_offset, 0) + b"\x00" * 20  # dummy span, never loaded
        out += struct.pack("<B", 0 if path_hash_only else 1)  # bHasFullDirectoryIndex
        if not path_hash_only:
            out += struct.pack("<qq", dir_offset, len(directory)) + dir_hash
        out += struct.pack("<i", len(encoded)) + encoded
        out += struct.pack("<i", 0)  # non-encodable Files list
        return out

    placeholder = primary_with(-1, b"\x00" * 20)
    dir_offset = index_offset + len(placeholder)
    primary = primary_with(dir_offset, hashlib.sha1(directory).digest())
    assert len(primary) == len(placeholder)
    # FPakInfo::IndexSize covers the primary index only; secondaries live outside
    # that span at their absolute offsets (PakFileUtilities.cpp write order).
    pak = body + primary + directory + _footer(
        index_offset, len(primary), hashlib.sha1(primary).digest(), method_names=method_names
    )
    out = tmp_path / "Synthetic.pak"
    out.write_bytes(pak)
    return mount


# --- tests ---


def test_pak_synthetic_legacy_v8_lists_files_and_reads_payload(tmp_path):
    path = tmp_path / "legacy.pak"
    mount = _build_legacy_pak(
        path,
        [
            ("Foo.uasset", b"UASSET-foo-bytes", 0),
            ("Chars/Hero.uasset", b"UASSET-hero", 0),
        ],
    )
    source = PakEntrySource(path)
    assert source.list_files() == (f"{mount}Foo.uasset", f"{mount}Chars/Hero.uasset")
    assert source.read_at(f"{mount}Foo.uasset", 0, 6) == b"UASSET"
    assert source.read_at(f"{mount}Foo.uasset", 6, 10) == b"-foo-bytes"
    assert source.read_at(f"{mount}Chars/Hero.uasset", 0, 11) == b"UASSET-hero"
    assert source.index.version == 8
    assert source.index.mount_point == mount


def test_pak_synthetic_legacy_v8_ignores_deleted_entries(tmp_path):
    path = tmp_path / "legacy_deleted.pak"
    mount = _build_legacy_pak(path, [("Alive.uasset", b"data", 0), ("Gone.uasset", b"gone", 0x02)])
    source = PakEntrySource(path)
    assert source.list_files() == (f"{mount}Alive.uasset",)
    assert len(source.index.files) == 1


def test_pak_synthetic_legacy_v8_reads_utf16_filenames(tmp_path):
    path = tmp_path / "legacy_utf16.pak"
    mount = "../../../SyntheticGame/Content/"
    entry = _entry(0, 10, 10, version=8)
    name = "Ünicode.uasset"
    utf16_name = struct.pack("<i", -(len(name) + 1)) + name.encode("utf-16-le") + b"\x00\x00"
    index = _fstring(mount) + struct.pack("<i", 1) + utf16_name + entry
    body = entry + b"utf16-name"
    path.write_bytes(body + index + _footer(len(body), len(index), hashlib.sha1(index).digest(), version=8))
    source = PakEntrySource(path)
    assert source.list_files() == (f"{mount}{name}",)
    assert source.read_at(f"{mount}{name}", 0, 5) == b"utf16"


def test_pak_synthetic_v12_full_directory_lists_and_reads(tmp_path):
    mount = _build_v12_pak(
        tmp_path,
        plain={"Foo.uasset": b"UASSET-foo", "Chars/Hero.uasset": b"hero-bytes"},
    )
    source = PakEntrySource(tmp_path / "Synthetic.pak")
    assert source.list_files() == (f"{mount}Foo.uasset", f"{mount}Chars/Hero.uasset")
    assert source.read_at(f"{mount}Foo.uasset", 0, 6) == b"UASSET"
    assert source.read_at(f"{mount}Chars/Hero.uasset", 0, 10) == b"hero-bytes"
    entry = source.index.files[0]
    assert entry.payload_offset == entry.offset + _HEADER_UNCOMPRESSED_V3PLUS
    assert source.index.compression_methods == ("None", "Oodle")


def test_pak_synthetic_v12_reports_compression_capability(tmp_path):
    _build_v12_pak(
        tmp_path,
        plain={"Plain.uasset": b"plain"},
        compressed={"Big.uasset": b"ZZZZZZZZZZ"},
    )
    source = PakEntrySource(tmp_path / "Synthetic.pak")
    caps = source.capabilities
    assert caps["toc_entries"] == "available"
    assert caps["entry_bytes"] == "available"
    assert caps["compression"] == "unavailable"
    assert caps["encryption"] == "unavailable"
    big = next(e for e in source.index.files if e.path.endswith("Big.uasset"))
    assert big.compressed and big.compression_method == "Oodle"
    with pytest.raises(PakError, match="no codec bundled"):
        source.read_at(big.path, 0, 4)


def test_pak_synthetic_v12_refuses_encrypted_entry_reads(tmp_path):
    _build_v12_pak(
        tmp_path, compressed={"Secret.uasset": b"ssssssssss"}, encrypted=("Secret.uasset",)
    )
    source = PakEntrySource(tmp_path / "Synthetic.pak")
    entry = next(e for e in source.index.files if e.path.endswith("Secret.uasset"))
    assert entry.encrypted
    with pytest.raises(PakError, match="encrypted"):
        source.read_at(entry.path, 0, 1)


def test_pak_synthetic_v12_refuses_encrypted_index(tmp_path):
    path = tmp_path / "enc.pak"
    body = b"\x00" * 64
    index = b"index-bytes-not-parsed"
    pak = body + index + _footer(len(body), len(index), hashlib.sha1(index).digest(), encrypted=True)
    path.write_bytes(pak)
    with pytest.raises(PakError, match="encrypted index"):
        read_pak_index(path)


def test_pak_synthetic_hash_mismatch_is_refused(tmp_path):
    path = tmp_path / "corrupt.pak"
    body = b"\x00" * 64
    index = _fstring("../../../M/") + struct.pack("<i", 0)
    corrupt = b"\xff" + index[1:]
    # Footer stores the hash of the pristine index, but different bytes sit in the span.
    path.write_bytes(body + corrupt + _footer(len(body), len(index), hashlib.sha1(index).digest(), version=8))
    with pytest.raises(PakError, match="SHA-1"):
        read_pak_index(path)


def test_pak_synthetic_frozen_version_9_is_refused(tmp_path):
    path = tmp_path / "frozen.pak"
    body = b"\x00" * 64
    index = b"x" * 8
    pak = body + index + _footer(len(body), len(index), hashlib.sha1(index).digest(), version=VERSION_FROZEN_INDEX)
    path.write_bytes(pak)
    with pytest.raises(PakError, match="frozen"):
        read_pak_index(path)


def test_pak_synthetic_path_hash_only_index_is_refused(tmp_path):
    _build_v12_pak(tmp_path, plain={"Foo.uasset": b"data"}, path_hash_only=True)
    with pytest.raises(PakError, match="path-hash-only"):
        read_pak_index(tmp_path / "Synthetic.pak")


def test_pak_synthetic_missing_footer_is_refused(tmp_path):
    path = tmp_path / "garbage.pak"
    path.write_bytes(b"\x00" * 512)
    with pytest.raises(PakError, match="no FPakInfo footer"):
        read_pak_index(path)


def test_pak_synthetic_implausible_entry_count_is_refused(tmp_path):
    path = tmp_path / "huge.pak"
    mount = "../../../M/Content/"
    index = _fstring(mount) + struct.pack("<i", 0x7FFFFFFF)
    pak = b"\x00" * 32 + index + _footer(32, len(index), hashlib.sha1(index).digest(), version=8)
    path.write_bytes(pak)
    with pytest.raises(PakError, match="count"):
        read_pak_index(path)


def test_pak_synthetic_read_range_out_of_entry_is_refused(tmp_path):
    mount = _build_v12_pak(tmp_path, plain={"Foo.uasset": b"0123456789"})
    source = PakEntrySource(tmp_path / "Synthetic.pak")
    with pytest.raises(PakError, match="escapes"):
        source.read_at(f"{mount}Foo.uasset", 8, 4)
    with pytest.raises(PakError, match="no contained file"):
        source.read_at(f"{mount}Missing.uasset", 0, 1)
