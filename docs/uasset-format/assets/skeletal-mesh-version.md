# 骨骼网格版本差异

## 概述

骨骼网格结构随 UE 版本演进，特别是权重系统和骨骼索引类型发生重大变更。UE5 支持无限骨骼影响和 uint16 骨骼索引，突破了 UE4 的固定 4 骨骼影响和 255 骨骼限制。

> **重要**：UE 源码中骨骼网格相关版本通过以下版本系统控制：
> - `FAnimObjectVersion` — 动画/骨骼相关版本（权重系统、骨骼索引）
> - `ESkeletalMeshGeoImportVersions` — 骨骼网格几何导入版本
> - `ESkeletalMeshSkinningImportVersions` — 骨骼网格皮肤权重导入版本
> - `FSkeletalMeshLODModel::DeclareCustomVersions()` — LOD 模型自定义版本
> - `FSkinWeightVertexBuffer::SerializeMetaData()` — 权重缓冲元数据版本

## FAnimObjectVersion 动画相关版本

> 定义在 `Runtime/Core/Public/UObject/ObjectVersion.h`，通过 `Ar.CustomVer(FAnimObjectVersion::GUID)` 检查。

| 版本 | 说明 | 影响 | 源码位置 |
|------|------|------|----------|
| UnlimitedBoneInfluences | 支持可变骨骼影响数 | 权重系统重构，引入 LookupVertexBuffer | ObjectVersion.h |
| IncreaseBoneIndexLimitPerChunk | 骨骼索引从 uint8 升级到 uint16 | 支持超过 255 骨骼 | ObjectVersion.h |
| AddVirtualBones | 支持虚拟骨骼 | FReferenceSkeleton 扩展 | ObjectVersion.h |

说明：这些版本属于 `FAnimObjectVersion` GUID，通过 `CustomVer()` 检查。

## UE5 新增特性

| 特性 | 说明 | 源码位置 |
|------|------|----------|
| TObjectPtr | 智能指针替代原始指针 | SkeletalMesh.h 第 730 行 |
| 可变骨骼影响 | LookupVertexBuffer 支持 | SkinWeightVertexBuffer.h |
| uint16 骨骼索引 | 支持超过 255 骨骼分段 | SkinWeightVertexBuffer.h |
| uint16 权重值 | Use16BitBoneWeight 支持 0-65535 精度 | SkinWeightVertexBuffer.h 第 427-430 行 |
| 虚拟骨骼 | FinalRefBoneInfo 扩展 | ReferenceSkeleton.h |
| CachedComposedRefPoseMatrices | 缓存参考姿势矩阵 | SkeletalMesh.h（ESkeletalMeshAsyncProperties 第 99 位） |
| Nanite 支持 | 骨骼网格 Nanite 实验性支持 | SkeletalMesh.h 第 944 行（EditorOnly） |
| ESkeletalMeshAsyncProperties | 异步属性枚举（60 位） | SkeletalMesh.h 第 74-138 行 |
| FSkinnedAssetCompilationContext | 异步编译上下文 | SkeletalMesh.h |
| RayTracingMinLOD | 光线追踪最小 LOD | SkeletalMesh.h 第 1917 行 |
| ClothLODBiasMode | 布料 LOD 偏差模式 | SkeletalMesh.h 第 1942 行 |
| ShadowPhysicsAsset | 胶囊阴影物理资产 | SkeletalMesh.h 第 1536 行 |
| OverlayMaterialInterface | 覆盖材质支持 | SkinnedAssetCommon.h 第 438 行 |
| DuplicatedVerticesBuffer | 重复顶点缓冲优化 | SkeletalMeshLODRenderData.h |
| HalfEdgeBuffer | 半边缓冲 | SkeletalMeshLODRenderData.h |
| VertexAttributes | 自定义顶点属性缓冲 | SkeletalMeshLODRenderData.h |

## UE4 关键变更

| 特性 | 版本 | 说明 |
|------|------|------|
| 固定 4 骨骼影响 | UE4 默认 | 每顶点最多 4 骨骼影响 |
| uint8 骨骼索引 | UE4 默认 | 最多 255 骨骼索引 |
| Materials 数组 | UE4.22+ | 材质槽数组增强 |
| SkelMirrorTable | UE4.26 | 骨骼镜像表（UE5.0 废弃） |
| bUseFullPrecisionUVs | UE4 | 使用全精度 UV（UE5 废弃） |
| bUseHighPrecisionTangentBasis | UE4 | 使用高精度切线（UE5 废弃） |

## 废弃字段

