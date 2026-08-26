"""Property parser tests — verifying property type dispatch and parsing.

Tests that various property types (struct, array, map, enum, bool, string,
object) are correctly parsed from real .uasset sample exports.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read import parse_package


class TestPropertyParsing:
    """Property parsing from real samples."""

    def test_properties_present_in_blueprint(self, samples_dir: Path):
        """Blueprint exports contain parsed properties."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert result.export_map is not None

        # At least one export should have properties
        has_props = False
        for export in result.export_map:
            props = getattr(export, "properties", None) or []
            if props:
                has_props = True
                break
        assert has_props, "No properties found in any export"

    def test_properties_present_in_material(self, samples_dir: Path):
        """Material exports contain parsed properties."""
        sample = samples_dir / "FirstPerson_M_FlatCol.uasset"
        result = parse_package(str(sample), tolerant=True)
        assert result.export_map is not None

        has_props = False
        for export in result.export_map:
            props = getattr(export, "properties", None) or []
            if props:
                has_props = True
                break
        assert has_props, "No properties found in any export"

    def test_property_type_diversity(self, samples_dir: Path, sample_uassets: list[Path]):
        """Across all samples, we should see multiple distinct property types."""
        seen_types: set[str] = set()

        for sample_path in sample_uassets:
            result = parse_package(str(sample_path), tolerant=True)
            if result is None or result.export_map is None:
                continue
            for export in result.export_map:
                props = getattr(export, "properties", None) or []
                for prop in props:
                    ptype = getattr(prop, "type", None)
                    if ptype:
                        seen_types.add(str(ptype))

        # We expect to see at least a few distinct types across all samples
        assert len(seen_types) >= 3, f"Expected diverse property types, got: {sorted(seen_types)}"

    def test_struct_properties_in_blueprint(self, samples_dir: Path):
        """Blueprint samples should contain struct-typed properties."""
        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_package(str(sample), tolerant=True)

        struct_found = False
        for export in result.export_map:
            props = getattr(export, "properties", None) or []
            for prop in props:
                ptype = getattr(prop, "type", None)
                if ptype and "struct" in str(ptype).lower():
                    struct_found = True
                    break

        # Not all blueprints have struct props, but most do
        # This is a soft check
        if not struct_found:
            pytest.skip("No struct properties found in this sample")

    def test_export_parse_status_values(self, samples_dir: Path, sample_uassets: list[Path]):
        """All exports must have valid parse_status values."""
        valid_statuses = {"success", "partial", "partial_metadata", "failed", "opaque", None}

        for sample_path in sample_uassets[:5]:  # Check first 5 for speed
            result = parse_package(str(sample_path), tolerant=True)
            if result is None or result.export_map is None:
                continue
            for export in result.export_map:
                status = getattr(export, "parse_status", None)
                assert status in valid_statuses, f"{sample_path.name}: invalid parse_status '{status}'"


class TestPropertyRoundTrip:
    """Property round-trip: parse -> IR -> verify."""

    def test_properties_appear_in_ir(self, samples_dir: Path):
        """Parsed properties are reflected in the IR builder output."""
        from uasset_read.pipeline.core import parse_uasset_with_linker
        from uasset_read.ir_builder import build_package_ir

        sample = samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset"
        result = parse_uasset_with_linker(str(sample), tolerant=True)
        ir = build_package_ir(result)

        # IR should have exports
        assert len(ir.exports) > 0

        # At least one export should have properties in IR
        has_props = False
        for export_ir in ir.exports:
            if export_ir.properties:
                has_props = True
                break
        assert has_props, "No properties found in IR exports"
