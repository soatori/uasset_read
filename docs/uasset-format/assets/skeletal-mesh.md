# 骨骼网格文档

骨骼网格资产类型 (USkeletalMesh) 相关文档导航。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| [skeletal-mesh-structure.md](skeletal-mesh-structure.md) | 基础结构 | USkeletalMesh 和 FSkeletalMeshLODModel 字段 |
| [skeletal-mesh-skeleton.md](skeletal-mesh-skeleton.md) | 骨骼层级 | FReferenceSkeleton 骨骼树结构 |
| [skeletal-mesh-weight.md](skeletal-mesh-weight.md) | 权重数据 | FSkinWeightVertexBuffer 皮肤权重 |
| [skeletal-mesh-vertex.md](skeletal-mesh-vertex.md) | 网格数据 | 顶点缓冲、UV、索引缓冲 |
| [skeletal-mesh-material.md](skeletal-mesh-material.md) | 材质槽 | FSkeletalMaterial 和 Section 材质索引 |
| [skeletal-mesh-version.md](skeletal-mesh-version.md) | 版本差异 | FAnimObjectVersion 关键变更 |

## 核心源码

- Runtime/Engine/Classes/Engine/SkeletalMesh.h — USkeletalMesh 主类定义（3249 行）
- Runtime/Engine/Classes/Engine/SkinnedAssetCommon.h — FSkeletalMaterial 定义
- Runtime/Engine/Public/Rendering/SkeletalMeshLODModel.h — FSkeletalMeshLODModel 和 FSkelMeshSection（编辑器模式）定义
- Runtime/Engine/Public/Rendering/SkeletalMeshLODRenderData.h — FSkelMeshRenderSection 和 FSkeletalMeshLODRenderData（运行时）定义
- Runtime/Engine/Public/ReferenceSkeleton.h — FReferenceSkeleton、FMeshBoneInfo、FVirtualBoneRefData 定义
- Runtime/Engine/Public/SkeletalMeshTypes.h — FSoftSkinVertex 定义
- Runtime/Engine/Public/Rendering/SkinWeightVertexBuffer.h — FSkinWeightVertexBuffer、FSkinWeightDataVertexBuffer、FSkinWeightLookupVertexBuffer 定义

## 重要说明

**FSkeletalMeshLODModel vs FSkeletalMeshLODRenderData 区别：**
- `FSkeletalMeshLODModel`（`SkeletalMeshLODModel.h`）— 编辑器模式下的导入/源数据模型，包裹在 `#if WITH_EDITOR` 中
- `FSkeletalMeshLODRenderData`（`SkeletalMeshLODRenderData.h`）— 运行时渲染数据，游戏模式下使用
- 序列化到 .uasset 的是 `FSkeletalMeshLODModel`（编辑器数据），运行时通过构建流程生成 `FSkeletalMeshLODRenderData`

## 相关文档

- [静态网格文档](static-mesh.md) — 静态网格结构对比
- [动画资产文档](animation.md) — 骨骼动画关联
- [BulkData 运行时机制](../serialization/bulkdata.md) — 流式加载机制
