# 类序列化策略的 UE 源码依据

本文档记录了 `class_serialization_strategy.py` 中每个类的序列化策略选择依据，引用自 Unreal Engine C++ 源码。

**UE 版本**: 5.4+  
**源码路径**: `E:\Develop\lib\UnrealEngine\Engine\Source`  
**最后更新**: 2026-06-09

---

## 策略定义

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `TAGGED_PROPERTIES_ONLY` | 仅解析 tagged properties | 类未重写 Serialize()，或仅调用 Super::Serialize(Ar) |
| `OPAQUE_CLASS_PAYLOAD` | 类专属二进制 payload | 类重写了 Serialize()，包含复杂自定义逻辑 |
| `SKIP_UNSUPPORTED` | 完全跳过 | 格式未知或解析风险过高 |

---

## TAGGED_PROPERTIES_ONLY 类

这些类在 UE 源码中**未重写 Serialize()**，或仅调用 `Super::Serialize(Ar)`，依赖 `UObject::Serialize()` 的默认 **tagged property 序列化机制**。

通用 parser 可以通过解析 `UScriptStruct::SerializeTaggedProperties()` 正确读取这些类的属性数据。

### BlueprintGeneratedClass

- **文件**: `Engine/Source/Runtime/Engine/Private/BlueprintGeneratedClass.cpp`
- **头文件**: `Engine/Source/Runtime/Engine/Classes/Engine/BlueprintGeneratedClass.h:472`
- **关键操作**:
  - 仅声明 `ENGINE_API virtual void Serialize(FArchive& Ar) override;`
  - 实际依赖 `UClass::Serialize()` 的默认实现（即 `UObject::Serialize()`）
  - 使用 `SerializeDefaultObject()` 序列化 CDO（默认对象）的 tagged properties

### WidgetBlueprintGeneratedClass

- **继承关系**: 继承自 `UBlueprintGeneratedClass`
- **关键操作**: 无自定义 Serialize()，完全依赖父类实现

### Function

- **类型**: `UFunction`（继承自 `UStruct`）
- **关键操作**: 使用 UObject 默认的 tagged property 序列化

### UserDefinedStruct

- **文件**: `Engine/Source/Runtime/Engine/Private/UserDefinedStruct.cpp`
- **头文件**: `Engine/Source/Runtime/Engine/Classes/Engine/UserDefinedStruct.h:586`
- **关键操作**:
  - 仅声明 `ENGINE_API virtual void Serialize(FArchive& Ar) override;`
  - 依赖 `UStruct::Serialize()` 的默认实现

### UserDefinedEnum

- **文件**: `Engine/Source/Runtime/Engine/Private/UserDefinedEnum.cpp`
- **头文件**: `Engine/Source/Runtime/Engine/Classes/Engine/UserDefinedEnum.h:46`
- **关键操作**:
  - 仅声明 `ENGINE_API virtual void Serialize(FArchive& Ar) override;`
  - 主要序列化 `DisplayNameMap`（用于本地化显示名称）

### EdGraph

- **文件**: `Engine/Source/Runtime/Engine/Private/EdGraph/EdGraph.cpp`
- **头文件**: `Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraph.h:126`
- **关键操作**:
  - `Serialize(FStructuredArchiveRecord Record)` - 使用结构化存档格式
  - 序列化 `Schema`、`Nodes` 数组、标志位等标准属性

### EdGraphNode

- **文件**: `Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphNode.cpp`
- **头文件**: `Engine/Source/Runtime/Engine/Classes/EdGraph/EdGraphNode.h:472`
- **关键操作**:
  - `Serialize(FArchive& Ar)` - 序列化 `NodePosX`、`NodePosY`、`NodeWidth`、`NodeHeight`
  - 序列化 `Pins` 数组（UEdGraphPin*）

### K2Node

- **继承关系**: 继承自 `UEdGraphNode`
- **关键操作**: 使用父类的 Serialize()，通过 tagged properties 序列化节点数据

---

