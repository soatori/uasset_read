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
```

### UWorldPartition 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| RuntimeHash | TObjectPtr<UWorldPartitionRuntimeHash> | 运行时 Hash |
| StreamingPolicy | TObjectPtr<UWorldPartitionStreamingPolicy> | 流送策略 |
| EnableStreaming | bool | 流送启用标记 |
| EnableLoadingInEditor | bool | 编辑器加载启用 |
| InstanceTransform | TOptional<FTransform> | 实例变换 |

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
| ProjectDefault | 使用项目默认设置 |
| Disabled | 服务器流送禁用 |
| Enabled | 服务器流送启用 |
| EnabledInPIE | 仅 PIE 启用 |

### 空间分区机制

RuntimeHash 使用空间 Hash 结构（Spatial Hash）管理 Cell：

- UWorldPartitionRuntimeSpatialHash — 空间 Hash 实现
- Cell 按 Grid 分层组织
- Bounds 决定 Cell 空间范围

### 源码引用

- Runtime/Engine/Public/WorldPartition/WorldPartition.h — UWorldPartition 定义
- Runtime/Engine/Public/WorldPartition/WorldPartitionRuntimeSpatialHash.h — RuntimeSpatialHash 定义

## Part C: WorldPartition RuntimeCell

### 继承关系

```
UWorldPartitionRuntimeCell → UObject
```

### 概述

RuntimeCell 表示 PIE/Game 流送单元，指向外部 Actor/DataChunk 包。

### UWorldPartitionRuntimeCell 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| Name | FString | Cell 名称 |
| GridName | FName | 所属 Grid 名称 |
| DataLayers | FDataLayerInstanceNames | Data Layer 实例名称 |
| bIsSpatiallyLoaded | bool | 空间加载标记（核心） |
| bIsAlwaysLoaded | bool | 常驻加载标记 |
| bClientOnlyVisible | bool | 仅客户端可见 |
| ContentBundleID | FGuid | Content Bundle ID |

### EWorldPartitionRuntimeCellState 枚举

| 值 | 说明 |
|-----|------|
| Unloaded | 已卸载 |
| Loaded | 已加载 |
| Activated | 已激活 |

### SpatiallyLoaded 加载逻辑

| 值 | 加载时机 |
|-----|----------|
| true | 玩家进入 Cell Bounds 时加载 |
| false | 始终加载（类似 UE4 AlwaysLoaded） |

### FWorldPartitionRuntimeCellObjectMapping 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| Package | FName | 外部包名 |
| Path | FName | 对象路径 |
| BaseClass | FTopLevelAssetPath | Actor 基类 |
| NativeClass | FTopLevelAssetPath | Actor 原生类 |
| ContainerID | FActorContainerID | 容器 ID |
| ContainerTransform | FTransform | 容器变换 |
| ActorInstanceGuid | FGuid | Actor 实例 GUID |
| bIsEditorOnly | bool | 仅编辑器标记 |

### FWorldPartitionRuntimeCellPropertyOverride 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| OwnerContainerID | FActorContainerID | 所有者容器 ID |
| AssetPath | FString | 资产路径 |
| PackageName | FName | 包名 |
| ContainerPath | FActorContainerPath | 容器路径 |

### 源码引用

- Runtime/Engine/Public/WorldPartition/WorldPartitionRuntimeCell.h — UWorldPartitionRuntimeCell 定义
- Runtime/Engine/Public/WorldPartition/WorldPartitionRuntimeCellData.h — Cell 数据结构

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
| ActorGuid | FGuid | Actor GUID |
| ActorPackageGuid | FGuid | Actor 包 GUID |
| ActorInstanceGuid | FGuid | Actor 实例 GUID（ObjectMapping） |

### Import 表引用

.umap 通过 Import 表引用外部 Actor：

- Import 条目结构：ClassPackage, ClassName, Outer, ObjectName
- Import Index 为负数：-N 表示 Import[N-1]

### RuntimeCell 引用

RuntimeCell 的 Packages/Actors 数组引用外部 Actor：

- GetActors() 返回 Actor 包名数组
- ObjectMapping.Package 指向外部 Actor 包

### 源码引用

- Runtime/Engine/Classes/Engine/Level.h — bUseExternalActors, EActorPackagingScheme 定义
- Runtime/Engine/Private/Engine/Level.cpp — External Actor 实现

## Part E: WorldComposition vs WorldPartition 对比

### 对比表

| 特性 | UE4 WorldComposition | UE5 WorldPartition |
|------|----------------------|--------------------|
| 空间分区 | Tile（2D Grid） | RuntimeCell（SpatiallyLoaded） |
| Actor 存储 | 内嵌 .umap | External Actors（默认） |
| 流送控制 | ZoneIndex + LODPackageNames | GridName + Bounds + SpatiallyLoaded |
| 加载触发 | LOD Distance | 玩家位置进入 Bounds |
| 常驻加载 | Tile LODLevels（AlwaysLoaded） | bSpatiallyLoaded=false |
| Data Layer | 无 | DataLayerInstanceNames |
| Origin Rebasing | WorldRoot + RebaseOriginDistance | InstanceTransform |

### Tile vs RuntimeCell

| 属性 | Tile | RuntimeCell |
|------|------|-------------|
| 边界 | FWorldTileInfo.Bounds | Cell Bounds |
| 位置 | FWorldTileInfo.Position（2D） | Cell Coord（XYZ） |
| LOD | FWorldTileLODInfo | 无独立 LOD（DataLayer 管理） |
| 流送 | ULevelStreamingDynamic | UWorldPartitionRuntimeCell |

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
| WorldPartition.h | Runtime/Engine/Public/WorldPartition/ | UWorldPartition 定义 |
| WorldPartitionRuntimeCell.h | Runtime/Engine/Public/WorldPartition/ | UWorldPartitionRuntimeCell 定义 |
| WorldPartitionRuntimeSpatialHash.h | Runtime/Engine/Public/WorldPartition/ | RuntimeSpatialHash 定义 |
| WorldComposition.h | Runtime/Engine/Classes/Engine/ | UWorldComposition 定义（UE4） |
| WorldCompositionUtility.h | Runtime/Engine/Classes/Engine/ | FWorldTileInfo 定义 |
| Level.h | Runtime/Engine/Classes/Engine/ | EActorPackagingScheme 定义 |

## 版本差异

详见 [../version/asset-level.md](../version/asset-level.md)

UE4 与 UE5 开放世界系统主要差异：

- **系统架构：** UE4 WorldComposition；UE5 WorldPartition
- **Actor 存储：** UE4 内嵌；UE5 External Actors
- **空间分区：** UE4 Tile 2D；UE5 RuntimeCell 3D
- **Data Layer：** UE5 新增 Data Layer 机制