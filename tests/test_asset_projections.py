# tests/test_asset_projections.py
import pytest

from uasset_read.models.document import PackageDocument, PackageInfo
from uasset_read.models.object_model import ObjectRecord, Relation
from uasset_read.projections.registry import CAPABILITY_MATRIX, ProjectorRegistry


def _doc(objects, relations=None) -> PackageDocument:
    return PackageDocument(
        package=PackageInfo(name="Synthetic", layout="legacy"),
        objects=list(objects),
        relations=list(relations or []),
    )


def _obj(oid, class_name=None, semantic=None) -> ObjectRecord:
    return ObjectRecord(
        id=oid,
        table_index=0,
        name=oid,
        class_name=class_name,
        semantic=semantic,
    )


def test_registry_selects_one_owner_for_each_asset_family(document):
    registry = ProjectorRegistry.default()
    for obj in document.objects:
        projections = registry.project_object(document, obj.id)
        assert all(item.source_object_id == obj.id for item in projections)
        assert all(item.status in {"translated", "represented", "untranslated", "unavailable"} for item in projections)
    for item in registry.project_document(document):
        assert "cpp" not in item.kind
        assert "editor_builder" not in item.kind
        assert not item.media_type.startswith("text/x-c")


def test_cooked_material_has_no_builder_projection(cooked_material):
    # Cooked/editor-stripped materials keep their semantic; the retired
    # editor-builder projection family is gone rather than faked unavailable.
    projections = ProjectorRegistry.default().project_document(cooked_material)
    assert all("editor_builder" not in item.kind for item in projections)
    assert all(not item.media_type.startswith("text/x-c") for item in projections)


def test_capability_matrix_declares_required_families_and_kinds():
    by_family = {entry["family"]: entry for entry in CAPABILITY_MATRIX}
    assert by_family["data_table"]["kinds"] == ["data_table", "data_table_csv", "data_table_json"]
    assert "values decoded" in by_family["data_table"]["rule"]
    assert by_family["curve_table"]["kinds"] == ["curve_table", "curve_table_csv", "curve_table_json"]
    assert "keys" in by_family["curve_table"]["rule"]
    assert by_family["material_instance"]["kinds"] == ["material_instance", "material_parameters"]
    assert by_family["other_graph_assets"]["kinds"] == ["graph"]
    assert by_family["physical_binary_assets"]["kinds"] == ["asset_metadata", "payload_reference"]
    assert by_family["user_defined_struct_enum"]["kinds"] == ["defaults_json"]
    for entry in CAPABILITY_MATRIX:
        for kind in entry["kinds"]:
            assert "cpp" not in kind
            assert "editor_builder" not in kind


def test_datatable_projector_copies_evidenced_fields_or_unavailable():
    registry = ProjectorRegistry.default()
    evidenced = _obj(
        "export:0",
        class_name="DataTable",
        semantic={
            "kind": "data_table",
            "row_struct": "/Script/Game.MyRow",
            "row_count": 1,
            "rows": [
                {
                    "name": "Row_A",
                    "fields": {"Score": {"type": "int32", "size": 4}},
                }
            ],
        },
    )
    records = registry.project_object(_doc([evidenced]), evidenced.id)
    kinds = {item.kind for item in records}
    assert kinds == {"data_table", "data_table_csv", "data_table_json"}
    data = next(item for item in records if item.kind == "data_table")
    assert data.status == "represented"
    assert data.content["columns"] == [{"name": "Score", "type": "int32"}]
    assert data.content["rows"][0]["values"]["Score"] == {"type": "int32", "size": 4}

    empty = _obj(
        "export:1",
        class_name="DataTable",
        semantic={
            "kind": "data_table",
            "row_struct": "/Script/Game.MyRow",
            "rows": [{"name": "NoneOnly", "fields": {}}],
        },
    )
    empty_records = registry.project_object(_doc([empty]), empty.id)
    assert empty_records
    assert all(item.status == "unavailable" for item in empty_records)
    assert all(item.content is None for item in empty_records)


def test_curve_table_without_explicit_keys_is_unavailable():
    registry = ProjectorRegistry.default()
    obj = _obj(
        "export:0",
        class_name="CurveTable",
        semantic={
            "kind": "curve_table",
            "curve_table_mode": "RichCurves",
            "rows": [
                {
                    "name": "RowA",
                    "fields": {"Keys": {"type": "ArrayProperty", "size": 58}},
                }
            ],
        },
    )
    records = registry.project_object(_doc([obj]), obj.id)
    assert records
    assert all(item.status == "unavailable" for item in records)


def test_kind_first_dispatch_does_not_dual_claim_by_class_name():
    registry = ProjectorRegistry.default()
    # Semantic kind owns the object even when class_name looks like another family.
    obj = _obj(
        "export:0",
        class_name="Material",
        semantic={
            "kind": "data_table",
            "row_struct": "/Script/Game.MyRow",
            "rows": [{"name": "R", "fields": {"A": {"type": "int32", "size": 4}}}],
        },
    )
    records = registry.project_object(_doc([obj]), obj.id)
    assert records
    assert not any("editor_builder" in item.kind for item in records)
    assert any(item.kind.startswith("data_table") for item in records)


