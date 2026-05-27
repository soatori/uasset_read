# 材质实例 (UMaterialInstance)

## 概述

UMaterialInstance 类继承自 UMaterialInterface，实现对父材质的参数覆盖。核心用途：允许在不修改材质的情况下，创建材质变体（如不同颜色的同一材质）。

参数覆盖机制简要说明（per D-06）：材质实例通过 Parent 引用建立继承链，参数值在渲染时从继承链查找，优先使用实例自身覆盖值，若无覆盖则沿 Parent 链向上查找直到找到值或到达根材质。不展开参数查找流程。

## 字段表

### 核心引用字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| Parent | TObjectPtr<UMaterialInterface> | 父材质引用（材质或材质实例） |
| PhysMaterial | TObjectPtr<UPhysicalMaterial> | 物理材质引用（可覆盖父材质） |
| PhysicalMaterialMap | TObjectPtr<UPhysicalMaterial>[MAX] | 物理材质映射数组 |
| NaniteOverrideMaterial | FMaterialOverrideNanite | Nanite 替代材质 |

### 缓存属性字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| BlendMode | TEnumAsByte<EBlendMode> | 缓存的混合模式 |
| ShadingModels | FMaterialShadingModelField | 缓存的着色模型字段 |
| TwoSided | uint8:1 | 缓存的双面属性 |
| bIsThinSurface | uint8:1 | 缓存的薄表面属性 |
| OpacityMaskClipValue | float | 缓存的不透明度裁剪值 |

### 参数覆盖数组

| 字段名 | 类型 | 用途 |
|--------|------|------|
| ScalarParameterValues | TArray<FScalarParameterValue> | 标量参数覆盖 |
| VectorParameterValues | TArray<FVectorParameterValue> | 向量参数覆盖 |
| DoubleVectorParameterValues | TArray<FDoubleVectorParameterValue> | 双精度向量参数覆盖（UE5） |
| TextureParameterValues | TArray<FTextureParameterValue> | 纹理参数覆盖 |
| FontParameterValues | TArray<FFontParameterValue> | 字体参数覆盖 |
| RuntimeVirtualTextureParameterValues | TArray<FRuntimeVirtualTextureParameterValue> | 运行时虚拟纹理参数覆盖 |
| SparseVolumeTextureParameterValues | TArray<FSparseVolumeTextureParameterValue> | 稀疏体积纹理参数覆盖（UE5） |

### BasePropertyOverrides 字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| BasePropertyOverrides | FMaterialInstanceBasePropertyOverrides | 基础属性覆盖结构（per D-07，只说明存在） |

BasePropertyOverrides 用途：控制材质实例可覆盖哪些父材质的基础属性（如 BlendMode、ShadingModel、TwoSided 等），包含 bOverride_* 标志和对应覆盖值。

### 其他字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| bHasStaticPermutationResource | uint8:1 | 有静态排列资源（静态参数时必需） |
| bOverrideSubsurfaceProfile | uint8:1 | 覆盖次表面 Profile |
| bOverrideSpecularProfile | uint8:1 | 覆盖镜面 Profile（UE5 Substrate） |

WITH_EDITORONLY_DATA 相关字段统一列出（per D-20）。

## 源码引用

- Runtime/Engine/Public/Materials/MaterialInstance.h — UMaterialInstance 类定义
- Runtime/Engine/Public/Materials/MaterialInstanceBasePropertyOverrides.h — FMaterialInstanceBasePropertyOverrides 结构

## 版本差异

| 变更 | 版本 | 说明 |
|------|------|------|
| DoubleVectorParameterValues | UE5 | 新增双精度向量参数覆盖 |
| SparseVolumeTextureParameterValues | UE5 | 新增稀疏体积纹理参数覆盖 |
| bOverrideSpecularProfile | UE5 | Substrate 系统镜面 Profile 覆盖 |

---
*文档创建: Phase 3 - 材质与纹理资产*
*源码路径: 相对引用 UE Engine 目录*