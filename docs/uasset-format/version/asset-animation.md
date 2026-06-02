# 动画序列版本差异

## 概述

动画序列资产 (UAnimSequence) 在 UE4 至 UE5 演进过程中经历多项格式变更，涉及动画曲线数据变更、骨骼动画数据序列化、动画通知处理、压缩格式变更等。本文档汇总动画相关关键版本差异。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举和 `AnimObjectVersion.h` FAnimObjectVersion 自定义版本。

## UE4 版本差异表格

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 272 | VER_UE4_ANIMATION_REMOVE_NANS | 动画 NaN 移除 | 动画数据 NaN 处理 |
| 357 | VER_UE4_ANIM_SUPPORT_NONUNIFORM_SCALE_ANIMATION | 非均匀缩放动画支持 | ScaleAnimation |
| 380 | VER_UE4_ANIMATION_ADD_TRACKCURVES | 动画曲线数据添加 (TrackCurves) | TrackCurves |
| 388 | VER_UE4_MONTAGE_BRANCHING_POINT_REMOVAL | 动画蒙塔奇分支点移除 | BranchingPoints |
| 395 | VER_UE4_SKELETON_ADD_SMARTNAMES | 骨骼 SmartNames 添加 | SkeletonSmartNames |
| 423 | VER_UE4_CLEAR_NOTIFY_TRIGGERS | 动画通知触发器清除 | NotifyTriggers |
| 440 | VER_UE4_FIX_ANIMATIONBASEPOSE_SERIALIZATION | 动画基础姿势序列化修复 | BasePoseSerialization |
| 453 | VER_UE4_FIXUP_ROOTBONE_PARENT | 根骨骼父骨骼索引修复 | RootBoneParent |
| 475 | VER_UE4_SERIALIZE_RICH_CURVE_KEY | 动画组件 RichCurveKey 序列化 | RichCurveKey |
| 486 | VER_UE4_ADDED_NON_LINEAR_TRANSITION_BLENDS | 动画过渡非线性混合 | NonLinearTransitionBlends |
| 518 | VER_UE4_SKINWEIGHT_PROFILE_DATA_LAYOUT_CHANGES | 动画插槽名称重复修复 / 骨骼权重 Profile 数据布局 | SkinWeightProfile / SlotNameDuplication |
| 544 | VER_UE4_SORT_ACTIVE_BONE_INDICES | 动画骨骼权重 Profile 数据布局 | ActiveBoneIndices |
| 562 | VER_UE4_SKELETON_ASSET_PROPERTY_TYPE_CHANGE | 动画骨骼资产属性类型变更 | SkeletonAssetPropertyType |

## UE5 动画变更

| 特性 | 版本 | 说明 |
|------|------|------|
| Large World Coordinates | 1004 | 动画位置转为 double |
| Property Tag Extension | 1011 | 动画属性标签扩展支持 |
| DATA_RESOURCES | 1009 | 动画大数据通过 Data Resources 管理 |

## FAnimObjectVersion 自定义版本（与动画相关）

> 定义位置: `Runtime/Core/Public/UObject/AnimObjectVersion.h`

| 版本值 | 版本名 | 说明 |
|-------|--------|------|
| 0 | BeforeCustomVersionWasAdded | 初始版本 |
| 1 | LinkTimeAnimBlueprintRootDiscovery | 链接时动画蓝图根节点发现 |
| 2 | StoreMarkerNamesOnSkeleton | 骨骼上存储标记器同步名称（编辑器） |
| 3 | SerializeRigVMRegisterArrayState | RigVM 寄存器数组状态序列化 |
| 4 | IncreaseBoneIndexLimitPerChunk | 每区块骨骼索引限制从 uint8→uint16 |
| 5 | UnlimitedBoneInfluences | 无限骨骼影响支持 |
| 6 | AnimSequenceCurveColors | 动画序列曲线颜色 |
| 7 | NotifyAndSyncMarkerGuids | 通知和同步标记 GUID |
| 8 | SerializeRigVMRegisterDynamicState | RigVM 动态状态序列化 |
| 9-12 | Groom 相关 | Groom 卡片、网格、LOD 剥离、绑定序列化 |

## 关键变更详细说明

### VER_UE4_ANIMATION_REMOVE_NANS (272)

移除动画数据中的 NaN 值：
- 版本 < 272：动画数据可能包含 NaN（损坏的插值数据）
- 版本 >= 272：加载时自动移除 NaN
- 导入时检测 NaN 并防止进入源数据

### VER_UE4_ANIMATION_ADD_TRACKCURVES (380)

添加动画曲线数据支持：
- 版本 < 380：无 TrackCurves 数据
- 版本 >= 380：支持 FloatCurve、VectorCurve、TransformCurve

### VER_UE4_MONTAGE_BRANCHING_POINT_REMOVAL (388)

移除 AnimMontage 的 BranchingPoints：
- 版本 < 388：使用 BranchingPoints（特殊类型的通知点）
- 版本 >= 388：BranchingPoints 转换为普通 AnimNotifies

### VER_UE4_SERIALIZE_RICH_CURVE_KEY (475)

FRichCurveKey 手动序列化：
- 版本 < 475：完整结构序列化（浪费空间）
- 版本 >= 475：紧凑序列化，节省存储空间

### VER_UE4_ADDED_NON_LINEAR_TRANSITION_BLENDS (486)

非线性过渡混合：
- 版本 < 486：仅支持线性混合
- 版本 >= 486：支持自定义混合曲线
- 旧类型标记为 deprecated

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| AnimObjectVersion.h | Runtime/Core/Public/UObject/ | 动画 CustomVersion |
| AnimSequence.h | Runtime/Engine/Classes/Animation/ | 动画序列类定义 |
| AnimSequenceBase.h | Runtime/Engine/Classes/Animation/ | 动画序列基类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h + AnimObjectVersion.h 完整枚举同步版本号与版本名*
