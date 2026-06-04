# WorldPartition + WorldComposition 结构

## 概述

WorldPartition（UE5）和 WorldComposition（UE4）是开放世界关卡流送系统的两种实现方案。WorldComposition 使用 Tile 分区机制，基于距离 LOD 控制流送。WorldPartition 使用 RuntimeCell 空间分区机制，基于 SpatiallyLoaded 标记控制流送。UE5 External Actors 机制将 Actor 存储为独立 .uasset 文件。

本文档描述 UE4 WorldComposition 序列化、UE5 WorldPartition 序列化、RuntimeCell 结构、External Actors 机制、两者对比。

## Part A: UE4 WorldComposition 序列化

### 概述

WorldComposition 是 UE4 开放世界流送系统（历史方案）。通过 Tile 分区管理关卡流送，基于距离 LOD 控制加载时机。

### 继承关系

```
UWorldComposition → UObject
```

### FWorldCompositionTile 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| PackageName | FName | Tile 包名（长包名） |
| LODPackageNames | TArray<FName> | LOD 关卡包名数组 |
| Info | FWorldTileInfo | Tile 信息 |
| StreamingLevelStateChangeTime | double | 流送状态变更时间 |

### FWorldTileInfo 结构（来自 WorldCompositionUtility.h）

| 字段 | 类型 | 说明 |
|------|------|------|
| Bounds | FBox | Tile 边界 |
| Position | FIntPoint | Tile 位置（XY） |
| LODLevels | TArray<FWorldTileLODInfo> | LOD 层级信息 |
| Layer | FWorldTileLayer | Tile 层 |
| ZOrder | int32 | Z 顺序 |

### UWorldComposition 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| WorldRoot | FString | 世界根路径（长包名） |
| Tiles | FTilesList | Tile 列表 |
| TilesStreaming | TArray<TObjectPtr<ULevelStreaming>> | Tile 流送对象数组 |
| TilesStreamingTimeThreshold | double | 流送状态变更时间阈值 |
| bLoadAllTilesDuringCinematic | bool | Cinematic 时加载所有 Tile |
| bRebaseOriginIn3DSpace | bool | 3D 空间 Origin Rebasing |
| RebaseOriginDistance | float | Origin Rebasing 距离 |
| bLockTilesLocation | bool (EditorOnly) | 锁定 Tile 位置 |

### 与 LevelStreaming 关系

Tile → ULevelStreamingDynamic 映射：

- PopulateStreamingLevels() 创建流送对象
- UpdateStreamingState() 基于 View Location 更新流送状态
- GetDistanceVisibleLevels() 计算可见 Tile

### 源码引用

- Runtime/Engine/Classes/Engine/WorldComposition.h — UWorldComposition 定义
- Runtime/Engine/Classes/Engine/WorldCompositionUtility.h — FWorldTileInfo 定义

## Part B: UE5 WorldPartition 序列化

### 概述

WorldPartition 是 UE5 开放世界分区系统（当前方案）。通过 RuntimeCell 空间分区管理关卡流送，基于 SpatiallyLoaded 标记控制加载时机。

### 继承关系

```
UWorldPartition → UObject
                → FActorDescContainerInstanceCollection
                → IWorldPartitionCookPackageGenerator
```

### UWorldPartition 字段表

| 字段 | 类型 | 可见性 | 说明 |
|------|------|--------|------|
| RuntimeHash | TObjectPtr<UWorldPartitionRuntimeHash> | public | 运行时 Hash |
| bEnableStreaming | bool | public | 流送启用标记 |
| ServerStreamingMode | EWorldPartitionServerStreamingMode | public | 服务器流送模式 |
| ServerStreamingOutMode | EWorldPartitionServerStreamingOutMode | public | 服务器流送输出模式 |
| EditorHash | TObjectPtr<UWorldPartitionEditorHash> | public (EditorOnly) | 编辑器 Hash |
| World | TObjectPtr<UWorld> | private | 所属 World |
| InitState | EWorldPartitionInitState | private | 初始化状态 |
| InstanceTransform | TOptional<FTransform> | private | 实例变换 |
| bStreamingInEnabled | bool | private | 流送输入启用 |
| StreamingStateEpoch | int32 (mutable) | private | 流送状态纪元 |
| StreamingPolicy | mutable TObjectPtr<UWorldPartitionStreamingPolicy> | private (Transient) | 流送策略 |
| DataLayerManager | TObjectPtr<UDataLayerManager> | private (Transient) | 数据层管理器 |
| ExternalDataLayerManager | TObjectPtr<UExternalDataLayerManager> | private (Transient) | 外部数据层管理器 |
| DataLayersLogicOperator | EWorldPartitionDataLayersLogicOperator | private | 数据层逻辑运算符 |
| ReferencedObjects | TSet<TObjectPtr<UObject>> | public (Transient) | 引用对象集合（Verse 支持） |

