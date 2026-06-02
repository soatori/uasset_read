# 关卡资产版本差异

## 概述

关卡资产 (ULevel/UWorld — .umap 文件) 在 UE4 至 UE5 演进过程中经历重大格式变更，涉及 Actor 存储机制变更（内嵌 → External Actors）、开放世界系统变更（WorldComposition → WorldPartition）、Level Streaming 机制演进、预计算数据格式演进等变更。本文档汇总关卡相关关键版本差异。

> **源码同步状态**: 基于 `ObjectVersion.h` EUnrealEngineObjectUE4Version 枚举和 EUnrealEngineObjectUE5Version 枚举。

## 版本差异表格

### UE4 关卡版本变更

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 135 | VER_UE4_WORLD_LEVEL_INFO | World Level Info 引入 | FWorldTileInfo |
| 225 | VER_UE4_WORLD_LEVEL_INFO_UPDATED | World Level Info 更新（父级引用、流送距离） | ParentLevel, StreamingDistance |
| 321 | VER_UE4_WORLD_LEVEL_INFO_LOD_LIST | World Level Info LOD 列表 | LODLevels 数组 |
| 327 | VER_UE4_WORLD_LEVEL_INFO_ZORDER | World Level Info ZOrder | ZOrder |
| 343 | VER_UE4_WORLD_NAMED_AFTER_PACKAGE | World 命名跟随包名 | UWorld 名称规则 |
| 347 | VER_UE4_WORLD_LAYER_ENABLE_DISTANCE_STREAMING | World Layer 启用距离流送 | EnableDistanceStreaming |
| 464 | VER_UE4_LEVEL_STREAMING_DRAW_COLOR_TYPE_CHANGE | Level Streaming 绘制颜色类型变更 | LevelStreamingColor |

### UE5 关卡版本变更

| 版本号 | 版本名 | 变更描述 | 影响字段/结构 |
|-------|--------|----------|---------------|
| 1000 | INITIAL_VERSION | UE5 初始版本 | UE5 版本起点 |
| 1004 | LARGE_WORLD_COORDINATES | 大世界坐标 | FVector → double |
| 1015 | VERSE_CELLS | Verse Cells 支持 | Verse 相关 |
| 1017 | OS_SUB_OBJECT_SHADOW_SERIALIZATION | 子对象阴影序列化 | 子对象管理 |

## Part A: UE4 → UE5 关卡格式演进

### 版本里程碑

| 时期 | 版本范围 | 关卡格式特征 |
|------|----------|--------------|
| UE4.0-UE4.26 | 214-464 | WorldComposition + 内嵌 Actor |
| UE4.27-UE4.28 | 465-522 | WorldComposition 增强 + Level Instance |
| UE5.0+ | 1000+ | WorldPartition + External Actors |

### 核心变更总结

| 特性 | UE4 | UE5 |
|------|-----|-----|
| Actor 存储 | 内嵌 .umap Export 表 | External Actors（独立 .uasset） |
| 开放世界 | WorldComposition（Tile） | WorldPartition（RuntimeCell） |
| 空间分区 | 2D Grid（Tile Position） | 3D SpatialHash（Cell Bounds） |
| 加载触发 | LOD Distance | SpatiallyLoaded（玩家进入 Bounds） |
| Data Layer | 无 | DataLayerInstanceNames |
| Large World | float FVector | double FVector（可选） |

## Part B: Actor 存储演进

### UE4 内嵌 Actor 机制

UE4 所有 Actor 内嵌于 .umap Export 表：

- Export 表完整序列化 Actor 对象
- Actor 层次通过 Export Index 追踪
- 组件内嵌于 Actor（Instanced 属性）
- 子 Actor 内嵌于父 Actor 层次

### UE5 External Actors 机制

UE5 引入 External Actors 机制：

- bUseExternalActors = true 时，Actor 存储为独立 .uasset
- .umap 通过 Import 表引用外部 Actor
- EActorPackagingScheme 定义目录结构
- Actor GUID 独立存储用于追踪

### External Actors 引入时机

| UE 版本 | External Actors 特性 |
|---------|---------------------|
| UE5.0 | bUseExternalActors 引入（可选） |
| UE5.1 | External Actors 成为默认模式 |
| UE5.2 | EActorPackagingScheme 默认 Reduced |

### GUID 追踪演进

| 特性 | UE4 | UE5 |
|------|-----|-----|
| Actor GUID | 仅 EditorOnly | 独立存储（External Actor） |
| ActorPackage GUID | 无 | 对应 Actor 包 |
| ActorInstance GUID | 无 | ObjectMapping 追踪 |

## Part C: WorldComposition → WorldPartition 演进

### WorldComposition 字段演进

| 版本 | 变更 | 说明 |
|------|------|------|
| VER_UE4_WORLD_LEVEL_INFO (135) | FWorldTileInfo 引入 | Tile 信息结构 |
| VER_UE4_WORLD_LEVEL_INFO_UPDATED (225) | 父级引用、流送距离 | Tile 关系增强 |
| VER_UE4_WORLD_LEVEL_INFO_LOD_LIST (321) | LODLevels 数组 | Tile LOD 层级 |
| VER_UE4_WORLD_LAYER_ENABLE_DISTANCE_STREAMING (347) | EnableDistanceStreaming | 距离流送控制 |

