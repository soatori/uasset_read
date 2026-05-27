# 骨骼网格文档

骨骼网格资产类型 (USkeletalMesh) 相关文档导航。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| [skeletal-mesh-structure.md](skeletal-mesh-structure.md) | 基础结构 | USkeletalMesh 和 FSkeletalMeshRenderData 字段 |
| [skeletal-mesh-skeleton.md](skeletal-mesh-skeleton.md) | 骨骼层级 | FReferenceSkeleton 骨骼树结构 |
| [skeletal-mesh-weight.md](skeletal-mesh-weight.md) | 权重数据 | FSkinWeightVertexBuffer 皮肤权重 |
| [skeletal-mesh-vertex.md](skeletal-mesh-vertex.md) | 网格数据 | 顶点缓冲、UV、索引缓冲 |
| [skeletal-mesh-material.md](skeletal-mesh-material.md) | 材质槽 | FSkeletalMaterial 和 Section 材质索引 |
| [skeletal-mesh-version.md](skeletal-mesh-version.md) | 版本差异 | FAnimObjectVersion 关键变更 |

## 核心源码

- Runtime/Engine/Classes/Engine/SkeletalMesh.h — USkeletalMesh 主类定义
- Runtime/Engine/Public/Rendering/SkeletalMeshRenderData.h — 渲染数据结构
- Runtime/Engine/Public/ReferenceSkeleton.h — 骨骼层级定义
- Runtime/Engine/Private/Engine/SkeletalMesh.cpp — 序列化实现

## 相关文档

- [静态网格文档](static-mesh.md) — 静态网格结构对比
- [动画资产文档](animation.md) — 骨骼动画关联
- [BulkData 运行时机制](../serialization/bulkdata.md) — 流式加载机制