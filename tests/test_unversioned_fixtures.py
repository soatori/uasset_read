"""Structural assertions for unversioned property fixtures."""
from __future__ import annotations

import json
import os
import struct

import pytest

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")
MANIFEST_PATH = os.path.join(SAMPLES_DIR, "manifest.json")


class TestUnversionedFixtureIntegrity:
    """Unversioned-specific invariants; file integrity is covered by test_samples.py."""

    @pytest.fixture
    def unversioned_entries(self):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        return [s for s in manifest.get("samples", []) if s.get("unversioned")]

    def test_version_zero_indicates_unversioned(self, unversioned_entries):
        """FileVersionUE4 == 0 is the detection signal for unversioned properties."""
        assert len(unversioned_entries) >= 2, (
            f"Expected >=2 unversioned fixtures, got {len(unversioned_entries)}"
        )
        for entry in unversioned_entries:
            assert entry.get("file_version_ue4") == 0, (
                f"{entry['name']}: expected file_version_ue4=0 for unversioned, "
                f"got {entry.get('file_version_ue4')}"
            )

    def test_usmap_file_exists(self, unversioned_entries):
        for entry in unversioned_entries:
            usmap_name = entry.get("usmap_file")
            if usmap_name:
                path = os.path.join(SAMPLES_DIR, usmap_name)
                assert os.path.isfile(path), f"USMAP file missing: {path}"

    def test_usmap_parses(self, unversioned_entries):
        from uasset_read.mappings import UsmapParser

        for entry in unversioned_entries:
            usmap_name = entry.get("usmap_file")
            if not usmap_name:
                continue
            path = os.path.join(SAMPLES_DIR, usmap_name)
            mappings = UsmapParser(path)
            assert len(mappings.mappings.types) > 0, (
                f"USMAP {usmap_name} parsed but contains no struct definitions"
            )


class TestUnversionedPropertySchema:
    """Verify USMAP schema has expected structure for unversioned properties."""

    @pytest.fixture
    def mappings(self):
        from uasset_read.mappings import UsmapParser

        usmap_path = os.path.join(SAMPLES_DIR, "UnversionedTest.usmap")
        if not os.path.isfile(usmap_path):
            pytest.skip("USMAP file not present")
        return UsmapParser(usmap_path)

    def test_has_target_structs(self, mappings):
        """Verify the target classes/structs exist in the schema."""
        expected_structs = ["BP_UnversionedTest_C", "UnversionedTestAsset", "UnversionedTestStruct"]
        found = []
        for name in expected_structs:
            if mappings.mappings.get_struct(name) is not None:
                found.append(name)
        assert len(found) >= 2, (
            f"Expected >=2 of {expected_structs} in USMAP, found {found}. "
            f"Available: {list(mappings.mappings.types.keys())[:10]}"
        )

    def test_has_expected_property_types(self, mappings):
        """Verify at least 3 fields with distinct types exist in target struct."""
        struct = mappings.mappings.get_struct("BP_UnversionedTest_C")
        if struct is None:
            pytest.skip("BP_UnversionedTest_C not found in USMAP")

        type_names = {p.mapping_type.type for p in struct.properties.values()}
        assert len(type_names) >= 3, (
            f"Expected >=3 distinct property types, got {len(type_names)}: {type_names}"
        )

    def test_property_count_matches(self, mappings):
        """Verify property count in schema matches declared count."""
        struct = mappings.mappings.get_struct("BP_UnversionedTest_C")
        if struct is None:
            pytest.skip("BP_UnversionedTest_C not found in USMAP")
        assert len(struct.properties) == struct.property_count, (
            f"Property count mismatch: {len(struct.properties)} actual vs "
            f"{struct.property_count} declared"
        )

    def test_struct_has_known_types(self, mappings):
        """Verify the schema contains expected UE property types."""
        struct = mappings.mappings.get_struct("BP_UnversionedTest_C")
        if struct is None:
            pytest.skip("BP_UnversionedTest_C not found in USMAP")

        type_names = {p.mapping_type.type for p in struct.properties.values()}
        # These are common types that should appear in a Blueprint
        expected_types = {"IntProperty", "DoubleProperty", "BoolProperty", "ObjectProperty"}
        found = type_names & expected_types
        assert len(found) >= 2, (
            f"Expected >=2 of {expected_types} in schema, found {found}. "
            f"All types: {type_names}"
        )


