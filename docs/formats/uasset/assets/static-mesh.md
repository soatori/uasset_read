# 静态网格文档（修订版）

静态网格资产类型 (UStaticMesh) 相关文档导航。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| static-mesh-structure.md | 基础结构 | UStaticMesh 和 FStaticMeshRenderData 字段 |
| static-mesh-lod.md | LOD 数据 | FStaticMeshLODResources 和切换机制 |
| static-mesh-vertex.md | 顶点数据 | 顶点缓冲、UV 通道、索引缓冲 |
| static-mesh-material.md | 材质槽 | FStaticMaterial 和 Section 材质索引 |
| static-mesh-collision.md | 碰撞数据 | UBodySetup 和碰撞几何类型 |
| static-mesh-version.md | 版本差异 | UE4/UE5 结构变更 |

## 核心源码

- Runtime/Engine/Classes/Engine/StaticMesh.h — UStaticMesh 主类定义、FStaticMaterial 定义、FMeshSectionInfo 定义、EImportStaticMeshVersion 枚举
- Runtime/Engine/Public/StaticMeshResources.h — FStaticMeshRenderData、FStaticMeshLODResources、FStaticMeshSection、FStaticMeshVertexBuffers 定义、MAX_STATIC_MESH_LODS 常量
- Runtime/Engine/Private/Engine/StaticMesh.cpp — 序列化实现

---

# 静态网格基础结构（修订版）

## UStaticMesh 主类字段表

### 核心渲染与数据字段

| 字段名 | 类型 | 用途 | 源码位置 | 版本标记 |
|--------|------|------|----------|----------|
| RenderData | TUniquePtr&lt;FStaticMeshRenderData&gt; | 渲染数据容器 | StaticMesh.h:623 | UE_DEPRECATED(5.0) |
| StaticMaterials | TArray&lt;FStaticMaterial&gt; | 材质槽数组 | StaticMesh.h:1077 | UE_DEPRECATED(5.0) |
| BodySetup | TObjectPtr&lt;UBodySetup&gt; | 碰撞体定义 | StaticMesh.h:1238 | UE_DEPRECATED(5.0) |
| SourceModels | TArray&lt;FStaticMeshSourceModel&gt; | 导入原始网格数据（仅编辑器） | StaticMesh.h:647 | UE_DEPRECATED(5.0) |
| HiResSourceModel | FStaticMeshSourceModel | 高精度源数据（仅编辑器） | StaticMesh.h:652 | UE_DEPRECATED(5.0) |
| SectionInfoMap | FMeshSectionInfoMap | LOD+Section 到材质的映射（仅编辑器） | StaticMesh.h:665 | UE_DEPRECATED(5.0) |
| OriginalSectionInfoMap | FMeshSectionInfoMap | 原始 Section 映射（仅编辑器） | StaticMesh.h:677 | UE_DEPRECATED(5.0) |

### LOD 与平台配置字段

| 字段名 | 类型 | 用途 | 源码位置 | 版本标记 |
|--------|------|------|----------|----------|
| LODGroup | FName | LOD 组设置 | StaticMesh.h:690 | UE_DEPRECATED(5.7) |
| NumStreamedLODs | FPerPlatformInt | 最大流式 LOD 数量 | StaticMesh.h:698 | UE_DEPRECATED(5.7) |
| MinLOD | FPerPlatformInt | 最小 LOD 级别 | StaticMesh.h:955 | UE_DEPRECATED(4.27) |
| MinQualityLevelLOD | FPerQualityLevelInt | 按质量级别的最小 LOD | StaticMesh.h:881 | — |
| bAutoComputeLODScreenSize | uint8:1 | 自动计算 LOD 屏幕尺寸 | StaticMesh.h:712 | UE_DEPRECATED(5.7) |
| bRequiresLODDistanceConversion | uint8:1 | 需要 LOD 距离转换 | StaticMesh.h:719 | UE_DEPRECATED(5.7) |
| bRequiresLODScreenSizeConversion | uint8:1 | 需要 LOD 屏幕尺寸转换 | StaticMesh.h:726 | UE_DEPRECATED(5.7) |
| ImportVersion | int32 | 最后导入版本号 | StaticMesh.h:703 | UE_DEPRECATED(5.7) |
| MaterialRemapIndexPerImportVersion | TArray&lt;FMaterialRemapIndex&gt; | 材质重映射索引 | StaticMesh.h:707 | UE_DEPRECATED(5.7) |

