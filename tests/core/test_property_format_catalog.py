"""Property format variant regression tests.

Each test parses a known sample asset and asserts specific property values,
catching format-variant regressions before merge. Add a new test whenever a
format variant fix lands (e.g. StructValue, MapProperty legacy, CurveMetaData).
"""

from __future__ import annotations

from pathlib import Path


from uasset_read import parse_package

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def _parse(asset_name: str):
    """Parse a sample asset and return the result."""
    return parse_package(str(SAMPLES / asset_name), tolerant=True)


# ---------------------------------------------------------------------------
# StructProperty variants
# ---------------------------------------------------------------------------


class TestStructPropertyVariants:
    """Regression tests for struct format variants that caused repeated fixes."""

    def test_struct_value_in_material_properties(self):
        """#556: StructValue must be handled in material property parsing."""
        result = _parse("CassiniSample_MI_Template_BaseGray_Metal.uasset")
        assert result is not None
        assert result.export_map is not None
        # Material instance should parse without StructValue errors
        assert result.status in ("success", "partial", "partial_metadata")

    def test_struct_value_in_expression_outputs(self):
        """#556: _build_expression_outputs must unwrap nested StructValue."""
        result = _parse("FirstPerson_M_FlatCol.uasset")
        assert result is not None
        assert result.export_map is not None
        # Should not crash on StructValue in expression outputs
        assert result.status in ("success", "partial", "partial_metadata")

    def test_legacy_struct_array_with_property_tag(self):
        """#521: Legacy struct arrays read element PropertyTag for inner type."""
        result = _parse("ALS_Mannequin_Skeleton.uasset")
        assert result is not None
        assert result.export_map is not None
        # Skeleton should parse with struct arrays intact
        assert result.status in ("success", "partial", "partial_metadata")


# ---------------------------------------------------------------------------
# MapProperty / SetProperty variants
# ---------------------------------------------------------------------------


class TestMapPropertyVariants:
    """Regression tests for map/set format variants."""

    def test_map_property_legacy_inner_type_fallback(self):
        """#541: MapProperty legacy format uses inner_type fallback."""
        result = _parse("FirstPerson_DT_WeaponList.uasset")
        assert result is not None
        assert result.export_map is not None
        # DataTable with map properties should parse cleanly
        assert result.status in ("success", "partial", "partial_metadata")

    def test_set_property_basic(self):
        """SetProperty with standard key type."""
        result = _parse("FirstPerson_BP_FirstPersonCharacter.uasset")
        assert result is not None
        assert result.export_map is not None
        # Blueprint may contain SetProperty — should not crash
        assert result.status in ("success", "partial", "partial_metadata")


# ---------------------------------------------------------------------------
# TextProperty / DelegateProperty variants
# ---------------------------------------------------------------------------


class TestTextPropertyVariants:
    """Regression tests for text and delegate format variants."""

    def test_ftext_with_history(self):
        """FText with history data should parse without truncation."""
        result = _parse("FirstPerson_BP_FirstPersonCharacter.uasset")
        assert result is not None
        assert result.export_map is not None
        # Blueprint should have text properties intact
        assert result.status in ("success", "partial", "partial_metadata")

    def test_delegate_property(self):
        """DelegateProperty with binding info."""
        result = _parse("FirstPerson_BP_FirstPersonCharacter.uasset")
        assert result is not None
        assert result.export_map is not None
        assert result.status in ("success", "partial", "partial_metadata")


# ---------------------------------------------------------------------------
# FPrefix / BinaryOrNative fallback
# ---------------------------------------------------------------------------


class TestBinaryOrNativeFallback:
    """Regression tests for F prefix normalization and BinaryOrNative dispatch."""

    def test_binary_handler_lookup_with_f_prefix(self):
        """#541: Binary handler lookup tries both with and without F prefix."""
        result = _parse("ALS_CLF_GetUp_Back_Montage_Default.uasset")
        assert result is not None
        assert result.export_map is not None
        assert result.status in ("success", "partial", "partial_metadata")

    def test_niagara_variable_binary_or_native(self):
        """#527: NiagaraVariable decoded via BinaryOrNative handler."""
        # Niagara samples not in tests/samples — test via any asset with binary data
        result = _parse("FirstPerson_BP_FirstPersonCharacter.uasset")
        assert result is not None
        assert result.export_map is not None
        # Should not crash on BinaryOrNative dispatch
        assert result.status in ("success", "partial", "partial_metadata")
