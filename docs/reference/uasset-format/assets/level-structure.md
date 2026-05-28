# ULevel + UWorld + Level Streaming 结构

## 概述

.umap 关卡文件存储 ULevel 导出对象，包含 Actor 集合、BSP 模型、导航数据和预计算光照数据。UWorld 作为世界容器，持有 PersistentLevel 和 StreamingLevels 数组。Level Streaming 机制通过 ULevelStreaming 对象引用外部关卡包，实现关卡流送加载。

本文档描述 ULevel 顶层结构、UWorld 与 ULevel 的关系、Level Streaming 序列化、BSP Model 概要、预计算数据概要和 LevelScriptBlueprint 引用。

## Part A: .umap 与 .uasset 格式关系

### 文件魔数与结构

.umap 与普通 .uasset 文件使用相同的文件结构：

| 属性 | .umap | .uasset |
|------|-------|----------|
| 文件魔数 | PACKAGE_FILE_TAG (0x9E2A83C1) | PACKAGE_FILE_TAG (0x9E2A83C1) |
| 文件结构 | FPackageFileSummary + Tables + Data | FPackageFileSummary + Tables + Data |
| 包标志 | PKG_ContainsMap (0x00020000) | 无特定标志 |
| 扩展名 | .umap | .uasset |

### PKG_ContainsMap 包标志

ObjectMacros.h 定义的包标志用于标识关卡类型：

```cpp
PKG_ContainsMap = 0x00020000      // 包包含 ULevel/UWorld 对象
PKG_ContainsMapData = 0x00004000  // 包含关卡数据（独立包存储）
```

FPackageFileSummary 的 PackageFlags 字段包含 PKG_ContainsMap 标志时，表示该包为关卡资产。

### 导出对象层次

.umap 文件的 Export 表导出对象典型层次：

| Export Index | 对象类型 | 说明 |
|--------------|----------|------|
| Export[0] | UWorld | 世界容器对象 |
| Export[1] | ULevel | 主关卡（PersistentLevel） |
| Export[2..N] | AActor | Actor 层次（内嵌 Actor） |
| Export[N+1..] | UActorComponent | 组件层次 |

### 源码引用

- Runtime/CoreUObject/Public/UObject/ObjectMacros.h — PKG_ContainsMap 定义
- Runtime/Core/Public/UObject/ObjectVersion.h — PACKAGE_FILE_TAG 魔数

## Part B: ULevel 顶层结构

### 继承关系

```
ULevel → UObject
```

### 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| URL | FURL | 关卡 URL（运行时） |
| Actors | TArray<TObjectPtr<AActor>> | Actor 数组（内嵌或外部引用） |
| Model | TObjectPtr<UModel> | BSP 模型（遗留系统） |
| WorldSettings | TObjectPtr<AWorldSettings> | 关卡设置 Actor |
| NavDataChunks | TArray<TObjectPtr<UNavigationDataChunk>> | 导航数据块（BulkData） |
| OwningWorld | TObjectPtr<UWorld> | 所属 World（Transient） |
| LevelScriptBlueprint | TObjectPtr<ULevelScriptBlueprint> | 关卡蓝图（EditorOnly） |
| LevelScriptActor | TObjectPtr<ALevelScriptActor> | 关卡脚本 Actor 实例 |
| NavListStart | TObjectPtr<ANavigationObjectBase> | 导航链表起始（Deprecated） |
| NavListEnd | TObjectPtr<ANavigationObjectBase> | 导航链表结束（Deprecated） |
| LightmapTotalSize | float | Lightmap 总大小（KB） |
| ShadowmapTotalSize | float | Shadowmap 总大小（KB） |
| StaticNavigableGeometry | TArray<FVector> | 静态可导航几何体 |
| StreamingTextureGuids | TArray<FGuid> | 流送纹理 GUID 数组 |
| StreamingTextures | TArray<FName> | 流送纹理名称数组 |
| LevelBuildDataId | FGuid | 关卡构建数据 ID |
| MapBuildData | TObjectPtr<UMapBuildDataRegistry> | 地图构建数据注册表 |
| LightBuildLevelOffset | FIntVector | 光照构建时的关卡偏移 |
| bIsLightingScenario | uint8 (bool) | 光照场景标记 |
| bIsVisible | uint8 (bool) | 可见标记（Transient） |
| bIsPartitioned | uint8 (bool) | 分区标记 |
| bUseExternalActors | bool (EditorOnly) | UE5 External Actors 标记 |
| ActorPackagingScheme | EActorPackagingScheme (EditorOnly) | Actor 打包方案 |

### 预计算数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| PrecomputedLightVolume | FPrecomputedLightVolume* | 预计算光照体积（指针） |
| PrecomputedVolumetricLightmap | FPrecomputedVolumetricLightmap* | 体素光照贴图（指针） |
| PrecomputedVisibilityHandler | FPrecomputedVisibilityHandler | 预计算可见性处理 |
| PrecomputedVolumeDistanceField | FPrecomputedVolumeDistanceField | 预计算体积距离场 |

