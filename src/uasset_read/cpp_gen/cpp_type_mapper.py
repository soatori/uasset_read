"""
UE 类型路径 → C++ 类型名映射模块。

提供 UE 资产路径（如 ScriptStruct'CoreUObject.Vector'）到 C++ 类型名（FVector）的转换。
Per D-03: 核心类型硬编码字典 + 可扩展脚本路径策略。

导出：
    UE_TO_CPP_TYPE_MAP: 核心类型映射字典
    ENGINE_CLASS_PATHS: Engine 类路径映射字典
    ue_path_to_cpp_type: UE 类型路径 → C++ 类型名转换函数
    ue_package_path_to_cpp_class: /Script/Engine.XXX → C++ 类名转换函数
    infer_class_prefix: 父类名 → C++ 前缀推断函数
    resolve_ue_type: 完整 UE 路径 → C++ 类型名解析函数
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
    "/Script/CoreUObject.Object": "UObject",
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
    "GameState", "GameStateBase", "PlayerState",
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

    # UE 编辑器元数据属性名 — 非真实 C++ 类型，作为 FString 处理
    if ue_type in ("Warning", "Info", "Details", "Category"):
        return "FString"

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
    # 基本类型直接返回（已在 UE_TO_CPP_TYPE_MAP 中）
    if lower_type in ("float", "double", "bool", "int", "int32", "int64",
                       "uint8", "uint16", "uint32", "uint64",
                       "byte", "char", "string", "fstring", "fname", "ftext",
                       "uobject", "uobject*", "fstring*"):
        return UE_TO_CPP_TYPE_MAP.get(lower_type, ue_type)

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
# 父类前缀推断
# ============================================================================

# 父类名前缀 → C++ 类型前缀映射
_PREFIX_MAP = {
    "A": "A",
    "U": "U",
    "F": "F",
    "E": "E",
    "I": "I",
}


def infer_class_prefix(parent_class: str) -> str:
    """
    根据父类名推断 C++ 类型前缀。

    规则：
    - 父类以 A 开头 → 返回 A（Actor 派生）
    - 父类以 U 开头 → 返回 U（UObject 派生）
    - 父类以 F 开头 → 返回 F（结构体）
    - 父类以 E 开头 → 返回 E（枚举）
    - 父类以 I 开头 → 返回 I（接口）
    - 默认返回 U

    Args:
        parent_class: 父类 C++ 类名（如 "ACharacter"、"USceneComponent"）

    Returns:
        C++ 类型前缀字符

    Examples:
        >>> infer_class_prefix("ACharacter")
        'A'
        >>> infer_class_prefix("USceneComponent")
        'U'
        >>> infer_class_prefix("FVector")
        'F'
        >>> infer_class_prefix("EDirection")
        'E'
        >>> infer_class_prefix("IInteractable")
        'I'
        >>> infer_class_prefix("Unknown")
        'U'
    """
    if not parent_class:
        return "U"

    first_char = parent_class[0]
    return _PREFIX_MAP.get(first_char, "U")


# ============================================================================
# UE 类型路径 → C++ 类型名解析
# ============================================================================

def resolve_ue_type(ue_path: str) -> str:
    """
    从完整 UE 路径解析出 C++ 类型名。

    支持的路径格式：
    - /Script/Engine.Actor → AActor
    - /Script/CoreUObject.Object → UObject
    - /Script/Engine.SceneComponent → USceneComponent
    - /Script/CoreUObject.Vector → FVector

    Args:
        ue_path: UE 完整类型路径（如 "/Script/Engine.Actor"）

    Returns:
        C++ 类型名字符串。如果无法解析，返回 UObject 作为安全默认值。

    Examples:
        >>> resolve_ue_type("/Script/Engine.Actor")
        'AActor'
        >>> resolve_ue_type("/Script/CoreUObject.Object")
        'UObject'
        >>> resolve_ue_type("/Script/Engine.Character")
        'ACharacter'
        >>> resolve_ue_type("/Script/Engine.SceneComponent")
        'USceneComponent'
        >>> resolve_ue_type("/Script/CoreUObject.Vector")
        'FVector'
    """
    if not ue_path:
        return "UObject"

    # 尝试精确匹配已知映射
    if ue_path in UE_TO_CPP_TYPE_MAP:
        return UE_TO_CPP_TYPE_MAP[ue_path]

    if ue_path in ENGINE_CLASS_PATHS:
        return ENGINE_CLASS_PATHS[ue_path]

    # 从路径提取类名部分
    # /Script/Engine.Actor → Actor, /Script/CoreUObject.Vector → Vector
    class_name = ue_path.rsplit(".", 1)[-1] if "." in ue_path else ue_path

    # 根据路径包推断前缀
    # CoreUObject 包下的类型通常是 F 前缀（结构体）
    if "/CoreUObject." in ue_path:
        return f"F{class_name}"

    # Engine 包下的类型需要进一步判断
    if "/Engine." in ue_path:
        # 尝试启发式
        return _apply_type_heuristic(ue_path)

    # 其他包默认使用 U 前缀
    return f"U{class_name}"


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "UE_TO_CPP_TYPE_MAP",
    "ENGINE_CLASS_PATHS",
    "ue_path_to_cpp_type",
    "ue_package_path_to_cpp_class",
    "infer_class_prefix",
    "resolve_ue_type",
]