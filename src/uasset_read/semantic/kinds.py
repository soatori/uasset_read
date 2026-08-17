"""Asset type resolver — maps UE class names to normalized semantic type strings.

Each type string is a stable slug used as the common ``asset_type`` discriminator.
Exact UE class names are preserved only in debug evidence or when type is ``unknown``.

Mapping policy: only classes proven to appear as a primary export class in
tracked samples (tests/samples/) are mapped. Never guess mappings for classes
that are not evidenced — they must stay ``unknown``.
"""
from __future__ import annotations

_TYPE_MAP: dict[str, str] = {
    # Material
    "Material": "material",
    "MaterialInstance": "material",
    "MaterialInstanceConstant": "material",
    "MaterialInstanceDynamic": "material",
    "MaterialFunction": "material_function",
    "MaterialParameterCollection": "material_parameter_collection",
    # Sound
    "SoundCue": "sound_cue",
    "SoundWave": "sound_wave",
    "SoundAttenuation": "sound_attenuation",
    "SoundConcurrency": "sound_concurrency",
    "ReverbEffect": "reverb_effect",
    "DialogueWave": "dialogue_wave",
    "DialogueVoice": "dialogue_voice",
    # Niagara
    "NiagaraSystem": "niagara_system",
    "NiagaraEmitter": "niagara_emitter",
    "NiagaraScript": "niagara_script",
    # Mesh
    "StaticMesh": "static_mesh",
    "SkeletalMesh": "skeletal_mesh",
    "Skeleton": "skeleton",
    "SkeletalMeshLODSettings": "skeletal_mesh_lod_settings",
    # Animation
    "AnimSequence": "anim_sequence",
    "AnimMontage": "anim_montage",
    "PoseAsset": "pose_asset",
    "AnimCurveCompressionSettings": "anim_curve_compression_settings",
    "AnimCurveCompressionCodec": "anim_curve_compression_codec",
    "AnimBoneCompressionSettings": "anim_bone_compression_settings",
    "AnimationDataModel": "anim_data_model",
    "AnimComposite": "anim_composite",
    "AnimBlendSpace": "anim_blend_space",
    "AnimBlendSpace1D": "anim_blend_space",
    "AimOffsetBlendSpace": "anim_blend_space",
    "AimOffsetBlendSpace1D": "anim_blend_space",
    # Data
    "DataTable": "data_table",
    "CurveTable": "curve_table",
    "StringTable": "string_table",
    # Texture
    "Texture2D": "texture",
    "TextureCube": "texture",
    "TextureRenderTarget2D": "texture",
    "TextureRenderTargetCube": "texture",
    # Blueprint
    "BlueprintGeneratedClass": "blueprint",
    "AnimBlueprintGeneratedClass": "anim_blueprint",
    "Blueprint": "blueprint",
    "AnimBlueprint": "anim_blueprint",
    # User-defined data types
    "UserDefinedEnum": "enum",
    "UserDefinedStruct": "struct",
    # Rendering configuration
    "SubsurfaceProfile": "subsurface_profile",
    # Curves
    "CurveFloat": "curve",
    "CurveLinearColor": "curve",
    "CurveVector": "curve",
    # Foliage
    "FoliageType_InstancedStaticMesh": "foliage_type",
    "FoliageType": "foliage_type",
    # Builder
    "CubeBuilder": "cube_builder",
    # Physics
    "PhysicsAsset": "physics_asset",
    "PhysicalMaterial": "physical_material",
    # Animation (extended)
    "AnimLayerInterface": "anim_layer_interface",
    # Sound (extended)
    "SoundMix": "sound_mix",
    "SoundClass": "sound_class",
    "SoundSubmix": "sound_submix",
    # AI
    "BehaviorTree": "behavior_tree",
    "BlackboardData": "blackboard_data",
    # Data assets
    "DataAsset": "data_asset",
    "PrimaryDataAsset": "primary_data_asset",
    # Landscape
    "Landscape": "landscape",
    "LandscapeGrassType": "landscape_grass_type",
    "LandscapeLayerInfoObject": "landscape_layer_info",
    # World
    "World": "world",
    "Level": "level",
    # Particles
    "ParticleSystem": "particle_system",
    # UI
    "WidgetBlueprintGeneratedClass": "widget_blueprint",
    "WidgetBlueprint": "widget_blueprint",
    # Texture (extended)
    "Texture2DArray": "texture",
    "VolumeTexture": "texture",
    # Media
    "MediaPlayer": "media_player",
    "MediaTexture": "media_texture",
    "MediaSource": "media_source",
    # Cloth and Hair
    "ClothAsset": "cloth_asset",
    "GroomAsset": "groom_asset",
    # Sparse Volume Texture
    "SparseVolumeTexture": "sparse_volume_texture",
}


def resolve_asset_type(export_class: str) -> str:
    """Resolve a UE class name to a normalized semantic type string.

    Args:
        export_class: UE class name (e.g. "Material", "Texture2D")

    Returns:
        Normalized type string, or "unknown" if unresolvable.
    """
    if not export_class:
        return "unknown"
    return _TYPE_MAP.get(export_class, "unknown")
