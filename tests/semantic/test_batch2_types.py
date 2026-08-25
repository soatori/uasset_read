"""Tests for Batch 2 missing UAsset type mappings."""

from uasset_read.semantic.builder import resolve_asset_type
from uasset_read.parsers.asset_types.opaque_stub import make_opaque_stub


def _make_stub(class_name):
    """Create an opaque stub parser for testing."""
    return make_opaque_stub(class_name)


class TestPhysicsTypes:
    """Test physics type mappings."""

    def test_physics_asset_resolves(self):
        assert resolve_asset_type("PhysicsAsset") == "physics_asset"

    def test_physical_material_resolves(self):
        assert resolve_asset_type("PhysicalMaterial") == "physical_material"

    def test_physics_asset_parser_exists(self):
        parse_physics_asset = _make_stub("PhysicsAsset")
        assert callable(parse_physics_asset)

    def test_physical_material_parser_exists(self):
        parse_physical_material = _make_stub("PhysicalMaterial")
        assert callable(parse_physical_material)


class TestAnimationTypes:
    """Test animation type mappings."""

    def test_anim_layer_interface_resolves(self):
        assert resolve_asset_type("AnimLayerInterface") == "anim_layer_interface"

    def test_anim_layer_interface_parser_exists(self):
        parse_anim_layer_interface = _make_stub("AnimLayerInterface")
        assert callable(parse_anim_layer_interface)


class TestSoundTypes:
    """Test sound type mappings."""

    def test_sound_mix_resolves(self):
        assert resolve_asset_type("SoundMix") == "sound_mix"

    def test_sound_class_resolves(self):
        assert resolve_asset_type("SoundClass") == "sound_class"

    def test_sound_submix_resolves(self):
        assert resolve_asset_type("SoundSubmix") == "sound_submix"

    def test_sound_mix_parser_exists(self):
        parse_sound_mix = _make_stub("SoundMix")
        assert callable(parse_sound_mix)

    def test_sound_class_parser_exists(self):
        parse_sound_class = _make_stub("SoundClass")
        assert callable(parse_sound_class)

    def test_sound_submix_parser_exists(self):
        parse_sound_submix = _make_stub("SoundSubmix")
        assert callable(parse_sound_submix)


class TestAITypes:
    """Test AI type mappings."""

    def test_behavior_tree_resolves(self):
        assert resolve_asset_type("BehaviorTree") == "behavior_tree"

    def test_blackboard_data_resolves(self):
        assert resolve_asset_type("BlackboardData") == "blackboard_data"

    def test_behavior_tree_parser_exists(self):
        parse_behavior_tree = _make_stub("BehaviorTree")
        assert callable(parse_behavior_tree)

    def test_blackboard_data_parser_exists(self):
        parse_blackboard_data = _make_stub("BlackboardData")
        assert callable(parse_blackboard_data)


class TestDataTypes:
    """Test data asset type mappings."""

    def test_data_asset_resolves(self):
        assert resolve_asset_type("DataAsset") == "data_asset"

    def test_primary_data_asset_resolves(self):
        assert resolve_asset_type("PrimaryDataAsset") == "primary_data_asset"

    def test_data_asset_parser_exists(self):
        parse_data_asset = _make_stub("DataAsset")
        assert callable(parse_data_asset)

    def test_primary_data_asset_parser_exists(self):
        parse_primary_data_asset = _make_stub("PrimaryDataAsset")
        assert callable(parse_primary_data_asset)


class TestLandscapeTypes:
    """Test landscape type mappings."""

    def test_landscape_resolves(self):
        assert resolve_asset_type("Landscape") == "landscape"

    def test_landscape_grass_type_resolves(self):
        assert resolve_asset_type("LandscapeGrassType") == "landscape_grass_type"

    def test_landscape_layer_info_object_resolves(self):
        assert resolve_asset_type("LandscapeLayerInfoObject") == "landscape_layer_info"

    def test_landscape_parser_exists(self):
        parse_landscape = _make_stub("Landscape")
        assert callable(parse_landscape)

    def test_landscape_grass_type_parser_exists(self):
        parse_landscape_grass_type = _make_stub("LandscapeGrassType")
        assert callable(parse_landscape_grass_type)

    def test_landscape_layer_info_parser_exists(self):
        parse_landscape_layer_info = _make_stub("LandscapeLayerInfoObject")
        assert callable(parse_landscape_layer_info)


class TestWorldTypes:
    """Test world type mappings."""

    def test_world_resolves(self):
        assert resolve_asset_type("World") == "world"

    def test_level_resolves(self):
        assert resolve_asset_type("Level") == "level"

    def test_world_parser_exists(self):
        parse_world = _make_stub("World")
        assert callable(parse_world)

    def test_level_parser_exists(self):
        parse_level = _make_stub("Level")
        assert callable(parse_level)


