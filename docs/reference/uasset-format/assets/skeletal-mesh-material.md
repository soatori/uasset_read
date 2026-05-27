# 骨骼网格材质槽

## 概述

骨骼网格通过 FSkeletalMaterial 数组存储材质引用，渲染分段通过 MaterialIndex 引用材质槽。材质槽结构与静态网格类似，但 MaterialIndex 类型为 uint16 以支持更多材质。

## FSkeletalMaterial 骨骼网格材质槽

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 材质对象引用 | SkeletalMesh.h 第 900 行 |
| MaterialSlotName | FName | 材质槽名称 | SkeletalMesh.h 第 902 行 |
| UVChannelData | FMeshUVChannelInfo | UV 通道信息 | SkeletalMesh.h 第 904 行 |

说明：骨骼网格材质槽结构比静态网格简单，无 ImportedMaterialSlotName 字段。

## FSkelMeshRenderSection 渲染分段材质

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | uint16 | 材质槽索引 | SkeletalMeshLODRenderData.h |
| BaseIndex | uint32 | 索引缓冲起始位置 | SkeletalMeshLODRenderData.h |
| NumTriangles | uint32 | 三角形数量 | SkeletalMeshLODRenderData.h |

说明：骨骼网格的 MaterialIndex 为 uint16（最大 65535 材质），静态网格为 int32。

## 骨骼网格 vs 静态网格材质槽差异

| 特性 | 静态网格 | 骨骼网格 |
|------|----------|----------|
| 材质槽数组名 | StaticMaterials | Materials |
| 材质槽结构 | FStaticMaterial | FSkeletalMaterial |
| MaterialIndex 类型 | int32 | uint16 |
| ImportedMaterialSlotName | 有 | 无 |
| OverlayMaterialInterface | 有 | 无 |

## 材质引用机制

骨骼网格材质引用方式与静态网格相同：
- MaterialInterface 使用 TObjectPtr 智能指针
- 材质对象存储在 Import 表（外部包）或 Export 表（本包）
- MaterialSlotName 用于材质编辑和材质重映射

## 材质槽与骨骼分段关联

```
USkeletalMesh
├── Materials[] (材质槽数组)
│   ├── [0] FSkeletalMaterial → MaterialInterface, MaterialSlotName
│   ├── [1] FSkeletalMaterial → ...
│   └── ...
├── RenderData
│   └── LODRenderData[0]
│       └── RenderSections[] (渲染分段)
│           ├── [0] FSkelMeshRenderSection → MaterialIndex=0, BoneMap...
│           ├── [1] FSkelMeshRenderSection → MaterialIndex=1, BoneMap...
│           └── ...
```

每个 FSkelMeshRenderSection 通过 MaterialIndex 引用 Materials 数组中的材质槽。同一材质可能被多个分段使用。

## 材质槽与骨骼映射

骨骼网格材质槽与骨骼映射的关联：
- 每个 RenderSection 有独立的 BoneMap（影响骨骼列表）
- 材质通常不直接关联骨骼，骨骼影响由皮肤权重决定
- 特殊材质（如布料材质）可能需要特定骨骼映射

## 源码引用

- Runtime/Engine/Classes/Engine/SkeletalMesh.h — FSkeletalMaterial 定义
- Runtime/Engine/Public/Rendering/SkeletalMeshLODRenderData.h — FSkelMeshRenderSection 定义
- Runtime/Engine/Private/Engine/SkeletalMesh.cpp — 材质槽序列化

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| TObjectPtr | 智能指针替代原始指针 |
| uint16 MaterialIndex | 支持更多材质槽数量 |
| 材质槽增强 | 材质管理优化 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 原始指针 | UMaterialInterface* 直接引用 |
| int32 MaterialIndex | 材质索引类型与静态网格一致 |
| 简单材质槽 | 无 UVChannelData 优化 |