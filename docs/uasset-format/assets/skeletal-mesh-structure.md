# 骨骼网格基础结构

## 概述

USkeletalMesh 是 UE 引擎中用于存储可动画几何体的资产类型，继承自 `USkinnedAsset`。骨骼网格包含：
- 渲染数据：顶点位置、法线、UV、索引缓冲
- 骨骼层级：骨骼树结构和参考姿势变换（通过 FReferenceSkeleton）
- 皮肤权重：逐顶点骨骼影响和权重值
- LOD 系统：多级细节数据，支持可变骨骼影响
- 材质槽：材质引用和 UV 通道信息
- 变形目标：MorphTargets 支持网格变形
- Nanite 设置：骨骼网格 Nanite 实验性支持（UE5）

骨骼网格用于角色、动物等需要骨骼动画的物体。

> **关键区别**：UE 源码中存在两个不同的 LOD 数据结构：
> - `FSkeletalMeshLODModel`（`SkeletalMeshLODModel.h`）— 编辑器模式（`#if WITH_EDITOR`）下的导入/源数据模型
> - `FSkeletalMeshLODRenderData`（`SkeletalMeshLODRenderData.h`）— 运行时渲染数据
> 
> 序列化到 .uasset 的是 `FSkeletalMeshLODModel`，运行时通过构建流程生成 `FSkeletalMeshLODRenderData`。

## USkeletalMesh 主类字段表

USkeletalMesh 继承自 `USkinnedAsset`，以下为主要字段（基于 UE5 源码 `SkeletalMesh.h`）：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Skeleton | TObjectPtr&lt;USkeleton&gt; | 骨骼资产引用 | SkeletalMesh.h 第 730 行 |
| Materials | TArray&lt;FSkeletalMaterial&gt; | 材质槽数组 | SkeletalMesh.h 第 903 行 |
| MorphTargets | TArray&lt;TObjectPtr&lt;UMorphTarget&gt;&gt; | 变形目标数组 | SkeletalMesh.h 第 1962 行 |
| ImportedBounds | FBoxSphereBounds | 导入时包围盒 | SkeletalMesh.h 第 776 行 |
| ExtendedBounds | FBoxSphereBounds | 扩展包围盒 | SkeletalMesh.h 第 781 行 |
| PositiveBoundsExtension | FVector | 正向包围盒扩展 | SkeletalMesh.h 第 809 行 |
| NegativeBoundsExtension | FVector | 负向包围盒扩展 | SkeletalMesh.h 第 823 行 |
| NaniteSettings | FMeshNaniteSettings | Nanite 设置（EditorOnly） | SkeletalMesh.h 第 944 行 |
| RefSkeleton | FReferenceSkeleton | 引用骨骼层级 | SkeletalMesh.h 第 2022 行 |
| RefBasesInvMatrix | TArray&lt;FMatrix44f&gt; | 参考骨骼逆矩阵 | SkeletalMesh.h 第 2094 行 |
| MorphTargetIndexMap | TMap&lt;FName, int32&gt; | 变形目标名称到索引映射 | SkeletalMesh.h 第 2059 行 |
| PhysicsAsset | TObjectPtr&lt;UPhysicsAsset&gt; | 物理资产 | SkeletalMesh.h 第 1503 行 |
| ShadowPhysicsAsset | TObjectPtr&lt;UPhysicsAsset&gt; | 阴影物理资产 | SkeletalMesh.h 第 1536 行 |
| BodySetup | TObjectPtr&lt;UBodySetup&gt; | 碰撞体设置 | SkeletalMesh.h 第 1473 行 |
| NodeMappingData | TArray&lt;TObjectPtr&lt;UNodeMappingContainer&gt;&gt; | 节点映射数据 | SkeletalMesh.h 第 1566 行 |
| bHasVertexColors | uint8 | 是否包含顶点颜色 | SkeletalMesh.h 第 1365 行 |
| bSupportRayTracing | uint8 | 是否支持光线追踪 | SkeletalMesh.h 第 1893 行 |
| RayTracingMinLOD | int32 | 光线追踪最小 LOD | SkeletalMesh.h 第 1917 行 |
| ClothLODBiasMode | EClothLODBiasMode | 布料 LOD 偏差模式 | SkeletalMesh.h 第 1942 行 |