### 编辑器专用字段

| 字段 | 类型 | 说明 |
|------|------|------|
| AlwaysLoadedActors | FLoaderAdapterAlwaysLoadedActors* | 常驻加载 Actor 适配器 |
| ForceLoadedActors | FLoaderAdapterActorList* | 强制加载 Actor 适配器 |
| PinnedActors | FLoaderAdapterActorList* | 固定加载 Actor 适配器 |
| WorldPartitionEditor | IWorldPartitionEditor* | 编辑器接口 |
| ActorDescContainerInstance | TObjectPtr<UActorDescContainerInstance> | Actor 描述容器实例 |
| ContainerInstanceClass | TSubclassOf<UActorDescContainerInstance> | 容器实例类 |
| RuntimeCellsTransformerStack | TArray<FRuntimeCellTransformerInstance> | Runtime Cell 变换器栈 |
| DefaultHLODLayer | TObjectPtr<UHLODLayer> | 默认 HLOD 层 |
| bOverrideEnableStreamingInEditor | TOptional<bool> | 编辑器流送覆盖 |

### EWorldPartitionInitState 枚举

| 值 | 说明 |
|-----|------|
| Uninitialized | 未初始化 |
| Initializing | 正在初始化 |
| Initialized | 已初始化 |
| Uninitializing | 正在取消初始化 |

### EWorldPartitionServerStreamingMode 枚举

| 值 | 说明 |
|-----|------|
| ProjectDefault = 0 | 使用项目默认设置 (wp.Runtime.EnableServerStreaming) |
| Disabled = 1 | 服务器流送禁用 |
| Enabled = 2 | 服务器流送启用 |
| EnabledInPIE = 3 | 仅 PIE 启用 |

### EWorldPartitionServerStreamingOutMode 枚举

| 值 | 说明 |
|-----|------|
| ProjectDefault = 0 | 使用项目默认设置 (wp.Runtime.EnableServerStreamingOut) |
| Disabled = 1 | 服务器流送输出禁用 |
| Enabled = 2 | 服务器流送输出启用 |

### EWorldPartitionDataLayersLogicOperator 枚举

| 值 | 说明 |
|-----|------|
| Or | 或逻辑 — 匹配任一数据层 |
| And | 与逻辑 — 匹配所有数据层 |

### 空间分区机制

RuntimeHash 使用空间 Hash 结构（Spatial Hash）管理 Cell：

- UWorldPartitionRuntimeSpatialHash — 空间 Hash 实现
- Cell 按 Grid 分层组织
- Bounds 决定 Cell 空间范围

### 核心方法

| 方法 | 说明 |
|------|------|
| Initialize(UWorld*, FTransform) | 初始化 WorldPartition |
| Uninitialize() | 取消初始化 |
| IsInitialized() | 是否已初始化 |
| IsStreamingEnabled() | 流送是否启用 |
| CanStream() | 是否可以流送 |
| IsServer() | 是否为服务器 |
| IsServerStreamingEnabled() | 服务器流送是否启用 |
| GetInstanceTransform() | 获取实例变换 |
| HasInstanceTransform() | 是否有实例变换 |
| SupportsStreaming() | 是否支持流送 |
| IsMainWorldPartition() | 是否为主 WorldPartition |
| IsStreamingCompleted() | 流送是否完成 |
| GetIntersectingCells() | 获取相交 Cell |
| GetDataLayerManager() | 获取数据层管理器 |
| RegisterActorDescContainerInstance() | 注册 Actor 描述容器实例 |
| PinActors() / UnpinActors() | 固定/取消固定 Actor |
| GenerateStreaming() | 生成流送（编辑器） |
| SetupHLODActors() | 设置 HLOD Actor |

### 源码引用

- Runtime/Engine/Public/WorldPartition/WorldPartition.h — UWorldPartition 定义
- Runtime/Engine/Public/WorldPartition/WorldPartitionRuntimeSpatialHash.h — RuntimeSpatialHash 定义

## Part C: WorldPartition RuntimeCell

### 继承关系

```
UWorldPartitionRuntimeCell → UObject
                           → IWorldPartitionCell
                           → IWorldPartitionCookPackageObject
```

