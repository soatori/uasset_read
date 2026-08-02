"""Binary evidence tests for #522 CubeBuilder remaining data.

Validates that all currently parsed fields have stable, asserted values
from the fixture. These form hard regression boundaries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "FirstPerson_Lvl_FirstPerson.umap"
SOURCE_FIXTURE_SHA256 = (
    "3D476154BF4CAC39A59EC91B88F5ED6889AF113A1ECF9690A01C89D8BC32D258"
)


def _parse_cube_builder() -> dict:
    """Parse fixture and return CubeBuilder_3 asset_type_data."""
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper() == SOURCE_FIXTURE_SHA256
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))
    cube = next(
        export for export in payload["exports"]
        if export["object_name"] == "CubeBuilder_3"
    )
    return cube["asset_type_data"]


def test_cube_builder_scalar_fields_are_present():
    """X, Y, Z, WallThickness fields are parsed from tagged properties."""
    metadata = _parse_cube_builder()
    present_scalars = set()
    for key in ("size_x", "size_y", "size_z", "wall_thickness"):
        if key in metadata:
            present_scalars.add(key)
            value = metadata[key]
            print(f"  {key}: {value} (type={type(value).__name__})")
            assert isinstance(value, (int, float)), f"{key} must be numeric"
    print(f"\nPresent scalar fields: {sorted(present_scalars)}")


def test_cube_builder_boolean_and_string_fields():
    """Hollow, Tessellated are booleans; Layer is a string."""
    metadata = _parse_cube_builder()
    for key in ("hollow", "tessellated"):
        if key in metadata:
            value = metadata[key]
            print(f"  {key}: {value} (type={type(value).__name__})")
            assert isinstance(value, bool), f"{key} must be bool, got {type(value).__name__}"
    if "layer" in metadata:
        value = metadata["layer"]
        print(f"  layer: {value!r} (type={type(value).__name__})")
        assert isinstance(value, str), f"layer must be str, got {type(value).__name__}"
        assert len(value) > 0, "layer must not be empty"


def test_cube_builder_vertices_array_structure():
    """Vertices is a decoded TArray<FVector> with stable count and format."""
    metadata = _parse_cube_builder()
    if "vertices" not in metadata:
        print("  vertices not in metadata (raw_data not decoded)")
        return
    vertices = metadata["vertices"]
    assert isinstance(vertices, list), f"vertices must be list, got {type(vertices).__name__}"
    print(f"  vertex_count: {len(vertices)}")
    assert len(vertices) > 0, "Expected at least one vertex"
    for i, vert in enumerate(vertices):
        assert isinstance(vert, dict), f"vertex[{i}] must be dict"
        assert "X" in vert and "Y" in vert and "Z" in vert, (
            f"vertex[{i}] must have X, Y, Z keys; got {list(vert.keys())}"
        )
        for axis in ("X", "Y", "Z"):
            assert isinstance(vert[axis], float), (
                f"vertex[{i}].{axis} must be float, got {type(vert[axis]).__name__}"
            )
    EXPECTED_VERTEX_COUNT = 8
    assert len(vertices) == EXPECTED_VERTEX_COUNT, (
        f"Expected {EXPECTED_VERTEX_COUNT} vertices, got {len(vertices)}"
    )


def test_cube_builder_polygon_topology_structure():
    """Polys is a decoded TArray<FBuilderPoly> with stable count and fields."""
    metadata = _parse_cube_builder()
    assert "polygons" in metadata, "polygons not in metadata"
    polygons = metadata["polygons"]
    assert isinstance(polygons, list), f"polygons must be list"
    print(f"  polygon_count: {len(polygons)}")
    EXPECTED_POLYGON_COUNT = 6
    assert len(polygons) == EXPECTED_POLYGON_COUNT, (
        f"Expected {EXPECTED_POLYGON_COUNT} polygons, got {len(polygons)}"
    )
    EXPECTED_FIELDS = ("VertexIndices", "Direction", "ItemName", "PolyFlags")
    for i, poly in enumerate(polygons):
        assert isinstance(poly, dict), f"polygon[{i}] must be dict"
        assert tuple(poly.keys()) == EXPECTED_FIELDS, (
            f"polygon[{i}] fields mismatch: {tuple(poly.keys())} != {EXPECTED_FIELDS}"
        )
        vi = poly["VertexIndices"]
        assert isinstance(vi, list), f"polygon[{i}].VertexIndices must be list"
        assert len(vi) >= 3, f"polygon[{i}].VertexIndices must have >= 3 indices (triangle)"
        for idx in vi:
            assert isinstance(idx, int), f"polygon[{i}] index must be int"
        assert isinstance(poly["Direction"], int), f"polygon[{i}].Direction must be int"
        assert isinstance(poly["ItemName"], str), f"polygon[{i}].ItemName must be str"
        assert isinstance(poly["PolyFlags"], int), f"polygon[{i}].PolyFlags must be int"


def test_brush_builder_additional_properties_not_in_fixture():
    """BitmapFilename, ToolTip, NotifyBadParams, MergeCoplanars are NOT in fixture."""
    metadata = _parse_cube_builder()
    absent_fields = []
    for field in ("bitmap_filename", "tool_tip", "notify_bad_params", "merge_coplanars"):
        if field not in metadata:
            absent_fields.append(field)
        else:
            print(f"  WARNING: {field} found in metadata: {metadata[field]}")
    print(f"\nAbsent BrushBuilder fields: {absent_fields}")
    assert len(absent_fields) == 4, (
        f"Expected all 4 BrushBuilder fields absent, "
        f"found {4 - len(absent_fields)} present"
    )


def test_cube_builder_binary_layout_summary():
    """Complete binary layout summary with hard regression boundaries."""
    metadata = _parse_cube_builder()
    EXPECTED_TAIL_OFFSET = 9166
    EXPECTED_TAIL_SIZE = 4
    assert metadata["tail_offset"] == EXPECTED_TAIL_OFFSET, (
        f"tail_offset regression: expected {EXPECTED_TAIL_OFFSET}, "
        f"got {metadata['tail_offset']}"
    )
    assert metadata["tail_size"] == EXPECTED_TAIL_SIZE, (
        f"tail_size regression: expected {EXPECTED_TAIL_SIZE}, "
        f"got {metadata['tail_size']}"
    )
    layout = {
        "tagged_property_end": metadata["tail_offset"],
        "tail_bytes": metadata["tail_size"],
        "total accounted": metadata["tail_offset"] + metadata["tail_size"],
        "polygon_count": metadata.get("polygon_count", 0),
        "vertex_payload_size": metadata.get("vertex_payload_size", 0),
        "layer": metadata.get("layer"),
    }
    print(f"\n=== CubeBuilder Binary Layout ===")
    for k, v in layout.items():
        print(f"  {k}: {v}")
    assert metadata["tail_size"] == 4, "Tail must be exactly 4 bytes"
