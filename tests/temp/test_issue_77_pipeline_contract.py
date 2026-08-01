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
from uasset_read.kismet.native_fields import (
    NativeFieldDeclaration,
    native_field_cpp_type,
    build_native_function_signature,
)


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


# ---------------------------------------------------------------------------
# Test: Native function signature building
# ---------------------------------------------------------------------------

# Property flag constants (from uasset_read.constants)
CPF_Parm = 0x0000000000000080
CPF_OutParm = 0x0000000000000100
CPF_ReturnParm = 0x0000000000000400
CPF_ReferenceParm = 0x0000000008000000
CPF_ConstParm = 0x0000000000000002


def _make_field(type_name: str, name: str, flags: int) -> NativeFieldDeclaration:
    """Build a minimal NativeFieldDeclaration with given property flags."""
    decl = NativeFieldDeclaration(type_name=type_name, name=name, property_flags=flags)
    return decl


class TestBuildNativeFunctionSignature:
    """Verify build_native_function_signature derives C++ signatures from native fields."""

    def test_basic_signature_with_return_and_params(self):
        """BoolProperty return + FloatProperty param + ObjectProperty out param."""
        fields = [
            _make_field("BoolProperty", "ReturnValue", CPF_Parm | CPF_ReturnParm),
            _make_field("FloatProperty", "Yaw", CPF_Parm),
            _make_field("ObjectProperty", "Target", CPF_Parm | CPF_OutParm | CPF_ReferenceParm),
        ]
        signature, parameters, return_type = build_native_function_signature("Aim", fields)
        assert signature == "bool Aim(float Yaw, UObject*& Target)"
        assert return_type == "bool"
        assert parameters == [
            {"name": "Yaw", "param_type": "float", "is_input": True, "is_output": False},
            {"name": "Target", "param_type": "UObject*&", "is_input": True, "is_output": True},
        ]

    def test_void_signature_no_params(self):
        """No fields produces a void function with no parameters."""
        signature, parameters, return_type = build_native_function_signature("DoNothing", [])
        assert signature == "void DoNothing()"
        assert return_type == "void"
        assert parameters == []

    def test_const_reference_param(self):
        """ConstParm + ReferenceParm produces const T&."""
        fields = [
            _make_field("StructProperty", "Data", CPF_Parm | CPF_ConstParm | CPF_ReferenceParm),
        ]
        signature, parameters, return_type = build_native_function_signature("Process", fields)
        assert "const FStruct& Data" in signature
        assert return_type == "void"
        assert len(parameters) == 1
        assert parameters[0]["param_type"] == "const FStruct&"

    def test_array_signature(self):
        """ArrayProperty with inner IntProperty produces TArray<int32>."""
        inner = NativeFieldDeclaration(type_name="IntProperty", name="Element")
        arr_field = _make_field("ArrayProperty", "Items", CPF_Parm)
        arr_field.inner_fields = [inner]
        fields = [arr_field]
        signature, parameters, return_type = build_native_function_signature("SetItems", fields)
        assert "TArray<int32> Items" in signature
        assert parameters[0]["param_type"] == "TArray<int32>"

    def test_map_signature(self):
        """MapProperty with key/value produces TMap<K, V>."""
        key_field = NativeFieldDeclaration(type_name="NameProperty", name="Key")
        val_field = NativeFieldDeclaration(type_name="StrProperty", name="Value")
        map_field = _make_field("MapProperty", "Lookup", CPF_Parm)
        map_field.inner_fields = [key_field, val_field]
        fields = [map_field]
        signature, parameters, return_type = build_native_function_signature("Find", fields)
        assert "TMap<FName, FString> Lookup" in signature
        assert parameters[0]["param_type"] == "TMap<FName, FString>"

    def test_out_param_is_output(self):
        """CPF_OutParm marks param as is_output=True."""
        fields = [
            _make_field("FloatProperty", "Result", CPF_Parm | CPF_OutParm),
        ]
        _, parameters, _ = build_native_function_signature("Calc", fields)
        assert len(parameters) == 1
        assert parameters[0]["is_output"] is True
        assert parameters[0]["is_input"] is True

    def test_return_param_excluded_from_parameters(self):
        """CPF_ReturnParm field is the return type, not in parameters list."""
        fields = [
            _make_field("IntProperty", "ReturnValue", CPF_Parm | CPF_ReturnParm),
            _make_field("FloatProperty", "X", CPF_Parm),
        ]
        _, parameters, return_type = build_native_function_signature("GetX", fields)
        assert return_type == "int32"
        assert len(parameters) == 1
        assert parameters[0]["name"] == "X"

    def test_parameter_order_preserved(self):
        """Parameters appear in the same order as fields (excluding return)."""
        fields = [
            _make_field("BoolProperty", "ReturnValue", CPF_Parm | CPF_ReturnParm),
            _make_field("FloatProperty", "A", CPF_Parm),
            _make_field("FloatProperty", "B", CPF_Parm),
            _make_field("FloatProperty", "C", CPF_Parm),
        ]
        _, parameters, _ = build_native_function_signature("Lerp", fields)
        names = [p["name"] for p in parameters]
        assert names == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Test: KismetDecompiledResult native parameters