### 概述

RuntimeCell 表示 PIE/Game 流送单元，指向外部 Actor/DataChunk 包。

### UWorldPartitionRuntimeCell 字段表

| 字段 | 类型 | 可见性 | 说明 |
|------|------|--------|------|
| RuntimeCellData | TObjectPtr<UWorldPartitionRuntimeCellData> | public | 运行时 Cell 数据（边界、流送信息等） |
| bIsAlwaysLoaded | bool | public (UPROPERTY) | 常驻加载标记 |
| bIsSpatiallyLoaded | bool | public (UPROPERTY) | 空间加载标记（核心） |
| bClientOnlyVisible | bool | private (UPROPERTY) | 仅客户端可见 |
| bIsHLOD | bool | private (UPROPERTY) | HLOD Cell |
| bIsCustomHLODPlaceholderCell | bool | private (UPROPERTY) | 自定义 HLOD 占位 Cell |
| bBlockOnSlowLoading | bool | private (UPROPERTY) | 阻塞慢加载 |
| ContentBundleID | FGuid | private (UPROPERTY) | Content Bundle ID |
| CellDebugColor | FLinearColor | private (UPROPERTY) | Cell 调试颜色 |
| CellGuid | FGuid | protected (UPROPERTY) | Cell GUID |
| SourceCellGuid | FGuid | protected (UPROPERTY) | 源 Cell GUID（注入 HLOD） |
| DataLayers | FDataLayerInstanceNames | private (UPROPERTY) | 数据层实例名称 |
| EffectiveWantedState | EDataLayerRuntimeState (mutable) | protected | 有效期望状态 |
| EffectiveWantedStateEpoch | int32 (mutable) | protected | 有效期望状态纪元 |
| UnsavedActorsContainer | TObjectPtr<UActorContainer> | public (EditorOnly) | 未保存 Actor 容器 |
| ExternalDataLayerAsset | TObjectPtr<UExternalDataLayerAsset> | private (EditorOnly) | 外部数据层资产 |

### EWorldPartitionRuntimeCellState 枚举

| 值 | 说明 |
|-----|------|
| Unloaded | 已卸载 |
| Loaded | 已加载 |
| Activated | 已激活 |

> 注意：枚举值顺序有意设计为 Unloaded < Loaded < Activated，流送查询代码依赖此顺序。

### SpatiallyLoaded 加载逻辑

| 值 | 加载时机 |
|-----|----------|
| true | 玩家进入 Cell Bounds 时加载 |
| false | 始终加载（类似 UE4 AlwaysLoaded） |

### FWorldPartitionRuntimeCellObjectMapping 结构

| 字段 | 类型 | 可见性 | 说明 |
|------|------|--------|------|
| Package | FName | public (EditorOnly) | 外部包名 |
| Path | FName | public (EditorOnly) | 对象路径 |
| BaseClass | FTopLevelAssetPath | public (EditorOnly) | Actor 基类 |
| NativeClass | FTopLevelAssetPath | public (EditorOnly) | Actor 原生类 |
| ContainerID | FActorContainerID | public (EditorOnly) | 容器 ID |
| ContainerTransform | FTransform | public (EditorOnly) | 容器变换 |
| EditorOnlyParentTransform | FTransform | public (EditorOnly) | 编辑器父变换 |
| ContainerPackage | FName | public (EditorOnly) | 容器包名 |
| WorldPackage | FName | public (EditorOnly) | World 包名 |
| ActorInstanceGuid | FGuid | public (EditorOnly) | Actor 实例 GUID |
| LoadedPath | FName | public (EditorOnly) | 加载路径 |
| bIsEditorOnly | bool | public (EditorOnly) | 仅编辑器标记 |
| PropertyOverrides | TArray<FWorldPartitionRuntimeCellPropertyOverride> | public (EditorOnly) | 属性覆盖 |

### FWorldPartitionRuntimeCellPropertyOverride 结构

| 字段 | 类型 | 可见性 | 说明 |
|------|------|--------|------|
| OwnerContainerID | FActorContainerID | public (EditorOnly) | 所有者容器 ID |
| AssetPath | FString | public (EditorOnly) | 资产路径 |
| PackageName | FName | public (EditorOnly) | 包名 |
| ContainerPath | FActorContainerPath | public (EditorOnly) | 容器路径 |

### FWorldPartitionRuntimeCellDebugInfo 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| Name | FString | Cell 名称 |
| GridName | FName | Grid 名称 |
| CoordX | int64 | X 坐标 |
| CoordY | int64 | Y 坐标 |
| CoordZ | int64 | Z 坐标 |

