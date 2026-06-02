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
       → IInterface_AssetUserData
       → ITextureStreamingContainer
       → IEditorPathObjectInterface
```

### 字段表

| 字段 | 类型 | 可见性 | 说明 |
|------|------|--------|------|
| URL | FURL | public | 关卡 URL（运行时） |
| Actors | TArray<TObjectPtr<AActor>> | public | Actor 数组（内嵌或外部引用） |
| ActorsForGC | TArray<TObjectPtr<AActor>> | public | GC 暴露的 Actor 数组，其他 Actor 通过 ULevelActorContainer 引用 |
| ActorCluster | TObjectPtr<ULevelActorContainer> | public (Transient) | Actor 集群容器，用于 Cell 流送时复制 Actor |
| Model | TObjectPtr<UModel> | private | BSP 模型（遗留系统） |
| ModelComponents | TArray<TObjectPtr<UModelComponent>> | public | BSP 渲染组件 |
| WorldSettings | TObjectPtr<AWorldSettings> | private | 关卡设置 Actor |
| WorldDataLayers | TObjectPtr<AWorldDataLayers> | private | World Data Layers 信息 |
| NavDataChunks | TArray<TObjectPtr<UNavigationDataChunk>> | public | 导航数据块（BulkData） |
| OwningWorld | TObjectPtr<UWorld> | public (Transient) | 所属 World（Transient） |
| WorldPartitionRuntimeCell | TSoftObjectPtr<UWorldPartitionRuntimeCell> | private | WorldPartition Runtime Cell 引用 |
| LevelScriptBlueprint | TObjectPtr<ULevelScriptBlueprint> | private (EditorOnly) | 关卡蓝图 |
| LevelScriptActor | TObjectPtr<ALevelScriptActor> | public | 关卡脚本 Actor 实例 |
| NavListStart | TObjectPtr<ANavigationObjectBase> | public | 导航链表起始（Deprecated） |
| NavListEnd | TObjectPtr<ANavigationObjectBase> | public | 导航链表结束（Deprecated） |
| LightmapTotalSize | float | public | Lightmap 总大小（KB） |
| ShadowmapTotalSize | float | public | Shadowmap 总大小（KB） |
| StaticNavigableGeometry | TArray<FVector> | public | 静态可导航几何体 |
| StreamingTextureGuids | TArray<FGuid> | public | 流送纹理 GUID 数组 |
| StreamingTextures | TArray<FName> | public | 流送纹理名称数组 |
| PackedTextureStreamingQualityLevelFeatureLevel | uint32 | public | 纹理流质量级别打包 |
| TextureStreamingResourceGuids | TArray<FGuid> | public (EditorOnly) | 纹理流资源 GUID |
| NumTextureStreamingUnbuiltComponents | int32 | public | 未构建流送组件数 |
| NumTextureStreamingDirtyResources | int32 | public | 脏资源数 |
| LevelBuildDataId | FGuid | public | 关卡构建数据 ID |
| MapBuildData | TObjectPtr<UMapBuildDataRegistry> | public | 地图构建数据注册表 |
| LightBuildLevelOffset | FIntVector | public | 光照构建时的关卡偏移 |
| VolumetricLightmapGridManager | FVolumetricLightmapGridManager* | public | 体素光照贴图网格管理器 |
| TickTaskLevel | FTickTaskLevel* | public | Tick 任务关卡 |

### 位标志字段

| 字段 | 类型 | 可见性 | 说明 |
|------|------|--------|------|
| bIsLightingScenario | uint8:1 | public | 光照场景标记 |
| bAreComponentsCurrentlyRegistered | uint8:1 | public | 组件当前已注册 |
| bGeometryDirtyForLighting | uint8:1 | public | 几何体光照脏标记 |
| bTextureStreamingRotationChanged | uint8:1 | public | 纹理流旋转变化 |
| bStaticComponentsRegisteredInStreamingManager | uint8:1 | public (Transient) | 静态组件已在流送管理器注册 |
| bIsVisible | uint8:1 | public (Transient) | 可见标记 |
| bLocked | uint8:1 | public (EditorOnly) | 锁定标记 |
| bContainsStableActorGUIDs | uint8:1 | public (EditorOnly) | 包含稳定 Actor GUID |
| bFixupActorFoldersAtLoad | uint8:1 | public (EditorOnly) | 加载时修复 Actor 文件夹 |
| bForceCantReuseUnloadedButStillAround | uint8:1 | private (EditorOnly) | 强制不可重用已卸载对象 |
| bForcePackageTrashingAtCleanup | uint8:1 | private (EditorOnly) | 清理时强制销毁包 |
| bIsMapBuildDataOwner | uint8:1 | public | 是 MapBuildData 所有者 |
| bIsPartitioned | uint8:1 | public | 分区标记 |
| bGarbageCollectionClusteringEnabled | uint8:1 | public | 垃圾回收集群启用 |
| bActorClusterCreated | uint8:1 | public | Actor 集群已创建 |
| bIncrementalUnregisterComponentsCompleted | uint8:1 | public | 增量取消注册组件完成 |
| bHasRerunConstructionScripts | uint8:1 | public | 已重新运行构造脚本 |
| bAlreadyMovedActors | uint8:1 | public | 已移动 Actor |
| bAlreadyShiftedActors | uint8:1 | public | 已偏移 Actor 位置 |
| bAlreadyUpdatedComponents | uint8:1 | public | 已更新组件 |
| bAlreadyAssociatedStreamableResources | uint8:1 | public | 已关联流送资源 |
| bAlreadyInitializedNetworkActors | uint8:1 | public | 已初始化网络 Actor |
| bAlreadyClearedActorsSeamlessTraveledFlag | uint8:1 | public | 已清除无缝旅行标志 |
| bAlreadySortedActorList | uint8:1 | public | 已排序 Actor 列表 |
| bIsAssociatingLevel | uint8:1 | public | 正在关联到 World |
| bIsDisassociatingLevel | uint8:1 | public | 正在从 World 取消关联 |
| bRequireFullVisibilityToRender | uint8:1 | public | 需要完全可见才能渲染 |
| bClientOnlyVisible | uint8:1 | public | 仅客户端可见 |
| bWasDuplicated | uint8:1 | public | 已复制 |
| bWasDuplicatedForPIE | uint8:1 | public | 已为 PIE 复制 |
| bIsBeingRemoved | uint8:1 | public | 正在从 World 移除 |
| bUseExternalActors | bool | public (EditInstanceOnly, EditorOnly) | UE5 External Actors 标记 |
| ActorPackagingScheme | EActorPackagingScheme | public (EditorOnly) | Actor 打包方案 |
| bUseActorFolders | bool | private (EditInstanceOnly, EditorOnly) | Actor 文件夹对象模式 |

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
| NumTextureStreamingDirtyResources | int32 | 脏资源数 |
| PackedTextureStreamingQualityLevelFeatureLevel | uint32 | 纹理流质量级别打包 |

### 编辑器专用字段

| 字段 | 类型 | 说明 |
|------|------|------|
| PlayFromHereActor | AActor* | "从此处播放" Actor |
| LevelSimplification[WORLDTILE_LOD_MAX_INDEX] | FLevelSimplificationDetails | LOD 级别简化设置 |
| LevelColor | FLinearColor | 关卡可视化颜色（WorldComposition 模式） |
| ActorFolders | TMap<FGuid, TObjectPtr<UActorFolder>> | Actor 文件夹对象（Transient） |
| FolderLabelToActorFolders | TMap<FString, FActorFolderSet> | 文件夹标签加速表（Transient） |

### 内部状态字段

| 字段 | 类型 | 说明 |
|------|------|------|
| IncrementalComponentState | EIncrementalComponentState | 增量组件更新状态 |
| CurrentActorIndexForIncrementalUpdate | int32 | 增量更新当前 Actor 索引 |
| CurrentActorIndexForUnregisterComponents | int32 | 取消注册组件当前 Actor 索引 |
| PendingVisibilityState | ELevelPendingVisibilityState:2 | 可见性变更状态 |
| RouteActorInitializationState | ERouteActorInitializationState | Actor 初始化路由状态 |
| RouteActorInitializationIndex | int32 | Actor 初始化路由索引 |
| AsyncRegisterLevelContext | FAsyncRegisterLevelContext* | 异步注册关卡上下文 |

### 源码引用

- Runtime/Engine/Classes/Engine/Level.h — ULevel 定义
- Runtime/Engine/Private/Engine/Level.cpp — ULevel 序列化实现

## Part C: UWorld 与 ULevel 关系

### 继承关系

```
UWorld → UObject
       → FNetworkNotify
