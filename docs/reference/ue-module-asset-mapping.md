# UE 模块与资产类型映射参考

> **UE 源码对照**: `Engine/Source/Runtime/` 模块目录结构, `Engine/Source/Editor/` 模块目录结构
> **最后对齐**: UE 5.7 (2026-06)

## 概述

UE 引擎由数百个模块组成。本文档建立 UE 模块与 `.uasset` 资产类型之间的映射关系，帮助理解每种资产类型的依赖链和序列化代码来源。

---

## 核心序列化模块（与所有资产相关）

| 模块 | 职责 | 关键类 |
|------|------|--------|
| **CoreUObject** | UObject 系统、序列化、反射 | `UObject`, `UClass`, `FPropertyTag`, `FLinkerLoad` |
| **Core** | 基础类型、容器、序列化 | `FArchive`, `FName`, `FString`, `TArray` |
| **Serialization** | 高级序列化框架 | `FBulkData`, `FStructuredArchive` |

---

## Runtime 模块 → 资产类型映射

### 渲染与网格类

| 资产类型 | 核心模块 | 序列化关键类 | 项目覆盖 |
|---------|---------|-------------|---------|
| StaticMesh | Engine, MeshDescription | `UStaticMesh`, `FStaticMeshLODResources` | ✅ |
| SkeletalMesh | Engine, AnimationCore | `USkeletalMesh`, `FSkeletalMeshLODModel` | ✅ |
| Material | Engine, RenderCore | `UMaterial`, `UMaterialInterface` | ✅ |
| Texture2D | Engine, ImageCore | `UTexture2D`, `FTexturePlatformData` | ✅ |
| TextureCube | Engine, ImageCore | `UTextureCube` | ✅ |

### 动画类

| 资产类型 | 核心模块 | 序列化关键类 | 项目覆盖 |
|---------|---------|-------------|---------|
| AnimSequence | AnimGraphRuntime | `UAnimSequence`, `FAnimSequenceData` | ⚠️ 基础 |
| AnimMontage | AnimGraphRuntime | `UAnimMontage` | ⚠️ 基础 |
| AnimBlueprint | AnimGraph, AnimGraphRuntime | `UAnimBlueprint`, `UAnimInstance` | ⚠️ 基础 |
| BlendSpace | AnimGraphRuntime | `UBlendSpace`, `UBlendSpace1D/2D` | ❌ |
| Skeleton | Engine | `USkeleton` | ⚠️ 基础 |

### 蓝图与逻辑类

| 资产类型 | 核心模块 | 序列化关键类 | 项目覆盖 |
|---------|---------|-------------|---------|
| Blueprint | Engine, Kismet | `UBlueprint`, `UEdGraph`, `UK2Node` | ✅ |
| WidgetBlueprint | UMGEditor | `UWidgetBlueprint` | ⚠️ 基础 |
| DataTable | Engine | `UDataTable`, `FTableRowBase` | ✅ |
| CurveTable | Engine | `UCurveTable`, `FRichCurve` | ✅ |
| DataAsset | Engine | `UPrimaryDataAsset`, `UDataAsset` | ✅ |

### 关卡与世界类

| 资产类型 | 核心模块 | 序列化关键类 | 项目覆盖 |
|---------|---------|-------------|---------|
| World/Level | Engine | `UWorld`, `ULevel` | ✅ |
| LevelSequence | MovieScene, LevelSequence | `ULevelSequence`, `UMovieScene` | ⚠️ 基础 |
| NavMesh | NavigationSystem | `ANavigationData` | ❌ |

### 音频类

| 资产类型 | 核心模块 | 序列化关键类 | 项目覆盖 |
|---------|---------|-------------|---------|
| SoundWave | AudioMixer | `USoundWave`, `FSoundWavePCM` | ⚠️ 基础 |
| SoundCue | AudioEditor | `USoundCue` | ⚠️ 基础 |
| MetaSound | MetasoundFrontend | `UMetasoundGraph` | ⚠️ 基础 |
| SoundMix | AudioEditor | `USoundMix` | ⚠️ 基础 |

### 粒子与特效类

| 资产类型 | 核心模块 | 序列化关键类 | 项目覆盖 |
|---------|---------|-------------|---------|
| ParticleSystem | Engine | `UParticleSystem` | ⚠️ 基础 |
| NiagaraSystem | Niagara | `UNiagaraSystem`, `UNiagaraEmitter` | ⚠️ 基础 |
| NiagaraEmitter | Niagara | `UNiagaraEmitter` | ⚠️ 基础 |

### UI 类

