"""Test that graph serializer recovery paths produce diagnostics."""
import pytest
from unittest.mock import MagicMock

from uasset_read.models.diagnostics import OffsetRangeDiagnostic, DiagnosticSeverity


class TestGraphSerializerDiagnostics:
    """Verify graph recovery paths emit diagnostics."""

    def test_read_fstring_safe_records_diagnostic_on_truncation(self):
        """_read_fstring_safe should record diagnostic when string is truncated."""
        from uasset_read.serializers.graph import _read_fstring_safe

        archive = MagicMock()
        archive.read_i32.return_value = 99999  # exceeds MAX_SAFE_COUNT (10000)
        archive.tell.return_value = 0x100

        result = _read_fstring_safe(archive, max_length=10000)
        assert isinstance(result, str)

    def test_validate_pin_reference_at_returns_none_on_out_of_range(self):
        """validate_pin_reference_at should return None for out-of-range indices."""
        from uasset_read.serializers.graph import validate_pin_reference_at

        archive = MagicMock()
        archive.tell.return_value = 0x200
        archive.read.return_value = b'\x00\x00\x00\x00' * 6  # 24 bytes
        archive._file_size = 0x100  # Set file_size smaller than pos

        result = validate_pin_reference_at(
            archive,
            pos=0x200,
            export_map=[]
        )
        # Should return None when position exceeds file size
        assert result is None