### 已废弃字段

| 字段名 | 状态 | 替代方案 |
|--------|------|----------|
| FBoneMirrorInfo | UE5.0 已废弃 | UMirrorDataTable |
| FBoneMirrorExport | UE5.0 已废弃 | UMirrorDataTable |
| SkelMirrorTable | UE5.0 已废弃 | UMirrorDataTable |
| bAlwaysFullAnimWeight_DEPRECATED | 已废弃 | — |
| SourceModels | UE5.4 已废弃 | 使用 GetSourceModel() 访问器 |
| ImportedModel | UE5.0 已废弃 | 使用 GetImportedModel() 访问器 |
| SkeletalMeshRenderData | UE5.0 已废弃 | 使用 GetSkeletalMeshRenderData() 访问器 |

说明：UE5 中大量字段标记为 `UE_DEPRECATED`，实际访问应通过 getter/setter 方法，字段变为 protected/private。

## FSkeletalMeshLODModel 编辑器 LOD 模型字段表

> **注意**：`FSkeletalMeshLODModel` 仅存在于 `#if WITH_EDITOR` 中，是编辑器模式下的源数据模型。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Sections | TArray&lt;FSkelMeshSection&gt; | 分段数组（编辑器模式） | SkeletalMeshLODModel.h 第 297 行 |
| UserSectionsData | TMap&lt;int32, FSkelMeshSourceSectionUserData&gt; | 用户修改的分段数据 | SkeletalMeshLODModel.h 第 305 行 |
| NumVertices | uint32 | 顶点总数 | SkeletalMeshLODModel.h 第 307 行 |
| NumTexCoords | uint32 | UV 通道数量 | SkeletalMeshLODModel.h 第 309 行 |
| IndexBuffer | TArray&lt;uint32&gt; | 索引缓冲（覆盖所有分段） | SkeletalMeshLODModel.h 第 312 行 |
| ActiveBoneIndices | TArray&lt;FBoneIndexType&gt; | 该 LOD 活跃骨骼列表 | SkeletalMeshLODModel.h 第 318 行 |
| RequiredBones | TArray&lt;FBoneIndexType&gt; | 渲染时需要更新的骨骼（含父骨骼路径） | SkeletalMeshLODModel.h 第 325 行 |
| SkinWeightProfiles | TMap&lt;FName, FImportedSkinWeightProfileData&gt; | 皮肤权重配置文件 | SkeletalMeshLODModel.h 第 328 行 |
| VertexAttributes | TMap&lt;FName, FSkeletalMeshModelVertexAttribute&gt; | 顶点属性 | SkeletalMeshLODModel.h 第 331 行 |
| MeshToImportVertexMap | TArray&lt;int32&gt; | LOD 顶点到导入源顶点的映射 | SkeletalMeshLODModel.h 第 336 行 |
| MaxImportVertex | int32 | 最大导入顶点索引 | SkeletalMeshLODModel.h 第 339 行 |
| RawSkeletalMeshBulkDataID | FString | DDC 密钥使用的 BulkData ID | SkeletalMeshLODModel.h 第 360 行 |
| bIsBuildDataAvailable | bool | 构建数据是否可用 | SkeletalMeshLODModel.h 第 361 行 |
| bIsRawSkeletalMeshBulkDataEmpty | bool | 原始 BulkData 是否为空 | SkeletalMeshLODModel.h 第 362 行 |

