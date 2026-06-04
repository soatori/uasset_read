# 骨骼网格顶点数据

## 概述

骨骼网格顶点数据与静态网格类似，包含位置、法线、UV、颜色缓冲，但额外包含皮肤权重数据用于骨骼动画。顶点数据分为两种模式：
- **编辑器模式**：通过 `FSkeletalMeshLODModel` 的 `FSkelMeshSection::SoftVertices` 存储 `FSoftSkinVertex`
- **运行时模式**：通过 `FSkeletalMeshLODRenderData` 的 `StaticVertexBuffers` 存储分离的顶点缓冲

## FSoftSkinVertex 软顶点结构

> 定义在 `SkeletalMeshTypes.h` 第 56 行。编辑器模式下用于 `FSkelMeshSection::SoftVertices`。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Position | FVector3f | 顶点位置 | SkeletalMeshTypes.h 第 58 行 |
| TangentX | FVector3f | 切线（U 方向） | SkeletalMeshTypes.h 第 61 行 |
| TangentY | FVector3f | 副法线（V 方向） | SkeletalMeshTypes.h 第 63 行 |
| TangentZ | FVector4f | 法线 | SkeletalMeshTypes.h 第 65 行 |
| UVs | FVector2f[MAX_TEXCOORDS] | UV 坐标数组（最多 8 个通道） | SkeletalMeshTypes.h 第 68 行 |
| Color | FColor | 顶点颜色 | SkeletalMeshTypes.h 第 70 行 |
| InfluenceBones | uint16[MAX_TOTAL_INFLUENCES] | 影响骨骼索引 | SkeletalMeshTypes.h 第 71 行 |
| InfluenceWeights | uint16[MAX_TOTAL_INFLUENCES] | 骨骼权重 | SkeletalMeshTypes.h 第 72 行 |

> **修正**：原 wiki 称骨骼网格使用 `FStaticMeshVertexBuffers` 存储顶点数据。实际上：
> - **编辑器模式**：`FSkelMeshSection::SoftVertices` 使用 `FSoftSkinVertex`，每个顶点直接包含 `InfluenceBones` 和 `InfluenceWeights`
> - **运行时模式**：顶点位置/法线/UV 使用 `FStaticMeshVertexBuffers`，皮肤权重使用独立的 `FSkinWeightVertexBuffer`
>
> `FSoftSkinVertex` 的 `InfluenceBones`/`InfluenceWeights` 类型为 `uint16`，不是 `FBoneIndexType`（FBoneIndexType 在旧版本中为 uint8）。
> `TangentZ` 类型为 `FVector4f`（四维），不是 `FVector3f`。

### FSoftSkinVertex 辅助方法

| 方法名 | 返回类型 | 用途 | 源码位置 |
|--------|----------|------|----------|
| GetRigidWeightBone(uint16&) | bool | 判断是否刚性绑定到单一骨骼 | SkeletalMeshTypes.h 第 75 行 |
| GetMaximumWeight() | uint16 | 获取最大权重值 | SkeletalMeshTypes.h 第 78 行 |
| operator<<(FArchive&, FSoftSkinVertex&) | FArchive& | 序列化运算符 | SkeletalMeshTypes.h 第 87 行 |

## FSkeletalMeshLODModel 编辑器顶点存储

编辑器模式下，顶点数据通过 `FSkelMeshSection::SoftVertices` 存储：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SoftVertices | TArray&lt;FSoftSkinVertex&gt; | 该分段的所有顶点 | SkeletalMeshLODModel.h 第 61 行 |
| NumVertices | int32 | 该分段顶点数 | SkeletalMeshLODModel.h 第 78 行 |
| BoneMap | TArray&lt;FBoneIndexType&gt; | 该分段影响的骨骼索引映射 | SkeletalMeshLODModel.h 第 75 行 |

## FSkeletalMeshLODRenderData 运行时顶点缓冲容器

运行时模式下，顶点数据分离为多个缓冲：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| StaticVertexBuffers | FStaticMeshVertexBuffers | 静态顶点缓冲容器 | SkeletalMeshLODRenderData.h |
| SkinWeightVertexBuffer | FSkinWeightVertexBuffer | 皮肤权重缓冲 | SkeletalMeshLODRenderData.h |
| MultiSizeIndexContainer | FRawStaticIndexBuffer | 索引缓冲容器 | SkeletalMeshLODRenderData.h |
| NumTexCoords | uint32 | UV 通道数量 | SkeletalMeshLODRenderData.h |

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