### IWorldPartitionCell 接口方法

| 方法 | 说明 |
|------|------|
| GetDataLayerInstances() | 获取数据层实例 |
| GetExternalDataLayerInstance() | 获取外部数据层实例 |
| ContainsDataLayer() | 是否包含数据层 |
| HasContentBundle() | 是否有 Content Bundle |
| GetDataLayers() | 获取数据层名称列表 |
| GetExternalDataLayer() | 获取外部数据层 |
| HasAnyDataLayer() | 是否有任何指定数据层 |
| GetLevelPackageName() | 获取关卡包名 |
| GetDebugName() | 获取调试名称 |
| GetOwningWorld() | 获取所属 World |
| GetOuterWorld() | 获取外层 World |

### 源码引用

- Runtime/Engine/Public/WorldPartition/WorldPartitionRuntimeCell.h — UWorldPartitionRuntimeCell 定义
- Runtime/Engine/Public/WorldPartition/WorldPartitionRuntimeCellData.h — Cell 数据结构
- Runtime/Engine/Public/WorldPartition/WorldPartitionRuntimeCellInterface.h — IWorldPartitionCell 接口

## Part D: External Actors 机制

### EActorPackagingScheme 枚举

Level.h 定义的 Actor 打包方案：

| 值 | 目录结构 | 文件夹数量 |
|-----|----------|-----------|
| Original | ZZ/ZZ/... | 最多 1679616 |
| Reduced | Z/ZZ/... | 最多 46656 |

### 目录结构

外部 Actor 目录结构：

```
__ExternalActors__/XX/YY/GUID.uasset
```

- XX、YY 为路径编码（基于 EActorPackagingScheme）
- GUID 为 Actor GUID（FGuid 格式）

### __ExternalActors__ 目录

ULevel::GetExternalActorsFolderName() 返回 "__ExternalActors__"：

- 位于关卡包同级目录
- 包含所有外部 Actor 文件

### GUID 追踪机制

| 字段 | 类型 | 说明 |
|------|------|------|
| ActorGuid | FGuid | Actor GUID（持久，流送关卡间一致） |
| ActorInstanceGuid | FGuid | Actor 实例 GUID（唯一，流送关卡间变化） |
| CellGuid | FGuid | Cell GUID |
| ContentBundleID | FGuid | Content Bundle ID |

### Import 表引用

.umap 通过 Import 表引用外部 Actor：

- Import 条目结构：ClassPackage, ClassName, Outer, ObjectName
- Import Index 为负数：-N 表示 Import[N-1]

### RuntimeCell 引用

RuntimeCell 的 Packages/Actors 数组引用外部 Actor：

- GetActors() 返回 Actor 包名数组
- ObjectMapping.Package 指向外部 Actor 包
- RuntimeCellData 存储 Cell 内容和边界信息

### 源码引用

- Runtime/Engine/Classes/Engine/Level.h — bUseExternalActors, EActorPackagingScheme 定义
- Runtime/Engine/Private/Engine/Level.cpp — External Actor 实现
- Runtime/Engine/Classes/GameFramework/Actor.h — ActorGuid, ActorInstanceGuid 定义
- Runtime/Engine/Public/WorldPartition/WorldPartitionRuntimeCell.h — FWorldPartitionRuntimeCellObjectMapping

## Part E: WorldComposition vs WorldPartition 对比

### 对比表

| 特性 | UE4 WorldComposition | UE5 WorldPartition |
|------|----------------------|--------------------|
| 空间分区 | Tile（2D Grid） | RuntimeCell（SpatiallyLoaded） |
| Actor 存储 | 内嵌 .umap | External Actors（默认） |
| 流送控制 | ZoneIndex + LODPackageNames | GridName + Bounds + SpatiallyLoaded |
| 加载触发 | LOD Distance | 玩家位置进入 Bounds |
| 常驻加载 | Tile LODLevels（AlwaysLoaded） | bIsSpatiallyLoaded=false |
| Data Layer | 无 | DataLayerInstanceNames |
| Origin Rebasing | WorldRoot + RebaseOriginDistance | InstanceTransform |
| 服务器流送 | 无 | ServerStreamingMode / ServerStreamingOutMode |
| Content Bundle | 无 | ContentBundleID |
| HLOD 支持 | 基础 | 完整 HLODLayer + StandaloneHLOD |
| 外部数据层 | 无 | ExternalDataLayerAsset + ExternalDataLayerManager |

