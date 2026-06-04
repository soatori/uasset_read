# 材质实例 (UMaterialInstance)

## 概述

UMaterialInstance 类继承自 UMaterialInterface，实现对父材质的参数覆盖。核心用途：允许在不修改材质的情况下，创建材质变体（如不同颜色的同一材质）。

**类继承关系：**
```
UMaterialInterface
└── UMaterialInstance (abstract)
    └── UMaterialInstanceConstant (具体实现，游戏中最常用的材质实例类型)
```

参数覆盖机制简要说明（per D-06）：材质实例通过 Parent 引用建立继承链，参数值在渲染时从继承链查找，优先使用实例自身覆盖值，若无覆盖则沿 Parent 链向上查找直到找到值或到达根材质。不展开参数查找流程。

## 字段表

### 核心引用字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Parent | TObjectPtr&lt;UMaterialInterface&gt; | 父材质引用（材质或材质实例） |
| PhysMaterial | TObjectPtr&lt;UPhysicalMaterial&gt; | 物理材质引用（可覆盖父材质） |
| PhysicalMaterialMap | TObjectPtr&lt;UPhysicalMaterial&gt;[EPhysicalMaterialMaskColor::MAX] | 物理材质映射数组（配合 PhysicalMaterialMask 使用） |
| NaniteOverrideMaterial | FMaterialOverrideNanite | Nanite 替代材质 |
| SpecularProfileOverride | TObjectPtr&lt;USpecularProfile&gt; | 镜面 Profile 覆盖（UE5 Substrate） |

### 缓存属性字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| BlendMode | TEnumAsByte&lt;EBlendMode&gt; | 缓存的混合模式 |
| ShadingModels | FMaterialShadingModelField | 缓存的着色模型字段 |
| TwoSided | uint8:1 | 缓存的双面属性 |
| bIsThinSurface | uint8:1 | 缓存的薄表面属性 |
| OpacityMaskClipValue | float | 缓存的不透明度裁剪值 |
| DisplacementScaling | FDisplacementScaling | 位移缩放（缓存） |
| DisplacementFadeRange | FDisplacementFadeRange | 位移淡出范围（缓存） |
| MaxWorldPositionOffsetDisplacement | float | 最大世界位置偏移位移（缓存） |
| DitheredLODTransition | uint8:1 | 抖动 LOD 过渡 |
| bCastDynamicShadowAsMasked | uint8:1 | 动态阴影作为 Masked 渲染 |
| bOutputTranslucentVelocity | uint8:1 | 输出半透明速度 |
| bIsShadingModelFromMaterialExpression | uint8:1 | 着色模型来自材质表达式 |
| bHasPixelAnimation | uint8:1 | 有像素动画 |
| bEnableTessellation | uint8:1 | 启用细分 |
| bEnableDisplacementFade | uint8:1 | 启用位移淡出 |
| bCompatibleWithLumenCardSharing | uint8:1 | 兼容 Lumen 卡共享 |

### 参数覆盖数组

| 字段名 | 类型 | 用途 |
|--------|------|------|
| ScalarParameterValues | TArray&lt;FScalarParameterValue&gt; | 标量参数覆盖 |
| VectorParameterValues | TArray&lt;FVectorParameterValue&gt; | 向量参数覆盖 |
| DoubleVectorParameterValues | TArray&lt;FDoubleVectorParameterValue&gt; | 双精度向量参数覆盖（UE5） |
| TextureParameterValues | TArray&lt;FTextureParameterValue&gt; | 纹理参数覆盖 |
| FontParameterValues | TArray&lt;FFontParameterValue&gt; | 字体参数覆盖 |
| RuntimeVirtualTextureParameterValues | TArray&lt;FRuntimeVirtualTextureParameterValue&gt; | 运行时虚拟纹理参数覆盖 |
| SparseVolumeTextureParameterValues | TArray&lt;FSparseVolumeTextureParameterValue&gt; | 稀疏体积纹理参数覆盖（UE5） |
| TextureCollectionParameterValues | TArray&lt;FTextureCollectionParameterValue&gt; | 纹理集合参数覆盖 |
| ParameterCollectionParameterValues | TArray&lt;FParameterCollectionParameterValue&gt; | 参数集合参数覆盖 |
| UserSceneTextureOverrides | TArray&lt;FUserSceneTextureOverride&gt; | 用户场景纹理覆盖（后处理材质） |

### BasePropertyOverrides 字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| BasePropertyOverrides | FMaterialInstanceBasePropertyOverrides | 基础属性覆盖结构（per D-07，只说明存在） |

BasePropertyOverrides 用途：控制材质实例可覆盖哪些父材质的基础属性（如 BlendMode、ShadingModel、TwoSided 等），包含 bOverride_* 标志和对应覆盖值。

