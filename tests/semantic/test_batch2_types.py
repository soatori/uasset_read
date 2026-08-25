"""Tests for Batch 2 missing UAsset type mappings."""
from uasset_read.semantic.kinds import resolve_asset_type


class TestPhysicsTypes:
    """Test physics type mappings."""

    def test_physics_asset_resolves(self):
        assert resolve_asset_type("PhysicsAsset") == "physics_asset"

    def test_physical_material_resolves(self):
        assert resolve_asset_type("PhysicalMaterial") == "physical_material"

    def test_physics_asset_parser_exists(self):
        from uasset_read.parsers.asset_types.physics_asset import parse_physics_asset
        assert callable(parse_physics_asset)

    def test_physical_material_parser_exists(self):
        from uasset_read.parsers.asset_types.physical_material import parse_physical_material
        assert callable(parse_physical_material)


class TestAnimationTypes:
    """Test animation type mappings."""

    def test_anim_layer_interface_resolves(self):
        assert resolve_asset_type("AnimLayerInterface") == "anim_layer_interface"

    def test_anim_layer_interface_parser_exists(self):
        from uasset_read.parsers.asset_types.anim_layer_interface import parse_anim_layer_interface
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
        from uasset_read.parsers.asset_types.sound_mix import parse_sound_mix
        assert callable(parse_sound_mix)

    def test_sound_class_parser_exists(self):
        from uasset_read.parsers.asset_types.sound_class import parse_sound_class
        assert callable(parse_sound_class)

    def test_sound_submix_parser_exists(self):
        from uasset_read.parsers.asset_types.sound_submix import parse_sound_submix
        assert callable(parse_sound_submix)


class TestAITypes:
    """Test AI type mappings."""

    def test_behavior_tree_resolves(self):
        assert resolve_asset_type("BehaviorTree") == "behavior_tree"

    def test_blackboard_data_resolves(self):
        assert resolve_asset_type("BlackboardData") == "blackboard_data"

    def test_behavior_tree_parser_exists(self):
        from uasset_read.parsers.asset_types.behavior_tree import parse_behavior_tree
        assert callable(parse_behavior_tree)

    def test_blackboard_data_parser_exists(self):
        from uasset_read.parsers.asset_types.blackboard_data import parse_blackboard_data
        assert callable(parse_blackboard_data)


class TestDataTypes:
    """Test data asset type mappings."""

    def test_data_asset_resolves(self):
        assert resolve_asset_type("DataAsset") == "data_asset"

    def test_primary_data_asset_resolves(self):
        assert resolve_asset_type("PrimaryDataAsset") == "primary_data_asset"

    def test_data_asset_parser_exists(self):
        from uasset_read.parsers.asset_types.data_asset import parse_data_asset
        assert callable(parse_data_asset)

    def test_primary_data_asset_parser_exists(self):
        from uasset_read.parsers.asset_types.primary_data_asset import parse_primary_data_asset
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
        from uasset_read.parsers.asset_types.landscape import parse_landscape
        assert callable(parse_landscape)

    def test_landscape_grass_type_parser_exists(self):
        from uasset_read.parsers.asset_types.landscape_grass_type import parse_landscape_grass_type
        assert callable(parse_landscape_grass_type)

    def test_landscape_layer_info_parser_exists(self):
        from uasset_read.parsers.asset_types.landscape_layer_info import parse_landscape_layer_info
        assert callable(parse_landscape_layer_info)


class TestWorldTypes:
    """Test world type mappings."""

    def test_world_resolves(self):
        assert resolve_asset_type("World") == "world"

    def test_level_resolves(self):
        assert resolve_asset_type("Level") == "level"

    def test_world_parser_exists(self):
        from uasset_read.parsers.asset_types.world import parse_world
        assert callable(parse_world)

    def test_level_parser_exists(self):
        from uasset_read.parsers.asset_types.level import parse_level
        assert callable(parse_level)