class TestUnversionedFixtureProvenance:
    """Verify provenance documentation exists and is complete."""

    def test_provenance_file_exists(self):
        # Check for any provenance-related files
        provenance_files = [
            "UnversionedTest.provenance.md",
            "unversioned-fixture-design.md",
        ]
        found = False
        for pf in provenance_files:
            path = os.path.join(SAMPLES_DIR, pf)
            if os.path.isfile(path):
                found = True
                break
        # Also check temp/ for design docs
        temp_design = os.path.join(os.path.dirname(__file__), "..", "temp", "unversioned-fixture-design.md")
        if os.path.isfile(temp_design):
            found = True
        assert found, "No provenance/documentation file found for unversioned fixtures"


class TestUnversionedBinaryHeader:
    """Verify fixture binaries have valid UE4/UE5 headers."""

    def test_valid_package_magic(self):
        """Verify .uasset files have valid UE package magic."""
        asset_files = [
            "BP_UnversionedTest.uasset",
            "DA_UnversionedTest.uasset",
        ]
        for name in asset_files:
            path = os.path.join(SAMPLES_DIR, name)
            if not os.path.isfile(path):
                continue
            with open(path, "rb") as f:
                header = f.read(64)
            magic = struct.unpack_from("<I", header, 0)[0]
            assert magic in (0x9E2A83C1, 0x00690083), (
                f"{name}: unexpected package magic 0x{magic:08X}"
            )

    def test_sidecar_files_exist(self):
        """Verify .uexp sidecar files exist for unversioned fixtures."""
        sidecar_files = [
            "BP_UnversionedTest.uexp",
            "DA_UnversionedTest.uexp",
        ]
        for name in sidecar_files:
            path = os.path.join(SAMPLES_DIR, name)
            assert os.path.isfile(path), f"Sidecar file missing: {name}"
            assert os.path.getsize(path) > 0, f"Sidecar file empty: {name}"


class TestUnversionedPackageParsing:
    """Verify unversioned packages can be parsed without VersionError."""

    def test_bp_unversioned_parses(self):
        """BP_UnversionedTest should parse without VersionError."""
        from uasset_read.package import open_package_bundle
        from uasset_read.parsers.legacy_reader import LegacyPackageReader

        bundle = open_package_bundle("tests/samples/BP_UnversionedTest.uasset")
        archive = bundle.open_archive(tolerant=True)
        try:
            reader = LegacyPackageReader(mappings_path="tests/samples/UnversionedTest.usmap")
            doc = reader.read(archive=archive, main_path="tests/samples/BP_UnversionedTest.uasset")
            assert doc is not None
            assert len(doc.objects) >= 1
        finally:
            archive.close()

    def test_da_unversioned_parses(self):
        """DA_UnversionedTest should parse without VersionError."""
        from uasset_read.package import open_package_bundle
        from uasset_read.parsers.legacy_reader import LegacyPackageReader

        bundle = open_package_bundle("tests/samples/DA_UnversionedTest.uasset")
        archive = bundle.open_archive(tolerant=True)
        try:
            reader = LegacyPackageReader(mappings_path="tests/samples/UnversionedTest.usmap")
            doc = reader.read(archive=archive, main_path="tests/samples/DA_UnversionedTest.uasset")
            assert doc is not None
        finally:
            archive.close()
        assert len(doc.objects) >= 1


