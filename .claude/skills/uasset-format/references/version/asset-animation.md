# 动画序列版本差异

## 概述

动画序列资产 (UAnimSequence) 在 UE4 演进过程中经历多项格式变更，涉及动画曲线数据变更、骨骼动画数据序列化、动画通知处理、压缩格式变更等。本文档汇总动画相关关键版本差异。

## 版本差异表格

| 版本号 | 变更描述 | 影响字段/结构 |
|-------|----------|---------------|
| 272 | 动画 NaN 移除 (VER_UE4_ANIMATION_REMOVE_NANS) | 动画数据 NaN 处理 |
| 357 | 非均匀缩放动画支持 | ScaleAnimation |
| 380 | 动画曲线数据添加 (VER_UE4_ANIMATION_ADD_TRACKCURVES) | TrackCurves |
| 388 | 动画蒙塔奇分支点移除 | BranchingPoints |
| 395 | 骨骼 SmartNames 添加 | SkeletonSmartNames |
| 423 | 动画通知触发器清除 | NotifyTriggers |
| 440 | 动画基础姿势序列化修复 | BasePoseSerialization |
| 453 | 根骨骼父骨骼索引修复 | RootBoneParent |
| 475 | 动画组件 RichCurveKey 序列化 | RichCurveKey |
| 486 | 动画过渡非线性混合 | NonLinearTransitionBlends |
| 518 | 动画插槽名称重复修复 | SlotNameDuplication |
| 544 | 动画骨骼权重 Profile 数据布局 | SkinWeightProfile |
| 562 | 动画骨骼资产属性类型变更 | SkeletonAssetPropertyType |

## UE5 动画变更

| 特性 | 说明 |
|------|------|
| Large World Coordinates | 动画位置转为 double |
| Property Tag Extension | 动画属性标签扩展支持 |

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| AnimSequence.h | Runtime/Engine/Classes/Animation/ | 动画序列类定义 |
| AnimSequenceBase.h | Runtime/Engine/Classes/Animation/ | 动画序列基类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*