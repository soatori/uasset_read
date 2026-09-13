"""Capability-gate hardening tests (plan Tasks 4–5).

Thin Material enrichment and row-names-only DataTables must not claim
``status.semantic == "complete"``. MaterialInstance parameter counts come
from normalized array lengths (legacy ``fields`` dict fallback); the real
CassiniSample MI fixture carries 3 scalar + 1 vector parameters and is
semantically complete. See docs/superpowers/plans/
2026-09-12-parse-quality-hardening.md Tasks 4–5 (#629 follow-ups) and
2026-09-13-audit-remediation-1-6.md Task 5.
"""

from __future__ import annotations

from pathlib import Path

from uasset_read.package import parse_package_document

SAMPLES = Path(__file__).parent / "samples"


# --- Task 4: Material / MaterialInstance ---


def test_material_flags_only_is_not_semantic_complete():
    doc = parse_package_document(
        SAMPLES / "MyProject_UE58_TestMaterial.uasset", depth="asset", tolerant=True
    )
    mat = next(o for o in doc.objects if o.class_name == "Material")
    assert mat.status.semantic == "partial"


def test_material_instance_real_sample_counts_parameters():
    doc = parse_package_document(
        SAMPLES / "CassiniSample_MI_Template_BaseGray_Metal.uasset",
        depth="asset",
        tolerant=True,
    )
    mi = next(o for o in doc.objects if o.class_name == "MaterialInstanceConstant")
    assert mi.semantic is not None
    assert mi.semantic["scalar_param_count"] == 3
    assert mi.semantic["vector_param_count"] == 1
    assert mi.status.semantic == "complete"


# --- Task 5: DataTable row field projection ---


def test_table_rows_project_empty_field_skeleton_for_none_only_rows():
    import struct

    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.legacy_reader import _read_table_rows

    data = (
        struct.pack("<i", 2)
        + struct.pack("<ii", 1, 0)  # A
        + struct.pack("<ii", 0, 0)  # None
        + struct.pack("<ii", 2, 0)  # B
        + struct.pack("<ii", 0, 0)  # None
    )
    arc = ByteArchive(data)
    diags: list = []
    result = _read_table_rows(
        arc, serial_end=len(data), name_map=["None", "A", "B"], object_id="export:1", diagnostics=diags
    )
    assert "rows" in result
    assert result["rows"] == [
        {"name": "A", "fields": {}},
        {"name": "B", "fields": {}},
    ]
    assert result["row_names"] == ["A", "B"]
    assert result["complete"] is True


def test_datatable_capability_requires_non_empty_field_maps():
    # Measured: every current DataTable sample carries real tagged fields, so
    # the summary path is proven at the capability gate, not by a sample.
    from uasset_read.parsers.asset_types.handlers_impl import DataTableHandler

    h = DataTableHandler()
    empty = {"rows": [{"name": "A", "fields": {}}, {"name": "B", "fields": {}}]}
    assert h.capability(empty) == "summary"
    with_fields = {"rows": [{"name": "A", "fields": {"StaticMesh": {"type": "ObjectProperty", "size": 4}}}]}
    assert h.capability(with_fields) == "decoded"
    assert h.capability({}) == "summary"


def test_datatable_with_field_names_projects_rows():
    doc = parse_package_document(
        SAMPLES / "ALS_FootstepDataTable.uasset", depth="asset", tolerant=True
    )
    dt = next(o for o in doc.objects if o.class_name == "DataTable")
    assert dt.status.semantic == "complete"
    rows = dt.semantic.get("rows")
    assert isinstance(rows, list)
    assert rows and rows[0]["name"] == "Default"
    # Field names present (values are name/type/size descriptors).
    assert isinstance(rows[0]["fields"], dict)
    assert rows[0]["fields"]


def test_datatable_parser_weapon_projects_field_maps():
    # Measured: DT_ParserWeapon rows carry SoftObjectProperty/ObjectProperty
    # field tags (not None-only), so the stricter gate legitimately yields
    # complete — the earlier row-names-only claim is gone, rows carry fields.
    doc = parse_package_document(
        SAMPLES / "DT_ParserWeapon.uasset", depth="asset", tolerant=True
    )
    dt = next(o for o in doc.objects if o.class_name == "DataTable")
    assert dt.semantic.get("row_names") == ["EmptyWeaponA", "EmptyWeaponB"]
    rows = dt.semantic.get("rows")
    assert isinstance(rows, list)
    assert rows and any((r.get("fields") or {}) for r in rows)
    assert dt.status.semantic == "complete"


# --- Task 5 (audit): MaterialInstance array parameter counts ---


def _mi_record(props: dict):
    from uasset_read.models.object_model import ObjectRecord, ObjectStatus

    obj = ObjectRecord(
        id="export:0",
        table_index=0,
        name="MI_Test",
        class_name="MaterialInstanceConstant",
        status=ObjectStatus(),
    )
    obj.properties = props
    return obj


def test_material_instance_counts_normalized_array_params():
    from uasset_read.parsers.asset_types.handlers_impl import MaterialInstanceHandler
    from uasset_read.versioning import VersionContext

    obj = _mi_record(
        {
            "Parent": {"kind": "value", "type": "ObjectProperty", "value": None},
            "ScalarParameterValues": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [{"a": 1}, {"b": 2}, {"c": 3}],
            },
            "VectorParameterValues": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [{"v": 1}],
            },
        }
    )
    result = MaterialInstanceHandler().enrich(obj, VersionContext(), [], None)
    assert result is not None
    assert result["scalar_param_count"] == 3
    assert result["vector_param_count"] == 1
    assert MaterialInstanceHandler().capability(result) == "decoded"


def test_material_instance_fields_dict_still_counted():
    from uasset_read.parsers.asset_types.handlers_impl import MaterialInstanceHandler
    from uasset_read.versioning import VersionContext

    obj = _mi_record(
        {
            "Parent": {"kind": "value", "type": "ObjectProperty", "value": None},
            "ScalarParameterValues": {"fields": {"A": 1, "B": 2}},
        }
    )
    result = MaterialInstanceHandler().enrich(obj, VersionContext(), [], None)
    assert result["scalar_param_count"] == 2


def test_material_instance_empty_arrays_stay_summary():
    # Empty normalized arrays count as present-but-zero: parent-only MI with
    # no parameters remains a summary projection, not semantic=complete.
    from uasset_read.parsers.asset_types.handlers_impl import MaterialInstanceHandler
    from uasset_read.versioning import VersionContext

    obj = _mi_record(
        {
            "Parent": {"kind": "value", "type": "ObjectProperty", "value": None},
            "ScalarParameterValues": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [],
            },
            "VectorParameterValues": {
                "kind": "value",
                "type": "ArrayProperty",
                "value": [],
            },
        }
    )
    handler = MaterialInstanceHandler()
    result = handler.enrich(obj, VersionContext(), [], None)
    assert result is not None
    assert result["scalar_param_count"] == 0
    assert result["vector_param_count"] == 0
    assert handler.capability(result) == "summary"