### 私有字段（不直接序列化）

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ImportedMeshInfos | TArray&lt;FSkelMeshImportedMeshInfo&gt; | 导入的网格信息 | SkeletalMeshLODModel.h 第 443 行 |
| RawPointIndices2 | TArray&lt;uint32&gt; | 原始点索引（楔形索引映射） | SkeletalMeshLODModel.h 第 449 行 |
| RawPointIndices | FIntBulkData | 已废弃 | SkeletalMeshLODModel.h 第 451 行 |
| LegacyRawPointIndices | FWordBulkData | 已废弃 | SkeletalMeshLODModel.h 第 452 行 |
| RawSkeletalMeshBulkData | FRawSkeletalMeshBulkData | 已废弃 | SkeletalMeshLODModel.h 第 453 行 |
| BulkDataReadMutex | FCriticalSection* | BulkData 读取互斥锁 | SkeletalMeshLODModel.h 第 458 行 |
| BuildStringID | FThreadSafeBuildStringID | 线程安全构建 ID | SkeletalMeshLODModel.h 第 594 行 |

## FSkelMeshSection 编辑器模式分段字段表

> 位于 `SkeletalMeshLODModel.h`，编辑器模式下使用。与运行时 `FSkelMeshRenderSection` 结构不同。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | uint16 | 材质索引 | SkeletalMeshLODModel.h 第 25 行 |
| BaseIndex | uint32 | 索引缓冲起始位置 | SkeletalMeshLODModel.h 第 28 行 |
| NumTriangles | uint32 | 三角形数量 | SkeletalMeshLODModel.h 第 31 行 |
| bSelected | uint8 | 是否选中 | SkeletalMeshLODModel.h 第 34 行 |
| bRecomputeTangent | bool | 运行时重新计算切线 | SkeletalMeshLODModel.h 第 37 行 |
| RecomputeTangentsVertexMaskChannel | ESkinVertexColorChannel | 重新计算切线的顶点颜色掩码通道 | SkeletalMeshLODModel.h 第 40 行 |
| bCastShadow | bool | 是否投射阴影 | SkeletalMeshLODModel.h 第 43 行 |
| bVisibleInRayTracing | bool | 是否在光线追踪中可见 | SkeletalMeshLODModel.h 第 46 行 |
| bLegacyClothingSection | bool | 已废弃的布料分段标记 | SkeletalMeshLODModel.h 第 49 行 |
| CorrespondClothSectionIndex_DEPRECATED | int16 | 已废弃的对应布料分段索引 | SkeletalMeshLODModel.h 第 55 行 |
| BaseVertexIndex | uint32 | 该分段顶点在 LOD 顶点缓冲中的偏移 | SkeletalMeshLODModel.h 第 58 行 |
| SoftVertices | TArray&lt;FSoftSkinVertex&gt; | 该分段的软顶点 | SkeletalMeshLODModel.h 第 61 行 |
| ClothMappingDataLODs | TArray&lt;TArray&lt;FMeshToMeshVertData&gt;&gt; | 布料变形映射数据 | SkeletalMeshLODModel.h 第 72 行 |
| BoneMap | TArray&lt;FBoneIndexType&gt; | 影响骨骼列表（RefSkeleton 中的骨骼索引） | SkeletalMeshLODModel.h 第 75 行 |
| NumVertices | int32 | 该分段顶点数 | SkeletalMeshLODModel.h 第 78 行 |
| MaxBoneInfluences | int32 | 该分段最大骨骼影响数 | SkeletalMeshLODModel.h 第 81 行 |
| bUse16BitBoneIndex | bool | 是否使用 16 位骨骼索引 | SkeletalMeshLODModel.h 第 84 行 |
| CorrespondClothAssetIndex | int16 | 对应布料资产索引 | SkeletalMeshLODModel.h 第 87 行 |
| ClothingData | FClothingSectionData | 布料数据 | SkeletalMeshLODModel.h 第 90 行 |
| OverlappingVertices | TMap&lt;int32, TArray&lt;int32&gt;&gt; | 共享相同位置的顶点映射 | SkeletalMeshLODModel.h 第 93 行 |
| bDisabled | bool | 是否禁用该分段 | SkeletalMeshLODModel.h 第 96 行 |
| GenerateUpToLodIndex | int32 | 生成低质量 LOD 时的包含级别 | SkeletalMeshLODModel.h 第 102 行 |
| OriginalDataSectionIndex | int32 | 原始导入数据中的分段索引 | SkeletalMeshLODModel.h 第 110 行 |
| ChunkedParentSectionIndex | int32 | 如果是 BONE 分块产生的分段，父分段索引 | SkeletalMeshLODModel.h 第 118 行 |

