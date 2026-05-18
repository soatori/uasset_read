"""
UE 类型路径 → C++ 类型名映射模块。

提供 UE 资产路径（如 ScriptStruct'CoreUObject.Vector'）到 C++ 类型名（FVector）的转换。
Per D-03: 核心类型硬编码字典 + 可扩展脚本路径策略。

导出：
    UE_TO_CPP_TYPE_MAP: 核心类型映射字典
    ENGINE_CLASS_PATHS: Engine 类路径映射字典
    ue_path_to_cpp_type: UE 类型路径 → C++ 类型名转换函数
    ue_package_path_to_cpp_class: /Script/Engine.XXX → C++ 类名转换函数
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# UE 类型路径 → C++ 类型名映射
# D-03: 核心类型硬编码字典
# ============================================================================

UE_TO_CPP_TYPE_MAP: Dict[str, str] = {
    # ScriptStruct 类型（F 前缀）
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
    "/Script/Engine.HitResult": "FHitResult",
    "/Script/Engine.TimerHandle": "FTimerHandle",
    "/Script/Engine.ActorReference": "FActorReference",
    "/Script/Engine.LevelReference": "FLevelReference",
    "/Script/Engine.InputActionKeyMapping": "FInputActionKeyMapping",
    "/Script/Engine.InputAxisKeyMapping": "FInputAxisKeyMapping",
    "/Script/Engine.GameplayTag": "FGameplayTag",
    "/Script/Engine.GameplayTagContainer": "FGameplayTagContainer",

    # Class 类型（A 前缀 Actor，U 前缀 UObject/Component）
    "/Script/Engine.SceneComponent": "USceneComponent",
    "/Script/Engine.ActorComponent": "UActorComponent",
    "/Script/Engine.Character": "ACharacter",
    "/Script/Engine.Pawn": "APawn",
    "/Script/Engine.Actor": "AActor",
    "/Script/Engine.GameModeBase": "AGameModeBase",
    "/Script/Engine.GameMode": "AGameMode",
    "/Script/Engine.PlayerController": "APlayerController",
    "/Script/Engine.Controller": "AController",
    "/Script/Engine.HUD": "AHUD",
    "/Script/Engine.PlayerCameraManager": "APlayerCameraManager",
    "/Script/Engine.CameraComponent": "UCameraComponent",
    "/Script/Engine.SpringArmComponent": "USpringArmComponent",
    "/Script/Engine.StaticMeshComponent": "UStaticMeshComponent",
    "/Script/Engine.SkeletalMeshComponent": "USkeletalMeshComponent",
    "/Script/Engine.AudioComponent": "UAudioComponent",
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

    # 基本类型（无前缀或 UE 特定包装）
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
    "vector": "FVector",
    "rotator": "FRotator",
    "transform": "FTransform",
    "linearcolor": "FLinearColor",
    "color": "FColor",
    "guid": "FGuid",
}

# ============================================================================
# Engine 类路径映射（支持 D-02 继承链解析）
# /Script/Engine.XXX → AXXX/UXXX/FXXX
# ============================================================================

ENGINE_CLASS_PATHS: Dict[str, str] = {
    # Actors (A 前缀)
    "/Script/Engine.Actor": "AActor",
    "/Script/Engine.Pawn": "APawn",
    "/Script/Engine.Character": "ACharacter",
    "/Script/Engine.Controller": "AController",
    "/Script/Engine.PlayerController": "APlayerController",
    "/Script/Engine.GameModeBase": "AGameModeBase",
    "/Script/Engine.GameMode": "AGameMode",
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

    # Components (U 前缀)
    "/Script/Engine.ActorComponent": "UActorComponent",
    "/Script/Engine.SceneComponent": "USceneComponent",
    "/Script/Engine.PrimitiveComponent": "UPrimitiveComponent",
    "/Script/Engine.MeshComponent": "UMeshComponent",
    "/Script/Engine.StaticMeshComponent": "UStaticMeshComponent",
    "/Script/Engine.SkeletalMeshComponent": "USkeletalMeshComponent",
    "/Script/Engine.CameraComponent": "UCameraComponent",
    "/Script/Engine.SpringArmComponent": "USpringArmComponent",
    "/Script/Engine.AudioComponent": "UAudioComponent",
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

    # UObjects (U 前缀)
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

# Actor 类后缀集合（用于启发式前缀判断）
ACTOR_SUFFIXES = frozenset({
    "Actor", "Pawn", "Character", "Controller", "GameMode", "GameModeBase",
    "HUD", "Manager", "Volume", "Brush", "Light", "Camera", "PlayerStart",
    "Trigger", "Zone",
})

# Component 类后缀集合
COMPONENT_SUFFIXES = frozenset({
    "Component", "Subcomponent",
})


def ue_path_to_cpp_type(ue_type: str) -> str:
    """
    将 UE 类型路径转换为 C++ 类型名。

    支持的输入格式：
    1. 引用格式: "ScriptStruct'CoreUObject.Vector'"
    2. 路径格式: "/Script/CoreUObject.Vector"
    3. 基本类型: "float", "bool", "name", "text"

    Args:
        ue_type: UE 类型字符串

    Returns:
        C++ 类型名字符串。如果无法识别，返回输入值并记录警告日志。

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

    # 1. 尝试精确匹配
    if ue_type in UE_TO_CPP_TYPE_MAP:
        return UE_TO_CPP_TYPE_MAP[ue_type]

    # 2. 处理引用格式 (ScriptStruct'...' 或 Class'...')
    # 格式: Type'SubPath.Name' 或 Type'/Script/Package.Name'
    match = re.match(r"^(ScriptStruct|Class|Enum|Interface)'(.+)'$", ue_type)
    if match:
        inner = match.group(2)
        # 尝试构建完整路径
        # 格式可能是 "CoreUObject.Vector" 或 "/Script/CoreUObject.Vector"
        if not inner.startswith("/"):
            # 简化路径: "CoreUObject.Vector" → "/Script/CoreUObject.Vector"
            # 假设简化的 ScriptStruct 路径在 CoreUObject 包下
            inner = f"/Script/{inner}"

        # 尝试匹配
        if inner in UE_TO_CPP_TYPE_MAP:
            return UE_TO_CPP_TYPE_MAP[inner]

        # 尝试作为完整路径再次处理
        return _apply_type_heuristic(inner)

    # 3. 处理路径格式 /Script/Package.Name
    if ue_type.startswith("/Script/"):
        if ue_type in UE_TO_CPP_TYPE_MAP:
            return UE_TO_CPP_TYPE_MAP[ue_type]
        return _apply_type_heuristic(ue_type)

    # 4. 简单类型名（可能是基本类型或已知类型）
    # 尝试小写匹配（"vector" → "FVector"）
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

    # 5. 未知类型 - 应用启发式
    logger.warning(f"Unknown UE type path: '{ue_type}', returning as-is")
    return ue_type


