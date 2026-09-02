"""Real-sample contract home: every fixture-touching check lives here.

The 52-fixture matrix is manifest-driven and uncapped by design; shared
parse results are cached per sample so each fixture is parsed once per
depth. Case bodies folded from the former ``tests/contract/`` layer are
kept verbatim with the case/sample name in the failure message.
"""

from __future__ import annotations

import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "samples"
MANIFEST = SAMPLES / "manifest.json"
SCHEMA = json.loads((ROOT / "docs" / "designs" / "contract" / "package_document_v2.schema.json").read_text(encoding="utf-8"))

_MANIFEST_DATA = json.loads(MANIFEST.read_text(encoding="utf-8"))
MANIFEST_SAMPLES = _MANIFEST_DATA["samples"]
MANIFEST_BY_NAME = {entry["name"]: entry for entry in MANIFEST_SAMPLES}
GOLDEN_DIR = SAMPLES / "golden"
GOLDEN_FILES = _MANIFEST_DATA["golden_files"]

# (sample, class, expected keys, expected status.semantic at depth=asset).
# "complete" requires decoded-tier handler output; summary-tier handlers
# (mesh, blueprint summary, niagara) stay "partial" (#629).
CAPABILITIES = (
    ("ALS_FootstepDataTable.uasset", "DataTable", {"kind": "data_table"}, "complete"),
    (
        "Lyra_Enum_PanelType.uasset",
        "UserDefinedEnum",
        {"kind": "user_defined_enum", "enum_name": "Enum_PanelType"},
        "complete",
    ),
    (
        "StackOBot_Struct_Objective.uasset",
        "UserDefinedStruct",
        {"kind": "user_defined_struct", "struct_name": "Struct_Objective"},
        "complete",
    ),
    ("FirstPerson_T_GridChecker_A.uasset", "Texture2D", {"kind": "texture", "texture_type": "Texture2D"}, "complete"),
    (
        "MutableSample_GrayLightTextureCube.uasset",
        "TextureCube",
        {"kind": "texture", "texture_type": "TextureCube"},
        "complete",
    ),
    ("ALS_Concrete_Step_01_SoundWave.uasset", "SoundWave", {"kind": "sound", "sound_type": "SoundWave"}, "complete"),
    ("ALS_Mannequin_Skeleton.uasset", "Skeleton", {"kind": "skeleton"}, "complete"),
    (
        "StarterContent_SM_Chair.uasset",
        "StaticMesh",
        {"kind": "mesh", "mesh_type": "StaticMesh"},
        "partial",  # summary tier: geometry is not decoded
    ),
    ("FirstPerson_M_PrototypeGrid.uasset", "Material", {"kind": "material"}, "complete"),
    (
        "CassiniSample_MI_Template_BaseGray_Metal.uasset",
        "MaterialInstanceConstant",
        {"kind": "material_instance"},
        "complete",
    ),
    (
        "StackOBot_BP_Drone.uasset",
        "BlueprintGeneratedClass",
        {"kind": "blueprint"},
        "partial",  # summary tier at depth=asset
    ),
    ("ABP_RifleAnimLayers.uasset", "AnimBlueprintGeneratedClass", {"kind": "anim_blueprint"}, "partial"),
    ("ALS_AnimBP.uasset", "AnimBlueprint", {"kind": "anim_blueprint"}, "partial"),
    ("ALS_AnimBP.uasset", "AnimBlueprintGeneratedClass", {"kind": "anim_blueprint"}, "partial"),
    (
        "NM_BPSystemEvent.uasset",
        "NiagaraGraph",
        {"kind": "niagara", "niagara_type": "NiagaraGraph"},
        "partial",  # summary tier: name/type echo
    ),
    ("NM_BPSystemEvent.uasset", "NiagaraScript", {"kind": "niagara", "niagara_type": "NiagaraScript"}, "partial"),
    (
        "NM_BPSystemEvent.uasset",
        "NiagaraScriptSource",
        {"kind": "niagara", "niagara_type": "NiagaraScriptSource"},
        "partial",
    ),
    (
        "NM_BPSystemEvent.uasset",
        "NiagaraNodeOutput",
        {"kind": "niagara", "niagara_type": "NiagaraNodeOutput"},
        "partial",
    ),
    (
        "NM_BPSystemEvent.uasset",
        "NiagaraNodeSelect",
        {"kind": "niagara", "niagara_type": "NiagaraNodeSelect"},
        "partial",
    ),
    (
        "NM_BPSystemEvent.uasset",
        "NiagaraNodeStaticSwitch",
        {"kind": "niagara", "niagara_type": "NiagaraNodeStaticSwitch"},
        "partial",
    ),
)