| 字段名 | 废弃版本 | 替代方案 | 源码位置 |
|--------|----------|----------|----------|
| FBoneMirrorInfo | UE5.0 | UMirrorDataTable | SkeletalMesh.h 第 152-172 行 |
| FBoneMirrorExport | UE5.0 | UMirrorDataTable | SkeletalMesh.h 第 174-195 行 |
| SkelMirrorTable | UE5.0 | UMirrorDataTable | SkeletalMesh.h 第 936-940 行 |
| bAlwaysFullAnimWeight_DEPRECATED | UE5.0 | — | BodySetup.h |
| bUseFullPrecisionUVs_DEPRECATED | UE5.0 | — | SkeletalMesh.h 第 1342 行 |
| bUseHighPrecisionTangentBasis_DEPRECATED | UE5.0 | — | SkeletalMesh.h 第 1346 行 |
| bEnableShadowCasting_DEPRECATED | UE5.0 | — | SkinnedAssetCommon.h 第 434 行 |
| bRecomputeTangent_DEPRECATED | UE5.0 | — | SkinnedAssetCommon.h 第 435 行 |
| SourceModels | UE5.4 | GetSourceModel() 访问器 | SkeletalMesh.h 第 454-455 行 |
| ImportedModel | UE5.0 | GetImportedModel() 访问器 | SkeletalMesh.h 第 662-663 行 |
| SkeletalMeshRenderData | UE5.0 | GetSkeletalMeshRenderData() 访问器 | SkeletalMesh.h 第 667-668 行 |
| ImportedBounds | UE5.0 | GetImportedBounds() 访问器 | SkeletalMesh.h 第 774-776 行 |
| ExtendedBounds | UE5.0 | GetExtendedBounds() 访问器 | SkeletalMesh.h 第 779-781 行 |
| FSkeletalMeshCompilationContext | UE5.1 | FSkinnedAssetCompilationContext | SkeletalMesh.h 第 143 行 |
| RawPointIndices | UE5.0 | RawPointIndices2 | SkeletalMeshLODModel.h 第 451 行 |
| LegacyRawPointIndices | UE5.0 | RawPointIndices2 | SkeletalMeshLODModel.h 第 452 行 |
| RawSkeletalMeshBulkData | UE5.0 | — | SkeletalMeshLODModel.h 第 453 行 |
| ClothMappingData_DEPRECATED | UE5.0 | ClothMappingDataLODs | SkeletalMeshLODRenderData.h 第 54 行 |

## 权重系统版本判断

SkinWeightVertexBuffer.cpp 中版本判断逻辑：

```
if (Ar.CustomVer(FAnimObjectVersion::GUID) >= FAnimObjectVersion::UnlimitedBoneInfluences)
{
    // 可变骨骼影响模式
    // 需要 LookupVertexBuffer
    // MaxBoneInfluences 可大于 4
    // 通过 GetVariableBonesPerVertex() 判断
}
else
{
    // 固定影响数模式（通常 4 骨骼）
    // 无 LookupVertexBuffer（或数据紧凑）
    // InfluenceBones/Weights 固定长度
}

if (Ar.CustomVer(FAnimObjectVersion::GUID) >= FAnimObjectVersion::IncreaseBoneIndexLimitPerChunk)
{
    // 支持 uint16 骨骼索引
    // FBoneIndexType = uint16
    // 最大骨骼数 65535
}
else
{
    // uint8 骨骼索引
    // FBoneIndexType = uint8
    // 最大骨骼数 255
}
```

## 骨骼索引类型判断

| 版本判断 | 索引类型 | 最大骨骼数 |
|----------|----------|------------|
| < IncreaseBoneIndexLimitPerChunk | uint8 (FBoneIndexType) | 255 |
| >= IncreaseBoneIndexLimitPerChunk | uint8 或 uint16 (FBoneIndexType) | 65535 |

说明：骨骼索引类型由 FBoneIndexType typedef 决定，根据版本定义为不同类型。
在运行时通过 `Use16BitBoneIndex()` 方法判断当前使用的索引类型。

## 编辑器模式 vs 运行时模式

| 特性 | 编辑器模式 (WITH_EDITOR) | 运行时模式 |
|------|------------------------|------------|
| LOD 数据模型 | FSkeletalMeshLODModel | FSkeletalMeshLODRenderData |
| 分段结构 | FSkelMeshSection | FSkelMeshRenderSection |
| 顶点存储 | FSoftSkinVertex (每顶点含骨骼权重) | FStaticMeshVertexBuffers + FSkinWeightVertexBuffer |
| 顶点权重 | uint16 InfluenceBones/Weights | 可变 uint8/uint16 |
| SoftVertices | 有 | 无 |
| OverlappingVertices | 有 | 无 |
| UserSectionsData | 有 | 无 |
| MeshToImportVertexMap | 有 | 无 |

## 源码引用

- Runtime/Core/Public/UObject/ObjectVersion.h — FAnimObjectVersion 定义
- Runtime/Engine/Classes/Engine/SkeletalMesh.h — USkeletalMesh 版本相关字段（3249 行）
- Runtime/Engine/Classes/Engine/SkinnedAssetCommon.h — FSkeletalMaterial 版本字段
- Runtime/Engine/Public/Rendering/SkinWeightVertexBuffer.h — 权重版本判断
- Runtime/Engine/Private/Rendering/SkinWeightVertexBuffer.cpp — 权重序列化
- Runtime/Engine/Public/Rendering/SkeletalMeshLODModel.h — 编辑器模式版本
- Runtime/Engine/Public/Rendering/SkeletalMeshLODRenderData.h — 运行时版本

## 版本兼容处理建议

解析骨骼网格时：
1. 检查 FAnimObjectVersion.CustomVer() 确定权重系统版本
2. 根据 UnlimitedBoneInfluences 选择固定/可变影响模式
3. 根据 IncreaseBoneIndexLimitPerChunk 选择骨骼索引类型 (uint8/uint16)
4. 处理虚拟骨骼：检查 FinalRefBoneInfo 是否存在
5. 忽略废弃字段：SkelMirrorTable、FBoneMirrorInfo、bEnableShadowCasting_DEPRECATED 等
6. 使用替代方案：UMirrorDataTable 替代镜像表功能
7. 区分编辑器模式（FSkeletalMeshLODModel）和运行时模式（FSkeletalMeshLODRenderData）的序列化
8. 检查 ESkeletalMeshGeoImportVersions 和 ESkeletalMeshSkinningImportVersions 处理导入版本
9. 注意 FSkeletalMeshLODModel 包裹在 `#if WITH_EDITOR` 中，cooked/运行时数据不包含该结构
