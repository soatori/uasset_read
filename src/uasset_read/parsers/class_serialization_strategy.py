"""Class serialization strategy table -- maps UE class names to serialization strategies.

Complements class_specific_skip.py (property_parser level):
- This module intercepts early at linker.preload() level, avoiding entry into property parser
- class_specific_skip.py acts as a secondary safety net inside property_parser

Strategies:
- TAGGED_PROPERTIES_ONLY: parse only tagged properties (generic parser can handle)
- OPAQUE_CLASS_PAYLOAD: class-specific binary payload, no parsing attempted
- SKIP_UNSUPPORTED: completely unsupported, skip entirely

Note: FULL_SERIALIZER has been removed -- no actual handler implementations exist currently.
"""

from enum import Enum


class SerializationStrategy(str, Enum):
    """Serialization strategy enum."""
    # FULL_SERIALIZER removed -- no actual handler implementations exist
    # Tagged properties only (generic property parser can handle)
    TAGGED_PROPERTIES_ONLY = "tagged_properties_only"
    # Class-specific opaque payload (has custom Serialize() but not implemented)
    OPAQUE_CLASS_PAYLOAD = "opaque_class_payload"
    # Completely unsupported (format unknown or too risky)
    SKIP_UNSUPPORTED = "skip_unsupported"


# ========== Strategy mapping table ==========

# Tagged properties only — generic parser can handle
_TAGGED_PROPERTIES_CLASSES = frozenset({
    "BlueprintGeneratedClass",
    "WidgetBlueprintGeneratedClass",
    "Function",
    "UserDefinedStruct",
    "UserDefinedEnum",
    "EdGraph",
    "EdGraphNode",
    "K2Node",
    "AnimBlueprintGeneratedClass",
    # #320: ControlRig / RigVM blueprint-generated classes (containing tagged properties)
    "ControlRigBlueprintGeneratedClass",
    "RigVMBlueprintGeneratedClass",
    # MovieScene series classes (#317)
    "MovieScene",
    "MovieSceneControlRigParameterTrack",
    "MovieSceneControlRigParameterSection",
})

# Opaque class payload — has dedicated Serialize() but not implemented
_OPAQUE_CLASSES = frozenset({
    "CubeBuilder",
    "StaticMesh",
    "SkeletalMesh",
    "Texture2D",
    "TextureCube",
    "Material",
    "MaterialInstanceConstant",
    "AnimSequence",
    "AnimMontage",
    "SoundWave",
    "SoundCue",
    "ParticleSystem",
    "NiagaraSystem",
    # #521: migrated from _SKIP_CLASSES for field-level parsing
    "NiagaraGraph",
    "NiagaraScript",
    # #164: MovieScene/Sequencer classes (MovieScene/ControlRig migrated to TAGGED_PROPERTIES_ONLY)
    "MovieSceneBuiltInEasingFunction",
    # #320: ControlRig / RigVM serialization classes (custom Serialize())
    "ControlRig",
    "RigHierarchy",
    "RigVM",
    "RigVMHost",
    "RigVMScript",
    "RigVMFunction",
    "RigVMClosure",
    "RigVMBlueprint",
    "RigVMController",
    "RigVMGraph",
    "RigVMNode",
    "RigVMLink",
    "RigVMVariable",
    "RigVMParameter",
    "RigVMOperand",
    "RigVMStruct",
    "RigVMUserWorkflowOptions",
    "RigVMEditorSettings",
    # #165: MetaSound editor metadata classes
    "MetasoundEditorGraphMemberDefaultBool",
    "MetasoundEditorGraphMemberDefaultInt",
    "MetasoundEditorGraphMemberDefaultFloat",
    "MetasoundEditorGraphMemberDefaultString",
    "MetasoundEditorGraphMemberDefaultLiteral",
    "MetasoundEditorGraphMemberDefaultObjectArray",
    # Pure UPROPERTY classes that the current parser cannot fully parse
    "FoliageType",
    "SkeletalMeshLODSettings",
})

