# 静态网格 LOD 数据

## 概述

静态网格使用 LOD 数组存储多级细节数据，LOD0 为最高精度，最多支持 8 级 LOD。LOD 切换通过 ScreenSize 阈值自动完成，当物体屏幕投影尺寸小于阈值时切换到更低的 LOD 级别。

## FStaticMeshLODResources 字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Sections | FStaticMeshSectionArray | 渲染分段数组 | StaticMeshResources.h 第 430 行 |
| DistanceFieldData | FDistanceFieldVolumeData* | 距离场体积数据（无则为 nullptr） | StaticMeshResources.h 第 433 行 |
| CardRepresentationData | FCardRepresentationData* | 卡片表示数据（无则为 nullptr） | StaticMeshResources.h 第 436 行 |
| RayTracingGeometry | FRayTracingGeometry* | 光线追踪几何（无则为 nullptr） | StaticMeshResources.h 第 439 行 |
| SourceMeshBounds | FBoxSphereBounds | LOD 源网格包围盒 | StaticMeshResources.h 第 442 行 |
| MaxDeviation | float | LOD 与基网格最大偏差 | StaticMeshResources.h 第 445 行 |
| bHasDepthOnlyIndices | uint32 (bitfield) | 深度通道索引缓冲初始化时是否有数据 | StaticMeshResources.h 第 448 行 |
| bHasReversedIndices | uint32 (bitfield) | 反向索引缓冲初始化时是否有数据 | StaticMeshResources.h 第 451 行 |
| bHasReversedDepthOnlyIndices | uint32 (bitfield) | 反向深度通道索引缓冲初始化时是否有数据 | StaticMeshResources.h 第 454 行 |
| bHasColorVertexData | uint32 (bitfield) | 是否有顶点颜色数据 | StaticMeshResources.h 第 456 行 |
| bHasWireframeIndices | uint32 (bitfield) | 是否有线框索引 | StaticMeshResources.h 第 458 行 |
| bBuffersInlined | uint32 (bitfield) | 顶点索引数据内联标志 | StaticMeshResources.h 第 461 行 |
| bIsOptionalLOD | uint32 (bitfield) | 可选 LOD 标志 | StaticMeshResources.h 第 464 行 |
| DepthOnlyNumTriangles | uint32 | 深度通道三角形数量 | StaticMeshResources.h 第 466 行 |
| BuffersSize | uint32 | 顶点和索引缓冲总大小（SerializeBuffers 中计算） | StaticMeshResources.h 第 469 行 |
| StreamingBulkData | FByteBulkData | 流式加载数据 | StaticMeshResources.h 第 471 行 |
| VertexBuffers | FStaticMeshVertexBuffers | 顶点缓冲容器 | StaticMeshResources.h 第 486 行 |
| IndexBuffer | FRawStaticIndexBuffer | 三角形索引缓冲 | StaticMeshResources.h 第 489 行 |
| DepthOnlyIndexBuffer | FRawStaticIndexBuffer | 深度通道索引 | StaticMeshResources.h 第 492 行 |
| AdditionalIndexBuffers | FAdditionalStaticMeshIndexBuffers* | 额外索引缓冲（反向索引、线框索引） | StaticMeshResources.h 第 494 行 |
| AreaWeightedSampler | FStaticMeshAreaWeightedSectionSampler | 基于面积的 Section 采样器 | StaticMeshResources.h 第 497 行 |
| AreaWeightedSectionSamplers | FStaticMeshSectionAreaWeightedTriangleSamplerArray | 基于面积的三角形采样器数组 | StaticMeshResources.h 第 499 行 |
| AreaWeightedSectionSamplersBuffer | FStaticMeshSectionAreaWeightedTriangleSamplerBuffer | GPU 三角形采样器缓冲 | StaticMeshResources.h 第 501 行 |

编辑期字段（WITH_EDITOR）：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| BulkData | FByteBulkData | 编辑器 Bulk 数据 | StaticMeshResources.h 第 478 行 |
| DerivedDataKey | FString | 派生数据键 | StaticMeshResources.h 第 480 行 |
| WedgeMap | TArray&lt;int32&gt; | 楔形索引到顶点索引映射 | StaticMeshResources.h 第 483 行 |

