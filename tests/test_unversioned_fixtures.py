"""Structural assertions for unversioned property fixtures."""
from __future__ import annotations

import hashlib
import json
import os
import struct

import pytest

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")
MANIFEST_PATH = os.path.join(SAMPLES_DIR, "manifest.json")


def _load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class TestUnversionedFixtureIntegrity:
    """Verify fixture files exist, match manifest, and have expected structure."""

    @pytest.fixture
    def manifest(self):
        return _load_manifest()

    @pytest.fixture
    def unversioned_entries(self, manifest):
        return [s for s in manifest.get("samples", []) if s.get("unversioned")]

    def test_unversioned_fixtures_exist(self, unversioned_entries):
        assert len(unversioned_entries) >= 2, (
            f"Expected >=2 unversioned fixtures, got {len(unversioned_entries)}"
        )
        for entry in unversioned_entries:
            path = os.path.join(SAMPLES_DIR, entry["name"])
            assert os.path.isfile(path), f"Fixture file missing: {path}"

    def test_sha256_matches(self, unversioned_entries):
        for entry in unversioned_entries:
            path = os.path.join(SAMPLES_DIR, entry["name"])
            actual = _sha256_file(path)
            assert actual == entry["sha256"], (
                f"SHA-256 mismatch for {entry['name']}: "
                f"expected {entry['sha256']}, got {actual}"
            )

    def test_size_matches(self, unversioned_entries):
        for entry in unversioned_entries:
            path = os.path.join(SAMPLES_DIR, entry["name"])
            actual = os.path.getsize(path)
            assert actual == entry["size_bytes"], (
                f"Size mismatch for {entry['name']}: "
                f"expected {entry['size_bytes']}, got {actual}"
            )

    def test_version_zero_indicates_unversioned(self, unversioned_entries):
        """FileVersionUE4 == 0 is the detection signal for unversioned properties."""
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