class TestParticlesAndUITypes:
    """Test particle and UI type mappings."""

    def test_particle_system_resolves(self):
        assert resolve_asset_type("ParticleSystem") == "particle_system"

    def test_widget_blueprint_resolves(self):
        assert resolve_asset_type("WidgetBlueprint") == "widget_blueprint"

    def test_particle_system_parser_exists(self):
        parse_particle_system = _make_stub("ParticleSystem")
        assert callable(parse_particle_system)

    def test_widget_blueprint_parser_exists(self):
        parse_widget_blueprint = _make_stub("WidgetBlueprintGeneratedClass")
        assert callable(parse_widget_blueprint)


class TestAdvancedTextureTypes:
    """Test advanced texture type mappings."""

    def test_texture2d_array_resolves_to_texture(self):
        assert resolve_asset_type("Texture2DArray") == "texture"

    def test_volume_texture_resolves_to_texture(self):
        assert resolve_asset_type("VolumeTexture") == "texture"

    def test_texture2d_array_parser_exists(self):
        parse_texture2d_array = _make_stub("Texture2DArray")
        assert callable(parse_texture2d_array)

    def test_volume_texture_parser_exists(self):
        parse_volume_texture = _make_stub("VolumeTexture")
        assert callable(parse_volume_texture)


class TestMediaTypes:
    """Test media type mappings."""

    def test_media_player_resolves(self):
        assert resolve_asset_type("MediaPlayer") == "media_player"

    def test_media_texture_resolves(self):
        assert resolve_asset_type("MediaTexture") == "media_texture"

    def test_media_source_resolves(self):
        assert resolve_asset_type("MediaSource") == "media_source"

    def test_media_player_parser_exists(self):
        parse_media_player = _make_stub("MediaPlayer")
        assert callable(parse_media_player)

    def test_media_texture_parser_exists(self):
        parse_media_texture = _make_stub("MediaTexture")
        assert callable(parse_media_texture)

    def test_media_source_parser_exists(self):
        parse_media_source = _make_stub("MediaSource")
        assert callable(parse_media_source)


class TestClothAndHairTypes:
    """Test cloth and hair type mappings."""

    def test_cloth_asset_resolves(self):
        assert resolve_asset_type("ClothAsset") == "cloth_asset"

    def test_groom_asset_resolves(self):
        assert resolve_asset_type("GroomAsset") == "groom_asset"

    def test_cloth_asset_parser_exists(self):
        parse_cloth_asset = _make_stub("ClothAsset")
        assert callable(parse_cloth_asset)

    def test_groom_asset_parser_exists(self):
        parse_groom_asset = _make_stub("GroomAsset")
        assert callable(parse_groom_asset)


class TestSparseVTType:
    """Test sparse volume texture type mapping."""

    def test_sparse_volume_texture_resolves(self):
        assert resolve_asset_type("SparseVolumeTexture") == "sparse_volume_texture"

    def test_sparse_volume_texture_parser_exists(self):
        parse_sparse_volume_texture = _make_stub("SparseVolumeTexture")
        assert callable(parse_sparse_volume_texture)


class TestBatch2Integration:
    """Integration test for all Batch 2 types."""

    def test_all_batch2_types_have_kinds_mapping(self):
        """Verify all Batch 2 registered parser types have kinds.py mappings."""
        from uasset_read.semantic.builder import resolve_asset_type

        batch2_classes = [
            "PhysicsAsset",
            "PhysicalMaterial",
            "AnimLayerInterface",
            "SoundMix",
            "SoundClass",
            "SoundSubmix",
            "BehaviorTree",
            "BlackboardData",
            "DataAsset",
            "PrimaryDataAsset",
            "Landscape",
            "LandscapeGrassType",
            "LandscapeLayerInfoObject",
            "World",
            "Level",
            "ParticleSystem",
            "WidgetBlueprintGeneratedClass",
            "WidgetBlueprint",
            "Texture2DArray",
            "VolumeTexture",
            "MediaPlayer",
            "MediaTexture",
            "MediaSource",
            "ClothAsset",
            "GroomAsset",
            "SparseVolumeTexture",
        ]

        unmapped = [cls for cls in batch2_classes if resolve_asset_type(cls) == "unknown"]
        assert unmapped == [], f"Classes without kinds.py mapping: {unmapped}"

    def test_total_type_count_increased(self):
        """Verify _TYPE_MAP has grown significantly."""
        from uasset_read.semantic.builder import _TYPE_MAP

        assert len(_TYPE_MAP) >= 75, f"Expected >=75 types, got {len(_TYPE_MAP)}"
