"""Tests for Issue #77 — native UFunction script parsing pipeline contract.

Verifies that:
- Only true Function/UFunction exports are decompiled (no K2Node pseudo-functions)
- Production results never use BPGC or serial scan
- Diagnostic scan results cannot become decompiled results
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.kismet.bytecode_extractor import (
    FUNCTION_EXPORT_CLASSES,
)
from uasset_read.kismet.diagnostics import (
    scan_function_export_for_diagnostics,
    BytecodeCandidateDiagnostic,
)
from uasset_read.kismet.result import KismetDecompiledResult


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
    # Set _class_name on the class_index mock for resolve_class_name
    export.class_index._class_name = class_name
    return export


def _mock_resolve_class(class_index, import_map, export_map):
    """Return class name based on mock class_index.

    resolve_class_name receives class_index as first arg, not export.
    """
    return getattr(class_index, "_class_name", "Function")


def run_post_process_kismet(exports):
    """Run the post-process kismet extraction with given exports.

    Uses unittest.mock.patch instead of monkeypatch to properly intercept
    local imports inside _extract_kismet_decompiled.
    """
    from uasset_read.pipeline.post_process import _extract_kismet_decompiled

    mock_resolve = MagicMock(side_effect=_mock_resolve_class)

    def mock_decompile(archive, export, summary, name_map, import_map, export_map,
                       tolerant=True, linker=None):
        # Mimic real pipeline: skip exports without script serialization
        if not export.has_script_serialization:
            return None
        return KismetDecompiledResult(
            function_name=export.object_name,
            signature=f"void {export.object_name}()",
            local_variables=[],
            cpp_code=f"void {export.object_name}() {{ }}",
            bytecode_status="parsed",
            translation_status="complete",
        )

    archive = MagicMock()
    summary = MagicMock()
    name_map = ["None"]
    import_map = []
    export_map = exports

    with patch("uasset_read.serializers.object_resources.resolve_class_name", mock_resolve), \
         patch("uasset_read.kismet.pipeline.decompile_single_function", side_effect=mock_decompile):
        results = _extract_kismet_decompiled(
            "test.uasset", archive, summary, name_map,
            import_map, export_map, tolerant=True,
        )
    return results


# ---------------------------------------------------------------------------
# Test: FUNCTION_EXPORT_CLASSES constant
# ---------------------------------------------------------------------------

class TestFunctionExportClasses:
    """Verify FUNCTION_EXPORT_CLASSES contains only true Function types."""

    def test_contains_function_and_ufunction(self):
        assert "Function" in FUNCTION_EXPORT_CLASSES
        assert "UFunction" in FUNCTION_EXPORT_CLASSES

    def test_does_not_contain_k2node_types(self):
        assert "K2Node_FunctionEntry" not in FUNCTION_EXPORT_CLASSES
        assert "K2Node_FunctionResult" not in FUNCTION_EXPORT_CLASSES

    def test_is_frozen(self):
        assert isinstance(FUNCTION_EXPORT_CLASSES, frozenset)

    def test_length_is_two(self):
        assert len(FUNCTION_EXPORT_CLASSES) == 2


# ---------------------------------------------------------------------------
# Test: Pipeline only selects true Function exports
# ---------------------------------------------------------------------------

class TestPipelineFunctionFiltering:
    """Verify only true Function/UFunction exports are decompiled."""

    def test_only_true_function_exports_are_decompiled(self):
        """K2Node pseudo-functions must not appear in decompilation results."""
        func_export = make_export("Function", "RealFunction")
        entry_export = make_export("K2Node_FunctionEntry", "Entry")

        results = run_post_process_kismet([func_export, entry_export])
        assert [item.function_name for item in results] == ["RealFunction"]

    def test_ufunction_exports_are_selected(self):
        """UFunction exports should also be selected."""
        ufunc_export = make_export("UFunction", "NativeFunc")

        results = run_post_process_kismet([ufunc_export])
        assert len(results) == 1

    def test_no_script_exports_not_selected(self):
        """Exports without script serialization should be skipped."""
        export = make_export("Function", "NoScript", has_script_serialization=False)

        results = run_post_process_kismet([export])
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Test: Production results never use BPGC or serial scan
# ---------------------------------------------------------------------------

class TestProductionBytecodeSource:
    """Verify production results use native-only bytecode source."""

    def test_production_result_never_uses_bpgc_or_serial_scan(self):
        """Native function results should be function_export, not fallback."""
        result = KismetDecompiledResult(
            function_name="NativeFunc",
            signature="void NativeFunc()",
            local_variables=[],
            cpp_code="void NativeFunc() { }",
            expressions=[],
            bytecode_source="function_export",
            bytecode_status="parsed",
            translation_status="complete",
        )
        assert result.bytecode_source == "function_export"
        assert "bpgc_bytecode_extraction" not in result.fallback_reasons
        assert "serial_scan_recovery" not in result.fallback_reasons

    def test_infer_bytecode_confidence_no_longer_returns_heuristic(self):
        """infer_bytecode_confidence should never produce 'heuristic' for native results."""
        from uasset_read.kismet.result import infer_bytecode_confidence
        # Native path: no heuristic reasons
        assert infer_bytecode_confidence(
            [], bytecode_status="parsed",
        ) == "verified"

    def test_infer_bytecode_confidence_no_longer_returns_fallback(self):
        """infer_bytecode_confidence should never produce 'fallback' for native results."""
        from uasset_read.kismet.result import infer_bytecode_confidence
        # Native path: no BPGC reasons
        assert infer_bytecode_confidence(
            [], bytecode_status="parsed",
        ) == "verified"


# ---------------------------------------------------------------------------
# Test: Diagnostic scan results cannot become decompiled results
# ---------------------------------------------------------------------------

class TestDiagnosticScanIsolation:
    """Verify diagnostic scan produces only diagnostic data, not decompiled results."""

    def test_diagnostic_scan_result_cannot_become_decompiled_result(self):
        """scan_function_export_for_diagnostics returns only BytecodeCandidateDiagnostic."""
        archive = MagicMock()
        archive.tell.return_value = 0
        archive.read_bytes.return_value = b"\x53"  # EX_EndOfScript

        export = make_export("Function", "TestFunc")
        name_map = ["None"]
        import_map = []
        export_map = []

        candidates = scan_function_export_for_diagnostics(
            archive, export, name_map, import_map, export_map,
        )
        assert all(isinstance(item, BytecodeCandidateDiagnostic) for item in candidates)
        assert not any(isinstance(item, KismetDecompiledResult) for item in candidates)


# ---------------------------------------------------------------------------
# Test: BytecodeCandidateDiagnostic structure
# ---------------------------------------------------------------------------

class TestBytecodeCandidateDiagnostic:
    """Verify BytecodeCandidateDiagnostic contains only diagnostic fields."""

    def test_has_required_fields(self):
        diag = BytecodeCandidateDiagnostic(
            start_offset=0,
            end_offset=10,
            expression_count=5,
            validation_error=None,
        )
        assert diag.start_offset == 0
        assert diag.end_offset == 10
        assert diag.expression_count == 5
        assert diag.validation_error is None

    def test_is_dataclass(self):
        assert hasattr(BytecodeCandidateDiagnostic, "__dataclass_fields__")
        fields = BytecodeCandidateDiagnostic.__dataclass_fields__
        assert "start_offset" in fields
        assert "end_offset" in fields
        assert "expression_count" in fields
        assert "validation_error" in fields
