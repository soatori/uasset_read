# 关卡资产文档

关卡资产类型 (ULevel/UWorld — .umap 文件) 相关文档导航。

## 概述

.umap 是 Unreal Engine 的关卡文件格式，存储关卡中的 Actor 集合、 BSP 模型、导航数据和预计算光照数据。与普通 .uasset 文件使用相同的文件结构，但扩展名语义区分关卡资产。文件以 PACKAGE_FILE_TAG (0x9E2A83C1) 验证，包标志 PKG_ContainsMap (0x00020000) 标识关卡类型。

.umap 文件是 Unreal Engine 关卡存储的基本单元，所有关卡（PersistentLevel、 StreamingLevels）均以 .umap 格式保存。加载时，引擎首先读取 UWorld 和 ULevel 导出对象，建立 Actor 层次结构后按需加载流送关卡。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| [level-structure.md](level-structure.md) | ULevel + UWorld 结构 | ULevel 顶层结构、UWorld 与 ULevel 关系、Level Streaming 序列化 |
| [level-actor.md](level-actor.md) | Actor 序列化机制 | AActor/UActorComponent/USceneComponent 序列化字段、内嵌 Actor vs 外部 Actor |
| [level-world-partition.md](level-world-partition.md) | WorldPartition + WorldComposition | UE5 WorldPartition 序列化、UE4 WorldComposition 结构、External Actors 机制 |
| [../version/asset-level.md](../version/asset-level.md) | 版本差异 | UE4/UE5 关卡格式演进、WorldComposition 至 WorldPartition 迁移 |

## 核心源码

### 关卡核心定义

| 文件 | 路径 | 说明 |
|------|------|------|
| Level.h | Runtime/Engine/Classes/Engine/ | ULevel 定义、Actors 数组、ActorsForGC、ActorCluster、WorldSettings、Model、WorldDataLayers、WorldPartitionRuntimeCell |
| Level.cpp | Runtime/Engine/Private/ | ULevel 序列化实现 |
| World.h | Runtime/Engine/Classes/Engine/ | UWorld 定义、PersistentLevel、StreamingLevels、LevelCollections |
| World.cpp | Runtime/Engine/Private/ | UWorld 序列化实现 |

### Actor 与组件定义

| 文件 | 路径 | 说明 |
|------|------|------|
| Actor.h | Runtime/Engine/Classes/GameFramework/ | AActor 定义、RootComponent、InstanceComponents、Tags、bIsSpatiallyLoaded |
| Actor.cpp | Runtime/Engine/Private/GameFramework/ | AActor 序列化实现 |
| ActorComponent.h | Runtime/Engine/Classes/Components/ | UActorComponent 定义 |
| SceneComponent.h | Runtime/Engine/Classes/Components/ | USceneComponent 定义、Transform 属性 |

### Level Streaming 定义

| 文件 | 路径 | 说明 |
|------|------|------|
| LevelStreaming.h | Runtime/Engine/Classes/Engine/ | ULevelStreaming 定义、WorldAsset、LODPackageNames |
| LevelStreaming.cpp | Runtime/Engine/Private/Engine/ | Level Streaming 序列化 |

### WorldPartition 定义

| 文件 | 路径 | 说明 |
|------|------|------|
| WorldPartition.h | Runtime/Engine/Public/WorldPartition/ | UWorldPartition 定义、RuntimeHash、StreamingPolicy、ServerStreamingMode、DataLayerManager |
| WorldPartitionRuntimeCell.h | Runtime/Engine/Public/WorldPartition/ | RuntimeCell 定义、SpatiallyLoaded |
| WorldComposition.h | Runtime/Engine/Classes/Engine/ | WorldCompositionInfo 定义（UE4） |
| ActorPackagingScheme | Level.h (EActorPackagingScheme 枚举) | EActorPackagingScheme 定义 |

### 包标志定义

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectMacros.h | Runtime/CoreUObject/Public/UObject/ | PKG_ContainsMap 定义 |
| ObjectVersion.h | Runtime/Core/Public/UObject/ | PACKAGE_FILE_TAG 魔数定义 |

## 文件格式说明

### .umap 与 .uasset 关系

.umap 与普通 .uasset 文件使用相同的文件结构：

- **文件魔数：** PACKAGE_FILE_TAG = 0x9E2A83C1（与 .uasset 相同）
- **文件结构：** FPackageFileSummary + Name Table + Import/Export Map + Export Data + BulkData（与 .uasset 相同）
- **扩展名语义：** .umap 表示关卡资产，.uasset 表示普通资产

