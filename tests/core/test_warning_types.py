# tests/temp/test_warning_types.py
"""Per-warning-type regression tests for #507.

Each test uses a real sample that triggers a specific warning type in tolerant mode.
Tests verify: (1) parse completes, (2) expected structured diagnostic is produced,
(3) diagnostic has stable code, (4) output is valid JSON.
"""

import json
from pathlib import Path

import pytest

from uasset_read import parse_single
from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.models.diagnostics import (
    DIAGNOSTIC_CODE_NAME_INDEX_OUT_OF_RANGE,
    DIAGNOSTIC_CODE_FSTRING_ALL_NULL,
    DIAGNOSTIC_CODE_FSTRING_LENGTH_EXCEEDS_LIMIT,
    DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE,
    DIAGNOSTIC_CODE_UNKNOWN_SERIALIZATION_CONTROL_BITS,
)

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def _parse_sample(name):
    """Parse a sample and return parsed JSON data."""
    sample = SAMPLES_DIR / name
    if not sample.exists():
        pytest.skip(f"sample {name} not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    return json.loads(output)


def _find_structured_diagnostic(structured_diags, code):
    """Find a structured diagnostic by stable code."""
    for diag in structured_diags:
        if diag.code == code:
            return diag
    return None


def _find_diagnostic(data, pattern):
    """Find a diagnostic matching the given pattern string."""
    for diag in data.get("diagnostics", []):
        msg = diag.get("message", "")
        if pattern.lower() in msg.lower():
            return diag
    return None


class TestNameIndexOutOfRange:
    """FName index exceeds name_map length."""

    def test_structured_diagnostic_code(self):
        """Verify structured diagnostic has stable code name_index_out_of_range."""
        sample = SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        diag = _find_structured_diagnostic(result.structured_diagnostics, DIAGNOSTIC_CODE_NAME_INDEX_OUT_OF_RANGE)
        assert diag is not None, f"Expected structured diagnostic with code {DIAGNOSTIC_CODE_NAME_INDEX_OUT_OF_RANGE}"
        assert diag.code == DIAGNOSTIC_CODE_NAME_INDEX_OUT_OF_RANGE
        assert diag.stage == "read_name"
        assert diag.severity == "warning"
        assert diag.fallback == "used_default_name"

    def test_parse_completes_with_out_of_range_name(self):
        """Parse should complete without exception in tolerant mode."""
        data = _parse_sample("ALS_Concrete_Step_01_SoundWave.uasset")
        assert data["status"]["parse"] in ("complete", "partial")


class TestHugeFStringLength:
    """FString length exceeds MAX_FSTRING_LENGTH."""

    def test_structured_diagnostic_code(self):
        """Verify structured diagnostic has stable code fstring_length_exceeds_limit."""
        sample = SAMPLES_DIR / "ALS_Mannequin_Skeleton.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        diag = _find_structured_diagnostic(result.structured_diagnostics, DIAGNOSTIC_CODE_FSTRING_LENGTH_EXCEEDS_LIMIT)
        assert diag is not None, f"Expected structured diagnostic with code {DIAGNOSTIC_CODE_FSTRING_LENGTH_EXCEEDS_LIMIT}"
        assert diag.code == DIAGNOSTIC_CODE_FSTRING_LENGTH_EXCEEDS_LIMIT
        assert diag.stage in ("read_fstring", "read_utf8_string")
        assert diag.severity == "warning"
        assert diag.fallback == "used_empty_string"

    def test_parse_completes_with_huge_fstring(self):
        """Parse should complete without exception in tolerant mode."""
        data = _parse_sample("ALS_Mannequin_Skeleton.uasset")
        assert data["status"]["parse"] in ("complete", "partial")


class TestFStringAllNull:
    """FString contains all null characters."""

    def test_structured_diagnostic_code(self):
        """Verify structured diagnostic has stable code fstring_all_null."""
        sample = SAMPLES_DIR / "ALS_Mannequin_Skeleton.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        diag = _find_structured_diagnostic(result.structured_diagnostics, DIAGNOSTIC_CODE_FSTRING_ALL_NULL)
        assert diag is not None, f"Expected structured diagnostic with code {DIAGNOSTIC_CODE_FSTRING_ALL_NULL}"
        assert diag.code == DIAGNOSTIC_CODE_FSTRING_ALL_NULL
        assert diag.stage in ("read_fstring", "read_utf8_string")
        assert diag.severity == "warning"
        assert diag.fallback == "used_empty_string"


class TestUnknownSerializationBits:
    """SerializationControlExtensions has unknown bits."""

    def test_structured_diagnostic_code(self):
        """Verify structured diagnostic has stable code unknown_serialization_control_bits."""
        sample = SAMPLES_DIR / "MutableSample_GrayLightTextureCube.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        diag = _find_structured_diagnostic(result.structured_diagnostics, DIAGNOSTIC_CODE_UNKNOWN_SERIALIZATION_CONTROL_BITS)
        assert diag is not None, f"Expected structured diagnostic with code {DIAGNOSTIC_CODE_UNKNOWN_SERIALIZATION_CONTROL_BITS}"
        assert diag.code == DIAGNOSTIC_CODE_UNKNOWN_SERIALIZATION_CONTROL_BITS
        assert diag.stage == "parse_properties"
        assert diag.severity == "warning"
        assert diag.fallback == "skipped_subsequent_reads"

    def test_parse_completes_with_unknown_bits(self):
        """Parse should complete without exception in tolerant mode."""
        data = _parse_sample("MutableSample_GrayLightTextureCube.uasset")
        assert data["status"]["parse"] in ("complete", "partial")


class TestInvalidSerialSize:
    """serial_size is negative or unreasonably large."""

    def test_structured_diagnostic_code(self):
        """Verify structured diagnostic has stable code invalid_serial_size."""
        sample = SAMPLES_DIR / "ALS_AnimBP.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        diag = _find_structured_diagnostic(result.structured_diagnostics, DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE)
        assert diag is not None, f"Expected structured diagnostic with code {DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE}"
        assert diag.code == DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE
        assert diag.stage == "read_export_map"
        assert diag.severity == "warning"
        assert diag.fallback == "set_to_zero"


class TestCorruptedFStringRecovery:
    """FName recovery adjusts offset for corrupted data."""

    def test_parse_completes_with_recovery(self):
        """Parse should complete without exception in tolerant mode."""
        data = _parse_sample("ALS_AnimBP.uasset")
        assert data["status"]["parse"] in ("complete", "partial")


class TestDiagnosticCodeStability:
    """Verify diagnostic codes are stable across multiple parses."""

    def test_same_code_on_reparse(self):
        """Parsing the same file twice should produce the same diagnostic codes."""
        sample = SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"
        if not sample.exists():
            pytest.skip("sample not available")

        result1 = parse_uasset_with_linker(str(sample), tolerant=True)
        result2 = parse_uasset_with_linker(str(sample), tolerant=True)

        codes1 = {d.code for d in result1.structured_diagnostics}
        codes2 = {d.code for d in result2.structured_diagnostics}
        assert codes1 == codes2, f"Diagnostic codes differ: {codes1} vs {codes2}"

    def test_diagnostic_to_dict(self):
        """Verify StructuredDiagnostic.to_dict() produces JSON-compatible output."""
        from uasset_read.models.diagnostics import StructuredDiagnostic

        diag = StructuredDiagnostic(
            code="test_code",
            severity="warning",
            asset="test.uasset",
            stage="test_stage",
            offset=100,
            raw_value=-1,
            ue_version="5.4",
            fallback="used_default",
            message="Test message",
        )
        d = diag.to_dict()
        assert isinstance(d, dict)
        assert d["code"] == "test_code"
        assert d["severity"] == "warning"
        assert d["offset"] == 100
        assert d["raw_value"] == -1
        # Verify it's JSON-serializable
        json.dumps(d)