### 覆盖标志字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| bHasStaticPermutationResource | uint8:1 | 有静态排列资源（静态参数时必需） |
| bOverrideSubsurfaceProfile | uint8:1 | 覆盖次表面 Profile |
| bOverrideSpecularProfile | uint8:1 | 覆盖镜面 Profile（UE5 Substrate） |
| bOverrideBlendableLocation | uint8:1 | 覆盖混合位置（后处理材质） |
| bOverrideBlendablePriority | uint8:1 | 覆盖混合优先级（后处理材质） |
| bLoadedCachedData | uint8:1 | 已加载缓存数据（内部） |

### 后处理相关字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| BlendableLocationOverride | TEnumAsByte&lt;EBlendableLocation&gt; | 混合位置覆盖 |
| BlendablePriorityOverride | int32 | 混合优先级覆盖 |

### 内部字段（源码中存在）

| 字段名 | 类型 | 用途 |
|--------|------|------|
| StaticParametersRuntime | FStaticParameterSetRuntimeData | 运行时静态参数集 |
| Resource | FMaterialInstanceResource* | 渲染线程资源代理 |
| CachedData | TUniquePtr&lt;FMaterialInstanceCachedData&gt; | 缓存的实例数据 |
| LoadedMaterialResources | TArray&lt;FMaterialResource&gt; | 从磁盘加载的材质资源（PostLoad 处理） |
| StaticPermutationMaterialResources | TArray&lt;FMaterialResource*&gt; | 静态排列材质资源 |
| bResourceCreated | bool | 实例资源已创建（渲染线程） |
| bCachingUniformExpressions | bool | 正在缓存均匀表达式 |

### WITH_EDITORONLY_DATA 字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| bOverrideBaseProperties_DEPRECATED | bool | 已弃用 |
| EnumerationObjects | TArray&lt;TSoftObjectPtr&lt;UObject&gt;&gt; | 枚举对象数组（标量参数枚举索引） |
| ReferencedTextureGuids | TArray&lt;FGuid&gt; | 引用的纹理 GUID |
| StaticParameters_DEPRECATED | FStaticParameterSet | 已弃用的静态参数集 |
| bSavedCachedData_DEPRECATED | bool | 已弃用的缓存数据标志 |
| ReentrantFlag[2] | bool | 循环检测标志（材质实例图） |
| bDisallowStaticParameterPermutations | bool | 禁止静态参数排列 |
| TransientTextureParameterOverrides | TArray&lt;FTextureParameterOverride&gt; | 瞬态纹理参数覆盖 |

### 参数值结构详解

**FScalarParameterValue：**
| 字段名 | 类型 | 用途 |
|--------|------|------|
| ParameterInfo | FMaterialParameterInfo | 参数信息（名称、关联等） |
| ParameterValue | float | 标量值 |
| ExpressionGUID | FGuid | 表达式 GUID |

**FVectorParameterValue：**
| 字段名 | 类型 | 用途 |
|--------|------|------|
| ParameterInfo | FMaterialParameterInfo | 参数信息 |
| ParameterValue | FLinearColor | 向量值（RGBA） |
| ExpressionGUID | FGuid | 表达式 GUID |

**FDoubleVectorParameterValue（UE5 新增）：**
| 字段名 | 类型 | 用途 |
|--------|------|------|
| ParameterInfo | FMaterialParameterInfo | 参数信息 |
| ParameterValue | FVector4d | 双精度向量值（LWC 大世界坐标） |
| ExpressionGUID | FGuid | 表达式 GUID |

## 源码引用

- Runtime/Engine/Public/Materials/MaterialInstance.h — UMaterialInstance 类定义
- Runtime/Engine/Public/Materials/MaterialInstanceConstant.h — UMaterialInstanceConstant 类定义
- Runtime/Engine/Public/Materials/MaterialInstanceBasePropertyOverrides.h — FMaterialInstanceBasePropertyOverrides 结构

## 版本差异

| 变更 | 版本 | 说明 |
|------|------|------|
| DoubleVectorParameterValues | UE5 | 新增双精度向量参数覆盖（LWC 大世界坐标支持） |
| SparseVolumeTextureParameterValues | UE5 | 新增稀疏体积纹理参数覆盖 |
| bOverrideSpecularProfile | UE5 | Substrate 系统镜面 Profile 覆盖 |
| TextureCollectionParameterValues | UE5 | 新增纹理集合参数覆盖 |
| ParameterCollectionParameterValues | UE5 | 新增参数集合参数覆盖 |
| bCompatibleWithLumenCardSharing | UE5 | Lumen 光照系统兼容性标志 |
| DisplacementScaling/DisplacementFadeRange | UE5 | 位移相关缓存字段 |
| UserSceneTextureOverrides | UE5 | 用户场景纹理覆盖（后处理材质） |

---
*文档版本: v1.2 | 最后更新: 2026-06-01*
*源码对照: UE5.x Engine/Source/Runtime/Engine/Public/Materials/MaterialInstance.h*
*源码对照: UE5.x Engine/Source/Runtime/Engine/Public/Materials/MaterialInstanceConstant.h*