def test_blueprint_family_has_no_dedicated_projection_record():
    # Blueprint static semantics (IR/CFG/calls/reads/writes) live on
    # objects[].semantic; the family emits no projection record at all.
    registry = ProjectorRegistry.default()
    obj = _obj("export:0", class_name="Blueprint", semantic=None)
    doc = _doc(
        [obj],
        relations=[Relation(kind="depends_on", from_id="export:0", to_id="import:3")],
    )
    assert registry.project_object(doc, obj.id) == []


def test_material_instance_and_physical_family_matrix_behavior():
    registry = ProjectorRegistry.default()
    mi = _obj(
        "export:0",
        class_name="MaterialInstanceConstant",
        semantic={"kind": "material_instance", "name": "MI", "has_parent": True},
    )
    mi_records = registry.project_object(_doc([mi]), mi.id)
    assert {item.kind for item in mi_records} == {"material_instance", "material_parameters"}
    assert all(item.status == "represented" for item in mi_records)

    texture = _obj("export:1", class_name="Texture2D", semantic={"kind": "texture"})
    tex_records = registry.project_object(_doc([texture]), texture.id)
    kinds = {item.kind for item in tex_records}
    assert "asset_metadata" in kinds
    payload = next(item for item in tex_records if item.kind == "payload_reference")
    assert payload.status == "unavailable"


def test_registry_rejects_two_matching_projectors():
    class _Stub:
        def can_project(self, obj):
            return True

        def project(self, document, obj):
            return []

    registry = ProjectorRegistry()
    registry.register(_Stub())
    registry.register(_Stub())
    doc = _doc([_obj("export:0", class_name="StaticMesh")])
    with pytest.raises(ValueError, match="ambiguous projector ownership"):
        registry.project_object(doc, "export:0")


def _csv_rows(record) -> list[list[str]]:
    import csv
    from io import StringIO

    return list(csv.reader(StringIO(record.content)))


def test_datatable_csv_cells_survive_commas_quotes_newlines_and_structure():
    registry = ProjectorRegistry.default()
    obj = _obj(
        "export:0",
        class_name="DataTable",
        semantic={
            "kind": "data_table",
            "row_struct": "/Script/Game.MyRow",
            "row_count": 2,
            "rows": [
                {
                    "name": 'Row, "A"\nB',
                    "fields": {
                        "Text": {"type": "StrProperty", "value": 'has, "quotes"\nnewline'},
                        "Struct": {"type": "StructProperty", "size": 8, "struct_type": "Vector"},
                    },
                },
                {"name": "RowB", "fields": {"Text": {"type": "StrProperty", "value": "plain"}}},
            ],
        },
    )
    records = registry.project_object(_doc([obj]), obj.id)
    rows = _csv_rows(next(item for item in records if item.kind == "data_table_csv"))
    header = rows[0]
    assert header == ["name", "Text", "Struct"]
    assert all(len(row) == len(header) for row in rows)
    assert rows[1][0] == 'Row, "A"\nB'
    assert rows[1][1] == 'has, "quotes"\nnewline'
    assert rows[1][2] == '{"size":8,"struct_type":"Vector","type":"StructProperty"}'
    assert rows[2][0] == "RowB"
    assert rows[2][1] == "plain"
    assert rows[2][2] == ""


def test_curve_table_csv_pins_columns_and_compact_json_cells():
    import json

    registry = ProjectorRegistry.default()
    obj = _obj(
        "export:0",
        class_name="CurveTable",
        semantic={
            "kind": "curve_table",
            "curve_table_mode": "RichCurves",
            "rows": [
                {
                    "name": 'Curve, "X"\nY',
                    "fields": {
                        "Keys": {
                            "type": "ArrayProperty",
                            "value": [{"time": 1.0, "value": 2.0, "interp": "linear"}],
                        },
                        "Other": {"type": "FloatProperty", "size": 4},
                    },
                }
            ],
        },
    )
    records = registry.project_object(_doc([obj]), obj.id)
    rows = _csv_rows(next(item for item in records if item.kind == "curve_table_csv"))
    assert rows[0] == ["name", "key_count", "field_types", "keys"]
    assert all(len(row) == 4 for row in rows)
    compact = {"ensure_ascii": False, "separators": (",", ":"), "sort_keys": True}
    assert rows[1][0] == 'Curve, "X"\nY'
    assert rows[1][1] == "1"
    assert rows[1][2] == json.dumps({"Keys": "ArrayProperty", "Other": "FloatProperty"}, **compact)
    assert rows[1][3] == json.dumps([{"interp": "linear", "time": 1.0, "value": 2.0}], **compact)
