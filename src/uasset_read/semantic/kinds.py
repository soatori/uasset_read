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
    # Sound
    "SoundCue": "sound_cue",
    "SoundWave": "sound_wave",
    "SoundAttenuation": "sound_attenuation",
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
    # Data
    "DataTable": "data_table",
    "CurveTable": "curve_table",
    # Texture
    "Texture2D": "texture",
    "TextureCube": "texture",
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
    # Foliage
    "FoliageType_InstancedStaticMesh": "foliage_type",
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