### 光照贴图字段

| 字段名 | 类型 | 用途 | 源码位置 | 版本标记 |
|--------|------|------|----------|----------|
| LightMapResolution | int32 | 光照贴图分辨率 | StaticMesh.h:1158 | UE_DEPRECATED(4.27) |
| LightMapCoordinateIndex | int32 | 光照贴图坐标索引（0-3） | StaticMesh.h:1186 | UE_DEPRECATED(4.27) |
| LightmapUVDensity | float | 光照贴图 UV 密度 | StaticMesh.h:1138 | UE_DEPRECATED(5.0) |
| LightmapUVVersion | int32 | 光照贴图 UV 生成版本（仅编辑器） | StaticMesh.h:743 | UE_DEPRECATED(5.0) |

### 碰撞与物理字段

| 字段名 | 类型 | 用途 | 源码位置 | 版本标记 |
|--------|------|------|----------|----------|
| LODForCollision | int32 | 碰撞使用的 LOD 级别 | StaticMesh.h:1269 | — |
| bGenerateMeshDistanceField | uint8:1 | 是否生成网格距离场 | StaticMesh.h:1276 | — |
| bHasNavigationData | uint8:1 | 是否有导航数据（NavCollision） | StaticMesh.h:1286 | — |
| bStripComplexCollisionForConsole_DEPRECATED | uint8:1 | 废弃：剥离控制台复杂碰撞 | StaticMesh.h:1281 | DEPRECATED |
| bCustomizedCollision | bool | 自定义碰撞标志（仅编辑器） | StaticMesh.h:1445 | UE_DEPRECATED(5.7) |
| ComplexCollisionMesh | TObjectPtr&lt;UStaticMesh&gt; | 复杂碰撞网格引用（仅编辑器） | StaticMesh.h:1594 | WITH_EDITORONLY_DATA |

### 渲染与采样字段

| 字段名 | 类型 | 用途 | 源码位置 | 版本标记 |
|--------|------|------|----------|----------|
| bSupportRayTracing | uint8:1 | 光线追踪支持 | StaticMesh.h:1367 | — |
| bAllowCPUAccess | uint8:1 | 允许 CPU 访问几何数据 | StaticMesh.h:1404 | — |
| bSupportUniformlyDistributedSampling | uint8:1 | 均匀分布采样支持 | StaticMesh.h:1294 | — |
| bSupportPhysicalMaterialMasks | uint8:1 | 物理材质遮罩支持 | StaticMesh.h:1302 | — |
| bSupportGpuUniformlyDistributedSampling | uint8:1 | GPU 均匀采样支持 | StaticMesh.h:1411 | — |
| bDoFastBuild | uint8:1 | 快速构建标志 | StaticMesh.h:1375 | — |
| bRenderingResourcesInitialized | uint8:1 | 渲染资源已初始化 | StaticMesh.h:1396 | — |
| NaniteSettings | FMeshNaniteSettings | Nanite 设置 | StaticMesh.h:736 | UE_DEPRECATED(5.7) |
| RayTracingProxySettings | FMeshRayTracingProxySettings | 光线追踪代理设置（仅编辑器） | StaticMesh.h:1331 | UE_DEPRECATED(5.7) |
| bUseLegacyTangentScaling | uint8:1 | 旧版切线缩放（仅编辑器） | StaticMesh.h:1309 | UE_DEPRECATED(5.4) |

### 网格绘制字段

| 字段名 | 类型 | 用途 | 源码位置 | 版本标记 |
|--------|------|------|----------|----------|
| StaticMeshPaintSupport | EStaticMeshPaintSupport | 纹理颜色网格绘制支持 | StaticMesh.h:1213 | — |
| MeshPaintTextureCoordinateIndex | int32 | 网格绘制纹理坐标索引 | StaticMesh.h:1220 | — |
| MeshPaintTextureResolution | int32 | 网格绘制纹理分辨率 | StaticMesh.h:1228 | — |

### 元数据与编辑器字段