骨骼网格支持 UV0~UV7 通道（`MAX_TEXCOORDS` 常量定义），用途与静态网格相同：
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

## FSkelMeshRenderSection 运行时渲染分段

> 定义在 `SkeletalMeshLODRenderData.h`，运行时使用。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | uint16 | 材质槽索引 | SkeletalMeshLODRenderData.h 第 30 行 |
| BaseIndex | uint32 | 索引缓冲起始位置 | SkeletalMeshLODRenderData.h 第 33 行 |
| NumTriangles | uint32 | 三角形数量 | SkeletalMeshLODRenderData.h 第 36 行 |
| BoneMap | TArray&lt;FBoneIndexType&gt; | 影响骨骼列表 | SkeletalMeshLODRenderData.h 第 68 行 |
| MaxBoneInfluences | int32 | 最大骨骼影响数 | SkeletalMeshLODRenderData.h 第 74 行 |
| NumVertices | uint32 | 该分段顶点数 | SkeletalMeshLODRenderData.h 第 71 行 |
| BaseVertexIndex | uint32 | 顶点缓冲中的偏移 | SkeletalMeshLODRenderData.h 第 51 行 |

> **修正**：原 wiki 称 `NumVertices` 为 `int32`，实际运行时为 `uint32`。
> **修正**：原 wiki 将 `MaterialIndex` 描述为 "uint16（支持更多材质），静态网格为 int32" — 骨骼网格确实使用 uint16。

## 骨骼网格 vs 静态网格顶点差异

| 特性 | 静态网格 | 骨骼网格 |
|------|----------|----------|
| 皮肤权重 | 无 | FSkinWeightVertexBuffer（运行时）/ FSoftSkinVertex（编辑器） |
| 骨骼映射 | 无 | ActiveBoneIndices, BoneMap |
| 布料数据 | 无 | ClothVertexBuffer（可选） |
| 变形目标 | 无 | MorphTargets 数组 |
| 顶点缓冲 | FStaticMeshVertexBuffers | FStaticMeshVertexBuffers（复用） |
| 重复顶点 | 无 | DuplicatedVerticesBuffer |
| 半边缓冲 | 无 | HalfEdgeBuffer |

## ClothVertexBuffer 布料数据（可选）

骨骼网格可能包含布料模拟数据：
- ClothVertexBuffer (FSkeletalMeshVertexClothBuffer): 布料顶点权重和约束数据
- ClothMappingDataLODs: 布料到骨骼的映射（支持多 LOD 偏差）
- 仅在使用布料物理时存在
- CorrespondClothAssetIndex 和 ClothingData 在每个分段级别存储布料引用

## 源码引用

- Runtime/Engine/Public/SkeletalMeshTypes.h — FSoftSkinVertex 定义（第 56-88 行）
- Runtime/Engine/Public/Rendering/SkeletalMeshLODModel.h — FSkelMeshSection::SoftVertices 定义
- Runtime/Engine/Public/Rendering/SkeletalMeshLODRenderData.h — FSkelMeshRenderSection 和 FSkeletalMeshLODRenderData 定义
- Runtime/Engine/Public/Rendering/PositionVertexBuffer.h — 位置缓冲
- Runtime/Engine/Public/Rendering/StaticMeshVertexBuffer.h — 静态网格缓冲
- Runtime/Engine/Public/Rendering/ColorVertexBuffer.h — 颜色缓冲
- Runtime/Engine/Private/Rendering/SkeletalMeshLODModel.cpp — FSoftSkinVertex 序列化

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| FVector3f | 顶点位置使用显式单精度 FVector3f（替代 FVector） |
| FVector4f | 法线 TangentZ 使用四维 FVector4f |
| ClothVertexBuffer 增强 | 布料数据结构优化 |
| 可变骨骼影响 | UnlimitedBoneInfluences 支持 |
| DuplicatedVerticesBuffer | 重复顶点缓冲优化 |
| HalfEdgeBuffer | 半边缓冲（几何处理） |
| VertexAttributes | 自定义顶点属性缓冲 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| FVector | 顶点位置使用 FVector |
| 简单布料数据 | 布料结构较简单 |
| 固定 4 骨骼影响 | 每顶点最多 4 骨骼 |
| uint8 骨骼索引 | FSoftSkinVertex 中使用 uint8 骨骼索引 |
