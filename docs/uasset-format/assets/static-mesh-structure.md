# 静态网格基础结构

## 概述

UStaticMesh 是 UE 引擎中用于存储静态几何体的资产类型。静态网格包含：
- 渲染数据：顶点位置、法线、UV、索引缓冲
- LOD 系统：多级细节数据，通过 ScreenSize 自动切换
- 材质槽：材质引用和 UV 通道信息
- 碰撞数据：简单碰撞和复杂碰撞几何

静态网格不包含动画数据，适用于环境物体、建筑结构等静态场景元素。

## UStaticMesh 主类字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| RenderData | TUniquePtr&lt;FStaticMeshRenderData&gt; | 渲染数据容器（私有，UE_DEPRECATED 5.0，应使用 GetRenderData/SetRenderData 访问） | StaticMesh.h 第 621-623 行 |
| StaticMaterials | TArray&lt;FStaticMaterial&gt; | 材质槽数组（私有，UE_DEPRECATED 5.0，应使用 accessor 访问） | StaticMesh.h 第 1076-1077 行 |
| MinLOD | FPerPlatformInt | 最小 LOD 级别（UE_DEPRECATED 4.27，应使用 GetMinLOD/SetMinLOD） | StaticMesh.h 第 952-955 行 |
| MinQualityLevelLOD | FPerQualityLevelInt | 按质量等级覆盖的 MinLOD | StaticMesh.h 第 878-881 行 |
| LODGroup | FName | LOD 组设置（UE_DEPRECATED 5.7，应使用 Get/SetLODGroup） | StaticMesh.h 第 688-690 行 |
| NaniteSettings | FMeshNaniteSettings | Nanite 设置（UE_DEPRECATED 5.7，应使用 accessor） | StaticMesh.h 第 734-736 行 |
| ElementToIgnoreForTexFactor | int32 | 流式纹理因子忽略的元素索引 | StaticMesh.h 第 1020-1021 行 |
| BodySetup | UBodySetup* | 碰撞体定义（通过 IInterface_CollisionDataProvider 接口） | StaticMesh.h 继承自 IInterface_CollisionDataProvider |

说明：
- UStaticMesh 继承自 `UStreamableRenderAsset`、`IInterface_CollisionDataProvider`、`IInterface_AssetUserData`、`IInterface_AsyncCompilation`（StaticMesh.h 第 592 行）
- RenderData 在 UE5.0 起标记为私有并废弃直接访问，必须通过 `GetRenderData()` / `SetRenderData()` 访问器操作
- StaticMaterials 同样在 UE5.0 标记为私有，通过 BlueprintGetter/Setter 管理

## FStaticMeshRenderData 渲染数据容器字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LODResources | FStaticMeshLODResourcesArray | LOD 资源数组 | StaticMeshResources.h 第 785 行 |
| LODVertexFactories | FStaticMeshVertexFactoriesArray | 顶点工厂数组 | StaticMeshResources.h 第 786 行 |
| ScreenSize | FPerPlatformFloat[MAX_STATIC_MESH_LODS] | LOD 切换阈值 | StaticMeshResources.h 第 789 行 |
| NaniteResourcesPtr | TPimplPtr&lt;Nanite::FResources&gt; | Nanite 数据 | StaticMeshResources.h 第 791 行 |
| RayTracingProxy | FStaticMeshRayTracingProxy* | 光线追踪代理 | StaticMeshResources.h 第 794 行 |
| Bounds | FBoxSphereBounds | 包围盒 | StaticMeshResources.h 第 797 行 |
| bLODsShareStaticLighting | bool | LOD 是否共享静态光照数据 | StaticMeshResources.h 第 813 行 |
| bHasNaniteFallbackMesh | bool | 是否有 Nanite 回退网格 | StaticMeshResources.h 第 815 行 |
| bReadyForStreaming | bool | RHI 资源是否已初始化就绪 | StaticMeshResources.h 第 818 行 |
| NumInlinedLODs | uint8 | 内联 LOD 数量 | StaticMeshResources.h 第 820 行 |
| CurrentFirstLODIdx | uint8 | 当前首个 LOD 索引 | StaticMeshResources.h 第 822 行 |
| LODBiasModifier | uint8 | LOD 偏置修正 | StaticMeshResources.h 第 824 行 |

