"""Tests for asset kind classifier."""
from uasset_read.semantic.kinds import AssetKind, classify_asset


class TestAssetKindEnum:
    def test_has_graph_value(self):
        assert AssetKind.GRAPH.value == "graph"

    def test_has_structured_value(self):
        assert AssetKind.STRUCTURED.value == "structured"

    def test_has_resource_value(self):
        assert AssetKind.RESOURCE.value == "resource"

    def test_has_opaque_value(self):
        assert AssetKind.OPAQUE.value == "opaque"


class TestClassifyAsset:
    # Graph domain
    def test_material_is_graph(self):
        assert classify_asset("Material", None) == AssetKind.GRAPH

    def test_material_instance_is_graph(self):
        assert classify_asset("MaterialInstanceConstant", None) == AssetKind.GRAPH

    def test_sound_cue_is_graph(self):
        assert classify_asset("SoundCue", None) == AssetKind.GRAPH

    def test_niagara_system_is_graph(self):
        assert classify_asset("NiagaraSystem", None) == AssetKind.GRAPH

    def test_niagara_script_is_graph(self):
        assert classify_asset("NiagaraScript", None) == AssetKind.GRAPH

    # Structured domain
    def test_static_mesh_is_structured(self):
        assert classify_asset("StaticMesh", None) == AssetKind.STRUCTURED

    def test_skeletal_mesh_is_structured(self):
        assert classify_asset("SkeletalMesh", None) == AssetKind.STRUCTURED

    def test_skeleton_is_structured(self):
        assert classify_asset("Skeleton", None) == AssetKind.STRUCTURED

    def test_anim_sequence_is_structured(self):
        assert classify_asset("AnimSequence", None) == AssetKind.STRUCTURED

    def test_data_table_is_structured(self):
        assert classify_asset("DataTable", None) == AssetKind.STRUCTURED

    # Resource domain
    def test_texture2d_is_resource(self):
        assert classify_asset("Texture2D", None) == AssetKind.RESOURCE

    def test_sound_wave_is_resource(self):
        assert classify_asset("SoundWave", None) == AssetKind.RESOURCE

    # Opaque fallback
    def test_unknown_class_is_opaque(self):
        assert classify_asset("SomeUnknownClass", None) == AssetKind.OPAQUE

    def test_empty_class_is_opaque(self):
        assert classify_asset("", None) == AssetKind.OPAQUE

    # Blueprint exclusion — #551 handles these
    def test_blueprint_generated_class_is_opaque(self):
        assert classify_asset("BlueprintGeneratedClass", None) == AssetKind.OPAQUE

    def test_anim_blueprint_is_opaque(self):
        assert classify_asset("AnimBlueprintGeneratedClass", None) == AssetKind.OPAQUE
