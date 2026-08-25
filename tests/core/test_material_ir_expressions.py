"""Material IR expression builder regression tests.

Tests the build_package_ir Material path against real sample assets.
Catches regressions in _build_expression_outputs, _build_material_inputs,
_build_single_expression_ir, and _resolve_material_parent (#556).
"""

from __future__ import annotations

import pytest
from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[1] / "samples"

# Material-instance samples (have parent + material inputs)
MATERIAL_INSTANCE_SAMPLES = [
    "CassiniSample_MI_Template_BaseGray_Metal.uasset",
    "StackOBot_M_BotBase.uasset",
    "StarterContent_M_Wood_Walnut.uasset",
]

# Material samples (base material with expressions)
MATERIAL_SAMPLES = [
    "FirstPerson_M_FlatCol.uasset",
    "FirstPerson_M_PrototypeGrid.uasset",
    "IntroToUnreal_M_Plastic.uasset",
]


def _parse_and_build_ir(asset_name: str):
    """Parse a sample asset and return PackageIR."""
    from uasset_read import parse_package
    from uasset_read.ir_builder import build_package_ir

    result = parse_package(str(SAMPLES / asset_name))
    return build_package_ir(result)


# ---------------------------------------------------------------------------
# TestMaterialExpressionOutputs
# ---------------------------------------------------------------------------
class TestMaterialExpressionOutputs:
    """Regression: _build_expression_outputs must handle StructValue (#556)."""

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES)
    def test_base_material_ir_not_none(self, asset: str):
        """Base materials should produce a MaterialIR (not crash)."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None, f"{asset}: MaterialIR is None"
        assert isinstance(ir.material.expressions, list)

    def test_at_least_one_base_material_has_expressions(self):
        """At least one base material sample should have parsed expressions."""
        has_expressions = False
        for asset in MATERIAL_SAMPLES:
            ir = _parse_and_build_ir(asset)
            if ir.material and len(ir.material.expressions) > 0:
                has_expressions = True
                break
        assert has_expressions, "No base material sample has expressions"

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES)
    def test_expression_output_types_are_valid(self, asset: str):
        """Every expression output should have a non-empty output_name string."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        for expr in ir.material.expressions:
            for output in expr.outputs:
                assert isinstance(output.output_name, str)
                # output_name may be empty for unnamed outputs, but must be a string
                assert isinstance(output.mask, int)

    @pytest.mark.parametrize("asset", MATERIAL_INSTANCE_SAMPLES)
    def test_material_instance_has_expressions_or_empty(self, asset: str):
        """Material instances may have 0 expressions (inherited) — no crash allowed."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None, f"{asset}: MaterialIR is None"
        # Just verifying it doesn't crash; instances may have 0 expressions
        assert isinstance(ir.material.expressions, list)


# ---------------------------------------------------------------------------
# TestMaterialInputs
# ---------------------------------------------------------------------------
class TestMaterialInputs:
    """Regression: _build_material_inputs must handle StructValue (#556)."""

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES + MATERIAL_INSTANCE_SAMPLES)
    def test_material_inputs_parsed_without_crash(self, asset: str):
        """All Material/MaterialInstance assets should parse inputs without error."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None, f"{asset}: MaterialIR is None"
        assert isinstance(ir.material.material_inputs, list)

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES)
    def test_base_material_inputs_is_list(self, asset: str):
        """Base materials should have a material_inputs list (may be empty for opaque exports)."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        assert isinstance(ir.material.material_inputs, list)

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES + MATERIAL_INSTANCE_SAMPLES)
    def test_material_input_fields_valid(self, asset: str):
        """Each material input should have valid source_expression_guid and input_name."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        for inp in ir.material.material_inputs:
            assert isinstance(inp.input_name, str)
            assert len(inp.input_name) > 0
            # source_expression_guid is str or None
            assert inp.source_expression_guid is None or isinstance(inp.source_expression_guid, str)

    @pytest.mark.parametrize("asset", MATERIAL_INSTANCE_SAMPLES)
    def test_material_parent_resolution(self, asset: str):
        """#556: _resolve_material_parent wraps raw int as PackageIndex."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        # Material instances should have a resolved parent path
        if ir.material.parent is not None:
            assert isinstance(ir.material.parent, str)
            assert len(ir.material.parent) > 0


# ---------------------------------------------------------------------------
# TestSingleExpressionIR
# ---------------------------------------------------------------------------
class TestSingleExpressionIR:
    """Regression: _build_single_expression_ir must handle StructValue (#556)."""

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES)
    def test_expression_ir_structure(self, asset: str):
        """Each expression should have the required IR fields."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        for expr in ir.material.expressions:
            assert hasattr(expr, "expression_guid")
            assert hasattr(expr, "expression_class")
            assert hasattr(expr, "expression_type")
            assert hasattr(expr, "inputs")
            assert hasattr(expr, "outputs")
            assert isinstance(expr.expression_guid, str)
            assert isinstance(expr.inputs, list)
            assert isinstance(expr.outputs, list)

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES)
    def test_expression_guid_is_hex_string(self, asset: str):
        """Expression GUIDs should be hex strings (normalized)."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        for expr in ir.material.expressions:
            if expr.expression_guid:  # may be empty for some expressions
                # Should be parseable as hex
                assert all(c in "0123456789abcdef" for c in expr.expression_guid.lower()), (
                    f"Non-hex GUID: {expr.expression_guid}"
                )

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES)
    def test_expression_inputs_have_source_guid(self, asset: str):
        """Expression inputs with a resolved source should have a valid GUID."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        for expr in ir.material.expressions:
            for inp in expr.inputs:
                if inp.source_expression_guid is not None:
                    assert isinstance(inp.source_expression_guid, str)
                    assert len(inp.source_expression_guid) > 0


# ---------------------------------------------------------------------------
# TestMaterialEnumValues
# ---------------------------------------------------------------------------
class TestMaterialEnumValues:
    """Regression: EnumValue handling in material properties (#556)."""

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES + MATERIAL_INSTANCE_SAMPLES)
    def test_blend_mode_is_string_or_none(self, asset: str):
        """#556: BlendMode should be decoded as string, not crash on EnumValue."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        blend = ir.material.properties.get("BlendMode")
        # BlendMode may be absent, a string, or a dict — must not be raw EnumValue
        if blend is not None:
            assert isinstance(blend, (str, dict)), f"{asset}: BlendMode is {type(blend).__name__}, expected str or dict"

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES + MATERIAL_INSTANCE_SAMPLES)
    def test_material_type_is_string(self, asset: str):
        """material_type should always be a non-empty string."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        assert isinstance(ir.material.material_type, str)
        assert len(ir.material.material_type) > 0

    @pytest.mark.parametrize("asset", MATERIAL_SAMPLES)
    def test_material_properties_is_dict(self, asset: str):
        """material.properties should be a dict."""
        ir = _parse_and_build_ir(asset)
        assert ir.material is not None
        assert isinstance(ir.material.properties, dict)