## OPAQUE_CLASS_PAYLOAD 类

这些类在 UE 源码中**重写了 Serialize()**，包含复杂的自定义序列化逻辑：

- 二进制数据块（`FByteBulkData`）
- 平台特定的 cooked data
- 复杂的版本控制和条件序列化
- 自定义数据结构（非 tagged properties）

**通用 tagged property parser 无法正确解析这些内容**，因为：

1. 数据不是以 tagged property 格式存储
2. 需要特定的上下文（如平台信息、版本检查）
3. 包含大量二进制 blob，需要专门的解析器

### StaticMesh

- **文件**: `Engine/Source/Runtime/Engine/Private/StaticMesh.cpp:7195`
- **函数**: `void UStaticMesh::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Super::Serialize(Ar);
  Ar << LocalBodySetup;      // UBodySetup 引用
  Ar << LocalNavCollision;   // UNavCollisionBase 引用
  Ar << bCooked;             // cooked 标志
  // 多个自定义版本检查
  Ar.UsingCustomVersion(FEditorObjectVersion::GUID);
  Ar.UsingCustomVersion(FRenderingObjectVersion::GUID);
  // FStripDataFlags 控制数据剥离
  FStripDataFlags StripFlags(Ar);
  ```
- **为何 opaque**: 包含 LOD 模型数据、碰撞数据、cooked 平台特定数据

### SkeletalMesh

- **文件**: `Engine/Source/Runtime/Engine/Private/SkeletalMesh.cpp`
- **头文件**: `Engine/Source/Runtime/Engine/Classes/Engine/SkeletalMesh.h:2571`
- **函数**: `ENGINE_API virtual void Serialize(FArchive& Ar) override;`
- **关键操作**:
  - 序列化骨骼层次结构（RefSkeleton）
  - 序列化 LOD 模型（FSkeletalMeshLODModel）
  - 序列化顶点缓冲区数据
  - 处理皮肤权重和骨骼索引
- **为何 opaque**: 包含大量二进制网格数据、蒙皮信息、动画绑定数据

### Texture2D

- **文件**: `Engine/Source/Runtime/Engine/Private/Texture2D.cpp:462`
- **函数**: `void UTexture2D::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Super::Serialize(Ar);
  FStripDataFlags StripDataFlags(Ar);
  bool bCooked = Ar.IsCooking();
  Ar << bCooked;
  if (Ar.IsCooking() || bCooked)
  {
      SerializeCookedPlatformData(Ar, bSerializeMipData);
  }
  ```
- **为何 opaque**: 包含压缩的纹理 mip 数据（FByteBulkData），平台特定格式

### TextureCube

- **文件**: `Engine/Source/Runtime/Engine/Private/TextureCube.cpp:131`
- **函数**: `void UTextureCube::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Super::Serialize(Ar);
  FStripDataFlags StripFlags(Ar);
  bool bCooked = Ar.IsCooking();
  Ar << bCooked;
  if (bCooked || Ar.IsCooking())
  {
      SerializeCookedPlatformData(Ar);
  }
  ```
- **为何 opaque**: 与 Texture2D 类似，包含 6 个面的压缩纹理数据

### Material

- **文件**: `Engine/Source/Runtime/Engine/Private/Materials/Material.cpp:3054`
- **函数**: `void UMaterial::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Super::Serialize(Ar);
  // 序列化内联着色器映射
  UE::MaterialInterface::Private::SerializeInlineShaderMaps(
      Ar, LoadedMaterialResources, ...);
  // 旧版本兼容
  LegacyResource->LegacySerialize(Ar);
  ```
- **为何 opaque**: 包含编译后的着色器资源（FMaterialResource）、着色器映射

### MaterialInstanceConstant

