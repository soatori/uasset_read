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
_TAGGED_PROPERTIES_CLASSES = frozenset({
    "BlueprintGeneratedClass",
    "WidgetBlueprintGeneratedClass",
    "Function",
    "UserDefinedStruct",
    "UserDefinedEnum",
    "EdGraph",
    "EdGraphNode",
    "K2Node",
})

# Opaque class payload — 有专用 Serialize() 但我们不实现
_OPAQUE_CLASSES = frozenset({
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
})

# Skip entirely — 格式未知或风险过高
_SKIP_CLASSES = frozenset({
    "NiagaraGraph",
    "NiagaraScript",
    "NiagaraDataInterface",
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
