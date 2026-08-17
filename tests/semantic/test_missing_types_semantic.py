"""Tests for missing UAsset type mappings and parser stubs."""
import pytest
from uasset_read.semantic.kinds import resolve_asset_type


class TestMissingTypeMappings:
    """Test that parser-only types are correctly mapped."""

    def test_animation_data_model_resolves(self):
        assert resolve_asset_type("AnimationDataModel") == "anim_data_model"

    def test_string_table_resolves(self):
        assert resolve_asset_type("StringTable") == "string_table"

    def test_anim_bone_compression_settings_resolves(self):
        assert resolve_asset_type("AnimBoneCompressionSettings") == "anim_bone_compression_settings"

    def test_anim_curve_compression_codec_resolves(self):
        assert resolve_asset_type("AnimCurveCompressionCodec") == "anim_curve_compression_codec"

    def test_anim_curve_compression_settings_still_works(self):
        """Existing mapping should continue to work."""
        assert resolve_asset_type("AnimCurveCompressionSettings") == "anim_curve_compression_settings"


class TestCurveFloatParser:
    """Test CurveFloat parser stub."""

    def test_curve_float_parser_exists(self):
        from uasset_read.parsers.asset_types.curve_float import parse_curve_float
        assert callable(parse_curve_float)

    def test_curve_float_returns_opaque_stub(self):
        from uasset_read.parsers.asset_types.curve_float import parse_curve_float

        class MockArchive:
            def tell(self):
                return 0

            def total_size(self):
                return 100

            def read(self, n):
                return b'\x00' * n

        result = parse_curve_float(MockArchive(), [])
        assert result["parse_status"] == "partial_metadata"
        assert "raw_offset" in result
        assert "sample_size" in result


class TestMaterialTypes:
    """Test MaterialFunction and MaterialParameterCollection types."""

    def test_material_function_resolves(self):
        assert resolve_asset_type("MaterialFunction") == "material_function"

    def test_material_parameter_collection_resolves(self):
        assert resolve_asset_type("MaterialParameterCollection") == "material_parameter_collection"

    def test_material_function_parser_exists(self):
        from uasset_read.parsers.asset_types.material_function import parse_material_function
        assert callable(parse_material_function)

    def test_material_parameter_collection_parser_exists(self):
        from uasset_read.parsers.asset_types.material_parameter_collection import parse_material_parameter_collection
        assert callable(parse_material_parameter_collection)


class TestAnimationTypes:
    """Test animation type mappings."""

    def test_anim_composite_resolves(self):
        assert resolve_asset_type("AnimComposite") == "anim_composite"

    def test_anim_blend_space_resolves(self):
        assert resolve_asset_type("AnimBlendSpace") == "anim_blend_space"

    def test_anim_blend_space_1d_resolves(self):
        assert resolve_asset_type("AnimBlendSpace1D") == "anim_blend_space"

    def test_aim_offset_blend_space_resolves(self):
        assert resolve_asset_type("AimOffsetBlendSpace") == "anim_blend_space"

    def test_aim_offset_blend_space_1d_resolves(self):
        assert resolve_asset_type("AimOffsetBlendSpace1D") == "anim_blend_space"

    def test_anim_composite_parser_exists(self):
        from uasset_read.parsers.asset_types.anim_composite import parse_anim_composite
        assert callable(parse_anim_composite)

    def test_anim_blend_space_parser_exists(self):
        from uasset_read.parsers.asset_types.anim_blend_space import parse_anim_blend_space
        assert callable(parse_anim_blend_space)


class TestSoundTypes:
    """Test sound type mappings."""

    def test_sound_concurrency_resolves(self):
        assert resolve_asset_type("SoundConcurrency") == "sound_concurrency"

    def test_reverb_effect_resolves(self):
        assert resolve_asset_type("ReverbEffect") == "reverb_effect"

    def test_dialogue_wave_resolves(self):
        assert resolve_asset_type("DialogueWave") == "dialogue_wave"

    def test_dialogue_voice_resolves(self):
        assert resolve_asset_type("DialogueVoice") == "dialogue_voice"

    def test_sound_concurrency_parser_exists(self):
        from uasset_read.parsers.asset_types.sound_concurrency import parse_sound_concurrency
        assert callable(parse_sound_concurrency)

    def test_reverb_effect_parser_exists(self):
        from uasset_read.parsers.asset_types.reverb_effect import parse_reverb_effect
        assert callable(parse_reverb_effect)

    def test_dialogue_wave_parser_exists(self):
        from uasset_read.parsers.asset_types.dialogue_wave import parse_dialogue_wave
        assert callable(parse_dialogue_wave)

    def test_dialogue_voice_parser_exists(self):
        from uasset_read.parsers.asset_types.dialogue_voice import parse_dialogue_voice
        assert callable(parse_dialogue_voice)