### Tile vs RuntimeCell

| 属性 | Tile | RuntimeCell |
|------|------|-------------|
| 边界 | FWorldTileInfo.Bounds | RuntimeCellData.GetCellBounds() / GetStreamingBounds() |
| 位置 | FWorldTileInfo.Position（2D） | Cell Coord（XYZ，3D） |
| LOD | FWorldTileLODInfo | 无独立 LOD（DataLayer 管理） |
| 流送 | ULevelStreamingDynamic | UWorldPartitionRuntimeCell |
| 状态枚举 | ELevelStreamingState（8 值） | EWorldPartitionRuntimeCellState（3 值：Unloaded/Loaded/Activated） |
| 数据层 | 无 | FDataLayerInstanceNames |
| 对象映射 | 间接 | FWorldPartitionRuntimeCellObjectMapping |

### 迁移说明

UE4 → UE5 关卡迁移 WorldComposition → WorldPartition：

- WorldPartitionConverter 提供迁移工具
- Tile → RuntimeCell 映射
- Actor 内嵌 → External Actors 转换
- ZoneIndex → SpatialHash 映射

### 源码引用

- Runtime/Engine/Public/WorldPartition/WorldPartitionConverter.h — 迁移转换器

## Part F: 交叉引用

### StaticMesh Actor

| 文档 | 内容 | WorldPartition 引用 |
|------|------|---------------------|
| [static-mesh.md](static-mesh.md) | StaticMesh 结构 | External Actor StaticMesh |
| [static-mesh-collision.md](static-mesh-collision.md) | 碰撞数据 | Cell 内 StaticMesh Collision |

### IoStore External Asset

| 文档 | 内容 | WorldPartition 引用 |
|------|------|---------------------|
| [../cooked/iostore.md](../cooked/iostore.md) | IoStore 格式 | External Asset 存储机制 |

### Level Streaming

| 文档 | 内容 | WorldPartition 引用 |
|------|------|---------------------|
| [level-structure.md](level-structure.md) | Level Streaming | ULevelStreamingDynamic |

## 源码引用汇总

| 文件 | 路径 | 说明 |
|------|------|------|
| WorldPartition.h | Runtime/Engine/Public/WorldPartition/ | UWorldPartition 定义（含 ServerStreamingMode, DataLayerManager, StreamingPolicy） |
| WorldPartitionRuntimeCell.h | Runtime/Engine/Public/WorldPartition/ | UWorldPartitionRuntimeCell 定义（含 bIsSpatiallyLoaded, DataLayers, RuntimeCellData） |
| WorldPartitionRuntimeCellData.h | Runtime/Engine/Public/WorldPartition/ | Cell 数据结构 |
| WorldPartitionRuntimeSpatialHash.h | Runtime/Engine/Public/WorldPartition/ | RuntimeSpatialHash 定义 |
| WorldPartitionRuntimeCellInterface.h | Runtime/Engine/Public/WorldPartition/ | IWorldPartitionCell 接口 |
| WorldComposition.h | Runtime/Engine/Classes/Engine/ | UWorldComposition 定义（UE4） |
| WorldCompositionUtility.h | Runtime/Engine/Classes/Engine/ | FWorldTileInfo 定义 |
| Level.h | Runtime/Engine/Classes/Engine/ | EActorPackagingScheme 定义 |

## 版本差异

详见 [../version/asset-level.md](../version/asset-level.md)

UE4 与 UE5 开放世界系统主要差异：

- **系统架构：** UE4 WorldComposition；UE5 WorldPartition
- **Actor 存储：** UE4 内嵌；UE5 External Actors
- **空间分区：** UE4 Tile 2D；UE5 RuntimeCell 3D
- **Data Layer：** UE5 新增 Data Layer 机制（DataLayerInstanceNames, DataLayerManager, ExternalDataLayerManager）
- **服务器流送：** UE5 新增 ServerStreamingMode 和 ServerStreamingOutMode
- **Content Bundle：** UE5 新增 ContentBundleID 支持
- **状态枚举：** UE5 简化为 3 值枚举（Unloaded/Loaded/Activated），UE4 使用 8 值 ELevelStreamingState
- **对象映射：** UE5 RuntimeCell 通过 FWorldPartitionRuntimeCellObjectMapping 直接映射外部对象
- **Actor 空间加载：** UE5 在 AActor 级别新增 bIsSpatiallyLoaded 字段，取代已弃用的 EActorGridPlacement
