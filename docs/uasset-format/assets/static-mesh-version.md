# 静态网格版本差异

## 概述

静态网格结构随 UE 版本演进，UE5 引入 Nanite、TObjectPtr、平台相关 LOD、异步编译等新特性。解析静态网格时需检查版本号以选择正确的字段读取方式。

## 关键版本变更

### UE5 新增特性

| 特性 | 版本 | 说明 | 源码位置 |
|------|------|------|----------|
| Nanite 数据 | UE5.0 | NaniteResourcesPtr 字段新增 | StaticMeshResources.h 第 791 行 |
| TObjectPtr | UE5.0 | 智能指针替代原始指针 | StaticMesh.h 第 506-507 行 |
| PerPlatform LOD | UE5.0 | FPerPlatformInt/FPerPlatformFloat | StaticMesh.h 第 952-955 行 |
| ImportedMaterialSlotName | UE5.0 | 材质重映射支持 | StaticMesh.h 第 514-515 行 |
| OverlayMaterialInterface | UE5.0 | 覆盖材质支持 | StaticMesh.h 第 521-522 行 |
| RayTracingGeometry | UE5.0 | 光线追踪几何 | StaticMeshResources.h 第 439 行 |
| RenderData 私有化 | UE5.0 | 标记 UE_DEPRECATED，强制使用 GetRenderData/SetRenderData | StaticMesh.h 第 621-623 行 |
| StaticMaterials 私有化 | UE5.0 | 标记 UE_DEPRECATED，通过 BlueprintGetter/Setter 管理 | StaticMesh.h 第 1076-1077 行 |
| 异步编译支持 | UE5.x | IInterface_AsyncCompilation、LockedProperties、FStaticMeshAsyncBuildWorker | StaticMesh.h 第 610-221 行 |
| FPerQualityLevelInt | UE5.x | 按质量等级覆盖 MinLOD | StaticMesh.h 第 878-881 行 |
| DistanceFieldData | UE5.x | 距离场体积数据 | StaticMeshResources.h 第 433 行 |
| CardRepresentationData | UE5.x | Nanite 卡片表示数据 | StaticMeshResources.h 第 436 行 |
| bVisibleInRayTracing | UE5.x | Section 级别光线追踪可见性 | StaticMeshResources.h 第 218 行 |
| bAffectDistanceFieldLighting | UE5.x | Section 级别距离场光照 | StaticMeshResources.h 第 220 行 |
| bForceOpaque | UE5.x | Section 级别光线追踪强制不透明 | StaticMeshResources.h 第 222 行 |
| AdditionalIndexBuffers | UE5.x | 额外索引缓冲（反向索引、线框索引） | StaticMeshResources.h 第 494 行 |
| ChaosConvex | UE5.0 | FKConvexElem 使用 Chaos 物理引擎 | ConvexElem.h 第 51 行 |
| Transform 字段 | UE5.x | FKConvexElem 增加独立 Transform 管理 | ConvexElem.h 第 48-49 行 |
| LevelSetElems | UE5.x | LevelSet 碰撞支持 | AggregateGeom.h 第 43 行 |
| SkinnedLevelSetElems | UE5.x | 实验性骨骼 LevelSet 碰撞 | AggregateGeom.h 第 46 行 |
| FStaticMaterialMinimalInfo | UE5.x | 轻量级材质信息缓存 | StaticMesh.h 第 526-536 行 |

### UE4 关键变更

| 特性 | 版本 | 说明 | 源码位置 |
|------|------|------|----------|
| LODGroup | UE4.22 | LOD 组设置新增 | StaticMesh.h 第 688-690 行 |
| MaterialIndexToImportIndex | UE4.23 | 材质索引映射 | StaticMeshResources.h |
| bAutoComputeLODScreenSize | UE4.25 | 自动计算 LOD 阈值 | StaticMesh.h 第 712 行 |
| Materials_DEPRECATED | UE4.x | 旧版材质数组 TArray&lt;UMaterialInterface*&gt; | StaticMesh.h 第 729-731 行 |

## 废弃字段