@lru_cache(maxsize=None)
def _asset_document(sample: str):
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(SAMPLES / sample, depth="asset")


@lru_cache(maxsize=None)
def _object_document(sample: str):
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(SAMPLES / sample, depth="object")


@lru_cache(maxsize=None)
def _decode_document(sample: str, object_ids: tuple[str, ...]):
    from uasset_read.v2.api import parse_package_document

    return parse_package_document(SAMPLES / sample, depth="decode", object_ids=list(object_ids))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_depends_map(sample: str):
    """Re-read ObjectDependsMap through the low-level archive, independent of v2."""
    from uasset_read.serializers.package_summary import (
        read_depends_map,
        read_name_table,
        read_package_summary,
    )
    from uasset_read.v2.package.legacy import _make_package_archive
    from uasset_read.v2.source import FileSource

    archive = _make_package_archive(FileSource(SAMPLES / sample), tolerant=True)
    try:
        summary = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        archive.set_name_map(name_map)
        return read_depends_map(archive, summary)
    finally:
        archive.close()


def test_manifest_matches_every_real_sample():
    """The retained real-sample corpus must match its review-controlled manifest exactly."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["version"] == 2
    expected_files = {entry["name"] for entry in manifest["samples"]}
    actual_files = {path.name for path in SAMPLES.iterdir() if path.suffix in {".uasset", ".umap", ".utoc", ".ucas", ".pak"}}
    assert manifest["summary"]["total_samples"] == len(manifest["samples"]) == 52
    assert actual_files == expected_files
    allowed = expected_files | {
        "manifest.json",
        "README.md",
        "golden",
        "ORIGIN-issue-516-plugin-mount.md",
        "ORIGIN-issue-521-niagara.md",
        "ORIGIN-issue-522-cube-builder.md",
        "ORIGIN-issue-615-618-619-samples.md",
    }
    extra = {path.name for path in SAMPLES.iterdir()} - allowed
    assert not extra, f"Unexpected files in samples/: {extra}"
    for entry in manifest["samples"]:
        path = SAMPLES / entry["name"]
        assert path.exists(), f"Missing sample: {entry['name']}"
        assert path.stat().st_size == entry["size_bytes"], entry["name"]
        assert _sha256(path) == entry["sha256"], entry["name"]
    # Golden reference tables are manifest-tracked artifacts too (issue #633).
    golden_entries = manifest["golden_files"]
    golden_on_disk = {path.name for path in (SAMPLES / "golden").glob("*.golden.json")}
    assert golden_on_disk == {entry["name"] for entry in golden_entries}
    for entry in golden_entries:
        assert entry["fixture"] in expected_files, entry["name"]
        path = SAMPLES / "golden" / entry["name"]
        assert path.stat().st_size == entry["size_bytes"], entry["name"]
        assert _sha256(path) == entry["sha256"], entry["name"]


def _golden_mapped_ids(raws, export_count: int, import_count: int) -> list[str]:
    """Map raw FPackageIndex int32s like v2 does: null and out-of-range targets drop."""
    ids = []
    for raw in raws:
        if raw > 0 and raw <= export_count:
            ids.append(f"export:{raw - 1}")
        elif raw < 0 and -raw <= import_count:
            ids.append(f"import:{-raw - 1}")
    return ids


@pytest.mark.parametrize("entry", GOLDEN_FILES, ids=[entry["name"] for entry in GOLDEN_FILES])
def test_v2_tables_match_independent_golden_reference(entry):
    """Break the circular-verification gap of #633: compare v2 relations and table
    counts against UAssetAPI-generated golden data, failing on any drift."""
    golden = json.loads((GOLDEN_DIR / entry["name"]).read_text(encoding="utf-8"))
    assert golden["provenance"]["generator"] == entry["generator"], entry["name"]
    assert golden["provenance"]["generator_version"] == entry["generator_version"], entry["name"]
    sample_entry = MANIFEST_BY_NAME[entry["fixture"]]
    assert golden["fixture"]["sha256"] == sample_entry["sha256"], (
        f"{entry['name']} was generated from different bytes than the manifest fixture"
    )

    doc = _object_document(entry["fixture"])
    counts = golden["counts"]
    assert doc.package.name_count == counts["name"], entry["name"]
    assert doc.package.import_count == counts["import"] == len(doc.dependencies), entry["name"]
    assert doc.package.export_count == counts["export"] == len(doc.objects), entry["name"]

    export_count, import_count = counts["export"], counts["import"]
    actual: dict[str, dict[str, list[str]]] = {"depends_on": {}, "preload_of": {}}
    for rel in doc.relations:
        if rel.kind in actual:
            actual[rel.kind].setdefault(rel.from_id, []).append(rel.to_id)

    depends_expected = {
        f"export:{i}": edges
        for i, row in golden["depends_map"]["rows"].items()
        if (edges := _golden_mapped_ids(row, export_count, import_count))
    }
    assert actual["depends_on"] == depends_expected, f"{entry['name']} depends_on drift vs UAssetAPI"

    preload_expected = {
        f"export:{i}": edges
        for i, span in golden["preload"]["spans"].items()
        if (edges := _golden_mapped_ids(span, export_count, import_count))
    }
    assert actual["preload_of"] == preload_expected, f"{entry['name']} preload_of drift vs UAssetAPI"
    if not golden["preload"]["spans"]:
        # Editor-saved corpus: UE only writes the preload table for cooked packages.
        assert golden["preload"]["total_entries"] == 0, entry["name"]


@pytest.mark.parametrize(
    ("sample", "class_name", "expected", "expected_semantic"),
    CAPABILITIES,
    ids=[f"{item[1]}-{item[3]}" for item in CAPABILITIES],
)
def test_real_sample_proves_claimed_capability(
    sample: str, class_name: str, expected: dict[str, object], expected_semantic: str
):
    """Each claimed capability must produce stable semantics from a real fixture.

    The status column pins the #629 tier contract: decoded-tier fixtures are
    ``complete``; summary-tier fixtures prove ``partial`` with coverage.
    """
    doc = _asset_document(sample)
    obj = next(item for item in doc.objects if item.class_name == class_name)
    assert obj.status.semantic == expected_semantic, f"{sample}:{class_name}"
    assert obj.coverage, f"{sample}:{class_name}"
    assert {key: obj.semantic[key] for key in expected} == expected, f"{sample}:{class_name}"

    if class_name == "DataTable":
        assert obj.semantic["row_count"] >= 0
    elif class_name == "Skeleton":
        assert obj.semantic["bone_count"] == len(obj.semantic["bones"]) > 0
        # ALS_Mannequin_Skeleton carries real BoneTree property data; decoded
        # names must win over the NameMap regex name-guess (#630).
        assert obj.semantic["bone_source"] == "bone_tree"
        names = {b["name"] for b in obj.semantic["bones"]}
        assert "UpperArm_L" in names, "BoneTree names missing — regex fallback used?"
    elif class_name == "StaticMesh":
        assert obj.semantic["lod_count"] == len(obj.semantic["lods"])
    elif class_name in {"BlueprintGeneratedClass", "AnimBlueprintGeneratedClass"}:
        assert not {"nodes", "bytecode", "graph"} & obj.semantic.keys()
        if class_name == "AnimBlueprintGeneratedClass":
            dec = _decode_document(sample, (obj.id,))
            dobj = next(o for o in dec.objects if o.id == obj.id)
            assert dobj.semantic is not None, f"{sample}:{class_name} decode"
            assert dobj.semantic["kind"] == "anim_blueprint"
            # At depth=decode, graph data should be present
            if "graph" in dobj.semantic:
                graph = dobj.semantic["graph"]
                assert "nodes" in graph
                assert "edges" in graph
                # Decoded-tier output is what lifts the status to complete (#629).
                assert dobj.status.semantic == "complete", f"{sample}:{class_name} decode tier"
                # Verify all edge references point to existing nodes
                node_ids = {node["id"] for node in graph["nodes"]}
                for edge in graph["edges"]:
                    assert edge["from_node"] in node_ids, f"Edge from_node {edge['from_node']} not in nodes"
                    assert edge["to_node"] in node_ids, f"Edge to_node {edge['to_node']} not in nodes"
    elif class_name in {"Texture2D", "TextureCube"}:
        assert isinstance(obj.semantic["srgb"], bool), f"{sample}:{class_name}"
        assert "compression_settings" in obj.semantic, f"{sample}:{class_name}"
        feature_names = [c.feature for c in obj.coverage]
        for feature in ("texture.kind", "texture.texture_type", "texture.srgb", "texture.compression_settings"):
            assert feature in feature_names, f"{sample}:{class_name} missing coverage {feature}"
        twin = copy.deepcopy(obj)
        from uasset_read.v2.handlers import TexturePayloadHandler
        from uasset_read.v2.version import VersionContext

        result = TexturePayloadHandler().enrich(twin, VersionContext(), doc.objects, None)
        if class_name == "TextureCube":
            # TextureCube doesn't have ImportedSize property, so result is None
            assert result is None, f"{sample}:{class_name}"
        else:
            # May be None if ImportedSize is absent or empty
            if result is not None:
                payload = result["payload"]
                assert payload["kind"] == "texture_mip"
                assert payload["source_region"] == "main"
                assert isinstance(payload["logical_size"], int)
                # Payload must never contain raw bytes
                assert "raw_bytes" not in payload
            payload_features = [c for c in obj.coverage if c.feature == "texture.payload"]
            assert len(payload_features) == 1, f"{sample}:{class_name}"
            assert payload_features[0].status in ("present", "partial")
    elif class_name == "SoundWave":
        handler_features = [c for c in obj.coverage if c.feature == "handler.SoundHandler"]
        assert len(handler_features) == 1, f"{sample}:{class_name}"


@pytest.mark.parametrize("sample", [entry["name"] for entry in MANIFEST_SAMPLES])
def test_every_real_sample_forms_a_valid_package_document(sample: str):
    """Every tracked fixture must form a schema-valid, complete, blob-free document."""
    doc = _object_document(sample)
    entry = MANIFEST_BY_NAME[sample]

    ids = [o.id for o in doc.objects]
    assert ids == [f"export:{i}" for i in range(len(ids))], sample
    assert len(ids) == entry["export_count"], sample
    assert doc.package.layout == "legacy", sample
    assert doc.package.export_count == entry["export_count"], sample
    assert len(doc.summary.asset_object_ids) == entry["b_is_asset_count"], sample

    valid = set(ids) | {f"import:{i}" for i in range(len(doc.dependencies))}
    assert doc.relations, sample
    for rel in doc.relations:
        assert rel.from_id in ids, f"{sample}: relation from {rel.from_id} is not an export"
        assert rel.to_id in valid, f"{sample}: dangling {rel.kind} {rel.from_id} -> {rel.to_id}"

    # depends_on must map raw FPackageIndex values per UE sign convention.
    depends_expected: set[tuple[str, str]] = set()
    for i, deps in enumerate(_raw_depends_map(sample)):
        for raw in deps:
            if raw > 0:
                depends_expected.add((f"export:{i}", f"export:{raw - 1}"))
            elif raw < 0:
                depends_expected.add((f"export:{i}", f"import:{-raw - 1}"))
    depends_actual = {(r.from_id, r.to_id) for r in doc.relations if r.kind == "depends_on"}
    assert depends_actual == {edge for edge in depends_expected if edge[1] in valid}, sample

    super_expected = {
        (o.id, f"{o.super_ref.table}:{o.super_ref.index}") for o in doc.objects if o.super_ref is not None
    }
    super_actual = {(r.from_id, r.to_id) for r in doc.relations if r.kind == "super_of"}
    assert super_actual == {edge for edge in super_expected if edge[1] in valid}, sample
    if sample == "ABP_RifleAnimLayers.uasset":
        assert super_expected, "ABP sample must contain exports with a super reference"

    for d in doc.diagnostics:
        assert d.stage, f"{sample}: Diagnostic missing stage: {d.code}"
    for o in doc.objects:
        if o.serial_region and o.serial_region.size > 0:
            assert o.properties is not None, f"{sample}:{o.id} has no property bag"
            json.dumps(o.properties)

    bounds = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_BOUNDS_EXCEEDED"]
    failed = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_PARSE_FAILED"]
    oob = [d for d in doc.diagnostics if d.code == "RELATION_TARGET_OUT_OF_RANGE"]
    assert not bounds and not failed and not oob, (
        f"{sample}: unexpected diagnostics {[d.code for d in bounds + failed + oob]}"
    )

    from uasset_read.v2.projection import project_document

    # Schema validation runs for every fixture. The shipped schema must accept
    # all legitimate projection values; mismatches are contract bugs, not
    # test-fold decisions. Every fixture's bounded page must still round-trip
    # and echo its view.
    for view in ("semantic", "raw", "debug"):
        page = project_document(doc, depth="object", view=view, limit=3)
        parsed = json.loads(json.dumps(page, ensure_ascii=False))
        assert parsed["view"] == view, sample
        jsonschema.validate(page, SCHEMA)
        for dep in page["dependencies"]:
            assert set(dep) == {"index", "class", "object_name", "package_name"}, f"{sample}: {dep}"
        for o in page["objects"]:
            if view == "semantic":
                assert "properties" not in o, sample
                if "properties_summary" in o:
                    assert set(o["properties_summary"]) == {"properties", "property_count"}, sample
            else:
                assert "properties_summary" not in o, sample
    # raw_data legitimately appears as a length-only {"kind": "bytes", ...}
    # descriptor for struct fallbacks; the contract is that it never carries
    # inline bytes, and any truncation marker wins.
    blob_free = json.dumps(project_document(doc, depth="object", view="semantic", limit=3))
    assert "raw_data_truncated" in blob_free or '"raw_data": "' not in blob_free, sample


def test_v2_path_emits_no_handler_warnings(capfd, caplog):
    # capfd alone cannot catch the leak under pytest: the logging plugin
    # installs a root handler, which suppresses logging.lastResort. Assert
    # on captured WARNING records too — the real contract is "no warning
    # logs on the v2 parse path".
    import logging

    from uasset_read.v2.api import parse_package_document

    with caplog.at_level(logging.WARNING):
        parse_package_document(SAMPLES / "NM_BPSystemEvent.uasset", depth="object")
    captured = capfd.readouterr()
    assert captured.err == "", f"v2 parse leaked stderr: {captured.err[:200]}"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [], (
        f"v2 parse emitted warning logs: {[r.getMessage()[:120] for r in warnings]}"
    )


def test_object_depth_parses_only_requested_export():
    from uasset_read.v2.api import parse_package_document

    doc = parse_package_document(str(SAMPLES / "ABP_RifleAnimLayers.uasset"), depth="object", object_ids=["export:1"])
    parsed = [obj.id for obj in doc.objects if obj.properties is not None]
    assert parsed == ["export:1"]
    assert len(doc.objects) == doc.package.export_count


def test_package_depth_has_no_properties():
    from uasset_read.v2.api import parse_package_document

    doc = parse_package_document(str(SAMPLES / "ABP_RifleAnimLayers.uasset"), depth="package")
    for obj in doc.objects:
        assert obj.properties is None, f"{obj.id} should have no properties at package depth"


def test_large_sample_all_exports():
    """ALS_AnimBP — 3395 exports, 2 asset roles (shares the matrix parse via cache)."""
    from uasset_read.v2.projection import project_document

    doc = _object_document("ALS_AnimBP.uasset")
    assert len(doc.objects) == 3395

    # #631 acceptance: bounded agent request — 25 objects, id/name/class only,
    # relations/dependencies opted out — fits a 10 KB budget; the opted-out
    # keys are absent and the page is schema-valid.
    page = project_document(
        doc, depth="package", fields=["id", "name", "class"], limit=25, sections=[], max_bytes=10_000
    )
    size = len(json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    assert size < 10_000, f"bounded request must fit 10 KB, got {size}"
    assert len(page["objects"]) == 25, page.get("truncation")
    assert "relations" not in page and "dependencies" not in page
    assert not any(d.get("code") in ("TRUNCATED", "BUDGET_EXHAUSTED") for d in page["diagnostics"])
    jsonschema.validate(page, SCHEMA)


def test_zero_asset_role_fixture_is_manifested():
    entry = MANIFEST_BY_NAME["uasset_rs_UE410_SimpleRefsSoftRef.uasset"]
    assert entry["size_bytes"] == 4037
    assert entry["engine_layout"] == "legacy"
    assert entry["export_count"] == 6
    assert entry["b_is_asset_count"] == 0


def test_v2_api_does_not_call_v1_pipeline(monkeypatch):
    import uasset_read.pipeline.core as old_core

    def forbidden(*args, **kwargs):
        raise AssertionError("v1 pipeline called")

    monkeypatch.setattr(old_core, "parse_uasset_with_linker", forbidden)
    # Re-import to get a fresh module-level reference
    from uasset_read.v2.api import parse_package_document

    result = parse_package_document(str(SAMPLES / "ABP_RifleAnimLayers.uasset"), depth="package")
    assert result.package.layout == "legacy"
    assert result.summary.total_exports == len(result.objects)


def test_niagara_fixture_enriched_at_summary_tier():
    """Every Niagara-class object is enriched, but the summary tier stays partial (#629).

    The fixture also contains EdGraphNode_Comment and MetaData exports that no
    handler covers; those are intentionally not asserted here.
    """
    from uasset_read.v2.handlers import NiagaraHandler

    doc = _asset_document("NM_BPSystemEvent.uasset")
    covered = [o for o in doc.objects if o.class_name in NiagaraHandler._NIAGARA_CLASSES]
    assert covered, "Niagara class set must match the fixture"
    for o in covered:
        assert o.semantic and o.semantic["kind"] == "niagara", o.id
        assert o.coverage, o.id
        assert o.status.semantic == "partial", (o.id, o.class_name, o.status.semantic)


def _synthetic_export(**kwargs):
    from uasset_read.serializers.object_resources import ObjectExport, PackageIndex

    base = dict(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="Test",
        object_flags=0,
        serial_size=0,
        serial_offset=0,
    )
    base.update(kwargs)
    return ObjectExport(**base)


def test_preload_relations_use_ue_ranges_and_sign_semantics():
    """Per-export preload ranges index the flat summary array; sign maps like FPackageIndex."""
    from uasset_read.v2.package.legacy import _build_preload_relations

    exports = [
        _synthetic_export(
            first_export_dependency=0,
            serialization_before_serialization_dependencies=2,
            create_before_create_dependencies=1,
        ),
        _synthetic_export(first_export_dependency=-1),
        _synthetic_export(
            first_export_dependency=3,
            serialization_before_serialization_dependencies=2,
        ),
    ]
    # raw values: +2 -> export:1, -4 -> import:3, 0 -> null, -1 -> import:0, +1 -> export:0
    preload = [2, -4, 0, -1, 1]

    relations, diagnostics = _build_preload_relations(preload, exports)
    edges = {(r.kind, r.from_id, r.to_id) for r in relations}
    assert edges == {
        ("preload_of", "export:0", "export:1"),
        ("preload_of", "export:0", "import:3"),
        ("preload_of", "export:2", "import:0"),
        ("preload_of", "export:2", "export:0"),
    }
    assert diagnostics == []


def test_relation_targets_out_of_range_are_dropped_with_diagnostic():
    """A relation whose target exceeds the table size is corrupt data, not an edge."""
    from uasset_read.v2.object_model import Relation
    from uasset_read.v2.package.legacy import _validate_relation_targets

    relations = [
        Relation(kind="outer_of", from_id="export:0", to_id="export:1"),
        Relation(kind="outer_of", from_id="export:1", to_id="export:67108864"),
        Relation(kind="class_of", from_id="export:2", to_id="import:5"),
        Relation(kind="class_of", from_id="export:3", to_id="import:999"),
    ]
    kept, diagnostics = _validate_relation_targets(relations, export_count=2, import_count=6)
    assert [(r.kind, r.from_id, r.to_id) for r in kept] == [
        ("outer_of", "export:0", "export:1"),
        ("class_of", "export:2", "import:5"),
    ]
    assert len(diagnostics) == 2
    assert {d.code for d in diagnostics} == {"RELATION_TARGET_OUT_OF_RANGE"}
    assert {d.object_id for d in diagnostics} == {"export:1", "export:3"}
    assert all(d.recoverable for d in diagnostics)


def test_depends_map_validates_package_index_sign_per_ue_convention():
    """read_depends_map must range-check positives against exports, negatives against imports."""

    class _StubArchive:
        def __init__(self, values):
            self._values = list(values)
            self._pos = 0

        def seek(self, offset):
            self._pos = 0

        def read_i32(self, context):
            value = self._values[self._pos]
            self._pos += 1
            return value

    from types import SimpleNamespace

    from uasset_read.serializers.package_summary import read_depends_map

    summary = SimpleNamespace(depends_offset=1, export_count=3, import_count=5)
    # export 0 list: +2 -> export:1 (valid), -2 -> import:1 (valid),
    # +4 -> export:3 (missing, export_count=3), -99 -> import:98 (missing)
    archive = _StubArchive([4, 2, -2, 4, -99, 0, 0])
    warnings: list[str] = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert result == [[2, -2, 4, -99], [], []]
    invalid = [w for w in warnings if "non-existent" in w]
    assert len(invalid) == 1
    assert "2 PackageIndex value(s)" in invalid[0]


def test_preload_relations_report_invalid_ranges_without_crashing():
    """Out-of-range preload spans produce a structured diagnostic and are skipped."""
    from uasset_read.v2.package.legacy import _build_preload_relations

    exports = [
        _synthetic_export(
            first_export_dependency=2,
            serialization_before_serialization_dependencies=5,
        ),
        _synthetic_export(
            first_export_dependency=0,
            serialization_before_serialization_dependencies=1,
        ),
    ]
    relations, diagnostics = _build_preload_relations([3, -2], exports)
    assert [(r.from_id, r.to_id) for r in relations] == [("export:1", "export:2")]
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "PRELOAD_DEPENDENCY_RANGE_INVALID"
    assert diagnostics[0].object_id == "export:0"
    assert diagnostics[0].recoverable is True


def test_version_context_is_frozen_and_summary_derived():
    """G1 contract: full immutable context built once from the package summary."""
    import dataclasses

    from uasset_read.serializers.package_summary import read_package_summary
    from uasset_read.v2.package.legacy import _make_package_archive
    from uasset_read.v2.source import FileSource
    from uasset_read.v2.version import (
        MappingInfo,
        build_version_context_from_summary,
    )

    archive = _make_package_archive(FileSource(SAMPLES / "ABP_RifleAnimLayers.uasset"), tolerant=True)
    try:
        summary = read_package_summary(archive)
    finally:
        archive.close()

    ctx = build_version_context_from_summary(
        summary,
        package_layout="legacy",
        game="ue",
        mappings=MappingInfo(path="x.usmap"),
        depth="asset",
    )
    # ABP fixture facts verified at plan time: UE4 522, UE5 1004, 10 custom versions,
    # saved/compatible engine version 5.0.0.19274859.
    assert ctx.file_version_ue4 == 522
    assert ctx.file_version_ue5 == 1004
    assert len(ctx.custom_versions) == 10
    assert next(iter(ctx.custom_versions)) == next(iter(summary.custom_versions)).guid
    assert ctx.engine_version is not None and ctx.engine_version.major == 5
    assert ctx.compatible_engine_version is not None
    assert ctx.package_layout == "legacy"
    assert ctx.game == "ue"
    assert ctx.mappings is not None and ctx.mappings.path == "x.usmap"
    assert ctx.depth == "asset"
    assert ctx.is_ue5 is True
    assert ctx.version_string.startswith("5.0")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.file_version_ue5 = 0


def test_blueprint_fixtures_carry_generated_and_cdo_relations():
    """Output Gate: blueprint packages expose generated-class and CDO edges."""
    from uasset_read.v2.api import parse_package_document

    expected = {
        "FirstPerson_BP_FirstPersonCharacter.uasset": {
            ("generated_class_of", "export:2", "export:1"),
            ("default_object_of", "export:3", "export:2"),
        },
        "ABP_RifleAnimLayers.uasset": {
            ("generated_class_of", "export:2", "export:1"),
            ("default_object_of", "export:0", "export:2"),
        },
        "StackOBot_BP_Drone.uasset": {
            ("generated_class_of", "export:1", "export:0"),
            ("default_object_of", "export:2", "export:1"),
        },
        "ALS_AnimBP.uasset": {
            ("generated_class_of", "export:281", "export:274"),
            ("default_object_of", "export:0", "export:281"),
        },
    }
    for sample, edges in expected.items():
        doc = parse_package_document(str(SAMPLES / sample), depth="package")
        actual = {(r.kind, r.from_id, r.to_id) for r in doc.relations}
        for edge in edges:
            assert edge in actual, f"{sample}: missing {edge}"


def test_blueprint_graph_decodes_without_parse_errors():
    """G2 regression (2026-09-02 ue-source audit): editor FText Base carries gated DevNotes."""
    from uasset_read.pipeline.core import parse_uasset

    result = parse_uasset(str(SAMPLES / "BP_CombatCharacter.uasset"), force_full_parse=True)
    graphs = getattr(result, "graphs", None) or []
    nodes = [n for g in graphs for n in (getattr(g, "nodes", None) or [])]
    bad = [
        n
        for n in nodes
        if isinstance(getattr(n, "node_data", None), dict) and n.node_data.get("_parse_error")
    ]
    assert len(nodes) == 370, f"expected 370 graph nodes across 4 graphs, got {len(nodes)}"
    assert not bad, f"{len(bad)}/{len(nodes)} graph nodes failed to parse"
