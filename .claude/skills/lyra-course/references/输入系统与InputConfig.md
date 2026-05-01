# 输入系统与 InputConfig

## 概述

Lyra 的输入系统基于 **Enhanced Input**，通过 **Tag 映射**将输入动作与 GameplayAbility 解耦。核心思路：输入产生 GameplayTag，Tag 驱动能力激活。

---

## InputConfig 数据结构

**文件**：`Source/LyraGame/Input/LyraInputConfig.h`

```cpp
USTRUCT(BlueprintType)
struct FLyraInputAction
{
    GENERATED_BODY()

    // 输入对应的 GameplayTag，如 InputTag.Move、InputTag.Jump
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    FGameplayTag InputTag;

    // 对应的 Enhanced Input Action 资源
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TObjectPtr<UInputAction> InputAction = nullptr;
};

UCLASS(BlueprintType)
class ULyraInputConfig : public UDataAsset
{
    GENERATED_BODY()

public:
    // 所有 Tag→InputAction 映射
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly)
    TArray<FLyraInputAction> InputActions;

    // 根据 Tag 查找对应的 InputAction
    UFUNCTION(BlueprintCallable)
    const UInputAction* FindInputActionForTag(const FGameplayTag& Tag) const
    {
        for (const FLyraInputAction& Action : InputActions)
        {
            if (Action.InputTag == Tag)
            {
                return Action.InputAction;
            }
        }
        return nullptr;
    }
};
```

---

## 绑定流程

### 第一步：设置输入映射上下文

**文件**：`Source/LyraGame/Character/LyraHeroComponent.h`

```cpp
void ULyraHeroComponent::InitializePlayerInput(UInputComponent* PlayerInputComponent)
{
    APlayerController* PC = GetController<APlayerController>();
    ULocalPlayer* LP = Cast<ULocalPlayer>(PC->GetLocalPlayer());
    UEnhancedInputLocalPlayerSubsystem* Subsystem = LP->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>();

    // 添加输入映射上下文
    // LyraInputMapping 是一个 UInputMappingContext，在 Content 中定义
    Subsystem->AddMappingContext(LyraInputMapping, Priority);

    // 绑定能力激活
    ULyraInputComponent* LyraInputComp = ...;
    LyraInputComp->BindAbilityActions(InputConfig, InputHandles,
        this, &ThisClass::OnInputStarted, &ThisClass::OnInputTriggered, &ThisClass::OnInputCompleted);
}
```

### 第二步：Tag 绑定到 GA

**文件**：`Source/LyraGame/Input/LyraInputComponent.h`

```cpp
void ULyraInputComponent::BindAbilityActions(
    ULyraInputConfig* InputConfig,
    TArray<uint32>& BindHandles,
    UObject* Object,
    FInputActionHandler StartedHandler,
    FInputActionHandler TriggeredHandler,
    FInputActionHandler CompletedHandler)
{
    for (const FLyraInputAction& Action : InputConfig->InputActions)
    {
        if (Action.InputAction)
        {
            // 为每个 InputAction 绑定三个阶段的回调
            uint32 Handle = BindNativeAction(
                Action.InputAction,
                ETriggerEvent::Started,
                Object,
                StartedHandler,
                Action.InputTag
            );
            BindHandles.Add(Handle);

            Handle = BindNativeAction(
                Action.InputAction,
                ETriggerEvent::Triggered,
                Object,
                TriggeredHandler,
                Action.InputTag
            );
            BindHandles.Add(Handle);

            Handle = BindNativeAction(
                Action.InputAction,
                ETriggerEvent::Completed,
                Object,
                CompletedHandler,
                Action.InputTag
            );
            BindHandles.Add(Handle);
        }
    }
}
```

### 第三步：HeroComponent 处理输入事件

```cpp
void ULyraHeroComponent::OnInputStarted(const FInputActionInstance& InputAction)
{
    // 获取绑定的 Tag
    FGameplayTag InputTag = InputAction.GetSourceObject()->GetGameplayTag();

    // 通过 AbilitySystemComponent 激活对应的 GA
    if (ASC && ASC->IsOwnerActorAuthoritative())
    {
        // 直接输入激活
        ASC->AbilityLocalInputPressed(InputTag);
    }
}
```

---

## 输入修饰器（Input Modifiers）

Lyra 使用 Enhanced Input 的 Modifier 机制处理输入预处理：

| 修饰器 | 功能 |
|--------|------|
| `UInputModifierDeadZone` | 摇杆死区处理 |
| `UInputModifierNegate` | 输入值取反 |
| `UInputModifierScalar` | 输入值缩放 |
| `UInputModifierFOVScaling` | 根据 FOV 缩放鼠标灵敏度 |

鼠标灵敏度缩放是 Lyra 特有的做法：
```
MouseSensitivity = BaseSensitivity * FOVScalingFactor
```
其中 `FOVScalingFactor` 由 `UInputModifierFOVScaling` 根据当前 CameraMode 的 FOV 计算。

---

## 完整链路

```
玩家按键/摇杆
    → EnhancedInput 触发 UInputAction
    → Input Modifier 处理（死区/缩放/FOV）
    → ULyraInputComponent 的绑定回调
    → HeroComponent::OnInputStarted/OnInputTriggered/OnInputCompleted
    → Tag 匹配（InputTag.Move → ASC 激活 GA）
    → 对应 GameplayAbility 执行
```

---

## 添加新的输入绑定

```cpp
// 1. 在 Content 中创建 UInputAction 和 UInputMappingContext
// 2. 在 InputConfig 数据资产中添加 Tag→InputAction 映射

// 3. 在 GA 中设置 InputTag
UCLASS()
class UMyShootAbility : public ULyraGameplayAbility
{
    GENERATED_BODY()

public:
    UMyShootAbility()
    {
        // 与 InputConfig 中配置的 Tag 一致
        AbilityTags.AddTag(FGameplayTag::RequestGameplayTag("InputTag.Shoot"));
    }
};
```

---

## 关键设计要点

1. **Tag 驱动** — 输入和 GA 之间通过 FGameplayTag 连接，双方不需要互相引用
2. **三阶段回调** — Started/Triggered/Completed 分别对应按下、持续、释放
3. **映射上下文优先级** — 多个输入上下文通过优先级控制覆盖关系（如：UI 打开时游戏输入被阻挡）
4. **本地玩家子系统** — EnhancedInputLocalPlayerSubsystem 管理每个玩家的输入映射上下文
