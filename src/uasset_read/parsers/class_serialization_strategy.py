"""类序列化策略表 — 按 UE class 名称映射序列化策略。

与 class_specific_skip.py（property_parser 层级）互补：
- 本模块在 linker.preload() 层级提前拦截，避免进入 property parser
- class_specific_skip.py 在 property_parser 内部作为二次安全网

## UE Serialize() 等价性矩阵 v0.4.5

### 策略定义

| 策略 | UE Serialize 方法 | 说明 |
|---|---|---|
| FULL_SERIALIZER | native+tagged | 有专用 parser，完整实现 UE Serialize() |
| UCLASS_NATIVE | native+tagged | UClass 派生类：UClass::Serialize 原生字段 + tagged properties |
| TAGGED_PROPERTIES_ONLY | tagged_only | 仅 tagged properties（Super::Serialize 链终止于 UObject） |
| OPAQUE_CLASS_PAYLOAD | opaque_bulk | 有自定义 Serialize() 但不实现，保留原始二进制 |
| SKIP_UNSUPPORTED | unsupported | 格式未知或风险过高，完全跳过 |

### ue_serialize_method 元数据

- `"native+tagged"` — 原生字段序列化 + tagged properties（UClass/UFunction 派生类）
- `"tagged_only"` — 仅 tagged properties（依赖 UObject::Serialize 默认实现）
- `"opaque_bulk"` — 自定义二进制数据块（FByteBulkData、cooked platform data 等）
- `"unsupported"` — 格式过于复杂，暂不支持

### 参考 UE 源码位置

- UClass::Serialize: Class.cpp:5987
- UFunction::Serialize: Class.cpp:7573
- UStruct::SerializeTaggedProperties: Class.cpp:1514
- UBlueprintGeneratedClass::Serialize: BlueprintGeneratedClass.cpp:2595
- UStaticMesh::Serialize: StaticMesh.cpp:7195
- USkeletalMesh::Serialize: SkeletalMesh.cpp:1908
- UTexture2D::Serialize: Texture2D.cpp:462
- UMaterial::Serialize: Material.cpp:3054
- UAnimSequence::Serialize: AnimSequence.cpp:609
- UAnimMontage::Serialize: AnimMontage.cpp:119
- USoundWave::Serialize: SoundWave.cpp:1199
- USoundCue::Serialize: SoundCue.cpp:129
- UParticleSystem::Serialize: ParticleSystem.cpp:643
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class SerializationStrategy(str, Enum):
    """序列化策略枚举。"""
    # 完整专用序列化器（当前未实现任何此类 handler）
    FULL_SERIALIZER = "full_serializer"
    # UClass 原生字段 + tagged properties（UClass 派生类专用）
    UCLASS_NATIVE = "uclass_native"
    # 仅 tagged properties（通用 property parser 可处理）
    TAGGED_PROPERTIES_ONLY = "tagged_properties_only"
    # 类专属 opaque payload（有自定义 Serialize() 但我们不实现）
    OPAQUE_CLASS_PAYLOAD = "opaque_class_payload"
    # 完全不支持（格式未知或风险过高）
    SKIP_UNSUPPORTED = "skip_unsupported"


# ========== UE Serialize() 等价性矩阵 ==========

# --- UClass-native classes: native+tagged ---
# 这些类继承自 UClass，UE 中的 Serialize() 执行顺序：
# 1. UClass::Serialize(Class.cpp:5987) — 序列化 FuncMap、ClassFlags、ClassWithin 等原生字段
# 2. UStruct::SerializeTaggedProperties(Class.cpp:1514) — 序列化 tagged properties
# 注意：只有真正的 UClass 派生类才读取 SerializationControlExtensions header
_UCLASS_NATIVE_CLASSES = frozenset({
    "BlueprintGeneratedClass",       # UE: BlueprintGeneratedClass.cpp:2595 - 调用 Super::Serialize + CookedEditorTags
    "WidgetBlueprintGeneratedClass",  # UE: 继承自 UBlueprintGeneratedClass，无额外 Serialize 重写
})

# --- Tagged properties only: tagged_only ---
# 这些类在 UE 中要么：
# a) 没有重写 Serialize()，完全依赖 UObject::Serialize 默认实现
# b) 有 Serialize() 但仅调用 Super::Serialize(Ar) 后无额外操作
# 数据全部通过 FProperty::SerializeTaggedProperties 序列化
_TAGGED_PROPERTIES_CLASSES = frozenset({
    "Function",             # UE: Class.cpp:7573 - 序列化 FunctionFlags、RepOffset、EventGraphFunction，然后 tagged properties
    "UserDefinedStruct",    # UE: UserDefinedStruct.h:586 - 仅声明 Serialize()，依赖 UStruct 默认实现
    "UserDefinedEnum",      # UE: UserDefinedEnum.h:46 - 仅声明 Serialize()，依赖 UEnum 默认实现
    "EdGraph",              # UE: EdGraph.h:126 - Serialize(FStructuredArchiveRecord)，标准 tagged properties
    "EdGraphNode",          # UE: EdGraphNode.h:472 - Serialize(FArchive&)，标准 tagged properties
    "K2Node",               # UE: K2Node.h - 继承自 UEdGraphNode，使用 tagged properties
})

# --- Opaque class payload: opaque_bulk ---
# 这些类在 UE 中有复杂的自定义 Serialize() 实现，包含：
# - FStripDataFlags（版本门控的数据条带化）
# - FByteBulkData / FCompressedChunk（二进制数据块）
# - SerializeCookedPlatformData（平台特定的 cooked 数据）
# - 复杂的条件序列化和自定义版本控制
# 通用 tagged property parser 无法正确解析这些内容
_OPAQUE_CLASSES = frozenset({
    # --- 网格资源 ---
    "StaticMesh",           # UE: StaticMesh.cpp:7195 - BodySetup、NavCollision、cooked LOD 数据、FStripDataFlags、多自定义版本
    "SkeletalMesh",         # UE: SkeletalMesh.cpp:1908 - LOD 模型、骨骼数据、cooked render data、FSkeletalMeshCustomVersion

    # --- 纹理资源 ---
    "Texture2D",            # UE: Texture2D.cpp:462 - FStripDataFlags、bCooked 标志、SerializeCookedPlatformData
    "TextureCube",          # UE: TextureCube.cpp:131 - FStripDataFlags、bCooked 标志、SerializeCookedPlatformData

    # --- 材质资源 ---
    "Material",             # UE: Material.cpp:3054 - SerializeInlineShaderMaps、LoadedMaterialResources、版本控制
    "MaterialInstanceConstant",  # TODO: UE: MaterialInstance.cpp:3197 - Scalar/Vector/Texture ParameterValues（待实现专用 parser）

    # --- 动画资源 ---
    "AnimSequence",         # UE: AnimSequence.cpp:609 - RawAnimationData、压缩动画数据、多个自定义版本
    "AnimMontage",          # UE: AnimMontage.cpp:119 - BlendIn/BlendOut、SlotAnimTracks、CompositeSections

    # --- 音频资源 ---
    "SoundWave",            # UE: SoundWave.cpp:1199 - 压缩音频数据、CuePoints、平台特定格式、位打包 flags
    "SoundCue",             # UE: SoundCue.cpp:129 - SoundCueGraph、FirstNode 引用、FStructuredArchive 格式

    # --- 粒子/Niagara 系统 ---
    "ParticleSystem",       # UE: ParticleSystem.cpp:643 - Emitters 数组、LODLevels、DetailMode 裁剪、FParticleSystemCustomVersion
    "NiagaraSystem",        # TODO: UE: NiagaraSystem.cpp:1083 - EmitterHandles、EmitterCompiledData、自定义版本（待实现专用 parser）
})

# --- Skip entirely: unsupported ---
# 这些类的序列化格式极其复杂，或包含大量动态生成的数据：
# - VM 字节码和编译产物
# - 复杂的节点图数据，依赖其他系统的编译结果
# - 运行时动态生成的数据结构
# 解析风险高且收益低，因此完全跳过
_SKIP_CLASSES = frozenset({
    "NiagaraGraph",         # UE: NiagaraGraph.h - 复杂节点图数据，依赖 NiagaraScript 编译结果
    "NiagaraScript",        # UE: NiagaraScript.cpp:1769 - FNiagaraVMExecutableData（VM 字节码）、RapidIterationParameters
    "NiagaraDataInterface", # UE: NiagaraDataInterface.h - 基类，具体实现类众多，序列化逻辑各异
})

CLASS_STRATEGY_TABLE: dict[str, SerializationStrategy] = {
    cls: SerializationStrategy.UCLASS_NATIVE
    for cls in _UCLASS_NATIVE_CLASSES
} | {
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


# ========== UE Serialize 方法元数据 ==========

# 每个类的 UE Serialize 实现方式描述
# 用于诊断输出 ue_serialize_fidelity 字段
_UE_SERIALIZE_METHOD_MAP: dict[str, str] = {
    # UClass-native: native+tagged
    "BlueprintGeneratedClass": "native+tagged",
    "WidgetBlueprintGeneratedClass": "native+tagged",

    # Tagged properties only: tagged_only
    "Function": "tagged_only",
    "UserDefinedStruct": "tagged_only",
    "UserDefinedEnum": "tagged_only",
    "EdGraph": "tagged_only",
    "EdGraphNode": "tagged_only",
    "K2Node": "tagged_only",

    # Opaque bulk: opaque_bulk
    "StaticMesh": "opaque_bulk",
    "SkeletalMesh": "opaque_bulk",
    "Texture2D": "opaque_bulk",
    "TextureCube": "opaque_bulk",
    "Material": "opaque_bulk",
    "MaterialInstanceConstant": "opaque_bulk",
    "AnimSequence": "opaque_bulk",
    "AnimMontage": "opaque_bulk",
    "SoundWave": "opaque_bulk",
    "SoundCue": "opaque_bulk",
    "ParticleSystem": "opaque_bulk",
    "NiagaraSystem": "opaque_bulk",

    # Skip: unsupported
    "NiagaraGraph": "unsupported",
    "NiagaraScript": "unsupported",
    "NiagaraDataInterface": "unsupported",
}


def get_ue_serialize_method(class_name: str) -> str:
    """获取类在 UE 中的 Serialize 实现方法。

    Args:
        class_name: UE class 名称

    Returns:
        UE Serialize 方法描述："native+tagged" | "tagged_only" | "opaque_bulk" | "unsupported"
    """
    return _UE_SERIALIZE_METHOD_MAP.get(class_name, "tagged_only")  # 未知类默认假设可用 tagged properties


def get_ue_serialize_fidelity(class_name: str) -> str:
    """获取当前解析器对该类的序列化保真度。

    对应 JSON/IR 输出中的 ue_serialize_fidelity 字段值。

    Args:
        class_name: UE class 名称

    Returns:
        保真度描述：
        - "full_native": 完整原生序列化（FULL_SERIALIZER，当前未实现）
        - "partial_native": 部分原生（UCLASS_NATIVE — UClass 级别字段 + tagged properties）
        - "tagged_properties": 仅 tagged properties
        - "opaque_payload": 原始二进制
        - "skipped": 完全跳过
    """
    strategy = get_serialization_strategy(class_name)
    if strategy == SerializationStrategy.FULL_SERIALIZER:
        return "full_native"
    elif strategy == SerializationStrategy.UCLASS_NATIVE:
        return "partial_native"
    elif strategy == SerializationStrategy.TAGGED_PROPERTIES_ONLY:
        return "tagged_properties"
    elif strategy == SerializationStrategy.OPAQUE_CLASS_PAYLOAD:
        return "opaque_payload"
    else:  # SKIP_UNSUPPORTED
        return "skipped"
