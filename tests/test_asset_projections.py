# tests/test_asset_projections.py
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
        assert all(item.status in {
            "translated", "represented", "untranslated", "unavailable"
        } for item in projections)
    assert any(item.kind == "cpp_declaration" for item in registry.project_document(document))


def test_cooked_material_builder_is_not_reported_as_complete(cooked_material):
    projections = ProjectorRegistry.default().project_document(cooked_material)
    builders = [item for item in projections if item.kind == "material_editor_builder"]
    assert builders
    assert builders[0].status == "unavailable"


def test_capability_matrix_declares_required_families_and_kinds():
    by_family = {entry["family"]: entry for entry in CAPABILITY_MATRIX}
    assert by_family["data_table"]["kinds"] == [
        "data_table", "data_table_csv", "data_table_json"
    ]
    assert "values decoded" in by_family["data_table"]["rule"]
    assert by_family["curve_table"]["kinds"] == [
        "curve_table", "curve_table_csv", "curve_table_json"
    ]
    assert "keys" in by_family["curve_table"]["rule"]
    assert by_family["material_instance"]["kinds"] == [
        "material_instance", "material_parameters"
    ]
    assert by_family["other_graph_assets"]["kinds"] == ["graph", "asset_builder_cpp"]
    assert by_family["physical_binary_assets"]["kinds"] == [
        "asset_metadata", "payload_reference"
    ]


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
    assert not any(item.kind == "material_editor_builder" for item in records)
    assert any(item.kind.startswith("data_table") for item in records)


def test_blueprint_unavailable_records_keep_relation_dependencies():
    registry = ProjectorRegistry.default()
    obj = _obj("export:0", class_name="Blueprint", semantic=None)
    doc = _doc(
        [obj],
        relations=[Relation(kind="depends_on", from_id="export:0", to_id="import:3")],
    )
    records = registry.project_object(doc, obj.id)
    assert records
    assert all(item.status == "unavailable" for item in records)
    assert all("import:3" in item.dependencies for item in records)


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
