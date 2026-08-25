"""
UE type path -> C++ type name mapping module.

Provides conversion from UE asset paths (e.g. ScriptStruct'CoreUObject.Vector') to C++ type names (FVector).
Per D-03: Hardcoded core type dictionary + extensible script path strategy.

Exports:
    UE_TO_CPP_TYPE_MAP: Core type mapping dictionary
    ENGINE_CLASS_PATHS: Engine class path mapping dictionary
    ue_path_to_cpp_type: UE type path -> C++ type name conversion function
    ue_package_path_to_cpp_class: /Script/Engine.XXX -> C++ class name conversion function
    infer_class_prefix: Parent class name -> C++ prefix inference function
    resolve_ue_type: Full UE path -> C++ type name resolution function
"""

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

# ============================================================================
# UE type path -> C++ type name mapping
# D-03: Hardcoded core type dictionary
# ============================================================================

UE_TO_CPP_TYPE_MAP: Dict[str, str] = {
    # ScriptStruct types (F prefix)
    "/Script/CoreUObject.Vector": "FVector",
    "/Script/CoreUObject.Rotator": "FRotator",
    "/Script/CoreUObject.Transform": "FTransform",
    "/Script/CoreUObject.Vector2D": "FVector2D",
    "/Script/CoreUObject.LinearColor": "FLinearColor",
    "/Script/CoreUObject.Name": "FName",
    "/Script/CoreUObject.Text": "FText",
    "/Script/CoreUObject.String": "FString",
    "/Script/CoreUObject.Guid": "FGuid",
    "/Script/CoreUObject.Box": "FBox",
    "/Script/CoreUObject.Box2D": "FBox2D",
    "/Script/CoreUObject.Plane": "FPlane",
    "/Script/CoreUObject.Quat": "FQuat",
    "/Script/CoreUObject.RandomStream": "FRandomStream",
    "/Script/CoreUObject.DateTime": "FDateTime",
    "/Script/CoreUObject.Timespan": "FTimespan",
    "/Script/CoreUObject.Color": "FColor",
    "/Script/CoreUObject.Object": "UObject",
    "/Script/Engine.HitResult": "FHitResult",
    "/Script/Engine.TimerHandle": "FTimerHandle",
    "/Script/Engine.ActorReference": "FActorReference",
    "/Script/Engine.LevelReference": "FLevelReference",
    "/Script/Engine.InputActionKeyMapping": "FInputActionKeyMapping",
    "/Script/Engine.InputAxisKeyMapping": "FInputAxisKeyMapping",
    "/Script/Engine.GameplayTag": "FGameplayTag",
    "/Script/Engine.GameplayTagContainer": "FGameplayTagContainer",

    # Class types (A prefix for Actor, U prefix for UObject/Component)
    "/Script/Engine.SceneComponent": "USceneComponent",
    "/Script/Engine.ActorComponent": "UActorComponent",
    "/Script/Engine.Character": "ACharacter",
    "/Script/Engine.Pawn": "APawn",
    "/Script/Engine.Actor": "AActor",
    "/Script/Engine.GameModeBase": "AGameModeBase",
    "/Script/Engine.GameMode": "AGameMode",
    "/Script/Engine.GameStateBase": "AGameStateBase",
    "/Script/Engine.PlayerController": "APlayerController",
    "/Script/Engine.PlayerState": "APlayerState",
    "/Script/Engine.Controller": "AController",
    "/Script/Engine.HUD": "AHUD",
    "/Script/Engine.PlayerCameraManager": "APlayerCameraManager",
    "/Script/Engine.CameraActor": "ACameraActor",
    "/Script/Engine.Light": "ALight",
    "/Script/Engine.CameraComponent": "UCameraComponent",
    "/Script/Engine.SpringArmComponent": "USpringArmComponent",
    "/Script/Engine.StaticMeshComponent": "UStaticMeshComponent",
    "/Script/Engine.SkeletalMeshComponent": "USkeletalMeshComponent",
    "/Script/Engine.BoxComponent": "UBoxComponent",
    "/Script/Engine.SphereComponent": "USphereComponent",
    "/Script/Engine.CapsuleComponent": "UCapsuleComponent",
    "/Script/Engine.AudioComponent": "UAudioComponent",
    "/Script/Engine.LightComponent": "ULightComponent",
    "/Script/Engine.ParticleSystemComponent": "UParticleSystemComponent",
    "/Script/Engine.MovementComponent": "UMovementComponent",
    "/Script/Engine.CharacterMovementComponent": "UCharacterMovementComponent",
    "/Script/Engine.WidgetComponent": "UWidgetComponent",
    "/Script/Engine.LightComponentBase": "ULightComponentBase",
    "/Script/Engine.DirectionalLightComponent": "UDirectionalLightComponent",
    "/Script/Engine.PointLightComponent": "UPointLightComponent",
    "/Script/Engine.SpotLightComponent": "USpotLightComponent",
    "/Script/Engine.SkyLightComponent": "USkyLightComponent",
    "/Script/Engine.PawnMovementComponent": "UPawnMovementComponent",
    "/Script/UMG.Widget": "UWidget",
    "/Script/UMG.UserWidget": "UUserWidget",
    "/Script/UMG.Button": "UButton",
    "/Script/UMG.TextBlock": "UTextBlock",
    "/Script/UMG.CanvasPanel": "UCanvasPanel",
    "/Script/UMG.GridPanel": "UGridPanel",
    "/Script/UMG.HorizontalBox": "UHorizontalBox",
    "/Script/UMG.VerticalBox": "UVerticalBox",
    "/Script/UMG.Image": "UImage",
    "/Script/UMG.Slider": "USlider",
    "/Script/UMG.CheckBox": "UCheckBox",
    "/Script/UMG.ComboBox": "UComboBox",
    "/Script/UMG.EditTextBox": "UEditTextBox",
    "/Script/UMG.ProgressBar": "UProgressBar",
    "/Script/UMG.Spacer": "USpacer",

    # Basic types (no prefix or UE-specific wrappers)
    "float": "float",
    "double": "double",
    "bool": "bool",
    "int": "int32",
    "int32": "int32",
    "int64": "int64",
    "uint8": "uint8",
    "uint16": "uint16",
    "uint32": "uint32",
    "uint64": "uint64",
    "byte": "uint8",
    "char": "char",
    "name": "FName",
    "text": "FText",
    "string": "FString",
    "fstring": "FString",
    "fname": "FName",
    "ftext": "FText",
    "vector": "FVector",
    "rotator": "FRotator",
    "transform": "FTransform",
    "linearcolor": "FLinearColor",
    "color": "FColor",
    "guid": "FGuid",
    "uobject": "UObject",
    "uobject*": "UObject*",
    "fstring*": "FString*",
}