| 字段名 | 类型 | 用途 | 源码位置 | 版本标记 |
|--------|------|------|----------|----------|
| AssetImportData | TObjectPtr&lt;UAssetImportData&gt; | 资产导入数据（仅编辑器） | StaticMesh.h:1420 | UE_DEPRECATED(5.7) |
| SourceFilePath_DEPRECATED | FString | 废弃：源文件路径（仅编辑器） | StaticMesh.h:1425 | UE_DEPRECATED(5.7) |
| SourceFileTimestamp_DEPRECATED | FString | 废弃：源文件时间戳（仅编辑器） | StaticMesh.h:1430 | UE_DEPRECATED(5.7) |
| ThumbnailInfo | TObjectPtr&lt;UThumbnailInfo&gt; | 缩略图信息（仅编辑器） | StaticMesh.h:1435 | UE_DEPRECATED(5.7) |
| EditorCameraPosition | FAssetEditorOrbitCameraPosition | 编辑器相机位置（仅编辑器） | StaticMesh.h:1440 | UE_DEPRECATED(5.7) |
| LightingGuid | FGuid | 光照缓存 GUID | StaticMesh.h:1451 | UE_DEPRECATED(5.0) |
| Sockets | TArray&lt;TObjectPtr&lt;UStaticMeshSocket&gt;&gt; | 插槽数组 | StaticMesh.h:1482 | — |
| PositiveBoundsExtension | FVector | 正方向包围盒扩展 | StaticMesh.h:1490 | UE_DEPRECATED(4.27) |
| NegativeBoundsExtension | FVector | 负方向包围盒扩展 | StaticMesh.h:1518 | UE_DEPRECATED(4.27) |
| ExtendedBounds | FBoxSphereBounds | 扩展后包围盒 | StaticMesh.h:1546 | UE_DEPRECATED(5.0) |
| AssetUserData | TArray&lt;TObjectPtr&lt;UAssetUserData&gt;&gt; | 用户数据数组 | StaticMesh.h:1581 | — |
| DistanceFieldSelfShadowBias | float | 距离场自阴影偏移 | StaticMesh.h:1232 | — |
| ElementToIgnoreForTexFactor | int32 | 流式纹理因子忽略元素 | StaticMesh.h:1021 | — |
| EditableMesh_DEPRECATED | TObjectPtr&lt;UObject&gt; | 废弃：可编辑网格（仅编辑器） | StaticMesh.h:1591 | DEPRECATED |
| bIsBuiltAtRuntime_DEPRECATED | uint8:1 | 废弃：运行时构建标志 | StaticMesh.h:1380 | UE_DEPRECATED(5.0) |

## FStaticMeshRenderData 渲染数据容器字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LODResources | FStaticMeshLODResourcesArray | LOD 资源数组 | StaticMeshResources.h:785 |
| LODVertexFactories | FStaticMeshVertexFactoriesArray | 顶点工厂数组 | StaticMeshResources.h:786 |
| ScreenSize | FPerPlatformFloat[MAX_STATIC_MESH_LODS] | LOD 切换阈值 | StaticMeshResources.h:789 |
| NaniteResourcesPtr | TPimplPtr&lt;Nanite::FResources&gt; | Nanite 数据 | StaticMeshResources.h:791 |
| RayTracingProxy | FStaticMeshRayTracingProxy* | 光线追踪代理 | StaticMeshResources.h:794 |
| Bounds | FBoxSphereBounds | 包围盒 | StaticMeshResources.h:797 |
| bLODsShareStaticLighting | bool | LOD 是否共享静态光照 | StaticMeshResources.h:813 |
| bHasNaniteFallbackMesh | bool | 是否有 Nanite 回退网格 | StaticMeshResources.h:815 |
| bReadyForStreaming | bool | 是否准备好流式加载 | StaticMeshResources.h:818 |
| NumInlinedLODs | uint8 | 内联 LOD 数量 | StaticMeshResources.h:820 |
| CurrentFirstLODIdx | uint8 | 当前首个 LOD 索引 | StaticMeshResources.h:822 |
| LODBiasModifier | uint8 | LOD 偏移修正 | StaticMeshResources.h:824 |

