"""Regression coverage for #522's CubeBuilder property metadata path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from uasset_read import parse_single
from uasset_read.parsers.asset_types.property_metadata import build_property_metadata
from uasset_read.parsers.class_specific_skip import should_skip_export_for_tolerant_parsing
from uasset_read.parsers.class_serialization_strategy import (
    SerializationStrategy,
    get_serialization_strategy,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "tests" / "samples" / "FirstPerson_Lvl_FirstPerson.umap"
SOURCE_FIXTURE_SHA256 = (
    "3D476154BF4CAC39A59EC91B88F5ED6889AF113A1ECF9690A01C89D8BC32D258"
)

# Dimension-acceptance fixture: a CubeBuilder that serializes non-default
# X/Y/Z tagged properties (the baseline CubeBuilder_3 is default-sized, so
# delta serialization omits its dimensions).
# Source: FirstPersonC .../Variant_Shooter/Lvl_Shooter external actor.
# Evidence: docs/designs/issue-522-cube-builder-source-evidence.md §6.
DIM_SAMPLE = ROOT / "tests" / "samples" / "FirstPersonC_Variant_Shooter_CubeBuilder_4.uasset"
DIM_FIXTURE_SHA256 = (
    "958456CBF07FC4575EC7727BAD6F3E47A8331F68778C713FC0259A3173453C80"
)

# ── Expected binary evidence for CubeBuilder_3 ──────────────────────────
# tail_offset / tail_size are the raw bytes remaining after all tagged
# properties have been consumed.  They form a hard regression boundary:
# any future change to the parser must not shift these values.
EXPECTED_TAIL_OFFSET = 9166
EXPECTED_TAIL_SIZE = 4
EXPECTED_POLYGON_FIELDS = ("VertexIndices", "Direction", "ItemName", "PolyFlags")


def _parse_cube_builder() -> dict:
    """Parse the fixture once and return the CubeBuilder_3 metadata dict."""
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper() == SOURCE_FIXTURE_SHA256
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))
    cube = next(
        export for export in payload["exports"]
        if export["object_name"] == "CubeBuilder_3"
    )
    return cube["asset_type_data"]


def _parse_dim_fixture() -> tuple[dict, dict]:
    """Parse the dimension fixture; return (cube metadata, full payload)."""
    assert hashlib.sha256(DIM_SAMPLE.read_bytes()).hexdigest().upper() == DIM_FIXTURE_SHA256
    payload = json.loads(parse_single(
        str(DIM_SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))
    cube = next(
        export for export in payload["exports"]
        if export["object_name"] == "CubeBuilder_4"
    )
    return cube["asset_type_data"], payload


def test_public_map_exposes_cube_builder_property_metadata() -> None:
    """CubeBuilder properties are published without decoding its native payload."""
    metadata = _parse_cube_builder()

    assert metadata["asset_type"] == "CubeBuilder"
    assert metadata["parse_status"] == "partial_metadata"
    assert metadata["layer"] == "Cube"
    assert metadata["polygon_count"] == 6
    assert metadata["vertex_payload_size"] == 196


# ── Phase 1: binary evidence regression boundaries ──────────────────────


def test_cube_builder_tail_offset_and_size_are_stable() -> None:
    """tail_offset / tail_size form a hard binary regression boundary.

    The 4-byte tail after tagged-property consumption is alignment padding
    or a version-specific residual; its position must not shift across
    parser changes.
    """
    metadata = _parse_cube_builder()
    assert metadata["tail_offset"] == EXPECTED_TAIL_OFFSET
    assert metadata["tail_size"] == EXPECTED_TAIL_SIZE


def test_cube_builder_has_all_expected_keys() -> None:
    """All projected keys are present; no spurious fields leak in."""
    metadata = _parse_cube_builder()
    expected_keys = {
        "asset_type", "parse_status", "layer", "polygon_count",
        "polygons", "vertex_payload_size", "vertices",
        "tail_offset", "tail_size",
    }
    assert set(metadata.keys()) == expected_keys


# ── Phase 2: material attribution — FBuilderPoly has no material field ───


def test_builder_poly_has_exactly_four_fields_no_material() -> None:
    """FBuilderPoly has exactly 4 fields; material lives in FBspSurf/UModel.

    Version-pinned evidence (UE 5.8.0-release@7deeb413,
    docs/designs/issue-522-cube-builder-source-evidence.md):
    FBuilderPoly declares exactly these UPROPERTYs
    (Engine/Source/Runtime/Engine/Classes/Engine/BrushBuilder.h:13-33):
      - VertexIndices (TArray<int32>)
      - Direction (int32)
      - ItemName (FName)
      - PolyFlags (int32)

    Materials are stored in FBspSurf.Material inside UModel
    (Engine/Source/Runtime/Engine/Public/Model.h:215), linked back to the
    editor polygon via FBspSurf.iBrushPoly.  They are NOT serialized as
    part of the CubeBuilder export.
    """
    metadata = _parse_cube_builder()
    polygons = metadata.get("polygons", [])
    assert len(polygons) > 0, "fixture must contain decoded polygons"
    first_poly = polygons[0]
    assert tuple(first_poly.keys()) == EXPECTED_POLYGON_FIELDS
    # Explicitly verify no material-related keys exist
    for field in first_poly:
        assert "material" not in field.lower(), (
            f"unexpected material field '{field}' in FBuilderPoly"
        )


def test_builder_poly_schema_matches_tagged_fallback() -> None:
    """_TAGGED_FALLBACK_STRUCT_SCHEMAS for BuilderPoly/FBuilderPoly has 4 fields."""
    from uasset_read.parsers.property_types import (
        _TAGGED_FALLBACK_STRUCT_SCHEMAS,
    )
    for struct_name in ("BuilderPoly", "FBuilderPoly"):
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS.get(struct_name)
        assert schema is not None, f"{struct_name} missing from schema dict"
        field_names = [entry[0] for entry in schema]
        assert field_names == list(EXPECTED_POLYGON_FIELDS), (
            f"{struct_name} schema fields mismatch: {field_names}"
        )


# ── Phase 3: collision / LOD — not in CubeBuilder serialization ──────────


def test_cube_builder_exposes_no_collision_or_lod_fields() -> None:
    """Collision lives in UBrushComponent→UBodySetup; LOD is a StaticMesh
    concern.  Neither is serialized as part of CubeBuilder exports.

    Version-pinned evidence (UE 5.8.0-release@7deeb413,
    docs/designs/issue-522-cube-builder-source-evidence.md):
      - Collision: UBrushComponent.BrushBodySetup
        (Engine/Source/Runtime/Engine/Classes/Components/BrushComponent.h:30)
      - LOD: UStaticMesh.RenderData / FStaticMeshLODResources
        (Engine/Source/Runtime/Engine/Classes/Engine/StaticMesh.h:602,633)
    UCubeBuilder and its parents declare no collision/LOD UPROPERTY.

    This test asserts the absence of collision/lod keys in the metadata
    output.  If future UE versions add such fields to CubeBuilder, this
    test will fail and the plan must be re-evaluated.
    """
    metadata = _parse_cube_builder()
    for key in metadata:
        key_lower = key.lower()
        assert "collision" not in key_lower, (
            f"unexpected collision field '{key}' in CubeBuilder metadata"
        )
        assert "lod" not in key_lower, (
            f"unexpected LOD field '{key}' in CubeBuilder metadata"
        )


def test_empty_cube_builder_metadata_remains_opaque() -> None:
    """No serialized business fields must not imply partial extraction."""
    assert build_property_metadata("CubeBuilder", []) == {
        "asset_type": "CubeBuilder",
        "parse_status": "opaque",
    }


def test_cube_builder_metadata_uses_empty_serialized_polys_as_zero() -> None:
    """An explicitly serialized empty Polys array is business metadata, not absence."""
    assert build_property_metadata(
        "CubeBuilder", [SimpleNamespace(name="Polys", value=[])],
    ) == {
        "asset_type": "CubeBuilder",
        "parse_status": "partial_metadata",
        "polygon_count": 0,
    }


def test_cube_builder_metadata_does_not_promote_size_without_raw_vertices() -> None:
    """A structural size alone does not prove the native vertex payload was read."""
    assert build_property_metadata(
        "CubeBuilder", [SimpleNamespace(name="Vertices", value={"size": 196})],
    ) == {
        "asset_type": "CubeBuilder",
        "parse_status": "opaque",
    }


def test_cube_builder_uses_opaque_strategy_without_broadening_skip_prefixes() -> None:
    """Only the exact CubeBuilder class is reclassified from the builder skip family."""
    assert get_serialization_strategy("CubeBuilder") is SerializationStrategy.OPAQUE_CLASS_PAYLOAD
    assert get_serialization_strategy("CubeBuilderHelper") is SerializationStrategy.SKIP_UNSUPPORTED
    assert get_serialization_strategy("GeomModifier_Any") is SerializationStrategy.SKIP_UNSUPPORTED
    assert get_serialization_strategy("BrushBuilderAny") is SerializationStrategy.SKIP_UNSUPPORTED
    assert should_skip_export_for_tolerant_parsing(
        SimpleNamespace(object_name="CubeBuilder_3"), "CubeBuilder",
    ) is False
    assert should_skip_export_for_tolerant_parsing(
        SimpleNamespace(object_name="CubeBuilderHelper_3"), "CubeBuilderHelper",
    ) is True


# ── Dimension acceptance: non-default X/Y/Z tagged properties ───────────
# The baseline CubeBuilder_3 is default-sized (X=Y=Z=200 in the UE 5.8 CDO),
# so delta serialization omits its dimensions.  This fixture was created with
# non-default dimensions, forcing X/Y/Z into the tagged stream.  Values are
# read from the serialized properties — never inferred from the vertex bbox.
# UE source: CubeBuilder.h:27-36 (X/Y/Z), EditorBrushBuilder.cpp:395-418
# (defaults), Class.cpp:1992/2018 (delta serialization).


def test_dimension_fixture_serializes_non_default_sizes() -> None:
    """size_x/size_y/size_z are projected from serialized X/Y/Z properties."""
    metadata, _ = _parse_dim_fixture()
    assert metadata["asset_type"] == "CubeBuilder"
    assert metadata["parse_status"] == "partial_metadata"
    assert metadata["size_x"] == 2936.522705078125
    assert metadata["size_y"] == 3349.49560546875
    assert metadata["size_z"] == 682.7445068359375


def test_dimension_sizes_are_distinct_not_engine_defaults() -> None:
    """The fixture proves per-axis reads: three distinct, non-default values.

    A parser that manufactured engine defaults (200.0) or copied one axis to
    all three would fail this test.
    """
    metadata, _ = _parse_dim_fixture()
    sizes = (metadata["size_x"], metadata["size_y"], metadata["size_z"])
    assert len(set(sizes)) == 3, f"axes must be distinct, got {sizes}"
    assert all(s != 200.0 for s in sizes), "sizes must not be CDO defaults"


def test_dimension_geometry_still_decodes_with_sizes_present() -> None:
    """Vertices/polygons decode alongside the new size fields; bbox is ±size/2."""
    metadata, _ = _parse_dim_fixture()
    assert metadata["polygon_count"] == 6
    assert metadata["vertex_payload_size"] == 196
    verts = metadata["vertices"]
    assert len(verts) == 8
    for axis, field in (("X", "size_x"), ("Y", "size_y"), ("Z", "size_z")):
        half = metadata[field] / 2.0
        values = [v[axis] for v in verts]
        assert min(values) == -half and max(values) == half, (
            f"{axis} bbox {min(values)}..{max(values)} != ±{half}"
        )
    assert all(tuple(p.keys()) == EXPECTED_POLYGON_FIELDS for p in metadata["polygons"])


def test_dimension_fixture_tail_boundary_is_stable() -> None:
    """The dimension fixture keeps the universal 4-byte zero tail boundary."""
    metadata, _ = _parse_dim_fixture()
    assert metadata["tail_offset"] == 7528
    assert metadata["tail_size"] == 4
    raw = DIM_SAMPLE.read_bytes()
    assert raw[7528:7532] == b"\x00\x00\x00\x00"


def test_baseline_fixture_tail_bytes_are_zero() -> None:
    """The baseline 4-byte tail is all-zero content, not just a stable offset."""
    metadata = _parse_cube_builder()
    raw = SAMPLE.read_bytes()
    start = metadata["tail_offset"]
    assert raw[start:start + metadata["tail_size"]] == b"\x00\x00\x00\x00"


# ── Hardened attribution: version-pinned source evidence ────────────────
# Absence of material/collision/LOD keys in one fixture only proves the
# fixture lacks them.  The dimension fixture's package ALSO contains the real
# owners (Model, BrushComponent, BodySetup), so the attribution claim is
# checked against a package where that data is present.  Version-pinned
# evidence: docs/designs/issue-522-cube-builder-source-evidence.md.


def test_attribution_package_contains_real_owners_but_cube_builder_has_none() -> None:
    """Same package holds Model/BrushComponent/BodySetup; CubeBuilder stays clean."""
    metadata, payload = _parse_dim_fixture()
    classes = {export.get("object_class") for export in payload["exports"]}
    assert {"Model", "BrushComponent", "BodySetup"} <= classes, (
        f"fixture must contain the real owners, got {sorted(classes)}"
    )
    for key in metadata:
        key_lower = key.lower()
        assert "material" not in key_lower
        assert "collision" not in key_lower
        assert "lod" not in key_lower
        assert "transform" not in key_lower
