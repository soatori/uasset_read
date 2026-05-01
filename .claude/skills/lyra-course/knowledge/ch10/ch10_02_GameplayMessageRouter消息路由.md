# GameplayMessageRouter 消息路由

## 概述

Lyra 的消息系统采用双层架构：底层是 `GameplayMessageRouter` 插件提供的通用 Tag 消息路由机制，上层是 `LyraGame/Messages/` 中基于此构建的 VerbMessage 消息协议层。消息系统支持服务器向客户端广播、本地监听、蓝图访问，以及消息处理器链式响应。

## 插件层：GameplayMessageRouter

[GameplayMessageSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/GameplayMessageRouter/Source/GameplayMessageRuntime/Public/GameFramework/GameplayMessageSubsystem.h)

作为 `UGameInstanceSubsystem`，提供基于 GameplayTag 的消息发布-订阅机制。

### 核心接口

- **BroadcastMessage**：按 Tag 广播消息，支持父标签遍历（父标签的监听者也能收到子标签的消息）
- **RegisterListener**：注册监听器，通过 `FGameplayMessageListenerParams` 配置监听参数
- **K2_BroadcastMessage**：蓝图版本的广播接口

### FGameplayMessageListenerParams

```cpp
FGameplayMessageListenerParams
{
    FGameplayTag Tag;                                     // 监听的标签
    TFunction<void(FGameplayTag, const TSharedPtr<void>&)> OnMessageReceived;  // 回调
    EGameplayMessageMatch MatchType = EGameplayMessageMatch::ExactMatch;       // 匹配方式
};
```

### 蓝图支持

通过 `AsyncAction_ListenForGameplayMessage` 提供蓝图异步节点，支持在蓝图中监听消息。

## 应用层：LyraGame/Messages/

[LyraGame/Messages/](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/)

### FLyraVerbMessage 消息结构

[LyraVerbMessage.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraVerbMessage.h)

核心消息结构，描述"谁(Instigator) 对谁(Target) 做了什么(Verb)"：

```cpp
USTRUCT(BlueprintType)
struct FLyraVerbMessage
{
    FGameplayTag Verb;                  // 动作标签
    TObjectPtr<UObject> Instigator;     // 发起者
    TObjectPtr<UObject> Target;         // 目标
    FGameplayTagContainer InstigatorTags;  // 发起者标签
    FGameplayTagContainer TargetTags;      // 目标标签
    FGameplayTagContainer ContextTags;     // 上下文标签
    double Magnitude;                   // 强度值
};
```

### FLyraVerbMessageReplication 消息复制

[LyraVerbMessageReplication.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraVerbMessageReplication.h) / [LyraVerbMessageReplication.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraVerbMessageReplication.cpp)

基于 `FFastArraySerializer` 的服务器到客户端消息复制机制：

1. 服务器调用 `AddMessage()` 将消息加入 `CurrentMessages` 数组，标记为脏
2. FastArray 通过 `NetDeltaSerialize` 自动同步到客户端
3. 客户端在 `PostReplicatedAdd` / `PostReplicatedChange` 中通过 `UGameplayMessageSubsystem` 本地重新广播
4. 本地监听者收到消息

这种设计实现了**服务器驱动的消息复制 + 本地消息系统分发**的解耦。

### ULyraVerbMessageHelpers 工具函数

[LyraVerbMessageHelpers.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraVerbMessageHelpers.h) / [LyraVerbMessageHelpers.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraVerbMessageHelpers.cpp)

- `GetPlayerStateFromObject`：从任意 UObject 获取对应的 PlayerState
- `GetPlayerControllerFromObject`：从任意 UObject 获取对应的 PlayerController
- `VerbMessageToCueParameters` / `CueParametersToVerbMessage`：VerbMessage 与 GameplayCueParameters 的双向转换

### FLyraNotificationMessage 通知消息

[LyraNotificationMessage.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraNotificationMessage.h) / [LyraNotificationMessage.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraNotificationMessage.cpp)

用于击杀反馈、拾取提示等 UI 瞬时通知，通过 `TargetChannel` 区分不同通知频道。

```cpp
USTRUCT(BlueprintType)
struct FLyraNotificationMessage
{
    FGameplayTag TargetChannel;          // 目标频道
    TObjectPtr<APlayerState> TargetPlayer;  // 目标玩家
    FText PayloadMessage;                // 显示文本
    FGameplayTag PayloadTag;             // 负载标签
    TObjectPtr<UObject> PayloadObject;   // 负载对象
};
```

### UGameplayMessageProcessor 消息处理器基类

[GameplayMessageProcessor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/GameplayMessageProcessor.h) / [GameplayMessageProcessor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/GameplayMessageProcessor.cpp)

采用**模板方法模式**的基类，子类只需重写 `StartListening()` 在其中注册消息监听，即可自动管理生命周期。

- `BeginPlay()` → `StartListening()`
- `EndPlay()` → `StopListening()`，自动清理所有 ListenerHandles
- `GetServerTime()`：通过 `GetWorld()->GetGameState()->GetServerWorldTimeSeconds()` 获取服务器时间