## FSkelMeshRenderSection 运行时渲染分段字段表

> 位于 `SkeletalMeshLODRenderData.h`，运行时渲染使用。与编辑器模式 `FSkelMeshSection` 结构不同（无 SoftVertices、无 OverlappingVertices）。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | uint16 | 材质索引 | SkeletalMeshLODRenderData.h 第 30 行 |
| BaseIndex | uint32 | 索引缓冲起始位置 | SkeletalMeshLODRenderData.h 第 33 行 |
| NumTriangles | uint32 | 三角形数量 | SkeletalMeshLODRenderData.h 第 36 行 |
| bRecomputeTangent | bool | 运行时重新计算切线 | SkeletalMeshLODRenderData.h 第 39 行 |
| bCastShadow | bool | 是否投射阴影 | SkeletalMeshLODRenderData.h 第 42 行 |
| bVisibleInRayTracing | bool | 是否在光线追踪中可见 | SkeletalMeshLODRenderData.h 第 45 行 |
| RecomputeTangentsVertexMaskChannel | ESkinVertexColorChannel | 重新计算切线的顶点颜色掩码通道 | SkeletalMeshLODRenderData.h 第 48 行 |
| BaseVertexIndex | uint32 | 该分段顶点在 LOD 顶点缓冲中的偏移 | SkeletalMeshLODRenderData.h 第 51 行 |
| ClothMappingData_DEPRECATED | TArray&lt;FMeshToMeshVertData&gt; | 已废弃的布料映射数据 | SkeletalMeshLODRenderData.h 第 54 行 |
| ClothMappingDataLODs | TArray&lt;TArray&lt;FMeshToMeshVertData&gt;&gt; | 布料变形映射数据 | SkeletalMeshLODRenderData.h 第 65 行 |
| BoneMap | TArray&lt;FBoneIndexType&gt; | 影响骨骼列表 | SkeletalMeshLODRenderData.h 第 68 行 |
| NumVertices | uint32 | 该分段顶点数 | SkeletalMeshLODRenderData.h 第 71 行 |
| MaxBoneInfluences | int32 | 最大骨骼影响数 | SkeletalMeshLODRenderData.h 第 74 行 |
| CorrespondClothAssetIndex | int16 | 对应布料资产索引 | SkeletalMeshLODRenderData.h 第 77 行 |
| ClothingData | FClothingSectionData | 布料数据 | SkeletalMeshLODRenderData.h 第 80 行 |

## FSkeletalMaterial 骨骼网格材质槽

> 定义在 `SkinnedAssetCommon.h`，不在 `SkeletalMesh.h`。

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

> **修正**：原 wiki 称骨骼网格材质槽无 `ImportedMaterialSlotName` 字段，实际在 `WITH_EDITORONLY_DATA` 下存在该字段。原 wiki 引用的 `FMeshUVChannelInfo` 作为 `UVChannelData` 字段不存在于 `FSkeletalMaterial` 中。

## FSkeletalMeshLODRenderData 运行时 LOD 渲染数据字段表

