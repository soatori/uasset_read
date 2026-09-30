"""Sample-first behavior baseline: every tracked check is driven by real samples.

Manifest-driven parse items (one per package) plus a small set of aggregate
checks for manifest closure, golden references, capability claims, quality
ceilings, containers, and sidecars. The collection budget (<=100 suite-wide
items) lives in tests/conftest.py; size and module-count ratchets live in
tests/test_size_baseline.py.

Only SimpleNamespace diagnostics stubs reach internal helpers now (no duck-typed
archives/exports), so strict-object rules are off; ``src/uasset_read`` is the pyright gate (ci.yml).
"""

# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
# pyright: reportOptionalSubscript=false, reportOptionalMemberAccess=false, reportOperatorIssue=false

from __future__ import annotations

from contextlib import contextmanager
import copy
from functools import lru_cache
import hashlib
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(__file__).parent / "samples"
MANIFEST = SAMPLES / "manifest.json"

_MANIFEST_DATA = json.loads(MANIFEST.read_text(encoding="utf-8"))
MANIFEST_SAMPLES = _MANIFEST_DATA["samples"]
MANIFEST_BY_NAME = {entry["name"]: entry for entry in MANIFEST_SAMPLES}
GOLDEN_DIR = SAMPLES / "golden"
GOLDEN_FILES = _MANIFEST_DATA["golden_files"]

# Diagnostic-count ceilings for the quality-system seed fixtures. Regenerate
# with tools/gen_quality_baseline.py after intentional diagnostic-count changes.
QUALITY_BASELINE = json.loads((SAMPLES / "quality_baseline.json").read_text(encoding="utf-8"))

# (sample, class, expected keys, expected status.semantic at depth=asset).
# "complete" requires decoded-tier handler output; summary-tier handlers
# (mesh, blueprint summary, niagara) stay "partial" (#629).
CAPABILITIES = (
    ("ALS_FootstepDataTable.uasset", "DataTable", {"kind": "data_table"}, "complete"),
    # Row blocks are pinned by name, not just by count: the #626 UE 5.8 fixtures proved
    # the row anchor was 4 bytes early, and a count-only assertion cannot see that.
    (
        "FirstPerson_DT_WeaponList.uasset",
        "DataTable",
        {"kind": "data_table", "row_count": 3, "row_names": ["GrenadeLauncher", "Pistol", "Rifle"]},
        "complete",
    ),
    (
        "TestSimpleCurveTable.uasset",
        "CurveTable",
        {
            "kind": "curve_table",
            "curve_table_mode": "SimpleCurves",
            "row_count": 2,
            "row_names": ["RowA", "RowB"],
        },
        "complete",
    ),
    (
        "TestRichCurveTable.uasset",
        "CurveTable",
        {
            "kind": "curve_table",
            "curve_table_mode": "RichCurves",
            "row_count": 2,
            "row_names": ["RowA", "RowB"],
        },
        "complete",
    ),
    (
        "testrCurveTable.uasset",
        "CurveTable",
        {
            "kind": "curve_table",
            "curve_table_mode": "SimpleCurves",
            # Repeated base names are FName instances, so the on-disk Number must
            # render into the row name (Curve, Curve_1, Curve_2).
            "row_count": 3,
            "row_names": ["Curve", "Curve_0", "Curve_1"],
        },
        "complete",
    ),
    (
        "DT_ParserWeapon.uasset",
        "DataTable",
        {"kind": "data_table", "row_count": 2, "row_names": ["EmptyWeaponA", "EmptyWeaponB"]},
        "complete",
    ),
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
    ("ALS_Mannequin_Skeleton.uasset", "Skeleton", {"kind": "skeleton"}, "partial"),
    (
        "StarterContent_SM_Chair.uasset",
        "StaticMesh",
        {"kind": "mesh", "mesh_type": "StaticMesh"},
        "partial",  # summary tier: geometry is not decoded
    ),
    # Flags/editor-position only — not enough core fields for decoded tier (#629 hardening).
    ("FirstPerson_M_PrototypeGrid.uasset", "Material", {"kind": "material"}, "partial"),
    # Real fixture carries 3 scalar + 1 vector parameters (normalized arrays);
    # decoded tier per audit-remediation Task 5.
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
    (
        "ALSCommunity_Mannequin_PhysicsAsset.uasset",
        "PhysicsAsset",
        {"kind": "physics_asset", "body_count": 19, "constraint_count": 18},
        "partial",  # summary tier: collision table/shapes not decoded (#619/#638)
    ),
    (
        "Lyra_PM_Concrete.uasset",
        "PhysicalMaterial",
        {"kind": "physical_material", "surface_type": "EPhysicalSurface::SurfaceType2"},
        "partial",  # float defaults omitted by the editor; SurfaceType is real data
    ),
)


@lru_cache(maxsize=None)
def _asset_document(sample: str):
    from uasset_read.package import parse_package_document

    return parse_package_document(SAMPLES / sample, depth="asset")


@lru_cache(maxsize=None)
def _object_document(sample: str):
    from uasset_read.package import parse_package_document

    return parse_package_document(SAMPLES / sample, depth="object")


@lru_cache(maxsize=None)
def _decode_document(sample: str, object_ids: tuple[str, ...]):
    from uasset_read.package import parse_package_document

    return parse_package_document(SAMPLES / sample, depth="decode", object_ids=list(object_ids))


def _graph_owner_id(doc) -> str | None:
    """Export id of the Blueprint-family asset that owns the package's graphs.

    A graph export's outer chain resolves to the UBlueprint/UAnimBlueprint
    asset export (verified on ABP_RifleAnimLayers and ALS_AnimBP). Returns the
    first family-class export reachable from any EdGraph export's outer.
    """
    family = {"Blueprint", "AnimBlueprint", "BlueprintGeneratedClass", "AnimBlueprintGeneratedClass"}
    by_id = {o.id: o for o in doc.objects}
    for o in doc.objects:
        if (o.class_name or "").endswith("Graph") or (o.class_name or "") == "EdGraph":
            cur = o
            for _ in range(8):
                outer = cur.outer_ref
                if outer is None or outer.table != "export":
                    break
                nxt = by_id.get(f"export:{outer.index}")
                if nxt is None:
                    break
                if (nxt.class_name or "") in family:
                    return nxt.id
                cur = nxt
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _open_sample_archive(sample):
    """Open a fixture archive and yield (archive, summary, name_map, import_map, export_map)."""
    from uasset_read.package import open_package_bundle
    from uasset_read.serializers.object_resources import read_export_map, read_import_map
    from uasset_read.serializers.package_summary import read_name_table, read_package_summary

    archive = open_package_bundle(str(sample)).open_archive(tolerant=True)
    try:
        summary, _ = read_package_summary(archive)
        name_map = read_name_table(archive, summary)
        archive.set_name_map(name_map)
        yield (
            archive,
            summary,
            name_map,
            read_import_map(archive, summary, name_map),
            read_export_map(archive, summary, name_map),
        )
    finally:
        archive.close()


def _raw_depends_map(sample: str):
    """Re-read ObjectDependsMap through the low-level archive, independent of v2."""
    from uasset_read.serializers.package_summary import read_depends_map

    with _open_sample_archive(SAMPLES / sample) as (archive, summary, _names, _imports, _exports):
        return read_depends_map(archive, summary)


PACKAGE_SUFFIXES = {".uasset", ".umap", ".uexp", ".ubulk", ".uptnl"}
ORIGIN_DOCS = {
    "ORIGIN-issue-516-plugin-mount.md",
    "ORIGIN-issue-521-niagara.md",
    "ORIGIN-issue-522-cube-builder.md",
    "ORIGIN-issue-615-618-619-samples.md",
    "ORIGIN-issue-624-iostore.md",
    "ORIGIN-issue-625-pak.md",
    "ORIGIN-issue-626-curve-table.md",
    "ORIGIN-issue-627-sidecar.md",
}