- **文件**: `Engine/Source/Runtime/Engine/Private/Materials/MaterialInstance.cpp:3197`
- **函数**: `void UMaterialInstance::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Super::Serialize(Ar);
  // 序列化参数覆盖值
  for (FScalarParameterValue& Parameter : ScalarParameterValues) { ... }
  for (FVectorParameterValue& Parameter : VectorParameterValues) { ... }
  for (FTextureParameterValue& Parameter : TextureParameterValues) { ... }
  for (FFontParameterValue& Parameter : FontParameterValues) { ... }
  ```
- **为何 opaque**: 包含材质参数覆盖数组，需要特殊的序列化格式

### AnimSequence

- **文件**: `Engine/Source/Runtime/Engine/Private/Animation/AnimSequence.cpp:609`
- **函数**: `void UAnimSequence::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Super::Serialize(Ar);
  FStripDataFlags StripFlags(Ar);
  // 原始动画数据（编辑器专用）
  #if WITH_EDITORONLY_DATA
  Ar << RawAnimationData;
  #endif
  // 压缩动画数据处理
  if (Ar.CustomVer(FFrameworkObjectVersion::GUID) < ...)
  {
      // 版本特定的反序列化逻辑
  }
  ```
- **为何 opaque**: 包含关键帧数据、压缩动画轨道、时间轴曲线

### AnimMontage

- **文件**: `Engine/Source/Runtime/Engine/Private/Animation/AnimMontage.cpp:119`
- **函数**: `void UAnimMontage::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  // 混合设置版本控制
  if (Ar.CustomVer(FFortniteMainBranchObjectVersion::GUID) < 
      FFortniteMainBranchObjectVersion::ChangeDefaultAlphaBlendType)
  {
      BlendIn.SetBlendOption(EAlphaBlendOption::Linear);
      BlendOut.SetBlendOption(EAlphaBlendOption::Linear);
  }
  Super::Serialize(Ar);
  ```
- **为何 opaque**: 包含 SlotAnimTracks、CompositeSections、Notify 事件

### SoundWave

- **文件**: `Engine/Source/Runtime/Engine/Private/SoundWave.cpp:1199`
- **函数**: `void USoundWave::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Super::Serialize(Ar);
  // 位打包标志
  uint32 Flags = 0;
  if (Ar.IsCooking())
  {
      Flags |= CookedFlag;
      Flags |= (uint32)OwnerBehavior.LoadingBehavior << LoadingBehaviorShift;
  }
  Ar << Flags;
  // 压缩音频数据
  SerializeCuePoints(Ar, ...);
  ```
- **为何 opaque**: 包含压缩音频数据（FByteBulkData）、CuePoints、平台特定格式

### SoundCue

- **文件**: `Engine/Source/Runtime/Engine/Private/SoundCue.cpp:129`
- **函数**: `void USoundCue::Serialize(FStructuredArchive::FRecord Record)`
- **关键操作**:
  ```cpp
  // 使用结构化存档格式
  FArchive& UnderlyingArchive = Record.GetUnderlyingArchive();
  Duration = FirstNode->GetDuration();
  CacheAggregateValues();
  Super::Serialize(UnderlyingArchive);
  ```
- **为何 opaque**: 包含 SoundCueGraph 引用和节点图数据

### ParticleSystem

- **文件**: `Engine/Source/Runtime/Engine/Private/Particles/ParticleSystem.cpp:643`
- **函数**: `void UParticleSystem::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Ar.UsingCustomVersion(FParticleSystemCustomVersion::GUID);
  // 根据 DetailMode 裁剪 emitter
  for (int32 EmitterIdx = 0; EmitterIdx<Emitters.Num(); EmitterIdx++)
  {
      if (Emitters[EmitterIdx] && !(Emitters[EmitterIdx]->DetailModeBitmask & CookTargetPlatformDetailModeMask))
      {
          Emitters[EmitterIdx] = nullptr;
      }
  }
  Super::Serialize(Ar);
  ```
- **为何 opaque**: 包含 Emitters 数组、LODLevels、模块数据

### NiagaraSystem

