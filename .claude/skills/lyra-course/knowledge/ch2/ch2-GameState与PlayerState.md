# GameState 与 PlayerState

## ALyraGameState

[ALyraGameState](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraGameState.h) 继承自 `AModularGameStateBase`，同时实现 `IAbilitySystemInterface`。

### 职责

1. **持有 ExperienceManagerComponent** — GameState 上挂载 `ULyraExperienceManagerComponent` 管理 Experience 加载
2. **网络同步** — 所有客户端共享的游戏状态（如团队得分、游戏阶段）
3. **AbilitySystem 接口** — `IAbilitySystemInterface` 提供全局的 `UAbilitySystemComponent` 访问

### ModularGameplay 支持

`AModularGameStateBase` 是 `ModularGameplayActors` 插件提供的基类，支持 GameFeature 插件动态向 GameState 添加组件，无需修改基类代码。

```cpp
UCLASS()
class ALyraGameState : public AModularGameStateBase, public IAbilitySystemInterface
{
    GENERATED_BODY()

public:
    // IAbilitySystemInterface
    virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override;

    // Experience 管理器组件
    UPROPERTY()
    TObjectPtr<ULyraExperienceManagerComponent> ExperienceManagerComponent;

    // 玩家生成管理器
    UPROPERTY()
    TObjectPtr<ULyraPlayerSpawningManagerComponent> PlayerSpawningManagerComponent;
};
```

## ALyraPlayerState

[ALyraPlayerState](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraPlayerState.h) 继承自 `AModularPlayerState`，同时实现 `IAbilitySystemInterface` 和 `ILyraTeamAgentInterface`。

### 职责

1. **持有个体 ASC** — 每个玩家拥有独立的 `UAbilitySystemComponent`
2. **TagStack 持有者** — 使用 `FGameplayTagStack` 管理玩家的 Tag 计数
3. **队伍接口** — 实现 `ILyraTeamAgentInterface`，标识玩家所属队伍

### 核心属性

```cpp
UCLASS()
class ALyraPlayerState : public AModularPlayerState, 
    public IAbilitySystemInterface,
    public ILyraTeamAgentInterface
{
    // 玩家的 ASC
    UPROPERTY()
    TObjectPtr<ULyraAbilitySystemComponent> AbilitySystemComponent;

    // TagStack 容器
    UPROPERTY(Replicated)
    FGameplayTagStackContainer TagStacks;

    // 队伍 ID
    UPROPERTY(ReplicatedUsing = OnRep_TeamId)
    ELyraTeamType TeamType;

    // 队伍显示资产（颜色、材质等）
    UPROPERTY(ReplicatedUsing = OnRep_TeamDisplayAsset)
    TObjectPtr<ULyraTeamDisplayAsset> TeamDisplayAsset;
};
```

## FGameplayTagStack 容器

[FGameplayTagStack](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/GameplayTagStack.h) 是基于 `FFastArraySerializer` 的 Tag 计数机制。

### FastArray 原理

使用 `FFastArraySerializer` 实现高效的网络同步，仅传输发生变化的元素而非整个数组。

```cpp
USTRUCT()
struct FGameplayTagStack : public FFastArraySerializerItem
{
    GENERATED_BODY()

    UPROPERTY()
    FGameplayTag Tag;

    UPROPERTY()
    int32 StackCount = 0;
};

USTRUCT()
struct FGameplayTagStackContainer : public FFastArraySerializer
{
    GENERATED_BODY()

    // 增加指定 Tag 的计数
    void AddStack(FGameplayTag Tag, int32 Count);

    // 获取指定 Tag 的当前计数
    int32 GetStackCount(FGameplayTag Tag) const;

    // 是否包含指定 Tag
    bool ContainsTag(FGameplayTag Tag) const;

    UPROPERTY()
    TArray<FGameplayTagStack> Stacks;
};
```

### 使用场景

- **资源计数** — 弹药数量、货币等
- **状态标记** — 是否拥有某种状态
- **权限判断** — 是否拥有特定 Tag

### FastArray 关键函数

`FFastArraySerializer` 中的关键函数：

| 函数 | 说明 |
|------|------|
| `MarkItemDirty(Item)` | 标记某个元素为脏，触发增量同步 |
| `MarkArrayDirty()` | 强制全量同步 |
| `SetItemDelta replicated(Item)` | 增量更新 |
| `PreReplicatedRemove` | 元素移除前的回调 |
| `PostReplicatedAdd` | 元素添加后的回调 |
| `PostReplicatedChange` | 元素修改后的回调 |

## 常见 G 开头的全局变量

UE 引擎中常见的 G 开头全局变量：

| 全局变量 | 类型 | 说明 |
|---------|------|------|
| `GEngine` | `UEngine*` | 引擎实例 |
| `GWorld` | `UWorld*` | 当前活动世界 |
| `GConfig` | `FConfigCacheIni*` | 配置系统 |
| `GEditor` | `UEditorEngine*` | 编辑器引擎实例 |
| `GEditorToDiscard` | `bool` | 编辑器重启标记 |
| `GFileManager` | `IFileManager*` | 文件管理器 |
| `GLog` | `FOutputDevice*` | 日志系统 |
| `GIsEditor` | `bool` | 是否编辑器模式 |
| `GIsGameThread` | `bool` | 当前是否游戏线程 |
| `GIsServer` | `bool` | 当前是否服务器 |
| `GIsClient` | `bool` | 当前是否客户端 |
| `GScreen` | `FViewport*` | 屏幕视口 |
| `GInputKeyframeInformation` | 集合 | 输入关键帧信息 |
| `GNearClippingPlane` | `float` | 近裁剪面距离 |

### `GIsServer` 和 `GIsClient` 的区分

| 环境 | GIsServer | GIsClient |
|------|-----------|-----------|
| 独立游戏（Standalone） | true | true |
| 专用服务器（DS） | true | false |
| 客户端 | false | true |
| 编辑器 PIE 服务器 | true | true |
| 编辑器 PIE 客户端 | false | true |
