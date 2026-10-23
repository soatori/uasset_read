"""Tests for the traditional Pak index reader (issue #651).

Two layers prove the reader:

- Synthetic paks are hand-assembled from struct-packed bytes that mirror the
  UE 5.8 layouts cited in ``uasset_read.parsers.pak_reader`` (FPakInfo
  footer probe, hash-validated index load, legacy and v10+ directory walks,
  encoded-entry decode, geometry refusals). They are byte-level probes, not
  real-asset support claims.
- Two real redistributable ``.pak`` fixtures tracked under
  ``tests/samples/containers/`` (``ParserFixturesLegacy-Windows.pak`` and
  ``MyProject-Windows.pak``, manifest issue #625) are parsed end to end:
  exact entry counts, mount points, known paths, and entry-geometry bounds.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest

from uasset_read.parsers.pak_reader import (
    PAK_MAGIC,
    VERSION_FROZEN_INDEX,
    VERSION_UTF8_PAK_DIRECTORY,
    PakEntrySource,
    PakError,
    read_pak_index,
)

CONTAINERS = Path(__file__).resolve().parent / "samples" / "containers"
_PACKAGE_FILE_TAG = b"\xc1\x83\x2a\x9e"  # PACKAGE_FILE_TAG, little-endian

# --- byte builders mirroring FPakInfo / FPakEntry / index serialization ---

_HEADER_UNCOMPRESSED_V3PLUS = 53  # Offset+Size+Uncompressed+Method+Hash+Flags+BlockSize

# ECompressionFlags values FPakEntry::Serialize stores below v8, indexed by method slot.
_LEGACY_METHOD_FLAGS = (0x00, 0x01, 0x02, 0x04)


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
    """One serialized FPakEntry in FPakEntry::Serialize field order."""
    out = struct.pack("<qqq", offset, size, uncompressed)
    if version < 8:
        out += struct.pack("<i", _LEGACY_METHOD_FLAGS[method])  # ECompressionFlags pre-v8
    else:
        out += struct.pack("<I", method)
    if version <= 1:
        out += struct.pack("<q", 0)  # Timestamp (FDateTime)
    out += b"\x00" * 20  # Hash
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


def _record_single_block_unencrypted(offset: int, stored: int, uncompressed: int) -> bytes:
    """DecodePakEntry: count=1 unencrypted stores no per-block sizes."""
    flags = 0xE0000000 | (1 << 23) | (1 << 6)
    return struct.pack("<IIII", flags, offset, uncompressed, stored)


def _record_single_block_encrypted(offset: int, stored: int, uncompressed: int) -> bytes:
    """DecodePakEntry: count=1 encrypted stores one per-block size."""
    flags = 0xE0000000 | (1 << 23) | (1 << 22) | (1 << 6)
    return struct.pack("<IIIII", flags, offset, uncompressed, stored, stored)


def _record_two_blocks_packed(offset: int, stored: int, uncompressed: int) -> bytes:
    """count=2 with block size packed as 8 (bits 5-0) -> 8 << 11 = 16384."""
    flags = 0xE0000000 | (1 << 23) | (2 << 6) | 8
    return struct.pack("<IIIIII", flags, offset, uncompressed, stored, stored // 2, stored - stored // 2)


def _record_two_blocks_escape(offset: int, stored: int, uncompressed: int) -> bytes:
    """count=2 with packed=0x3F: the real block size follows the flag word."""
    flags = 0xE0000000 | (1 << 23) | (2 << 6) | 0x3F
    return struct.pack("<IIIIIII", flags, 1000, offset, uncompressed, stored, 16, stored - 16)


def _footer(
    index_offset: int,
    index_size: int,
    index_hash: bytes,
    *,
    version: int = VERSION_UTF8_PAK_DIRECTORY,
    encrypted: bool = False,
    method_names: tuple[str, ...] = (),
    frozen: bool = False,
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
        # bIndexIsFrozen occupies one byte in the GetSerializedSize window.
        out += struct.pack("<B", 1 if frozen else 0)
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
    version: int = VERSION_UTF8_PAK_DIRECTORY,
    deleted: tuple[str, ...] = (),
    nonencodable: tuple[tuple[str, bytes, int], ...] = (),
    custom: tuple[dict, ...] = (),
    num_entries_override: int | None = None,
):
    """Layout: [payloads][primary index][full directory index][footer], v10+ layout.

    ``custom`` entries are dicts with keys name / payload / uncompressed /
    method / block_count / flags / record, where record(offset, stored,
    uncompressed) returns the bit-packed EncodedPakEntries record.
    ``deleted`` names become directory records with an invalid
    FPakEntryLocation. ``nonencodable`` entries (name, payload, uncompressed)
    live in the primary index's Files list, referenced by negative locations.
    """
    plain = plain or {}
    compressed = compressed or {}
    mount = "../../../SyntheticGame/Content/"
    body = bytearray()
    encoded = b""
    locations: dict[str, int] = {}

    def add_body_entry(entry: bytes, payload: bytes) -> int:
        header_offset = len(body)
        body.extend(entry + payload)
        return header_offset

    for name, payload in plain.items():
        header_offset = add_body_entry(
            _entry(len(body), len(payload), len(payload), version=version), payload
        )
        locations[name] = len(encoded)
        encoded += _encoded_uncompressed(header_offset, len(payload))
    for name, payload in compressed.items():
        header_offset = add_body_entry(
            _entry(len(body), len(payload), len(payload) // 2, version=version, method=1), payload
        )
        locations[name] = len(encoded)
        encoded += _encoded_compressed(
            header_offset, len(payload) // 2, len(payload) // 2, encrypted=name in encrypted
        )
    for spec in custom:
        header_offset = add_body_entry(
            _entry(
                len(body),
                len(spec["payload"]),
                spec["uncompressed"],
                version=version,
                method=spec["method"],
                flags=spec["flags"],
                blocks=tuple((0, 0) for _ in range(spec["block_count"])),
            ),
            spec["payload"],
        )
        locations[spec["name"]] = len(encoded)
        encoded += spec["record"](header_offset, len(spec["payload"]), spec["uncompressed"])

    files_list = bytearray()
    for i, (name, payload, uncompressed) in enumerate(nonencodable):
        entry = _entry(len(body), len(payload), uncompressed, version=version)
        body.extend(entry + payload)
        locations[name] = -(i + 1)  # FPakEntryLocation::CreateFromListIndex
        files_list.extend(entry)

    # Directory records: live locations first, then delete records whose
    # FPakEntryLocation is Invalid (MIN_int32).
    dir_records = [(name, locations[name]) for name in locations]
    dir_records += [(name, -(1 << 31)) for name in deleted]
    directory = struct.pack("<i", 1) + _fstring("") + struct.pack("<i", len(dir_records))
    for name, loc in dir_records:
        if version >= VERSION_UTF8_PAK_DIRECTORY:
            directory += _utf8string(name)
        else:
            directory += _fstring(name)
        directory += struct.pack("<i", loc)

    index_offset = len(body)
    num_entries_field = len(dir_records) if num_entries_override is None else num_entries_override
    # Primary index with a placeholder directory span, rebuilt once its length is known.
    def primary_with(dir_offset: int, dir_hash: bytes) -> bytes:
        out = _fstring(mount)
        out += struct.pack("<i", num_entries_field)  # NumEntries
        out += struct.pack("<Q", 0x1234)  # PathHashSeed
        # FArchive bools serialize as 4-byte UBOOLs.
        out += struct.pack("<I", 1 if path_hash_only else 0)  # bHasPathHashIndex
        if path_hash_only:
            out += struct.pack("<qq", index_offset, 0) + b"\x00" * 20  # dummy span, never loaded
        out += struct.pack("<I", 0 if path_hash_only else 1)  # bHasFullDirectoryIndex
        if not path_hash_only:
            out += struct.pack("<qq", dir_offset, len(directory)) + dir_hash
        out += struct.pack("<i", len(encoded)) + encoded
        out += struct.pack("<i", len(nonencodable)) + bytes(files_list)
        return out

    placeholder = primary_with(-1, b"\x00" * 20)
    dir_offset = index_offset + len(placeholder)
    primary = primary_with(dir_offset, hashlib.sha1(directory).digest())
    assert len(primary) == len(placeholder)
    # FPakInfo::IndexSize covers the primary index only; secondaries live outside
    # that span at their absolute offsets (PakFileUtilities.cpp write order).
    pak = bytes(body) + primary + directory + _footer(
        index_offset, len(primary), hashlib.sha1(primary).digest(), version=version, method_names=method_names
    )
    out = tmp_path / "Synthetic.pak"
    out.write_bytes(pak)
    return mount


def _build_handmade_legacy(tmp_path, entry: bytes, *, name: str = "F.bin", version: int = 8, payload: bytes = b""):
    """Assemble a one-file legacy pak around raw entry bytes (for crafted fields)."""
    path = tmp_path / "handmade.pak"
    mount = "../../../M/Content/"
    body = entry + payload
    index = _fstring(mount) + struct.pack("<i", 1) + _fstring(name) + entry
    path.write_bytes(body + index + _footer(len(body), len(index), hashlib.sha1(index).digest(), version=version))
    return path, mount


# --- synthetic mechanics ---


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
    assert source.index.deleted_count == 0


def test_pak_synthetic_legacy_v8_ignores_deleted_entries(tmp_path):
    path = tmp_path / "legacy_deleted.pak"
    mount = _build_legacy_pak(path, [("Alive.uasset", b"data", 0), ("Gone.uasset", b"gone", 0x02)])
    source = PakEntrySource(path)
    assert source.list_files() == (f"{mount}Alive.uasset",)
    assert len(source.index.files) == 1
    assert source.index.deleted_count == 1


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5, 6, 7])
def test_pak_synthetic_legacy_version_matrix_lists_and_reads(tmp_path, version):
    """v1-v7 legacy (Filename, FPakEntry) pairs parse with per-version layouts."""
    path = tmp_path / f"legacy_v{version}.pak"
    mount = _build_legacy_pak(path, [("Foo.uasset", b"payload-bytes", 0)], version=version)
    source = PakEntrySource(path)
    assert source.index.version == version
    assert source.list_files() == (f"{mount}Foo.uasset",)
    assert source.read_at(f"{mount}Foo.uasset", 0, 7) == b"payload"
    entry = source.index.files[0]
    expected_header = 56 if version == 1 else 48 if version == 2 else _HEADER_UNCOMPRESSED_V3PLUS
    assert entry.payload_offset == entry.offset + expected_header


@pytest.mark.parametrize("version", [10, 11])
def test_pak_synthetic_v10_v11_full_directory_lists_and_reads(tmp_path, version):
    """v10 and v11 use the same primary-index layout as v12 (FString names)."""
    mount = _build_v12_pak(tmp_path, plain={"Foo.uasset": b"UASSET-foo"}, version=version)
    source = PakEntrySource(tmp_path / "Synthetic.pak")
    assert source.index.version == version
    assert source.list_files() == (f"{mount}Foo.uasset",)
    assert source.read_at(f"{mount}Foo.uasset", 0, 6) == b"UASSET"


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
    pak = body + index + _footer(
        len(body), len(index), hashlib.sha1(index).digest(), version=VERSION_FROZEN_INDEX, frozen=True
    )
    path.write_bytes(pak)
    with pytest.raises(PakError, match="frozen"):
        read_pak_index(path)


def test_pak_synthetic_non_frozen_version_9_parses(tmp_path):
    """UE fatals only when bIndexIsFrozen is set; non-frozen v9 paks are valid."""
    path = tmp_path / "v9.pak"
    mount = _build_legacy_pak(path, [("Foo.uasset", b"v9-bytes", 0)], version=VERSION_FROZEN_INDEX)
    source = PakEntrySource(path)
    assert source.index.version == 9
    assert source.list_files() == (f"{mount}Foo.uasset",)
    assert source.read_at(f"{mount}Foo.uasset", 0, 2) == b"v9"


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


# --- legacy compression flag mapping (FPakEntry::Serialize below v8) ---


@pytest.mark.parametrize(
    "flag,method_name",
    [(0x01, "Zlib"), (0x02, "Gzip"), (0x04, "Oodle")],
)
def test_pak_synthetic_legacy_v7_compression_flag_mapping(tmp_path, flag, method_name):
    """ECompressionFlags bits map onto method slots 1/2/3 (0x01 is Zlib, not Oodle)."""
    entry = (
        struct.pack("<qqqi", 0, 8, 8, flag)
        + b"\x00" * 20
        + struct.pack("<i", 0)  # CompressionBlocks count
        + struct.pack("<B", 0)  # Flags
        + struct.pack("<I", 0)  # CompressionBlockSize
    )
    path, mount = _build_handmade_legacy(tmp_path, entry, payload=b"12345678", version=7)
    index = read_pak_index(path)
    parsed = index.files[0]
    assert parsed.path == f"{mount}F.bin"
    assert parsed.compression_method_index == {"Zlib": 1, "Gzip": 2, "Oodle": 3}[method_name]
    assert parsed.compression_method == method_name


def test_pak_synthetic_legacy_unknown_compression_flag_is_refused(tmp_path):
    entry = struct.pack("<qqqi", 0, 8, 8, 0x08) + b"\x00" * 20  # UE Fatals on unknown types
    path, _mount = _build_handmade_legacy(tmp_path, entry, payload=b"12345678", version=7)
    with pytest.raises(PakError, match="unknown legacy compression"):
        read_pak_index(path)


# --- geometry validation and payload bounds ---


@pytest.mark.parametrize("bad_entry", [(-1, 10, 10), (0, -1, 10), (0, 10, -1)])
def test_pak_synthetic_negative_entry_geometry_is_refused(tmp_path, bad_entry):
    offset, size, uncompressed = bad_entry
    entry = _entry(offset, size, uncompressed, version=8)
    path, _mount = _build_handmade_legacy(tmp_path, entry, payload=b"0123456789")
    with pytest.raises(PakError, match="negative entry geometry"):
        read_pak_index(path)


def test_pak_synthetic_entry_payload_span_past_eof_is_refused(tmp_path):
    entry = _entry(10_000_000, 10, 10, version=8)  # payload claim runs far past the file
    path, _mount = _build_handmade_legacy(tmp_path, entry, payload=b"0123456789")
    with pytest.raises(PakError, match="payload span"):
        read_pak_index(path)


def test_pak_synthetic_footer_index_span_past_eof_is_refused(tmp_path):
    path = tmp_path / "span.pak"
    body = b"\x00" * 64
    index = b"x" * 8
    pak = body + index + _footer(64, 1000, hashlib.sha1(index).digest(), version=12)  # size runs past EOF
    path.write_bytes(pak)
    with pytest.raises(PakError, match="escapes"):
        read_pak_index(path)


def test_pak_synthetic_read_at_caps_to_stored_size(tmp_path):
    """Crafted size=10/uncompressed=1000: reads never leave the stored payload."""
    entry = _entry(0, 10, 1000, version=8)
    payload = b"0123456789"
    path, mount = _build_handmade_legacy(tmp_path, entry, payload=payload + b"TOMORROW-IS-ANOTHER-FILE")
    source = PakEntrySource(path)
    assert source.read_at(f"{mount}F.bin", 0, 10) == payload
    with pytest.raises(PakError, match="escapes the 10-byte stored payload"):
        source.read_at(f"{mount}F.bin", 0, 11)
    with pytest.raises(PakError, match="escapes the 10-byte stored payload"):
        source.read_at(f"{mount}F.bin", 0, 1000)


# --- v10+ index structures ---


def test_pak_synthetic_v12_files_list_negative_location(tmp_path):
    """Non-encodable entries live in the Files list behind negative locations."""
    mount = _build_v12_pak(
        tmp_path,
        plain={"Plain.uasset": b"plain-1234"},
        nonencodable=(("Listed.uasset", b"listed-5678", 12),),
    )
    source = PakEntrySource(tmp_path / "Synthetic.pak")
    assert source.list_files() == (f"{mount}Plain.uasset", f"{mount}Listed.uasset")
    assert source.read_at(f"{mount}Listed.uasset", 0, 6) == b"listed"
    assert source.index.num_entries == 2
    assert source.index.deleted_count == 0


def test_pak_synthetic_v12_invalid_location_is_a_delete_record(tmp_path):
    """Invalid FPakEntryLocation resolves to FoundDeleted, not PakError."""
    mount = _build_v12_pak(tmp_path, plain={"Alive.uasset": b"data"}, deleted=("Gone.uasset",))
    index = read_pak_index(tmp_path / "Synthetic.pak")
    assert index.num_entries == 2
    assert index.deleted_count == 1
    assert [entry.path for entry in index.files] == [f"{mount}Alive.uasset"]
    source = PakEntrySource(tmp_path / "Synthetic.pak")
    with pytest.raises(PakError, match="no contained file"):
        source.read_at(f"{mount}Gone.uasset", 0, 1)


def test_pak_synthetic_v12_num_entries_mismatch_is_refused(tmp_path):
    _build_v12_pak(tmp_path, plain={"Foo.uasset": b"data"}, num_entries_override=99)
    with pytest.raises(PakError, match="NumEntries 99 does not match 1 directory records"):
        read_pak_index(tmp_path / "Synthetic.pak")


def test_pak_synthetic_v12_encoded_block_records_decode(tmp_path):
    payload = b"Z" * 32
    _build_v12_pak(
        tmp_path,
        custom=(
            {
                "name": "Single.uasset",
                "payload": payload,
                "uncompressed": len(payload),
                "method": 1,
                "block_count": 1,
                "flags": 0,
                "record": _record_single_block_unencrypted,
            },
            {
                "name": "Enc.uasset",
                "payload": payload,
                "uncompressed": len(payload),
                "method": 1,
                "block_count": 1,
                "flags": 0x01,
                "record": _record_single_block_encrypted,
            },
            {
                "name": "Blocks.uasset",
                "payload": payload,
                "uncompressed": len(payload),
                "method": 1,
                "block_count": 2,
                "flags": 0,
                "record": _record_two_blocks_packed,
            },
            {
                "name": "Escape.uasset",
                "payload": payload,
                "uncompressed": len(payload),
                "method": 1,
                "block_count": 2,
                "flags": 0,
                "record": _record_two_blocks_escape,
            },
        ),
    )
    index = read_pak_index(tmp_path / "Synthetic.pak")
    by_name = {entry.path.rsplit("/", 1)[-1]: entry for entry in index.files}
    single = by_name["Single.uasset"]
    assert single.compressed and not single.encrypted
    assert single.compression_block_size == len(payload)  # count==1: block size = UncompressedSize
    enc = by_name["Enc.uasset"]
    assert enc.encrypted and enc.compression_block_size == len(payload)
    blocks = by_name["Blocks.uasset"]
    assert blocks.compression_block_size == 8 << 11  # packed multiple of 1<<11
    escape = by_name["Escape.uasset"]
    assert escape.compression_block_size == 1000  # 0x3F escape carries the raw value


# --- real tracked fixtures (tests/samples/containers, manifest issue #625) ---


def test_real_pak_parser_fixtures_legacy_index():
    pak = CONTAINERS / "ParserFixturesLegacy-Windows.pak"
    index = read_pak_index(pak)
    assert index.version == 12
    assert index.mount_point == "../../../MyProject/Content/ParserFixtures/"
    assert index.num_entries == 25
    assert len(index.files) == 25
    assert index.deleted_count == 0
    assert index.compression_methods == ("None",)  # every entry is plain
    paths = {entry.path for entry in index.files}
    for known in (
        "/DT_ParserWeapon.uasset",
        "/DT_ParserWeapon.uexp",
        "/L_ParserFixtures.umap",
        "/T_ParserBulk.ubulk",
        "/TestBlueprint.uasset",
    ):
        assert f"{index.mount_point}{known}" in paths
    file_size = pak.stat().st_size
    for entry in index.files:
        assert entry.offset >= 0 and entry.size >= 0 and entry.uncompressed_size >= 0
        assert entry.payload_offset + entry.size <= file_size
    source = PakEntrySource(pak)
    with pytest.raises(PakError, match="no contained file"):
        source.read_at(f"{index.mount_point}Missing.uasset", 0, 1)


def test_real_pak_parser_fixtures_legacy_payload_is_a_plain_package():
    pak = CONTAINERS / "ParserFixturesLegacy-Windows.pak"
    index = read_pak_index(pak)
    source = PakEntrySource(pak)
    payload = source.read_at(f"{index.mount_point}/DT_ParserWeapon.uasset", 0, 4)
    assert payload == _PACKAGE_FILE_TAG  # plain uncompressed payload, no codec involved


def test_real_pak_myproject_index():
    pak = CONTAINERS / "MyProject-Windows.pak"
    index = read_pak_index(pak)
    assert index.version == 12
    assert index.mount_point == "../../../"
    assert index.num_entries == 1741
    assert index.compression_methods == ("None", "Oodle")
    assert len(index.files) + index.deleted_count == index.num_entries
    paths = {entry.path for entry in index.files}
    assert f"{index.mount_point}Engine/Config/Base.ini" in paths
    assert f"{index.mount_point}Engine/GlobalShaderCache-PCD3D_SM5.bin" in paths
    file_size = pak.stat().st_size
    for entry in index.files:
        assert entry.offset >= 0 and entry.size >= 0 and entry.uncompressed_size >= 0
        assert entry.payload_offset + entry.size <= file_size