# Skip entirely — format unknown or too risky
_SKIP_CLASSES = frozenset({
    "NiagaraDataInterface",
    # Migrated from class_specific_skip.py SKIP_CLASS_NAMES (eliminates strategy conflict)
    "NiagaraScriptSource",
    "NiagaraDataInterfaceExport",
    "NiagaraDataInterfaceGrid2D",
    "NiagaraDataInterfaceGrid3D",
    "NiagaraDataInterfaceSkeletalMesh",
    "NiagaraDataInterfaceTexture",
    "NiagaraDataInterfaceComponentRenderer",
    "NiagaraDataInterfaceAudioSubmix",
    "NiagaraDataInterfaceCurlNoise",
    "NiagaraDataInterfaceRenderTarget2D",
    "NiagaraDataInterfaceSkeletalMeshSlice",
    "NiagaraDataInterfaceStaticMesh",
    "NiagaraDataInterfaceRwGrid2D",
    "NiagaraDataInterfaceRwGrid3D",
    "NiagaraDataInterfaceNeighborGrid3D",
    "NiagaraDataInterfaceLandscape",
    "NiagaraDataInterfaceOcclusion",
    "NiagaraDataInterfaceParticleRead",
    "NiagaraDataInterfaceDebugColor",
    "NiagaraDataInterfaceGpuReadback",
    "NiagaraDataInterfaceAudio",
    "NiagaraDataInterfaceMediaTexture",
    "NiagaraDataInterfaceVideo",
    "NiagaraDataInterfaceVirtualTexture",
    "NiagaraDataInterfaceSparseVolumeTexture",
    "AnimBlueprintExtension",
    "AnimComposite",
    "AnimPoseSnapshot",
    "ImpulseResponse",
    "SoundConcurrency",
    "SoundMix",
    "SoundClass",
    "ReverbEffect",
    "AmbientSound",
    # Migrated from class_specific_skip.py SKIP_CLASS_NAMES (eliminates strategy conflict #6)
    "NiagaraEmitter",
    "NiagaraSpriteRendererProperties",
    "NiagaraMeshRendererProperties",
    "NiagaraRibbonRendererProperties",
    "NiagaraRendererProperties",
    "NiagaraEmitterProperties",
})

CLASS_STRATEGY_TABLE: dict[str, SerializationStrategy] = {
    cls: SerializationStrategy.TAGGED_PROPERTIES_ONLY
    for cls in _TAGGED_PROPERTIES_CLASSES
} | {
    cls: SerializationStrategy.OPAQUE_CLASS_PAYLOAD
    for cls in _OPAQUE_CLASSES
} | {
    cls: SerializationStrategy.SKIP_UNSUPPORTED
    for cls in _SKIP_CLASSES
}


def get_serialization_strategy(class_name: str) -> SerializationStrategy:
    """Get the serialization strategy for a given class (supports exact name and prefix matching).

    Lookup order:
    1. CLASS_STRATEGY_TABLE Exact name match
    2. Prefix matching from class_specific_skip module (SKIP_CLASS_PREFIXES)
    3. Default TAGGED_PROPERTIES_ONLY

    Args:
        class_name: UE class name (e.g. "StaticMesh")

    Returns:
        SerializationStrategy enum value
    """
    # Exact name match
    if class_name in CLASS_STRATEGY_TABLE:
        return CLASS_STRATEGY_TABLE[class_name]

    # Prefix match: from class_specific_skip module
    from uasset_read.parsers.class_specific_skip import should_skip_export_class_prefix
    if should_skip_export_class_prefix(class_name):
        return SerializationStrategy.SKIP_UNSUPPORTED

    return SerializationStrategy.TAGGED_PROPERTIES_ONLY


def should_skip_class(class_name: str) -> bool:
    """Determine whether this class should be skipped entirely (no parsing attempted).

    Args:
        class_name: UE class name

    Returns:
        True if the class should be skipped (SKIP_UNSUPPORTED)
    """
    return (
        get_serialization_strategy(class_name)
        == SerializationStrategy.SKIP_UNSUPPORTED
    )


def is_opaque_class(class_name: str) -> bool:
    """Determine whether this class is an opaque payload (has dedicated Serialize() but not implemented).

    Args:
        class_name: UE class name

    Returns:
        True if the class is opaque
    """
    return (
        get_serialization_strategy(class_name)
        == SerializationStrategy.OPAQUE_CLASS_PAYLOAD
    )
