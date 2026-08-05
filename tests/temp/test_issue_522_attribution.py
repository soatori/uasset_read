"""Attribution investigation tests for #522.

Verifies whether material, collision, and LOD data belong to CubeBuilder
or to other UE classes (UModel/FBspSurf, UBrushComponent/UBodySetup).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "FirstPerson_Lvl_FirstPerson.umap"
SOURCE_FIXTURE_SHA256 = (
    "3D476154BF4CAC39A59EC91B88F5ED6889AF113A1ECF9690A01C89D8BC32D258"
)


def _parse_fixture() -> dict:
    """Parse fixture and return full payload."""
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper() == SOURCE_FIXTURE_SHA256
    return json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))


def test_fbuilder_poly_has_no_material_field() -> None:
    """FBuilderPoly contains only VertexIndices, Direction, ItemName, PolyFlags.

    UE source: Engine/BrushBuilder.h
    Materials are stored in FBspSurf.Material inside UModel, not in CubeBuilder.
    """
    payload = _parse_fixture()
    cube = next(
        e for e in payload["exports"]
        if e.get("object_name") == "CubeBuilder_3"
    )
    atd = cube.get("asset_type_data", {})
    polygons = atd.get("polygons", [])
    assert len(polygons) > 0, "Expected decoded polygons"

    for i, poly in enumerate(polygons):
        keys = set(poly.keys())
        assert keys == {"VertexIndices", "Direction", "ItemName", "PolyFlags"}, (
            f"polygon[{i}] has unexpected keys: {keys}"
        )
        # Explicitly verify no material-related keys
        for key in keys:
            assert "material" not in key.lower(), (
                f"polygon[{i}] has material field '{key}' — "
                f"materials belong in FBspSurf/UModel, not CubeBuilder"
            )


def test_cube_builder_export_has_no_material_property() -> None:
    """CubeBuilder_3 export must not contain a Material tagged property."""
    payload = _parse_fixture()
    cube = next(
        e for e in payload["exports"]
        if e.get("object_name") == "CubeBuilder_3"
    )
    props = cube.get("properties", [])
    prop_names = {p.get("name", "") for p in props}
    assert "Material" not in prop_names, (
        "CubeBuilder_3 should not have a Material property"
    )


def test_cube_builder_export_has_no_collision_property() -> None:
    """CubeBuilder_3 export must not contain collision-related properties.

    Collision lives in UBrushComponent -> UBodySetup, not in CubeBuilder.
    UE source: Engine/BrushComponent.h, Engine/BodySetup.h
    """
    payload = _parse_fixture()
    cube = next(
        e for e in payload["exports"]
        if e.get("object_name") == "CubeBuilder_3"
    )
    props = cube.get("properties", [])
    prop_names = {p.get("name", "") for p in props}
    collision_keywords = {"Collision", "BodySetup", "PhysMaterial", "CollisionProfile"}
    found = prop_names & collision_keywords
    assert len(found) == 0, (
        f"CubeBuilder_3 has collision-related properties: {found}. "
        f"Collision belongs in UBrushComponent/UBodySetup."
    )


def test_cube_builder_export_has_no_lod_property() -> None:
    """CubeBuilder_3 export must not contain LOD-related properties.

    LOD is a StaticMesh concern, not a CubeBuilder concern.
    UE source: Engine/StaticMesh.h
    """
    payload = _parse_fixture()
    cube = next(
        e for e in payload["exports"]
        if e.get("object_name") == "CubeBuilder_3"
    )
    props = cube.get("properties", [])
    prop_names = {p.get("name", "") for p in props}
    lod_keywords = {"LOD", "LodGroup", "ScreenSize", "ForcedLodModel"}
    found = prop_names & lod_keywords
    assert len(found) == 0, (
        f"CubeBuilder_3 has LOD-related properties: {found}. "
        f"LOD belongs in StaticMesh, not CubeBuilder."
    )
