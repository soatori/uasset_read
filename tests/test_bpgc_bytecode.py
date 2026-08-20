"""Tests for BPGC bytecode extraction with sentinel fallback."""

import struct
import pytest
from uasset_read.kismet.bpgc_bytecode import (
    _parse_cooked_bytecode_buffer,
    _parse_cooked_bytecode_buffer_sentinel_fallback,
    _find_next_sentinel,
    BPGCExtractionMetrics,
    BytecodeConfidenceLevel,
    _END_OF_SCRIPT,
    _COOKED_END_SENTINEL,
)


def _make_bpgc_header(num_functions: int, ss_size: int = 0, bb_size: int = 0) -> bytes:
    """Helper to create a BPGC header."""
    return struct.pack("<ii", bb_size, ss_size) + struct.pack("<I", num_functions)


def _make_size_array(sizes: list[int]) -> bytes:
    """Helper to create a function size array."""
    return b"".join(struct.pack("<i", sz) for sz in sizes)


def _make_bytecode_buffer(data: bytes, sentinel: int = _END_OF_SCRIPT) -> bytes:
    """Helper to create a bytecode buffer with sentinel."""
    return data + bytes([sentinel])


class TestFindNextSentinel:
    """Tests for _find_next_sentinel helper."""

    def test_finds_ex_end_of_script(self):
        data = b"\x00\x00\x00\x53\x00\x00"
        assert _find_next_sentinel(data, 0) == 3

    def test_finds_cooked_sentinel(self):
        data = b"\x00\x00\x00\xdd\x00\x00"
        assert _find_next_sentinel(data, 0) == 3

    def test_finds_sentinel_at_start(self):
        data = b"\x53\x00\x00"
        assert _find_next_sentinel(data, 0) == 0

    def test_returns_minus_one_when_not_found(self):
        data = b"\x00\x00\x00\x00\x00\x00"
        assert _find_next_sentinel(data, 0) == -1

    def test_respects_start_offset(self):
        data = b"\x53\x00\x00\x53\x00\x00"
        assert _find_next_sentinel(data, 1) == 3

    def test_empty_data(self):
        assert _find_next_sentinel(b"", 0) == -1


class TestParseCookedBytecodeBuffer:
    """Tests for primary size-based parsing."""

    def test_empty_data(self):
        buffers, metrics = _parse_cooked_bytecode_buffer(b"")
        assert buffers == []
        assert metrics.early_exit is True
        assert metrics.exit_reason == "data_too_short_for_header"

    def test_zero_functions(self):
        header = _make_bpgc_header(num_functions=0)
        buffers, metrics = _parse_cooked_bytecode_buffer(header)
        assert buffers == []
        assert metrics.early_exit is True
        assert metrics.exit_reason == "zero_functions_declared"

    def test_single_function(self):
        bytecode = b"\x01\x02\x03\x53"  # 4 bytes with sentinel
        header = _make_bpgc_header(num_functions=1)
        sizes = _make_size_array([len(bytecode)])
        data = header + sizes + bytecode

        buffers, metrics = _parse_cooked_bytecode_buffer(data)
        assert len(buffers) == 1
        assert buffers[0] == bytecode
        assert metrics.extracted_buffer_count == 1
        assert metrics.confidence == BytecodeConfidenceLevel.HIGH

    def test_multiple_functions(self):
        buf1 = b"\x01\x02\x53"
        buf2 = b"\x03\x04\x05\xdd"
        header = _make_bpgc_header(num_functions=2)
        sizes = _make_size_array([len(buf1), len(buf2)])
        data = header + sizes + buf1 + buf2

        buffers, metrics = _parse_cooked_bytecode_buffer(data)
        assert len(buffers) == 2
        assert buffers[0] == buf1
        assert buffers[1] == buf2
        assert metrics.extracted_buffer_count == 2

    def test_size_exceeds_data_truncates(self):
        header = _make_bpgc_header(num_functions=1)
        sizes = _make_size_array([100])  # Request 100 bytes but only provide 4
        data = header + sizes + b"\x01\x02\x03\x53"

        buffers, metrics = _parse_cooked_bytecode_buffer(data)
        # Should truncate to available data
        assert metrics.truncated_buffer_count > 0

    def test_sentinel_mismatch_logged(self):
        bytecode = b"\x01\x02\x03\xff"  # Wrong sentinel
        header = _make_bpgc_header(num_functions=1)
        sizes = _make_size_array([len(bytecode)])
        data = header + sizes + bytecode

        buffers, metrics = _parse_cooked_bytecode_buffer(data)
        assert metrics.sentinel_mismatch_count == 1
        assert metrics.confidence == BytecodeConfidenceLevel.MEDIUM


