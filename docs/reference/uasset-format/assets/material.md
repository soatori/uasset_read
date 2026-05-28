# 材质资产 (UMaterial)

## 概述

UMaterial 类继承自 UMaterialInterface，定义材质的核心渲染属性和使用标志。核心用途：控制材质的渲染行为（混合模式、着色模型等）以及材质可应用于哪些几何类型。

参数系统和 Expression 引用不在本文档范围（per D-05）。

## 字段表

### 渲染属性字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| MaterialDomain | TEnumAsByte<EMaterialDomain> | 材质域（Surface/PostProcess/Decal等），决定材质用途 |
| BlendMode | TEnumAsByte<EBlendMode> | 混合模式，控制透明度渲染方式（per D-14，不列出类型值） |
| ShadingModel | TEnumAsByte<EMaterialShadingModel> | 着色模型，控制光照计算方式（per D-13，不列出类型值） |
| ShadingModels | FMaterialShadingModelField | 多着色模型组合，支持同一材质使用多种着色（UE5） |
| OpacityMaskClipValue | float | Masked 模式裁剪阈值（默认0.333） |
| TwoSided | uint8:1 | 双面材质，背面法线翻转 |
| bIsThinSurface | uint8:1 | 薄表面材质（Substrate专用，UE5） |

### 半透明属性字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| TranslucencyPass | TEnumAsByte<EMaterialTranslucencyPass> | 半透明渲染 Pass（BeforeDOF/AfterDOF/AfterMotionBlur） |
| TranslucencyLightingMode | TEnumAsByte<ETranslucencyLightingMode> | 半透明光照模式 |
| TranslucentShadowDensityScale | float | 半透明阴影密度缩放 |
| TranslucentSelfShadowDensityScale | float | 半透明自阴影密度缩放 |
| TranslucentBackscatteringExponent | float | 后散射指数 |
| TranslucentMultipleScatteringExtinction | FLinearColor | 多次散射消光颜色 |

### Nanite/Displacement 字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| NaniteOverrideMaterial | FMaterialOverrideNanite | Nanite 渲染替代材质（UE5） |
| bEnableTessellation | uint8:1 | 启用曲面细分 |
| DisplacementScaling | FDisplacementScaling | 置换缩放参数 |

### 物理材质引用

| 字段名 | 类型 | 用途 |
|--------|------|------|
| PhysMaterial | TObjectPtr<UPhysicalMaterial> | 物理材质引用（per D-16，只说明存在） |
| PhysMaterialMask | TObjectPtr<UPhysicalMaterialMask> | 物理材质遮罩引用（per D-16，只说明存在） |
| PhysicalMaterialMap | TObjectPtr<UPhysicalMaterial>[MAX] | 物理材质映射数组 |

### Usage 标志

约 20+ 个 Usage 标志控制材质可应用于哪些几何类型（per D-15，只说明存在）。典型示例：

- bUsedWithSkeletalMesh — 骨骼网格
- bUsedWithStaticMesh — 静态网格
- bUsedWithNanite — Nanite 几何（UE5）
- bUsedWithParticleSprites — 粒子精灵
- bUsedWithBeamTrails — 光束轨迹
- bUsedWithMeshParticles — 网格粒子
- bUsedWithSplineMeshes — 样条网格
- bUsedWithInstancedStaticMeshes — 实例化静态网格
- bUsedWithGeometryCollections — 几何集合
- bUsedWithWater — 水面
- bUsedWithHairStrands — 发丝
- bUsedWithVolumetricCloud — 体积云

### 其他字段

| 字段名 | 类型 | 用途 |
|--------|------|------|
| MaterialDecalResponse | TEnumAsByte<EMaterialDecalResponse> | DBuffer 贴花响应（per D-17，只说明存在） |
| DitheredLODTransition | uint8:1 | LOD 抖动过渡（植被系统） |
| DitherOpacityMask | uint8:1 | 抖动不透明度遮罩 |
| bEnableResponsiveAA | uint8:1 | 响应式抗锯齿 |
| bScreenSpaceReflections | uint8:1 | 半透明屏幕空间反射 |
| bContactShadows | uint8:1 | 半透明接触阴影 |
| bCastDynamicShadowAsMasked | uint8:1 | 半透明作为遮罩投射动态阴影 |
| bTangentSpaceNormal | uint8:1 | 切线空间法线输入 |
| bFullyRough | uint8:1 | 强制完全粗糙 |
| bUseMaterialAttributes | uint8:1 | 使用材质属性 Pin |

WITH_EDITORONLY_DATA 相关字段统一列出（per D-20）。

## 源码引用

- Runtime/Engine/Public/Materials/Material.h — UMaterial 类定义

## 版本差异

| 变更 | 版本 | 说明 |
|------|------|------|
| Substrate 系统 | UE5 | bIsThinSurface 字段（薄表面材质） |
| Nanite 系统 | UE5 | NaniteOverrideMaterial 字段 |
| ShadingModels 字段 | UE5 | 从单值 ShadingModel 变为多着色模型组合 |
| HairStrands/Cloud Usage | UE5 | 新增 Usage 标志 |

---
*文档创建: Phase 3 - 材质与纹理资产*
*源码路径: 相对引用 UE Engine 目录*