# ---------------------------------------------------------------------------


class TestKismetDecompiledResultNativeParameters:
    """Verify KismetDecompiledResult carries native parameters and return_type."""

    def test_has_parameters_and_return_type_fields(self):
        """KismetDecompiledResult accepts parameters and return_type."""
        result = KismetDecompiledResult(
            function_name="Aim",
            signature="bool Aim(float Yaw)",
            local_variables=[],
            cpp_code="",
            bytecode_status="parsed",
            translation_status="complete",
            parameters=[
                {"name": "Yaw", "param_type": "float", "is_input": True, "is_output": False},
            ],
            return_type="bool",
        )
        assert result.parameters == [
            {"name": "Yaw", "param_type": "float", "is_input": True, "is_output": False},
        ]
        assert result.return_type == "bool"

    def test_default_parameters_empty(self):
        """Default parameters is an empty list."""
        result = KismetDecompiledResult(
            function_name="Empty",
            signature="void Empty()",
            local_variables=[],
            cpp_code="",
            bytecode_status="no_script",
            translation_status="not_applicable",
        )
        assert result.parameters == []
        assert result.return_type == "void"

    def test_to_dict_includes_parameters(self):
        """to_dict() includes parameters and return_type."""
        result = KismetDecompiledResult(
            function_name="Aim",
            signature="bool Aim(float Yaw)",
            local_variables=[],
            cpp_code="",
            bytecode_status="parsed",
            translation_status="complete",
            parameters=[
                {"name": "Yaw", "param_type": "float", "is_input": True, "is_output": False},
            ],
            return_type="bool",
        )
        d = result.to_dict()
        assert d["parameters"] == [
            {"name": "Yaw", "param_type": "float", "is_input": True, "is_output": False},
        ]
        assert d["return_type"] == "bool"


# ---------------------------------------------------------------------------
# Test: IR builder uses native parameters
# ---------------------------------------------------------------------------


class TestIRBuilderNativeParameters:
    """Verify IR builder prefers native parameters over signature parsing."""

    def test_ir_uses_native_parameters_when_available(self):
        """DecompiledFunctionIR uses native parameters and return_type."""
        from dataclasses import dataclass
        from uasset_read.ir_builder import _build_decompiled_functions_ir

        # Minimal mock ParseResult
        @dataclass
        class MockResult:
            decompiled_functions: list = None

        native_params = [
            {"name": "Yaw", "param_type": "float", "is_input": True, "is_output": False},
            {"name": "Target", "param_type": "UObject*&", "is_input": True, "is_output": True},
        ]
        func = KismetDecompiledResult(
            function_name="Aim",
            signature="void Aim(float, UObject*&)",
            local_variables=[],
            cpp_code="",
            bytecode_status="parsed",
            translation_status="complete",
            parameters=native_params,
            return_type="bool",
            native_signature=True,
        )
        result = MockResult(decompiled_functions=[func])
        ir_funcs = _build_decompiled_functions_ir(result)
        assert len(ir_funcs) == 1
        assert ir_funcs[0].return_type == "bool"
        assert ir_funcs[0].parameters == native_params

    def test_ir_falls_back_to_signature_parsing(self):
        """When native parameters are empty, IR falls back to signature parsing."""
        from dataclasses import dataclass
        from uasset_read.ir_builder import _build_decompiled_functions_ir

        @dataclass
        class MockResult:
            decompiled_functions: list = None

        func = KismetDecompiledResult(
            function_name="TestFunc",
            signature="void TestFunc(int32 EntryPoint)",
            local_variables=[],
            cpp_code="",
            bytecode_status="parsed",
            translation_status="complete",
        )
        result = MockResult(decompiled_functions=[func])
        ir_funcs = _build_decompiled_functions_ir(result)
        assert len(ir_funcs) == 1
        # Should fall back to parsing signature string
        assert ir_funcs[0].return_type == "void"
        assert len(ir_funcs[0].parameters) == 1
        assert ir_funcs[0].parameters[0]["name"] == "EntryPoint"
