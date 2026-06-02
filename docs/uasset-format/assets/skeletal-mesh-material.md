# 骨骼网格材质槽

## 概述

骨骼网格通过 `FSkeletalMaterial` 数组存储材质引用，渲染分段通过 `MaterialIndex` 引用材质槽。材质槽结构与静态网格类似。

## FSkeletalMaterial 骨骼网格材质槽

> 定义在 `SkinnedAssetCommon.h` 第 369 行，不是 `SkeletalMesh.h`。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 材质对象引用 | SkinnedAssetCommon.h 第 431 行 |
| MaterialSlotName | FName | 材质槽名称 | SkinnedAssetCommon.h 第 432 行 |
| OverlayMaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 覆盖材质接口 | SkinnedAssetCommon.h 第 438 行 |

### 编辑器模式字段（WITH_EDITORONLY_DATA）

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bEnableShadowCasting_DEPRECATED | bool | 已废弃的阴影投射标记 | SkinnedAssetCommon.h 第 434 行 |
| bRecomputeTangent_DEPRECATED | bool | 已废弃的重新计算切线标记 | SkinnedAssetCommon.h 第 435 行 |
| ImportedMaterialSlotName | FName | 导入的材质槽名称 | SkinnedAssetCommon.h 第 436 行 |

> **重要修正**：
> 1. 原 wiki 称骨骼网格无 `ImportedMaterialSlotName` 字段 — 实际在 `WITH_EDITORONLY_DATA` 下存在
> 2. 原 wiki 引用 `FMeshUVChannelInfo` 作为 `UVChannelData` 字段 — 该字段不存在于 `FSkeletalMaterial` 中（静态网格的 `FStaticMaterial` 才有）
> 3. 原 wiki 称 `MaterialInterface` 在 SkeletalMesh.h 第 900 行 — 实际 FSkeletalMaterial 定义在 SkinnedAssetCommon.h
> 4. `FSkeletalMaterial` 比静态网格的 `FStaticMaterial` 多了 `OverlayMaterialInterface` 字段

## FSkelMeshRenderSection 运行时渲染分段材质

> 定义在 `SkeletalMeshLODRenderData.h`。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | uint16 | 材质槽索引 | SkeletalMeshLODRenderData.h 第 30 行 |
| BaseIndex | uint32 | 索引缓冲起始位置 | SkeletalMeshLODRenderData.h 第 33 行 |
| NumTriangles | uint32 | 三角形数量 | SkeletalMeshLODRenderData.h 第 36 行 |

## FSkelMeshSection 编辑器模式分段材质

> 定义在 `SkeletalMeshLODModel.h`。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | uint16 | 材质槽索引 | SkeletalMeshLODModel.h 第 25 行 |
| BaseIndex | uint32 | 索引缓冲起始位置 | SkeletalMeshLODModel.h 第 28 行 |
| NumTriangles | uint32 | 三角形数量 | SkeletalMeshLODModel.h 第 31 行 |

## 骨骼网格 vs 静态网格材质槽差异

| 特性 | 静态网格 (FStaticMaterial) | 骨骼网格 (FSkeletalMaterial) |
|------|----------|----------|
| 材质槽数组名 | StaticMaterials | Materials |
| 材质槽结构 | FStaticMaterial | FSkeletalMaterial |
| MaterialIndex 类型 | int32 (在 FStaticMeshSection 中) | uint16 (在 FSkelMeshRenderSection 中) |
| ImportedMaterialSlotName | 有（EditorOnly） | 有（EditorOnly，SkinnedAssetCommon.h 第 436 行） |
| OverlayMaterialInterface | 无 | 有 |
| UVChannelData | 有 (FMeshUVChannelInfo) | 无 |
| bEnableShadowCasting | 无 | 有（已废弃，EditorOnly） |

> **修正**：原 wiki 称骨骼网格无 `ImportedMaterialSlotName` 和 `OverlayMaterialInterface` — 实际两者都存在（`OverlayMaterialInterface` 始终存在，`ImportedMaterialSlotName` 在 EditorOnly 下存在）。

## 材质引用机制

骨骼网格材质引用方式：
- MaterialInterface 使用 TObjectPtr 智能指针
- 材质对象存储在 Import 表（外部包）或 Export 表（本包）
- MaterialSlotName 用于材质编辑和材质重映射
- OverlayMaterialInterface 用于覆盖材质（骨骼网格特有）

## 材质槽与骨骼分段关联

```
USkeletalMesh
├── Materials[] (FSkeletalMaterial 材质槽数组)
│   ├── [0] FSkeletalMaterial → MaterialInterface, MaterialSlotName, OverlayMaterialInterface
│   ├── [1] FSkeletalMaterial → ...
│   └── ...
├── (编辑器模式) FSkeletalMeshLODModel
│   └── Sections[] (FSkelMeshSection)
│       ├── [0] FSkelMeshSection → MaterialIndex=0, BoneMap, SoftVertices...
│       ├── [1] FSkelMeshSection → MaterialIndex=1, ...
│       └── ...
└── (运行时) FSkeletalMeshRenderData
    └── LODRenderData[0]
        └── RenderSections[] (FSkelMeshRenderSection)
            ├── [0] FSkelMeshRenderSection → MaterialIndex=0, BoneMap...
            ├── [1] FSkelMeshRenderSection → MaterialIndex=1, ...
            └── ...
```

每个 FSkelMeshSection / FSkelMeshRenderSection 通过 MaterialIndex 引用 Materials 数组中的材质槽。同一材质可能被多个分段使用。

## 材质槽与骨骼映射

骨骼网格材质槽与骨骼映射的关联：
- 每个 RenderSection/Section 有独立的 BoneMap（影响骨骼列表）
- 材质通常不直接关联骨骼，骨骼影响由皮肤权重决定
- 特殊材质（如布料材质）可能需要特定骨骼映射
- ClothingData 在每个分段级别存储布料材质引用

## 源码引用

- Runtime/Engine/Classes/Engine/SkinnedAssetCommon.h — FSkeletalMaterial 定义（第 369-440 行）
- Runtime/Engine/Public/Rendering/SkeletalMeshLODRenderData.h — FSkelMeshRenderSection 定义
- Runtime/Engine/Public/Rendering/SkeletalMeshLODModel.h — FSkelMeshSection 定义
- Runtime/Engine/Classes/Engine/SkeletalMesh.h — USkeletalMesh::Materials（第 903 行）
- Runtime/Engine/Private/Engine/SkeletalMesh.cpp — 材质槽序列化

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| TObjectPtr | 智能指针替代原始指针 |
| uint16 MaterialIndex | 支持更多材质槽数量（最大 65535） |
| OverlayMaterialInterface | 覆盖材质支持 |
| ImportedMaterialSlotName | 编辑器模式下导入材质槽名称保留 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 原始指针 | UMaterialInterface* 直接引用 |
| int32 MaterialIndex | 材质索引类型与静态网格一致 |
| 简单材质槽 | 无 OverlayMaterialInterface |
| bEnableShadowCasting | 阴影投射标记（已废弃） |
| bRecomputeTangent | 重新计算切线标记（已废弃） |
