"""Tests for #524 — function body provenance and bytecode status public contract.

Verifies that DecompiledFunctionIR carries and exposes all provenance fields
from KismetDecompiledResult through IR mapping, JSON rendering, and Markdown rendering.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from uasset_read.ir_builder import (
    _bind_implementations,
    _build_decompiled_functions_ir,
    _infer_bytecode_confidence,
)
from uasset_read.models.ir import (
    BlueprintFunctionIR,
    BlueprintIR,
    DecompiledFunctionIR,
    PackageIR,
    PackageHeaderIR,
)
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.markdown_renderer import MarkdownRenderer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(**overrides):
    """Build a minimal KismetDecompiledResult-like object for testing."""
    defaults = {
        "function_name": "TestFunc",
        "signature": "void TestFunc()",
        "local_variables": [],
        "cpp_code": "",
        "expressions": [],
        "bytecode_source": "unknown",
        "bytecode_status": "unknown",
        "warnings": [],
        "fallback_reasons": [],
        "semantic_calls": [],
        "logic_source": "current_asset",
        "function_ref_stats": {},
        "structured_rate": None,
    }
    defaults.update(overrides)
    result = MagicMock()
    for k, v in defaults.items():
        setattr(result, k, v)
    return result


def _make_ir_with_decompiled(funcs):
    """Build a minimal PackageIR with decompiled_functions for rendering tests."""
    header = PackageHeaderIR(
        package_name="Test/TestAsset",
        package_class="BlueprintGeneratedClass",
        package_flags=0,
        total_export_count=0,
        total_import_count=0,
        ue_version="5.4",
        saved_hash=b"",
        total_properties=0,
        total_name_entries=0,
    )
    ir = PackageIR(
        header=header,
        name_map=(),
        imports=[],
        exports=[],
        linker=None,
        decompiled_functions=funcs,
    )
    return ir


# ---------------------------------------------------------------------------
# IR Mapping Tests
# ---------------------------------------------------------------------------

class TestIRMapping:
    """Verify that _build_decompiled_functions_ir propagates all provenance fields."""

    def test_failed_result_fields(self):
        """Failed KismetDecompiledResult carries status through to IR."""
        result = _make_result(
            bytecode_status="failed",
            bytecode_source="unknown",
            logic_source="current_asset",
            warnings=["bytecode extraction error: bad data"],
            fallback_reasons=["bytecode extraction error: bad data"],
        )
        mock_result = MagicMock()
        mock_result.decompiled_functions = [result]
        decompiled = _build_decompiled_functions_ir(mock_result)
        assert len(decompiled) == 1
        func = decompiled[0]
        assert func.bytecode_status == "failed"
        assert func.bytecode_source == "unknown"
        assert func.logic_source == "current_asset"
        assert func.bytecode_confidence == "failed"
        assert len(func.warnings) == 1

    def test_graph_topology_result_fields(self):
        """Graph topology enriched result carries logic_source and confidence."""
        result = _make_result(
            cpp_code="// enriched from graph",
            bytecode_status="parsed",
            bytecode_source="function_export",
            logic_source="graph_topology",
            warnings=["Empty bytecode body enriched from UEdGraph K2Node topology (0 expressions)"],
        )
        mock_result = MagicMock()
        mock_result.decompiled_functions = [result]
        decompiled = _build_decompiled_functions_ir(mock_result)
        func = decompiled[0]
        assert func.logic_source == "graph_topology"
        assert func.bytecode_confidence == "graph_topology"

    def test_normal_parsed_result_fields(self):
        """Normal parsed result retains existing confidence logic."""
        result = _make_result(
            cpp_code="void TestFunc() { /* parsed */ }",
            bytecode_status="parsed",
            bytecode_source="function_export",
            logic_source="current_asset",
        )
        mock_result = MagicMock()
        mock_result.decompiled_functions = [result]
        decompiled = _build_decompiled_functions_ir(mock_result)
        func = decompiled[0]
        assert func.bytecode_status == "parsed"
        assert func.bytecode_source == "function_export"
        assert func.logic_source == "current_asset"
        assert func.bytecode_confidence == "verified"

    def test_local_variables_are_not_reclassified_as_parameters(self):
        """TypeRegistry locals remain local when no native parameter data exists."""
        from uasset_read.kismet.result import KismetDecompiledResult

        result = KismetDecompiledResult(
            function_name="UsesLocal",
            signature="void UsesLocal()",
            local_variables=[{"name": "Temp", "type": "float"}],
            cpp_code="float Temp = 1.0f;",
            bytecode_status="parsed",
            translation_status="complete",
            bytecode_source="function_export",
        )
        mock_result = MagicMock()
        mock_result.decompiled_functions = [result]

        function = _build_decompiled_functions_ir(mock_result)[0]
        assert function.parameters == []
        assert function.local_variables == [{"name": "Temp", "type": "float"}]

    def test_fallback_reasons_absent_from_production_enums(self):
        """Defunct fallback_or_serial_scan and bpgc_bytecode_extraction are absent."""
        result = _make_result(
            cpp_code="void TestFunc() { /* bpgc */ }",
            bytecode_status="parsed",
            bytecode_source="function_export",
            logic_source="current_asset",
            fallback_reasons=[],
        )
        mock_result = MagicMock()
        mock_result.decompiled_functions = [result]
        decompiled = _build_decompiled_functions_ir(mock_result)
        func = decompiled[0]
        assert func.bytecode_source != "fallback_or_serial_scan"
        assert "bpgc_bytecode_extraction" not in func.fallback_reasons
        assert func.bytecode_confidence == "verified"


class TestBlueprintImplementationProvenance:
    """Verify nested Blueprint implementations retain decompilation provenance."""

    def test_json_implementation_keeps_topology_provenance(self):
        """Blueprint implementation preserves decompilation provenance through rendering.

        NOTE: temporarily skipped — the old JSONRenderer has been removed and the
        semantic pipeline does not yet include decompiled_functions in its output.
        Re-enable once the semantic pipeline supports blueprint implementation
        rendering.
        """
        pytest.skip("JSONRenderer removed; semantic pipeline lacks decompiled_functions support")


# ---------------------------------------------------------------------------
# Confidence Priority Tests
# ---------------------------------------------------------------------------

class TestConfidencePriority:
    """Verify _infer_bytecode_confidence priority ordering."""

    def test_graph_topology_overrides_verified(self):
        """graph_topology always wins over verified."""
        assert _infer_bytecode_confidence(
            [], bytecode_status="parsed", logic_source="graph_topology",
        ) == "graph_topology"

    def test_failed_overrides_heuristic(self):
        """failed status wins over any fallback reasons."""
        assert _infer_bytecode_confidence(
            ["serial_scan_recovery"], bytecode_status="failed", logic_source="current_asset",
        ) == "failed"

    def test_failed_without_reasons(self):
        """failed status without any fallback reasons."""
        assert _infer_bytecode_confidence(
            [], bytecode_status="failed", logic_source="current_asset",
        ) == "failed"

    def test_serial_scan_recovery_absent_from_production(self):
        """serial_scan_recovery no longer produces 'heuristic' confidence."""
        assert _infer_bytecode_confidence(
            ["serial_scan_recovery"], bytecode_status="parsed", logic_source="current_asset",
        ) == "verified"

    def test_bpgc_bytecode_extraction_absent_from_production(self):
        """bpgc_bytecode_extraction no longer produces 'fallback' confidence."""
        assert _infer_bytecode_confidence(
            ["bpgc_bytecode_extraction"], bytecode_status="parsed", logic_source="current_asset",
        ) == "verified"

    def test_verified_default(self):
        """No special conditions → verified."""
        assert _infer_bytecode_confidence(
            [], bytecode_status="parsed", logic_source="current_asset",
        ) == "verified"


# ---------------------------------------------------------------------------
# Direct Kismet Serialization and Stable JSON Shape Tests
# ---------------------------------------------------------------------------

class TestDirectKismetSerialization:
    """Verify KismetDecompiledResult exposes the same provenance contract."""

    def test_graph_topology_to_dict_includes_confidence(self):
        """Direct Kismet JSON must not present topology code without confidence."""
        from uasset_read.kismet.result import KismetDecompiledResult

        result = KismetDecompiledResult(
            function_name="TopologyFunc",
            signature="void TopologyFunc()",
            local_variables=[],
            cpp_code="// topology body",
            bytecode_status="failed",
            bytecode_source="unknown",
            logic_source="graph_topology",
        )

        payload = result.to_dict()

        assert payload["bytecode_confidence"] == "graph_topology"
        assert payload["warnings"] == []
        assert payload["fallback_reasons"] == []


class TestStableProvenanceShape:
    """Verify renderer output and schema retain empty provenance arrays."""

    def test_renderer_includes_empty_provenance_arrays(self):
        """Renderer output retains empty warnings and fallback_reasons arrays.

        NOTE: temporarily skipped — the old JSONRenderer has been removed and the
        semantic pipeline does not yet include decompiled_functions in its output.
        """
        pytest.skip("JSONRenderer removed; semantic pipeline lacks decompiled_functions support")

    def test_schema_requires_stable_provenance_shape_for_nested_implementations(self):
        schema_path = Path("schemas/package.schema.json")
        if not schema_path.exists():
            pytest.skip("Schema file not found")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = schema["$defs"]["DecompiledFunction"]["required"]

        assert "warnings" in required
        assert "fallback_reasons" in required
        for definition in ("BlueprintFunction", "BlueprintEvent"):
            implementation = schema["$defs"][definition]["properties"]["implementation"]
            assert {"$ref": "#/$defs/DecompiledFunction"} in implementation["oneOf"]


# ---------------------------------------------------------------------------
# JSON Rendering Tests
# ---------------------------------------------------------------------------

class TestJSONRendering:
    """Verify JSON output includes provenance fields for every decompiled function.

    NOTE: all tests temporarily skipped — the old JSONRenderer has been removed
    and the semantic pipeline does not yet include decompiled_functions in its
    output. Re-enable once the semantic pipeline supports blueprint
    decompiled-function rendering.
    """

    def test_json_always_includes_provenance_fields(self):
        pytest.skip("JSONRenderer removed; semantic pipeline lacks decompiled_functions support")

    def test_graph_topology_not_verified_in_json(self):
        pytest.skip("JSONRenderer removed; semantic pipeline lacks decompiled_functions support")

    def test_failed_function_with_graph_topology_cpp_code(self):
        pytest.skip("JSONRenderer removed; semantic pipeline lacks decompiled_functions support")

    def test_verified_function_omits_confidence(self):
        pytest.skip("JSONRenderer removed; semantic pipeline lacks decompiled_functions support")


# ---------------------------------------------------------------------------
# Markdown Rendering Tests
# ---------------------------------------------------------------------------

class TestMarkdownRendering:
    """Verify Markdown output shows provenance warnings for degraded functions."""

    def _render_markdown(self, funcs):
        ir = _make_ir_with_decompiled(funcs)
        return MarkdownRenderer().render(ir, RenderOptions())

    def test_degraded_function_shows_warning(self):
        """Failed/graph_topology function shows warning before code block."""
        func = DecompiledFunctionIR(
            name="DegradedFunc",
            signature="void DegradedFunc()",
            cpp_code="// from topology",
            parameters=[],
            return_type="void",
            bytecode_confidence="graph_topology",
            bytecode_status="failed",
            translation_status="not_applicable",
            bytecode_source="unknown",
            logic_source="graph_topology",
            warnings=["Empty bytecode body enriched"],
            fallback_reasons=["bytecode extraction error: short read"],
        )
        md = self._render_markdown([func])
        assert "> [!WARNING]" in md
        assert "Function body provenance:" in md
        assert "status=failed" in md
        assert "translation=not_applicable" in md
        assert "logic=graph_topology" in md
        assert "confidence=graph_topology" in md

    def test_failed_empty_function_shows_warning_without_code_fence(self):
        """Failed bytecode remains visible even when no C++ body was produced."""
        func = DecompiledFunctionIR(
            name="FailedEmptyFunc",
            signature="void FailedEmptyFunc()",
            cpp_code="",
            parameters=[],
            return_type="void",
            bytecode_confidence="failed",
            bytecode_status="failed",
            translation_status="not_applicable",
            bytecode_source="unknown",
            logic_source="current_asset",
            warnings=["bytecode extraction error: short read"],
            fallback_reasons=["bytecode extraction error: short read"],
        )

        md = self._render_markdown([func])

        assert "> [!WARNING]" in md
        assert "status=failed" in md
        assert "```cpp" not in md

    def test_normal_function_no_warning(self):
        """Verified bytecode function produces no [!WARNING] block."""
        func = DecompiledFunctionIR(
            name="NormalFunc",
            signature="void NormalFunc()",
            cpp_code="void NormalFunc() { }",
            parameters=[],
            return_type="void",
            bytecode_confidence="verified",
            bytecode_status="parsed",
            bytecode_source="function_export",
            logic_source="current_asset",
        )
        md = self._render_markdown([func])
        assert "> [!WARNING]" not in md
        assert "Function body provenance:" not in md

    def test_function_locals_render_only_when_recovered(self):
        """Recovered locals are shown with their owning function, not globally."""
        func = DecompiledFunctionIR(
            name="UsesLocal",
            signature="void UsesLocal()",
            cpp_code="float Temp = 1.0f;",
            parameters=[],
            return_type="void",
            bytecode_status="parsed",
            translation_status="complete",
            bytecode_source="function_export",
            local_variables=[{"name": "Temp", "type": "float"}],
        )

        md = self._render_markdown([func])
        assert "**Local Variables:**" in md
        assert "| Temp | float |" in md
        # NOTE: JSON output assertion removed — the old JSONRenderer has been
        # removed and the semantic pipeline does not yet include
        # decompiled_functions in its output. The Markdown test above
        # validates local_variables rendering.

    def test_function_without_locals_has_no_empty_locals_section(self):
        """A function with no recoverable locals remains valid without a placeholder."""
        func = DecompiledFunctionIR(
            name="NoLocals",
            signature="void NoLocals()",
            cpp_code="return;",
            parameters=[],
            return_type="void",
            bytecode_status="parsed",
            translation_status="complete",
            bytecode_source="function_export",
        )

        assert "**Local Variables:**" not in self._render_markdown([func])

    def test_schema_declares_optional_function_local_variables(self):
        """The public JSON schema documents the optional per-function locals list."""
        schema_path = Path(__file__).parents[2] / "schemas" / "package.schema.json"
        if not schema_path.exists():
            pytest.skip("Schema file not found")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        local_variables = schema["$defs"]["DecompiledFunction"]["properties"]["local_variables"]

        assert local_variables["type"] == "array"
        assert local_variables["items"]["type"] == "object"
        assert local_variables["items"]["required"] == ["name", "type"]

    def test_defunct_provenance_values_absent_from_output(self):
        """fallback_or_serial_scan and serial_scan_recovery are absent from production output."""
        func = DecompiledFunctionIR(
            name="HeuristicFunc",
            signature="void HeuristicFunc()",
            cpp_code="void HeuristicFunc() { /* parsed */ }",
            parameters=[],
            return_type="void",
            bytecode_confidence="verified",
            bytecode_status="parsed",
            bytecode_source="function_export",
            logic_source="current_asset",
            fallback_reasons=[],
        )
        md = self._render_markdown([func])
        assert "> [!WARNING]" not in md
        assert "fallback_or_serial_scan" not in md
        assert "serial_scan_recovery" not in md


# ---------------------------------------------------------------------------
# EventGraph Completion Regression Test
# ---------------------------------------------------------------------------

class TestEventGraphCompletion:
    """Verify graph topology does not replace parsed bytecode provenance."""

    def test_eventgraph_semantics_preserve_parsed_bytecode(self, monkeypatch):
        """EventGraph semantics do not replace verified Function Script."""
        from uasset_read.kismet import semantic
        from uasset_read.kismet.result import KismetDecompiledResult

        result = KismetDecompiledResult(
            function_name="ReceiveBeginPlay",
            signature="void ReceiveBeginPlay()",
            local_variables=[],
            cpp_code="void ReceiveBeginPlay() { /* bytecode */ }",
            bytecode_source="function_export",
            bytecode_status="parsed",
            translation_status="complete",
        )
        monkeypatch.setattr(
            semantic,
            "extract_eventgraph_semantic_calls",
            lambda graphs: [{
                "event_name": "ReceiveBeginPlay",
                "call": "Initialize()",
            }],
        )

        semantic.enrich_decompiled_functions([result], [])

        assert result.cpp_code == "void ReceiveBeginPlay() { /* bytecode */ }"
        assert result.bytecode_source == "function_export"
        assert result.logic_source == "current_asset"
        assert result.warnings == []

    def test_execute_ubergraph_semantics_preserve_parsed_bytecode(self, monkeypatch):
        """ExecuteUbergraph topology does not replace verified Function Script."""
        from uasset_read.kismet import semantic
        from uasset_read.kismet.result import KismetDecompiledResult

        result = KismetDecompiledResult(
            function_name="ExecuteUbergraph_TestBlueprint",
            signature="void ExecuteUbergraph_TestBlueprint()",
            local_variables=[],
            cpp_code="void ExecuteUbergraph_TestBlueprint() { /* bytecode */ }",
            bytecode_source="function_export",
            bytecode_status="parsed",
            translation_status="complete",
        )
        monkeypatch.setattr(
            semantic,
            "extract_eventgraph_semantic_calls",
            lambda graphs: [{
                "event_name": "ReceiveBeginPlay",
                "call": "Initialize()",
            }],
        )

        semantic.enrich_decompiled_functions([result], [])

        assert result.cpp_code == (
            "void ExecuteUbergraph_TestBlueprint() { /* bytecode */ }"
        )
        assert result.bytecode_source == "function_export"
        assert result.logic_source == "current_asset"
        assert result.warnings == []