class TestCurveAndTextureTypes:
    """Test curve and texture type mappings."""

    def test_curve_linear_color_resolves_to_curve(self):
        assert resolve_asset_type("CurveLinearColor") == "curve"

    def test_curve_vector_resolves_to_curve(self):
        assert resolve_asset_type("CurveVector") == "curve"

    def test_texture_render_target_2d_resolves_to_texture(self):
        assert resolve_asset_type("TextureRenderTarget2D") == "texture"

    def test_texture_render_target_cube_resolves_to_texture(self):
        assert resolve_asset_type("TextureRenderTargetCube") == "texture"

    def test_curve_linear_color_parser_exists(self):
        from uasset_read.parsers.asset_types.curve_linear_color import parse_curve_linear_color
        assert callable(parse_curve_linear_color)

    def test_curve_vector_parser_exists(self):
        from uasset_read.parsers.asset_types.curve_vector import parse_curve_vector
        assert callable(parse_curve_vector)

    def test_texture_render_target_parser_exists(self):
        from uasset_read.parsers.asset_types.texture_render_target import parse_texture_render_target
        assert callable(parse_texture_render_target)


class TestPropertyMetadataHandlers:
    """Test PropertyMetadataHandler for new types."""

    def test_material_function_property_metadata(self):
        from uasset_read.parsers.asset_types.property_metadata import build_property_metadata

        class MockProp:
            def __init__(self, name, value):
                self.name = name
                self.value = value

        properties = [
            MockProp("Description", "Test function"),
            MockProp("UserExposedCaption", "Test Caption"),
            MockProp("bExposeToLibrary", True),
        ]
        result = build_property_metadata("MaterialFunction", properties)
        assert result["asset_type"] == "MaterialFunction"
        assert result["parse_status"] == "partial_metadata"

    def test_material_parameter_collection_property_metadata(self):
        from uasset_read.parsers.asset_types.property_metadata import build_property_metadata

        class MockProp:
            def __init__(self, name, value):
                self.name = name
                self.value = value

        properties = [
            MockProp("ScalarParameters", []),
            MockProp("VectorParameters", []),
        ]
        result = build_property_metadata("MaterialParameterCollection", properties)
        assert result["asset_type"] == "MaterialParameterCollection"

    def test_reverb_effect_property_metadata(self):
        from uasset_read.parsers.asset_types.property_metadata import build_property_metadata

        class MockProp:
            def __init__(self, name, value):
                self.name = name
                self.value = value

        properties = [
            MockProp("DecayTime", 1.5),
            MockProp("Density", 0.8),
            MockProp("Diffusion", 0.9),
        ]
        result = build_property_metadata("ReverbEffect", properties)
        assert result["asset_type"] == "ReverbEffect"


def test_all_parser_types_have_kinds_mapping():
    """Verify all registered parser types have kinds.py mappings."""
    from uasset_read.parsers.asset_types import register_asset_type_handlers
    from uasset_read.parsers.class_registry import get_class_registry

    # Reset and register all handlers
    registry = get_class_registry()
    registry._handlers.clear()
    register_asset_type_handlers()

    # Get all registered class names
    registered_classes = set()
    for handler in registry._handlers:
        if hasattr(handler, '_class_names'):
            registered_classes.update(handler._class_names)
        elif hasattr(handler, '_class_name'):
            registered_classes.add(handler._class_name)

    # Check each has a mapping
    unmapped = []
    for class_name in registered_classes:
        if resolve_asset_type(class_name) == "unknown":
            unmapped.append(class_name)

    assert unmapped == [], f"Classes without kinds.py mapping: {unmapped}"