class TestUnversionedMappedProperties:
    """Wave B P6: usmap-driven unversioned parse must yield mapped values or opaque."""

    def _parse(self, asset_name: str):
        from uasset_read.package import open_package_bundle
        from uasset_read.parsers.legacy_reader import LegacyPackageReader

        path = f"tests/samples/{asset_name}.uasset"
        bundle = open_package_bundle(path)
        archive = bundle.open_archive(tolerant=True)
        try:
            reader = LegacyPackageReader(mappings_path="tests/samples/UnversionedTest.usmap")
            return reader.read(archive=archive, main_path=path, depth="object")
        finally:
            archive.close()

    def test_da_unversioned_exposes_mapped_properties(self):
        """DA asset with usmap must produce a non-empty mapped bag."""
        doc = self._parse("DA_UnversionedTest")
        assert doc is not None
        primary = next(o for o in doc.objects if o.name == "DA_UnversionedTest")
        props = primary.properties or {}
        assert props, "unversioned export with usmap must produce a non-empty property bag"
        # Mapped values, not opaque
        assert props.get("AssetID", {}).get("kind") == "value"
        assert props["AssetID"]["value"] == "UnversionedAssetID"
        assert props.get("NumericArray", {}).get("value") == [10, 20, 30, 40]
        # No name-index misparse
        codes = [d.code for d in doc.diagnostics]
        assert codes.count("name_index_out_of_range") == 0

    def test_bp_unversioned_exposes_mapped_properties(self):
        """BP CDO with usmap must produce non-empty bag or explicit opaque; no name-index storm."""
        doc = self._parse("BP_UnversionedTest")
        assert doc is not None
        # CDO has BP_UnversionedTest_C mapping in the usmap
        cdo = next(o for o in doc.objects if o.name == "Default__BP_UnversionedTest_C")
        props = cdo.properties or {}
        assert props, "unversioned CDO with usmap must produce a non-empty property bag"
        # Early scalar fields must be real values
        assert props.get("ScriptInt", {}).get("value") == 77
        assert props.get("ScriptBool", {}).get("value") is True
        # BlueprintGeneratedClass export has no usmap entry -> whole-region opaque
        class_obj = next(o for o in doc.objects if o.name == "BP_UnversionedTest_C")
        class_props = class_obj.properties or {}
        assert class_props, "unmapped class export must still yield explicit opaque"
        class_is_opaque = any(
            isinstance(v, dict) and v.get("kind") == "opaque" for v in class_props.values()
        )
        assert class_is_opaque, "BlueprintGeneratedClass without usmap must be UnversionedOpaque"
        # Forbid tagged name-index misparse: zero name_index_out_of_range diagnostics.
        # The mapping path stops and opaques the remainder instead of falling back
        # to tagged FName parsing.
        codes = [d.code for d in doc.diagnostics]
        assert codes.count("name_index_out_of_range") == 0, (
            f"unversioned parse must not emit name_index_out_of_range; got: {codes}"
        )


class TestUnversionedFTextStopPath:
    """Unknown FText history must stop + rewind, not invent an empty complete TextValue."""

    def test_unknown_history_returns_none_and_rewinds(self):
        from uasset_read.archive import ByteArchive
        from uasset_read.parsers.property_parser import _read_unversioned_ftext

        # flags(i32=0) + history=1 (not Base/None) + garbage body that must
        # not be consumed as typed text or projected as complete.
        payload = struct.pack("<iB", 0, 1) + b"\xde\xad\xbe\xef" * 2
        archive = ByteArchive(payload)
        start = archive.tell()
        result = _read_unversioned_ftext(archive, property_end=len(payload))
        assert result is None
        assert archive.tell() == start, "unknown history must rewind so the caller can opaque the tail"

    def test_base_history_still_reads_three_fstrings(self):
        from uasset_read.archive import ByteArchive
        from uasset_read.models.properties import TextValue
        from uasset_read.parsers.property_parser import _read_unversioned_ftext

        def _fstring(text: str) -> bytes:
            raw = text.encode("utf-8")
            return struct.pack("<i", len(text) + 1) + raw + b"\x00"

        payload = struct.pack("<iB", 0, 0) + _fstring("NS") + _fstring("Key") + _fstring("Src")
        archive = ByteArchive(payload)
        result = _read_unversioned_ftext(archive, property_end=len(payload))
        assert isinstance(result, TextValue)
        assert result.history_type == 0
        assert result.source_string == "Src"
