"""Asset kind classifier — maps UE class names to semantic kinds.

Classification rules:
- GRAPH: Material, SoundCue, Niagara (node-based assets)
- STRUCTURED: StaticMesh, Skeleton, AnimSequence, DataTable (structured data)
- RESOURCE: Texture2D, SoundWave (binary resources with metadata)
- OPAQUE: Everything else (including Blueprint — handled by #554)
"""
from __future__ import annotations

from enum import Enum


class AssetKind(str, Enum):
    """Semantic asset kind."""
    GRAPH = "graph"
    STRUCTURED = "structured"
    RESOURCE = "resource"
    OPAQUE = "opaque"


# Classification lookup: UE class name → AssetKind
_CLASS_KIND_MAP: dict[str, AssetKind] = {
    # Graph domain
    "Material": AssetKind.GRAPH,
    "MaterialInstance": AssetKind.GRAPH,
    "MaterialInstanceConstant": AssetKind.GRAPH,
    "MaterialInstanceDynamic": AssetKind.GRAPH,
    "SoundCue": AssetKind.GRAPH,
    "NiagaraSystem": AssetKind.GRAPH,
    "NiagaraEmitter": AssetKind.GRAPH,
    "NiagaraScript": AssetKind.GRAPH,
    # Structured domain
    "StaticMesh": AssetKind.STRUCTURED,
    "SkeletalMesh": AssetKind.STRUCTURED,
    "Skeleton": AssetKind.STRUCTURED,
    "AnimSequence": AssetKind.STRUCTURED,
    "AnimMontage": AssetKind.STRUCTURED,
    "DataTable": AssetKind.STRUCTURED,
    "CurveTable": AssetKind.STRUCTURED,
    # Resource domain
    "Texture2D": AssetKind.RESOURCE,
    "TextureCube": AssetKind.RESOURCE,
    "SoundWave": AssetKind.RESOURCE,
}

# Classes explicitly excluded (Blueprint domain — #554)
_EXCLUDED_CLASSES = frozenset({
    "BlueprintGeneratedClass",
    "AnimBlueprintGeneratedClass",
})


def classify_asset(export_class: str, asset_type_data: dict | None = None) -> AssetKind:
    """Classify an export into a semantic asset kind.

    Args:
        export_class: UE class name (e.g. "Material", "StaticMesh")
        asset_type_data: Optional asset type data dict from ExportIR

    Returns:
        AssetKind enum value
    """
    if not export_class:
        return AssetKind.OPAQUE

    kind = _CLASS_KIND_MAP.get(export_class)
    if kind is not None:
        return kind

    # Blueprint classes → opaque (handled by #554)
    if export_class in _EXCLUDED_CLASSES:
        return AssetKind.OPAQUE

    return AssetKind.OPAQUE