## FStaticMeshSection 渲染分段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | int32 | 材质槽索引 | StaticMeshResources.h 第 204 行 |
| FirstIndex | uint32 | 索引缓冲起始位置 | StaticMeshResources.h 第 207 行 |
| NumTriangles | uint32 | 三角形数量 | StaticMeshResources.h 第 208 行 |
| MinVertexIndex | uint32 | 最小顶点索引 | StaticMeshResources.h 第 209 行 |
| MaxVertexIndex | uint32 | 最大顶点索引 | StaticMeshResources.h 第 210 行 |
| bEnableCollision | bool | 碰撞启用标志 | StaticMeshResources.h 第 213 行 |
| bCastShadow | bool | 阴影投射标志 | StaticMeshResources.h 第 216 行 |
| bVisibleInRayTracing | bool | 光线追踪效果可见标志 | StaticMeshResources.h 第 218 行 |
| bAffectDistanceFieldLighting | bool | 是否影响距离场光照 | StaticMeshResources.h 第 220 行 |
| bForceOpaque | bool | 在光线追踪中强制不透明 | StaticMeshResources.h 第 222 行 |

编辑期字段（WITH_EDITORONLY_DATA）：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| UVDensities | float[MAX_STATIC_TEXCOORDS] | 各 UV 通道密度（LocalSpaceUnit/UV Unit） | StaticMeshResources.h 第 225 行 |
| Weights | float[MAX_STATIC_TEXCOORDS] | 基于面积的 UV 密度权重 | StaticMeshResources.h 第 228 行 |

## LOD 切换机制

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ScreenSize | FPerPlatformFloat[MAX_STATIC_MESH_LODS] | LOD 切换屏幕尺寸阈值 | StaticMeshResources.h 第 789 行 |
| MAX_STATIC_MESH_LODS | 常量 = 8 | LOD 最大级数 | StaticMesh.h 第 59 行 |
| NumInlinedLODs | uint8 | 内联（非流式）LOD 数量 | StaticMeshResources.h 第 820 行 |
| CurrentFirstLODIdx | uint8 | 当前首个 LOD 索引 | StaticMeshResources.h 第 822 行 |
| LODBiasModifier | uint8 | LOD 偏置修正 | StaticMeshResources.h 第 824 行 |

说明：ScreenSize[i] 表示当物体屏幕投影尺寸小于该值时切换到 LOD i+1。例如 ScreenSize[0] = 1.0 表示当物体屏幕占比小于 100% 时可能切换到 LOD1。

## FStaticMeshVertexBuffers 顶点缓冲容器

| 子缓冲 | 类型 | 内容 | 源码位置 |
|--------|------|------|----------|
| PositionVertexBuffer | FPositionVertexBuffer | 顶点位置 | StaticMeshResources.h 第 325 行 |
| StaticMeshVertexBuffer | FStaticMeshVertexBuffer | 法线/UV/切线 | StaticMeshResources.h 第 322 行 |
| ColorVertexBuffer | FColorVertexBuffer | 顶点颜色 | StaticMeshResources.h 第 328 行 |

详细顶点数据结构见 [static-mesh-vertex.md](static-mesh-vertex.md)。

## LOD 数据流式加载

流式加载标志说明：
- **bBuffersInlined = true**: LOD 数据内联在文件头部，加载时立即可用
- **bBuffersInlined = false**: LOD 数据存储在 BulkData 区域，需要异步流式加载
- **bIsOptionalLOD = true**: 该 LOD 为可选级别，顶点和索引数据可能不可用

流式加载由 FByteBulkData (StreamingBulkData) 管理，详见 [BulkData 运行时机制](../serialization/bulkdata.md)。

## 源码引用

- Runtime/Engine/Classes/Engine/StaticMesh.h — FStaticMeshSection 定义（已迁移至 StaticMeshResources.h）、MAX_STATIC_MESH_LODS 常量
- Runtime/Engine/Public/StaticMeshResources.h — FStaticMeshLODResources、FStaticMeshSection、FStaticMeshRenderData 定义
- Runtime/Engine/Private/Engine/StaticMesh.cpp — LOD 序列化实现

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| FPerPlatformFloat ScreenSize | 平台相关 LOD 阈值，不同平台可有不同切换策略 |
| bIsOptionalLOD | 可选 LOD 支持，高级 LOD 可按需加载 |
| RayTracingGeometry | 光线追踪几何数据 |
| DistanceFieldData | 距离场体积数据，用于距离场光照 |
| CardRepresentationData | 网格卡片表示数据（Nanite 相关） |
| bVisibleInRayTracing | Section 级别光线追踪可见性控制 |
| bAffectDistanceFieldLighting | Section 级别距离场光照影响控制 |
| bForceOpaque | Section 级别光线追踪强制不透明 |
| AdditionalIndexBuffers | 反向索引和线框索引的额外索引缓冲 |
| AreaWeightedSectionSamplers | GPU 均匀分布三角形采样支持 |

### UE4 特性
- 简单 float ScreenSize 数组，所有平台使用相同阈值
- 流式加载优化较少，高级 LOD 更常被剥离
- 无 DistanceFieldData、CardRepresentationData、RayTracingGeometry