仅编辑器数据（WITH_EDITORONLY_DATA）：
| DerivedDataKey | FString | 派生数据键 | StaticMeshResources.h:829 |
| SupportedPlatforms | TSet&lt;const ITargetPlatform*&gt; | 支持的平台集合 | StaticMeshResources.h:835 |
| MaterialIndexToImportIndex | TArray&lt;int32&gt; | 材质索引到导入索引映射 | StaticMeshResources.h:840 |
| UVChannelDataPerMaterial | TArray&lt;FMeshUVChannelInfo&gt; | 每材质 UV 通道数据 | StaticMeshResources.h:843 |
| NextCachedRenderData | TUniquePtr&lt;FStaticMeshRenderData&gt; | 下一个缓存渲染数据 | StaticMeshResources.h:846 |
| CollisionDataForCookedCooker | TUniquePtr&lt;FTriMeshCollisionData&gt; | CookedCooker 碰撞数据 | StaticMeshResources.h:852 |
| EstimatedCompressedSize | uint64 | 估算压缩总大小 | StaticMeshResources.h:855 |
| EstimatedNaniteTotalCompressedSize | uint64 | 估算 Nanite 压缩总大小 | StaticMeshResources.h:858 |
| EstimatedNaniteStreamingCompressedSize | uint64 | 估算 Nanite 流式压缩大小 | StaticMeshResources.h:861 |
| bForceGenerateNaniteFallbackMesh | bool | 强制生成 Nanite 回退网格 | StaticMeshResources.h:864 |

说明：
- MAX_STATIC_MESH_LODS = 8（StaticMeshResources.h:59），最多支持 8 级 LOD
- NumInlinedLODs 和 CurrentFirstLODIdx 是 LOD 流式加载的核心控制字段
- RayTracingProxy 是顶层光线追踪代理，与 FStaticMeshLODResources 中的 RayTracingGeometry（每 LOD 的几何数据）是不同层级的概念

## FStaticMaterial 材质槽结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 材质对象引用 | StaticMesh.h:507 |
| MaterialSlotName | FName | 材质槽名称 | StaticMesh.h:511 |
| ImportedMaterialSlotName | FName | 导入时的材质槽名（仅编辑器） | StaticMesh.h:515 |
| UVChannelData | FMeshUVChannelInfo | UV 通道信息 | StaticMesh.h:519 |
| OverlayMaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 覆盖材质引用 | StaticMesh.h:522 |

说明：ImportedMaterialSlotName 位于 #if WITH_EDITORONLY_DATA 保护下，Cooked 资产中不包含此字段。

---

# 静态网格 LOD 数据（修订版）

## FStaticMeshLODResources 字段表

### 核心渲染数据字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Sections | FStaticMeshSectionArray | 渲染分段数组 | StaticMeshResources.h:430 |
| VertexBuffers | FStaticMeshVertexBuffers | 顶点缓冲容器 | StaticMeshResources.h:486 |
| IndexBuffer | FRawStaticIndexBuffer | 三角形索引缓冲 | StaticMeshResources.h:489 |
| DepthOnlyIndexBuffer | FRawStaticIndexBuffer | 深度通道索引 | StaticMeshResources.h:492 |
| AdditionalIndexBuffers | FAdditionalStaticMeshIndexBuffers* | 额外索引缓冲 | StaticMeshResources.h:494 |
| StreamingBulkData | FByteBulkData | 流式加载数据 | StaticMeshResources.h:471 |

### 包围盒与 LOD 偏差字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SourceMeshBounds | FBoxSphereBounds | LOD 源网格包围盒 | StaticMeshResources.h:442 |
| MaxDeviation | float | LOD 与基网格最大偏差 | StaticMeshResources.h:445 |

### 标志位字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bHasDepthOnlyIndices | uint32:1 | 是否有深度专用索引 | StaticMeshResources.h:448 |
| bHasReversedIndices | uint32:1 | 是否有反向索引 | StaticMeshResources.h:451 |
| bHasReversedDepthOnlyIndices | uint32:1 | 是否有反向深度索引 | StaticMeshResources.h:454 |
| bHasColorVertexData | uint32:1 | 是否有顶点颜色数据 | StaticMeshResources.h:456 |
| bHasWireframeIndices | uint32:1 | 是否有线框索引 | StaticMeshResources.h:458 |
| bBuffersInlined | uint32:1 | 顶点索引数据内联标志 | StaticMeshResources.h:461 |
| bIsOptionalLOD | uint32:1 | 可选 LOD 标志 | StaticMeshResources.h:464 |

