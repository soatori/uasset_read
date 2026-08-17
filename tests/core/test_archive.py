"""FArchive binary reader tests.

Tests the FArchive class: seek, read, boundary validation, byte swapping.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError


class TestFArchiveBasicIO:
    """Basic read/seek/tell operations."""

    def test_open_and_close(self, tmp_path: Path):
        """FArchive opens and closes without error."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 16)
        archive = FArchive(str(f))
        assert archive.total_size() == 16
        archive.close()

    def test_read_bytes(self, tmp_path: Path):
        """Read returns exact bytes."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x01\x02\x03\x04")
        archive = FArchive(str(f))
        data = archive.read(4)
        assert data == b"\x01\x02\x03\x04"
        archive.close()

    def test_seek_and_tell(self, tmp_path: Path):
        """Seek moves the position; tell reports it."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 32)
        archive = FArchive(str(f))
        archive.seek(16)
        assert archive.tell() == 16
        archive.seek(0)
        assert archive.tell() == 0
        archive.close()

    def test_skip(self, tmp_path: Path):
        """Skip advances the position by n bytes."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 32)
        archive = FArchive(str(f))
        archive.seek(4)
        archive.skip(8)
        assert archive.tell() == 12
        archive.close()

    def test_read_all(self, tmp_path: Path):
        """Read all bytes sequentially."""
        data = bytes(range(256))
        f = tmp_path / "test.bin"
        f.write_bytes(data)
        archive = FArchive(str(f))
        result = archive.read(256)
        assert result == data
        archive.close()

    def test_context_manager(self, tmp_path: Path):
        """FArchive can be used as a context manager."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 8)
        with FArchive(str(f)) as archive:
            assert archive.total_size() == 8


class TestFArchiveBoundaryValidation:
    """Boundary and validation checks."""

    def test_read_beyond_eof_raises(self, tmp_path: Path):
        """Reading past EOF raises ParseError."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 4)
        archive = FArchive(str(f))
        with pytest.raises(ParseError):
            archive.read(8)
        archive.close()

    def test_read_negative_size_raises(self, tmp_path: Path):
        """Reading negative size raises ParseError."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 4)
        archive = FArchive(str(f))
        with pytest.raises(ParseError):
            archive.read(-1)
        archive.close()

    def test_seek_negative_raises(self, tmp_path: Path):
        """Seeking to negative offset raises ParseError."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 4)
        archive = FArchive(str(f))
        with pytest.raises(ParseError):
            archive.seek(-1)
        archive.close()

    def test_seek_beyond_eof_raises(self, tmp_path: Path):
        """Seeking past EOF raises ParseError."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 4)
        archive = FArchive(str(f))
        with pytest.raises(ParseError):
            archive.seek(100)
        archive.close()

    def test_validate_size_negative(self, tmp_path: Path):
        """validate_size rejects negative sizes."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 16)
        archive = FArchive(str(f))
        assert archive.validate_size(-1, tolerant=True) is False
        archive.close()

    def test_validate_size_exceeds_remaining_tolerant(self, tmp_path: Path):
        """validate_size returns False in tolerant mode when size exceeds remaining."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 16)
        archive = FArchive(str(f))
        assert archive.validate_size(100, tolerant=True) is False
        archive.close()

    def test_validate_size_exceeds_remaining_strict(self, tmp_path: Path):
        """validate_size raises in strict mode when size exceeds remaining."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 16)
        archive = FArchive(str(f))
        with pytest.raises(ParseError):
            archive.validate_size(100, tolerant=False)
        archive.close()


class TestFArchiveByteSwapping:
    """Byte swapping functionality."""

    def test_byte_swapping_default_off(self, tmp_path: Path):
        """Byte swapping is off by default."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 4)
        archive = FArchive(str(f))
        assert archive.is_byte_swapping is False
        archive.close()

    def test_set_byte_swapping(self, tmp_path: Path):
        """set_byte_swapping toggles the flag."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * 4)
        archive = FArchive(str(f))
        archive.set_byte_swapping(True)
        assert archive.is_byte_swapping is True
        archive.set_byte_swapping(False)
        assert archive.is_byte_swapping is False
        archive.close()


class TestFArchiveWithRealSample:
    """FArchive operations on a real .uasset sample."""

    def test_open_real_sample(self, samples_dir: Path):
        """Open a real .uasset and verify basic properties."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        if not sample.exists():
            pytest.skip("Sample not found")

        archive = FArchive(str(sample))
        assert archive.total_size() > 0
        assert archive.tell() == 0

        # Read first 4 bytes (magic number area)
        magic = archive.read(4)
        assert len(magic) == 4
        archive.close()

    def test_seek_around_real_sample(self, samples_dir: Path):
        """Seek to various positions in a real sample."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        if not sample.exists():
            pytest.skip("Sample not found")

        archive = FArchive(str(sample))
        size = archive.total_size()

        # Seek to middle
        archive.seek(size // 2)
        assert archive.tell() == size // 2

        # Seek to start
        archive.seek(0)
        assert archive.tell() == 0

        # Seek to near end
        archive.seek(size - 4)
        assert archive.tell() == size - 4
        archive.close()
