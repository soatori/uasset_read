"""Tests for Issue #544 — Kismet decompile pipeline crashes on status pair mismatch.

Verifies that:
- decompile_single_function sets translation_status on the success path
- ("parsed", "not_applicable") is never produced (would violate ALLOWED_STATUS_PAIRS)
- no_script and failed paths remain unchanged
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from uasset_read.kismet.result import KismetDecompiledResult, ALLOWED_STATUS_PAIRS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_export(class_name: str, name: str, **overrides) -> MagicMock:
    """Build a minimal ObjectExport mock for pipeline tests."""
    export = MagicMock()
    export.object_name = name
    export.class_index = MagicMock()
    export.has_script_serialization = True
    export.serial_offset = 0
    export.serial_size = 100
    export.script_serialization_start_offset = 0
    export.script_serialization_size = 100
    for k, v in overrides.items():
        setattr(export, k, v)
    export.class_index._class_name = class_name
    return export


def _make_script_result(status: str = "extracted", **overrides) -> MagicMock:
    """Build a mock FunctionScriptReadResult."""
    result = MagicMock()
    result.status = status
    result.script_bytes = b"\x00" * 20  # minimal bytecode
    result.native_fields = []
    for k, v in overrides.items():
        setattr(result, k, v)
    return result


# ---------------------------------------------------------------------------
# Test: Success path sets translation_status
# ---------------------------------------------------------------------------

class TestSuccessPathTranslationStatus:
    """Verify translation_status is set correctly on the success path."""

    def test_success_path_sets_translation_status(self):
        """Success path without warnings should produce translation_status='complete'."""
        from uasset_read.kismet.pipeline import decompile_single_function

        export = make_export("Function", "TestFunc")
        script_result = _make_script_result(status="extracted")
        # Build minimal valid bytecode: just a return token
        script_result.script_bytes = bytes([0x04])  # EX_Return

        with patch(
            "uasset_read.kismet.ufunction_reader.read_ufunction_script",
            return_value=script_result,
        ), patch(
            "uasset_read.kismet.pipeline.parse_bytecode_stream",
            return_value=([], 2),
        ), patch(
            "uasset_read.kismet.pipeline.FunctionBodyBuilder",
        ) as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.to_function_body_structured.return_value = (
                "void TestFunc() {\n    return;\n}"
            )
            # Ensure func_resolver does not inject spurious warnings
            mock_builder._translator._func_resolver = None
            result = decompile_single_function(
                MagicMock(), export, None, [], [], 0,
            )

        assert result is not None
        assert result.bytecode_status == "parsed"
        assert result.translation_status == "complete"

    def test_success_path_with_warnings_sets_partial(self):
        """Success path with warnings should produce translation_status='partial'."""
        from uasset_read.kismet.pipeline import decompile_single_function

        export = make_export("Function", "TestFunc")
        script_result = _make_script_result(status="extracted")
        script_result.script_bytes = bytes([0x04])  # EX_Return

        with patch(
            "uasset_read.kismet.ufunction_reader.read_ufunction_script",
            return_value=script_result,
        ), patch(
            "uasset_read.kismet.pipeline.parse_bytecode_stream",
            return_value=([], 2),
        ), patch(
            "uasset_read.kismet.pipeline.FunctionBodyBuilder",
        ) as MockBuilder:
            mock_builder = MockBuilder.return_value
            # C++ code containing warning triggers
            mock_builder.to_function_body_structured.return_value = (
                "void TestFunc() {\n    /* unknown: 0xFF */\n}"
            )
            result = decompile_single_function(
                MagicMock(), export, None, [], [], 0,
            )

        assert result is not None
        assert result.bytecode_status == "parsed"
        assert result.translation_status == "partial"
        assert any("unsupported expression tokens" in w for w in result.warnings)

    def test_no_value_error_on_success_path(self):
        """The success path must not raise ValueError from status pair validation."""
        from uasset_read.kismet.pipeline import decompile_single_function

        export = make_export("Function", "SafeFunc")
        script_result = _make_script_result(status="extracted")
        script_result.script_bytes = bytes([0x04])  # EX_Return

        with patch(
            "uasset_read.kismet.ufunction_reader.read_ufunction_script",
            return_value=script_result,
        ), patch(
            "uasset_read.kismet.pipeline.parse_bytecode_stream",
            return_value=([], 2),
        ), patch(
            "uasset_read.kismet.pipeline.FunctionBodyBuilder",
        ) as MockBuilder:
            mock_builder = MockBuilder.return_value
            mock_builder.to_function_body_structured.return_value = (
                "void SafeFunc() { return; }"
            )
            # Should not raise ValueError
            result = decompile_single_function(
                MagicMock(), export, None, [], [], 0,
            )

        assert result is not None
        assert result.translation_status in ("complete", "partial")


# ---------------------------------------------------------------------------
# Test: Regression guards for unchanged paths
# ---------------------------------------------------------------------------

class TestUnchangedPaths:
    """Regression guards for no_script and failed paths."""

    def test_no_script_path_unchanged(self):
        """('no_script', 'not_applicable') must still work."""
        result = KismetDecompiledResult(
            function_name="NoScriptFunc",
            signature="void NoScriptFunc()",
            local_variables=[],
            cpp_code="",
            bytecode_status="no_script",
            translation_status="not_applicable",
        )
        assert result.bytecode_status == "no_script"
        assert result.translation_status == "not_applicable"

    def test_failed_path_unchanged(self):
        """('failed', 'not_applicable') must still work."""
        result = KismetDecompiledResult(
            function_name="FailedFunc",
            signature="void FailedFunc()",
            local_variables=[],
            cpp_code="",
            bytecode_status="failed",
            translation_status="not_applicable",
        )
        assert result.bytecode_status == "failed"
        assert result.translation_status == "not_applicable"


# ---------------------------------------------------------------------------
# Test: ALLOWED_STATUS_PAIRS coverage
# ---------------------------------------------------------------------------

class TestAllowedStatusPairsCoverage:
    """Verify all allowed pairs can construct a result, and disallowed pair raises."""

    def test_all_allowed_pairs_constructible(self):
        """Every pair in ALLOWED_STATUS_PAIRS should produce a valid result."""
        pairs = list(ALLOWED_STATUS_PAIRS)
        assert len(pairs) == 5
        for bytecode_status, translation_status in pairs:
            result = KismetDecompiledResult(
                function_name="TestFunc",
                signature="void TestFunc()",
                local_variables=[],
                cpp_code="",
                bytecode_status=bytecode_status,
                translation_status=translation_status,
            )
            assert result.bytecode_status == bytecode_status
            assert result.translation_status == translation_status

    def test_disallowed_pair_raises(self):
        """('parsed', 'not_applicable') must raise ValueError."""
        with pytest.raises(ValueError, match="disallowed status pair"):
            KismetDecompiledResult(
                function_name="BadFunc",
                signature="void BadFunc()",
                local_variables=[],
                cpp_code="",
                bytecode_status="parsed",
                translation_status="not_applicable",
            )
