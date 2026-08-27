"""Reader contract — Source/SliceReader bounded reads and overflow protection."""

from __future__ import annotations

import pytest

from uasset_read.v2.source import FileSource, MemorySource, SliceReader


class TestMemorySource:
    def test_size(self):
        src = MemorySource(b"hello world")
        assert src.size() == 11

    def test_read_at(self):
        src = MemorySource(b"hello world")
        assert src.read_at(0, 5) == b"hello"
        assert src.read_at(6, 5) == b"world"

    def test_read_at_negative_offset(self):
        src = MemorySource(b"hello")
        with pytest.raises(IndexError):
            src.read_at(-1, 1)

    def test_read_at_overflow(self):
        src = MemorySource(b"hello")
        with pytest.raises(IndexError):
            src.read_at(3, 5)

    def test_describe(self):
        src = MemorySource(b"test", name="test.bin")
        info = src.describe()
        assert info.kind == "memory"
        assert info.name == "test.bin"
        assert info.size == 4


class TestFileSource:
    def test_read(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00\x01\x02\x03\x04")
        src = FileSource(f)
        assert src.size() == 5
        assert src.read_at(1, 3) == b"\x01\x02\x03"

    def test_read_out_of_range(self, tmp_path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00\x01")
        src = FileSource(f)
        with pytest.raises(IndexError):
            src.read_at(0, 10)


class TestSliceReader:
    def test_basic_read(self):
        src = MemorySource(b"0123456789")
        sr = SliceReader(src, 2, 5)
        assert sr.source_size == 5
        assert sr.read(3) == b"234"
        assert sr.tell() == 3
        assert sr.remaining() == 2

    def test_seek(self):
        src = MemorySource(b"0123456789")
        sr = SliceReader(src, 0, 10)
        sr.seek(5)
        assert sr.tell() == 5
        assert sr.read(3) == b"567"

    def test_seek_out_of_range(self):
        src = MemorySource(b"0123456789")
        sr = SliceReader(src, 0, 10)
        with pytest.raises(IndexError):
            sr.seek(11)

    def test_read_exceeds_slice(self):
        src = MemorySource(b"0123456789")
        sr = SliceReader(src, 2, 3)
        with pytest.raises(IndexError):
            sr.read(4)

    def test_sub_slice(self):
        src = MemorySource(b"0123456789")
        sr = SliceReader(src, 0, 10)
        sub = sr.sub_slice(2, 4)
        assert sub.source_size == 4
        assert sub.read(4) == b"2345"

    def test_sub_slice_out_of_range(self):
        src = MemorySource(b"0123456789")
        sr = SliceReader(src, 2, 3)
        with pytest.raises(IndexError):
            sr.sub_slice(0, 10)

    def test_nested_sub_slice(self):
        src = MemorySource(b"0123456789")
        sr = SliceReader(src, 0, 10)
        sub1 = sr.sub_slice(2, 6)
        sub2 = sub1.sub_slice(1, 3)
        assert sub2.read(3) == b"345"

    def test_invalid_slice_negative_base(self):
        src = MemorySource(b"0123456789")
        with pytest.raises(IndexError):
            SliceReader(src, -1, 5)

    def test_invalid_slice_exceeds_source(self):
        src = MemorySource(b"0123456789")
        with pytest.raises(IndexError):
            SliceReader(src, 8, 5)


def test_slice_reader_satisfies_archive_like():
    from uasset_read.package import PackageArchive
    from uasset_read.v2.source import MemorySource, SliceReader

    reader = SliceReader(MemorySource(b"abcdef"), 1, 4)
    archive = PackageArchive(reader)
    assert archive.total_size() == 4
    archive.set_byte_swapping(True)
    assert archive.read(2) == b"bc"
    archive.close()