def test_manifest_matches_every_real_sample():
    """The retained real-sample corpus must match its review-controlled manifest exactly."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["version"] == 2
    expected_files = {entry["name"] for entry in manifest["samples"]}
    for entry in manifest["samples"]:
        expected_files |= {side["name"] for side in entry["sidecars"]}
    actual_files = {path.name for path in SAMPLES.iterdir() if path.suffix in PACKAGE_SUFFIXES}
    assert manifest["summary"]["total_samples"] == len(manifest["samples"]) == 66
    assert actual_files == expected_files
    allowed = (
        expected_files
        | {
            "manifest.json",
            "README.md",
            "golden",
            "containers",
            "UnversionedTest.usmap",
            "UnversionedTest.provenance.md",
            "quality_baseline.json",
        }
        | ORIGIN_DOCS
    )
    extra = {path.name for path in SAMPLES.iterdir()} - allowed
    assert not extra, f"Unexpected files in samples/: {extra}"
    for entry in manifest["samples"]:
        path = SAMPLES / entry["name"]
        assert path.exists(), f"Missing sample: {entry['name']}"
        assert path.stat().st_size == entry["size_bytes"], entry["name"]
        assert _sha256(path) == entry["sha256"], entry["name"]
        # A declared sidecar must exist, and an existing sidecar must be declared (#627).
        sides = {side["name"]: side for side in entry["sidecars"]}
        assert set(sides) == {
            path.with_suffix(ext).name for ext in (".uexp", ".ubulk", ".uptnl") if path.with_suffix(ext).exists()
        }, entry["name"]
        for name, side in sides.items():
            side_path = SAMPLES / name
            assert side_path.exists(), f"{entry['name']}: missing sidecar {name}"
            assert side_path.stat().st_size == side["size_bytes"], name
            assert _sha256(side_path) == side["sha256"], name
    # Golden reference tables are manifest-tracked artifacts too (issue #633).
    golden_entries = manifest["golden_files"]
    golden_on_disk = {path.name for path in (SAMPLES / "golden").glob("*.golden.json")}
    assert golden_on_disk == {entry["name"] for entry in golden_entries}
    for entry in golden_entries:
        assert entry["fixture"] in expected_files, entry["name"]
        path = SAMPLES / "golden" / entry["name"]
        assert path.stat().st_size == entry["size_bytes"], entry["name"]
        assert _sha256(path) == entry["sha256"], entry["name"]
    # Zero-asset-role fixture is part of the pinned manifest contract
    # (was tests/test_samples.py::test_zero_asset_role_fixture_is_manifested).
    zero = MANIFEST_BY_NAME["uasset_rs_UE410_SimpleRefsSoftRef.uasset"]
    assert zero["size_bytes"] == 4037
    assert zero["engine_layout"] == "legacy"
    assert zero["export_count"] == 6
    assert zero["b_is_asset_count"] == 0


def test_container_fixtures_match_manifest():
    """Container fixtures get their own integrity gate (#624/#625).

    ``committed: false`` marks a fixture too large for git (GitHub rejects >100 MB).
    Such a file is still hash-checked when this machine has it, so local Phase 5
    evidence cannot silently drift; it is never claimed as CI coverage.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    containers = manifest["containers"]
    manifest_names = {entry["name"] for entry in containers}
    actual_names = {
        path.name for path in (SAMPLES / "containers").iterdir() if path.suffix in {".pak", ".utoc", ".ucas"}
    }
    assert actual_names <= manifest_names
    for entry in containers:
        assert entry["container_kind"] in {"pak", "iostore_toc", "iostore_data"}, entry["name"]
        assert entry["issue"] in {624, 625}, entry["name"]
        path = SAMPLES / "containers" / entry["name"]
        if entry["committed"]:
            assert path.exists(), f"missing committed container: {entry['name']}"
        elif not path.exists():
            assert entry["local_only_reason"], entry["name"]
            continue
        assert path.stat().st_size == entry["size_bytes"], entry["name"]
        assert _sha256(path) == entry["sha256"], entry["name"]
    # A .utoc must always be paired with its .ucas of the same base name.
    utoc_bases = {entry["name"][: -len(".utoc")] for entry in containers if entry["container_kind"] == "iostore_toc"}
    ucas_bases = {entry["name"][: -len(".ucas")] for entry in containers if entry["container_kind"] == "iostore_data"}
    assert utoc_bases == ucas_bases, "every IoStore TOC needs its data archive"


def test_fixture_gap_statuses_pin_the_capability_boundary():
    """A gap status is a capability claim, not an aspiration (#621).

    ``available`` means the capability is proven in CI from tracked files;
    ``partial`` means usable evidence exists locally but no CI-completable
    path; ``missing`` means nothing usable, including negative-only fixtures;
    ``not_required`` means the product explicitly excludes the capability.
    Drifting these upward is how "documented" quietly becomes "implemented".
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    gaps = manifest["fixture_gaps"]
    assert gaps["zen_package"]["status"] == "not_required"
    assert gaps["iostore_container"]["status"] == "not_required"
    assert gaps["pak_container"]["status"] == "available"
    assert gaps["unversioned_properties"]["status"] == "not_required"
    assert gaps["sidecar_files"]["status"] == "available"
    # Hand-written counts drift ("54 samples" survived a corpus of 66): gaps may
    # only cite the manifest's own total, never a literal that ages.
    total = manifest["summary"]["total_samples"]
    for name, gap in gaps.items():
        for count in re.findall(r"\b(\d+) samples\b", gap["description"]):
            assert int(count) == total, name


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


def test_real_sample_proves_claimed_capability():
    """Each claimed capability must produce stable semantics from a real fixture.

    The status column pins the #629 tier contract: decoded-tier fixtures are
    ``complete``; summary-tier fixtures prove ``partial`` with coverage.
    Loops the CAPABILITIES table so 27 claims cost one collected item; every
    assertion message carries ``sample:class_name``.
    """
    for sample, class_name, expected, expected_semantic in CAPABILITIES:
        doc = _asset_document(sample)
        obj = next(item for item in doc.objects if item.class_name == class_name)
        assert obj.status.semantic == expected_semantic, f"{sample}:{class_name}"
        assert obj.coverage, f"{sample}:{class_name}"
        assert {key: obj.semantic[key] for key in expected} == expected, f"{sample}:{class_name}"

        if class_name == "DataTable":
            assert obj.semantic["row_count"] == len(obj.semantic["row_names"]) > 0, f"{sample}:{class_name}"
        elif class_name == "CurveTable":
            sem = obj.semantic
            assert sem["row_count"] == len(sem["row_names"]) > 0, f"{sample}:{class_name}"
            assert sem["curve_table_mode"] in ("SimpleCurves", "RichCurves"), f"{sample}:{class_name}"
            # complete coverage requires the row block to have been exhausted: residue
            # would mean an anchor or row-walk drift, which the reader discloses instead.
            table_cov = next(c for c in obj.coverage if c.feature == "handler.DataTableHandler")
            assert table_cov.status == "present", f"{sample}:{class_name} table payload not fully decoded"
        elif class_name == "Skeleton":
            assert obj.semantic["bone_count"] == len(obj.semantic["bones"]) > 0, f"{sample}:{class_name}"
            # ALS_Mannequin_Skeleton's BoneTree is a UE4-era struct array: ONE inner
            # FPropertyTag then per-element tagged streams (PropertyArray.cpp). Its
            # FBoneNode element streams carry only the retargeting mode; the actual
            # bone names live outside the property region (native payload), so the
            # NameMap regex guess is the honest source and stays summary-tier (#630).
            assert obj.semantic["bone_source"] == "name_guess", f"{sample}:{class_name}"
            names = {b["name"] for b in obj.semantic["bones"]}
            assert "spine_01" in names and "clavicle_l" in names, f"{sample}:{class_name}"
        elif class_name == "StaticMesh":
            assert obj.semantic["lod_count"] == len(obj.semantic["lods"]), f"{sample}:{class_name}"
        elif class_name in {"BlueprintGeneratedClass", "AnimBlueprintGeneratedClass"}:
            assert not {"nodes", "bytecode", "graph", "graphs"} & obj.semantic.keys(), f"{sample}:{class_name}"
            if class_name == "AnimBlueprintGeneratedClass" or sample == "StackOBot_BP_Drone.uasset":
                owner = _graph_owner_id(doc)
                assert owner is not None, f"{sample}:{class_name} graph owner not found"
                dec = _decode_document(sample, (owner,))
                bp = next(o for o in dec.objects if o.id == owner)
                assert bp.semantic is not None, f"{sample}:{class_name} decode"
                if class_name == "AnimBlueprintGeneratedClass":
                    assert bp.semantic["kind"] == "anim_blueprint", f"{sample}:{class_name}"
                    assert bp.status.semantic == "complete", f"{sample}:{class_name} decode tier"
                else:
                    assert bp.semantic["kind"] == "blueprint", f"{sample}:{class_name}"
                assert bp.semantic.get("graphs"), f"{sample}:{class_name} graphs missing"
                node_ids = {n["id"].split("/")[-1] for g in bp.semantic["graphs"] for n in g["nodes"]}
                for graph in bp.semantic["graphs"]:
                    for node in graph["nodes"]:
                        for pin in node["pins"]:
                            for link in pin["links"]:
                                # E1 flip: link endpoints are NodeId strings that may
                                # qualify the node export alone; join on that suffix.
                                target = link["to_node_id"].split("/")[-1]
                                assert target in node_ids, f"{sample} dangling link"
                if sample == "StackOBot_BP_Drone.uasset":
                    # Audit items 2+3: external references and complete signatures.
                    decls = {item["name"]: item for item in bp.semantic["function_declarations"]}
                    uber = decls["ExecuteUbergraph_BP_Drone"]
                    assert [(p["name"], p["type_name"], p["direction"]) for p in uber["parameters"]] == [
                        ("EntryPoint", "IntProperty", "in")
                    ]
                    assert uber["return_type"] is None and uber["cpp_return_type"] == "void"
                    assert uber["flags"] is None and uber["unresolved"] is False
                    look = decls["InpActEvt_IA_Look_K2Node_EnhancedInputActionEvent_0"]
                    assert [(p["name"], p["type_name"], p["direction"]) for p in look["parameters"]] == [
                        ("ActionValue", "StructProperty", "in"),
                        ("ElapsedTime", "FloatProperty", "in"),
                        ("TriggeredTime", "FloatProperty", "in"),
                        ("SourceAction", "ObjectProperty", "in"),
                    ]
                    assert all(p["cpp_type"] for p in look["parameters"])
                    assert all(p["source_range"] is None and p["default_value"] is None for p in look["parameters"])

                    refs = bp.semantic["external_refs"]
                    assert len(refs) == 10, f"got {len(refs)} external refs"
                    conv = next(item for item in refs if item["symbol"] == "Conv_InputActionValueToAxis2D")
                    assert conv["local_id"] == "import:28"
                    assert conv["package"] == "/Script/EnhancedInput"
                    assert conv["class_name"] == "Function"
                    assert conv["qualified_key"] == "/Script/EnhancedInput::Function::Conv_InputActionValueToAxis2D"
                    assert conv["origin"] == "unknown_origin"
                    assert conv["status"] == "resolved" and conv["reason"] == "exact_package_index"
                    assert conv["candidate_local_ids"] == ["import:28"]
                    assert conv["source_evidence"] == [{"kind": "stack_node_package_index", "value": -29}]
                    unresolved_refs = [item for item in refs if item["status"] == "unresolved"]
                    assert {item["symbol"] for item in unresolved_refs} == {
                        "AddMovementInput",
                        "AddControllerYawInput",
                        "AddControllerPitchInput",
                    }
                    assert all(item["local_id"] is None for item in unresolved_refs)
                    assert all(item["reason"] == "no_name_match" for item in unresolved_refs)
                    assert all(item["qualified_key"].startswith("unresolved::") for item in unresolved_refs)
                    assert all(item["origin"] == "unknown_origin" for item in refs)
                    assert all(
                        set(item)
                        == {
                            "local_id",
                            "package",
                            "class_name",
                            "symbol",
                            "qualified_key",
                            "origin",
                            "source_evidence",
                            "status",
                            "reason",
                            "candidate_local_ids",
                        }
                        for item in refs
                    )

                    calls = bp.semantic["calls"]
                    assert len(calls) == 17
                    assert sum(1 for item in calls if item["target_ref_key"] is None) == 2
                    assert sum(1 for item in calls if item["target_ref_key"] is not None) == 15
                    assert all(item["source_node_reason"] == "debug_mapping_unavailable" for item in calls)
                    assert all(
                        entry["source_node_reason"] == "debug_mapping_unavailable"
                        for fn in bp.semantic["functions"]
                        for entry in fn["instructions"]
                    )
                    assert all(
                        item["source_node_reason"] == "debug_mapping_unavailable"
                        for item in bp.semantic["variable_accesses"]
                    )
        elif class_name in {"Texture2D", "TextureCube"}:
            assert isinstance(obj.semantic["srgb"], bool), f"{sample}:{class_name}"
            assert "compression_settings" in obj.semantic, f"{sample}:{class_name}"
            feature_names = [c.feature for c in obj.coverage]
            for feature in ("texture.kind", "texture.texture_type", "texture.srgb", "texture.compression_settings"):
                assert feature in feature_names, f"{sample}:{class_name} missing coverage {feature}"
            twin = copy.deepcopy(obj)
            from uasset_read.parsers.asset_types.handlers_impl import TexturePayloadHandler

            result = TexturePayloadHandler().enrich(twin, "package", doc.objects, None)
            if class_name == "TextureCube":
                # TextureCube doesn't have ImportedSize property, so result is None
                assert result is None, f"{sample}:{class_name}"
            else:
                # May be None if ImportedSize is absent or empty
                if result is not None:
                    payload = result["payload"]
                    assert payload["kind"] == "texture_mip", f"{sample}:{class_name}"
                    assert payload["source_region"] == "main", f"{sample}:{class_name}"
                    assert isinstance(payload["width"], int) and isinstance(payload["height"], int), (
                        f"{sample}:{class_name}"
                    )
                    # Payload must never contain raw bytes
                    assert "raw_bytes" not in payload, f"{sample}:{class_name}"
                payload_features = [c for c in obj.coverage if c.feature == "texture.payload"]
                assert len(payload_features) == 1, f"{sample}:{class_name}"
                assert payload_features[0].status in ("present", "partial"), f"{sample}:{class_name}"
        elif class_name == "SoundWave":
            handler_features = [c for c in obj.coverage if c.feature == "handler.SoundHandler"]
            assert len(handler_features) == 1, f"{sample}:{class_name}"
        elif class_name == "PhysicsAsset":
            # Instanced bodies are real package exports; raw CollisionDisableTable
            # trailer stays a disclosed gap at the parse layer too (#638).
            assert len(obj.semantic["bodies"]) == obj.semantic["body_count"] == 19, f"{sample}:{class_name}"
            features = {c.feature: c.status for c in obj.coverage}
            assert features["physics_asset.bodies"] == "present", f"{sample}:{class_name}"
            assert features["physics_asset.collision_disable_table"] == "missing", f"{sample}:{class_name}"
            assert any(d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED" for d in doc.diagnostics), (
                f"{sample}:{class_name} must disclose the undecoded raw trailer"
            )
        elif class_name == "PhysicalMaterial":
            # Editor defaulted the four floats out of the tag stream: "missing"
            # coverage is correct UE behavior, not a parser failure.
            features = {c.feature: c.status for c in obj.coverage}
            for key in ("friction", "static_friction", "restitution", "density"):
                assert features[f"physical_material.{key}"] == "missing", f"{sample}:{class_name}"
                assert f"physical_material.{key}" not in obj.semantic, f"{sample}:{class_name}"
            assert not any(
                d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED" and d.object_id != "export:0" for d in doc.diagnostics
            ), f"{sample}:{class_name} has no raw trailer by design (export:0 MetaData excluded)"


@pytest.mark.parametrize("sample", [entry["name"] for entry in MANIFEST_SAMPLES])
def test_every_real_sample_forms_a_valid_package_document(sample: str):
    """Every tracked fixture must form a complete, relation-valid, blob-free document."""
    doc = _object_document(sample)
    entry = MANIFEST_BY_NAME[sample]
    from uasset_read.serializers.package_summary import _read_version_and_tag

    ids = [o.id for o in doc.objects]
    assert ids == [f"export:{i}" for i in range(len(ids))], sample
    assert len(ids) == entry["export_count"], sample
    assert doc.package.layout == entry["engine_layout"], sample
    assert doc.package.export_count == entry["export_count"], sample
    assert len(doc.summary.asset_object_ids) == entry["b_is_asset_count"], sample

    with _open_sample_archive(SAMPLES / sample) as (archive, _summary, _names, _imports, _exports):
        archive.seek(0)
        _, _legacy_version, raw_ue4, raw_ue5, *_ = _read_version_and_tag(archive)
        assert raw_ue4 == entry["file_version_ue4"], sample
        assert raw_ue5 == entry["file_version_ue5"], sample

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
            from uasset_read.models.properties import PropertyBag, project_property_bag

            if isinstance(o.properties, PropertyBag):
                blob = json.dumps(project_property_bag(o.properties))
            else:
                blob = json.dumps(o.properties)
            # raw_data legitimately appears as a length-only {"kind": "bytes", ...}
            # descriptor for struct fallbacks; the contract is that it never
            # carries inline bytes, and any truncation marker wins.
            assert "raw_data_truncated" in blob or '"raw_data": "' not in blob, f"{sample}:{o.id}"
        if o.semantic is not None:
            json.dumps(o.semantic)

    bounds = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_BOUNDS_EXCEEDED"]
    failed = [d for d in doc.diagnostics if d.code == "EXPORT_PROPERTY_PARSE_FAILED"]
    oob = [d for d in doc.diagnostics if d.code == "RELATION_TARGET_OUT_OF_RANGE"]
    assert not bounds and not failed and not oob, (
        f"{sample}: unexpected diagnostics {[d.code for d in bounds + failed + oob]}"
    )


def test_v2_path_emits_no_handler_warnings(capfd, caplog, tmp_path):
    # capfd alone cannot catch the leak under pytest: the logging plugin
    # installs a root handler, which suppresses logging.lastResort. Assert
    # on captured WARNING records too — the real contract is "no warning
    # logs on the v2 parse path".
    import logging

    from uasset_read.package import parse_package_document

    root = logging.getLogger()
    handlers_before = tuple(root.handlers)
    files_before = set(tmp_path.iterdir())
    with caplog.at_level(logging.WARNING):
        parse_package_document(SAMPLES / "NM_BPSystemEvent.uasset", depth="object")
    captured = capfd.readouterr()
    assert captured.err == "", f"v2 parse leaked stderr: {captured.err[:200]}"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [], f"v2 parse emitted warning logs: {[r.getMessage()[:120] for r in warnings]}"
    assert tuple(root.handlers) == handlers_before
    assert set(tmp_path.iterdir()) == files_before


def test_v4_public_output_contract(capsys, monkeypatch, tmp_path):
    """Real samples exercise both v4 modes and every public producer route."""
    import sys

    import jsonschema

    from uasset_read.agent_tools import inspect_package
    from uasset_read.package import parse_package_document
    from uasset_read.projection import project_document
    from uasset_read.projections.bundle import write_projected_document

    schema = json.loads(
        (ROOT / "docs" / "designs" / "contract" / "package_document_v4.schema.json").read_text(encoding="utf-8")
    )
    top_level = {
        "format",
        "format_version",
        "mode",
        "source",
        "package",
        "summary",
        "objects",
        "relations",
        "dependencies",
        "projections",
        "payloads",
        "sidecars",
        "diagnostics",
    }
    debug_keys = {
        "object_regions",
        "property_evidence",
        "semantic_source_ranges",
        "payload_sources",
        "sidecar_sources",
        "diagnostic_details",
        "byte_accounting",
    }
    banned_semantic_keys = {
        "source_range",
        "script_source_range",
        "raw_region",
        "tag_range",
        "value_range",
        "raw_data",
    }

    def evidence_key_hits(value, path=""):
        if isinstance(value, dict):
            hits = []
            for key, item in value.items():
                child = f"{path}/{key}"
                if key in banned_semantic_keys:
                    hits.append(child)
                hits.extend(evidence_key_hits(item, child))
            return hits
        if isinstance(value, list):
            return [hit for index, item in enumerate(value) for hit in evidence_key_hits(item, f"{path}/{index}")]
        return []

    def strip_debug(value: Any, *, top_level: bool = False) -> Any:
        if isinstance(value, dict):
            return {
                key: strip_debug(item)
                for key, item in value.items()
                if key != "debug_evidence" and not (top_level and key == "debug")
            }
        if isinstance(value, list):
            return [strip_debug(item) for item in value]
        return value

    samples = (
        "StackOBot_BP_Drone.uasset",
        "T_ParserBulk.uasset",
        "FirstPerson_DT_WeaponList.uasset",
        "BP_CombatCharacter.uasset",
        "MyProject_UE58_TestBlueprint.uasset",
    )
    projected = {}
    for name in samples:
        document = parse_package_document(SAMPLES / name, depth="decode")
        normal = project_document(document, mode="normal")
        debug = project_document(document, mode="debug")
        projected[name] = {"normal": normal, "debug": debug}

        jsonschema.validate(normal, schema)
        jsonschema.validate(debug, schema)
        assert set(normal) == top_level, name
        assert set(debug) == top_level | {"debug"}, name
        assert set(debug["debug"]) == debug_keys, name
        assert all(isinstance(debug["debug"][key], list) for key in debug_keys), name
        stripped = strip_debug(copy.deepcopy(debug), top_level=True)
        stripped["mode"] = "normal"
        assert stripped == normal, name
        for obj in normal["objects"]:
            assert evidence_key_hits(obj.get("semantic")) == [], f"{name}:{obj['id']}"

    # T0: nested debug_evidence is mode-filtered at the semantic boundary.
    from uasset_read.projection import _sanitize_semantic

    sample_semantic = {
        "links": [{"graph_id": "export:0/export:4", "debug_evidence": {"raw_source_pin_guid": "aa"}}],
        "debug_evidence": None,
        "keep": "x",
    }
    hits: list[dict] = []
    normal_semantic = _sanitize_semantic(
        copy.deepcopy(sample_semantic), "export:0", "", hits, strip_debug_evidence=True
    )
    assert "debug_evidence" not in normal_semantic
    assert "debug_evidence" not in normal_semantic["links"][0]
    assert normal_semantic["keep"] == "x"
    debug_semantic = _sanitize_semantic(
        copy.deepcopy(sample_semantic), "export:0", "", hits, strip_debug_evidence=False
    )
    assert debug_semantic["debug_evidence"] is None
    assert debug_semantic["links"][0]["debug_evidence"] == {"raw_source_pin_guid": "aa"}

    stack = projected["StackOBot_BP_Drone.uasset"]
    normal_owner = next(item for item in stack["normal"]["objects"] if item["id"] == "export:0")
    normal_instructions = [entry for fn in normal_owner["semantic"]["functions"] for entry in fn["instructions"]]
    assert len(normal_instructions) == 85
    for entry in normal_instructions:
        assert "serialized_start" not in entry and "serialized_end" not in entry, entry["opcode"]
        assert "debug_evidence" not in entry
    # source_node_reason cross-fixture asserts live in the T5 block below.
    for key in ("calls", "variable_accesses"):
        for entry in normal_owner["semantic"][key]:
            assert "serialized_start" not in entry and "serialized_end" not in entry

    debug_owner = next(item for item in stack["debug"]["objects"] if item["id"] == "export:0")
    debug_instructions = [entry for fn in debug_owner["semantic"]["functions"] for entry in fn["instructions"]]
    assert len(debug_instructions) == len(normal_instructions)
    for entry in debug_instructions:
        evidence = entry["debug_evidence"]
        assert evidence is not None and 0 <= evidence["raw_opcode"] <= 255
        assert evidence["source_node_evidence"] is None
        assert evidence["diagnostics"] == []
        span = evidence["serialized_range"]
        if span is not None:
            assert span["start"] >= 0 and span["end"] == span["start"] + span["size"]
            assert span["status"] in {"decoded", "opaque", "payload", "unavailable"}

    # Audit item 5: three-fixture Blueprint acceptance (T5).
    combat = projected["BP_CombatCharacter.uasset"]
    combat_owner = next(item for item in combat["normal"]["objects"] if item["id"] == "export:1")
    combat_graphs = combat_owner["semantic"]["graphs"]
    assert len(combat_graphs) == 4
    combat_links = [link for graph in combat_graphs for link in graph["links"]]
    assert len(combat_links) == 610
    assert all(link["status"] == "resolved" for link in combat_links)
    assert all("debug_evidence" not in link for link in combat_links), "normal strips nested evidence"
    assert "debug_evidence" not in json.dumps(combat_owner["semantic"])

    test_bp = projected["MyProject_UE58_TestBlueprint.uasset"]
    test_owner = next(item for item in test_bp["normal"]["objects"] if item["id"] == "export:0")
    test_links = [link for graph in test_owner["semantic"]["graphs"] for link in graph["links"]]
    assert len(test_links) == 20
    new_function_graph = next(graph for graph in test_owner["semantic"]["graphs"] if graph["name"] == "NewFunction")
    assert (new_function_graph["node_count"], new_function_graph["pin_count"], len(new_function_graph["links"])) == (
        3,
        8,
        10,
    )
    assert test_owner["semantic"]["external_refs"] == []
    test_decls = {item["name"]: item for item in test_owner["semantic"]["function_declarations"]}
    new_function = test_decls["NewFunction"]
    assert [(p["name"], p["type_name"], p["direction"]) for p in new_function["parameters"]] == [
        ("NewParam", "BoolProperty", "in"),
        ("NewParam1", "BoolProperty", "out"),
    ]
    assert new_function["unresolved"] is False
    test_instructions = [entry for fn in test_owner["semantic"]["functions"] for entry in fn["instructions"]]
    assert len([entry for entry in test_instructions if entry["opcode"] == "EX_JumpIfNot"]) == 1

    # StackOBot: debug is an evidence-only superset of the link records too.
    stack_links_normal = [link for graph in normal_owner["semantic"]["graphs"] for link in graph["links"]]
    assert len(stack_links_normal) == 26
    stack_links_debug = [
        link
        for graph in next(item for item in stack["debug"]["objects"] if item["id"] == "export:0")["semantic"]["graphs"]
        for link in graph["links"]
    ]
    assert len(stack_links_debug) == 26
    assert all(link["debug_evidence"] is not None for link in stack_links_debug)
    assert all("debug_evidence" not in link for link in stack_links_normal)

    # source_node_reason is normal-mode content: present and identical in BOTH
    # modes on every Blueprint fixture entry (no None-in-debug/absent-in-normal
    # asymmetry); measured 2026-09-28: no bytecode<->graph mapping exists on any
    # of these fixtures, so every value is debug_mapping_unavailable.
    for blueprint_name in (
        "StackOBot_BP_Drone.uasset",
        "BP_CombatCharacter.uasset",
        "MyProject_UE58_TestBlueprint.uasset",
    ):
        debug_objects = {item["id"]: item for item in projected[blueprint_name]["debug"]["objects"]}
        for normal_obj in projected[blueprint_name]["normal"]["objects"]:
            debug_semantic = debug_objects[normal_obj["id"]].get("semantic") or {}
            normal_semantic = normal_obj.get("semantic") or {}
            entry_pairs = {
                "instructions": (
                    [entry for fn in normal_semantic.get("functions") or [] for entry in fn["instructions"]],
                    [entry for fn in debug_semantic.get("functions") or [] for entry in fn["instructions"]],
                ),
                "calls": (normal_semantic.get("calls") or [], debug_semantic.get("calls") or []),
                "variable_accesses": (
                    normal_semantic.get("variable_accesses") or [],
                    debug_semantic.get("variable_accesses") or [],
                ),
            }
            for entry_key, (normal_entries, debug_entries) in entry_pairs.items():
                assert len(normal_entries) == len(debug_entries), (blueprint_name, entry_key)
                for normal_entry, debug_entry in zip(normal_entries, debug_entries):
                    assert "source_node_reason" in normal_entry, (blueprint_name, entry_key)
                    assert "source_node_reason" in debug_entry, (blueprint_name, entry_key)
                    assert (
                        normal_entry["source_node_reason"]
                        == debug_entry["source_node_reason"]
                        == "debug_mapping_unavailable"
                    ), (blueprint_name, entry_key, normal_obj["id"])
                    assert normal_entry["source_node_id"] is None, (blueprint_name, entry_key)

    bulk = projected["T_ParserBulk.uasset"]
    payload = next(item for item in bulk["normal"]["payloads"] if item["owner"] == "export:0")
    assert set(payload) <= {"id", "owner", "kind", "stored_size", "status", "logical_size", "compression", "hash"}
    source = next(item for item in bulk["debug"]["debug"]["payload_sources"] if item["payload_id"] == payload["id"])
    assert source["source_region"]["source_id"].endswith(".uexp")
    assert "data" not in payload and "raw_bytes" not in payload

    sample = SAMPLES / "StackOBot_BP_Drone.uasset"
    document = parse_package_document(sample, depth="decode")
    for mode in ("normal", "debug"):
        assert inspect_package(str(sample), mode=mode) == projected[sample.name][mode]

    output_path = write_projected_document(document, tmp_path / "v4-public-output.json")
    assert json.loads(output_path.read_text(encoding="utf-8")) == projected[sample.name]["normal"]

    # Default Python path (no depth override) == CLI == project_document.
    default_doc = parse_package_document(SAMPLES / "StackOBot_BP_Drone.uasset")
    default_owner = next(
        item for item in project_document(default_doc, mode="normal")["objects"] if item["id"] == "export:0"
    )
    assert sum(len(entry["instructions"]) for entry in default_owner["semantic"]["functions"]) == 85
    assert len([link for graph in default_owner["semantic"]["graphs"] for link in graph["links"]]) == 26

    from uasset_read.cli import main

    for args, mode in (([], "normal"), (["--debug"], "debug")):
        monkeypatch.setattr(sys, "argv", ["uasset_read", *args, str(sample)])
        with pytest.raises(SystemExit) as exit_info:
            main()
        assert exit_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        output = json.loads(captured.out)
        assert output == projected[sample.name][mode]


def test_critical_boundary_guards(monkeypatch):
    """Keep the mandatory trust-boundary checks in one bounded aggregate item."""
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.constants import MAX_SAFE_COUNT
    from uasset_read.exceptions import ExportBoundsExceeded, ParseError
    from uasset_read.kismet.native_fields import NativeFieldContext, read_native_fields
    from uasset_read.kismet.archive import FKismetArchive
    from uasset_read.mappings import UsmapParser
    from uasset_read.memory_safety import MemoryLimitExceeded, reserve_memory

    archive = ByteArchive(b"\x00" * 256)
    archive._read_range = (50, 100)
    archive._pos = 80
    assert archive.read(20) == b"\x00" * 20
    with pytest.raises(ExportBoundsExceeded):
        archive.read(1)
    with pytest.raises(ExportBoundsExceeded):
        archive.validate_offset(10, "test_seek")
    with pytest.raises(ExportBoundsExceeded):
        archive.validate_offset(150, "test_seek")

    with pytest.raises(MemoryLimitExceeded, match="negative"):
        reserve_memory(-100, "unit")
    with pytest.raises(MemoryLimitExceeded):
        reserve_memory(17 * 1024 * 1024, "unit")

    context = NativeFieldContext(name_map=[], import_map=[], export_map=[])
    with pytest.raises(ParseError, match="native field count"):
        read_native_fields(ByteArchive(b""), MAX_SAFE_COUNT + 1, context)
    with pytest.raises(ParseError, match="FFieldPath count"):
        FKismetArchive(struct.pack("<i", -1), "test", []).xfer_field_pointer()

    usmap = (0x30C4).to_bytes(2, "little") + bytes([1, 1]) + b"\x00" * 8 + (-1).to_bytes(4, "little", signed=True)
    with pytest.raises(ParseError, match="CustomVersion"):
        UsmapParser(usmap)

    # T5 addendum (1): projected-dict roundtrip keeps the T2/T3 instruction
    # fields — from_dict must restore what the producers emit (analysis.py
    # is a declared from_dict/projected-dict trust boundary).
    from uasset_read.models.analysis import FunctionAnalysis, GraphLinkRecord
    from uasset_read.package import parse_package_document
    from uasset_read.parsers.blueprint.correlation import (
        BlueprintCorrelation,
        external_ref_record,
        project_function_analysis,
        project_semantic_blueprint,
    )
    from uasset_read.parsers.blueprint.graph import _link_record_from_raw
    from uasset_read.projection import project_document
    from uasset_read.serializers.blueprint_graph import resolve_pin_links

    ue58_document = parse_package_document(str(SAMPLES / "MyProject_UE58_TestBlueprint.uasset"), depth="decode")
    debug_document = project_document(ue58_document, mode="debug")
    debug_function = next(
        fn
        for obj in debug_document["objects"]
        if obj["id"] == "export:0"
        for fn in obj["semantic"]["functions"]
        if fn["function_name"] == "NewFunction"
    )
    reemitted = project_function_analysis(FunctionAnalysis.from_dict(debug_function))
    assert reemitted["instructions"] == debug_function["instructions"]
    assert all(entry["source_node_reason"] == "debug_mapping_unavailable" for entry in reemitted["instructions"])
    assert reemitted["instructions"][0]["debug_evidence"] is not None

    # Declaration survival through build() over the projected semantic dict
    # (the _inputs from_dict path): params count, return_type, flags,
    # unresolved and the native-field lists all come back identical — nothing
    # re-declares as unresolved. Measured 2026-09-28: UE58 NewFunction 2
    # params / resolved; StackOBot declarations 1/4/4 params / resolved.
    ue58_live = next(o for o in ue58_document.objects if o.id == "export:0").semantic
    ue58_restored = project_semantic_blueprint(BlueprintCorrelation().build(ue58_document))["function_declarations"]
    assert ue58_restored == ue58_live["function_declarations"]
    new_function = next(d for d in ue58_restored if d["name"] == "NewFunction")
    assert len(new_function["parameters"]) == 2
    assert new_function["unresolved"] is False
    signature = next(d for d in ue58_restored if d["name"].startswith("NewEventDispatcher"))
    assert signature["native_fields"] == [] and signature["unresolved"] is True

    stack_document = parse_package_document(str(SAMPLES / "StackOBot_BP_Drone.uasset"), depth="decode")
    stack_live = next(o for o in stack_document.objects if o.id == "export:0").semantic
    stack_restored = project_semantic_blueprint(BlueprintCorrelation().build(stack_document))["function_declarations"]
    assert stack_restored == stack_live["function_declarations"]
    assert [len(d["parameters"]) for d in stack_restored] == [1, 4, 4]
    assert [d["unresolved"] for d in stack_restored] == [False, False, False]
    assert [len(d["native_fields"]) for d in stack_restored] == [36, 4, 4]

    # T5 addendum (3i): a null LinkedTo slot reaches the public record layer
    # as unresolved/null_link_reference (no real fixture contains null slots).
    synthetic_graph = {
        "id": "export:4",
        "nodes": [{"id": "export:0", "pins": [{"id": "ab" * 16, "linked": []}]}],
        "_pin_links": [
            {
                "from_node": 1,
                "from_pin": "ab" * 16,
                "to_owning_node": None,
                "to_pin": None,
                "null": True,
                "source_category": "exec",
            }
        ],
    }
    resolve_pin_links([synthetic_graph])
    (null_raw,) = synthetic_graph["links"]
    null_record = _link_record_from_raw(null_raw, "export:0", "export:4")
    assert isinstance(null_record, GraphLinkRecord)
    assert (null_record.status, null_record.reason) == ("unresolved", "null_link_reference")
    assert null_record.target_node_id is None and null_record.target_pin_guid is None
    assert null_record.debug_evidence is not None

    # T5 addendum (3ii): a name-only query with 2+ candidates stays ambiguous
    # at the builder (D8) — never silently first-matched.
    ambiguous, ambiguous_key = external_ref_record(
        query="SharedName",
        object_id="export:2",
        match_method="function_identity",
        function_ids_by_name={"SharedName": ["export:2", "export:5"]},
        import_ids_by_name={},
        dep_by_index={},
        class_by_id={},
    )
    assert ambiguous is not None
    assert (ambiguous.status, ambiguous.local_id, ambiguous.reason) == (
        "ambiguous",
        None,
        "2_name_candidates",
    )
    assert ambiguous.candidate_local_ids == ["export:2", "export:5"]
    assert ambiguous.qualified_key == ambiguous_key == "unresolved::SharedName"

    import uasset_read.serializers.object_resources as object_resources

    from uasset_read.package import _parse_cached, parse_package_document

    original_export = object_resources.ObjectExport
    calls = {"count": 0}

    def fail_second_export(**kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise ValueError("injected export table entry failure")
        return original_export(**kwargs)

    _parse_cached.cache_clear()
    try:
        monkeypatch.setattr(object_resources, "ObjectExport", fail_second_export)
        document = parse_package_document(str(SAMPLES / "FirstPerson_DT_WeaponList.uasset"), depth="package")
    finally:
        _parse_cached.cache_clear()
    assert document.objects[0].id == "export:0"
    assert any(d.code == "EXPORT_TABLE_TRUNCATED" for d in document.diagnostics)

    import uasset_read.mappings as mappings

    def missing_codec(*args, **kwargs):
        raise ImportError("optional codec unavailable")

    monkeypatch.setattr(mappings, "UsmapParser", missing_codec)
    _parse_cached.cache_clear()
    try:
        document = parse_package_document(
            str(SAMPLES / "BP_UnversionedTest.uasset"),
            depth="package",
            mappings_path=str(SAMPLES / "UnversionedTest.usmap"),
        )
    finally:
        _parse_cached.cache_clear()
    assert document.package.export_count == MANIFEST_BY_NAME["BP_UnversionedTest.uasset"]["export_count"]
    assert any(d.code == "MAPPINGS_LOAD_FAILED" for d in document.diagnostics)

    from uasset_read.serializers.graph_pin import read_pin_array

    # T1: LinkedTo retains serialized null slots + per-reference byte ranges;
    # other pin arrays (SubPins) keep the historical skip-null behavior.
    payload = struct.pack("<ii", 2, 1) + struct.pack("<ii", 0, 3) + b"\x11" * 16
    kept = read_pin_array(ByteArchive(payload), [], [], retain_nulls=True)
    assert [entry.get("null") for entry in kept] == [True, False]
    assert kept[0]["owning_node"] is None and kept[0]["pin_guid"] is None
    assert kept[1]["owning_node"] == 3 and kept[1]["pin_guid"] == "11" * 16
    assert kept[0]["ref_range"] == (4, 8) and kept[1]["ref_range"] == (8, 32)
    skipped = read_pin_array(ByteArchive(payload), [], [])
    assert len(skipped) == 1 and "null" not in skipped[0]


def test_object_depth_parses_only_requested_export():
    from uasset_read.package import parse_package_document

    doc = parse_package_document(str(SAMPLES / "ABP_RifleAnimLayers.uasset"), depth="object", object_ids=["export:1"])
    parsed = [obj.id for obj in doc.objects if obj.properties is not None]
    assert parsed == ["export:1"]
    assert len(doc.objects) == doc.package.export_count


def test_package_depth_has_no_properties():
    from uasset_read.package import parse_package_document

    doc = parse_package_document(str(SAMPLES / "ABP_RifleAnimLayers.uasset"), depth="package")
    for obj in doc.objects:
        assert obj.properties is None, f"{obj.id} should have no properties at package depth"


def test_large_sample_all_exports():
    """ALS_AnimBP — 3395 exports, 2 asset roles (shares the matrix parse via cache)."""

    doc = _object_document("ALS_AnimBP.uasset")
    assert len(doc.objects) == 3395
    assert doc.relations and doc.dependencies


def test_niagara_fixture_enriched_at_summary_tier():
    """Every Niagara-class object is enriched, but the summary tier stays partial (#629).

    The fixture also contains EdGraphNode_Comment and MetaData exports that no
    handler covers; those are intentionally not asserted here.
    """
    from uasset_read.parsers.asset_types.handlers_impl import NiagaraHandler

    doc = _asset_document("NM_BPSystemEvent.uasset")
    covered = [o for o in doc.objects if o.class_name in NiagaraHandler.classes]
    assert covered, "Niagara class set must match the fixture"
    for o in covered:
        assert o.semantic and o.semantic["kind"] == "niagara", o.id
        assert o.coverage, o.id
        assert o.status.semantic == "partial", (o.id, o.class_name, o.status.semantic)


def test_blueprint_fixtures_carry_generated_and_cdo_relations():
    """Output Gate: blueprint packages expose generated-class and CDO edges."""
    from uasset_read.package import parse_package_document

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
    """G2 regression (2026-09-02 ue-source audit): editor FText Base carries gated DevNotes.

    v2 decode contract: BP_CombatCharacter exposes all 4 graphs (370 nodes)
    on the owning export and emits no graph-failure diagnostics.
    """
    from uasset_read.package import parse_package_document

    doc = parse_package_document(str(SAMPLES / "BP_CombatCharacter.uasset"), depth="decode")
    graphs = [g for o in doc.objects for g in (o.semantic or {}).get("graphs") or []]
    nodes = [n for g in graphs for n in g["nodes"]]
    assert len(graphs) == 4 and len(nodes) == 370, f"got {len(graphs)} graphs / {len(nodes)} nodes"
    assert not [g for g in graphs if g.get("parse_errors")], "graph-level parse errors"
    assert not [d for d in doc.diagnostics if d.code.startswith("BLUEPRINT_GRAPH")], "graph diagnostics"

    # Audit item 1: one GraphLinkRecord per serialized LinkedTo slot (T1).
    links = [link for g in graphs for link in g.get("links") or []]
    assert len(links) == 610, f"got {len(links)} link records for {len(graphs)} graphs"
    assert sum(1 for link in links if link["status"] == "resolved") == 610
    assert all(link["reason"] for link in links)
    assert all(link["graph_id"].startswith("export:1/export:") for link in links)
    assert all(link["source_node_id"].startswith("export:1/export:") for link in links)
    assert all(link["source_pin_guid"] for link in links)
    assert {link["connection_type"] for link in links} <= {"exec", "data", "delegate", "unknown"}
    evidence = [link["debug_evidence"] for link in links]
    assert all(isinstance(item, dict) for item in evidence)
    assert all(
        isinstance(item["raw_source_owner_package_index"], int) and item["raw_source_owner_package_index"] > 0
        for item in evidence
    )
    assert all(isinstance(item["source_pin_range"], dict) for item in evidence)
    linked_total = sum(len(pin.get("links") or []) for g in graphs for n in g["nodes"] for pin in n["pins"])
    assert linked_total == 610, "pin adjacency must stay a derived view of the records"


def test_als_graph_owners_resolve_beyond_eight_hops():
    """Task 7: ALS's 74 nine-hop outer chains must attach, not go unresolved.

    Direct graph extraction stays at 275; the decode pass no longer reports
    the known BLUEPRINT_GRAPH_OWNER_UNRESOLVED owner-loss diagnostics.
    """
    from uasset_read.package import parse_package_document
    from uasset_read.serializers.blueprint_graph import read_blueprint_graphs

    # Direct extraction: graph count is a fixture regression, owner-independent.
    with _open_sample_archive(SAMPLES / "ALS_AnimBP.uasset") as (
        archive,
        summary,
        name_map,
        import_map,
        export_map,
    ):
        graphs = read_blueprint_graphs(archive, summary, name_map, import_map, export_map)
    assert len(graphs) == 275, f"expected 275 direct graphs, got {len(graphs)}"
    for graph in graphs:
        for node in graph["nodes"]:
            assert node["id"].startswith("export:"), node

    # Full decode: every graph attaches to a Blueprint-family owner.
    doc = parse_package_document(str(SAMPLES / "ALS_AnimBP.uasset"), depth="decode", tolerant=True)
    owner_unresolved = [d for d in doc.diagnostics if d.code == "BLUEPRINT_GRAPH_OWNER_UNRESOLVED"]
    assert not owner_unresolved, f"nine-hop owners must resolve: {len(owner_unresolved)} unresolved"
    attached = sum(len((o.semantic or {}).get("graphs") or []) for o in doc.objects)
    assert attached == 275, f"expected all 275 graphs attached, got {attached}"


# --------------------------------------------------------------------------- #
# Container fixtures (#624/#625): index reading only, never package parsing.
# --------------------------------------------------------------------------- #

CONTAINERS = SAMPLES / "containers"


def test_iostore_toc_fixture_headers_match_ue_struct_fields():
    """Both committed .utoc files must parse to the FIoStoreTocHeader values on disk."""
    from uasset_read.iostore import IoStoreTocError, read_toc

    primary = read_toc(CONTAINERS / "MyProject-Windows.utoc")
    assert primary.version == 8 and primary.header_size == 144
    assert primary.entry_count == 2221 == len(primary.chunks)
    assert primary.compression_block_count == 6694 == len(primary.blocks)
    assert primary.compression_block_size == 65536
    assert primary.compression_methods == ("None", "Oodle")
    assert primary.container_flags == 0x09  # Compressed | Indexed (IoDispatcher.h:435-444)
    assert not primary.encrypted and not primary.signed
    assert primary.encryption_key_guid == "0" * 32  # unencrypted: #624 requires no private key
    assert primary.directory_index_size == 35658
    assert primary.mount_point == "../../../"
    assert primary.data_path and Path(primary.data_path).name == "MyProject-Windows.ucas"

    # The secondary container is the committed .utoc/.ucas pair: one chunk, no index.
    secondary = read_toc(CONTAINERS / "global.utoc")
    assert secondary.version == 8
    assert secondary.entry_count == 1
    assert secondary.chunks[0].type_name == "ScriptObjects"
    assert secondary.compression_block_count == 49 == len(secondary.blocks)
    assert secondary.directory_index_size == 0 and secondary.files == ()

    with pytest.raises(IoStoreTocError):
        read_toc(CONTAINERS / "global.ucas")  # a data archive is not a TOC


def test_iostore_directory_index_lists_real_packages():
    """#624 verification: package names must be listable from the directory index.

    File names come from ``FIoDirectoryIndexResource`` and bind to their ExportBundle
    chunk through ``FIoFileIndexEntry.UserData`` (IoDirectoryIndex.cpp:407-442), which is
    what makes a container package *locatable* rather than merely present.
    """
    from uasset_read.iostore import read_toc

    toc = read_toc(CONTAINERS / "MyProject-Windows.utoc")
    packages = [f.path for f in toc.package_files()]
    assert len(packages) == 575, "one ExportBundle chunk per cooked package"
    assert len(packages) == len(set(packages))
    assert len([p for p in packages if p.endswith((".uasset", ".umap"))]) >= 5

    # Chunk offsets/lengths are the *logical* range, so on a compressed container they are
    # not bounded by the .ucas. The block table is the physical mapping and must be.
    ucas = Path(toc.data_path) if toc.data_path else None
    if ucas and ucas.exists():
        assert sum(b.compressed_size for b in toc.blocks) <= ucas.stat().st_size
        last = max(toc.blocks, key=lambda b: b.offset + b.compressed_size)
        assert last.offset + last.compressed_size <= ucas.stat().st_size
        assert any(c.length > 0 and c.compressed for c in toc.chunks)
    for chunk in toc.chunks:
        assert chunk.chunk_id[11] == chunk.type_id

    # The three families #624 asks for are individually locatable. Class identity needs
    # the package body (Phase 5), so this is a name-level assertion, not a type claim.
    by_family = {
        "Blueprint": "MyProject/Content/Test/TestBlueprint.uasset",
        "DataTable": "MyProject/Content/Test/TestDataTable.uasset",
        "Material": "MyProject/Content/LevelPrototyping/Materials/M_PrototypeGrid.uasset",
    }
    for family, expected in by_family.items():
        assert any(p.endswith(expected) for p in packages), f"{family} package not listed: {expected}"
        located = next(f for f in toc.package_files() if f.path.endswith(expected))
        chunk = toc.chunks[located.chunk_index]
        assert chunk.type_name == "ExportBundleData"
        assert chunk.length > 0


def test_iostore_toc_read_does_not_load_the_container():
    """A TOC read must never copy the .ucas into memory (#624 implementation acceptance).

    The 247 MB data archive is local-only (gitignored, ``committed: false``); when it is
    absent this asserts the TOC still parses, which is what CI sees.
    """
    import tracemalloc

    from uasset_read.iostore import read_toc

    toc_path = CONTAINERS / "MyProject-Windows.utoc"
    tracemalloc.start()
    try:
        toc = read_toc(toc_path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 32 * 1024 * 1024, f"TOC read peaked at {peak} bytes with {toc.entry_count} entries"
    assert toc.compression_block_count == len(toc.blocks)


_UE5_SPLIT_SAMPLES = [
    s
    for s in _MANIFEST_DATA["samples"]
    if any(sc["name"].endswith(".uexp") for sc in s.get("sidecars", [])) and s.get("file_version_ue5", 0) >= 1018
]


def test_missing_sidecar_diagnostic():
    """A split package without its .uexp emits PACKAGE_SIDECAR_MISSING."""
    import shutil
    import tempfile

    from uasset_read.package import parse_package_document

    for sample_entry in _UE5_SPLIT_SAMPLES:
        main_path = SAMPLES / sample_entry["name"]
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / main_path.name
            shutil.copy2(main_path, dst)
            # Do NOT copy the .uexp — simulate missing sidecar.
            doc = parse_package_document(dst, depth="package")
            codes = [d.code for d in doc.diagnostics]
            assert "PACKAGE_SIDECAR_MISSING" in codes, (
                f"expected PACKAGE_SIDECAR_MISSING for {sample_entry['name']}, got: {codes}"
            )


def _assert_quality_baseline(doc, name: str) -> None:
    entry = QUALITY_BASELINE["samples"][name]
    codes = [d.code for d in doc.diagnostics]
    for forbidden in entry.get("forbidden_codes", []):
        assert forbidden not in codes, f"{name}: forbidden diagnostic {forbidden}"

    max_total = entry.get("max_total_diagnostics")
    if max_total is not None:
        assert len(doc.diagnostics) <= max_total, (
            f"{name}: total diagnostics {len(doc.diagnostics)} > baseline max_total {max_total}"
        )

    def _count(code: str, reason: str | None) -> int:
        return sum(1 for d in doc.diagnostics if d.code == code and d.reason == reason)

    for code, by_reason in entry.get("max_by_code_reason", {}).items():
        for reason_key, rule in by_reason.items():
            reason = None if reason_key == "_" else reason_key
            actual = _count(code, reason)
            assert actual <= rule["max"], f"{name}: {code}/{reason_key} count {actual} > baseline max {rule['max']}"

    if entry.get("forbid_unlisted"):
        known = {
            (code, None if rk == "_" else rk)
            for code, by_reason in entry.get("max_by_code_reason", {}).items()
            for rk in by_reason
        }
        unlisted = sorted(
            {(d.code, d.reason) for d in doc.diagnostics if (d.code, d.reason) not in known},
            key=lambda pair: (pair[0], pair[1] or ""),
        )
        assert not unlisted, (
            f"{name}: unlisted (code, reason) pairs {unlisted}; regenerate baseline or classify the diagnostic"
        )


def test_quality_baseline_gate_behavior():
    """Fail paths and opt-in plumbing of the quality gate itself (was 5 items).

    forbid_unlisted rejects new (code, reason) pairs; max_total_diagnostics
    rejects overflow; opt-in entries stay out of the default sample set.
    """
    cases = [
        (
            {
                "forbid_unlisted": True,
                "max_by_code_reason": {"EXPORT_TRAILING_BYTES_UNCONSUMED": {"editor_only": {"max": 1}}},
            },
            [
                SimpleNamespace(code="EXPORT_TRAILING_BYTES_UNCONSUMED", reason="editor_only"),
                SimpleNamespace(code="NAME_INDEX_OUT_OF_RANGE", reason="recovered_corruption"),
            ],
            "unlisted",
        ),
        (
            {"max_total_diagnostics": 0, "max_by_code_reason": {}},
            [SimpleNamespace(code="EXPORT_TRAILING_BYTES_UNCONSUMED", reason="editor_only")],
            "total diagnostics",
        ),
    ]
    for entry, diags, match in cases:
        name = "__fail_path__"
        QUALITY_BASELINE["samples"][name] = {**entry, "forbidden_codes": []}
        try:
            with pytest.raises(AssertionError, match=match):
                _assert_quality_baseline(SimpleNamespace(diagnostics=diags), name)
        finally:
            QUALITY_BASELINE["samples"].pop(name, None)

    default_only = {"A.uasset": {"opt_in": False}, "B.uasset": {"opt_in": True}, "C.uasset": {}}
    assert _quality_baseline_sample_names(False, samples=default_only) == ["A.uasset", "C.uasset"]
    assert _quality_baseline_sample_names(True, samples=default_only) == ["A.uasset", "B.uasset", "C.uasset"]

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("UASSET_QUALITY_OPT_IN", "1")
        assert _quality_baseline_include_opt_in() is True
        mp.delenv("UASSET_QUALITY_OPT_IN", raising=False)
        assert _quality_baseline_include_opt_in() is False


def _quality_baseline_include_opt_in() -> bool:
    return os.environ.get("UASSET_QUALITY_OPT_IN") == "1"


def _quality_baseline_sample_names(
    include_opt_in: bool,
    samples: dict | None = None,
) -> list[str]:
    src = QUALITY_BASELINE["samples"] if samples is None else samples
    names = []
    for name, entry in src.items():
        if entry.get("opt_in") and not include_opt_in:
            continue
        names.append(name)
    return sorted(names)


def test_quality_baseline_diagnostics():
    from uasset_read.package import parse_package_document

    names = _quality_baseline_sample_names(_quality_baseline_include_opt_in())
    assert names, "quality_baseline.json must list at least one default sample"
    for sample_name in names:
        doc = parse_package_document(str(SAMPLES / sample_name), depth="asset")
        _assert_quality_baseline(doc, sample_name)


def test_trailing_diagnostics_carry_structured_size():
    """Trailing bytes must be machine-readable (Diagnostic.size), not message-only."""
    from uasset_read.package import parse_package_document

    doc = parse_package_document(str(SAMPLES / "StarterContent_Starter_Background_Cue.uasset"), depth="asset")
    trailing = [d for d in doc.diagnostics if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED"]
    assert trailing, "fixture must emit trailing diagnostics"
    for d in trailing:
        assert d.size is not None and d.size > 0, f"{d.object_id}: missing structured size"
        assert d.reason is not None
        # Message and structured field must agree.
        assert f"leaves {d.size} undecoded bytes" in d.message


def test_background_cue_sound_node_tails_reclassified_editor_only():
    """Starter_Background_Cue: 6 SoundNode trailers, 6 bytes each, now editor_only."""
    from uasset_read.package import parse_package_document

    doc = parse_package_document(str(SAMPLES / "StarterContent_Starter_Background_Cue.uasset"), depth="asset")
    by_id = {o.id: o for o in doc.objects}
    sound_trailing = [
        d
        for d in doc.diagnostics
        if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED"
        and (by_id[d.object_id].class_name or "").startswith("SoundNode")
    ]
    assert len(sound_trailing) == 6
    assert all(d.reason == "editor_only" for d in sound_trailing)
    assert all(d.size == 6 for d in sound_trailing)
    assert sum(d.size or 0 for d in sound_trailing) == 36  # d.size: int | None (type-checker)
    # No SoundNode trailer may remain in the catch-all bucket.
    assert not [d for d in sound_trailing if d.reason == "unexpected"]


def test_level_geometry_tails_known_unimplemented_with_bytes():
    """FirstPerson umap: Level/Model/Polys/World trailers keep bytes, lose unexpected."""
    from uasset_read.package import parse_package_document

    doc = parse_package_document(str(SAMPLES / "FirstPerson_Lvl_FirstPerson.umap"), depth="asset")
    by_id = {o.id: o for o in doc.objects}
    expected = {  # object_id -> (class, size)
        "export:6": ("Level", 199),
        "export:7": ("Model", 154),
        "export:8": ("Model", 190),
        "export:11": ("Polys", 1060),
        "export:13": ("World", 12),
    }
    trailing = {d.object_id: d for d in doc.diagnostics if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED"}
    for oid, (cls, size) in expected.items():
        d = trailing[oid]
        assert by_id[oid].class_name == cls, oid
        assert d.reason == "known_unimplemented", f"{oid}: {d.reason}"
        assert d.size == size, f"{oid}: {d.size} != {size}"
    assert not [
        d for d in doc.diagnostics if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED" and d.reason == "unexpected"
    ], "FirstPerson_Lvl must have zero unexpected after reclassification"


def test_collision_and_enum_pose_movie_tails_known_unimplemented():
    from uasset_read.package import parse_package_document

    cases = {
        "StarterContent_SM_Chair.uasset": {"BodySetup_13": 20, "NavCollision_9": 32},
        "Lyra_Enum_PanelType.uasset": {"Enum_PanelType": 53},
        "StackOBot_Enum_CameraState.uasset": {"Enum_CameraState": 85},
        "Echo_calf_l_PoseAsset.uasset": {"calf_l_PoseAsset": 16},
    }
    for sample, expect in cases.items():
        doc = parse_package_document(str(SAMPLES / sample), depth="asset")
        by_id = {o.id: o for o in doc.objects}
        found = {by_id[d.object_id].name: d for d in doc.diagnostics if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED"}
        for name, size in expect.items():
            d = found[name]
            assert d.reason == "known_unimplemented", f"{sample}:{name}: {d.reason}"
            assert d.size == size, f"{sample}:{name}: {d.size} != {size}"

    # MovieScene_0 no longer trails at all: the validated map-value fallback
    # (2026-09-23 moviescene plan) consumes ExpansionStates cleanly, so export:9
    # ends with zero EXPORT_TRAILING_BYTES_UNCONSUMED — fixed, not classified.
    lyra = parse_package_document(str(SAMPLES / "Lyra_SEQ_LobbyScreen_LevelSequence.uasset"), depth="asset")
    lyra_trailing = [
        d for d in lyra.diagnostics if d.code == "EXPORT_TRAILING_BYTES_UNCONSUMED" and d.object_id == "export:9"
    ]
    assert not lyra_trailing, lyra_trailing


def _assert_trailing_aggregate(actual: dict, baseline: dict) -> None:
    assert actual["sample_count"] == baseline["sample_count"], (
        f"aggregate sample_count {actual['sample_count']} != baseline {baseline['sample_count']}; "
        "regenerate quality_baseline.json (manifest changed)"
    )
    assert actual["max_total_warnings"] == baseline["max_total_warnings"], (
        f"trailing warnings {actual['max_total_warnings']} != baseline {baseline['max_total_warnings']} "
        "(totals must match; regenerate the baseline to review the change)"
    )
    assert actual["max_total_bytes"] == baseline["max_total_bytes"], (
        f"total bytes {actual['max_total_bytes']} != baseline {baseline['max_total_bytes']} "
        "(totals must match; regenerate the baseline to review the change)"
    )
    for reason, stats in actual["by_reason"].items():
        assert reason in baseline["by_reason"], f"reason mix: {reason} not in baseline"
        limit = baseline["by_reason"][reason]
        assert stats["max_count"] <= limit["max_count"], f"{reason}: count {stats['max_count']} > {limit['max_count']}"
        assert stats["max_bytes"] <= limit["max_bytes"], f"{reason}: bytes {stats['max_bytes']} > {limit['max_bytes']}"
    unlisted = sorted(set(actual["by_reason_class"]) - set(baseline["by_reason_class"]))
    assert not unlisted, f"not in baseline (new reason/class pair): {unlisted}"
    for key, stats in actual["by_reason_class"].items():
        limit = baseline["by_reason_class"][key]
        assert stats["max_count"] <= limit["max_count"], f"{key}: count {stats['max_count']} > {limit['max_count']}"
        assert stats["max_bytes"] <= limit["max_bytes"], f"{key}: bytes {stats['max_bytes']} > {limit['max_bytes']}"


def _aggregate_from_manifest():
    import gen_quality_baseline  # pyright: ignore[reportMissingImports] -- pytest adds tools/ via pythonpath

    docs = [(entry["name"], _asset_document(entry["name"])) for entry in MANIFEST_SAMPLES]
    return gen_quality_baseline.aggregate_trailing_report(docs)


def test_trailing_aggregate_report_within_baseline():
    """Report-level gate: all 66 manifest samples, counts AND bytes, by reason and class."""
    actual = _aggregate_from_manifest()
    baseline = json.loads((SAMPLES / "quality_baseline.json").read_text(encoding="utf-8"))["aggregate"]
    _assert_trailing_aggregate(actual, baseline)
    assert actual["sample_count"] == 66


def test_trailing_aggregate_gate_blocks_growth():
    """Fail path: a synthetic report over ceiling in bytes or with a new class must fail."""
    baseline = {
        "scope": "manifest",
        "sample_count": 2,
        "max_total_warnings": 3,
        "max_total_bytes": 40,
        "by_reason": {"unexpected": {"max_count": 3, "max_bytes": 40}},
        "by_reason_class": {"unexpected/ABP_X_C": {"max_count": 3, "max_bytes": 40}},
    }

    def _check(actual, match):
        with pytest.raises(AssertionError, match=match):
            _assert_trailing_aggregate(actual, baseline)

    good = {
        "scope": "manifest",
        "sample_count": 2,
        "max_total_warnings": 3,
        "max_total_bytes": 40,
        "by_reason": {"unexpected": {"max_count": 2, "max_bytes": 30}},
        "by_reason_class": {"unexpected/ABP_X_C": {"max_count": 2, "max_bytes": 30}},
    }
    # Totals exactly at ceiling, detail under it: passes (called directly, no raise).
    _assert_trailing_aggregate(good, baseline)

    over_bytes = dict(good, max_total_bytes=41)
    _check(over_bytes, "total bytes")
    # Loss regressions: totals BELOW baseline must also fail (gate is exact on totals).
    lost_warnings = dict(good, max_total_warnings=1)
    _check(lost_warnings, "trailing warnings")
    lost_bytes = dict(good, max_total_bytes=20)
    _check(lost_bytes, "total bytes")
    over_reason = {
        **good,
        "by_reason": {"unexpected": {"max_count": 2, "max_bytes": 30}, "editor_only": {"max_count": 1, "max_bytes": 5}},
    }
    _check(over_reason, "reason mix")
    new_pair = {"max_count": 1, "max_bytes": 3}
    new_class = dict(good, by_reason_class={**good["by_reason_class"], "unexpected/NewClass": new_pair})
    _check(new_class, "not in baseline")


def test_edgraphpin_type_payload_is_native_not_a_tagged_loop():
    """#655: an FEdGraphPinType tag payload is native bytes, never an inner tag loop.

    ``TStructOpsTypeTraits<FEdGraphPinType>::WithSerializer = true`` (EdGraphPin.h)
    sets STRUCT_SerializeNative, so ``UScriptStruct::SerializeItem`` calls
    ``FEdGraphPinType::Serialize`` (EdGraphPin.cpp) and only reaches
    ``SerializeTaggedProperties`` when that declines. Reading the payload as an
    inner property-tag loop instead reads payload FNames as field names and
    types, inventing keys (a category FName such as "int" becomes a field, and a
    raw package index comes back numericized rather than resolved).

    Both payloads below are fixed hex fixtures, not bytes lifted from a tracked
    sample: the sizes they exercise (69 scalar / 101 map) are proven only by
    tracked UE 5.4-5.8 saves — ALS_AnimBP (5.4, 494 x 69), BP_CombatCharacter
    (5.8, 29 x 69), StackOBot_GI_StackOBot (5.6, 11 x 69),
    LevelDesign_ABP_Manny (5.7, 6 x 69), MyProject_UE58_TestBlueprint (5.8,
    9 x 69 + 1 x 101). Every tracked sample that carries a PinType tag is either
    UE 4.11 (legacy 66/71-byte layouts, rejected) or UE 5.4-5.8 — no tracked
    PinType evidence covers UE 5.0-5.3 or a pre-31 terminal, so those layouts are
    deliberately unproven here.

    The two sizes are UE-source gated, not universal: the trailing
    ``bSerializeAsSinglePrecisionFloat`` is written only at
    ``FUE5ReleaseStreamObjectVersion >= 36`` (EdGraphPin.cpp:330-333) and the
    map terminal's ``bTerminalIsUObjectWrapper`` only at
    ``FReleaseObjectVersion >= 31`` (EdGraphNode.cpp:99-101,
    ReleaseObjectVersion.h:110). Below those gates the payload is 65/97 bytes
    (docs/designs/archive/issue-521-b0-gate-decision.md byte-walks a
    UE5ReleaseStream 33 fixture) and the decoder rejects it to opaque.

    The map payload is the layout pin — its FEdGraphTerminalType is 32 bytes
    (EdGraphNode.cpp, operator<<(FArchive&, FEdGraphTerminalType&)), so a 20-byte
    terminal read shifts member_name and member_guid onto payload bytes.
    """
    from uasset_read.archive import ByteArchive
    from uasset_read.models.properties import PropertyTag
    from uasset_read.parsers.property_types import parse_struct_property

    name_map = ["None"] * 400
    name_map[188] = "int"
    name_map[306] = "struct"

    scalar = bytes.fromhex(
        "bc00000000000000f3000000000000000000000000000000000000000000000000f30000000000000000000000000000000000000000000000000000000000000000000000"
    )
    map_pin = bytes.fromhex(
        "bc00000000000000f30000000000000000000000033201000000000000f30000000000000088ffffff000000000000000000000000000000000000000000000000f30000000000000000000000000000000000000000000000000000000000000000000000"
    )
    assert (len(scalar), len(map_pin)) == (69, 101)

    scalar_fields = {
        "pin_category",
        "pin_subcategory",
        "pin_subcategory_object",
        "container_type",
        "is_reference",
        "is_weak_pointer",
        "member_parent",
        "member_name",
        "member_guid",
        "is_const",
        "is_uobject_wrapper",
        "b_serialize_as_single_precision_float",
    }
    map_fields = scalar_fields | {
        "map_terminal_category",
        "map_terminal_subcategory",
        "map_terminal_subcategory_object",
    }

    scalar_value = parse_struct_property(
        PropertyTag(name="VarType", type="StructProperty", size=len(scalar), struct_type="EdGraphPinType"),
        ByteArchive(scalar),
        name_map,
        [],
    )
    assert scalar_value.parse_status == "success"
    assert set(scalar_value.fields) == scalar_fields
    assert scalar_value.fields["pin_category"] == "int"
    assert scalar_value.fields["container_type"] == 0
    assert scalar_value.fields["member_name"] == "None"

    map_archive = ByteArchive(map_pin)
    map_value = parse_struct_property(
        PropertyTag(name="VarType", type="StructProperty", size=len(map_pin), struct_type="EdGraphPinType"),
        map_archive,
        name_map,
        [],
    )
    # Exactly the payload is consumed: no decode may spill into the next property.
    assert map_archive.tell() == len(map_pin)
    assert map_value.parse_status == "success"
    assert set(map_value.fields) == map_fields
    assert map_value.fields["container_type"] == 3
    assert map_value.fields["map_terminal_category"] == "struct"
    assert map_value.fields["map_terminal_subcategory_object"] == -120
    # A 20-byte terminal read lands both of these on raw payload bytes instead.
    assert map_value.fields["member_name"] == "None"
    assert map_value.fields["member_guid"] == "0" * 32

    # Refusal matrix (#655 review F2/F5, folded here to hold the 100-item
    # collection budget): any size outside {69,101}, container_type outside
    # 0..3, a ct/size pairing violation, or a short raw payload must refuse
    # to the opaque path — never decode fabricated values. The F-form alias
    # routes through the same handler and the same refusals.
    def _refused(raw: bytes, struct_type: str = "EdGraphPinType") -> bool:
        archive = ByteArchive(raw)
        value = parse_struct_property(
            PropertyTag(name="VarType", type="StructProperty", size=len(raw), struct_type=struct_type),
            archive,
            name_map,
            [],
        )
        return value.parse_status != "success"

    assert _refused(scalar[:65])  # pre-36 gate shape (69−4)
    assert _refused(scalar + b"\x00")  # 70 B
    assert _refused(scalar[:20] + bytes([111]) + scalar[21:])  # FString-era ct=111
    assert _refused(scalar[:20] + bytes([4]) + scalar[21:])  # ct outside 0..3
    assert _refused(scalar[:20] + bytes([3]) + scalar[21:])  # scalar payload must not claim map
    assert _refused(map_pin[:20] + bytes([0]) + map_pin[21:])  # map payload must not claim scalar
    assert _refused(scalar[:60])  # raw shorter than declared size
    assert _refused(scalar[:65], struct_type="FEdGraphPinType")
    assert not _refused(scalar, struct_type="FEdGraphPinType")


def test_edgraphpin_type_undecodable_payload_is_opaque_and_diagnosed():
    """#655: an undecodable PinType payload is opaque + diagnosed, never silent or fabricated.

    ``StarterContent_Starter_Background_Cue`` (UE 4.11) carries 11 x 66-byte and
    1 x 71-byte ``EdGraphPinType`` tags in the pre-PinsStoreFName FString layout
    (FString "SoundNode"/"Root" category names, so byte 20 falls inside a string
    on the 71-byte one and reads as container_type 111). Neither size is the
    modern 69/101 layout, so the decoder refuses both: the guard must consume the
    payload, report an opaque struct with no fields, and emit one structured
    diagnostic per payload carrying offset + size — the constraint "unknown data
    is preserved as an opaque region plus a diagnostic".
    """
    from uasset_read.package import parse_package_document

    doc = parse_package_document(str(SAMPLES / "StarterContent_Starter_Background_Cue.uasset"), depth="asset")

    pin_diags = [d for d in doc.diagnostics if d.code == "edgraphpin_type_undecodable"]
    assert sorted(d.size for d in pin_diags) == [66] * 11 + [71], [d.size for d in pin_diags]
    assert all(d.offset is not None for d in pin_diags), "diagnostic must carry the payload offset"
    assert all(d.stage == "parse_properties" and d.reason == "known_unimplemented" for d in pin_diags)
    # One diagnostic per payload, attributed to the owning export — never swallowed.
    assert len({d.object_id for d in pin_diags}) == 12

    pin_values = [
        entry.value
        for obj in doc.objects
        for entry in getattr(obj.properties, "entries", None) or []
        if entry.name == "PinType"
    ]
    assert len(pin_values) == 12
    for value in pin_values:
        inner = value.get("value") if isinstance(value, dict) and value.get("kind") == "value" else value
        assert isinstance(inner, dict) and inner["kind"] == "struct" and inner["fields"] == {}, (
            "undecodable payload must stay an empty opaque struct, not fabricated fields",
            inner,
        )
