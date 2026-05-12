"""Unit tests for FText b_has_culture bool serialization in UE5 vs UE4.

Tests verify that:
- read_ftext_with_history(ue5_mode=True) consumes exactly 1 byte for b_has_culture
- read_ftext_with_history(ue5_mode=False) consumes exactly 4 bytes for b_has_culture
- Total consumption for FText history_type=0xFF: UE5=6 bytes, UE4=9 bytes
- Other history_types (0, custom) are unaffected by ue5_mode
"""
import struct
import tempfile
import os

import pytest

from uasset_read.archive import FArchive
from uasset_read.serializers.graph import read_ftext_with_history


class TestUE5FTextSerialization:
    """Tests for FText b_has_culture bool serialization."""

    def test_ftext_none_ue5_mode_consumes_one_byte_for_bool(self):
        """FText with history_type=0xFF (None) should consume 1 byte for b_has_culture in UE5 mode."""
        # FText None format: 4 bytes flags + 1 byte history_type + 1 byte b_has_culture
        # Total: 6 bytes (when b_has_culture=False, no culture string follows)
        data = struct.pack('<I', 0x00000000)  # flags (4 bytes)
        data += struct.pack('<B', 0xFF)       # history_type = None (1 byte)
        data += struct.pack('<B', 0x00)       # b_has_culture = False (1 byte for UE5)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(data)
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            # Read flags and history_type first (to match the call pattern in read_ue_graph_pin)
            flags = archive.read_i32()  # 4 bytes
            history_type = archive.read_u8()  # 1 byte

            start_pos = archive.tell()
            read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=True)
            end_pos = archive.tell()

            # b_has_culture should have consumed exactly 1 byte
            consumed = end_pos - start_pos
            assert consumed == 1, f"UE5 FText b_has_culture consumed {consumed} bytes, expected 1"
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_ftext_none_ue4_mode_consumes_four_bytes_for_bool(self):
        """FText with history_type=0xFF (None) should consume 4 bytes for b_has_culture in UE4 mode."""
        # FText None format for UE4: 4 bytes flags + 1 byte history_type + 4 bytes b_has_culture
        # Total: 9 bytes (when b_has_culture=False, no culture string follows)
        data = struct.pack('<I', 0x00000000)  # flags (4 bytes)
        data += struct.pack('<B', 0xFF)       # history_type = None (1 byte)
        data += struct.pack('<I', 0x00000000) # b_has_culture = False (4 bytes for UE4)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(data)
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            # Read flags and history_type first
            flags = archive.read_i32()  # 4 bytes
            history_type = archive.read_u8()  # 1 byte

            start_pos = archive.tell()
            read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=False)
            end_pos = archive.tell()

            # b_has_culture should have consumed exactly 4 bytes
            consumed = end_pos - start_pos
            assert consumed == 4, f"UE4 FText b_has_culture consumed {consumed} bytes, expected 4"
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_ftext_none_total_consumption_ue5(self):
        """Total FText consumption for history_type=0xFF should be 6 bytes in UE5 mode."""
        # Including the flags + history_type that are read before the function
        data = struct.pack('<I', 0x00000000)  # flags (4 bytes)
        data += struct.pack('<B', 0xFF)       # history_type = None (1 byte)
        data += struct.pack('<B', 0x00)       # b_has_culture = False (1 byte)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(data)
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            total_start = archive.tell()

            # Read all FText components
            flags = archive.read_i32()
            history_type = archive.read_u8()
            read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=True)

            total_end = archive.tell()
            total_consumed = total_end - total_start

            # Total: 4 (flags) + 1 (history_type) + 1 (b_has_culture) = 6 bytes
            assert total_consumed == 6, f"Total UE5 FText consumed {total_consumed} bytes, expected 6"
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_ftext_none_total_consumption_ue4(self):
        """Total FText consumption for history_type=0xFF should be 9 bytes in UE4 mode."""
        # Including the flags + history_type that are read before the function
        data = struct.pack('<I', 0x00000000)  # flags (4 bytes)
        data += struct.pack('<B', 0xFF)       # history_type = None (1 byte)
        data += struct.pack('<I', 0x00000000) # b_has_culture = False (4 bytes)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(data)
            temp_path = f.name

        try:
            archive = FArchive(temp_path)
            total_start = archive.tell()

            # Read all FText components
            flags = archive.read_i32()
            history_type = archive.read_u8()
            read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=False)

            total_end = archive.tell()
            total_consumed = total_end - total_start

            # Total: 4 (flags) + 1 (history_type) + 4 (b_has_culture) = 9 bytes
            assert total_consumed == 9, f"Total UE4 FText consumed {total_consumed} bytes, expected 9"
            archive.close()
        finally:
            os.unlink(temp_path)

    def test_ftext_base_unaffected_by_ue5_mode(self):
        """FText with history_type=0 (Base) should be unaffected by ue5_mode."""
        # FText Base format: 3 FStrings (namespace, key, source_string)
        # Each FString: 4 bytes length + data bytes
        # For empty strings: length=0, no data bytes
        data = struct.pack('<I', 0x00000000)  # flags (4 bytes)
        data += struct.pack('<B', 0x00)       # history_type = Base (1 byte)
        # 3 empty FStrings: each is length=0 (4 bytes)
        data += struct.pack('<I', 0x00000000)  # namespace length
        data += struct.pack('<I', 0x00000000)  # key length
        data += struct.pack('<I', 0x00000000)  # source_string length

        # Same data should work in both modes
        for ue5_mode in [True, False]:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
                f.write(data)
                temp_path = f.name

            try:
                archive = FArchive(temp_path)
                flags = archive.read_i32()
                history_type = archive.read_u8()

                start_pos = archive.tell()
                read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=ue5_mode)
                end_pos = archive.tell()

                consumed = end_pos - start_pos
                # For Base type, ue5_mode should not affect consumption
                # 3 empty FStrings = 12 bytes (3 * 4 bytes length)
                assert consumed == 12, f"FText Base consumed {consumed} bytes (ue5_mode={ue5_mode}), expected 12"
                archive.close()
            finally:
                os.unlink(temp_path)

    def test_ftext_custom_unaffected_by_ue5_mode(self):
        """FText with custom history_type should be unaffected by ue5_mode."""
        # FText Custom format: up to 5 FStrings
        # history_type 1-254 indicates number of history entries
        data = struct.pack('<I', 0x00000000)  # flags (4 bytes)
        data += struct.pack('<B', 0x02)       # history_type = 2 (custom)
        # 2 empty FStrings for this custom type
        data += struct.pack('<I', 0x00000000)  # history[0] length
        data += struct.pack('<I', 0x00000000)  # history[1] length

        # Same data should work in both modes
        for ue5_mode in [True, False]:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
                f.write(data)
                temp_path = f.name

            try:
                archive = FArchive(temp_path)
                flags = archive.read_i32()
                history_type = archive.read_u8()

                start_pos = archive.tell()
                read_ftext_with_history(archive, history_type, tolerant=True, ue5_mode=ue5_mode)
                end_pos = archive.tell()

                consumed = end_pos - start_pos
                # For Custom type, ue5_mode should not affect consumption
                # 2 empty FStrings = 8 bytes (2 * 4 bytes length)
                assert consumed == 8, f"FText Custom consumed {consumed} bytes (ue5_mode={ue5_mode}), expected 8"
                archive.close()
            finally:
                os.unlink(temp_path)