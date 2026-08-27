"""Document contract — exports, stable IDs, relations, multi-asset, failure isolation."""

from __future__ import annotations

from pathlib import Path

import json
import pytest

SAMPLES_DIR = Path(__file__).parent / "samples"

SAMPLE = str(SAMPLES_DIR / "ABP_RifleAnimLayers.uasset")
MULTI_ASSET = str(SAMPLES_DIR / "ALS_AnimBP.uasset")


@pytest.fixture
def doc():
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(SAMPLE)


@pytest.fixture
def multi_doc():
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(MULTI_ASSET)


class TestExportIdentity:
    def test_all_exports_present(self, doc):
        assert len(doc.objects) == 10

    def test_ids_are_export_prefix(self, doc):
        for obj in doc.objects:
            assert obj.id.startswith("export:")
            idx = int(obj.id.split(":")[1])
            assert idx == obj.table_index

    def test_stable_id_across_calls(self):
        from uasset_read.v2.api import parse_package_document

        doc1 = parse_package_document(SAMPLE)
        doc2 = parse_package_document(SAMPLE)
        ids1 = [o.id for o in doc1.objects]
        ids2 = [o.id for o in doc2.objects]
        assert ids1 == ids2

    def test_large_sample_all_exports(self, multi_doc):
        assert len(multi_doc.objects) == 3395


class TestMultiAsset:
    def test_multiple_asset_roles(self, doc):
        asset_objs = [o for o in doc.objects if "asset" in o.roles]
        assert len(asset_objs) >= 2

    def test_bisasset_does_not_filter(self, multi_doc):
        all_ids = {o.id for o in multi_doc.objects}
        assert len(all_ids) == 3395


class TestZeroAssetRole:
    def test_exports_survive_without_asset_role(self):
        from uasset_read.v2.api import parse_package_document

        doc = parse_package_document(SAMPLES_DIR / "uasset_rs_UE410_SimpleRefsSoftRef.uasset")
        assert len(doc.objects) == 6
        assert doc.summary.asset_object_ids == ()


class TestRelations:
    def test_relations_present(self, doc):
        assert len(doc.relations) > 0

    def test_relation_from_references_export(self, doc):
        export_ids = {o.id for o in doc.objects}
        for r in doc.relations:
            if r.from_id.startswith("export:"):
                assert r.from_id in export_ids

    def test_relation_to_valid(self, doc):
        for r in doc.relations:
            assert r.to_id.startswith("export:") or r.to_id.startswith("import:")


class TestDiagnostics:
    def test_no_critical_on_healthy(self, doc):
        critical = [d for d in doc.diagnostics if d.severity == "critical"]
        assert len(critical) == 0

    def test_diagnostics_have_stage(self, doc):
        for d in doc.diagnostics:
            assert d.stage, f"Diagnostic missing stage: {d.code}"


class TestSerialization:
    def test_to_dict_roundtrip(self, doc):
        d = doc.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["format"] == "uasset_read.package"
        assert len(parsed["objects"]) == 10

    def test_summary_fields(self, doc):
        d = doc.to_dict()
        assert d["summary"]["object_count"] == 10
        assert d["summary"]["total_exports"] == 10
        assert "total_imports" in d["summary"]


class TestDirectReader:
    """Verify v2 api uses direct reader, not v1 pipeline."""

    def test_v2_api_does_not_call_v1_pipeline(self, monkeypatch, doc):
        import uasset_read.pipeline.core as old_core

        def forbidden(*args, **kwargs):
            raise AssertionError("v1 pipeline called")

        monkeypatch.setattr(old_core, "parse_uasset_with_linker", forbidden)
        # Re-import to get a fresh module-level reference
        from uasset_read.v2.api import parse_package_document

        result = parse_package_document(SAMPLE, depth="package")
        assert result.package.layout == "legacy"
        assert result.summary.total_exports == len(result.objects)


class TestLegacyTableParity:
    """Verify every tracked legacy fixture parses with correct table counts."""

    @pytest.fixture(scope="class")
    def manifest(self):
        import json as _json

        with open(SAMPLES_DIR / "manifest.json") as f:
            return _json.load(f)

    def test_legacy_reader_matches_manifest_tables(self, manifest):
        from uasset_read.v2.api import parse_package_document

        for entry in manifest["samples"]:
            if entry["engine_layout"] != "legacy":
                continue
            doc = parse_package_document(SAMPLES_DIR / entry["name"], depth="package")
            assert doc.package.layout == "legacy", entry["name"]
            assert doc.package.export_count == entry["export_count"], entry["name"]
            assert len(doc.objects) == entry["export_count"], entry["name"]
            assert len(doc.summary.asset_object_ids) == entry["b_is_asset_count"], entry["name"]
