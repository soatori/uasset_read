# 材质资产版本差异

## 概述

材质资产 (UMaterial) 在 UE4 演进过程中经历多项格式变更，涉及材质属性重排序、材质实例覆盖、混合模式处理、属性序列化等变更。本文档汇总材质相关关键版本差异。

## 版本差异表格

| 版本号 | 变更描述 | 影响字段/结构 |
|-------|----------|---------------|
| 220 | 材质属性重排序 (VER_UE4_MATERIAL_ATTRIBUTES_REORDERING) | 材质属性字段顺序 |
| 297 | 材质实例基础属性覆盖 (VER_UE4_MATERIAL_INSTANCE_BASE_PROPERTY_OVERRIDES) | BasePropertyOverrides |
| 321 | 材质实例基础属性覆盖 Phase 2 | BasePropertyOverrides 字段扩展 |
| 362 | 材质属性序列化修复 | MaterialAttributes |
| 376 | 材质遮罩输入修复 (VER_UE4_FIX_REFRACTION_INPUT_MASKING) | 折射材质属性 |
| 396 | 材质实例抖动 LOD 过渡 | DitheredLODTransition |
| 421 | 材质注释边界修复 | 材质图表注释 |
| 428 | 材质坐标修复 (VER_UE4_FIX_MATERIAL_COORDS) | 材质坐标表达式 |
| 447 | 材质属性覆盖序列化修复 | MaterialInstanceBasePropertyOverrides |
| 474 | 材质线性颜色采样器 | ColorSampler 类型 |
| 537 | 材质折射深度偏移重命名 | RefractionBias → RefractionDepthBias |
| 550 | 材质遮罩混合模式整理 | BlendMode 处理 |
| 633 | 材质域 UI 使用标志移除 | bUsedWithUI → MaterialDomain |

## UE5 材质变更

| 特性 | 说明 |
|------|------|
| Substrate 系统 | bIsThinSurface 字段新增 |
| Nanite Override | NaniteOverrideMaterial 字段 |
| 多着色模型 | ShadingModels 字段替代单一 ShadingModel |

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| Material.h | Runtime/Engine/Public/Materials/ | 材质类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*