# ============================================================================
# Engine class path mapping (supports D-02 inheritance chain resolution)
# /Script/Engine.XXX -> AXXX/UXXX/FXXX
# ============================================================================

ENGINE_CLASS_PATHS: Dict[str, str] = {
    # Actors (A prefix)
    "/Script/Engine.Actor": "AActor",
    "/Script/Engine.Pawn": "APawn",
    "/Script/Engine.Character": "ACharacter",
    "/Script/Engine.Controller": "AController",
    "/Script/Engine.PlayerController": "APlayerController",
    "/Script/Engine.PlayerState": "APlayerState",
    "/Script/Engine.GameModeBase": "AGameModeBase",
    "/Script/Engine.GameMode": "AGameMode",
    "/Script/Engine.GameStateBase": "AGameStateBase",
    "/Script/Engine.HUD": "AHUD",
    "/Script/Engine.PlayerCameraManager": "APlayerCameraManager",
    "/Script/Engine.LevelScriptActor": "ALevelScriptActor",
    "/Script/Engine.Volume": "AVolume",
    "/Script/Engine.Brush": "ABrush",
    "/Script/Engine.Light": "ALight",
    "/Script/Engine.DirectionalLight": "ADirectionalLight",
    "/Script/Engine.PointLight": "APointLight",
    "/Script/Engine.SpotLight": "ASpotLight",
    "/Script/Engine.CameraActor": "ACameraActor",
    "/Script/Engine.PlayerStart": "APlayerStart",
    "/Script/Engine.TriggerVolume": "ATriggerVolume",

    # Components (U prefix)
    "/Script/Engine.ActorComponent": "UActorComponent",
    "/Script/Engine.SceneComponent": "USceneComponent",
    "/Script/Engine.PrimitiveComponent": "UPrimitiveComponent",
    "/Script/Engine.MeshComponent": "UMeshComponent",
    "/Script/Engine.StaticMeshComponent": "UStaticMeshComponent",
    "/Script/Engine.SkeletalMeshComponent": "USkeletalMeshComponent",
    "/Script/Engine.CameraComponent": "UCameraComponent",
    "/Script/Engine.SpringArmComponent": "USpringArmComponent",
    "/Script/Engine.AudioComponent": "UAudioComponent",
    "/Script/Engine.LightComponent": "ULightComponent",
    "/Script/Engine.ParticleSystemComponent": "UParticleSystemComponent",
    "/Script/Engine.MovementComponent": "UMovementComponent",
    "/Script/Engine.CharacterMovementComponent": "UCharacterMovementComponent",
    "/Script/Engine.PawnMovementComponent": "UPawnMovementComponent",
    "/Script/Engine.NavMovementComponent": "UNavMovementComponent",
    "/Script/Engine.WidgetComponent": "UWidgetComponent",
    "/Script/Engine.LightComponentBase": "ULightComponentBase",
    "/Script/Engine.DirectionalLightComponent": "UDirectionalLightComponent",
    "/Script/Engine.PointLightComponent": "UPointLightComponent",
    "/Script/Engine.SpotLightComponent": "USpotLightComponent",
    "/Script/Engine.SkyLightComponent": "USkyLightComponent",
    "/Script/Engine.BillboardComponent": "UBillboardComponent",
    "/Script/Engine.ArrowComponent": "UArrowComponent",
    "/Script/Engine.BoxComponent": "UBoxComponent",
    "/Script/Engine.SphereComponent": "USphereComponent",
    "/Script/Engine.CapsuleComponent": "UCapsuleComponent",

    # UObjects (U prefix)
    "/Script/Engine.Object": "UObject",
    "/Script/Engine.Blueprint": "UBlueprint",
    "/Script/Engine.BlueprintGeneratedClass": "UBlueprintGeneratedClass",
    "/Script/Engine.Asset": "UAsset",
    "/Script/Engine.DataAsset": "UDataAsset",
    "/Script/Engine.PrimaryDataAsset": "UPrimaryDataAsset",
    "/Script/Engine.Texture": "UTexture",
    "/Script/Engine.Texture2D": "UTexture2D",
    "/Script/Engine.Material": "UMaterial",
    "/Script/Engine.MaterialInstance": "UMaterialInstance",
    "/Script/Engine.StaticMesh": "UStaticMesh",
    "/Script/Engine.SkeletalMesh": "USkeletalMesh",
    "/Script/Engine.AnimSequence": "UAnimSequence",
    "/Script/Engine.AnimMontage": "UAnimMontage",
    "/Script/Engine.SoundWave": "USoundWave",
    "/Script/Engine.ParticleSystem": "UParticleSystem",
}