### PKG_ContainsMap 包标志

ObjectMacros.h 定义的包标志用于标识关卡类型：

```
PKG_ContainsMap = 0x00020000  // 包包含 ULevel/UWorld 对象
PKG_ContainsMapData = 0x00004000  // 包含关卡数据（存储于独立包）
```

FPackageFileSummary 的 PackageFlags 字段包含 PKG_ContainsMap 标志时，表示该包为关卡资产（.umap）。

### 导出对象层次

.umap 文件的 Export 表导出对象典型层次：

| Export Index | 对象类型 | 说明 |
|--------------|----------|------|
| Export[0] | UWorld | 世界容器对象 |
| Export[1] | ULevel | 主关卡（PersistentLevel） |
| Export[2..N] | AActor | Actor 层次（内嵌 Actor） |
| Export[N+1..] | UActorComponent | 组件层次（内嵌于 Actor） |

UE5 External Actors 模式下，Actor 通过 Import 表引用外部 .uasset 文件，而非内嵌于 .umap Export 表。

## 与 v1.0 文档交叉引用

### 序列化基础设施

| 文档 | 内容 | 关卡引用 |
|------|------|----------|
| [file-structure.md](file-structure.md) | 文件整体结构 | .umap 遵循标准格式 |
| [package-summary.md](package-summary.md) | FPackageFileSummary | PKG_ContainsMap 标志说明 |
| [import-export-tables.md](import-export-tables.md) | Import/Export 表 | Actor 层次通过 Export 表追踪 |
| [serialization/linker-load.md](serialization/linker-load.md) | LinkerLoad 序列化 | Actor 子对象加载机制 |
| [serialization/property-tag.md](serialization/property-tag.md) | PropertyTag 序列化 | Actor 属性标签结构 |
| [serialization/bulkdata.md](serialization/bulkdata.md) | BulkData 存储 | 预计算数据存储位置 |

### 资产引用

| 文档 | 内容 | 关卡引用 |
|------|------|----------|
| [blueprint.md](blueprint.md) | Blueprint 序列化 | LevelScriptBlueprint 复用 Blueprint 结构 |
| [static-mesh.md](static-mesh.md) | StaticMesh 结构 | 关卡中 StaticMesh Actor 引用 |
| [material.md](material.md) | Material 结构 | 关卡中材质引用 |
| [texture.md](texture.md) | Texture 结构 | 关卡中纹理引用 |
| [audio.md](audio.md) | SoundWave 结构 | 关卡中音频引用 |

### Cooked 格式

| 文档 | 内容 | 关卡引用 |
|------|------|----------|
| [cooked/cooked-vs-uncooked.md](cooked/cooked-vs-uncooked.md) | Cooked 格式差异 | 关卡 Cooked 差异说明 |
| [cooked/iostore.md](cooked/iostore.md) | IoStore 格式 | External Asset 存储机制 |

## 源码引用

- Runtime/CoreUObject/Public/UObject/ObjectMacros.h — PKG_ContainsMap 定义
- Runtime/Core/Public/UObject/ObjectVersion.h — PACKAGE_FILE_TAG 魔数
- Runtime/Engine/Classes/Engine/Level.h — ULevel 定义（含 bUseExternalActors, EActorPackagingScheme, ActorsForGC, ActorCluster, WorldDataLayers, WorldPartitionRuntimeCell）
- Runtime/Engine/Classes/Engine/World.h — UWorld 定义（含 LevelCollections, ActiveLevelCollectionIndex）
- Runtime/Engine/Classes/GameFramework/Actor.h — AActor 定义（含 InstanceComponents, bIsSpatiallyLoaded, DataLayers, RuntimeGrid）
- Runtime/Engine/Classes/Engine/LevelStreaming.h — ULevelStreaming 定义
- Runtime/Engine/Public/WorldPartition/WorldPartition.h — UWorldPartition 定义

## 版本差异

详见 [version/asset-level.md](../version/asset-level.md)

UE4 与 UE5 关卡格式主要差异：

- **Actor 存储：** UE4 内嵌 Actor；UE5 External Actors（独立 .uasset 文件）
- **开放世界：** UE4 WorldComposition；UE5 WorldPartition
- **流送机制：** UE4 Tile LOD；UE5 RuntimeCell SpatiallyLoaded
- **空间加载：** UE5 新增 AActor::bIsSpatiallyLoaded 字段，取代 UE4 的 EActorGridPlacement 已弃用枚举
- **关卡集合管理：** UE5 引入 FLevelCollection 结构管理关卡集合，替代 UE4 简单数组方式
