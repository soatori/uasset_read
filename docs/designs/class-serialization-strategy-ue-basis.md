# Class Serialization Strategy — UE 源码依据

## 概述

本文档记录 `src/uasset_read/parsers/class_serialization_strategy.py` 中每个分类的 UE C++ 源码证据。

源码根目录：`E:\Develop\lib\UnrealEngine`

## TAGGED_PROPERTIES_ONLY

仅依赖 `UStruct::SerializeTaggedProperties()` 的通用属性解析。

| 类 | UE 源码 | Serialize 策略 | 说明 |
|----|---------|---------------|------|
| BlueprintGeneratedClass | BlueprintGeneratedClass.h:472 | 仅声明 Serialize() | 实际依赖 UObject 默认实现 |
| WidgetBlueprintGeneratedClass | 继承自 UBlueprintGeneratedClass | 无自定义序列化 | 同上 |
| Function | UFunction.h | 继承自 UStruct | 使用 tagged properties |
| UserDefinedStruct | UserDefinedStruct.h:586 | 仅声明 Serialize() | 依赖 UObject 默认实现 |
| UserDefinedEnum | UserDefinedEnum.h:46 | 仅声明 Serialize() | 依赖 UObject 默认实现 |
| EdGraph | EdGraph.h:126 | Serialize(FStructuredArchiveRecord) | 标准 tagged properties |
| EdGraphNode | EdGraphNode.h:472 | Serialize(FArchive&) | 标准 tagged properties |
| K2Node | K2Node.h | 继承自 UEdGraphNode | 使用 tagged properties |

## OPAQUE_CLASS_PAYLOAD

有自定义 `Serialize()` 方法，当前未实现完整反序列化。

| 类 | UE 源码 | 自定义 Serialize 内容 | 当前状态 |
|----|---------|---------------------|---------|
| StaticMesh | StaticMesh.cpp:7195 | BodySetup, NavCollision, cooked LOD 数据, FStripDataFlags | partial_metadata |
| SkeletalMesh | SkeletalMesh.cpp:1114 | LOD 模型, 骨骼数据, cooked render data | partial_metadata |
| Texture2D | Texture2D.cpp:462 | FStripDataFlags, bCooked 标志, SerializeCookedPlatformData | partial_metadata |
| TextureCube | TextureCube.cpp:131 | FStripDataFlags, bCooked 标志, SerializeCookedPlatformData | partial_metadata |
| Material | Material.cpp:3054 | SerializeInlineShaderMaps, LoadedMaterialResources, 版本控制 | partial_metadata |
| MaterialInstanceConstant | MaterialInstance.cpp:3197 | ScalarParameterValues, VectorParameterValues, TextureParameterValues | partial_metadata |
| AnimSequence | AnimSequence.cpp:609 | RawAnimationData, 压缩动画数据, 多个自定义版本 | partial_metadata |
| AnimMontage | AnimMontage.cpp:119 | BlendIn/BlendOut, SlotAnimTracks, CompositeSections | partial_metadata |
| SoundWave | SoundWave.cpp:1199 | 压缩音频数据, CuePoints, 平台特定格式 | partial_metadata |
| SoundCue | SoundCue.cpp:129 | SoundCueGraph, FirstNode 引用 | partial_metadata |
| ParticleSystem | ParticleSystem.cpp:643 | Emitters 数组, LODLevels, DetailMode 裁剪 | partial_metadata |
| NiagaraSystem | NiagaraSystem.cpp:1083 | EmitterHandles, EmitterCompiledData, 自定义版本 | partial_metadata |

## SKIP_UNSUPPORTED

已知不支持或读取会导致问题。

| 类 | UE 源码 | 跳过原因 |
|----|---------|---------|
| NiagaraGraph | NiagaraGraph.h | 包含复杂的节点图数据，依赖 NiagaraScript 编译结果 |
| NiagaraScript | NiagaraScript.cpp:1769 | 包含 FNiagaraVMExecutableData（VM 字节码）, RapidIterationParameters |
| NiagaraDataInterface | NiagaraDataInterface.h | 基类，具体实现类众多，序列化逻辑各异 |

## 版本差异

### Editor-only vs Cooked

- Editor-only 资产包含完整 tagged properties
- Cooked 资产的 class-specific payload 已被烘焙，但 tagged properties 仍可读

### UE4 vs UE5

- 部分类的 `Serialize()` 方法签名在 UE4/UE5 间有差异
- UE5 新增了 `bIsInheritedInstance` 等字段

## 策略应用说明

### 分类原则

1. **TAGGED_PROPERTIES_ONLY**: 类未重写 `Serialize()` 或仅调用 `Super::Serialize(Ar)`，依赖 `UObject::Serialize()` 的默认 tagged property 机制
2. **OPAQUE_CLASS_PAYLOAD**: 类有复杂自定义 `Serialize()` 实现，包含二进制数据块、平台特定数据、版本控制等，通用 parser 无法处理
3. **SKIP_UNSUPPORTED**: 序列化格式极其复杂或包含动态生成数据，解析风险高且收益低

### 与 class_specific_skip.py 的关系

- 本策略表在 `linker.preload()` 层级提前拦截，避免进入 property parser
- `class_specific_skip.py` 在 `property_parser` 内部作为二次安全网

## 未来扩展

### FULL_SERIALIZER（未实现）

预留策略类型，用于未来实现完整专用序列化器：

```python
FULL_SERIALIZER = "full_serializer"
```

当需要完整支持某类的自定义序列化时：
1. 在 `serializers/` 下实现专用序列化器
2. 在策略表中注册为 `FULL_SERIALIZER`
3. 在 `linker.preload()` 中调用专用序列化器

## 参考资料

- [UE 源码对照矩阵](../formats/uasset/ue-correspondence-matrix.md)
- [Tagged Property 格式](../formats/uasset/tagged-property-format.md)
- [Class Payload 解析状态](../formats/uasset/class-payload-status.md)
