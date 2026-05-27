# 静态网格文档

静态网格资产类型 (UStaticMesh) 相关文档导航。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| [static-mesh-structure.md](static-mesh-structure.md) | 基础结构 | UStaticMesh 和 FStaticMeshRenderData 字段 |
| [static-mesh-lod.md](static-mesh-lod.md) | LOD 数据 | FStaticMeshLODResources 和切换机制 |
| [static-mesh-vertex.md](static-mesh-vertex.md) | 顶点数据 | 顶点缓冲、UV 通道、索引缓冲 |
| [static-mesh-material.md](static-mesh-material.md) | 材质槽 | FStaticMaterial 和 Section 材质索引 |
| [static-mesh-collision.md](static-mesh-collision.md) | 碰撞数据 | UBodySetup 和碰撞几何类型 |
| [static-mesh-version.md](static-mesh-version.md) | 版本差异 | UE4/UE5 结构变更 |

## 核心源码

- Runtime/Engine/Classes/Engine/StaticMesh.h — UStaticMesh 主类定义
- Runtime/Engine/Public/StaticMeshResources.h — 渲染数据结构
- Runtime/Engine/Private/Engine/StaticMesh.cpp — 序列化实现

## 相关文档

- [骨骼网格文档](skeletal-mesh.md) — 骨骼网格结构对比
- [BulkData 存储结构](../bulkdata-region.md) — LOD 流式数据存储
- [版本兼容机制](../serialization/version-compatibility.md) — 版本判断流程