# Actor class suffix set (used for heuristic prefix inference)
ACTOR_SUFFIXES = frozenset({
    "Actor", "Pawn", "Character", "Controller", "GameMode", "GameModeBase",
    "GameState", "GameStateBase", "PlayerState",
    "HUD", "Manager", "Volume", "Brush", "Light", "Camera", "PlayerStart",
    "Trigger", "Zone",
})

# Component class suffix set
COMPONENT_SUFFIXES = frozenset({
    "Component", "Subcomponent",
})


def ue_path_to_cpp_type(ue_type: str) -> str:
    """
    Convert UE type path to C++ type name.

    Supported input formats:
    1. Reference format: "ScriptStruct'CoreUObject.Vector'"
    2. Path format: "/Script/CoreUObject.Vector"
    3. Basic types: "float", "bool", "name", "text"

    Args:
        ue_type: UE type string

    Returns:
        C++ type name string. Returns input value and logs warning if unrecognized.

    Examples:
        >>> ue_path_to_cpp_type("ScriptStruct'CoreUObject.Vector'")
        'FVector'
        >>> ue_path_to_cpp_type("/Script/CoreUObject.Vector")
        'FVector'
        >>> ue_path_to_cpp_type("float")
        'float'
        >>> ue_path_to_cpp_type("Class'Engine.SceneComponent'")
        'USceneComponent'
    """
    if not ue_type:
        logger.warning("Empty UE type path provided")
        return ue_type

    # 1. Try exact match
    if ue_type in UE_TO_CPP_TYPE_MAP:
        return UE_TO_CPP_TYPE_MAP[ue_type]

    # UE editor metadata property names -- not real C++ types, treated as FString
    if ue_type in ("Warning", "Info", "Details", "Category"):
        return "FString"

    # 2. Handle reference format (ScriptStruct'...' or Class'...')
    # Format: Type'SubPath.Name' or Type'/Script/Package.Name'
    match = re.match(r"^(ScriptStruct|Class|Enum|Interface)'(.+)'$", ue_type)
    if match:
        inner = match.group(2)
        # Try to build full path
        # Format may be "CoreUObject.Vector" or "/Script/CoreUObject.Vector"
        if not inner.startswith("/"):
            # Simplified path: "CoreUObject.Vector" -> "/Script/CoreUObject.Vector"
            # Assume simplified ScriptStruct paths are under CoreUObject package
            inner = f"/Script/{inner}"

        # Try to match
        if inner in UE_TO_CPP_TYPE_MAP:
            return UE_TO_CPP_TYPE_MAP[inner]

        # Try processing as full path again
        return _apply_type_heuristic(inner)

    # 3. Handle path format /Script/Package.Name
    if ue_type.startswith("/Script/"):
        if ue_type in UE_TO_CPP_TYPE_MAP:
            return UE_TO_CPP_TYPE_MAP[ue_type]
        # World Partition hashed path normalization (e.g. /Script/Engine_3103784960 -> /Script/Engine)
        from uasset_read.link.linker import normalize_world_partition_path
        normalized = normalize_world_partition_path(ue_type)
        if normalized != ue_type and normalized in UE_TO_CPP_TYPE_MAP:
            return UE_TO_CPP_TYPE_MAP[normalized]
        return _apply_type_heuristic(ue_type)

    # 4. Simple type name (may be a basic or known type)
    # Try lowercase matching ("vector" -> "FVector")
    lower_type = ue_type.lower()
    if lower_type in ("vector",):
        return "FVector"
    if lower_type in ("rotator",):
        return "FRotator"
    if lower_type in ("transform",):
        return "FTransform"
    if lower_type in ("linearcolor",):
        return "FLinearColor"
    if lower_type in ("color",):
        return "FColor"
    if lower_type in ("guid",):
        return "FGuid"
    # Basic types returned directly (already in UE_TO_CPP_TYPE_MAP)
    if lower_type in ("float", "double", "bool", "int", "int32", "int64",
                       "uint8", "uint16", "uint32", "uint64",
                       "byte", "char", "string", "fstring", "fname", "ftext",
                       "uobject", "uobject*", "fstring*"):
        return UE_TO_CPP_TYPE_MAP.get(lower_type, ue_type)

    # 5. Unknown type -- apply heuristic
    logger.warning(f"Unknown UE type path: '{ue_type}', returning as-is")
    return ue_type