### 统计与缓冲字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| DepthOnlyNumTriangles | uint32 | 深度通道三角形数 | StaticMeshResources.h:466 |
| BuffersSize | uint32 | 顶点和索引缓冲区总大小 | StaticMeshResources.h:469 |

### 辅助数据字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| DistanceFieldData | FDistanceFieldVolumeData* | 距离场数据 | StaticMeshResources.h:433 |
| CardRepresentationData | FCardRepresentationData* | 卡片表示数据（Lumen） | StaticMeshResources.h:436 |
| RayTracingGeometry | FRayTracingGeometry* | 光线追踪几何 | StaticMeshResources.h:439 |
| AreaWeightedSampler | FStaticMeshAreaWeightedSectionSampler | 面积加权分段采样器 | StaticMeshResources.h:497 |
| AreaWeightedSectionSamplers | FStaticMeshSectionAreaWeightedTriangleSamplerArray | 分段三角形面积加权采样器数组 | StaticMeshResources.h:499 |

仅编辑器数据（WITH_EDITOR / WITH_EDITORONLY_DATA）：
| BulkData | FByteBulkData | 编辑器 BulkData | StaticMeshResources.h:478 |
| DerivedDataKey | FString | 派生数据键 | StaticMeshResources.h:480 |
| WedgeMap | TArray&lt;int32&gt; | Wedge 到顶点索引映射 | StaticMeshResources.h:483 |

说明：FStaticMeshLODResources 继承自 FRefCountBase（StaticMeshResources.h:425），使用引用计数管理生命周期以支持 LOD 流式加载。

## FStaticMeshSection 渲染分段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | int32 | 材质槽索引 | StaticMeshResources.h:204 |
| FirstIndex | uint32 | 索引缓冲起始位置 | StaticMeshResources.h:207 |
| NumTriangles | uint32 | 三角形数量 | StaticMeshResources.h:208 |
| MinVertexIndex | uint32 | 最小顶点索引 | StaticMeshResources.h:209 |
| MaxVertexIndex | uint32 | 最大顶点索引 | StaticMeshResources.h:210 |
| bEnableCollision | bool | 碰撞启用标志 | StaticMeshResources.h:213 |
| bCastShadow | bool | 阴影投射标志 | StaticMeshResources.h:216 |
| bVisibleInRayTracing | bool | 光线追踪可见性 | StaticMeshResources.h:218 |
| bAffectDistanceFieldLighting | bool | 距离场光照影响 | StaticMeshResources.h:220 |
| bForceOpaque | bool | 强制不透明（光线追踪） | StaticMeshResources.h:222 |

仅编辑器数据（WITH_EDITORONLY_DATA）：
| UVDensities | float[MAX_STATIC_TEXCOORDS] | 各 UV 通道密度 | StaticMeshResources.h:225 |
| Weights | float[MAX_STATIC_TEXCOORDS] | UV 密度面积权重 | StaticMeshResources.h:228 |

## LOD 切换机制

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ScreenSize | FPerPlatformFloat[MAX_STATIC_MESH_LODS] | LOD 切换屏幕尺寸阈值 | StaticMeshResources.h:789 |
| MAX_STATIC_MESH_LODS | 常量 = 8 | LOD 最大级数 | StaticMeshResources.h:59 |

说明：ScreenSize[i] 表示当物体屏幕投影尺寸小于该值时切换到 LOD i+1。

## FStaticMeshVertexBuffers 顶点缓冲容器

| 子缓冲 | 类型 | 内容 | 源码位置 |
|--------|------|------|----------|
| StaticMeshVertexBuffer | FStaticMeshVertexBuffer | 法线/UV/切线 | StaticMeshResources.h:322 |
| PositionVertexBuffer | FPositionVertexBuffer | 顶点位置 | StaticMeshResources.h:325 |
| ColorVertexBuffer | FColorVertexBuffer | 顶点颜色 | StaticMeshResources.h:328 |

注意：源码中子缓冲的实际声明顺序为 StaticMeshVertexBuffer → PositionVertexBuffer → ColorVertexBuffer。

---

# 静态网格版本差异（修订版）

## EImportStaticMeshVersion 枚举

定义位置：StaticMesh.h:538-546

| 枚举值 | 数值 | 说明 |
|--------|------|------|
| BeforeImportStaticMeshVersionWasAdded | 0 | 版本控制添加前 |
| RemoveStaticMeshSkinxxWorkflow | 1 | 移除材质重排序工作流 |
| LastVersion | 1 | 最新版本 |

