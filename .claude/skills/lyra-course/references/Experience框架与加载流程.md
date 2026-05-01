# Experience 框架与加载流程

## 概述

Experience 框架是 Lyra 启动流程的编排核心。它将"游戏模式初始化"从硬编码的 GameMode 中解耦，变为由数据资产（ExperienceDefinition）驱动的可配置流程。

---

## 三阶段架构

```
ExperienceDefinition（数据层）
    ↓ 引用
ExperienceManagerComponent（状态机层）
    ↓ 执行
UGameFeatureAction（动作层，Engine 原生类）
```

---

## 第一阶段：ExperienceDefinition

**文件**：`Source/LyraGame/GameModes/LyraExperienceDefinition.h`

```cpp
UCLASS(BlueprintType, Meta = (DisplayName = "Lyra Experience Definition"))
class LYRAGAME_API ULyraExperienceDefinition : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    // 此 Experience 需要加载的 GameFeature 插件列表
    UPROPERTY(EditDefaultsOnly, Category = "Experience")
    TArray<FString> GameFeaturesToEnable;

    // 此 Experience 需要执行的 GameFeatureAction 集合
    UPROPERTY(EditDefaultsOnly, Category = "Experience")
    TArray<TObjectPtr<ULyraExperienceActionSet>> ActionSets;

    // 默认 Gameplay 类
    UPROPERTY(EditDefaultsOnly, Category = "Gameplay")
    TSubclassOf<APawn> PawnClass;

    UPROPERTY(EditDefaultsOnly, Category = "Gameplay")
    TSubclassOf<AHUD> HUDClass;

    UPROPERTY(EditDefaultsOnly, Category = "Gameplay")
    TSubclassOf<APlayerController> PlayerControllerClass;

    UPROPERTY(EditDefaultsOnly, Category = "Gameplay")
    TSubclassOf<APlayerState> PlayerStateClass;

    UPROPERTY(EditDefaultsOnly, Category = "Gameplay")
    TSubclassOf<AGameStateBase> GameStateClass;
};
```

ExperienceDefinition 作为数据资产存放在 Content 目录，可在编辑器中配置。通过切换不同的 Experience，可以完全改变游戏的 GameFeature 集和默认 Gameplay 类。

---

## 第二阶段：ExperienceManagerComponent

**文件**：`Source/LyraGame/GameModes/LyraExperienceManagerComponent.h`

ExperienceManagerComponent 挂载在 GameState 上，管理 Experience 加载状态机。

### 状态流转

```
Inactive → WaitingForAction → LoadingActions → Loaded → Deactivating
    ↑                                                     │
    └─────────────────────────────────────────────────────┘
```

### 关键方法

```cpp
UCLASS()
class LYRAGAME_API ULyraExperienceManagerComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    // 开始加载 Experience
    void StartExperience(ULyraExperienceDefinition* Experience);

    // 当前加载进度（0~1）
    float GetExperienceLoadProgress() const;

    // 判断是否加载完成
    bool IsExperienceLoaded() const;

protected:
    // 状态机推进
    void OnExperienceLoaded();
    void OnExperienceFullLoadCompleted();

    // Action 执行完毕回调
    void OnActionActivationCompleted();
};
```

### 加载流程

1. GameMode 在 `InitGame` 阶段调用 `StartExperience`
2. ManagerComponent 将状态设为 `WaitingForAction`
3. 遍历 Experience 的 `ActionSets`，收集所有 `UGameFeatureAction`
4. 逐个激活 GameFeatureAction，状态推进到 `LoadingActions`
5. 所有 Action 完成后，状态推进到 `Loaded`
6. GameMode 收到 `OnExperienceFullLoadCompleted` 后开始 Spawn Player

---

## 第三阶段：UGameFeatureAction

Lyra 不定义自定义 ExperienceAction 类，而是直接使用 Engine 原生的 `UGameFeatureAction` 机制。`ULyraExperienceActionSet` 是 `UDataAsset`，持有 `TArray<TObjectPtr<UGameFeatureAction>>`，将所有 Action 聚合到单个资产中。

**文件**：`Source/LyraGame/GameModes/LyraExperienceActionSet.h`

```cpp
UCLASS()
class LYRAGAME_API ULyraExperienceActionSet : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditDefaultsOnly, Category = "Experience")
    TArray<TObjectPtr<UGameFeatureAction>> Actions;
};
```

Engine 提供的标准 `UGameFeatureAction` 子类包括：

| Action | 功能 |
|--------|------|
| UGameFeatureAction_AddComponents | 向指定 Actor 添加组件 |
| UGameFeatureAction_DataRegistry | 注册 DataRegistry |
| UGameFeatureAction_WorldActionBase | 世界操作基类 |

### GameFeature 插件激活流程

```
ExperienceManagerComponent::StartExperience()
    → 遍历 ActionSets，收集所有 UGameFeatureAction
    → 对每个 GameFeatureAction 调用 OnGameFeatureActivating()
    → 引擎加载插件中的 .uplugin
    → 执行插件的注册逻辑（AssetManager、PrimaryAsset）
    → 状态推进到 Loaded
```

---

## 自定义 GameFeatureAction

继承 `UGameFeatureAction` 并在 `OnGameFeatureActivating`/`OnGameFeatureDeactivating` 中注入自定义逻辑：

```cpp
UCLASS()
class UMyGameFeatureAction_CustomInit : public UGameFeatureAction
{
    GENERATED_BODY()

protected:
    virtual void OnGameFeatureActivating() override
    {
        // 在 GameFeature 加载完成后初始化自定义管理器
    }

    virtual void OnGameFeatureDeactivating() override
    {
        // 清理
    }
};
```

自定义 GameFeatureAction 可通过 `ULyraExperienceActionSet` 的 Actions 数组引用，无需额外 Lyra 层封装。

---

## GameMode 工作流程

**文件**：`Source/LyraGame/GameModes/LyraGameMode.h`

```
ALyraGameMode::InitGame()
    → 加载默认 ExperienceDefinition
    → GameState 上的 ManagerComponent::StartExperience()

ALyraGameMode::OnExperienceLoaded()
    → 设置 GameState、PlayerState 等类
    → 后续 SpawnPlayer 使用 Experience 配置的类
```

完整流程：
```
InitGame
    → Server 加载 ExperienceDefinition
    → 激活 GameFeature 插件
    → OnExperienceFullLoadCompleted
    → GameMode 设置默认类
    → 等待玩家进入
    → SpawnPlayer → 指定 Pawn/Controller/HUD
```

---

## 关键设计要点

1. **Experience 可在运行时切换** — 切换时 ManagerComponent 走 Deactivating → Inactive 循环
2. **GameFeature 插件的动态加载** — 意味着功能模块可以按需装载，减少初始加载时间
3. **GameFeatureAction 的串行激活** — 每个 Action 完成激活后才执行下一个，保证依赖顺序
4. **数据驱动的初始化** — 通过数据资产配置，无需修改 C++ 代码即可改变游戏行为
