# tests/test_asset_projections.py
from uasset_read.projections.registry import ProjectorRegistry


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
