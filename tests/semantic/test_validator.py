"""Tests for semantic IR validator."""
from uasset_read.semantic.validator import validate_semantic_ir
from uasset_read.semantic.ir import (
    SemanticIR, AssetMeta, ReferenceEntry, CoverageInfo,
    DiagnosticEntry, ContentNode,
)
from uasset_read.semantic.kinds import AssetKind


def _make_ir(**kwargs) -> SemanticIR:
    defaults = dict(
        format="uasset_read.asset_semantic",
        format_version="1.0.0",
        mode="standard",
        asset=AssetMeta(
            kind=AssetKind.RESOURCE,
            class_name="Texture2D",
            object_name="T_Default",
        ),
        references=(),
        content=ContentNode(key="root", children=()),
        coverage=CoverageInfo(
            fields_expected=5,
            fields_parsed=5,
            coverage_pct=100.0,
            unparsed_fields=(),
        ),
        diagnostics=(),
    )
    defaults.update(kwargs)
    return SemanticIR(**defaults)


class TestValidateSemanticIR:
    def test_valid_ir(self):
        ir = _make_ir()
        errors = validate_semantic_ir(ir)
        assert errors == []

    def test_wrong_format(self):
        ir = _make_ir(format="wrong")
        errors = validate_semantic_ir(ir)
        assert any("format" in e.lower() for e in errors)

    def test_wrong_version(self):
        ir = _make_ir(format_version="2.0.0")
        errors = validate_semantic_ir(ir)
        assert any("version" in e.lower() for e in errors)

    def test_invalid_mode(self):
        ir = _make_ir(mode="verbose")
        errors = validate_semantic_ir(ir)
        assert any("mode" in e.lower() for e in errors)

    def test_empty_class_name(self):
        ir = _make_ir(asset=AssetMeta(kind=AssetKind.OPAQUE, class_name="", object_name="X"))
        errors = validate_semantic_ir(ir)
        assert any("class_name" in e.lower() for e in errors)

    def test_coverage_pct_out_of_range(self):
        ir = _make_ir(coverage=CoverageInfo(
            fields_expected=1, fields_parsed=1, coverage_pct=101.0, unparsed_fields=(),
        ))
        errors = validate_semantic_ir(ir)
        assert any("coverage" in e.lower() for e in errors)

    def test_invalid_diagnostic_severity(self):
        ir = _make_ir(diagnostics=(
            DiagnosticEntry(severity="critical", code="X", message="msg"),
        ))
        errors = validate_semantic_ir(ir)
        assert any("severity" in e.lower() for e in errors)
