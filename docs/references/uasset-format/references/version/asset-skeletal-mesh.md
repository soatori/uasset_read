# 骨骼网格版本差异

## 概述

骨骼网格资产 (USkeletalMesh) 在 UE4 演进过程中经历多项格式变更，涉及骨骼层级重构、骨骼权重数据扩展、LOD 数据变更、服装系统变更等。本文档汇总骨骼网格相关关键版本差异。

## 版本差异表格

| 版本号 | 变更描述 | 影响字段/结构 |
|-------|----------|---------------|
| 228 | APEX 服装支持 (VER_UE4_APEX_CLOTH) | Clothing 数据 |
| 243 | 骨骼网格索引数据内存保留 (VER_UE4_KEEP_SKEL_MESH_INDEX_DATA) | IndexData |
| 248 | APEX 服装 LOD Info | ClothLODInfo |
| 258 | 骨骼层级重构为 FReferenceSkeleton (VER_UE4_REFERENCE_SKELETON_REFACTOR) | ReferenceSkeleton |
| 264 | 8 骨骼影响支持 (VER_UE4_SUPPORT_8_BONE_INFLUENCES_SKELETAL_MESHES) | SkinWeight 数据 |
| 272 | GPU 皮肤 8 骨骼影响 | GPU SkinWeight |
| 292 | 骨骼网格阴影投射移至材质 | ShadowCasting 标志 |
| 311 | 骨骼 Guid 序列化 | SkeletonGuid |
| 357 | 非均匀缩放动画支持 | ScaleAnimation |
| 395 | 骨骼导出名称存储 | BoneExportNames |
| 453 | 骨骼层级父骨骼索引修复 | ParentBoneIndex |
| 474 | 骨骼网格组件 BodySetup 移除 | BodySetup 序列化位置 |
| 518 | 骨骼权重 Profile 数据布局变更 | SkinWeightProfile |
| 544 | ActiveBoneIndices 排序 | ActiveBoneIndices 数组 |
| 562 | 骨骼资产属性类型变更 | SkeletonAssetPropertyType |

## UE5 骨骼网格变更

| 特性 | 说明 |
|------|------|
| Large World Coordinates | 骨骼位置转为 double |
| PayloadTOC | 骨骼网格大数据通过 PayloadTOC 管理 |

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| SkeletalMesh.h | Runtime/Engine/Classes/Engine/ | 骨骼网格类定义 |
| ReferenceSkeleton.h | Runtime/Engine/Public/ | 骨骼层级结构 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*