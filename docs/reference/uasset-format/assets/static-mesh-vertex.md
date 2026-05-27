# 静态网格顶点数据

## 概述

静态网格顶点数据分为位置缓冲、静态网格缓冲（法线/UV/切线）、颜色缓冲和索引缓冲。每个 LOD 级别拥有独立的顶点数据副本。顶点数据通过 BulkData 机制支持流式加载。

## FPositionVertexBuffer 顶点位置

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| VertexData | FResourceArrayInterface* | 顶点位置数据数组 | PositionVertexBuffer.h |
| NumVertices | uint32 | 顶点数量 | PositionVertexBuffer.h |

每个顶点位置存储为 FVector3f (12 字节)，UE5 使用显式单精度浮点。

## FStaticMeshVertexBuffer 顶点属性

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| NumTexCoords | uint32 | UV 通道数量 (1-8) | StaticMeshVertexBuffer.h |
| TangentsData | FResourceArrayInterface* | 法线和切线数据 | StaticMeshVertexBuffer.h |
| UVData | FResourceArrayInterface* | UV 坐标数据 | StaticMeshVertexBuffer.h |

说明：NumTexCoords 可为 1-8，对应 UV0~UV7 通道。UV 数据按顶点顺序存储，每个顶点存储 NumTexCoords 个 UV 坐标。

## FColorVertexBuffer 顶点颜色

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ColorData | FResourceArrayInterface* | 顶点颜色数据 | ColorVertexBuffer.h |
| NumVertices | uint32 | 顶点数量 | ColorVertexBuffer.h |

顶点颜色存储为 FColor (4 字节，RGBA)，每个分量 0-255。颜色缓冲可选，未设置时使用默认白色。

## FRawStaticIndexBuffer 三角形索引

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| IndexData | FResourceArrayInterface* | 索引数据数组 | RawIndexBuffer.h |
| NumIndices | uint32 | 索引数量 | RawIndexBuffer.h |

索引格式取决于顶点数量：
- 顶点数 ≤ 65535: uint16 索引 (2 字节)
- 顶点数 > 65535: uint32 索引 (4 字节)

索引数量 = NumTriangles * 3。

## UV 通道用途

| UV 通道 | 常见用途 |
|---------|----------|
| UV0 | 主纹理坐标 |
| UV1 | 光照贴图坐标 |
| UV2 | 顶点动画/细节纹理 |
| UV3-7 | 自定义用途 |

MAX_STATIC_TEXCOORDS = 8（最大 UV 通道数）。

## 顶点数据存储

顶点数据存储方式：
- **内联模式**: bBuffersInlined = true，数据直接存储在 LOD 结构中
- **流式模式**: bBuffersInlined = false，数据存储在 StreamingBulkData 中

流式模式允许高级 LOD 数据按需加载，减少内存占用。详见 [BulkData 存储结构](../bulkdata-region.md)。

## 源码引用

- Runtime/Engine/Public/Rendering/PositionVertexBuffer.h — FPositionVertexBuffer 定义
- Runtime/Engine/Public/Rendering/StaticMeshVertexBuffer.h — FStaticMeshVertexBuffer 定义
- Runtime/Engine/Public/Rendering/ColorVertexBuffer.h — FColorVertexBuffer 定义
- Runtime/Engine/Public/RawIndexBuffer.h — FRawStaticIndexBuffer 定义
- Runtime/Engine/Private/StaticMesh.cpp — 顶点数据序列化

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| FVector3f | 替代 FVector，显式单精度浮点 (12 字节) |
| uint32 索引 | 支持超过 65535 顶点的大型网格 |
| 8 UV 通道 | 最大 UV 通道扩展到 8 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| FVector | 顶点位置使用 FVector (可能 12 或 24 字节) |
| uint16 索引限制 | 顶点数超过 65535 时使用 uint32，但较少见 |
| 4 UV 通道 | 最大 UV 通道为 4 |