class TestSentinelFallback:
    """Tests for sentinel-based fallback parsing."""

    def test_empty_data(self):
        buffers, metrics = _parse_cooked_bytecode_buffer_sentinel_fallback(b"")
        assert buffers == []
        assert metrics.early_exit is True
        assert metrics.used_sentinel_fallback is True

    def test_sentinel_scan_finds_buffers(self):
        # Create data with sentinel markers but invalid header
        # Header: bb_size=0, ss_size=0, num_functions=999 (invalid)
        header = struct.pack("<ii", 0, 0) + struct.pack("<I", 999)
        buf1 = b"\x01\x02\x53"  # Ends with EX_EndOfScript
        buf2 = b"\x03\x04\xdd"  # Ends with Cooked sentinel
        data = header + buf1 + buf2

        buffers, metrics = _parse_cooked_bytecode_buffer_sentinel_fallback(data)
        assert metrics.used_sentinel_fallback is True
        # Should find buffers via sentinel scan
        assert len(buffers) >= 1

    def test_used_sentinel_fallback_flag(self):
        header = _make_bpgc_header(num_functions=0)
        buffers, metrics = _parse_cooked_bytecode_buffer_sentinel_fallback(header)
        assert metrics.used_sentinel_fallback is True


class TestConfidenceCalculation:
    """Tests for BPGCExtractionMetrics confidence calculation."""

    def test_high_confidence(self):
        m = BPGCExtractionMetrics()
        m.extracted_buffer_count = 5
        m.empty_buffer_count = 0
        m.sentinel_mismatch_count = 0
        m.truncated_buffer_count = 0
        m.early_exit = False
        m.mapping_mismatch = False
        m.used_sentinel_fallback = False
        assert m.confidence == BytecodeConfidenceLevel.HIGH

    def test_medium_confidence_from_sentinel_fallback(self):
        m = BPGCExtractionMetrics()
        m.extracted_buffer_count = 5
        m.used_sentinel_fallback = True
        assert m.confidence == BytecodeConfidenceLevel.MEDIUM

    def test_medium_confidence_from_sentinel_mismatch(self):
        m = BPGCExtractionMetrics()
        m.extracted_buffer_count = 5
        m.sentinel_mismatch_count = 1
        assert m.confidence == BytecodeConfidenceLevel.MEDIUM

    def test_low_confidence_from_truncation(self):
        m = BPGCExtractionMetrics()
        m.extracted_buffer_count = 5
        m.truncated_buffer_count = 1
        assert m.confidence == BytecodeConfidenceLevel.LOW

    def test_unrecoverable_when_no_buffers(self):
        m = BPGCExtractionMetrics()
        m.extracted_buffer_count = 0
        assert m.confidence == BytecodeConfidenceLevel.UNRECOVERABLE


class TestMetricsToDict:
    """Tests for BPGCExtractionMetrics.to_dict()."""

    def test_includes_sentinel_fallback_flag(self):
        m = BPGCExtractionMetrics()
        m.used_sentinel_fallback = True
        d = m.to_dict()
        assert d["used_sentinel_fallback"] is True

    def test_omits_zero_values(self):
        m = BPGCExtractionMetrics()
        d = m.to_dict()
        assert "empty_buffer_count" not in d
        assert "sentinel_mismatch_count" not in d
