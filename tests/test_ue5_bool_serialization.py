"""Unit tests for UE bool serialization in FArchive.

Tests verify that:
- read_bool() consumes exactly 4 bytes (uint32) - 标准 FArchive bool
- read_bool_1byte() consumes exactly 1 byte (uint8) - UE5 紧凑 bool
- Both methods return correct True/False for various values

Phase 44a: 恢复 UE 标准 bool（4-byte），添加 read_bool_1byte() 用于特定结构。
"""
import struct
import tempfile
import os

import pytest

from uasset_read.archive import FArchive


class TestUE5BoolSerialization:
    """Tests for UE bool serialization (4-byte standard + 1-byte compact)."""

    def test_read_bool_consumes_four_bytes(self):
        """read_bool() should consume exactly 4 bytes (standard FArchive bool)."""
        # Create a temp file with 4 bytes
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(struct.pack('<I', 0x00000001))  # 4 bytes: value 1
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            start_pos = archive.tell()
            result = archive.read_bool()
            end_pos = archive.tell()

            assert end_pos - start_pos == 4, f"read_bool() consumed {end_pos - start_pos} bytes, expected 4"
            assert result == True
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_read_bool_1byte_consumes_one_byte(self):
        """read_bool_1byte() should consume exactly 1 byte (UE5 compact bool)."""
        # Create a temp file with a single byte
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(struct.pack('<B', 0x01))  # 1 byte: value 0x01
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            start_pos = archive.tell()
            result = archive.read_bool_1byte()
            end_pos = archive.tell()

            assert end_pos - start_pos == 1, f"read_bool_1byte() consumed {end_pos - start_pos} bytes, expected 1"
            assert result == True
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_read_bool_returns_false_for_zero(self):
        """read_bool() should return False for 0x00000000."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(struct.pack('<I', 0x00000000))
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            result = archive.read_bool()
            assert result == False, "read_bool(0x00000000) should return False"
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_read_bool_1byte_returns_false_for_zero(self):
        """read_bool_1byte() should return False for 0x00."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(struct.pack('<B', 0x00))
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            result = archive.read_bool_1byte()
            assert result == False, "read_bool_1byte(0x00) should return False"
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_read_bool_1byte_returns_true_for_one(self):
        """read_bool_1byte() should return True for 0x01."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(struct.pack('<B', 0x01))
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            result = archive.read_bool_1byte()
            assert result == True, "read_bool_1byte(0x01) should return True"
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_read_bool_1byte_returns_true_for_ff(self):
        """read_bool_1byte() should return True for 0xFF (any non-zero value)."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(struct.pack('<B', 0xFF))
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            result = archive.read_bool_1byte()
            assert result == True, "read_bool_1byte(0xFF) should return True"
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_read_bool_1byte_sequence(self):
        """read_bool_1byte() should correctly read a sequence of bools."""
        # Create a file with 5 bool values: False, True, True, False, True
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(struct.pack('<BBBBB', 0x00, 0x01, 0xFF, 0x00, 0x42))
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            results = [archive.read_bool_1byte() for _ in range(5)]
            expected = [False, True, True, False, True]

            assert results == expected, f"Expected {expected}, got {results}"
            archive.close()
        finally:
            os.unlink(temp_path)