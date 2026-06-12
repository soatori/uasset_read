from __future__ import annotations

from io import BytesIO

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.package import PackageArchive
from uasset_read.pak.decompress import decompress_entry
from uasset_read.pak.structures import FPakCompressedBlock, FPakEntry


pytestmark = pytest.mark.unit


class MemoryArchive:
    def __init__(self, data: bytes, name: str = "<memory>") -> None:
        self._stream = BytesIO(data)
        self._data = data
        self._path = name

    def read(self, size: int) -> bytes:
        return self._stream.read(size)

    def seek(self, pos: int) -> None:
        self._stream.seek(pos)

    def tell(self) -> int:
        return self._stream.tell()

    def total_size(self) -> int:
        return len(self._data)

    def close(self) -> None:
        self._stream.close()

    def set_byte_swapping(self, enabled: bool) -> None:
        return None


def test_package_archive_rejects_negative_read_size() -> None:
    archive = PackageArchive(MemoryArchive(b"abc"))
    with pytest.raises(ParseError, match="negative size"):
        archive.read(-1)


def test_package_archive_rejects_out_of_range_read() -> None:
    archive = PackageArchive(MemoryArchive(b"abc"))
    archive.seek(2)
    with pytest.raises(ParseError, match="only 1 bytes remaining"):
        archive.read(2)


def test_package_archive_reads_across_uasset_and_uexp() -> None:
    archive = PackageArchive(MemoryArchive(b"abc"), MemoryArchive(b"def"))
    archive.seek(1)
    assert archive.read(4) == b"bcde"


def test_pak_uncompressed_short_read_is_parse_error() -> None:
    entry = FPakEntry(offset=0, uncompressed_size=8, size=8, is_compressed=False)
    with pytest.raises(ParseError, match="Pak .*短读"):
        decompress_entry(BytesIO(b"short"), entry)


def test_pak_compressed_block_short_read_is_parse_error() -> None:
    entry = FPakEntry(
        offset=0,
        uncompressed_size=8,
        size=8,
        is_compressed=True,
        compression_method_index=1,
        compression_block_size=8,
        compression_blocks=[FPakCompressedBlock(compressed_start=0, compressed_end=8)],
    )
    with pytest.raises(ParseError, match="读取不足"):
        decompress_entry(BytesIO(b"tiny"), entry, compression_method="None")


def test_iostore_uncompressed_partition_short_read_is_parse_error() -> None:
    reader = IoStoreReader("missing.utoc")
    reader._ucas_files = [BytesIO(b"tiny")]
    reader._header = None
    with pytest.raises(ParseError, match="IoStore .*读取不足"):
        reader._read_uncompressed_partitions(0, 0, 8)