def _apply_type_heuristic(path: str) -> str:
    """
    对未知类型路径应用启发式前缀判断。

    规则：
    - Actor 后缀 → A 前缀
    - Component 后缀 → U 前缀
    - ScriptStruct → F 前缀（结构体）
    - Enum → E 前缀
    - Interface → I 前缀
    - 默认 → U 前缀（UObject）

    Args:
        path: UE 类型路径（如 /Script/Engine.MyCustomActor）

    Returns:
        推断的 C++ 类型名
    """
    # 提取类名部分
    if "/" in path:
        class_name = path.rsplit(".", 1)[-1]
    else:
        class_name = path

    # 检查是否在已知映射中
    if path in ENGINE_CLASS_PATHS:
        return ENGINE_CLASS_PATHS[path]
    if path in UE_TO_CPP_TYPE_MAP:
        return UE_TO_CPP_TYPE_MAP[path]

    # 启发式前缀判断
    # Actor 后缀
    for suffix in ACTOR_SUFFIXES:
        if class_name.endswith(suffix):
            return f"A{class_name}"

    # Component 后缀
    for suffix in COMPONENT_SUFFIXES:
        if class_name.endswith(suffix):
            return f"U{class_name}"

    # 默认：U 前缀（UObject）
    return f"U{class_name}"


def ue_package_path_to_cpp_class(package_path: str) -> str:
    """
    将 UE 包路径转换为 C++ 类名。

    主要用于 D-02 继承链解析。

    Args:
        package_path: UE 包路径（如 "/Script/Engine.Character"）

    Returns:
        C++ 类名字符串

    Examples:
        >>> ue_package_path_to_cpp_class("/Script/Engine.Character")
        'ACharacter'
        >>> ue_package_path_to_cpp_class("/Script/Engine.SceneComponent")
        'USceneComponent'
    """
    if not package_path:
        logger.warning("Empty package path provided")
        return ""

    # 1. 尝试精确匹配
    if package_path in ENGINE_CLASS_PATHS:
        return ENGINE_CLASS_PATHS[package_path]

    # 2. 尝试 UE_TO_CPP_TYPE_MAP
    if package_path in UE_TO_CPP_TYPE_MAP:
        return UE_TO_CPP_TYPE_MAP[package_path]

    # 3. 应用启发式
    return _apply_type_heuristic(package_path)


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "UE_TO_CPP_TYPE_MAP",
    "ENGINE_CLASS_PATHS",
    "ue_path_to_cpp_type",
    "ue_package_path_to_cpp_class",
]