### 纹理流数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| TextureStreamingResourceGuids | TArray<FGuid> | 纹理流资源 GUID（EditorOnly） |
| NumTextureStreamingUnbuiltComponents | int32 | 未构建流送组件数 |
| NumTextureStreamingDirtyResources | int32 |脏资源数 |
| PackedTextureStreamingQualityLevelFeatureLevel | uint32 | 纹理流质量级别打包 |

### 源码引用

- Runtime/Engine/Classes/Engine/Level.h — ULevel 定义
- Runtime/Engine/Private/Engine/Level.cpp — ULevel 序列化实现

## Part C: UWorld 与 ULevel 关系

### 继承关系

```
UWorld → UObject
```

### 概述

UWorld 作为运行时世界容器，非磁盘序列化的主要对象类型。.umap 文件导出 UWorld 对象，但 UWorld 的主要作用是持有 PersistentLevel 和管理 StreamingLevels。

### 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| PersistentLevel | TObjectPtr<ULevel> | 主关卡（PKG_Map 包导出的 ULevel） |
| Levels | TArray<TObjectPtr<ULevel>> | 关卡数组（包含 PersistentLevel 和 StreamingLevels） |
| StreamingLevels | TArray<TObjectPtr<ULevelStreaming>> | 流送关卡数组 |
| URL | FURL | 世界 URL（运行时） |
| WorldType | EWorldType | 世界类型（PIE/Editor/Game 等） |
| bIsWorldInitialized | bool | 初始化标记 |

### FLevelCollection 结构

FLevelCollection 用于管理关卡集合：

| 字段 | 类型 | 说明 |
|------|------|------|
| CollectionType | ELevelCollectionType | 集合类型 |
| bIsVisible | bool | 可见标记 |
| GameState | TObjectPtr<AGameStateBase> | GameState 对象 |
| NetDriver | TObjectPtr<UNetDriver> | 网络驱动 |
| DemoNetDriver | TObjectPtr<UDemoNetDriver> | Demo 网络驱动 |
| PersistentLevel | TObjectPtr<ULevel> | 主关卡 |
| Levels | TSet<TObjectPtr<ULevel>> | 关卡集合 |

### 序列化行为

UWorld::Serialize() 标记 PKG_Map 包，但 UWorld 本身不持久化完整的运行时状态。.umap 文件导出 UWorld 对象作为容器，主要数据存储于 ULevel。

### 源码引用

- Runtime/Engine/Classes/Engine/World.h — UWorld 定义
- Runtime/Engine/Private/Engine/World.cpp — UWorld 序列化实现

## Part D: Level Streaming 序列化

### 继承关系

```
ULevelStreaming → UObject
```

### 概述

ULevelStreaming 管理外部关卡包的流送加载。通过 WorldAsset 字段引用外部 UWorld 包，控制加载时机和可见性。

### 子类列表

| 子类 | 说明 |
|------|------|
| ULevelStreamingAlwaysLoaded | 常驻加载（不卸载） |
| ULevelStreamingPersistent | 持久流送 |
| ULevelStreamingDynamic | 动态流送 |
| ULevelStreamingLevelStreamingObject | Level Streaming Object 包装 |

### 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| WorldAsset | TSoftObjectPtr<UWorld> | 关卡资产引用（PackageName） |
| PackageNameToLoad | FName | 加载包名 |
| LODPackageNames | TArray<FName> | LOD 关卡名称数组 |
| LODPackageNamesToLoad | TArray<FName> | LOD 包名数组（磁盘） |
| LevelTransform | FTransform | 关卡变换 |
| bShouldBeLoaded | uint8 | 应加载标记 |
| bShouldBeVisible | uint8 | 应可见标记 |
| bLocked | uint8 | 锁定标记 |
| bClientOnlyVisible | bool | 仅客户端可见 |
| StreamingPriority | int32 | 流送优先级 |
| LevelLODIndex | int32 | LOD 索引 |
| CurrentState | ELevelStreamingState | 当前状态（Transient） |
| TargetState | ELevelStreamingTargetState | 目标状态（Transient） |

### ELevelStreamingState 枚举

| 值 | 说明 |
|-----|------|
| Removed | 已移除 |
| Unloaded | 已卸载 |
| FailedToLoad | 加载失败 |
| Loading | 加载中 |
| LoadedNotVisible | 已加载不可见 |
| MakingVisible | 正在可见 |
| LoadedVisible | 已加载可见 |
| MakingInvisible | 正在不可见 |

### 源码引用

- Runtime/Engine/Classes/Engine/LevelStreaming.h — ULevelStreaming 定义
- Runtime/Engine/Private/Engine/LevelStreaming.cpp — Level Streaming 序列化

## Part E: BSP Model 概要

### 概述