| 资产类型 | 核心模块 | 序列化关键类 | 项目覆盖 |
|---------|---------|-------------|---------|
| Widget (UMG) | UMG, SlateCore | `UUserWidget`, `UWidget` | ⚠️ 基础 |
| WidgetAnimation | UMG | `UWidgetAnimation` | ⚠️ 基础 |

---

## Editor 模块（辅助理解）

| 模块 | 职责 | 与解析器关系 |
|------|------|-------------|
| **BlueprintGraph** | 蓝图节点定义（K2Node_*） | 理解节点序列化格式 |
| **KismetCompiler** | 蓝图编译器 | 理解字节码生成 |
| **UnrealEd** | 编辑器核心、FFactory | 理解资产导入流程 |
| **Persona** | 动画编辑器 | 理解 AnimBP 序列化 |
| **MaterialEditor** | 材质编辑器 | 理解材质图序列化 |

---

## 模块依赖链

### 蓝图依赖链

```
Blueprint (Engine)
  └─ UEdGraph (Engine)
       └─ UK2Node_* (BlueprintGraph/Editor)
            └─ FMemberReference (CoreUObject)
            └─ FPinConnection (Engine)
  └─ UBlueprintGeneratedClass (Engine)
       └─ FProperty (CoreUObject)
       └─ CDO (CoreUObject)
```

### 静态网格依赖链

```
UStaticMesh (Engine)
  └─ FStaticMeshLODResources (Engine/RenderCore)
       └─ FPositionVertexBuffer (RenderCore)
       └─ FStaticMeshVertexBuffer (RenderCore)
       └─ FRawStaticIndexBuffer (RenderCore)
  └─ FMeshDescription (MeshDescription)
  └─ FBulkData (Serialization)
```

### 骨骼网格依赖链

```
USkeletalMesh (Engine)
  └─ FSkeletalMeshLODModel (Engine)
       └─ FStaticLODModel (Engine)
       └─ FSkinWeightVertexBuffer (Engine)
  └─ USkeleton (Engine)
       └─ FReferenceSkeleton (Engine)
  └─ FBulkData (Serialization)
```

### 材质依赖链

```
UMaterial (Engine)
  └─ UMaterialInterface (Engine)
       └─ FMaterialResource (Engine/RenderCore)
       └─ UMaterialExpression* (Engine)
  └─ FParameterCollection (Engine)
  └─ FExpressionInput (Engine)
```

---

## 序列化特征对照

| 模块 | 序列化特征 | 关键标记 |
|------|-----------|---------|
| Engine (基础) | FPropertyTag + SerializeTaggedProperties | 所有 UObject 通用 |
| MeshDescription | BulkData + 顶点/索引缓冲区 | `bCooked` 标志 |
| AnimGraphRuntime | 压缩动画数据 + KeyTime/KeyValue | `CompressedRawDataSize` |
| Niagara | 自定义序列化（非 tagged property） | SKIP_CLASS_NAMES 列表 |
| MovieScene | 关键帧轨道 + 绑定 | `FMovieSceneEvaluationTree` |
| Audio | BulkData (PCM/OGG) + 流式标志 | `bStreaming` |

---

## 版本演进影响

| 版本 | 模块变化 | 影响 |
|------|---------|------|
| UE4 → UE5 | `AnimGraphRuntime` → `AnimGraphRuntime` (重组) | 动画资产序列化格式变化 |
| UE4 → UE5 | `Niagara` 模块成熟 | Niagara 取代 ParticleSystem |
| UE5.0+ | `PROPERTY_TAG_EXTENSION` 新增 | 所有模块受影响的属性序列化变化 |
| UE5.5+ | `PROPERTY_TAG_COMPLETE_TYPE_NAME` | 完整类型名序列化 |

---

## 与解析器的对应关系

| 场景 | 相关模块 | 解析器处理 |
|------|---------|-----------|
| UObject 基础序列化 | CoreUObject | 核心管线 |
| 网格数据读取 | Engine, RenderCore | BulkData 解析 |
| 蓝图节点解析 | BlueprintGraph (Editor) | K2Node 反序列化 |
| 动画压缩数据 | AnimGraphRuntime | 压缩格式解码 |
| 音频 PCM 数据 | AudioMixer | BulkData 解码 |

---

## 源码引用

- `Engine/Source/Runtime/` — Runtime 模块目录
- `Engine/Source/Editor/` — Editor 模块目录
- `Engine/Source/Runtime/CoreUObject/` — 核心 UObject 模块
- `Engine/Source/Runtime/Engine/` — 引擎核心模块
- `Engine/Source/Editor/BlueprintGraph/` — 蓝图图模块
