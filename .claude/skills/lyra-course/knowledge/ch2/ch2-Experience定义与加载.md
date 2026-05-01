# Experience 定义与加载

## 概述

Experience（体验）是 Lyra 的核心设计模式。它使用 `ULyraExperienceDefinition` 数据资产替代传统的硬编码 GameMode 玩法加载逻辑，使得每个地图/游戏模式可以独立声明需要加载的 GameFeature 插件、GameplayAbility、AttributeSet、GameplayEffect、PawnData 等。

## ExperienceDefinition 数据资产

[ULyraExperienceDefinition](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraExperienceDefinition.h) 继承自 `UPrimaryDataAsset`，定义了一个 Experience 包含的内容：

```cpp
UCLASS()
class ULyraExperienceDefinition : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    // Experience 关联的 GameFeature 插件列表
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TArray<FString> GameFeaturesToEnable;

    // 默认的 PawnData（定义角色属性、动画、相机等）
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TObjectPtr<const ULyraPawnData> DefaultPawnData;

    // Experience 加载时授予的 GameplayAbility
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TArray<TSoftClassPtr<ULyraGameplayAbility>> GameplayAbilities;

    // Experience 加载时授予的 AttributeSet
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TArray<TSoftClassPtr<ULyraAttributeSet>> AttributeSets;

    // Experience 加载时应用的 GameplayEffect
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TArray<TSoftClassPtr<UGameplayEffect>> GameplayEffects;

    // Experience 动作集（进一步封装 GA/GE/Attribute 的集合）
    UPROPERTY(EditDefaultsOnly, Category = Gameplay)
    TArray<TObjectPtr<ULyraExperienceActionSet>> Actions;

    // 自定义 Experience 加载时的动作
    UPROPERTY(EditDefaultsOnly, Instanced, Category = Actions)
    TArray<TObjectPtr<ULyraExperienceAction>> Actions_DEPRECATED;

    // 自定义 Experience 加载时的动作（新版）
    UPROPERTY(EditDefaultsOnly, Instanced, Category = Actions)
    TArray<TObjectPtr<ULyraExperienceAction>> ExperienceActions;
};
```

### ExperienceActionSet

[ULyraExperienceActionSet](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraExperienceActionSet.h) 是 `UPrimaryDataAsset`，将多个 GA/GE/AttributeSet 打包为一个可复用的集合，多个 Experience 可以共享同一个 ActionSet。

## ExperienceManagerComponent 加载流程

[ULyraExperienceManagerComponent](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraExperienceManagerComponent.h) 挂在 `ALyraGameState` 上，继承自 `UGameStateComponent`，实现 `ILoadingProcessInterface`。

### 加载状态

Experience 加载过程通过 `ELyraExperienceLoadState` 枚举跟踪状态：

- `Unloaded` — 未加载
- `Loading` — 正在加载
- `LoadingGameFeatures` — 正在激活 GameFeature 插件
- `LoadingChaosTestingWait` — 等待混沌测试
- `ExecutingActions` — 执行 Experience 动作
- `Loaded` — 加载完成
- `Deactivate` — 反激活

### 核心加载流程

```cpp
// 请求开始加载 Experience
void ULyraExperienceManagerComponent::StartExperienceLoad(ULyraExperienceDefinition* Experience)
{
    CurrentExperience = Experience;
    SetCurrentState(ELyraExperienceLoadState::Loading);

    // 加载并激活 GameFeature 插件
    // 异步——调用 UE 的 GameFeature 插件 API
    for (FString& PluginURL : Experience->GameFeaturesToEnable)
    {
        // 将插件名转换为 URL
        FString PluginURL;
        UGameFeaturesSubsystem::Get().GetPluginURLByName(PluginName, PluginURL);
        // 加载并激活...
    }

    // 异步加载所有 GameplayAbilities、AttributeSets、GameplayEffects
    // LoadPackages 使用 FSoftObjectPath 逐个检查并异步加载
}
```

### 加载完成后

当所有插件加载完成且资产就绪后：

```cpp
void ULyraExperienceManagerComponent::OnExperienceLoadComplete()
{
    // 授予 Experience 中定义的能力和属性
    // 将 GA/GE/AttributeSet 注册到全局能力系统
    // 广播 OnExperienceLoaded 事件
    SetCurrentState(ELyraExperienceLoadState::ExecutingActions);
    // 执行 ExperienceActions...
}
```

## GameInstance 中的 Experience 管理

[ULyraGameInstance](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraGameInstance.h) 继承自 `UCommonGameInstance`，负责用户登录和 Experience 生命周期管理：

```cpp
void ULyraGameInstance::BeginLoginAttempt(ULocalPlayer* LocalPlayer, ...)
{
    // 检查是否需要在线子系统登录
    // 调用 OnUserLoginComplete 回调
}
```

### 异步询问体验加载

`ULyraGameInstance` 中的 `ULyraUserFacingExperienceDefinition` 提供了前端 UI 触发 Experience 加载的能力——通过 `TryLoadExperience()` 在用户选择模式/地图后触发 Experience 加载。

## WorldSettings 中的默认 Experience

[ALyraWorldSettings](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraWorldSettings.h) 继承自 `AWorldSettings`，定义了默认的 Experience：

```cpp
UCLASS()
class ALyraWorldSettings : public AWorldSettings
{
    // 地图默认使用的 Experience
    UPROPERTY(EditDefaultsOnly, Category = Game)
    TSoftObjectPtr<ULyraExperienceDefinition> DefaultExperience;
};
```

### OnPacketHandling 错误处理

`ALyraWorldSettings` 中还重写了 `OnPacketHandling` 的错误处理逻辑：

```cpp
virtual void OnPacketHandling(EPacketHandling& OutHandling, bool& OutRemoveNetworkActors, bool& bForceFastArrayDev) override;
```
