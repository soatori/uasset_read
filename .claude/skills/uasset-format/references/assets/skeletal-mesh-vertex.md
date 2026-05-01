# 骨骼网格顶点数据

## 概述

骨骼网格顶点数据与静态网格类似，包含位置、法线、UV、颜色缓冲，但额外包含皮肤权重数据用于骨骼动画。顶点数据通过 FStaticMeshVertexBuffers 结构存储，骨骼网格复用静态网格的顶点缓冲定义。

## FSkeletalMeshLODRenderData 顶点缓冲容器

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| StaticVertexBuffers | FStaticMeshVertexBuffers | 静态顶点缓冲容器 | SkeletalMeshLODRenderData.h 第 23 行 |
| SkinWeightVertexBuffer | FSkinWeightVertexBuffer | 皮肤权重缓冲 | SkeletalMeshLODRenderData.h 第 24 行 |
| MultiSizeIndexContainer | FRawStaticIndexBuffer | 索引缓冲容器 | SkeletalMeshLODRenderData.h 第 26 行 |
| NumTexCoords | uint32 | UV 通道数量 | LOD 数据 |

## FStaticMeshVertexBuffers 静态顶点缓冲

骨骼网格使用与静态网格相同的顶点缓冲结构：

| 子缓冲 | 类型 | 内容 | 源码位置 |
|--------|------|------|----------|
| PositionVertexBuffer | FPositionVertexBuffer | 顶点位置 | StaticMeshResources.h 第 325 行 |
| StaticMeshVertexBuffer | FStaticMeshVertexBuffer | 法线/UV/切线 | StaticMeshResources.h 第 322 行 |
| ColorVertexBuffer | FColorVertexBuffer | 顶点颜色 | StaticMeshResources.h 第 328 行 |

详细字段定义见 [静态网格顶点数据](static-mesh-vertex.md)。

## UV 通道数量

| 字段名 | 类型 | 用途 |
|--------|------|------|
| NumTexCoords | uint32 | UV 通道数量 (1-8) |

骨骼网格支持 UV0~UV7 通道，用途与静态网格相同：
- UV0: 主纹理坐标
- UV1: 光照贴图坐标
- UV2-7: 自定义用途

## MultiSizeIndexContainer 索引缓冲

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| IndexBuffer | FRawStaticIndexBuffer | 三角形索引 | SkeletalMeshLODRenderData.h |

索引格式与静态网格相同：
- 顶点数 ≤ 65535: uint16 索引 (2 字节)
- 顶点数 > 65535: uint32 索引 (4 字节)

## FSkelMeshRenderSection 渲染分段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| BaseIndex | uint32 | 索引缓冲起始位置 | SkeletalMeshLODRenderData.h |
| NumTriangles | uint32 | 三角形数量 | SkeletalMeshLODRenderData.h |
| MaterialIndex | uint16 | 材质索引 | SkeletalMeshLODRenderData.h |
| BoneMap | TArray&lt;FBoneIndexType&gt; | 影响骨骼列表 | SkeletalMeshLODRenderData.h |
| MaxBoneInfluences | int32 | 最大骨骼影响数 | SkeletalMeshLODRenderData.h |

说明：骨骼网格的 MaterialIndex 为 uint16（支持更多材质），静态网格为 int32。

## 骨骼网格 vs 静态网格顶点差异

| 特性 | 静态网格 | 骨骼网格 |
|------|----------|----------|
| 皮肤权重 | 无 | FSkinWeightVertexBuffer |
| 骨骼映射 | 无 | ActiveBoneIndices, BoneMap |
| 布料数据 | 无 | ClothVertexBuffer（可选） |
| 变形目标 | 无 | MorphTargets 数组 |
| 顶点缓冲 | FStaticMeshVertexBuffers | FStaticMeshVertexBuffers（复用） |

## ClothVertexBuffer 布料数据（可选）

骨骼网格可能包含布料模拟数据：
- ClothVertexBuffer: 布料顶点权重和约束数据
- ClothMappingData: 布料到骨骼的映射
- 仅在使用布料物理时存在

## 源码引用

- Runtime/Engine/Public/Rendering/SkeletalMeshLODRenderData.h — FSkeletalMeshLODRenderData 定义
- Runtime/Engine/Public/Rendering/PositionVertexBuffer.h — 位置缓冲
- Runtime/Engine/Public/Rendering/StaticMeshVertexBuffer.h — 静态网格缓冲
- Runtime/Engine/Public/Rendering/ColorVertexBuffer.h — 颜色缓冲
- Runtime/Engine/Private/Rendering/SkeletalMeshLODRenderData.cpp — 序列化

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| FVector3f | 替代 FVector，显式单精度 |
| ClothVertexBuffer 增强 | 布料数据结构优化 |
| 可变骨骼影响 | UnlimitedBoneInfluences 支持 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| FVector | 顶点位置使用 FVector |
| 简单布料数据 | 布料结构较简单 |
| 固定 4 骨骼影响 | 每顶点最多 4 骨骼 |