def _apply_type_heuristic(path: str) -> str:
    """
    Apply heuristic prefix inference for unknown type paths.

    Rules:
    - Actor suffix -> A prefix
    - Component suffix -> U prefix
    - ScriptStruct -> F prefix (struct)
    - Enum -> E prefix
    - Interface -> I prefix
    - Default -> U prefix (UObject)

    Args:
        path: UE type path (e.g. /Script/Engine.MyCustomActor)

    Returns:
        Inferred C++ type name
    """
    # Extract class name portion
    if "/" in path:
        class_name = path.rsplit(".", 1)[-1]
    else:
        class_name = path

    # Check if in known mappings
    if path in ENGINE_CLASS_PATHS:
        return ENGINE_CLASS_PATHS[path]
    if path in UE_TO_CPP_TYPE_MAP:
        return UE_TO_CPP_TYPE_MAP[path]

    # Heuristic prefix inference
    # Actor suffix
    for suffix in ACTOR_SUFFIXES:
        if class_name.endswith(suffix):
            return f"A{class_name}"

    # Component suffix
    for suffix in COMPONENT_SUFFIXES:
        if class_name.endswith(suffix):
            return f"U{class_name}"

    # Default: U prefix (UObject)
    return f"U{class_name}"


def ue_package_path_to_cpp_class(package_path: str) -> str:
    """
    Convert UE package path to C++ class name.

    Primarily used for D-02 inheritance chain resolution.

    Args:
        package_path: UE package path (e.g. "/Script/Engine.Character")

    Returns:
        C++ class name string

    Examples:
        >>> ue_package_path_to_cpp_class("/Script/Engine.Character")
        'ACharacter'
        >>> ue_package_path_to_cpp_class("/Script/Engine.SceneComponent")
        'USceneComponent'
    """
    if not package_path:
        logger.warning("Empty package path provided")
        return ""

    # 1. Try exact match
    if package_path in ENGINE_CLASS_PATHS:
        return ENGINE_CLASS_PATHS[package_path]

    # 2. Try UE_TO_CPP_TYPE_MAP
    if package_path in UE_TO_CPP_TYPE_MAP:
        return UE_TO_CPP_TYPE_MAP[package_path]

    # 3. Apply heuristic
    return _apply_type_heuristic(package_path)


# ============================================================================
# Export list
# ============================================================================

__all__ = [
    "UE_TO_CPP_TYPE_MAP",
    "ENGINE_CLASS_PATHS",
    "ue_path_to_cpp_type",
    "ue_package_path_to_cpp_class",
]