| 字段名 | 废弃版本 | 替代字段 | 源码位置 |
|--------|----------|----------|----------|
| Materials_DEPRECATED (TArray&lt;UMaterialInterface*&gt;) | UE5.0 | StaticMaterials (TArray&lt;FStaticMaterial&gt;) | StaticMesh.h 第 729-731 行 |
| bStripComplexCollisionForConsole_DEPRECATED | UE5.0 | 平台 LOD 设置 | StaticMesh.h |
| SourceModels (直接访问) | UE5.0 | 使用 GetSourceModels() | StaticMesh.h 第 644-647 行 |
| HiResSourceModel (直接访问) | UE5.0 | 使用 Get/SetHiResSourceModel() | StaticMesh.h 第 650-652 行 |
| SectionInfoMap (直接访问) | UE5.0 | 使用 Get/SetSectionInfoMap() | StaticMesh.h 第 663-665 行 |
| OriginalSectionInfoMap (直接访问) | UE5.0 | 使用 Get/SetOriginalSectionInfoMap() | StaticMesh.h 第 675-677 行 |
| LODGroup (直接访问) | UE5.7 | 使用 Get/SetLODGroup() | StaticMesh.h 第 688-690 行 |
| NumStreamedLODs (直接访问) | UE5.7 | 使用 GetNumStreamedLODs() | StaticMesh.h 第 696-698 行 |
| ImportVersion (直接访问) | UE5.7 | 使用 GetImportVersion()/SetImportVersion() | StaticMesh.h 第 701-703 行 |
| MaterialRemapIndexPerImportVersion (直接访问) | UE5.7 | 使用 Get/AddMaterialRemapIndexPerImportVersion() | StaticMesh.h 第 705-707 行 |
| bAutoComputeLODScreenSize (直接访问) | UE5.7 | 使用 Get/SetAutoComputeLODScreenSize() | StaticMesh.h 第 710-712 行 |
| bRequiresLODDistanceConversion (直接访问) | UE5.7 | 使用 Get/SetRequiresLODDistanceConversion() | StaticMesh.h 第 718-719 行 |
| bRequiresLODScreenSizeConversion (直接访问) | UE5.7 | 使用 Get/SetRequiresLODScreenSizeConversion() | StaticMesh.h 第 724-726 行 |
| NaniteSettings (直接访问) | UE5.7 | 使用 Get/SetNaniteSettings() | StaticMesh.h 第 734-736 行 |
| LightmapUVVersion (直接访问) | UE5.0 | 使用 GetLightmapUVVersion()/SetLightmapUVVersion() | StaticMesh.h 第 741-743 行 |
| MinLOD (直接访问) | UE4.27 | 使用 GetMinLOD()/SetMinLOD() | StaticMesh.h 第 952-955 行 |
| GetVolume (FKConvexElem) | UE5.1 | GetScaledVolume() | ConvexElem.h 第 97-98 行 |
| SetChaosConvexMesh | UE5.4 | SetConvexMeshObject() | ConvexElem.h 第 115-116 行 |

## EImportStaticMeshVersion 导入版本枚举

| 版本值 | 说明 |
|--------|------|
| BeforeImportStaticMeshVersionWasAdded | 初始版本 |
| RemoveStaticMeshSkinxxWorkflow | 移除材质重排序工作流 |
| StaticMeshVersionPlusOne | 下一个版本（边界值） |

## FStaticMeshVersion 静态网格版本枚举

关键版本值（具体值见 ObjectVersion.h / UE5MainStreamObjectVersions.inl）：
- 增加 Nanite 数据版本
- TObjectPtr 迁移版本
- 材质重映射版本

## 版本判断机制

解析静态网格时应遵循以下流程：

1. **检查 FileVersionUE**: 确定引擎版本范围
2. **检查 CustomVersion**: 确定静态网格特定版本（FStaticMeshVersion）
3. **检查 EImportStaticMeshVersion**: 确定导入版本，判断是否移除材质重排序工作流
4. **根据版本选择字段读取方式**:
   - TObjectPtr vs 原始指针
   - FPerPlatformFloat vs float
   - Nanite 数据是否存在
5. **忽略废弃字段**: 使用替代字段或默认值

### 版本判断代码位置

StaticMesh.cpp 中使用 `Ar.CustomVer()` 检查版本号：
- FStaticMeshVersion 枚举定义静态网格特定版本
- ObjectVersion.h 定义引擎全局版本
- EImportStaticMeshVersion 定义导入特定版本

详见 [版本兼容机制](../serialization/version-compatibility.md)。

## 源码引用

- Runtime/Core/Public/UObject/ObjectVersion.h — 版本号定义
- Runtime/Core/Public/UObject/UE5MainStreamObjectVersions.inl — UE5 版本定义
- Runtime/Engine/Private/Engine/StaticMesh.cpp — 版本判断代码
- Runtime/Engine/Classes/Engine/StaticMesh.h — 废弃字段标记

## 版本兼容处理建议

解析静态网格时：
1. 优先使用现代字段（TObjectPtr、FPerPlatform）
2. 检查 NaniteSettings.IsValid() 判断 Nanite 数据存在
3. Materials_DEPRECATED 需转换为 FStaticMaterial 数组
4. 旧版 LOD 阈值需转换为 FPerPlatformFloat
5. ImportedMaterialSlotName 缺失时使用 MaterialSlotName
6. 检查 EImportStaticMeshVersion >= RemoveStaticMeshSkinxxWorkflow 判断是否需处理材质重排序
7. UE5.7+ 废弃字段均提供 accessor 方法，外部不应直接访问私有成员