### WorldPartition 字段演进

| UE 版本 | 变更 | 说明 |
|---------|------|------|
| UE5.0 | UWorldPartition 引入 | RuntimeHash 结构 |
| UE5.0 | RuntimeCell 结构 | SpatiallyLoaded 标记 |
| UE5.1 | DataLayerInstanceNames | Data Layer 管理 |
| UE5.2 | ContentBundle | Content Bundle 支持 |
| UE5.3 | ExternalStreamingObjects | 外部流送对象 |

### 迁移 API

WorldComposition → WorldPartition 转换：

- WorldPartitionConverter 提供迁移工具
- FWorldRenameFromRootContext 处理重命名
- ConvertAllActorsToPackaging() Actor 外部化

## Part D: LevelStreaming 演进

### UE4 LevelStreaming 子类演进

| 子类 | 引入版本 | 说明 |
|------|----------|------|
| ULevelStreamingAlwaysLoaded | UE4.0 | 常驻加载 |
| ULevelStreamingPersistent | UE4.10 | 持久流送 |
| ULevelStreamingDynamic | UE4.20 | 动态流送（WorldComposition） |
| ULevelStreamingLevelInstance | UE4.27 | Level Instance 流送 |

### UE5 LevelStreaming 与 WorldPartition 集成

| 特性 | 说明 |
|------|------|
| UWorldPartitionLevelStreamingDynamic | WorldPartition 动态流送 |
| WorldPartitionStreamingPolicy | 流送策略抽象 |
| EWorldPartitionServerStreamingMode | 服务器流送模式 |

### LODPackageNames → RuntimeCell Packages 演进

| UE4 | UE5 |
|-----|-----|
| LODPackageNames (FName 数组) | GetActors() (Actor 包名数组) |
| Tile LOD Distance | RuntimeCell SpatiallyLoaded |
| ULevelStreamingDynamic | UWorldPartitionRuntimeCell |

## Part E: 预计算数据演进

### 预计算光照格式演进

| 版本 | 版本名 | 变更 | 说明 |
|------|--------|------|------|
| 183 | VER_UE4_LOW_QUALITY_DIRECTIONAL_LIGHTMAPS | 低质量方向光照贴图 | Lightmap 格式 |
| 297 | VER_UE4_COMBINED_LIGHTMAP_TEXTURES | 合并光照贴图纹理 | Lightmap 存储 |
| 392 | VER_UE4_REFLECTION_DATA_IN_PACKAGES | 反射数据包存储 | ReflectionCapture |

### 体素光照贴图演进

| UE 版本 | 特性 |
|---------|------|
| UE4.20+ | FPrecomputedVolumetricLightmap 引入 |
| UE5.0+ | VolumetricLightmap 增强（LWC 支持） |

### 纹理流数据演进

| 版本 | 版本名 | 变更 | 说明 |
|------|--------|------|------|
| 362 | VER_UE4_REBUILD_TEXTURE_STREAMING_DATA_ON_LOAD | 加载时重建流数据 | StreamingData |
| 469 | VER_UE4_STREAMABLE_TEXTURE_MIN_MAX_DISTANCE | MinMax Distance | Distance 流送 |
| 461 | VER_UE4_STREAMABLE_TEXTURE_AABB | AABB 流送 | Bounds 流送 |

### BuildData 存储演进

| UE4 | UE5 |
|-----|-----|
| UMapBuildDataRegistry 内嵌 | _BuildData 独立包 |
| LightBuildLevelOffset | ContentBundleID |
| PrecomputedLightVolumeData | FPrecomputedVolumetricLightmap |

## Part F: 交叉引用

### Blueprint 版本文档

| 文档 | 内容 | 关卡引用 |
|------|------|----------|
| [asset-blueprint.md](asset-blueprint.md) | Blueprint 版本差异 | LevelScriptBlueprint 演进 |

### StaticMesh 版本文档

| 文档 | 内容 | 关卡引用 |
|------|------|----------|
| [asset-static-mesh.md](asset-static-mesh.md) | StaticMesh 版本差异 | StaticMesh Actor 演进 |

### 版本演进主文档

| 文档 | 内容 | 关卡引用 |
|------|------|----------|
| [ue4-evolution.md](ue4-evolution.md) | UE4 版本演进 | 关卡版本里程碑 |
| [ue5-evolution.md](ue5-evolution.md) | UE5 版本演进 | UE5 关卡变更 |

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| Level.h | Runtime/Engine/Classes/Engine/ | ULevel 定义 |
| World.h | Runtime/Engine/Classes/Engine/ | UWorld 定义 |
| WorldComposition.h | Runtime/Engine/Classes/Engine/ | UE4 WorldComposition |
| WorldPartition.h | Runtime/Engine/Public/WorldPartition/ | UE5 WorldPartition |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*
*Updated: 2026-06-01 — 基于 UE ObjectVersion.h 完整枚举同步版本号与版本名*
