"""Tests for diagnostic aggregator."""
from uasset_read.semantic.diagnostics import DiagnosticAggregator
from uasset_read.models.ir import DiagnosticsDataIR


class TestDiagnosticAggregator:
    def test_empty(self):
        agg = DiagnosticAggregator()
        diags = agg.build()
        assert diags == ()

    def test_add_manual(self):
        agg = DiagnosticAggregator()
        agg.add("warning", "PARTIAL_PARSE", "Some fields skipped")
        diags = agg.build()
        assert len(diags) == 1
        assert diags[0].severity == "warning"
        assert diags[0].code == "PARTIAL_PARSE"
        assert diags[0].message == "Some fields skipped"

    def test_from_ir_with_errors(self):
        ir_data = DiagnosticsDataIR(
            errors=["Parse failed"],
            warnings=["Deprecated field"],
            status="partial",
            status_message="Export partial",
            status_code="EXPORT_PARTIAL",
        )
        agg = DiagnosticAggregator()
        agg.from_ir(ir_data)
        diags = agg.build()
        assert len(diags) == 2
        assert diags[0].severity == "error"
        assert diags[0].code == "PARSE_ERROR"
        assert diags[1].severity == "warning"

    def test_from_ir_empty(self):
        ir_data = DiagnosticsDataIR()
        agg = DiagnosticAggregator()
        agg.from_ir(ir_data)
        diags = agg.build()
        assert diags == ()

    def test_deduplicates(self):
        agg = DiagnosticAggregator()
        agg.add("warning", "X", "msg")
        agg.add("warning", "X", "msg")
        diags = agg.build()
        assert len(diags) == 1