BSP Model 为遗留系统，低优先级。ULevel::Model 字段存储 BSP 模型，几何体数据存储于 BulkData 区域。

### 字段存在标注

| 字段 | 类型 | 说明 |
|------|------|------|
| Model | TObjectPtr<UModel> | BSP 模型 |
| ModelComponents | TArray<TObjectPtr<UModelComponent>> | BSP 渲染组件 |

### 存储位置

- BSP 几何体数据存储于 BulkData 区域
- 详细格式 deferred 说明（不展开几何体结构）

### 源码引用

- Runtime/Engine/Classes/Engine/Model.h — UModel 定义（仅标注存在）

## Part F: 预计算数据概要

### 概述

预计算数据存储位置标注，详细格式留给未来 Phase。

### 数据类型列表

| 类型 | 存储位置 | 说明 |
|------|----------|------|
| FPrecomputedLightVolume | BulkData | 预计算光照体积 |
| FPrecomputedVolumetricLightmap | BulkData | 体素光照贴图 |
| FPrecomputedVisibilityHandler | BulkData | 预计算可见性 |
| FPrecomputedVolumeDistanceField | BulkData | 体积距离场 |
| UMapBuildDataRegistry | 独立包 | 地图构建数据注册表 |

### 存储位置

预计算数据通过 ULevel 序列化后的 BulkData 区域存储，或存储于独立的 _BuildData 包。

### 源码引用

- Runtime/Engine/Classes/Engine/Level.h — 预计算数据字段定义
- Runtime/Engine/Classes/Engine/MapBuildDataRegistry.h — 构建数据注册表

## Part G: LevelScriptBlueprint 引用

### 概述

关卡蓝图复用 v1.0 Blueprint 文档的序列化机制。ULevelScriptBlueprint 继承自 UBlueprint，序列化结构相同。

### 继承关系

```
ULevelScriptBlueprint → UBlueprint → UObject
```

### ULevel 字段引用

| 字段 | 类型 | 说明 |
|------|------|------|
| LevelScriptBlueprint | TObjectPtr<ULevelScriptBlueprint> | 关卡蓝图引用（EditorOnly） |
| LevelScriptActor | TObjectPtr<ALevelScriptActor> | 关卡脚本 Actor 实例 |

### ULevelScriptBlueprint 定义

ULevelScriptBlueprint 继承 UBlueprint，无额外核心字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| FriendlyName | FString | UI 显示名称（EditorOnly, Transient） |

### 交叉引用

- [blueprint.md](blueprint.md) — Blueprint 序列化机制
- [blueprint-source.md](blueprint-source.md) — UBlueprint 核心属性

### 源码引用

- Runtime/Engine/Classes/Engine/LevelScriptBlueprint.h — ULevelScriptBlueprint 定义

## Part H: 交叉引用

### 序列化基础设施

| 文档 | 内容 | 关卡引用 |
|------|------|----------|
| [file-structure.md](../file-structure.md) | 文件整体结构 | .umap 遵循标准格式 |
| [package-summary.md](../package-summary.md) | FPackageFileSummary | PKG_ContainsMap 标志 |
| [import-export-tables.md](../import-export-tables.md) | Import/Export 表 | Actor 层次追踪 |
| [bulkdata-region.md](../bulkdata-region.md) | BulkData 存储 | 预计算数据存储 |

### 资产引用

| 文档 | 内容 | 关卡引用 |
|------|------|----------|
| [static-mesh.md](static-mesh.md) | StaticMesh 结构 | 关卡中 StaticMesh Actor |
| [material.md](material.md) | Material 结构 | 关卡中材质引用 |
| [blueprint.md](blueprint.md) | Blueprint 结构 | LevelScriptBlueprint |

## 源码引用汇总

| 文件 | 路径 | 说明 |
|------|------|------|
| Level.h | Runtime/Engine/Classes/Engine/ | ULevel 定义 |
| Level.cpp | Runtime/Engine/Private/Engine/ | ULevel 序列化 |
| World.h | Runtime/Engine/Classes/Engine/ | UWorld 定义 |
| World.cpp | Runtime/Engine/Private/Engine/ | UWorld 序列化 |
| LevelStreaming.h | Runtime/Engine/Classes/Engine/ | ULevelStreaming 定义 |
| WorldComposition.h | Runtime/Engine/Classes/Engine/ | WorldCompositionInfo（UE4） |
| LevelScriptBlueprint.h | Runtime/Engine/Classes/Engine/ | ULevelScriptBlueprint 定义 |
| ObjectMacros.h | Runtime/CoreUObject/Public/UObject/ | PKG_ContainsMap 定义 |

## 版本差异

详见 [../version/asset-level.md](../version/asset-level.md)

UE4 与 UE5 ULevel/UWorld 结构主要差异：

- **Actor 存储：** UE4 内嵌 Actor；UE5 External Actors
- **WorldType：** UE5 新增世界类型枚举值
- **预计算数据：** UE5 体素光照贴图增强