# ReplicationGraph 网络复制图

## 概述

ReplicationGraph 是 UE5 提供的高性能网络复制框架，Lyra 通过 `ULyraReplicationGraph` 实现了三层节点结构来优化 Actor 的网络复制效率。系统根据 Actor 类型将其路由到不同的复制节点，实现空间化、频率限制、始终相关等不同策略。

## 文件结构

- [LyraReplicationGraph.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraph.h) / [LyraReplicationGraph.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraph.cpp) — 主图与自定义节点
- [LyraReplicationGraphTypes.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraphTypes.h) — EClassRepNodeMapping 枚举定义
- [LyraReplicationGraphSettings.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraphSettings.h) / [LyraReplicationGraphSettings.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraphSettings.cpp) — 配置类

## 三层节点结构

```
ULyraReplicationGraph
  ├── GridNode (UReplicationGraphNode_GridSpatialization2D)
  │     处理 Spatialize_Static / Dynamic / Dormancy 的 Actor
  │
  ├── AlwaysRelevantNode (UReplicationGraphNode_ActorList)
  │     处理 RelevantAllConnections 的全局始终相关 Actor
  │
  ├── ULyraReplicationGraphNode_PlayerStateFrequencyLimiter (全局节点)
  │     每帧滚动返回 2 个 PlayerState
  │
  └── [每个连接] ULyraReplicationGraphNode_AlwaysRelevant_ForConnection
         连接级始终相关（Viewer、ViewTarget、Pawn、PlayerState、StreamingLevel Actor）
```

## EClassRepNodeMapping Actor 路由策略

[LyraReplicationGraphTypes.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraphTypes.h#L10-L20)

```cpp
enum class EClassRepNodeMapping : uint32
{
    NotRouted,                  // 不路由到任何节点，由特殊节点处理
    RelevantAllConnections,     // 路由到 AlwaysRelevantNode
    Spatialize_Static,          // 路由到 GridNode：不移动的 Actor
    Spatialize_Dynamic,         // 路由到 GridNode：频繁移动的 Actor
    Spatialize_Dormancy,        // 路由到 GridNode：休眠时静态、激活时动态
};
```

路由策略通过 `TClassMap<EClassRepNodeMapping>` 映射表管理，支持代码硬编码、配置文件自定义、运行时惰性初始化三种方式。

## RouteAddNetworkActorToNodes 路由逻辑

[LyraReplicationGraph.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraph.cpp#L582-L623)

```cpp
void ULyraReplicationGraph::RouteAddNetworkActorToNodes(...)
{
    switch(Policy)
    {
        case NotRouted: break;
        case RelevantAllConnections:
            AlwaysRelevantNode->NotifyAddNetworkActor(ActorInfo);
            break;
        case Spatialize_Static:
            GridNode->AddActor_Static(ActorInfo, GlobalInfo);
            break;
        case Spatialize_Dynamic:
            GridNode->AddActor_Dynamic(ActorInfo, GlobalInfo);
            break;
        case Spatialize_Dormancy:
            GridNode->AddActor_Dormancy(ActorInfo, GlobalInfo);
            break;
    }
}
```

## 自定义节点

### ULyraReplicationGraphNode_AlwaysRelevant_ForConnection

[LyraReplicationGraph.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraph.h#L67-L93)

每帧为每个连接构建始终相关列表，不维护持久列表。包含：
- Viewers（InViewer + ViewTarget）
- PlayerController 的 Pawn
- PlayerState（50% 帧节流）
- StreamingLevel 上的始终相关 Actor
- GameplayDebugger（调试模式下）

### ULyraReplicationGraphNode_PlayerStateFrequencyLimiter

[LyraReplicationGraph.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraph.h#L99-L123)

每帧最多返回 `TargetActorsPerFrame（2）` 个 PlayerState：
- `PrepareForReplication` 每帧重建列表，将全世界的 PlayerState 按 TargetActorsPerFrame 分桶
- `GatherActorListsForConnection` 根据 `ReplicationFrameNum` 轮询返回对应桶的内容

## 创建流程

[LyraReplicationGraph.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraph.cpp#L135-L177)

通过 `ConditionalCreateReplicationDriver` 工厂函数创建，该函数通过 `UReplicationDriver::CreateReplicationDriverDelegate()` 绑定。

```cpp
UReplicationDriver* ConditionalCreateReplicationDriver(UNetDriver* ForNetDriver, UWorld* World)
{
    const ULyraReplicationGraphSettings* LyraRepGraphSettings = GetDefault<ULyraReplicationGraphSettings>();
    if (LyraRepGraphSettings && LyraRepGraphSettings->bDisableReplicationGraph)
        return nullptr;  // 可禁用 ReplicationGraph 回退引擎默认

    TSubclassOf<ULyraReplicationGraph> GraphClass = ...;
    return NewObject<ULyraReplicationGraph>(GetTransientPackage(), GraphClass.Get());
}
```

## 配置项

[LyraReplicationGraphSettings.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraReplicationGraphSettings.h)

- `bDisableReplicationGraph`：是否禁用（默认 true）
- `DefaultReplicationGraphClass`：可配置的 Graph 子类
- `TargetKBytesSecFastSharedPath`：FastShared 路径带宽
- `SpatialGridCellSize` / `SpatialBiasX/Y`：空间网格参数
- `DynamicActorFrequencyBuckets`：动态 Actor 频率桶数（默认 3）
- `ClassSettings`：通过配置自定义每个类的路由策略