注意：源码中枚举名为 EImportStaticMeshVersion，不是 FStaticMeshVersion。

## 关键版本变更

### UE5.7 废弃的字段

以下字段在 UE 5.7 中标记为 UE_DEPRECATED(5.7)，正在从公共接口迁移到私有接口，应通过访问器函数访问：
- LODGroup → GetLODGroup()/SetLODGroup()
- NumStreamedLODs → GetNumStreamedLODs()
- ImportVersion → GetImportVersion()/SetImportVersion()
- MaterialRemapIndexPerImportVersion → GetMaterialRemapIndexPerImportVersion()
- bAutoComputeLODScreenSize → GetAutoComputeLODScreenSize()/SetAutoComputeLODScreenSize()
- NaniteSettings → GetNaniteSettings()/SetNaniteSettings()
- AssetImportData → GetAssetImportData()/SetAssetImportData()
- ThumbnailInfo → GetThumbnailInfo()/SetThumbnailInfo()
- EditorCameraPosition → GetEditorCameraPosition()/SetEditorCameraPosition()
- bCustomizedCollision → GetCustomizedCollision()/SetCustomizedCollision()
- RayTracingProxySettings → GetRayTracingProxySettings()/SetRayTracingProxySettings()

### UE5.0 废弃的字段

以下字段在 UE 5.0 中标记为 UE_DEPRECATED(5.0)：
- RenderData → GetRenderData()/SetRenderData()
- StaticMaterials → GetStaticMaterials()/SetStaticMaterials()
- BodySetup → GetBodySetup()/SetBodySetup()
- SourceModels → GetSourceModels()（仅编辑器）
- Materials_DEPRECATED → 被 StaticMaterials 替代
- bIsBuiltAtRuntime_DEPRECATED → IsBuiltAtRuntime() 始终返回 false
- LightingGuid → GetLightingGuid()/SetLightingGuid()
- LightmapUVDensity → SetLightmapUVDensity()/GetLightmapUVDensity()
- ExtendedBounds → GetExtendedBounds()/SetExtendedBounds()

### UE4.27 废弃的字段

以下字段在 UE 4.27 中标记为 UE_DEPRECATED(4.27)：
- MinLOD → GetMinLOD()/SetMinLOD()
- LightMapResolution → GetLightMapResolution()/SetLightMapResolution()
- LightMapCoordinateIndex → GetLightMapCoordinateIndex()/SetLightMapCoordinateIndex()
- PositiveBoundsExtension → GetPositiveBoundsExtension()/SetPositiveBoundsExtension()
- NegativeBoundsExtension → GetNegativeBoundsExtension()/SetNegativeBoundsExtension()

### UE5.4 废弃的字段

- bUseLegacyTangentScaling → GetLegacyTangentScaling()/SetLegacyTangentScaling()（UE_DEPRECATED(5.4)）

## 版本判断机制

解析静态网格时应遵循以下流程：

1. 检查 FileVersionUE: 确定引擎版本范围
2. 检查 CustomVersion: 确定静态网格特定版本
3. 根据版本选择字段读取方式：
   - TObjectPtr vs 原始指针
   - FPerPlatformFloat vs float
   - Nanite 数据是否存在
4. 忽略废弃字段: 使用替代字段或默认值

### 版本判断代码位置

StaticMesh.cpp 中使用 Ar.CustomVer() 检查版本号：
- EImportStaticMeshVersion 枚举定义静态网格特定版本（StaticMesh.h:538-546）
- ObjectVersion.h 定义引擎全局版本

## 版本兼容处理建议

解析静态网格时：
1. 优先使用现代字段（TObjectPtr、FPerPlatform）
2. 检查 NaniteSettings.IsValid() 判断 Nanite 数据存在
3. Materials_DEPRECATED 需转换为 FStaticMaterial 数组
4. 旧版 LOD 阈值需转换为 FPerPlatformFloat
5. ImportedMaterialSlotName 缺失时使用 MaterialSlotName
6. 注意 ImportedMaterialSlotName 仅在 WITH_EDITORONLY_DATA 条件下存在，Cooked 资产中不包含
7. 注意 FPerPlatformInt/FPerPlatformFloat 并非 UE5 独有，UE4.27+ 已引入