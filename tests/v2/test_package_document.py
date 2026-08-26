"""Tests for v2 PackageDocument — Phase 1 exit conditions.

Verifies:
- All exports included (no filtering)
- Multi-asset packages work (b_is_asset > 1)
- Header/import/export counts match v1 pipeline
- Document serializes to valid v2 JSON contract
"""

from __future__ import annotations

from pathlib import Path
import json
import pytest

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


@pytest.fixture
def sample_path():
    return str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")


@pytest.fixture
def multi_asset_sample():
    """Sample with 2 b_is_asset exports."""
    return str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")


@pytest.fixture
def large_sample():
    """Large AnimBP with 3395 exports."""
    return str(SAMPLES_DIR / "ALS_AnimBP.uasset")


class TestPackageDocumentBasic:
    """Phase 1 core: all exports present, multi-asset works."""

    def test_document_format_fields(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        d = doc.to_dict()

        assert d["format"] == "uasset_read.package"
        assert d["format_version"] == "2.0"
        assert d["view"] == "semantic"
        assert d["depth"] == "asset"

    def test_all_exports_present(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)

        # ABP_RifleAnimLayers has 10 exports
        assert len(doc.objects) == 10
        # All should be export:* ids
        for obj in doc.objects:
            assert obj.id.startswith("export:")

    def test_multi_asset_objects_have_asset_role(self, multi_asset_sample):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.v2.object_model import ROLES_ASSET

        doc = parse_package_document(multi_asset_sample)

        asset_objects = [o for o in doc.objects if ROLES_ASSET in o.roles]
        assert len(asset_objects) >= 2, "Should have 2+ asset-role objects"

    def test_export_count_matches_v1(self, sample_path):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.pipeline.core import parse_uasset_with_linker

        doc = parse_package_document(sample_path)
        v1 = parse_uasset_with_linker(sample_path, tolerant=True)

        assert doc.summary.total_exports == len(v1.export_map or [])
        assert doc.summary.total_imports == len(v1.import_map or [])

    def test_import_count_matches_v1(self, sample_path):
        from uasset_read.v2.api import parse_package_document
        from uasset_read.pipeline.core import parse_uasset_with_linker

        doc = parse_package_document(sample_path)
        v1 = parse_uasset_with_linker(sample_path, tolerant=True)

        assert doc.summary.total_imports == len(v1.import_map or [])

    def test_large_sample_all_exports(self, large_sample):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(large_sample)

        assert len(doc.objects) == 3395
        assert doc.summary.total_exports == 3395


class TestDocumentSerialization:
    """Verify the document serializes to valid v2 JSON."""

    def test_to_dict_has_all_required_keys(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        d = doc.to_dict()

        required = [
            "format", "format_version", "view", "depth",
            "source", "package", "objects", "relations",
            "dependencies", "payloads", "diagnostics", "summary",
        ]
        for key in required:
            assert key in d, f"Missing key: {key}"

    def test_source_info(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        d = doc.to_dict()

        assert d["source"]["kind"] == "loose"
        assert d["source"]["name"] == "ABP_RifleAnimLayers.uasset"
        assert d["source"]["size"] > 0

    def test_package_info(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        d = doc.to_dict()

        assert d["package"]["layout"] == "legacy"
        assert d["package"]["export_count"] == 10
        assert d["package"]["import_count"] == 191

    def test_object_structure(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        d = doc.to_dict()

        for obj in d["objects"]:
            assert "id" in obj
            assert "name" in obj
            assert "roles" in obj
            assert "status" in obj
            assert "parse" in obj["status"]
            assert "semantic" in obj["status"]

    def test_json_serializable(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        d = doc.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert len(json_str) > 0

        # Round-trip
        parsed = json.loads(json_str)
        assert parsed["format"] == "uasset_read.package"


class TestRelations:
    """Verify relations are derived from export indices."""

    def test_relations_present(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        assert len(doc.relations) > 0

    def test_relation_ids_valid(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        object_ids = {obj.id for obj in doc.objects}

        for rel in doc.relations:
            # from_id should reference an object
            if rel.from_id.startswith("export:"):
                assert rel.from_id in object_ids
            # to_id can be import:* or export:*
            assert rel.to_id.startswith("export:") or rel.to_id.startswith("import:")


class TestDiagnostics:
    """Verify diagnostics are structured."""

    def test_no_critical_on_healthy_sample(self, sample_path):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(sample_path)
        critical = [d for d in doc.diagnostics if d.severity == "critical"]
        assert len(critical) == 0


class TestAllSamples:
    """Smoke test: all samples produce a valid PackageDocument."""

    @pytest.mark.parametrize(
        "sample_name",
        [
            f.name
            for f in sorted(SAMPLES_DIR.glob("*.uasset"))
        ],
    )
    def test_sample_produces_document(self, sample_name):
        from uasset_read.v2.api import parse_package_document

        path = str(SAMPLES_DIR / sample_name)
        doc = parse_package_document(path)

        assert doc.summary.total_exports > 0, f"{sample_name}: no exports"
        assert len(doc.objects) > 0, f"{sample_name}: no objects"
        assert doc.to_dict()["format"] == "uasset_read.package"