> 定义在 `SkeletalMeshLODRenderData.h`，运行时渲染使用。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| RenderSections | TArray&lt;FSkelMeshRenderSection&gt; | 渲染分段数组 | SkeletalMeshLODRenderData.h |
| StaticVertexBuffers | FStaticMeshVertexBuffers | 静态顶点缓冲 | SkeletalMeshLODRenderData.h |
| SkinWeightVertexBuffer | FSkinWeightVertexBuffer | 皮肤权重缓冲 | SkeletalMeshLODRenderData.h |
| MultiSizeIndexContainer | FRawStaticIndexBuffer | 索引缓冲容器 | SkeletalMeshLODRenderData.h |
| ActiveBoneIndices | TArray&lt;FBoneIndexType&gt; | 活跃骨骼列表 | SkeletalMeshLODRenderData.h |
| ClothVertexBuffer | FSkeletalMeshVertexClothBuffer | 布料顶点缓冲 | SkeletalMeshLODRenderData.h |
| DuplicatedVerticesBuffer | FSkeletalMeshDuplicatedVerticesBuffer | 重复顶点缓冲 | SkeletalMeshLODRenderData.h |
| MorphVertexInfoBuffers | FMorphTargetVertexInfoBuffers | 变形目标顶点信息 | SkeletalMeshLODRenderData.h |
| HalfEdgeBuffer | FSkeletalMeshHalfEdgeBuffer | 半边缓冲 | SkeletalMeshLODRenderData.h |
| VertexAttributes | TArray&lt;FSkeletalMeshVertexAttributeBuffer&gt; | 顶点属性缓冲 | SkeletalMeshLODRenderData.h |
| NumTexCoords | uint32 | UV 通道数量 | SkeletalMeshLODRenderData.h |

## FSkeletalMeshRenderData 渲染数据容器字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LODRenderData | TIndirectArray&lt;FSkeletalMeshLODRenderData&gt; | LOD 渲染数据数组 | SkeletalMeshRenderData.h |
| MinLODThreshold | int32 | 最小 LOD 阈值 | SkeletalMeshRenderData.h |
| MaxLODThreshold | int32 | 最大 LOD 阈值 | SkeletalMeshRenderData.h |

## 骨骼网格与静态网格的关系

骨骼网格复用静态网格的顶点缓冲结构（FStaticMeshVertexBuffers），但额外包含：
- SkinWeightVertexBuffer: 皮肤权重数据
- ActiveBoneIndices: 该 LOD 活跃骨骼列表
- MorphTargets: 变形目标数组
- ClothVertexBuffer: 布料顶点缓冲（可选）
- DuplicatedVerticesBuffer: 重复顶点缓冲

## 源码引用

- Runtime/Engine/Classes/Engine/SkeletalMesh.h — USkeletalMesh 主类定义（3249 行）
- Runtime/Engine/Classes/Engine/SkinnedAssetCommon.h — FSkeletalMaterial 定义
- Runtime/Engine/Public/Rendering/SkeletalMeshLODModel.h — FSkeletalMeshLODModel 和 FSkelMeshSection（编辑器模式）定义
- Runtime/Engine/Public/Rendering/SkeletalMeshLODRenderData.h — FSkelMeshRenderSection 和 FSkeletalMeshLODRenderData（运行时）定义
- Runtime/Engine/Public/Rendering/SkeletalMeshRenderData.h — FSkeletalMeshRenderData 定义
- Runtime/Engine/Private/Engine/SkeletalMesh.cpp — 序列化实现

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| TObjectPtr | 智能指针替代原始指针 |
| MorphTargets 增强 | 更多变形目标支持 |
| Nanite 支持 | 骨骼网格 Nanite 实验性支持（EditorOnly） |
| CachedComposedRefPoseMatrices | 缓存参考姿势矩阵 |
| ESkeletalMeshAsyncProperties | 异步属性枚举，支持异步构建 |
| FSkinnedAssetCompilationContext | 异步编译上下文 |
| RayTracingMinLOD | 光线追踪最小 LOD 控制 |
| ClothLODBiasMode | 布料 LOD 偏差模式 |
| ShadowPhysicsAsset | 胶囊阴影物理资产 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 原始指针 | USkeleton* 直接引用 |
| Materials 数组 | 简单材质槽数组 |
| SkelMirrorTable | 骨骼镜像表（已废弃） |
| bUseFullPrecisionUVs | 使用全精度 UV |
| bUseHighPrecisionTangentBasis | 使用高精度切线基础 |
