# 材质资产版本差异

## 概述

材质资产 (UMaterial/UMaterialInstanceConstant) 在 UE4 至 UE5 演进过程中经历多项格式变更，涉及材质属性重排序、材质实例覆盖、混合模式处理、属性序列化等变更。本文档汇总材质相关关键版本差异。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举和 `CoreObjectVersion.h` FCoreObjectVersion 自定义版本。

## UE4 版本差异表格

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 220 | VER_UE4_MATERIAL_ATTRIBUTES_REORDERING | 材质属性重排序 | 材质属性字段顺序 |
| 297 | VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES | 材质实例基础属性覆盖 | BasePropertyOverrides |
| 321 | VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES_PHASE_2 | 材质实例基础属性覆盖 Phase 2 | BasePropertyOverrides 字段扩展 |
| 362 | VER_UE4_UNDO_BREAK_MATERIALATTRIBUTES_CHANGE | 撤销 BreakMaterialAttributes 变更 | MaterialAttributes |
| 376 | VER_UE4_FIX_REFRACTION_INPUT_MASKING | 折射输入掩码修复 | 折射材质属性 |
| 396 | VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES_DITHERED_LOD_TRANSITION | 材质实例抖动 LOD 过渡 | DitheredLODTransition |
| 421 | VER_UE4_FIX_MATERIAL_COMMENTS | 材质注释边界修复 | 材质图表注释 |
| 428 | VER_UE4_FIX_MATERIAL_COORDS | 材质坐标修复 | 材质坐标表达式 |
| 447 | VER_UE4_FIX_MATERIAL_PROPERTY_OVERRIDE_SERIALIZE | 材质属性覆盖序列化修复 | MaterialInstanceBasePropertyOverrides |
| 474 | VER_UE4_ADD_LINEAR_COLOR_SAMPLER | 线性颜色采样器 | ColorSampler 类型 |
| 537 | VER_UE4_REFRACTION_BIAS_TO_REFRACTION_DEPTH_BIAS | 折射深度偏移重命名 | RefractionBias → RefractionDepthBias |
| 550 | VER_UE4_MATERIAL_MASKED_BLENDMODE_TIDY | 遮罩混合模式整理 | BlendMode 处理 |
| 633 | VER_UE4_REMOVED_MATERIAL_USED_WITH_UI_FLAG | 材质域 UI 使用标志移除 | bUsedWithUI → MaterialDomain |

## UE5 材质变更

| 特性 | 说明 |
|------|------|
| Substrate 系统 | bIsThinSurface 字段新增（Substrate 材质系统） |
| Nanite Override | NaniteOverrideMaterial 字段 |
| 多着色模型 | ShadingModels 字段替代单一 ShadingModel |

## FCoreObjectVersion 自定义版本（与材质相关）

> 定义位置: `Runtime/Core/Public/UObject/CoreObjectVersion.h`

| 版本值 | 版本名 | 说明 |
|-------|--------|------|
| 0 | BeforeCustomVersionWasAdded | 初始版本 |
| 1 | MaterialInputNativeSerialize | 材质输入原生序列化 |
| 2 | EnumProperties | 枚举属性支持 |
| 3 | SkeletalMaterialEditorDataStripping | 骨骼材质编辑器数据剥离 |
| 4 | FProperties | FProperty 系统 |

## 关键变更详细说明

### VER_UE4_MATERIAL_ATTRIBUTES_REORDERING (220)

材质属性字段重排序：
- 版本 < 220：旧的属性字段顺序
- 版本 >= 220：新的属性字段顺序（BaseColor、Metallic、Specular 等标准化）

### VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES (297)

材质实例可以覆盖基础材质属性：
- 版本 < 297：材质实例不能覆盖基础属性
- 版本 >= 297：支持 BasePropertyOverrides 数组

### VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES_PHASE_2 (321)

Phase 2 扩展：
- 扩展了 BasePropertyOverrides 字段
- 新增更多可覆盖属性类型

### VER_UE4_FIX_MATERIAL_COORDS (428)

材质坐标修复：
- 版本 < 428：旧的材质坐标系统
- 版本 >= 428：永久翻转和缩放材质表达式坐标

### VER_UE4_REMOVED_MATERIAL_USED_WITH_UI_FLAG (633)

移除 bUsedWithUI 标志：
- 版本 < 633：使用 bUsedWithUI 布尔标志
- 版本 >= 633：使用 MaterialDomain 枚举（包含 UI Domain）

### VER_UE4_FIX_MATERIAL_PROPERTY_OVERRIDE_SERIALIZE (447)

FMaterialInstanceBasePropertyOverrides 使用正确的 UObject 序列化：
- 版本 < 447：非标准序列化
- 版本 >= 447：标准 UObject 序列化

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| CoreObjectVersion.h | Runtime/Core/Public/UObject/ | 核心 CustomVersion |
| Material.h | Runtime/Engine/Public/Materials/ | 材质类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h + CoreObjectVersion.h 完整枚举同步版本号与版本名*