- **文件**: `Engine/Plugins/FX/Niagara/Source/Niagara/Private/NiagaraSystem.cpp:1083`
- **函数**: `void UNiagaraSystem::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Ar.UsingCustomVersion(FNiagaraCustomVersion::GUID);
  Super::Serialize(Ar);
  // 序列化 EmitterCompiledData
  UScriptStruct* NiagaraEmitterCompiledDataStruct = FNiagaraEmitterCompiledData::StaticStruct();
  Ar << EmitterCompiledDataNum;
  for (int32 i = 0; i < EmitterCompiledDataNum; ++i)
  {
      FNiagaraEmitterCompiledData& CompiledData = EmitterCompiledData.AddDefaulted_GetRef();
      Struct->SerializeItem(Ar, &CompiledData, nullptr);
  }
  ```
- **为何 opaque**: 包含编译后的 emitter 数据、参数集合、自定义版本

---

## SKIP_UNSUPPORTED 类

这些类的序列化格式**极其复杂**，或包含大量动态生成的数据，解析风险高且收益低。

### NiagaraGraph

- **头文件**: `Engine/Plugins/FX/Niagara/Source/Niagara/Classes/NiagaraGraph.h`
- **原因**: 
  - 包含复杂的节点图数据
  - 依赖 NiagaraScript 编译结果
  - 图结构与 UE 编辑器状态紧密耦合
  - 解析价值低（数据主要用于编辑器）

### NiagaraScript

- **文件**: `Engine/Plugins/FX/Niagara/Source/Niagara/Private/NiagaraScript.cpp:1769`
- **函数**: `void UNiagaraScript::Serialize(FArchive& Ar)`
- **关键操作**:
  ```cpp
  Ar.UsingCustomVersion(FNiagaraCustomVersion::GUID);
  Super::Serialize(Ar);
  // 序列化 VM 可执行数据
  UScriptStruct* VMScriptStruct = FNiagaraVMExecutableData::StaticStruct();
  VMScriptStruct->SerializeItem(Ar, &VMExecutableData, nullptr);
  // 序列化 RapidIterationParameters
  RapidIterationParameters.Serialize(Ar);
  ```
- **原因**: 
  - 包含 `FNiagaraVMExecutableData`（VM 字节码）
  - 字节码格式复杂且随引擎版本变化
  - 解析成本极高，几乎不可能完整支持

### NiagaraDataInterface

- **头文件**: `Engine/Plugins/FX/Niagara/Source/Niagara/Classes/NiagaraDataInterface.h`
- **原因**:
  - 抽象基类，具体实现类众多（NDISkeletalMeshCommon、NIDistanceField 等）
  - 每个子类有独立的序列化逻辑
  - 需要为每个子类实现专门的解析器

---

## 为什么通用 Tagged Property Parser 不足以解析 Opaque 类？

UE 的 `UObject::Serialize()` 默认使用 `UScriptStruct::SerializeTaggedProperties()` 来序列化标记为 `UPROPERTY` 的属性。这种方法适用于大多数类，但以下情况需要自定义序列化：

1. **二进制大数据块**: 纹理 mip 数据、音频样本、网格顶点缓冲区
2. **平台特定格式**: `SerializeCookedPlatformData()` 等平台相关逻辑
3. **性能优化**: 直接序列化内存布局比 tagged properties 更快
4. **向后兼容**: 旧版本数据格式需要特殊处理
5. **复杂引用**: 需要特殊处理的 UObject 引用（如 BodySetup、NavCollision）

对于这些类，我们选择 `OPAQUE_CLASS_PAYLOAD` 策略，仅提取基本的元数据（类名、外层对象等），不尝试解析内部二进制数据。

---

## 参考

- UE 源码: `E:\Develop\lib\UnrealEngine\Engine\Source`
- `UObject::Serialize()`: `Engine/Source/Runtime/CoreUObject/Private/UObject/UObjectBase.cpp`
- `UScriptStruct::SerializeTaggedProperties()`: `Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp`
- `FArchive` 序列化系统: `Engine/Source/Runtime/Core/Public/Serialization/Archive.h`
