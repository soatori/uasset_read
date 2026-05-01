# InitState 初始化状态机

## 概述

Lyra 使用**4 态初始化状态机**协调 Pawn 各组件（ASC、Input、Camera、Movement）的初始化顺序。任何实现 `IGameFrameworkInitStateInterface` 的组件都可以注册到状态机中，按依赖顺序逐步初始化。

---

## 核心接口

**文件**：接口来自 Engine 模块 `Components/GameFrameworkInitStateInterface.h`

```cpp
class IGameFrameworkInitStateInterface
{
public:
    // 返回此组件的特征名，用于标识和依赖匹配
    virtual FName GetFeatureName() const = 0;

    // 返回此组件期望达到的状态名
    virtual FName GetDesiredState() const = 0;

    // 返回此组件依赖的"某 Feature 的某状态"
    // 例如：依赖 "PawnFeature" 的 "DataAvailable" 状态
    virtual FName GetRequiredState(const FName& FeatureName) const = 0;

    // 返回此组件达到哪个状态后，依赖它的其他组件可以继续
    virtual FName GetPrerequisiteState(const FName& FeatureName) const = 0;

    // 状态变更通知
    virtual void OnStateChanged(FName OldState, FName NewState) = 0;

    // 组件初始化前调用
    virtual void OnActorPreInitialize() = 0;

    // 组件初始化后调用
    virtual void OnActorInitStateChanged(const FActorInitStateChangedParams& Params) = 0;
};
```

---

## 4 态链

```
Spawned（已生成）
    │  Pawn 被创建，组件已 Register，基本内存就绪
    ▼
DataAvailable（数据就绪）
    │  PawnExtensionComponent 就绪，其他组件可安全引用
    ▼
DataInitialized（数据初始化完成）
    │  HeroComponent 就绪，输入绑定完成，ASC 可开始授予能力
    ▼
GameplayReady（游戏玩法就绪）
    │  所有组件就绪，Camera、Movement 完全可用
```

---

## 关键参与者

| 组件 | 文件路径 | 注册状态 | 前置依赖 | 特征名 |
|------|---------|---------|---------|--------|
| ULyraPawnExtensionComponent | `Character/LyraPawnExtensionComponent.h` | DataAvailable | Spawned | "PawnExtension" |
| ULyraHeroComponent | `Character/LyraHeroComponent.h` | DataInitialized | DataAvailable | "Hero" |
| UAbilitySystemComponent | 内置 GAS | GameplayReady | DataInitialized | "AbilitySystem" |
| ULyraCameraComponent | `Camera/LyraCameraComponent.h` | GameplayReady | DataInitialized | "Camera" |
| ULyraInputComponent | `Input/` | DataInitialized | DataAvailable | "Input" |

---

## 注册与使用

### 组件注册 InitState

```cpp
// 在组件的 OnRegister() 中注册
void UMyPawnComponent::OnRegister()
{
    Super::OnRegister();

    // 注册到全局 InitState 管理器
    RegisterInitStateFeature();

    // 注册依赖关系：依赖 PawnExtension 的 DataAvailable
    BindOnActorInitStateChanged(
        FName("PawnExtension"),
        FGameplayTag::RequestGameplayTag("InitState.DataAvailable"),
        false,
        false
    );
}
```

### 状态推进

```cpp
// 当组件就绪时，推进状态
void UMyPawnComponent::OnActorInitStateChanged(
    const FActorInitStateChangedParams& Params)
{
    // 检查依赖是否满足
    if (Params.FeatureName == FName("PawnExtension") &&
        Params.FeatureState == FGameplayTag::RequestGameplayTag("InitState.DataAvailable"))
    {
        // 前置条件满足，初始化本组件
        InitializeMyComponent();

        // 推进到目标状态
        CheckDefaultInitializationForFeature();
    }
}

void UMyPawnComponent::CheckDefaultInitializationForFeature()
{
    // 调用框架方法，沿状态链推进
    ContinueInitStateChain();
}
```

---

## 状态机管理器

全局 InitState 管理器由引擎框架隐式提供，通过以下函数访问状态：

| 函数 | 功能 |
|------|------|
| `RegisterInitStateFeature()` | 注册组件到状态机 |
| `UnregisterInitStateFeature()` | 卸载组件 |
| `CheckDefaultInitializationForFeature()` | 尝试沿状态链推进 |
| `ContinueInitStateChain()` | 显式推进到下一状态 |
| `BindOnActorInitStateChanged()` | 监听其他组件的状态变化 |

---

## 典型流程

```
Pawn Spawned
    → PawnExtensionComponent::OnRegister()
        → RegisterInitStateFeature()
        → 状态推进：Spawned → DataAvailable

    → HeroComponent::OnRegister()
        → RegisterInitStateFeature()
        → BindOnActorInitStateChanged("PawnExtension", "DataAvailable")
        → 等待 PawnExtension 的 DataAvailable 通知

    → PawnExtensionComponent 达到 DataAvailable
        → 通知所有绑定的组件
        → HeroComponent::OnActorInitStateChanged 被调用
        → 初始化 ASC
        → 状态推进：DataAvailable → DataInitialized

    → ASC 初始化完成
        → 通知绑定的相机和输入组件
        → 状态推进：DataInitialized → GameplayReady
```

---

## 自定义组件接入 InitState

```cpp
UCLASS()
class UMyCustomComponent : public UActorComponent,
    public IGameFrameworkInitStateInterface
{
    GENERATED_BODY()

public:
    virtual void OnRegister() override
    {
        Super::OnRegister();

        // 1. 注册特征
        RegisterInitStateFeature();

        // 2. 声明依赖 PawnExtension 的 DataAvailable
        BindOnActorInitStateChanged(
            FName("PawnExtension"),
            FGameplayTag::RequestGameplayTag("InitState.DataAvailable"),
            false
        );
    }

    virtual FName GetFeatureName() const override
    {
        return FName("MyCustom");
    }

    virtual FName GetDesiredState() const override
    {
        return FName("GameplayReady");
    }

    // 达到依赖条件后，推进自己的状态
    virtual void OnActorInitStateChanged(
        const FActorInitStateChangedParams& Params) override
    {
        if (Params.FeatureName == FName("PawnExtension") &&
            Params.FeatureState == FGameplayTag::RequestGameplayTag("InitState.DataAvailable"))
        {
            // 初始化逻辑
            // ...

            ContinueInitStateChain();
        }
    }
};
```

---

## 关键设计要点

1. **依赖声明** — 每个组件显式声明自己依赖哪个 Feature 的哪个状态，不依赖隐式顺序
2. **异步推进** — 状态推进通过回调通知，不依赖 Tick，支持网络同步场景
3. **可扩展** — 新增组件只需实现接口并注册，不影响已有组件
4. **状态回退** — 当 Pawn 被销毁或复用（如 Dormancy）时，状态自动回退到起点