class TestParticlesAndUITypes:
    """Test particle and UI type mappings."""

    def test_particle_system_resolves(self):
        assert resolve_asset_type("ParticleSystem") == "particle_system"

    def test_widget_blueprint_resolves(self):
        assert resolve_asset_type("WidgetBlueprint") == "widget_blueprint"

    def test_particle_system_parser_exists(self):
        from uasset_read.parsers.asset_types.particle_system import parse_particle_system
        assert callable(parse_particle_system)

    def test_widget_blueprint_parser_exists(self):
        from uasset_read.parsers.asset_types.widget_blueprint import parse_widget_blueprint
        assert callable(parse_widget_blueprint)


class TestAdvancedTextureTypes:
    """Test advanced texture type mappings."""

    def test_texture2d_array_resolves_to_texture(self):
        assert resolve_asset_type("Texture2DArray") == "texture"

    def test_volume_texture_resolves_to_texture(self):
        assert resolve_asset_type("VolumeTexture") == "texture"

    def test_texture2d_array_parser_exists(self):
        from uasset_read.parsers.asset_types.texture2d_array import parse_texture2d_array
        assert callable(parse_texture2d_array)

    def test_volume_texture_parser_exists(self):
        from uasset_read.parsers.asset_types.volume_texture import parse_volume_texture
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
        from uasset_read.parsers.asset_types.media_player import parse_media_player
        assert callable(parse_media_player)

    def test_media_texture_parser_exists(self):
        from uasset_read.parsers.asset_types.media_texture import parse_media_texture
        assert callable(parse_media_texture)

    def test_media_source_parser_exists(self):
        from uasset_read.parsers.asset_types.media_source import parse_media_source
        assert callable(parse_media_source)


class TestClothAndHairTypes:
    """Test cloth and hair type mappings."""

    def test_cloth_asset_resolves(self):
        assert resolve_asset_type("ClothAsset") == "cloth_asset"

    def test_groom_asset_resolves(self):
        assert resolve_asset_type("GroomAsset") == "groom_asset"

    def test_cloth_asset_parser_exists(self):
        from uasset_read.parsers.asset_types.cloth_asset import parse_cloth_asset
        assert callable(parse_cloth_asset)

    def test_groom_asset_parser_exists(self):
        from uasset_read.parsers.asset_types.groom_asset import parse_groom_asset
        assert callable(parse_groom_asset)


class TestSparseVTType:
    """Test sparse volume texture type mapping."""

    def test_sparse_volume_texture_resolves(self):
        assert resolve_asset_type("SparseVolumeTexture") == "sparse_volume_texture"

    def test_sparse_volume_texture_parser_exists(self):
        from uasset_read.parsers.asset_types.sparse_volume_texture import parse_sparse_volume_texture
        assert callable(parse_sparse_volume_texture)


class TestBatch2Integration:
    """Integration test for all Batch 2 types."""

    def test_all_batch2_types_have_kinds_mapping(self):
        """Verify all Batch 2 registered parser types have kinds.py mappings."""
        from uasset_read.semantic.kinds import resolve_asset_type

        batch2_classes = [
            "PhysicsAsset", "PhysicalMaterial",
            "AnimLayerInterface",
            "SoundMix", "SoundClass", "SoundSubmix",
            "BehaviorTree", "BlackboardData",
            "DataAsset", "PrimaryDataAsset",
            "Landscape", "LandscapeGrassType", "LandscapeLayerInfoObject",
            "World", "Level",
            "ParticleSystem",
            "WidgetBlueprintGeneratedClass", "WidgetBlueprint",
            "Texture2DArray", "VolumeTexture",
            "MediaPlayer", "MediaTexture", "MediaSource",
            "ClothAsset", "GroomAsset",
            "SparseVolumeTexture",
        ]

        unmapped = [cls for cls in batch2_classes if resolve_asset_type(cls) == "unknown"]
        assert unmapped == [], f"Classes without kinds.py mapping: {unmapped}"

    def test_total_type_count_increased(self):
        """Verify _TYPE_MAP has grown significantly."""
        from uasset_read.semantic.kinds import _TYPE_MAP
        assert len(_TYPE_MAP) >= 75, f"Expected >=75 types, got {len(_TYPE_MAP)}"