编辑期字段（WITH_EDITORONLY_DATA）：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| DerivedDataKey | FString | 派生数据键 | StaticMeshResources.h 第 829 行 |
| SupportedPlatforms | TSet&lt;const ITargetPlatform*&gt; | 支持的平台 | StaticMeshResources.h 第 835 行 |
| MaterialIndexToImportIndex | TArray&lt;int32&gt; | 材质索引到导入索引映射 | StaticMeshResources.h 第 840 行 |
| UVChannelDataPerMaterial | TArray&lt;FMeshUVChannelInfo&gt; | 每材质 UV 通道数据 | StaticMeshResources.h 第 843 行 |
| NextCachedRenderData | TUniquePtr&lt;FStaticMeshRenderData&gt; | 下一个缓存的派生数据 | StaticMeshResources.h 第 846 行 |
| CollisionDataForCookedCooker | TUniquePtr&lt;FTriMeshCollisionData&gt; | CookedCooker 平台的碰撞数据 | StaticMeshResources.h 第 852 行 |
| EstimatedCompressedSize | uint64 | 估算的渲染数据压缩大小 | StaticMeshResources.h 第 855 行 |
| EstimatedNaniteTotalCompressedSize | uint64 | 估算的 Nanite 总压缩大小 | StaticMeshResources.h 第 858 行 |
| EstimatedNaniteStreamingCompressedSize | uint64 | 估算的 Nanite 流式压缩大小 | StaticMeshResources.h 第 861 行 |

说明：MAX_STATIC_MESH_LODS = 8（StaticMesh.h 第 59 行常量），最多支持 8 级 LOD。

## FStaticMaterial 材质槽结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 材质对象引用 | StaticMesh.h 第 506-507 行 |
| MaterialSlotName | FName | 材质槽名称（供 gameplay 使用，避免材质数组拓扑变化导致的错误） | StaticMesh.h 第 510-511 行 |
| ImportedMaterialSlotName | FName | 导入时的材质槽名（重新导入时用于排序材质数组） | StaticMesh.h 第 514-515 行 |
| UVChannelData | FMeshUVChannelInfo | UV 通道纹理流式数据 | StaticMesh.h 第 518-519 行 |
| OverlayMaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 覆盖材质引用 | StaticMesh.h 第 521-522 行 |

## 源码引用

- Runtime/Engine/Classes/Engine/StaticMesh.h — UStaticMesh 主类定义、FStaticMaterial 定义
- Runtime/Engine/Public/StaticMeshResources.h — FStaticMeshRenderData、FStaticMeshLODResources 定义
- Runtime/Engine/Private/Engine/StaticMesh.cpp — 序列化实现

## 版本差异

### UE5 新增特性
| 特性 | 版本 | 说明 | 源码位置 |
|------|------|------|----------|
| NaniteResourcesPtr | UE5.0 | Nanite 数据指针 | StaticMeshResources.h 第 791 行 |
| TObjectPtr | UE5.0 | 智能指针替代原始指针 | StaticMesh.h 第 506-507 行 |
| FPerPlatformInt/FPerPlatformFloat | UE5.0 | 平台相关 LOD 控制 | StaticMesh.h 第 952-955 行 |
| ImportedMaterialSlotName | UE5.0 | 材质重映射支持 | StaticMesh.h 第 514-515 行 |
| OverlayMaterialInterface | UE5.0 | 覆盖材质支持 | StaticMesh.h 第 521-522 行 |
| MinQualityLevelLOD | UE5.x | 按质量等级覆盖 MinLOD | StaticMesh.h 第 878-881 行 |
| FPerQualityLevelInt | UE5.x | 质量等级相关的 LOD 控制 | StaticMesh.h 第 880 行 |
| 异步编译支持 | UE5.x | IInterface_AsyncCompilation 接口、LockedProperties | StaticMesh.h 第 610-618 行 |
| RenderData 私有化 | UE5.0 | 标记 UE_DEPRECATED，强制使用 accessor | StaticMesh.h 第 621-623 行 |

### UE4 特性
- 使用简单 MinLOD 整数值
- Materials_DEPRECATED 旧版材质数组（仅存储材质对象指针）
- RenderData 为公共成员直接访问
