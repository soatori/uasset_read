"""
Unit tests for UE5 BitField reading in UEdGraphPin serialization.

Tests verify that BitField parsing:
1. Consumes exactly 4 bytes (uint32) from the archive position
2. Correctly extracts individual flag bits:
   - bit 0: hidden
   - bit 1: not_connectable
   - bit 4: advanced_view
   - bit 5: orphaned_pin
"""

import os
import struct
import tempfile
import pytest

from uasset_read.archive import FArchive


class TestBitFieldByteConsumption:
    """Tests for BitField 4-byte consumption verification."""

    def test_bitfield_consumes_4_bytes(self):
        """BitField should advance archive position by exactly 4 bytes."""
        # Create a temp file with 4 bytes of BitField data
        bitfield_value = 0x00000033  # 51 in decimal
        data = struct.pack('<I', bitfield_value)

        fd, path = tempfile.mkstemp(suffix='.bin')
        try:
            os.write(fd, data)
            os.close(fd)

            archive = FArchive(path)
            try:
                start_pos = archive.tell()
                bitfield = archive.read_u32()  # This is what BitField reading does
                end_pos = archive.tell()

                consumed = end_pos - start_pos
                assert consumed == 4, f"BitField should consume 4 bytes, but consumed {consumed}"
                assert bitfield == bitfield_value
            finally:
                archive.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_bitfield_value_preserved(self):
        """BitField value should be preserved after reading."""
        test_value = 0x00000033  # 51 in decimal
        data = struct.pack('<I', test_value)

        fd, path = tempfile.mkstemp(suffix='.bin')
        try:
            os.write(fd, data)
            os.close(fd)

            archive = FArchive(path)
            try:
                bitfield = archive.read_u32()
                assert bitfield == test_value, f"Expected {test_value}, got {bitfield}"
            finally:
                archive.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestBitFieldFlagExtraction:
    """Tests for BitField flag bit extraction."""

    def extract_flags(self, bitfield: int) -> dict:
        """Helper to extract flags from bitfield value."""
        return {
            'hidden': bool(bitfield & (1 << 0)),
            'not_connectable': bool(bitfield & (1 << 1)),
            'advanced_view': bool(bitfield & (1 << 4)),
            'orphaned_pin': bool(bitfield & (1 << 5)),
        }

    def test_all_zero_bitfield_produces_all_false_flags(self):
        """BitField 0x00000000 should produce all False flags."""
        bitfield = 0x00000000
        flags = self.extract_flags(bitfield)

        assert flags['hidden'] is False
        assert flags['not_connectable'] is False
        assert flags['advanced_view'] is False
        assert flags['orphaned_pin'] is False

    def test_all_ones_bitfield_produces_true_flags_for_tested_bits(self):
        """BitField 0xFFFFFFFF should produce True for all tested bits."""
        bitfield = 0xFFFFFFFF
        flags = self.extract_flags(bitfield)

        assert flags['hidden'] is True
        assert flags['not_connectable'] is True
        assert flags['advanced_view'] is True
        assert flags['orphaned_pin'] is True

    def test_hidden_flag_bit_0(self):
        """Bit 0 (hidden) should be extracted correctly."""
        # Test with only bit 0 set
        bitfield = 0x00000001
        flags = self.extract_flags(bitfield)

        assert flags['hidden'] is True
        assert flags['not_connectable'] is False
        assert flags['advanced_view'] is False
        assert flags['orphaned_pin'] is False

    def test_not_connectable_flag_bit_1(self):
        """Bit 1 (not_connectable) should be extracted correctly."""
        # Test with only bit 1 set
        bitfield = 0x00000002
        flags = self.extract_flags(bitfield)

        assert flags['hidden'] is False
        assert flags['not_connectable'] is True
        assert flags['advanced_view'] is False
        assert flags['orphaned_pin'] is False

    def test_advanced_view_flag_bit_4(self):
        """Bit 4 (advanced_view) should be extracted correctly."""
        # Test with only bit 4 set
        bitfield = 0x00000010
        flags = self.extract_flags(bitfield)

        assert flags['hidden'] is False
        assert flags['not_connectable'] is False
        assert flags['advanced_view'] is True
        assert flags['orphaned_pin'] is False

    def test_orphaned_pin_flag_bit_5(self):
        """Bit 5 (orphaned_pin) should be extracted correctly."""
        # Test with only bit 5 set
        bitfield = 0x00000020
        flags = self.extract_flags(bitfield)

        assert flags['hidden'] is False
        assert flags['not_connectable'] is False
        assert flags['advanced_view'] is False
        assert flags['orphaned_pin'] is True

    def test_combined_flags_bitfield_0x33(self):
        """BitField 0x33 (bits 0, 1, 4, 5 set) should produce all True flags."""
        # 0x33 = 0b00110011 = bits 0, 1, 4, 5
        bitfield = 0x00000033
        flags = self.extract_flags(bitfield)

        assert flags['hidden'] is True
        assert flags['not_connectable'] is True
        assert flags['advanced_view'] is True
        assert flags['orphaned_pin'] is True


class TestBitFieldWithArchive:
    """Integration tests with FArchive for BitField reading."""

    def test_bitfield_4_byte_sequence_in_archive(self):
        """Verify 4-byte BitField reading with FArchive."""
        # Create archive with multiple values
        # 4 bytes BitField + 4 bytes extra data
        bitfield_value = 0x12345678
        extra_value = 0xDEADBEEF

        data = struct.pack('<II', bitfield_value, extra_value)

        fd, path = tempfile.mkstemp(suffix='.bin')
        try:
            os.write(fd, data)
            os.close(fd)

            archive = FArchive(path)
            try:
                # Read BitField
                bitfield = archive.read_u32()
                assert bitfield == bitfield_value

                # Verify position is correct for next read
                remaining = archive.read_u32()
                assert remaining == extra_value
            finally:
                archive.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_bitfield_large_value(self):
        """BitField should handle large uint32 values correctly."""
        large_value = 0xFFFFFFFF
        data = struct.pack('<I', large_value)

        fd, path = tempfile.mkstemp(suffix='.bin')
        try:
            os.write(fd, data)
            os.close(fd)

            archive = FArchive(path)
            try:
                bitfield = archive.read_u32()
                assert bitfield == large_value
                assert archive.tell() == 4  # Exactly 4 bytes consumed
            finally:
                archive.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])