"""Test corrupted data recovery in FArchive.

Verifies that:
1. Corrupted data produces structured diagnostics (not log-only warnings)
2. Recovery preserves partial/fallback state (never masquerades as success)
3. All 36 samples process without crash
4. Structured diagnostic codes are stable (not dependent on log text)
"""

from pathlib import Path

import pytest

from uasset_read import parse_single
from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.models.diagnostics import StructuredDiagnostic


SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def _get_all_samples():
    """Get all .uasset sample files."""
    if not SAMPLES_DIR.exists():
        return []
    return sorted(SAMPLES_DIR.glob("*.uasset"))


class TestCorruptedFStringRecovery:
    """FString corruption recovery tests."""

    def test_starter_content_bg_cue_parses(self):
        """StarterContent_Starter_Background_Cue has corrupted FString and out-of-range name index."""
        sample = SAMPLES_DIR / "StarterContent_Starter_Background_Cue.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert result.is_success, f"Errors: {result.errors}"
        # Should have diagnostics about the corrupted FString
        diag_messages = [d.error for d in result.diagnostics]
        has_corruption_note = any("null" in m.lower() or "corrupt" in m.lower() or "out of range" in m.lower() for m in diag_messages)
        assert has_corruption_note, f"Expected corruption diagnostics, got: {diag_messages[:5]}"

    def test_structured_diagnostics_present(self):
        """Verify structured diagnostics are collected from archive."""
        sample = SAMPLES_DIR / "StarterContent_Starter_Background_Cue.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert len(result.structured_diagnostics) > 0, "Expected structured diagnostics"

    def test_structured_diagnostic_has_required_fields(self):
        """Verify structured diagnostic has all required fields."""
        sample = SAMPLES_DIR / "StarterContent_Starter_Background_Cue.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        for diag in result.structured_diagnostics:
            assert isinstance(diag, StructuredDiagnostic)
            assert diag.code, "Diagnostic must have a code"
            assert diag.severity in ("warning", "error", "info"), "Invalid severity"
            assert diag.stage, "Diagnostic must have a stage"
            assert isinstance(diag.offset, int), "Offset must be int"


class TestNegativeSerialSizeRecovery:
    """Negative serial_size recovery tests."""

    def test_als_animbp_negative_serial_size(self):
        """ALS_AnimBP has negative serial_size: -5116089176692876519."""
        sample = SAMPLES_DIR / "ALS_AnimBP.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert result.is_success, f"Errors: {result.errors}"

    def test_negative_serial_size_produces_structured_diagnostic(self):
        """Verify negative serial_size produces invalid_serial_size diagnostic."""
        sample = SAMPLES_DIR / "ALS_AnimBP.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        diag = None
        for d in result.structured_diagnostics:
            if d.code == "invalid_serial_size":
                diag = d
                break
        assert diag is not None, "Expected invalid_serial_size structured diagnostic"
        assert diag.fallback == "set_to_zero"


class TestUnknownSerializationControlBits:
    """Unknown serialization control bits recovery tests."""

    def test_mutable_texture_parses(self):
        """MutableSample_GrayLightTextureCube has unknown SerializationControlExtensions bits."""
        sample = SAMPLES_DIR / "MutableSample_GrayLightTextureCube.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        assert result.is_success, f"Errors: {result.errors}"

    def test_unknown_bits_produces_structured_diagnostic(self):
        """Verify unknown bits produce unknown_serialization_control_bits diagnostic."""
        sample = SAMPLES_DIR / "MutableSample_GrayLightTextureCube.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        diag = None
        for d in result.structured_diagnostics:
            if d.code == "unknown_serialization_control_bits":
                diag = d
                break
        assert diag is not None, "Expected unknown_serialization_control_bits structured diagnostic"
        assert diag.fallback == "skipped_subsequent_reads"


class TestAllSamplesProcessWithoutCrash:
    """Verify all 36 samples process without crash."""

    @pytest.mark.parametrize("sample_path", _get_all_samples(), ids=lambda p: p.name)
    def test_sample_parses_without_crash(self, sample_path):
        """Each sample should parse without raising an exception."""
        result = parse_uasset_with_linker(str(sample_path), tolerant=True)
        assert result.is_success or result.status == "partial", (
            f"Sample {sample_path.name} failed: {result.errors}"
        )


class TestDiagnosticCodeNotDependentOnLogText:
    """Verify diagnostic codes are stable and not dependent on log message text."""

    def test_code_stable_across_reparse(self):
        """Same file should produce same diagnostic codes on reparse."""
        sample = SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"
        if not sample.exists():
            pytest.skip("sample not available")

        result1 = parse_uasset_with_linker(str(sample), tolerant=True)
        result2 = parse_uasset_with_linker(str(sample), tolerant=True)

        codes1 = [d.code for d in result1.structured_diagnostics]
        codes2 = [d.code for d in result2.structured_diagnostics]
        assert codes1 == codes2, f"Diagnostic codes differ: {codes1} vs {codes2}"

    def test_code_is_not_empty_string(self):
        """All diagnostic codes must be non-empty strings."""
        sample = SAMPLES_DIR / "ALS_AnimBP.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        for diag in result.structured_diagnostics:
            assert isinstance(diag.code, str)
            assert len(diag.code) > 0, "Diagnostic code must not be empty"

    def test_message_is_human_readable(self):
        """Diagnostic messages should be human-readable strings."""
        sample = SAMPLES_DIR / "ALS_AnimBP.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        for diag in result.structured_diagnostics:
            assert isinstance(diag.message, str)
            assert len(diag.message) > 10, f"Message too short: {diag.message}"


class TestFallbackNeverMasksAsSuccess:
    """Verify that fallback actions never masquerade as success."""

    def test_fstring_all_null_returns_empty_string(self):
        """fstring_all_null should return empty string, not fake content."""
        sample = SAMPLES_DIR / "StarterContent_Starter_Background_Cue.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        # Check that fstring_all_null diagnostics have correct fallback
        for diag in result.structured_diagnostics:
            if diag.code == "fstring_all_null":
                assert diag.fallback == "used_empty_string", (
                    f"fstring_all_null fallback should be 'used_empty_string', got '{diag.fallback}'"
                )

    def test_name_index_out_of_range_returns_none(self):
        """name_index_out_of_range should return 'None', not fake content."""
        sample = SAMPLES_DIR / "ALS_Concrete_Step_01_SoundWave.uasset"
        if not sample.exists():
            pytest.skip("sample not available")
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        for diag in result.structured_diagnostics:
            if diag.code == "name_index_out_of_range":
                assert diag.fallback == "used_default_name", (
                    f"name_index_out_of_range fallback should be 'used_default_name', got '{diag.fallback}'"
                )
