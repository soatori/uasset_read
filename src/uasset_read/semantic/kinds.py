"""Asset type resolver — maps UE class names to normalized semantic type strings.

Each type string is a stable slug used as the common ``asset_type`` discriminator.
Exact UE class names are preserved only in debug evidence or when type is ``unknown``.
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
    # Niagara
    "NiagaraSystem": "niagara_system",
    "NiagaraEmitter": "niagara_emitter",
    "NiagaraScript": "niagara_script",
    # Mesh
    "StaticMesh": "static_mesh",
    "SkeletalMesh": "skeletal_mesh",
    "Skeleton": "skeleton",
    # Animation
    "AnimSequence": "anim_sequence",
    "AnimMontage": "anim_montage",
    # Data
    "DataTable": "data_table",
    "CurveTable": "curve_table",
    # Texture
    "Texture2D": "texture",
    "TextureCube": "texture",
    # Blueprint
    "BlueprintGeneratedClass": "blueprint",
    "AnimBlueprintGeneratedClass": "anim_blueprint",
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
