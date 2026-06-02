# 静态网格材质槽

## 概述

静态网格通过材质槽数组 (StaticMaterials) 存储材质引用，渲染分段 (Section) 通过 MaterialIndex 引用材质槽。材质槽结构包含材质对象引用、槽名称和 UV 通道信息。

## FStaticMaterial 材质槽结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 材质对象引用 | StaticMesh.h 第 506-507 行 |
| MaterialSlotName | FName | 材质槽名称（供 gameplay 使用，避免材质数组拓扑变化导致的错误） | StaticMesh.h 第 510-511 行 |
| ImportedMaterialSlotName | FName | 导入时的材质槽名（重新导入时用于排序材质数组） | StaticMesh.h 第 514-515 行 |
| UVChannelData | FMeshUVChannelInfo | UV 通道纹理流式数据 | StaticMesh.h 第 518-519 行 |
| OverlayMaterialInterface | TObjectPtr&lt;UMaterialInterface&gt; | 覆盖材质引用 | StaticMesh.h 第 521-522 行 |

说明：
- ImportedMaterialSlotName 用于材质重映射，确保重新导入时材质槽顺序正确
- OverlayMaterialInterface 允许为特定材质槽添加覆盖材质
- FStaticMaterial 使用 GENERATED_USTRUCT_BODY 生成序列化支持

## FStaticMaterialMinimalInfo 材质最小信息

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialSlotName | FName | 材质槽名称 | StaticMesh.h 第 534 行 |
| MaterialObjectPath | FString | 材质对象路径 | StaticMesh.h 第 535 行 |

用于轻量级材质信息缓存（StaticMaterialsInfoCache 中使用）。

## FMeshUVChannelInfo UV 通道信息

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| bInitialized | bool | 是否已初始化 | MeshUVChannelInfo.h |
| bOverride | bool | 是否覆盖默认值 | MeshUVChannelInfo.h |
| LocalBounds | FBox | UV 局部包围盒 | MeshUVChannelInfo.h |
| UVDensities | float[MAX_STATIC_TEXCOORDS] | 各 UV 通道密度 | MeshUVChannelInfo.h |

## FStaticMeshSection 渲染分段材质

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MaterialIndex | int32 | 材质槽索引 | StaticMeshResources.h 第 204 行 |
| NumTriangles | uint32 | 三角形数量 | StaticMeshResources.h 第 208 行 |
| FirstIndex | uint32 | 索引缓冲起始位置 | StaticMeshResources.h 第 207 行 |
| bEnableCollision | bool | 碰撞启用标志 | StaticMeshResources.h 第 213 行 |
| bCastShadow | bool | 阴影投射标志 | StaticMeshResources.h 第 216 行 |
| bVisibleInRayTracing | bool | 光线追踪效果可见标志 | StaticMeshResources.h 第 218 行 |
| bAffectDistanceFieldLighting | bool | 是否影响距离场光照 | StaticMeshResources.h 第 220 行 |
| bForceOpaque | bool | 在光线追踪中强制不透明 | StaticMeshResources.h 第 222 行 |

说明：每个 Section 对应一个材质，通过 MaterialIndex 引用 StaticMaterials 数组。同一材质可能被多个 Section 使用。

## 材质引用机制

- **MaterialInterface**: 使用 TObjectPtr 智能指针，支持对象引用追踪
- **Import/Export 表**: 材质对象存储在 Import 表（外部包）或 Export 表（本包）
- **MaterialSlotName**: 用于材质编辑和材质重映射，保持材质槽稳定性

### 材质索引映射

Editor 模式下存在 MaterialRemapIndexPerImportVersion 映射数组（StaticMesh.h 第 706-707 行），用于处理材质导入时的重排序。Cooked 数据通常已整理为直接映射。

FMaterialRemapIndex 结构：
- ImportVersionKey (uint32)：导入版本键
- MaterialRemap (TArray&lt;int32&gt;)：重映射数组

### EImportStaticMeshVersion 导入版本枚举

| 版本值 | 说明 |
|--------|------|
| BeforeImportStaticMeshVersionWasAdded | 初始版本 |
| RemoveStaticMeshSkinxxWorkflow | 移除材质重排序工作流 |
| StaticMeshVersionPlusOne | 下一个版本（边界值） |

## 材质槽与分段关联

```
UStaticMesh
├── StaticMaterials[] (材质槽数组)
│   ├── [0] FStaticMaterial → MaterialInterface, MaterialSlotName, ImportedMaterialSlotName, UVChannelData, OverlayMaterialInterface
│   ├── [1] FStaticMaterial → ...
│   └── ...
├── RenderData
│   └── LODResources[0]
│       └── Sections[] (渲染分段)
│           ├── [0] FStaticMeshSection → MaterialIndex=0, triangles...
│           ├── [1] FStaticMeshSection → MaterialIndex=1, triangles...
│           └── ...
```

## 源码引用

- Runtime/Engine/Classes/Engine/StaticMesh.h — FStaticMaterial 定义、FStaticMaterialMinimalInfo 定义、FMaterialRemapIndex 定义
- Runtime/Engine/Public/StaticMeshResources.h — FStaticMeshSection 定义
- Runtime/Engine/Public/MeshUVChannelInfo.h — FMeshUVChannelInfo 定义
- Runtime/Engine/Private/Engine/StaticMesh.cpp — 材质槽序列化

## 版本差异

### UE5 特性
| 特性 | 说明 |
|------|------|
| TObjectPtr | 智能指针替代原始指针，支持引用追踪 |
| ImportedMaterialSlotName | 支持材质重映射，确保导入顺序稳定 |
| OverlayMaterialInterface | 覆盖材质支持 |
| bVisibleInRayTracing | Section 级别光线追踪可见性 |
| bAffectDistanceFieldLighting | Section 级别距离场光照影响 |
| bForceOpaque | Section 级别光线追踪强制不透明 |
| FStaticMaterialMinimalInfo | 轻量级材质信息缓存 |

### UE4 特性
| 特性 | 说明 |
|------|------|
| 原始指针 | UMaterialInterface* 直接引用 |
| Materials_DEPRECATED | 旧版材质数组，仅存储材质对象 |
| 无 ImportedMaterialSlotName | 材质重映射依赖手动处理 |
| 材质重排序工作流 | 通过 MaterialIndexToImportIndex 手动处理 |