```

### 概述

UWorld 作为运行时世界容器，非磁盘序列化的主要对象类型。.umap 文件导出 UWorld 对象，但 UWorld 的主要作用是持有 PersistentLevel 和管理 StreamingLevels。

### 字段表

| 字段 | 类型 | 可见性 | 说明 |
|------|------|--------|------|
| PersistentLevel | TObjectPtr<ULevel> | public (Transient) | 主关卡（PKG_Map 包导出的 ULevel） |
| Levels | TArray<TObjectPtr<ULevel>> | private (Transient) | 关卡数组（包含 PersistentLevel 和 StreamingLevels） |
| StreamingLevels | TArray<TObjectPtr<ULevelStreaming>> | private (Transient) | 流送关卡数组 |
| StreamingLevelsToConsider | FStreamingLevelsToConsider | private (Transient) | 正在考虑的流送关卡 |
| URL | FURL | public | 世界 URL（运行时） |
| WorldType | EWorldType::Type | public | 世界类型（PIE/Editor/Game 等） |
| bIsWorldInitialized | uint8:1 | public | 初始化标记 |
| LevelCollections | TArray<FLevelCollection> | public (Transient) | 关卡集合数组 |
| ActiveLevelCollectionIndex | int32 | private | 当前 Ticking 的关卡集合索引 |
| NetDriver | TObjectPtr<UNetDriver> | public (Transient) | 网络驱动 |
| DemoNetDriver | TObjectPtr<UDemoNetDriver> | public | Demo 网络驱动 |
| AudioDeviceHandle | FAudioDeviceHandle | public | 音频设备句柄 |
| GameState | TObjectPtr<AGameStateBase> | private (Transient) | Game State |
| AuthorityGameMode | TObjectPtr<AGameModeBase> | private (Transient) | 权威 GameMode（服务器） |
| NavigationSystem | TObjectPtr<UNavigationSystemBase> | private (Transient) | 导航系统 |
| AISystem | TObjectPtr<UAISystemBase> | private (Transient) | AI 系统 |
| Scene | FSceneInterface* | public | 渲染场景接口 |
| FXSystem | FFXSystemInterface* | public | FX 系统 |
| PhysicsScene_Chaos | TSharedPtr<FPhysScene_Chaos> | public | Chaos 物理场景 |
| TimerManager | FTimerManager* | private | 定时器管理器 |
| LatentActionManager | FLatentActionManager | private | 潜在动作管理器 |
| OwningGameInstance | TObjectPtr<UGameInstance> | private (Transient) | 所属 GameInstance |

### 位标志字段

| 字段 | 类型 | 说明 |
|------|------|------|
| bWorldWasLoadedThisTick | uint8:1 | 本 tick 加载了世界 |
| bTriggerPostLoadMap | uint8:1 | 触发 PostLoadMap |
| bInTick | uint8:1 | 正在 Ticking |
| bIsBuilt | uint8:1 | 已构建 |
| bTickNewlySpawned | uint8:1 | Ticking 新生成的 Actor |
| bPostTickComponentUpdate | uint8:1 | Post tick 组件更新 |
| bIsLevelStreamingFrozen | uint8:1 | 流送已冻结 |
| bDoDelayedUpdateCullDistanceVolumes | uint8:1 | 延迟更新剔除体积 |
| bIsRunningConstructionScript | uint8:1 | 正在运行构造脚本 |
| bShouldSimulatePhysics | uint8:1 | 应模拟物理 |
| bDropDetail | uint8:1 | 帧率低于阈值，丢弃高细节 |
| bAggressiveLOD | uint8:1 | 帧率远低于阈值，使用更激进 LOD |
| bIsDefaultLevel | uint8:1 | 是默认关卡 |
| bRequestedBlockOnAsyncLoading | uint8:1 | 请求阻塞异步加载 |
| bActorsInitialized | uint8:1 | Actor 已初始化 |
| bBegunPlay | uint8:1 | BeginPlay 已调用（已弃用公共访问） |
| bMatchStarted | uint8:1 | 比赛已开始 |
| bPlayersOnly | uint8:1 | 仅更新玩家 |
| bPlayersOnlyPending | uint8:1 | 待设置 PlayersOnly |
| bStartup | uint8:1 | 初始化阶段 |
| bIsTearingDown | uint8:1 | 正在拆除 |
| bKismetScriptError | uint8:1 | 蓝图编译错误 |
| bDebugPauseExecution | uint8:1 | 调试暂停执行 |
| bAreConstraintsDirty | uint8:1 (Transient) | 约束脏标记 |
| bShouldTick | uint8:1 | 应 Ticking |
| bStreamingDataDirty | uint8:1 | 流送数据脏标记 |
| bShouldForceUnloadStreamingLevels | uint8:1 | 强制卸载流送关卡 |
| bShouldForceVisibleStreamingLevels | uint8:1 | 强制可见流送关卡 |
| bHasEverBeenInitialized | uint8:1 | 曾初始化过 |
| bIsBeingCleanedUp | bool | 正在清理 |

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
| ULevelStreamingVolume | 体积触发流送 |

### 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| WorldAsset | TSoftObjectPtr<UWorld> | 关卡资产引用（PackageName） |
| PackageNameToLoad | FName | 加载包名 |
| LODPackageNames | TArray<FName> | LOD 关卡名称数组 |
| LevelTransform | FTransform | 关卡变换 |
| bShouldBeLoaded | uint8 | 应加载标记 |
| bShouldBeVisible | uint8 | 应可见标记 |
| bLocked | uint8 | 锁定标记 |
| bClientOnlyVisible | bool | 仅客户端可见 |
| StreamingPriority | int32 | 流送优先级 |
| LevelLODIndex | int32 | LOD 索引 |

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
| Level.h | Runtime/Engine/Classes/Engine/ | ULevel 定义（含 ActorsForGC, ActorCluster, WorldDataLayers, WorldPartitionRuntimeCell） |
| Level.cpp | Runtime/Engine/Private/ | ULevel 序列化 |
| World.h | Runtime/Engine/Classes/Engine/ | UWorld 定义（含 LevelCollections） |
| World.cpp | Runtime/Engine/Private/ | UWorld 序列化 |
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
- **关卡集合管理：** UE5 引入 FLevelCollection 管理关卡集合，替代 UE4 简单数组方式
- **WorldPartition 集成：** UE5 ULevel 新增 WorldPartitionRuntimeCell 私有字段，支持 WorldPartition Cell 机制
- **Actor 集群：** UE5 新增 ActorCluster (ULevelActorContainer) 用于 Cell 流送时 Actor 复制
- **Data Layers：** UE5 新增 WorldDataLayers 字段支持数据层系统
