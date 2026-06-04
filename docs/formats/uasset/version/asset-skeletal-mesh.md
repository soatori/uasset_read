# 骨骼网格版本差异

## 概述

骨骼网格资产 (USkeletalMesh) 在 UE4 至 UE5 演进过程中经历多项格式变更，涉及骨骼层级重构、骨骼权重数据扩展、LOD 数据变更、服装系统变更等。本文档汇总骨骼网格相关关键版本差异。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举和 `AnimObjectVersion.h` FAnimObjectVersion 自定义版本。

## UE4 版本差异表格

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 228 | VER_UE4_APEX_CLOTH | APEX 服装支持 | Clothing 数据 |
| 243 | VER_UE4_KEEP_SKEL_MESH_INDEX_DATA | 骨骼网格索引数据内存保留 | IndexData |
| 248 | VER_UE4_APEX_CLOTH_LOD | APEX 服装 LOD Info | ClothLODInfo |
| 258 | VER_UE4_REFERENCE_SKELETON_REFACTOR | 骨骼层级重构为 FReferenceSkeleton | ReferenceSkeleton |
| 264 | VER_UE4_SUPPORT_8_BONE_INFLUENCES_SKELETAL_MESHES | 8 骨骼影响支持（CPU） | SkinWeight 数据 |
| 272 | VER_UE4_SUPPORT_GPUSKINNING_8_BONE_INFLUENCES | GPU 皮肤 8 骨骼影响 | GPU SkinWeight |
| 292 | VER_UE4_MOVE_SKELETALMESH_SHADOWCASTING | 骨骼网格阴影投射移至材质 | ShadowCasting 标志 |
| 311 | VER_UE4_SKELETON_GUID_SERIALIZATION | 骨骼 Guid 序列化 | SkeletonGuid |
| 357 | VER_UE4_ANIM_SUPPORT_NONUNIFORM_SCALE_ANIMATION | 非均匀缩放动画支持 | ScaleAnimation |
| 395 | VER_UE4_STORE_BONE_EXPORT_NAMES | 骨骼导出名称存储 | BoneExportNames |
| 453 | VER_UE4_FIXUP_ROOTBONE_PARENT | 根骨骼父骨骼索引修复 | RootBoneParent |
| 474 | VER_UE4_REMOVE_SKELETALMESH_COMPONENT_BODYSETUP_SERIALIZATION | 骨骼网格组件 BodySetup 移除 | BodySetup 序列化位置 |
| 518 | VER_UE4_SKINWEIGHT_PROFILE_DATA_LAYOUT_CHANGES | 骨骼权重 Profile 数据布局变更 | SkinWeightProfile |
| 544 | VER_UE4_SORT_ACTIVE_BONE_INDICES | ActiveBoneIndices 排序 | ActiveBoneIndices 数组 |
| 562 | VER_UE4_SKELETON_ASSET_PROPERTY_TYPE_CHANGE | 骨骼资产属性类型变更 | SkeletonAssetPropertyType |

## UE5 骨骼网格变更

| 特性 | 版本 | 说明 |
|------|------|------|
| Large World Coordinates | 1004 | 骨骼位置转为 double |
| PayloadTOC | 1002 | 骨骼网格大数据通过 PayloadTOC 管理 |
| DATA_RESOURCES | 1009 | 大数据资源表统一管理 |

## FAnimObjectVersion 自定义版本

> 定义位置: `Runtime/Core/Public/UObject/AnimObjectVersion.h`

| 版本值 | 版本名 | 变更描述 |
|-------|--------|---------|
| 0 | BeforeCustomVersionWasAdded | 初始版本 |
| 1 | LinkTimeAnimBlueprintRootDiscovery | 链接时动画蓝图根节点发现 |
| 2 | StoreMarkerNamesOnSkeleton | 骨骼上存储标记器同步名称 |
| 3 | SerializeRigVMRegisterArrayState | RigVM 寄存器数组状态序列化 |
| 4 | IncreaseBoneIndexLimitPerChunk | 每区块骨骼索引限制从 uint8 升至 uint16 |
| 5 | UnlimitedBoneInfluences | 无限骨骼影响支持 |
| 6 | AnimSequenceCurveColors | 动画序列曲线颜色 |
| 7 | NotifyAndSyncMarkerGuids | 通知和同步标记 GUID |
| 8 | SerializeRigVMRegisterDynamicState | RigVM 动态状态序列化 |
| 9 | SerializeGroomCards | Groom 卡片序列化 |
| 10 | SerializeRigVMEntries | RigVM 条目序列化 |
| 11 | SerializeHairBindingAsset/HairClusterCullingData | 毛发绑定资产和集群剔除数据 |
| 12 | SerializeGroomCardsAndMeshes/GroomLODStripping/GroomBindingSerialization | Groom 卡片/网格/LOD 剥离/绑定序列化 |

## 关键变更详细说明

### VER_UE4_REFERENCE_SKELETON_REFACTOR (258)

骨骼层级从简单数组重构为 FReferenceSkeleton：
- 版本 < 258：骨骼数据直接存储在数组中
- 版本 >= 258：使用 FReferenceSkeleton 结构，支持更复杂的层级关系

### VER_UE4_SUPPORT_8_BONE_INFLUENCES_SKELETAL_MESHES (264)

骨骼影响从 4 个扩展到 8 个（CPU 顶点）：
- 版本 < 264：每个顶点最多 4 骨骼影响
- 版本 >= 264：每个顶点最多 8 骨骼影响

### VER_UE4_SKINWEIGHT_PROFILE_DATA_LAYOUT_CHANGES (518)

SkinWeightProfile 数据布局变更：
- 版本 < 518：旧布局格式
- 版本 >= 518：新布局格式，优化内存访问

### VER_UE4_SORT_ACTIVE_BONE_INDICES (544)

ActiveBoneIndices 数组排序：
- 版本 < 544：未排序，运行时需排序
- 版本 >= 544：已排序，可直接使用

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| AnimObjectVersion.h | Runtime/Core/Public/UObject/ | 动画 CustomVersion |
| SkeletalMesh.h | Runtime/Engine/Classes/Engine/ | 骨骼网格类定义 |
| ReferenceSkeleton.h | Runtime/Engine/Public/ | 骨骼层级结构 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h + AnimObjectVersion.h 完整枚举同步版本号与版本名*
