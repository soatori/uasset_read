"""类序列化策略表 — 按 UE class 名称映射序列化策略。

与 class_specific_skip.py（property_parser 层级）互补：
- 本模块在 linker.preload() 层级提前拦截，避免进入 property parser
- class_specific_skip.py 在 property_parser 内部作为二次安全网

策略定义：
- FULL_SERIALIZER: 完整支持该类专用 Serialize()（暂未实现）
- TAGGED_PROPERTIES_ONLY: 仅解析 tagged properties（通用 parser 可处理）
- OPAQUE_CLASS_PAYLOAD: 类专属二进制 payload，不尝试解析
- SKIP_UNSUPPORTED: 完全不支持，直接跳过
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class SerializationStrategy(str, Enum):
    """序列化策略枚举。"""
    # 完整专用序列化器（当前未实现任何此类 handler）
    FULL_SERIALIZER = "full_serializer"
    # 仅 tagged properties（通用 property parser 可处理）
    TAGGED_PROPERTIES_ONLY = "tagged_properties_only"
    # 类专属 opaque payload（有自定义 Serialize() 但我们不实现）
    OPAQUE_CLASS_PAYLOAD = "opaque_class_payload"
    # 完全不支持（格式未知或风险过高）
    SKIP_UNSUPPORTED = "skip_unsupported"


# ========== 策略映射表 ==========

# Tagged properties only — 通用 parser 可处理
# 这些类在 UE 源码中未重写 Serialize()，或仅调用 Super::Serialize(Ar)
# 依赖 UObject::Serialize() 的默认 tagged property 序列化机制
_TAGGED_PROPERTIES_CLASSES = frozenset({
    "BlueprintGeneratedClass",  # UE: BlueprintGeneratedClass.h:472 - 仅声明 Serialize()，实际依赖 UObject 默认实现
    "WidgetBlueprintGeneratedClass",  # UE: 继承自 UBlueprintGeneratedClass，无自定义序列化
    "Function",  # UE: UFunction.h - 继承自 UStruct，使用 tagged properties
    "UserDefinedStruct",  # UE: UserDefinedStruct.h:586 - 仅声明 Serialize()，依赖 UObject 默认实现
    "UserDefinedEnum",  # UE: UserDefinedEnum.h:46 - 仅声明 Serialize()，依赖 UObject 默认实现
    "EdGraph",  # UE: EdGraph.h:126 - Serialize(FStructuredArchiveRecord)，标准 tagged properties
    "EdGraphNode",  # UE: EdGraphNode.h:472 - Serialize(FArchive&)，标准 tagged properties
    "K2Node",  # UE: K2Node.h - 继承自 UEdGraphNode，使用 tagged properties
})

# Opaque class payload — 有专用 Serialize() 但我们不实现
# 这些类在 UE 源码中重写了 Serialize()，包含复杂的自定义序列化逻辑：
# - 二进制数据块（FByteBulkData）
# - 平台特定的 cooked data
# - 复杂的版本控制和条件序列化
# - 自定义数据结构（非 tagged properties）
# 通用 tagged property parser 无法正确解析这些内容
_OPAQUE_CLASSES = frozenset({
    "StaticMesh",  # UE: StaticMesh.cpp:7195 - 包含 BodySetup、NavCollision、cooked LOD 数据、FStripDataFlags
    "SkeletalMesh",  # UE: SkeletalMesh.cpp:1114 - 包含 LOD 模型、骨骼数据、cooked render data
    "Texture2D",  # UE: Texture2D.cpp:462 - 包含 FStripDataFlags、bCooked 标志、SerializeCookedPlatformData
    "TextureCube",  # UE: TextureCube.cpp:131 - 包含 FStripDataFlags、bCooked 标志、SerializeCookedPlatformData
    "Material",  # UE: Material.cpp:3054 - 包含 SerializeInlineShaderMaps、LoadedMaterialResources、版本控制
    "MaterialInstanceConstant",  # UE: MaterialInstance.cpp:3197 - 包含 ScalarParameterValues、VectorParameterValues、TextureParameterValues
    "AnimSequence",  # UE: AnimSequence.cpp:609 - 包含 RawAnimationData、压缩动画数据、多个自定义版本
    "AnimMontage",  # UE: AnimMontage.cpp:119 - 包含 BlendIn/BlendOut、SlotAnimTracks、CompositeSections
    "SoundWave",  # UE: SoundWave.cpp:1199 - 包含压缩音频数据、CuePoints、平台特定格式
    "SoundCue",  # UE: SoundCue.cpp:129 - 包含 SoundCueGraph、FirstNode 引用
    "ParticleSystem",  # UE: ParticleSystem.cpp:643 - 包含 Emitters 数组、LODLevels、DetailMode 裁剪
    "NiagaraSystem",  # UE: NiagaraSystem.cpp:1083 - 包含 EmitterHandles、EmitterCompiledData、自定义版本
})

# Skip entirely — 格式未知或风险过高
# 这些类的序列化格式极其复杂，或包含大量动态生成的数据，
# 解析风险高且收益低，因此完全跳过
_SKIP_CLASSES = frozenset({
    "NiagaraGraph",  # UE: NiagaraGraph.h - 包含复杂的节点图数据，依赖 NiagaraScript 编译结果
    "NiagaraScript",  # UE: NiagaraScript.cpp:1769 - 包含 FNiagaraVMExecutableData（VM 字节码）、RapidIterationParameters
    "NiagaraDataInterface",  # UE: NiagaraDataInterface.h - 基类，具体实现类众多，序列化逻辑各异
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
    """获取给定 class 的序列化策略。

    Args:
        class_name: UE class 名称（如 "StaticMesh"）

    Returns:
        SerializationStrategy 枚举值，默认返回 TAGGED_PROPERTIES_ONLY
        （表示可以用通用 parser 尝试）
    """
    return CLASS_STRATEGY_TABLE.get(
        class_name,
        SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    )


def should_skip_class(class_name: str) -> bool:
    """判断是否应完全跳过该 class（不尝试任何解析）。

    Args:
        class_name: UE class 名称

    Returns:
        True 表示应跳过（SKIP_UNSUPPORTED）
    """
    return (
        get_serialization_strategy(class_name)
        == SerializationStrategy.SKIP_UNSUPPORTED
    )


# UClass-derived classes — 只有 UClass 子类序列化 SerializationControlExtensions
# UE 源码 Class.cpp:1624-1627: const bool bIsUClass = IsA<UClass>();
# UClass : public UStruct，但 UStruct 子类（Function, UserDefinedStruct 等）不读取此 header
# 命名表（import.object_name）中 UClass 派生类的名称集合
_UCLASS_DERIVED_CLASSES = frozenset({
    "BlueprintGeneratedClass",       # UE: UClass 派生，主序列化路径
    "WidgetBlueprintGeneratedClass",  # UE: 继承自 UBlueprintGeneratedClass
    "Class",                          # UE: UStruct 的 UClass 表示（元类导出）
})


def is_uclass_derived(class_name: Optional[str]) -> bool:
    """判断该 class 是否为 UClass 派生类。

    只有 UClass 派生类在 UStruct::SerializeTaggedProperties() 中
    读取 SerializationControlExtensions header（Class.cpp:1624-1627）。

    Args:
        class_name: export 的 class name（来自 resolve_class_name()）

    Returns:
        True 表示为 UClass 派生类，False 表示非 UClass（如 UStruct 子类）
    """
    return class_name in _UCLASS_DERIVED_CLASSES


def is_opaque_class(class_name: str) -> bool:
    """判断该 class 是否为 opaque payload（有专用 Serialize() 但不实现）。

    Args:
        class_name: UE class 名称

    Returns:
        True 表示为 opaque class
    """
    return (
        get_serialization_strategy(class_name)
        == SerializationStrategy.OPAQUE_CLASS_PAYLOAD
    )
