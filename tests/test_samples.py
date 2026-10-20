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

# Diagnostic-count ceilings, hand-edited when a gate trips (see tools/gen_quality_baseline.py).
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
    # Task 1.0 measured: 3 scalar + 1 vector parameters (normalized arrays) and
    # a Parent whose import map resolves to M_Template_Master_Copy — every
    # promised field of the complete contract is asserted (Appendix B row 3).
    (
        "CassiniSample_MI_Template_BaseGray_Metal.uasset",
        "MaterialInstanceConstant",
        {
            "kind": "material_instance",
            "name": "MI_Template_BaseGray_Metal",
            "has_parent": True,
            "scalar_param_count": 3,
            "vector_param_count": 1,
        },
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
    # Task 1.0 carriage confirmation (temp/carriage_report.md) over the full
    # manifest: these two are the only BlendSpace/StringTable carriers, so the
    # zero-assertion classes each anchor on their measured values.
    (
        "FirstPerson_BS_Idle_Walk_Run.uasset",
        "BlendSpace",
        {"kind": "anim_blend_space", "blend_space_type": "BlendSpace", "sample_count": 27},
        "partial",  # summary tier: BlendParameters absent here, so axes coverage is missing (#618/#629)
    ),
    (
        "IntroToUnreal_StrT_Titles.uasset",
        "StringTable",
        {"kind": "string_table", "table_type": "StringTable", "namespace": "StrT_Titles", "entry_count": 16},
        "partial",  # summary tier: trailer per-key metadata unparsed (#615/#629)
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
        # Mirror the production mount point (LegacyPackageReader.read): the
        # threshold readers below consume archive.version_context (G1).
        from uasset_read.versioning import build_version_context

        archive.version_context = build_version_context(summary)
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
    assert manifest["summary"]["total_samples"] == len(manifest["samples"]) == 67
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
    # Runner absence folded into this aggregate for the collection budget (the CLI is the manual trigger).
    assert not (Path(__file__).parent / "extra_samples" / "run_extra_samples.py").exists()


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
    # Topic 2 Phase 1 (#657): five registered handler classes have no carrier in
    # any tracked package (Task 1.0 carriage confirmation), so their real-sample
    # CAPABILITIES row is absent by evidence — this pin is the assertion.
    assert gaps["skeletal_mesh"]["status"] == "missing"
    assert gaps["anim_composite"]["status"] == "missing"
    assert gaps["anim_layer_interface"]["status"] == "missing"
    assert gaps["material_function"]["status"] == "missing"
    assert gaps["material_parameter_collection"]["status"] == "missing"
    # D1 (plan blueprint-semantics): UE4 graph node/pin decoding stays an
    # explicit gap — no fixture exists and nothing is promised until the user
    # supplies a node-bearing UE4 Blueprint and the phase-A path plus the
    # PinsStoreFName/legacy pin-name gates are verified case by case.
    ue4_gap = gaps["ue4_graph_nodes"]
    assert ue4_gap["status"] == "missing"
    assert "用户" in ue4_gap["acquisition"] or "user" in ue4_gap["acquisition"].lower()
    assert "PinsStoreFName" in ue4_gap["verification"]
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


def _tagged_data_table_document(
    cells,
    *,
    prefix_size=0,
    terminated=True,
    terminator_index=0,
    summary=None,
    soft_paths=None,
    import_map=None,
    export_map=None,
    row_name_index=1,
):
    """One bounded legacy row, with hand-written tag/value bytes."""
    import struct

    from uasset_read.archive import ByteArchive, SourceInfo
    from uasset_read.models.document import PackageDocument, PackageInfo
    from uasset_read.models.object_model import ObjectRecord
    from uasset_read.models.properties import PropertyBag
    from uasset_read.parsers.asset_types.registry import run_handlers
    from uasset_read.parsers.legacy_reader import _read_table_rows
    from uasset_read.versioning import VersionContext

    names = ["None", "RowA"]
    row = b""
    for name, type_name, value in cells:
        names.extend([name, type_name])
        if type_name == "BoolProperty":
            row += struct.pack("<IIIIiiB", len(names) - 2, 0, len(names) - 1, 0, 0, 0, value)
        else:
            row += struct.pack("<IIIIii", len(names) - 2, 0, len(names) - 1, 0, len(value), 0) + value
    blob = b"\0" * prefix_size + struct.pack("<iII", 1, row_name_index, 0) + row
    if terminated:
        blob += struct.pack("<II", terminator_index, 0)
    archive = ByteArchive(blob)
    archive.seek(prefix_size)
    archive.set_read_range((prefix_size, len(blob)))
    if soft_paths is not None:
        archive._soft_object_paths = soft_paths
    # Synthetic caller outside the production chains (Step 0): mount the
    # context explicitly — mirrors the old getattr-0 defaults of the
    # payload._file_version_* copy for this bare archive.
    archive.version_context = VersionContext(
        file_version_ue4=getattr(summary, "file_version_ue4", 0),
        file_version_ue5=getattr(summary, "file_version_ue5", 0),
    )
    diagnostics = []
    rows = _read_table_rows(
        archive,
        len(blob),
        names,
        "export:0",
        diagnostics,
        summary=summary,
        import_map=import_map or [],
        export_map=export_map or [],
    )
    obj = ObjectRecord("export:0", 0, "Table", class_name="DataTable", properties=PropertyBag())
    result = run_handlers(obj, "decode", [obj], ([], names, {obj.id: {"table_rows": rows}}, None))
    obj.semantic = result.semantic
    document = PackageDocument(
        source=SourceInfo("memory", "Table", len(blob)),
        package=PackageInfo("Table", "legacy"),
        objects=[obj],
        diagnostics=diagnostics,
        depth="decode",
    )
    return rows, document


def _assert_data_table_row_values_decode_tagged_scalars():
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.exceptions import ParseError
    from uasset_read.models.properties import PropertyTag, project_property_value
    from uasset_read.projection import project_document
    from uasset_read.parsers.property_types import make_enum_value
    from uasset_read.parsers.property_types import parse_enum_property, parse_object_property
    from uasset_read.parsers.property_parser import parse_property_value
    from uasset_read.versioning import VersionContext

    enum = parse_enum_property(
        PropertyTag(name="Mode", type="EnumProperty", size=8, enum_type="EALSSpawnType"),
        ByteArchive(struct.pack("<II", 0, 0)),
        ["Location"],
    )
    assert project_property_value(enum) == {
        "kind": "enum",
        "enum_type": "EALSSpawnType",
        "value": "EALSSpawnType::Location",
    }
    unknown_enum = parse_enum_property(
        PropertyTag(name="Mode", type="EnumProperty", size=8),
        ByteArchive(struct.pack("<II", 0, 0)),
        ["Location"],
    )
    assert project_property_value(unknown_enum) == {
        "kind": "enum",
        "enum_type": "UnknownEnum",
        "value": "Location",
    }

    maps = ([object() for _ in range(11)], [object(), object()])
    for raw, expected in (
        (-11, {"kind": "object_ref", "table": "import", "index": 10, "id": "import:10"}),
        (2, {"kind": "object_ref", "table": "export", "index": 1, "id": "export:1"}),
        (0, None),
    ):
        archive = ByteArchive(struct.pack("<i", raw))
        archive._object_reference_maps = maps
        value = parse_object_property(PropertyTag(name="Target", type="ObjectProperty", size=4), archive)
        assert project_property_value(value) == expected
    map_archive = ByteArchive(struct.pack("<iiii", 0, 1, -11, 42))
    map_archive._object_reference_maps = maps
    map_archive.version_context = VersionContext(file_version_ue4=0, file_version_ue5=0)
    map_value = parse_property_value(
        PropertyTag(name="Lookup", type="MapProperty", size=16, inner_type="ObjectProperty", value_type="IntProperty"),
        map_archive,
        [],
        [],
    )
    assert project_property_value(map_value) == {
        "kind": "map",
        "key_type": "ObjectProperty",
        "value_type": "IntProperty",
        "entries": [
            {
                "key": {"kind": "object_ref", "table": "import", "index": 10, "id": "import:10"},
                "value": 42,
            }
        ],
    }
    invalid_archive = ByteArchive(struct.pack("<i", -12))
    invalid_archive._object_reference_maps = maps
    invalid_archive._current_object_id = "export:0"
    with pytest.raises(ParseError):
        parse_object_property(PropertyTag(name="Target", type="ObjectProperty", size=4), invalid_archive)
    (diagnostic,) = invalid_archive.get_structured_diagnostics()
    assert diagnostic.code == "OBJECT_PROPERTY_INDEX_INVALID"
    assert diagnostic.object_id == "export:0" and diagnostic.offset == 0

    assert (
        make_enum_value("EAttachLocation", "KeepRelativeOffset")["value_name"] == "EAttachLocation::KeepRelativeOffset"
    )
    assert (
        make_enum_value("EAttachLocation", "EAttachLocation::KeepRelativeOffset")["value_name"]
        == "EAttachLocation::KeepRelativeOffset"
    )

    rows, document = _tagged_data_table_document([("Count", "IntProperty", struct.pack("<i", 42))])
    assert rows["complete"] is True

    assert rows["row_names"] == ["RowA"]
    assert rows["rows"][0]["fields"]["Count"]["value"] == 42
    normal = project_document(document, mode="normal")
    table = next(p for p in normal["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"] == [{"name": "RowA", "values": {"Count": 42}}]
    assert table["content"]["values_decoded"] is True
    assert table["status"] == "translated"
    assert table["completeness"] == "complete"
    assert document.objects[0].status.semantic == "complete"
    json.dumps(normal)

    # A one-byte IntProperty must stay opaque rather than read the next tag.
    rows, document = _tagged_data_table_document(
        [
            ("ShortCount", "IntProperty", b"\x2a"),
            ("Count", "IntProperty", struct.pack("<i", 42)),
        ]
    )
    normal = project_document(document, mode="normal")
    table = next(p for p in normal["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"] == {
        "ShortCount": {"kind": "opaque", "type": "IntProperty", "size": 1, "reason": "parse_error"},
        "Count": 42,
    }
    assert rows["complete"] is True
    assert table["content"]["values_decoded"] is False
    assert table["completeness"] == "partial"
    assert document.objects[0].status.semantic == "partial"

    rows, document = _tagged_data_table_document(
        [
            ("Enabled", "BoolProperty", True),
            ("Count", "IntProperty", struct.pack("<i", 42)),
        ]
    )
    assert rows["rows"][0]["fields"]["Enabled"]["value"] is True
    assert rows["rows"][0]["fields"]["Count"]["value"] == 42
    assert rows["complete"] is True

    rows, document = _tagged_data_table_document(
        [("Count", "IntProperty", struct.pack("<i", 42))],
        row_name_index=99,
    )
    assert rows["row_names"] == ["<row:99>"]
    assert rows["complete"] is False
    diagnostic = next(d for d in document.diagnostics if d.code == "TABLE_ROW_NAME_INDEX_INVALID")
    assert diagnostic.object_id == "export:0" and diagnostic.offset == 4
    assert any(d.code == "TABLE_ROWS_TRUNCATED" for d in document.diagnostics)
    assert document.objects[0].status.semantic == "partial"
    for projection in project_document(document)["projections"]:
        assert projection["status"] == "represented"
        assert projection["completeness"] == "partial"

    rows, document = _tagged_data_table_document(
        [("InvalidName", "NameProperty", struct.pack("<II", 99, 0))],
        prefix_size=16,
    )
    diagnostic = next(d for d in document.diagnostics if d.code == "name_index_out_of_range")
    assert diagnostic.offset == 52  # prefix + row count + row FName + legacy tag
    assert diagnostic.object_id == "export:0"
    table = next(p for p in project_document(document)["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"]["InvalidName"] == {
        "kind": "opaque",
        "type": "NameProperty",
        "size": 8,
        "reason": "parse_error",
    }
    assert table["content"]["values_decoded"] is False
    assert table["completeness"] == "partial"

    rows, document = _tagged_data_table_document(
        [("Count", "IntProperty", struct.pack("<i", 42))],
        terminator_index=99,
    )
    assert rows["complete"] is False
    assert any(d.code == "name_index_out_of_range" and d.offset == 40 for d in document.diagnostics)
    assert any(d.code == "TABLE_ROWS_TRUNCATED" for d in document.diagnostics)
    assert document.objects[0].status.semantic == "partial"
    for projection in project_document(document)["projections"]:
        assert projection["completeness"] == "partial"

    rows, document = _tagged_data_table_document([("Count", "IntProperty", struct.pack("<i", 42))], terminated=False)
    assert rows["complete"] is False
    assert any(d.code == "TABLE_ROWS_TRUNCATED" for d in document.diagnostics)
    assert document.objects[0].status.semantic == "partial"
    for projection in project_document(document)["projections"]:
        assert projection["completeness"] == "partial"


def _assert_data_table_projection_stays_partial_when_any_cell_is_opaque():
    import struct

    from uasset_read.projection import project_document

    rows, document = _tagged_data_table_document(
        [
            ("Count", "IntProperty", struct.pack("<i", 42)),
            ("Mystery", "UnsupportedProperty", b"\x01\x02"),
        ]
    )
    assert rows["rows"][0]["fields"]["Count"]["value"] == 42
    normal = project_document(document, mode="normal")
    table = next(p for p in normal["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"] == {
        "Count": 42,
        "Mystery": {"kind": "opaque", "type": "UnsupportedProperty", "size": 2, "reason": "unsupported_type"},
    }
    assert table["content"]["values_decoded"] is False
    for projection in normal["projections"]:
        assert projection["status"] == "represented"
        assert projection["completeness"] == "partial"
    assert document.objects[0].status.semantic == "partial"
    json.dumps(normal)

    _, references = _tagged_data_table_document(
        [
            ("Imported", "ObjectProperty", struct.pack("<i", -11)),
            ("Exported", "ObjectProperty", struct.pack("<i", 2)),
            ("Null", "ObjectProperty", struct.pack("<i", 0)),
        ],
        import_map=[object() for _ in range(11)],
        export_map=[object(), object()],
    )
    table = next(p for p in project_document(references)["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"] == {
        "Imported": {"kind": "object_ref", "table": "import", "index": 10, "id": "import:10"},
        "Exported": {"kind": "object_ref", "table": "export", "index": 1, "id": "export:1"},
        "Null": None,
    }
    assert table["content"]["values_decoded"] is True
    assert references.objects[0].status.semantic == "complete"

    _, invalid_reference = _tagged_data_table_document(
        [("Target", "ObjectProperty", struct.pack("<i", -2))],
        import_map=[object()],
    )
    table = next(p for p in project_document(invalid_reference)["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"]["Target"] == {
        "kind": "opaque",
        "type": "ObjectProperty",
        "size": 4,
        "reason": "parse_error",
    }
    assert table["content"]["values_decoded"] is False
    assert table["completeness"] == "partial"
    diagnostic = next(d for d in invalid_reference.diagnostics if d.code == "OBJECT_PROPERTY_INDEX_INVALID")
    assert diagnostic.object_id == "export:0" and diagnostic.offset == 36
    assert invalid_reference.objects[0].status.semantic == "partial"

    from uasset_read.models.properties import SoftObjectPathValue

    paths = [SoftObjectPathValue("SoftObjectProperty", "/Game/Test.Asset", "")]
    summary = SimpleNamespace(file_version_ue5=1008, package_flags=0)
    _, indexed = _tagged_data_table_document(
        [("Path", "SoftObjectProperty", struct.pack("<i", 0))],
        summary=summary,
        soft_paths=paths,
    )
    table = next(p for p in project_document(indexed)["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"]["Path"] == {
        "kind": "soft_object_path",
        "raw_kind": "SoftObjectProperty",
        "asset_path": "/Game/Test.Asset",
        "sub_path": "",
    }
    _, inline = _tagged_data_table_document(
        [("Path", "SoftObjectProperty", struct.pack("<IIIII", 1, 0, 2, 0, 0))],
        summary=summary,
        soft_paths=paths,
    )
    table = next(p for p in project_document(inline)["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"]["Path"]["asset_path"] == "RowA.Path"
    _, null = _tagged_data_table_document(
        [("Path", "SoftObjectProperty", struct.pack("<i", -1))],
        summary=summary,
        soft_paths=paths,
    )
    table = next(p for p in project_document(null)["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"]["Path"]["asset_path"] == ""
    _, invalid = _tagged_data_table_document(
        [("Path", "SoftObjectProperty", struct.pack("<i", 9))],
        summary=summary,
        soft_paths=paths,
    )
    table = next(p for p in project_document(invalid)["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"]["Path"]["kind"] == "opaque"
    assert table["content"]["values_decoded"] is False
    assert table["completeness"] == "partial"
    diagnostic = next(d for d in invalid.diagnostics if d.code == "SOFT_OBJECT_PATH_INDEX_INVALID")
    assert diagnostic.offset == 36

    for raw, asset_path in (
        (struct.pack("<i", 0), "/Game/Test.Asset"),
        (struct.pack("<IIIII", 1, 0, 2, 0, 0), "RowA.Path"),
        (struct.pack("<i", -1), ""),
    ):
        _, soft_class = _tagged_data_table_document(
            [("Path", "SoftClassProperty", raw)],
            summary=summary,
            soft_paths=paths,
        )
        table = next(p for p in project_document(soft_class)["projections"] if p["kind"] == "data_table")
        assert table["content"]["rows"][0]["values"]["Path"] == {
            "kind": "soft_object_path",
            "raw_kind": "SoftClassProperty",
            "asset_path": asset_path,
            "sub_path": "",
        }
        assert table["content"]["values_decoded"] is True
    _, invalid_class = _tagged_data_table_document(
        [("Path", "SoftClassProperty", struct.pack("<i", 9))],
        summary=summary,
        soft_paths=paths,
    )
    table = next(p for p in project_document(invalid_class)["projections"] if p["kind"] == "data_table")
    assert table["content"]["rows"][0]["values"]["Path"]["kind"] == "opaque"
    assert table["content"]["values_decoded"] is False
    assert table["completeness"] == "partial"
    assert any(d.code == "SOFT_OBJECT_PATH_INDEX_INVALID" and d.offset == 36 for d in invalid_class.diagnostics)

    # The existing handler cap must not upgrade 50 of 51 rows to complete.
    from uasset_read.parsers.asset_types.registry import run_handlers

    obj = document.objects[0]
    capped_rows = {
        "row_count": 51,
        "row_names": [f"Row{i}" for i in range(51)],
        "rows": [
            {"name": f"Row{i}", "fields": {"Count": {"type": "IntProperty", "size": 4, "value": 42}}} for i in range(51)
        ],
        "complete": True,
    }
    obj.coverage.clear()
    obj.semantic = None
    obj.status.semantic = "not_requested"
    capped_result = run_handlers(obj, "decode", [obj], ([], [], {obj.id: {"table_rows": capped_rows}}, None))
    obj.semantic = capped_result.semantic
    assert obj.status.semantic == "partial"
    assert len(obj.semantic["rows"]) == 50
    assert obj.semantic["row_count"] == 51
    capped = project_document(document, mode="normal")
    for projection in capped["projections"]:
        assert projection["status"] == "represented"
        assert projection["completeness"] == "partial"
    table = next(p for p in capped["projections"] if p["kind"] == "data_table")
    assert table["content"]["values_decoded"] is False


def test_real_sample_proves_claimed_capability():
    """Each claimed capability must produce stable semantics from a real fixture.

    The status column pins the #629 tier contract: decoded-tier fixtures are
    ``complete``; summary-tier fixtures prove ``partial`` with coverage.
    Loops the CAPABILITIES table so 29 claims cost one collected item; every
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
            if sample == "FirstPerson_DT_WeaponList.uasset":
                from uasset_read.projection import project_document
                from uasset_read.package import parse_package_document

                projected = project_document(parse_package_document(SAMPLES / sample, depth="decode"), mode="normal")
                table = next(p for p in projected["projections"] if p["kind"] == "data_table")
                assert table["content"]["row_names"] == ["GrenadeLauncher", "Pistol", "Rifle"]
                assert table["content"]["values_decoded"] is True
                assert table["status"] == "translated"
                assert table["completeness"] == "complete"
                for row in table["content"]["rows"]:
                    assert len(row["values"]) == 2
                    mesh = f"/Game/Weapons/{row['name']}/Meshes/SM_{row['name']}.SM_{row['name']}"
                    actor = (
                        f"/Game/Variant_Shooter/Blueprints/Pickups/Weapons/BP_ShooterWeapon_{row['name']}"
                        f".BP_ShooterWeapon_{row['name']}_C"
                    )
                    assert row["values"] == {
                        "StaticMesh_10_8456479142D90AC54009A190C6522528": {
                            "kind": "soft_object_path",
                            "raw_kind": "SoftObjectProperty",
                            "asset_path": mesh,
                            "sub_path": "",
                        },
                        "SpawnActor_13_12829FCF4BC69EE56781F8AEEB1A9DD8": {
                            "kind": "soft_object_path",
                            "raw_kind": "SoftObjectProperty",
                            "asset_path": actor,
                            "sub_path": "",
                        },
                    }
                json.dumps(projected)
            elif sample == "ALS_FootstepDataTable.uasset":
                fields = obj.semantic["rows"][0]["fields"]
                assert fields["SoundAttachmentType"]["value"] == {
                    "kind": "enum",
                    "enum_type": "EAttachLocation",
                    "value": "EAttachLocation::KeepRelativeOffset",
                }
                assert fields["Sound"]["value"] == {
                    "kind": "object_ref",
                    "table": "import",
                    "index": 10,
                    "id": "import:10",
                }
                assert fields["DecalMaterial"]["value"] == {
                    "kind": "object_ref",
                    "table": "import",
                    "index": 3,
                    "id": "import:3",
                }
                assert fields["NiagaraSystem"]["value"] is None
                from uasset_read.package import parse_package_document
                from uasset_read.projection import project_document

                projected = project_document(parse_package_document(SAMPLES / sample, depth="decode"), mode="normal")
                table = next(p for p in projected["projections"] if p["kind"] == "data_table")
                assert table["content"]["values_decoded"] is True
                assert table["status"] == "translated"
                assert table["completeness"] == "complete"
                dependencies = {item["index"]: item for item in projected["dependencies"]}
                assert dependencies[10]["object_name"] == "Footstep_Cue"
                assert dependencies[3]["object_name"] == "M_DecalFootprint"
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
                    # C3 matrix (plan blueprint-semantics): the corpus exhibits
                    # the object_id/1.0 and unresolved/0.0 rows; the 0.9/0.7/0.5
                    # function_identity rows are pinned synthetically in
                    # test_critical_boundary_guards.
                    matrix = {(item["match_method"], item["confidence"]) for item in calls}
                    assert matrix == {("object_id", 1.0), ("unresolved", 0.0)}, matrix
                    assert all(item["unresolved"] == (item["confidence"] == 0.0) for item in calls)
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
        elif class_name == "MaterialInstanceConstant":
            # Envelope-layer assertions (coordinator ruling): the v4 completeness
            # enum string is the acceptance form of the internal 0.5 ratio, and
            # parent_resolved/parent must never contradict each other.
            from uasset_read.package import parse_package_document
            from uasset_read.projection import project_document

            projected = project_document(parse_package_document(SAMPLES / sample, depth="decode"), mode="normal")
            instance = next(p for p in projected["projections"] if p["kind"] == "material_instance")
            assert instance["status"] == "represented", f"{sample}:{class_name}"
            assert instance["completeness"] == "partial", f"{sample}:{class_name}"
            assert instance["content"]["parent_resolved"] is True, f"{sample}:{class_name}"
            assert instance["content"]["parent"] == "M_Template_Master_Copy", (
                f"{sample}:{class_name} parent_resolved/parent contradict"
            )
            parameters = next(p for p in projected["projections"] if p["kind"] == "material_parameters")
            assert parameters["content"]["scalar_parameters"] == obj.semantic["scalar_param_count"], (
                f"{sample}:{class_name} scalar count drift"
            )
            assert parameters["content"]["vector_parameters"] == obj.semantic["vector_param_count"], (
                f"{sample}:{class_name} vector count drift"
            )
            json.dumps(projected)
        elif class_name == "StringTable":
            # Task 1.4 option (i): the zero-projection absence is declared as a
            # capability-matrix row (semantics stay in objects[].semantic), and
            # the promised entries field is asserted against the measured count.
            from uasset_read.projections.registry import CAPABILITY_MATRIX

            row = next(r for r in CAPABILITY_MATRIX if r["family"] == "string_table")
            assert row["asset_kinds"] == ["string_table"] and row["kinds"] == [], f"{sample}:{class_name}"
            assert row["rule"].startswith("no embedded projections"), f"{sample}:{class_name}"
            assert len(obj.semantic["entries"]) == obj.semantic["entry_count"] == 16, f"{sample}:{class_name}"


@pytest.mark.parametrize("sample", [entry["name"] for entry in MANIFEST_SAMPLES])
def test_every_real_sample_forms_a_valid_package_document(sample: str, monkeypatch):
    """Every tracked fixture must form a complete, relation-valid, blob-free document."""
    # 方案甲 single-instance hook (A5-2): count VersionContext constructions
    # during this parse — exactly one per document, windows reference-copy it.
    from uasset_read.package import _parse_cached, parse_package_document
    import uasset_read.versioning as _versioning

    _orig_vc = _versioning.VersionContext
    vc_count = {"n": 0}

    class _CountingVC(_orig_vc):
        def __init__(self, *args, **kwargs):
            vc_count["n"] += 1
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(_versioning, "VersionContext", _CountingVC)
    _parse_cached.cache_clear()
    doc = parse_package_document(SAMPLES / sample, depth="object")
    assert vc_count["n"] == 1, f"{sample}: VersionContext constructed {vc_count['n']} times, expected 1"
    monkeypatch.undo()
    entry = MANIFEST_BY_NAME[sample]
    from uasset_read.serializers.package_summary import _read_version_and_tag
    from uasset_read.versioning import (
        CORE_GUID,
        FORTNITE_GUID,
        FRAMEWORK_GUID,
        RELEASE_GUID,
        build_version_context,
    )

    ids = [o.id for o in doc.objects]
    assert ids == [f"export:{i}" for i in range(len(ids))], sample
    assert len(ids) == entry["export_count"], sample
    assert doc.package.layout == entry["engine_layout"], sample
    assert doc.package.export_count == entry["export_count"], sample
    assert len(doc.summary.asset_object_ids) == entry["b_is_asset_count"], sample

    with _open_sample_archive(SAMPLES / sample) as (archive, summary, _names, _imports, _exports):
        archive.seek(0)
        _, _legacy_version, raw_ue4, raw_ue5, raw_licensee, *_ = _read_version_and_tag(archive)
        assert raw_ue4 == entry["file_version_ue4"], sample
        assert raw_ue5 == entry["file_version_ue5"], sample
        # raw == effective == gate (A5-3): all-zero raw normalizes to the
        # AUTOMATIC_VERSION pair; any non-zero raw passes through untouched
        # (a UE4 package's ue5==0 is a valid effective value, no normalization).
        if raw_ue4 == 0 and raw_ue5 == 0 and raw_licensee == 0:
            assert (summary.file_version_ue4, summary.file_version_ue5) == (522, 1018), sample
        else:
            assert (summary.file_version_ue4, summary.file_version_ue5) == (raw_ue4, raw_ue5), sample
        if sample in ("BP_UnversionedTest.uasset", "DA_UnversionedTest.uasset"):
            # The manifest's only all-zero samples must take the normalize branch.
            assert (raw_ue4, raw_ue5, raw_licensee) == (0, 0, 0), sample
            assert (summary.file_version_ue4, summary.file_version_ue5) == (522, 1018), sample
        ctx = build_version_context(summary)
        assert (ctx.file_version_ue4, ctx.file_version_ue5) == (
            summary.file_version_ue4,
            summary.file_version_ue5,
        ), sample
        # Mapping == first-match list scan (A5-8), self-implemented <=10-line scan.
        for guid in (FRAMEWORK_GUID, CORE_GUID, FORTNITE_GUID, RELEASE_GUID):
            expected = -1
            for cv in summary.custom_versions:
                if cv.guid == guid:
                    expected = cv.version
                    break
            assert ctx.custom_versions.get(guid, -1) == expected, f"{sample}: {guid}"

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


def test_logging_boundaries_and_cli_file_logs(capfd, caplog, tmp_path, monkeypatch):
    # capfd alone cannot catch the leak under pytest: the logging plugin
    # installs a root handler, which suppresses logging.lastResort. Assert
    # on captured WARNING records too. The API stays silent and leaves logger
    # state alone; the CLI owns its short-lived file handler.
    import logging
    import sys

    from uasset_read import cli
    from uasset_read.package import parse_package_document

    root = logging.getLogger()
    handlers_before = tuple(root.handlers)
    root_level_before = root.level
    files_before = set(tmp_path.iterdir())
    with caplog.at_level(logging.WARNING):
        parse_package_document(SAMPLES / "NM_BPSystemEvent.uasset", depth="object")
    captured = capfd.readouterr()
    assert captured.err == "", f"v2 parse leaked stderr: {captured.err[:200]}"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [], f"v2 parse emitted warning logs: {[r.getMessage()[:120] for r in warnings]}"
    assert tuple(root.handlers) == handlers_before
    assert set(tmp_path.iterdir()) == files_before

    monkeypatch.setattr(cli, "__file__", str(tmp_path / "repo" / "src" / "uasset_read" / "cli.py"))
    log_dir = tmp_path / "repo" / "temp"
    package_logger = logging.getLogger("uasset_read")
    package_handlers = tuple(package_logger.handlers)
    package_level = package_logger.level

    for argv, expected_code in (
        (["uasset_read", "--help"], cli.EXIT_SUCCESS),
        (["uasset_read", "--not-a-cli-option"], cli.EXIT_ARGUMENT_ERROR),
    ):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exit_info:
            cli.main()
        assert exit_info.value.code == expected_code
        assert not log_dir.exists()
        capfd.readouterr()

    monkeypatch.setattr(sys, "argv", ["uasset_read", "missing.uasset"])
    with pytest.raises(SystemExit) as missing_exit:
        cli.main()
    assert missing_exit.value.code == cli.EXIT_FILE_NOT_FOUND
    assert tuple(root.handlers) == handlers_before and root.level == root_level_before
    assert tuple(package_logger.handlers) == package_handlers and package_logger.level == package_level
    capfd.readouterr()

    def fail_to_open(*args, **kwargs):
        raise OSError("disk unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(logging, "FileHandler", fail_to_open, raising=False)
        with pytest.raises(SystemExit) as setup_failure_exit:
            cli.main()
        setup_failure = capfd.readouterr()
        assert setup_failure_exit.value.code == cli.EXIT_FILE_NOT_FOUND
        assert "Warning: could not write parser log file" in setup_failure.err
        assert "Error: File not found: missing.uasset" in setup_failure.err

    output_path = tmp_path / "result.json"
    sample = SAMPLES / "NM_BPSystemEvent.uasset"
    root.handlers.clear()
    try:
        monkeypatch.setattr(cli, "__file__", str(tmp_path / "repo" / "src" / "uasset_read" / "cli.py"))
        monkeypatch.setattr(sys, "argv", ["uasset_read", str(sample), "--verbose", "-o", str(output_path)])
        with pytest.raises(SystemExit) as parse_exit:
            cli.main()
        verbose = capfd.readouterr()
    finally:
        root.handlers.clear()
        root.handlers.extend(handlers_before)
        root.setLevel(root_level_before)

    assert parse_exit.value.code == cli.EXIT_SUCCESS
    document = json.loads(output_path.read_text(encoding="utf-8"))
    assert document["format_version"] == "4.0"
    assert "DEBUG: Parsing package: NM_BPSystemEvent.uasset" in verbose.err
    files = sorted(log_dir.glob("uasset_read-*.log"))
    assert len(files) == 2  # one run id per file-producing cli.main() call; the OSError run writes none
    for path in files:
        assert re.fullmatch(r"uasset_read-[0-9a-f]{12}\.log", path.name)
    missing_logs = [p for p in files if "File not found: missing.uasset" in p.read_text(encoding="utf-8")]
    assert len(missing_logs) == 1


def _assert_issue_665_struct_fallbacks_decode():
    """#665: Vector/Guid/Transform/LinearColor/Box fallbacks decode from real samples.

    Classification evidence recorded in the #665 implementation commit
    history (7bdeb3ed): Vector/Guid/LinearColor are native inline
    array elements sized from the legacy inner tag; Box is the native 49-byte
    double layout (Box.h uint8 IsValid); Transform payloads are legal tagged
    streams, so a clean decode must emit no TRANSFORM_SIZE_INVALID and must not
    downgrade parse status. Unversioned exports without schema stay honest
    schema_required partials.
    """
    from uasset_read.package import parse_package_document

    # Vector (16x size-0) + Box(49) + Transform(235): chair's KConvexElem was
    # wholly opaque before; now every reflected member decodes.
    chair = parse_package_document(str(SAMPLES / "StarterContent_SM_Chair.uasset"), depth="decode")
    assert not [d for d in chair.diagnostics if d.code == "TRANSFORM_SIZE_INVALID"]
    agg = chair.objects[0].properties.get("AggGeom")
    convex = agg["fields"]["ConvexElems"][0]["fields"]
    assert set(convex) >= {"VertexData", "IndexData", "ElemBox", "Transform"}
    assert len(convex["VertexData"]) == 16
    assert convex["VertexData"][0]["fields"] == {
        "X": 40.21192169189453,
        "Y": -40.45193099975586,
        "Z": 8.843807220458984,
    }
    assert convex["ElemBox"]["fields"] == {
        "Min": {"X": -41.94398880004883, "Y": -40.45193099975586, "Z": -0.5},
        "Max": {"X": 40.21192169189453, "Y": 40.45073699951172, "Z": 115.34375},
        "bIsValid": True,
    }
    transform = convex["Transform"]["fields"]
    assert transform["Rotation"]["fields"] == {"X": 0.0, "Y": 0.0, "Z": 0.0, "W": 1.0}
    assert transform["Scale3D"]["fields"] == {"X": 1.0, "Y": 1.0, "Z": 1.0}

    # LinearColor (4x size-0 RawTeamColors): opaque before, real team colors now.
    control = parse_package_document(str(SAMPLES / "B_ControlPointScoring.uasset"), depth="decode")
    colors = control.objects[0].properties.get("RawTeamColors")["value"]
    assert [c["fields"] for c in colors] == [
        {"R": 0.0, "G": 0.4999780058860779, "B": 1.0, "A": 1.0},
        {"R": 1.0, "G": 0.0, "B": 0.0, "A": 1.0},
        {"R": 0.1784989982843399, "G": 1.0, "B": 0.0, "A": 1.0},
        {"R": 1.0, "G": 0.0, "B": 0.9106259942054749, "A": 1.0},
    ]

    # Guid (3x size-0 + Lyra's ChildPossessables): opaque/empty-success before.
    wood = parse_package_document(str(SAMPLES / "StarterContent_M_Wood_Walnut.uasset"), depth="decode")
    guids = wood.objects[0].properties.get("ReferencedTextureGuids")["value"]
    assert [g["fields"] for g in guids] == [
        {"A": 2344919053, "B": 1291395776, "C": 844699801, "D": 500111011},
        {"A": 201753445, "B": 1183385308, "C": 1642468248, "D": 3257498810},
        {"A": 2742200478, "B": 1252459311, "C": 413933452, "D": 3362516772},
    ]

    # Transform (162/235): tagged payload decodes; the two CameraCut sections
    # were parse=partial solely because of the spurious recovered_corruption
    # diagnostic — they must now be complete with no TRANSFORM_SIZE_INVALID.
    lyra = parse_package_document(str(SAMPLES / "Lyra_SEQ_LobbyScreen_LevelSequence.uasset"), depth="decode")
    assert not [d for d in lyra.diagnostics if d.code == "TRANSFORM_SIZE_INVALID"]
    for oid in ("export:46", "export:47"):
        obj = next(o for o in lyra.objects if o.id == oid)
        assert obj.status.parse == "complete", (oid, obj.status)
        cut = obj.properties.get("InitialCameraCutTransform")
        assert set(cut["fields"]) == {"Rotation", "Translation"}
    def _find_nested(value, key):
        if isinstance(value, dict):
            if key in value:
                return value[key]
            for child in value.values():
                found = _find_nested(child, key)
                if found is not None:
                    return found
        elif isinstance(value, (list, tuple)):
            for child in value:
                found = _find_nested(child, key)
                if found is not None:
                    return found
        elif hasattr(value, "__dataclass_fields__"):
            for field_name in value.__dataclass_fields__:
                found = _find_nested(getattr(value, field_name, None), key)
                if found is not None:
                    return found
        return None

    possessable = _find_nested(lyra.objects[9].properties, "ChildPossessables")
    # Lyra carries two one-element ChildPossessables arrays; the first pins the decode.
    assert [g["fields"] for g in possessable] == [
        {"A": 1864024343, "B": 1180112327, "C": 329830544, "D": 734810239},
    ]

    # Unversioned boundary: without mappings every export stays schema_required
    # partial; with the fixture usmap the class export decodes via its own
    # schema while exports whose schemas the usmap lacks stay honest partials.
    unversioned = parse_package_document(str(SAMPLES / "BP_UnversionedTest.uasset"), depth="decode")
    assert all(o.status.parse == "partial" for o in unversioned.objects)
    unmapped_failed = [d for d in unversioned.diagnostics if d.code == "PROPERTY_VALUE_READ_FAILED"]
    assert len(unmapped_failed) == 5 and all(d.reason == "schema_required" for d in unmapped_failed)
    mapped = parse_package_document(
        str(SAMPLES / "BP_UnversionedTest.uasset"),
        depth="decode",
        mappings_path=str(SAMPLES / "UnversionedTest.usmap"),
    )
    by_id = {o.id: o for o in mapped.objects}
    assert by_id["export:0"].status.parse == "complete" and by_id["export:0"].properties
    assert by_id["export:1"].status.parse == "complete"
    mapped_failed = [d for d in mapped.diagnostics if d.code == "PROPERTY_VALUE_READ_FAILED"]
    assert len(mapped_failed) == 3 and all(d.reason == "schema_required" for d in mapped_failed)
    assert all(by_id[i].status.parse == "partial" for i in ("export:2", "export:3", "export:4"))


def test_parser_fallbacks_are_structured_and_silent(caplog, monkeypatch):
    _assert_data_table_row_values_decode_tagged_scalars()
    _assert_data_table_projection_stays_partial_when_any_cell_is_opaque()
    _assert_issue_665_struct_fallbacks_decode()

    import logging
    import struct
    from types import SimpleNamespace

    from uasset_read.archive import ByteArchive
    from uasset_read.models.fallback import FallbackReason, PropertyFallback
    from uasset_read.models.properties import PropertyTag
    from uasset_read.package import _parse_cached, parse_package_document
    from uasset_read.parsers.property_parser import parse_property_value
    from uasset_read.parsers.property_types import parse_struct_property, read_validated_count_tolerant
    from uasset_read.serializers.blueprint_graph import _validate_graph_export_offset
    from uasset_read.serializers.package_summary import _read_payload_toc_offset
    import uasset_read.parsers.properties.tagged as tagged

    archive = ByteArchive(struct.pack("<i", -1), tolerant=True)
    assert read_validated_count_tolerant(archive, 8, "Array") == 0
    (diagnostic,) = archive.get_structured_diagnostics()
    assert diagnostic.code == "INVALID_COLLECTION_COUNT"
    assert diagnostic.offset == 0 and "raw_value=-1" in diagnostic.message
    archive = ByteArchive(struct.pack("<i", 9), tolerant=True)
    assert read_validated_count_tolerant(archive, 8, "Array") == 0
    (diagnostic,) = archive.get_structured_diagnostics()
    assert diagnostic.code == "INVALID_COLLECTION_COUNT" and "raw_value=9" in diagnostic.message

    archive = ByteArchive(b"\0" * 4, tolerant=True)
    value = parse_struct_property(
        PropertyTag(name="Transform", type="StructProperty", size=4, struct_type="Transform"),
        archive,
        [],
        [],
        file_version_ue5=0,
    )
    (diagnostic,) = archive.get_structured_diagnostics()
    assert diagnostic.code == "TRANSFORM_SIZE_INVALID"
    assert value.struct_type == "Transform"

    archive = ByteArchive(b"data", tolerant=True)
    value = parse_struct_property(
        PropertyTag(name="Struct", type="StructProperty", size=-1, struct_type="Unknown"),
        archive,
        [],
        [],
        file_version_ue5=0,
    )
    (diagnostic,) = archive.get_structured_diagnostics()
    assert diagnostic.code == "STRUCT_PROPERTY_NEGATIVE_SIZE"
    assert value.parse_status == "opaque" and archive.tell() == 4

    archive = ByteArchive(struct.pack("<q", -1), tolerant=True)
    assert _read_payload_toc_offset(archive) == 0
    (diagnostic,) = archive.get_structured_diagnostics()
    assert diagnostic.code == "PAYLOAD_TOC_OFFSET_INVALID" and "raw_value=-1" in diagnostic.message

    archive = ByteArchive(b"data", tolerant=True)
    tag = PropertyTag(name="Native", type="UnknownNative", size=4, serialize_type="BinaryOrNative")
    value = parse_property_value(tag, archive, [], [], tolerant=True)
    (diagnostic,) = archive.get_structured_diagnostics()
    assert diagnostic.code == "BINARY_OR_NATIVE_PROPERTY_OPAQUE"
    assert value["raw_data"] == b"data"

    with caplog.at_level(logging.WARNING):
        assert not _validate_graph_export_offset(
            SimpleNamespace(object_name="Graph", serial_offset=-1, serial_size=8), 32
        )
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]

    monkeypatch.setattr(
        tagged,
        "parse_property_value",
        lambda tag, *args, **kwargs: PropertyFallback.from_tag(tag, FallbackReason.PARSE_ERROR),
    )
    _parse_cached.cache_clear()
    try:
        document = parse_package_document(
            SAMPLES / "FirstPerson_DT_WeaponList.uasset", depth="object", object_ids=["export:1"]
        )
    finally:
        _parse_cached.cache_clear()
    obj = next(obj for obj in document.objects if obj.id == "export:1")
    fallback_diags = [
        d for d in document.diagnostics if d.code == "PROPERTY_VALUE_READ_FAILED" and d.object_id == obj.id
    ]
    assert fallback_diags and obj.status.parse == "partial"
    assert any(
        entry.tag_region is not None and entry.tag_region.start == diagnostic.offset
        for entry in obj.properties.entries
        for diagnostic in fallback_diags
    )


def _check_file_source_and_composite_source_reuse_cached_sizes(tmp_path, monkeypatch):
    from pathlib import Path

    import pytest

    from uasset_read.exceptions import ParseError
    from uasset_read.sources import CompositeSource, FileSource

    path = tmp_path / "main.uasset"
    path.write_bytes(b"abcd")
    source = FileSource(path)
    original_stat = Path.stat

    def reject_restat(self, *args, **kwargs):
        if self == path:
            raise AssertionError("FileSource queried the file size again")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", reject_restat)
    assert source.size() == 4
    assert source.read_at(0, 2) == b"ab"
    assert source.map_range(1, 2) == [(path.name, 1, 2)]

    class CountingSource:
        calls = 0

        def size(self):
            self.calls += 1
            return 4

    counted = CountingSource()
    composite = CompositeSource([("counted", counted)])
    assert counted.calls == 1
    assert composite.segments() == (("counted", 0, 4),)
    assert counted.calls == 1

    path.write_bytes(b"ab")
    with pytest.raises(ParseError, match="short read"):
        source.read_at(0, 4)


def _check_farchive_uses_one_mib_mmap_threshold_and_keeps_buffered_fallback(tmp_path, monkeypatch):
    import pytest

    import uasset_read.archive as archive_module
    from uasset_read.archive import FArchive
    from uasset_read.constants import MMAP_THRESHOLD
    from uasset_read.exceptions import ParseError

    assert MMAP_THRESHOLD == 1024 * 1024
    path = tmp_path / "small.uasset"
    path.write_bytes(b"data")
    monkeypatch.setattr(archive_module, "MMAP_THRESHOLD", 1)

    def fail_mmap(*args, **kwargs):
        raise OSError("mmap unavailable")

    monkeypatch.setattr(archive_module.mmap, "mmap", fail_mmap)
    with FArchive(str(path)) as archive:
        assert not archive._use_mmap
        assert archive.read(4) == b"data"
        with pytest.raises(ParseError):
            archive.read(1)


def _check_archive_internal_diagnostic_marks_scan_only_new_entries(monkeypatch):
    import pytest

    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_parser import _stream_is_poisoned

    archive = ByteArchive(b"")
    archive._record_structured_diagnostic(code="old", stage="test", offset=0)
    mark = archive._diagnostic_mark()
    archive._record_structured_diagnostic(code="fstring_out_of_range", stage="test", offset=0)
    assert [item.code for item in archive._diagnostics_since(mark)] == ["fstring_out_of_range"]
    history = archive.get_structured_diagnostics()
    returned = archive.get_structured_diagnostics()
    returned.clear()
    assert archive._diagnostic_mark() == 2

    class IndexedSuffix:
        def __len__(self):
            return len(history)

        def __iter__(self):
            raise AssertionError("diagnostic scan traversed the historical prefix")

        def __getitem__(self, index):
            if not isinstance(index, int) or index < mark:
                raise AssertionError(f"diagnostic scan reached historical index {index}")
            return history[index]

    archive._structured_diagnostics = IndexedSuffix()

    def reject_snapshot():
        pytest.fail("hot-path check copied the complete diagnostics list")

    monkeypatch.setattr(archive, "get_structured_diagnostics", reject_snapshot)
    assert _stream_is_poisoned(archive, mark)


def _check_package_archive_reuses_known_segment_positions(tmp_path, monkeypatch):
    import pytest

    from uasset_read.archive import FArchive
    from uasset_read.exceptions import ExportBoundsExceeded, ParseError
    from uasset_read.package import PackageArchive

    main_path = tmp_path / "pkg.uasset"
    uexp_path = tmp_path / "pkg.uexp"
    main_path.write_bytes(b"abcd")
    uexp_path.write_bytes(b"EFGH")
    archive = PackageArchive(FArchive(str(main_path)), FArchive(str(uexp_path)))
    main_seeks = []
    uexp_seeks = []
    main_seek = archive._main_archive.seek
    uexp_seek = archive._uexp_archive.seek

    def counted_main_seek(position):
        main_seeks.append(position)
        return main_seek(position)

    def counted_uexp_seek(position):
        uexp_seeks.append(position)
        return uexp_seek(position)

    monkeypatch.setattr(archive._main_archive, "seek", counted_main_seek)
    monkeypatch.setattr(archive._uexp_archive, "seek", counted_uexp_seek)
    try:
        assert archive.read(2) == b"ab"
        assert archive.read(2) == b"cd"
        assert archive.read(4) == b"EFGH"
        assert main_seeks == [] and uexp_seeks == []

        archive.seek(1)
        assert archive.read(1) == b"b"
        assert main_seeks == [1]

        archive.seek(2)
        original_read = archive._main_archive.read

        def consume_then_fail(size):
            original_read(1)
            raise ParseError("injected segment read failure")

        monkeypatch.setattr(archive._main_archive, "read", consume_then_fail)
        with pytest.raises(ParseError, match="injected segment read failure"):
            archive.read(1)
        monkeypatch.setattr(archive._main_archive, "read", original_read)
        assert archive.read(1) == b"c"
        assert main_seeks == [1, 2]

        archive.seek(3)
        assert archive.read(3) == b"dEF"
        assert uexp_seeks == [0]
        archive.set_read_range((0, archive.total_size()))
        archive.seek(7)
        with pytest.raises(ExportBoundsExceeded):
            archive.read(2)
        assert main_seeks == [1, 2]
    finally:
        archive.close()


def _check_float_array_bulk_decode_matches_scalar_bits_with_one_payload_read():
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.models.properties import PropertyTag
    from uasset_read.parsers.property_types import parse_array_property, parse_float_property

    class CountingArchive(ByteArchive):
        def __init__(self, data):
            super().__init__(data)
            self.read_sizes = []

        def read(self, size):
            self.read_sizes.append(size)
            return super().read(size)

    values = (1.25, -0.0, float("nan"), -17.5)
    payload = b"".join(struct.pack("<f", value) for value in values)
    raw = struct.pack("<i", len(values)) + payload
    tag = PropertyTag(name="Samples", type="ArrayProperty", size=len(raw))
    tag.inner_type = "FloatProperty"
    archive = CountingArchive(raw)
    actual = parse_array_property(tag, archive, [], [])

    scalar_archive = ByteArchive(payload)
    scalar_tag = PropertyTag(name="Sample", type="FloatProperty", size=4)
    expected = [parse_float_property(scalar_tag, scalar_archive) for _ in values]
    assert [struct.pack("<f", value) for value in actual] == [struct.pack("<f", value) for value in expected]
    assert archive.read_sizes == [4, len(payload)]
    assert archive.tell() == len(raw)


def _check_float_array_bulk_decode_falls_back_at_export_boundary():
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.models.fallback import PropertyFallback
    from uasset_read.models.properties import PropertyTag
    from uasset_read.parsers.property_types import parse_array_property
    from uasset_read.versioning import VersionContext

    class CountingArchive(ByteArchive):
        def __init__(self, data):
            super().__init__(data)
            self.read_sizes = []
            # Synthetic bare-archive caller: mount a neutral context so value
            # dispatch (G1: version from VersionContext) stays structural.
            self.version_context = VersionContext(file_version_ue4=0, file_version_ue5=0)

        def read(self, size):
            self.read_sizes.append(size)
            return super().read(size)

    raw = struct.pack("<i3f", 3, 1.0, 2.0, 3.0)
    tag = PropertyTag(name="Samples", type="ArrayProperty", size=len(raw))
    tag.inner_type = "FloatProperty"
    archive = CountingArchive(raw)
    archive.set_read_range((0, len(raw) - 1))
    values = parse_array_property(tag, archive, [], [])
    assert values[:2] == [1.0, 2.0]
    assert isinstance(values[2], PropertyFallback)
    assert archive.tell() == len(raw) - 4
    assert archive.read_sizes == [4, 4, 4, 4]


def _check_float_array_bulk_decode_recovers_after_physical_short_read():
    import io
    import struct

    from uasset_read.archive import ByteArchive, FArchive
    from uasset_read.models.fallback import PropertyFallback
    from uasset_read.models.properties import PropertyTag
    from uasset_read.package import PackageArchive
    from uasset_read.parsers.property_types import parse_array_property
    from uasset_read.versioning import VersionContext

    raw = struct.pack("<i2f", 3, 1.0, 2.0)
    reported_size = 16

    def tag():
        result = PropertyTag(name="Samples", type="ArrayProperty", size=reported_size)
        result.inner_type = "FloatProperty"
        return result

    def assert_recovered(archive, expected_position):
        values = parse_array_property(tag(), archive, [], [])
        assert values[:2] == [1.0, 2.0]
        assert len(values) == 3 and isinstance(values[2], PropertyFallback)
        assert archive.tell() == expected_position

    class ShortByteArchive(ByteArchive):
        def __init__(self):
            super().__init__(raw)
            self._file_size = reported_size
            self.read_sizes = []
            # Synthetic bare-archive caller: neutral mounted context (G1).
            self.version_context = VersionContext(file_version_ue4=0, file_version_ue5=0)

        def read(self, size):
            self.read_sizes.append(size)
            return super().read(size)

    byte_archive = ShortByteArchive()
    assert_recovered(byte_archive, reported_size)
    assert byte_archive.read_sizes == [4, 12, 4, 4, 4]

    file_archive = FArchive.__new__(FArchive)
    file_archive._init_archive_attrs("<short-read>")
    file_archive._file = io.BytesIO(raw)
    file_archive._file_size = reported_size
    # Synthetic bare-archive caller: neutral mounted context (G1).
    file_archive.version_context = VersionContext(file_version_ue4=0, file_version_ue5=0)
    file_sizes = []
    original_file_read = file_archive.read

    def counted_file_read(size):
        file_sizes.append(size)
        return original_file_read(size)

    file_archive.read = counted_file_read
    assert_recovered(file_archive, len(raw))
    assert file_sizes == [4, 12, 4, 4, 4]
    file_archive.close()

    main_archive = FArchive.__new__(FArchive)
    main_archive._init_archive_attrs("<short-package>")
    main_archive._file = io.BytesIO(raw)
    main_archive._file_size = reported_size
    package = PackageArchive(main_archive)
    # Synthetic bare-archive caller: neutral mounted context (G1).
    package.version_context = VersionContext(file_version_ue4=0, file_version_ue5=0)
    package_sizes = []
    original_package_read = package.read

    def counted_package_read(size):
        package_sizes.append(size)
        return original_package_read(size)

    package.read = counted_package_read
    try:
        assert_recovered(package, len(raw))
        assert package_sizes == [4, 12, 4, 4, 4]
    finally:
        package.close()


def test_v4_public_output_contract(capsys, monkeypatch, tmp_path):
    """Real samples exercise both v4 modes and every public producer route."""
    import sys

    import jsonschema

    from uasset_read.agent_tools import inspect_package
    from uasset_read.package import parse_package_document
    from uasset_read.projection import project_document
    from uasset_read.projections.bundle import write_projected_document

    schema = json.loads((ROOT / "tests" / "package_document_v4.schema.json").read_text(encoding="utf-8"))
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
        # B_ControlPointScoring pins decode-mode JSON safety: its VarType fallback
        # values used to reach the envelope as raw PropertyFallback dataclasses.
        "B_ControlPointScoring.uasset",
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

    # C2 (plan blueprint-semantics, folded for the collection budget): pin
    # control_flow / exec_chains / functions[].cfg — previously zero test
    # references. Counts are measured doc totals (every object carrying the
    # function list), style of the 610-links pin.
    def _cfg_totals(projection):
        blocks = edges = unresolved = 0
        unresolved_kinds = set()
        for obj in projection["objects"]:
            sem = obj.get("semantic") or {}
            for fn in sem.get("functions") or []:
                cfg = fn.get("cfg") or {}
                assert {"blocks", "edges", "entry"} <= set(cfg), sorted(cfg)
                blocks += len(cfg["blocks"])
                edges += len(cfg["edges"])
                for edge in cfg["edges"]:
                    assert {"kind", "targets_known"} <= set(edge), sorted(edge)
                    if not edge["targets_known"]:
                        unresolved += 1
                        unresolved_kinds.add(edge["kind"])
        return blocks, edges, unresolved, unresolved_kinds

    ue58_normal = projected["MyProject_UE58_TestBlueprint.uasset"]["normal"]
    ue58_sem = next(o["semantic"] for o in ue58_normal["objects"] if o["id"] == "export:0")
    assert "control_flow" in ue58_sem and "exec_chains" in ue58_sem
    assert ue58_sem["exec_chains"]["metadata"]["kind"] == "direct_exec_edge_summary"
    nf_cfg = next(fn["cfg"] for fn in ue58_sem["functions"] if fn["function_name"] == "NewFunction")
    # Measured 2026-10-06: NewFunction = 4 blocks / 3 edges (the plan's 2/0
    # seed names NewEventDispatcher__DelegateSignature instead) — the plan
    # orders measure-first over its own seed.
    assert (len(nf_cfg["blocks"]), len(nf_cfg["edges"])) == (4, 3), nf_cfg["entry"]

    combat_blocks, combat_edges, combat_unresolved, combat_kinds = _cfg_totals(
        projected["BP_CombatCharacter.uasset"]["normal"]
    )
    assert (combat_blocks, combat_edges) == (324, 162), (combat_blocks, combat_edges)
    assert combat_unresolved == 2 and combat_kinds == {"computed_jump"}, (combat_unresolved, combat_kinds)

    bcps_blocks, bcps_edges, bcps_unresolved, bcps_kinds = _cfg_totals(
        projected["B_ControlPointScoring.uasset"]["normal"]
    )
    assert (bcps_blocks, bcps_edges) == (160, 116), (bcps_blocks, bcps_edges)
    assert bcps_unresolved == 2 and bcps_kinds == {"computed_jump"}, (bcps_unresolved, bcps_kinds)

    stack_blocks, stack_edges, stack_unresolved, stack_kinds = _cfg_totals(stack["normal"])
    assert (stack_blocks, stack_edges) == (18, 6), (stack_blocks, stack_edges)
    assert stack_unresolved == 2 and stack_kinds == {"computed_jump"}, (stack_unresolved, stack_kinds)

    # C4 (folded too): entrypoints were zero-referenced. BCPS Blueprint owner
    # carries 23 (16 function + 7 event), 0 unresolved; events correlate by
    # source_node at 0.9, functions by object_id at 1.0; StackOBot's asset
    # owner carries the construction attachment (measured 2026-10-06).
    bcps_normal = projected["B_ControlPointScoring.uasset"]["normal"]
    bcps_owner_ep = next(o["semantic"]["entrypoints"] for o in bcps_normal["objects"] if o["id"] == "export:1")
    assert len(bcps_owner_ep) == 23, len(bcps_owner_ep)
    assert not [e for e in bcps_owner_ep if e["unresolved"]]
    bcps_events = [e for e in bcps_owner_ep if e["kind"] == "event"]
    assert len(bcps_events) == 7
    assert all((e["match_method"], e["confidence"]) == ("source_node", 0.9) for e in bcps_events)
    bcps_functions = [e for e in bcps_owner_ep if e["kind"] == "function"]
    assert len(bcps_functions) == 16
    assert all((e["match_method"], e["confidence"]) == ("object_id", 1.0) for e in bcps_functions)

    stack_owner_ep = next(o["semantic"]["entrypoints"] for o in stack["normal"]["objects"] if o["id"] == "export:0")
    construction = [e for e in stack_owner_ep if e["kind"] == "construction"]
    assert construction == [
        {
            "kind": "construction",
            "name": "UserConstructionScript",
            "object_id": "export:0",
            "source_node_id": None,
            "match_method": "object_id",
            "confidence": 0.9,
            "unresolved": False,
        }
    ], construction

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


def test_critical_boundary_guards(monkeypatch, caplog, tmp_path):
    """Keep the mandatory trust-boundary checks in one bounded aggregate item."""
    import logging
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

    # C3 (plan blueprint-semantics): call-level resolution matrix — all five
    # (match_method, confidence) rows pinned synthetically, plus the call-level
    # ambiguous row that only the external_ref test covered before.
    from uasset_read.parsers.blueprint.correlation import _CallResolver

    ue58_owner = next(o for o in ue58_document.objects if o.id == "export:0")
    call_resolver = _CallResolver(ue58_document, ue58_owner, [], set(), set())
    # object_id row: a stack node resolves directly at full confidence.
    assert call_resolver.resolve_call("Whatever", 5)[2:] == ("object_id", 1.0, False)
    # function_identity 0.9: exactly one local function carries the name.
    call_resolver.function_ids_by_name["SoloTarget"] = ["export:7"]
    assert call_resolver.resolve_call("SoloTarget", None) == (
        "export:7",
        "SoloTarget",
        "function_identity",
        0.9,
        False,
    )
    # function_identity 0.7: the name only matches an import.
    call_resolver.import_ids_by_name["ImportedTarget"] = ["import:3"]
    assert call_resolver.resolve_call("ImportedTarget", None) == (
        "import:3",
        "ImportedTarget",
        "function_identity",
        0.7,
        False,
    )
    # function_identity 0.5: two+ local candidates stay ambiguous, diagnosed.
    call_resolver.function_ids_by_name["SharedTarget"] = ["export:2", "export:5"]
    assert call_resolver.resolve_call("SharedTarget", None) == (
        "export:2",
        "SharedTarget",
        "function_identity",
        0.5,
        False,
    )
    assert [d.code for d in call_resolver.diagnostics] == ["BLUEPRINT_CALL_NAME_AMBIGUOUS"]
    # unresolved 0.0: no local function or import carries the name.
    assert call_resolver.resolve_call("AbsentTarget", None) == (
        "unresolved:AbsentTarget",
        "AbsentTarget",
        "unresolved",
        0.0,
        True,
    )

    # C5 (plan blueprint-semantics): three zero-test diagnostics each get one
    # minimal trigger. (1) BLUEPRINT_NODE_CONTROL_FLAGS_UNSUPPORTED — a
    # >=1011 node whose SerializationControlExtensions byte carries bits
    # beyond 0x03 stops the property loop with the diagnostic.
    from uasset_read.serializers.graph_node import _read_node_script_serial
    from uasset_read.serializers.object_resources import ObjectExport, PackageIndex

    ctrl_archive = ByteArchive(bytes([0x04]) + b"\x00" * 31)
    ctrl_summary = SimpleNamespace(file_version_ue5=1011, package_flags=0)
    # Mirror the production mount point (G1): the >=1011 control-byte gate
    # reads require_version_context(archive), never the summary.
    from uasset_read.versioning import VersionContext

    ctrl_archive.version_context = VersionContext(file_version_ue4=0, file_version_ue5=1011)
    ctrl_export = ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="K2Node_CtrlFlags",
        object_flags=0,
        serial_size=32,
        serial_offset=0,
        script_serialization_start_offset=0,
        script_serialization_end_offset=16,
    )
    ctrl_result = _read_node_script_serial(ctrl_archive, ["None"], ctrl_summary, ctrl_export, [], [], "K2Node_CtrlFlags")
    ctrl_codes = [d.code for d in ctrl_archive.get_structured_diagnostics()]
    assert "BLUEPRINT_NODE_CONTROL_FLAGS_UNSUPPORTED" in ctrl_codes, ctrl_codes
    ctrl_diag = next(d for d in ctrl_archive.get_structured_diagnostics() if d.code == "BLUEPRINT_NODE_CONTROL_FLAGS_UNSUPPORTED")
    assert ctrl_diag.fallback == "skipped_node_properties"
    assert ctrl_result["raw_properties"] == {}, ctrl_result

    # (2)/(3) BLUEPRINT_EXTERNAL_PIN_LINK / BLUEPRINT_LINK_AMBIGUOUS — feed
    # _attach_blueprint_graph_extras synthetic graphs carrying unresolved and
    # ambiguous link counts; both aggregate diagnostics must land.
    import uasset_read.serializers.blueprint_graph as _blueprint_graph
    from uasset_read.models.object_model import ObjectRecord
    from uasset_read.parsers.legacy_reader import _attach_blueprint_graph_extras

    c5_export_map = [
        ObjectExport(
            class_index=PackageIndex(-1),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="BP_C5",
            object_flags=0,
            serial_size=0,
            serial_offset=0,
        ),
        ObjectExport(
            class_index=PackageIndex(-2),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(1),
            object_name="EventGraph",
            object_flags=0,
            serial_size=0,
            serial_offset=0,
        ),
    ]
    c5_objects = [
        ObjectRecord(id="export:0", table_index=0, name="BP_C5", class_name="Blueprint"),
        ObjectRecord(id="export:1", table_index=1, name="EventGraph", class_name="EdGraph"),
    ]
    c5_graphs = [
        {
            "id": "export:1",
            "nodes": [{"id": "export:1/export:9", "pins": []}],
            "links": [],
            "unresolved_links": 2,
            "ambiguous_links": 1,
        }
    ]
    monkeypatch.setattr(_blueprint_graph, "read_blueprint_graphs", lambda *a, **k: c5_graphs)
    c5_extras: dict = {}
    c5_diags: list = []
    try:
        _attach_blueprint_graph_extras(
            archive=ByteArchive(b""),
            summary=SimpleNamespace(package_flags=0),
            name_map=["None"],
            import_map=[],
            export_map=c5_export_map,
            objects=c5_objects,
            extras=c5_extras,
            diagnostics=c5_diags,
            object_ids=None,
        )
    finally:
        monkeypatch.undo()
    c5_codes = [d.code for d in c5_diags]
    assert "BLUEPRINT_EXTERNAL_PIN_LINK" in c5_codes, c5_codes
    assert "BLUEPRINT_LINK_AMBIGUOUS" in c5_codes, c5_codes
    assert "export:0" in c5_extras and c5_extras["export:0"]["graphs"][0]["id"] == "export:1"
    # The aggregate keys are consumed (popped), never leaked downstream.
    assert "unresolved_links" not in c5_extras["export:0"]["graphs"][0]

    # A4/A-4 (plan blueprint-semantics): a pins locate failure is a structured
    # diagnostic, never a silent empty array. Three synthetic triggers:
    # (a) pre-1010 node whose tag scan found no NAME_None tail,
    # (b) located count negative,
    # (c) located count beyond MAX_PINS_PER_NODE.
    from uasset_read.models.core import UEdGraphNode  # noqa: F401  (import anchor)
    from uasset_read.serializers.graph_node import _read_node_pins
    from uasset_read.serializers.object_resources import ObjectExport, PackageIndex

    def _synthetic_node_export() -> ObjectExport:
        return ObjectExport(
            class_index=PackageIndex(-1),
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="K2Node_Synthetic",
            object_flags=0,
            serial_size=64,
            serial_offset=0,
        )

    summary_stub = SimpleNamespace(file_version_ue5=1004)
    for locate_kwargs, label in (
        ({"property_stream_end": None}, "no_scan_tail"),
        ({"property_stream_end": 0}, "negative_count"),
        ({"property_stream_end": 4}, "oversized_count"),
    ):
        payload = (
            b"\x00" * 4
            + (-1).to_bytes(4, "little", signed=True)
            + b"\x00" * 56
            if label == "negative_count"
            else b"\x00" * 8 + (1001).to_bytes(4, "little", signed=True) + b"\x00" * 52
            if label == "oversized_count"
            else b"\x00" * 64
        )
        archive = ByteArchive(payload)
        pins = _read_node_pins(
            archive,
            ["None"],
            summary_stub,
            [],
            [],
            _synthetic_node_export(),
            label,
            **locate_kwargs,
        )
        assert pins == [], label
        codes = [d.code for d in archive.get_structured_diagnostics()]
        assert "BLUEPRINT_NODE_PINS_LOCATE_FAILED" in codes, (label, codes)

    # C1 unit (plan blueprint-semantics): a jump target that misses every
    # instruction boundary yields CFG_JUMP_TARGET_UNRESOLVED in the caller's
    # diagnostics list AND an edge with targets_known=False (never a guess).
    from uasset_read.models.diagnostics import Diagnostic
    from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction
    from uasset_read.parsers.blueprint.control_flow import build_cfg

    def _instr(stmt: int, opcode: str, jump_kind: str = "none", target: int | None = None):
        return BytecodeInstruction(
            statement_index=stmt,
            statement_ordinal=stmt,
            logical_end=stmt + 1,
            serialized_start=0,
            serialized_end=0,
            opcode=opcode,
            operands={},
            expression=None,
            reads=[],
            writes=[],
            call_target=None,
            jump_target_statement_index=target,
            jump_kind=jump_kind,  # type: ignore[arg-type]
            source_node_id=None,
        )

    cfg_diags: list[Diagnostic] = []
    cfg = build_cfg(
        [_instr(0, "EX_JumpIfNot", "conditional_false", 99), _instr(1, "EX_Return")],
        diagnostics=cfg_diags,
    )
    assert [d.code for d in cfg_diags] == ["CFG_JUMP_TARGET_UNRESOLVED"], cfg_diags
    unresolved = [e for e in cfg.edges if not e.targets_known]
    assert len(unresolved) == 1 and unresolved[0].kind == "false", cfg.edges

    # C1 wiring: monkeypatched build_cfg appends a marker only when the call
    # site forwards a diagnostics list; the marker must surface in the public
    # semantic.functions[].diagnostics projection (was unreachable before C1).
    import uasset_read.parsers.blueprint.control_flow as _control_flow

    _real_build_cfg = _control_flow.build_cfg

    def _marked_build_cfg(instructions, *, diagnostics=None):
        graph = _real_build_cfg(instructions, diagnostics=diagnostics)
        if diagnostics is not None:
            diagnostics.append(
                Diagnostic(code="CFG_WIRING_MARKER", message="marker", stage="semantic.functions.cfg")
            )
        return graph

    monkeypatch.setattr(_control_flow, "build_cfg", _marked_build_cfg)
    from uasset_read.package import _parse_cached as _ue58_cache

    _ue58_cache.cache_clear()  # a cached document would skip build_cfg entirely
    try:
        wiring_doc = parse_package_document(str(SAMPLES / "MyProject_UE58_TestBlueprint.uasset"), depth="decode")
        wiring_owner = next(o for o in wiring_doc.objects if o.id == "export:0")
        wiring_fn_diags = [d for fn in wiring_owner.semantic["functions"] for d in fn["diagnostics"]]
        assert any(d["code"] == "CFG_WIRING_MARKER" for d in wiring_fn_diags), (
            "build_cfg diagnostics must reach semantic.functions[].diagnostics",
            [d["code"] for d in wiring_fn_diags],
        )
    finally:
        _ue58_cache.cache_clear()  # never leak marker-bearing documents to later tests
    monkeypatch.undo()

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
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            document = parse_package_document(str(SAMPLES / "FirstPerson_DT_WeaponList.uasset"), depth="package")
    finally:
        _parse_cached.cache_clear()
    assert document.objects[0].id == "export:0"
    assert any(d.code == "EXPORT_TABLE_TRUNCATED" for d in document.diagnostics)
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]

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

    with pytest.MonkeyPatch.context() as mp:
        _check_file_source_and_composite_source_reuse_cached_sizes(tmp_path, mp)
    with pytest.MonkeyPatch.context() as mp:
        _check_farchive_uses_one_mib_mmap_threshold_and_keeps_buffered_fallback(tmp_path, mp)
    _check_float_array_bulk_decode_recovers_after_physical_short_read()
    with pytest.MonkeyPatch.context() as mp:
        _check_archive_internal_diagnostic_marks_scan_only_new_entries(mp)
    with pytest.MonkeyPatch.context() as mp:
        _check_package_archive_reuses_known_segment_positions(tmp_path, mp)
    _check_float_array_bulk_decode_matches_scalar_bits_with_one_payload_read()
    _check_float_array_bulk_decode_falls_back_at_export_boundary()

    # R5: canonical payload ids only; pagination envelope retired.
    import uasset_read.agent_tools as agent_tools

    assert agent_tools._parse_payload_id("payload:export:3") == ("export", 3)
    assert agent_tools._parse_payload_id("payload:(export:3)") is None
    assert not hasattr(agent_tools, "fit_list_response")
    shape = agent_tools._err("X", "agent.extract_payload", recoverable=True, message="nothing here")
    assert shape == {"error": "nothing here", "code": "X", "stage": "agent.extract_payload", "recoverable": True}


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

    Folded #664 (collection budget): depth=decode attaches the decoded editor
    graph to the owning NiagaraGraph, projects it as a represented graph
    record, and the high-frequency node kinds expose their tagged fields —
    while the domain tier stays partial and no payload stays skipped.
    """
    from uasset_read.parsers.asset_types.handlers_impl import NiagaraHandler

    doc = _asset_document("NM_BPSystemEvent.uasset")
    covered = [o for o in doc.objects if o.class_name in NiagaraHandler.classes]
    assert covered, "Niagara class set must match the fixture"
    for o in covered:
        assert o.semantic and o.semantic["kind"] == "niagara", o.id
        assert o.coverage, o.id
        assert o.status.semantic == "partial", (o.id, o.class_name, o.status.semantic)

    # #664: decode-depth structure (pins/links byte-verified by the
    # issue-521-b0-gate-decision pin walk: 99 pins, 76 links).
    from uasset_read.package import parse_package_document
    from uasset_read.projection import project_document

    decode_doc = parse_package_document(SAMPLES / "NM_BPSystemEvent.uasset", depth="decode")
    graph_obj = next(o for o in decode_doc.objects if o.class_name == "NiagaraGraph")
    graphs = (graph_obj.semantic or {}).get("graphs") or []
    assert len(graphs) == 1, "depth=decode must attach exactly one decoded graph"
    graph = graphs[0]
    assert (graph["node_count"], graph["pin_count"], graph["edge_count"]) == (28, 99, 76), graph["id"]
    assert graph["parse_errors"] == []
    node_types = {node["type"] for node in graph["nodes"]}
    assert {
        "NiagaraNodeFunctionCall",
        "NiagaraNodeParameterMapSet",
        "NiagaraNodeReroute",
        "NiagaraNodeSelect",
    } <= node_types, node_types
    coverage_features = {(c.feature, c.status) for c in graph_obj.coverage}
    assert ("niagara.graph", "present") in coverage_features, coverage_features
    assert ("niagara.domain", "partial") in coverage_features, coverage_features

    # Per-kind tagged fields are the decodable boundary for the four
    # high-frequency node kinds; all node payloads parse (no skips remain).
    props_by_class: dict[str, set[str]] = {}
    for o in decode_doc.objects:
        if o.class_name in NiagaraHandler.classes:
            props_by_class.setdefault(o.class_name, set()).update(e.name for e in o.properties.entries)
    assert {"SelectorPinType", "SelectorPinGuid"} <= props_by_class["NiagaraNodeSelect"]
    assert {"PinOutputToPinDefaultPersistentId"} <= props_by_class["NiagaraNodeParameterMapGet"]
    assert {"FunctionScript", "FunctionDisplayName"} <= props_by_class["NiagaraNodeFunctionCall"]
    assert {"ChangeId", "NodePosX", "NodePosY", "NodeGuid"} <= props_by_class["NiagaraNodeReroute"]
    assert {"ChangeId", "NodePosX", "NodePosY", "NodeGuid"} <= props_by_class["NiagaraNodeParameterMapSet"]
    assert not [d for d in decode_doc.diagnostics if d.code == "EXPORT_PAYLOAD_SKIPPED"]

    # Graph projections are no longer all unavailable (#664 acceptance).
    projection = project_document(decode_doc, mode="normal")
    graph_records = [r for r in projection["projections"] if r["kind"] == "graph"]
    assert len(graph_records) == 39, len(graph_records)
    represented = [r for r in graph_records if r["status"] == "represented"]
    assert [r["source_object_id"] for r in represented] == ["export:4"]
    assert (
        represented[0]["content"]["node_count"],
        represented[0]["content"]["pin_count"],
        represented[0]["content"]["edge_count"],
    ) == (28, 99, 76)


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


def test_blueprint_graph_decodes_and_definitions_stay_honest():
    """G2 regression (2026-09-02 ue-source audit): editor FText Base carries gated DevNotes.

    v2 decode contract: BP_CombatCharacter exposes all 4 graphs (370 nodes)
    on the owning export and emits no graph-failure diagnostics.

    Folded (#654, collection budget): a tracked-sample honesty aggregate over
    the eight manifest packages that carry NewVariables — none may claim
    ``unresolved is False`` while ``type_name`` is null — plus two
    trust-boundary pins for the shapes no tracked fixture carries (sample-first
    spec, "small ... assertion ... mandatory trust boundary" clause): a
    kind="struct" wrapper must unwrap to its pin fields, and a
    PropertyFallback must report unresolved.
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

    # A1 (plan blueprint-semantics, folded for the collection budget): pre-1010
    # nodes scan their property-tag stream instead of early-returning, so
    # NodePosX/NodePosY land on the node and the scan tail (property_stream_end)
    # becomes available for the A2 pins locate. BCPS (ue5=1004) currently reads
    # position {0,0} on all 145 nodes and ABP (ue5=1004) on all 3 — both must
    # become non-zero from the tag stream.
    from uasset_read.serializers.graph_node import _read_node_script_serial
    from uasset_read.serializers.object_resources import resolve_class_name

    # nodes with non-zero position: the others are exports whose tag stream
    # carries no NodePosX/NodePosY at all (6 K2Node_FunctionEntry in BCPS,
    # K2Node_Event_0 in ABP — verified tag-by-tag 2026-10-06) — honest (0,0).
    # Plan A1 acceptance ② is "not all zero", which the tag-driven majority proves.
    pre1010 = {"B_ControlPointScoring.uasset": (145, 139), "ABP_RifleAnimLayers.uasset": (3, 2)}
    for pre_name, (expected_nodes, expected_nonzero) in pre1010.items():
        pre_doc = parse_package_document(SAMPLES / pre_name, depth="decode")
        pre_graphs = [g for o in pre_doc.objects for g in (o.semantic or {}).get("graphs") or []]
        pre_nodes = [n for g in pre_graphs for n in g["nodes"]]
        assert len(pre_nodes) == expected_nodes, (pre_name, len(pre_nodes))
        nonzero_pos = sum(1 for n in pre_nodes if n["position"]["x"] or n["position"]["y"])
        assert nonzero_pos == expected_nonzero, (pre_name, f"{nonzero_pos}/{expected_nodes} nodes with non-zero position")
        assert not [d for d in pre_doc.diagnostics if d.code.startswith("BLUEPRINT_")], pre_name
        # A2: pins locate off the tag-scan tail (property_stream_end + 4)
        # instead of the missing script_serialization offsets — pre-1010 nodes
        # must carry their pins. Measured via plan A0 probe: BCPS 505 pins,
        # ABP 9 pins across all K2Node exports.
        pre_pins = sum(len(n["pins"]) for n in pre_nodes)
        assert pre_pins > 0, (pre_name, "pre-1010 nodes still read 0 pins")

    # Seam: the pre-1010 scan records the NAME_None tail on the serial dict.
    with _open_sample_archive(SAMPLES / "B_ControlPointScoring.uasset") as (
        archive,
        summary,
        name_map,
        import_map,
        export_map,
    ):
        # G1 (version-context contract): property version gates read the
        # mounted VersionContext; the legacy set_property_version_gates
        # scaffolding was removed with #621. _open_sample_archive mirrors
        # the production mount point above.
        k2_export = next(
            e
            for e in export_map
            if e.serial_size > 0
            and (resolve_class_name(e.class_index, import_map, export_map) or "").startswith("K2Node")
        )
        serial = _read_node_script_serial(
            archive, name_map, summary, k2_export, import_map, export_map, k2_export.object_name
        )
        assert serial["property_stream_end"] is not None, "pre-1010 tag scan must record its NAME_None tail"
        assert serial["node_pos_x"] != 0 or serial["node_pos_y"] != 0, serial

    # #654 folded here (collection budget): tracked-sample honesty aggregate
    # (83 definitions across the eight NewVariables packages; verified count
    # 2026-09-30) plus trust-boundary pins for shapes no fixture carries.
    from uasset_read.models.fallback import FallbackReason, PropertyFallback
    from uasset_read.models.object_model import ObjectRecord
    from uasset_read.models.properties import PropertyBag, PropertyEntry
    from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation

    samples = [
        "BP_CombatCharacter.uasset",
        "BP_CombatEnemy.uasset",
        "FirstPerson_BP_FirstPersonCharacter.uasset",
        "IntroToUnreal_BP_Light.uasset",
        "IntroToUnreal_BP_SaveData.uasset",
        "LevelDesign_ABP_Manny.uasset",
        "MyProject_UE58_TestBlueprint.uasset",
        "StackOBot_GI_StackOBot.uasset",
    ]
    total = 0
    for name in samples:
        document = parse_package_document(SAMPLES / name, depth="object")
        for owner in document.objects:
            for definition in BlueprintCorrelation()._extract_variable_definitions(owner):
                total += 1
                assert definition.type_name or definition.unresolved, (name, definition.name)
    assert total == 83

    bag = PropertyBag(
        entries=[
            PropertyEntry(
                name="NewVariables",
                type_name="ArrayProperty",
                value={
                    "value": [
                        {
                            "fields": {
                                "VarName": "Wrapped",
                                "VarType": {
                                    "kind": "struct",
                                    "struct_type": "EdGraphPinType",
                                    "fields": {"pin_category": "byte", "pin_subcategory": "None"},
                                },
                            }
                        },
                        {
                            "fields": {
                                "VarName": "Opaque",
                                "VarType": PropertyFallback(
                                    name="VarType",
                                    type="StructProperty",
                                    size=69,
                                    reason=FallbackReason.PARSE_ERROR,
                                ),
                            }
                        },
                    ]
                },
                array_index=None,
                tag_region=None,
                value_region=None,
            )
        ]
    )
    owner = ObjectRecord(id="export:0", table_index=0, name="BP_Issue654", properties=bag)
    definitions = {d.name: d for d in BlueprintCorrelation()._extract_variable_definitions(owner)}
    assert definitions["Wrapped"].type_name == "byte:None"
    assert definitions["Wrapped"].unresolved is False
    assert definitions["Opaque"].type_name is None
    assert definitions["Opaque"].unresolved is True


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
        assert d.offset is not None and d.offset >= 0, f"{d.object_id}: missing structured offset"
        assert d.reason is not None
        # Message and structured field must agree.
        assert f"leaves {d.size} undecoded bytes" in d.message


def test_byte_accounting_registers_reader_consumed_structural_bytes():
    """#653: reader-consumed structural bytes decode as structural, never unconsumed."""
    from uasset_read.package import parse_package_document
    from uasset_read.projection import project_document

    def _debug(sample: str):
        return project_document(parse_package_document(SAMPLES / sample, depth="decode"), mode="debug")

    def _scopes(projection):
        return {s["object_id"]: s for s in projection["debug"]["byte_accounting"]}

    # UE 5.4+ save: control byte (1B) + None terminator (8B) + GUID step (4B).
    proj54 = _debug("ThirtPerson_M_PrototypeGrid.uasset")
    scopes54 = _scopes(proj54)
    zero_prop = scopes54["export:112"]
    # Zero-property export: the whole 13-byte window is reader-consumed structure.
    assert zero_prop["window"]["size"] == 13
    assert [(leaf["size"], leaf["status"], leaf["feature"]) for leaf in zero_prop["leaves"]] == [
        (13, "decoded", "structural")
    ]
    # Export with properties: control byte and None+GUID tail are decoded as well.
    assert not [leaf for leaf in scopes54["export:76"]["leaves"] if leaf["reason"] == "unconsumed"]

    # Pre-5.4 save: None terminator (8B) + GUID step (4B) are structural; the
    # genuinely unread trailer stays unconsumed with its diagnostic's exact size.
    proj410 = _debug("uasset_rs_UE410_SimpleRefsSoftRef.uasset")
    scopes410 = _scopes(proj410)
    export0_leaves = scopes410["export:0"]["leaves"]
    assert sum(leaf["size"] for leaf in export0_leaves if leaf["feature"] == "structural") == 12
    assert sum(leaf["size"] for leaf in export0_leaves if leaf["reason"] == "unconsumed") == 68

    # Pin fixture trailing-diagnostic counts so the reconciliation loop below
    # cannot silently go vacuous when fixtures are swapped.
    assert [d["object_id"] for d in proj54["diagnostics"] if d["code"] == "EXPORT_TRAILING_BYTES_UNCONSUMED"] == []
    assert [d["object_id"] for d in proj410["diagnostics"] if d["code"] == "EXPORT_TRAILING_BYTES_UNCONSUMED"] == [
        "export:0",
        "export:2",
        "export:4",
    ]

    for projection in (proj54, proj410):
        scopes = _scopes(projection)
        details = {e["index"]: e for e in projection["debug"]["diagnostic_details"]}
        # Reconciliation (diagnostic -> bytes): each trailing diagnostic's size
        # equals its object's total unconsumed bytes. The converse (bytes ->
        # diagnostic) is asserted next; it holds on these two fixtures but is
        # not a repo-wide invariant (table tails and pre-stream preludes may
        # stay unconsumed without one).
        for index, diag in enumerate(projection["diagnostics"]):
            if diag["code"] != "EXPORT_TRAILING_BYTES_UNCONSUMED":
                continue
            unconsumed = sum(
                leaf["size"] for leaf in scopes[diag["object_id"]]["leaves"] if leaf["reason"] == "unconsumed"
            )
            assert unconsumed == details[index]["size"], f"{diag['object_id']}: {unconsumed} != diagnostic"
            window = scopes[diag["object_id"]]["window"]
            assert details[index]["offset"] is not None, f"{diag['object_id']}: missing structured offset"
            assert details[index]["offset"] + details[index]["size"] == window["start"] + window["size"], (
                f"{diag['object_id']}: offset+size must reach the export window end"
            )
        trailing_ids = {
            d["object_id"] for d in projection["diagnostics"] if d["code"] == "EXPORT_TRAILING_BYTES_UNCONSUMED"
        }
        for scope in projection["debug"]["byte_accounting"]:
            unconsumed = sum(leaf["size"] for leaf in scope["leaves"] if leaf["reason"] == "unconsumed")
            assert unconsumed == 0 or scope["object_id"] in trailing_ids, scope["object_id"]
        # Coverage: leaves tile each window exactly, no gaps or overlaps.
        for scope in projection["debug"]["byte_accounting"]:
            window = scope["window"]
            cursor = window["start"]
            for leaf in sorted(scope["leaves"], key=lambda item: item["start"]):
                assert leaf["size"] > 0 and leaf["start"] == cursor, scope["object_id"]
                cursor = leaf["end"]
            assert cursor == window["end"], scope["object_id"]

    # Folded #664 (collection budget): NiagaraNode* payloads are decoded, not
    # skipped — tagged properties become structural spans and each pin-tail
    # residue is owned byte-for-byte by one classified trailing diagnostic.
    proj = _debug("NM_BPSystemEvent.uasset")
    scopes = {s["object_id"]: s for s in proj["debug"]["byte_accounting"]}
    assert [d["object_id"] for d in proj["diagnostics"] if d["code"] == "EXPORT_PAYLOAD_SKIPPED"] == []
    details = {e["index"]: e for e in proj["debug"]["diagnostic_details"]}
    trailing = [
        (index, diag)
        for index, diag in enumerate(proj["diagnostics"])
        if diag["code"] == "EXPORT_TRAILING_BYTES_UNCONSUMED"
    ]
    # PackageMetaData (export:3) plus the 25 NiagaraNode* exports (export:5..29).
    assert [diag["object_id"] for _, diag in trailing] == ["export:3"] + [f"export:{i}" for i in range(5, 30)]
    for index, diag in trailing:
        if diag["object_id"] == "export:3":
            continue
        assert details[index]["reason"] == "known_unimplemented", diag["object_id"]
        window = scopes[diag["object_id"]]["window"]
        scope_leaves = scopes[diag["object_id"]]["leaves"]
        decoded = sum(leaf["size"] for leaf in scope_leaves if leaf["status"] == "decoded")
        assert decoded > 0, diag["object_id"]  # tagged properties decoded, not a full-window seek
        unconsumed = sum(leaf["size"] for leaf in scope_leaves if leaf["reason"] == "unconsumed")
        assert unconsumed == details[index]["size"], diag["object_id"]
        # Stable byte range: offset+size reaches the export window end (#664).
        assert details[index]["offset"] + details[index]["size"] == window["start"] + window["size"], diag["object_id"]
        assert unconsumed < window["size"], diag["object_id"]

    # #663: K2Node_CallFunction pin tails decode byte-exactly to serial_end —
    # every owning export on the sample keeps zero trailing diagnostics and
    # zero unconsumed leaves, while the class count (72 exports, all trailing
    # before the change) is pinned so the proof cannot go vacuous.
    cc = _debug("BP_CombatCharacter.uasset")
    callfunc_ids = {o["id"] for o in cc["objects"] if o.get("class") == "K2Node_CallFunction"}
    assert len(callfunc_ids) == 72, f"expected 72 K2Node_CallFunction exports, got {len(callfunc_ids)}"
    cc_trailing = {
        d["object_id"] for d in cc["diagnostics"] if d["code"] == "EXPORT_TRAILING_BYTES_UNCONSUMED"
    }
    assert not (callfunc_ids & cc_trailing), sorted(callfunc_ids & cc_trailing)
    cc_scopes = _scopes(cc)
    for oid in sorted(callfunc_ids):
        unconsumed = sum(leaf["size"] for leaf in cc_scopes[oid]["leaves"] if leaf["reason"] == "unconsumed")
        assert unconsumed == 0, f"{oid}: {unconsumed} bytes stay unconsumed after pin-tail decode"


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

    # The generator CLI is gone; only the aggregate helper may live in tools/.
    assert not hasattr(gen_quality_baseline, "main")
    assert not hasattr(gen_quality_baseline, "build_sample_entry")
    assert not hasattr(gen_quality_baseline, "SEED")

    docs = [(entry["name"], _asset_document(entry["name"])) for entry in MANIFEST_SAMPLES]
    return gen_quality_baseline.aggregate_trailing_report(docs)


def test_trailing_aggregate_report_and_gate():
    """Report gate on all 67 manifest samples, plus the aggregate's fail paths.

    Report half: counts AND bytes by reason and class must sit within the
    quality baseline. Fail half: a synthetic report over ceiling in bytes,
    with a new reason/class, or below baseline (loss regression) must fail.
    Folded from test_trailing_aggregate_report_within_baseline +
    test_trailing_aggregate_gate_blocks_growth to hold the 100-item budget
    after the 67th manifest sample.
    """
    actual = _aggregate_from_manifest()
    report_baseline = json.loads((SAMPLES / "quality_baseline.json").read_text(encoding="utf-8"))["aggregate"]
    _assert_trailing_aggregate(actual, report_baseline)
    assert actual["sample_count"] == 67
    # #663 decoded conclusion: the K2Node_CallFunction pin tail consumes
    # byte-exactly (370/370 corpus trailers), so the class leaves both the
    # live inventory and the regenerated baseline — totals above already pin
    # count AND bytes for the same change.
    assert "editor_only/K2Node_CallFunction" not in actual["by_reason_class"]
    assert "editor_only/K2Node_CallFunction" not in report_baseline["by_reason_class"]

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
        file_version_ue5=0,
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
        file_version_ue5=0,
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
            file_version_ue5=0,
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

    # Folded #655 (collection budget): an undecodable PinType payload is
    # opaque + diagnosed, never silent or fabricated. UE 4.11
    # StarterContent_Starter_Background_Cue carries 11 x 66-byte and 1 x
    # 71-byte EdGraphPinType tags in the pre-PinsStoreFName FString layout
    # (FString category names, so byte 20 falls inside a string on the
    # 71-byte one and reads as container_type 111); neither size is the
    # modern 69/101 layout, so the decoder refuses both: the guard consumes
    # the payload, reports an opaque struct with no fields, and emits one
    # structured diagnostic per payload carrying offset + size.
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

    # A3 (plan §4-A discriminant, folded here for the collection budget):
    # the in-graph sequential reader gates the trailing
    # bSerializeAsSinglePrecisionFloat on FUE5ReleaseStreamObjectVersion >= 36
    # (EdGraphPin.cpp:330-333); below the gate the stream carries no field.
    # ABP_RifleAnimLayers (UE5RELEASE=35) vs B_ControlPointScoring (=36) is the
    # real-sample discriminant pair; the cursor assertions prove the gate moves.
    from uasset_read.serializers.graph_pin import read_ed_graph_pin_type
    from uasset_read.serializers.package_summary import CustomVersion, PackageFileSummary
    from uasset_read.versioning import UE5_RELEASE_STREAM_GUID, build_version_context

    with _open_sample_archive(SAMPLES / "ABP_RifleAnimLayers.uasset") as (_a, abp_summary, *_rest):
        assert build_version_context(abp_summary).custom_versions.get(UE5_RELEASE_STREAM_GUID) == 35
    with _open_sample_archive(SAMPLES / "B_ControlPointScoring.uasset") as (_a, bcps_summary, *_rest):
        assert build_version_context(bcps_summary).custom_versions.get(UE5_RELEASE_STREAM_GUID) == 36

    def _pin_type_consumed(stream_version: int) -> int:
        summary = PackageFileSummary(
            custom_versions=[CustomVersion(guid=UE5_RELEASE_STREAM_GUID, version=stream_version)]
        )
        archive = ByteArchive(scalar)
        # Mirror the production mount point (G1): the gate reads the mounted
        # context, never the summary — missing mount is a structured failure.
        archive.version_context = build_version_context(summary)
        read_ed_graph_pin_type(archive, name_map, summary=summary)
        return archive.tell()

    assert _pin_type_consumed(36) == len(scalar) == 69, "gate met: the trailing 4B bool is consumed"
    assert _pin_type_consumed(35) == len(scalar) - 4, "gate missed: the field is absent from the stream"


def test_no_unreferenced_module_level_names():
    # Every module-level def/class/constant in src/ must be referenced at least
    # once outside its own definition.
    import pathlib, re

    roots = [pathlib.Path("src"), pathlib.Path("tests"), pathlib.Path("tools")]
    text = {
        p: p.read_text(encoding="utf-8", errors="ignore")
        for r in roots for p in r.rglob("*")
        if p.is_file() and p.suffix in (".py", ".json") and "__pycache__" not in str(p)
    }
    dead = []
    for p, t in text.items():
        if not str(p).startswith("src"):
            continue
        for m in re.finditer(r"^(?:def|class) (\w+)|^([A-Z][A-Z0-9_]{2,}) =", t, re.M):
            name = m.group(1) or m.group(2)
            if name.startswith("__"):
                continue
            total = sum(
                len(re.findall(r"\b" + re.escape(name) + r"\b", s)) - (1 if q == p else 0)
                for q, s in text.items()
            )
            if total == 0:
                dead.append(f"{p}:{name}")
    assert dead == [], f"unreferenced: {sorted(dead)}"

    # One home per shared helper.
    for name in ("_int_or_none", "_node_id_from_str", "_function_graph_ids"):
        homes = [
            p for p in pathlib.Path("src/uasset_read").rglob("*.py")
            if re.search(rf"^def {name}\(", p.read_text(encoding="utf-8", errors="ignore"), re.M)
        ]
        assert len(homes) == 1, f"{name} defined in {homes}"
