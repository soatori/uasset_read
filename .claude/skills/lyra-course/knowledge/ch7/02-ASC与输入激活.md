# ASC 与输入激活

> 对应讲义：[081_ASC与GA](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/docs/UE5_Lyra学习指南_081_ASC与GA.md)
> 核心代码：[LyraAbilitySystemComponent](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/LyraAbilitySystemComponent.h)

## ULyraAbilitySystemComponent

ULyraAbilitySystemComponent 是 UAbilitySystemComponent 的扩展，管理 Lyra 特有的能力激活管线。

## 能力授予流程

```
PawnData
  └── AbilitySets[] (TArray<TObjectPtr<ULyraAbilitySet>>)
        └── ALyraPlayerState::SetPawnData()
              └── 遍历 AbilitySets，调用 GiveToAbilitySystem()
                    └── 注册 Abilities / Effects / AttributeSets
                          └── 发送 NAME_LyraAbilityReady 帧事件
```

## 输入激活管线

```
Enhanced Input Action
  └── ULyraHeroComponent::Input_AbilityInputTagPressed(InputTag)
        └── ULyraAbilitySystemComponent::AbilityInputTagPressed(InputTag)
              ├── 遍历 ActivatableAbilities，匹配 InputTag
              ├── 按 ActivationPolicy 分桶：
              │     ├── OnInputTriggered → InputPressedSpecHandles
              │     └── WhileInputActive → InputHeldSpecHandles
              │
              └── ALyraPlayerController::PostProcessInput(DeltaTime)
                    └── ULyraAbilitySystemComponent::ProcessAbilityInput(DeltaTime, bGamePaused)
                          ├── 阶段 1：处理按住输入（WhileInputActive）
                          │     └── 尝试激活 InputHeldSpecHandles 中仍在 Pressed 列表的能力
                          │
                          ├── 阶段 2：处理按下触发（OnInputTriggered）
                          │     └── 尝试激活 InputPressedSpecHandles 中的能力
                          │
                          └── 阶段 3：清空
                                └── ClearAbilityInput() → 重置 InputPressedSpecHandles & InputReleasedSpecHandles
```

**输入阻塞机制：** 当 Actor 拥有 `TAG_Gameplay_AbilityInputBlocked` 标签时，`ProcessAbilityInput()` 跳过所有处理。

### AbilitySpecInputPressed/Released

Lyra 不直接使用 `UGameplayAbility::bReplicateInputDirectly`，而是通过 ASC 的 `InvokeReplicatedEvent()` 触发 `WaitInputPress` / `WaitInputRelease` AbilityTask 的复制事件。这在 [03-GA_Jump与GA_Dash.md]() 中有详细说明。

## ActorInfo 初始化位置

| 方案 | Owner | Avatar | 适用场景 |
|------|-------|--------|----------|
| PlayerState | PlayerState | Pawn | 标准玩家（防止 Pawn 重生时丢失） |
| GameState | GameState | GameState | GameMode 级全局能力 |
| PawnExtensionComponent | InOwnerActor | Pawn | 通过 GameFeature 动态设置 |
| LyraCharacterWithAbilities | Self | Self | 简单非玩家角色 |

`InitAbilityActorInfo()` 中还包含以下操作：
- `TryActivateAbilitiesOnSpawn()` —— 尝试激活 OnSpawn 策略的能力
- `ULyraGlobalAbilitySystem::RegisterASC(this)` —— 注册到全局系统（详见 [01-GAS架构概述.md]()）

## TryActivateAbilitiesOnSpawn

在 `InitAbilityActorInfo()` 中被调用，遍历 `ActivatableAbilities`，检查 `ULyraGameplayAbility` CDO 的 `TryActivateAbilityOnSpawn()` 返回值，若为 true 则尝试激活。

另外在 `OnGiveAbility()` 中也会调用 `TryActivateAbilitiesOnSpawn()`，确保动态注册的能力也能在生成时激活。

## 激活组管理

`ELyraAbilityActivationGroup` 枚举：

| 枚举值 | 行为 |
|--------|------|
| `Independent` | 互不影响 |
| `Exclusive_Replaceable` | 此组激活时被其他 Exclusive 能力替换 |
| `Exclusive_Blocking` | 此组激活时阻塞其他 Exclusive 能力 |

通过 `ActivationGroupCounts[]` 数组维护各组当前计数：

- `IsActivationGroupBlocked(Group)` —— 根据计数判断是否被阻塞
- `AddAbilityToActivationGroup(Group, Handle)` —— 递增计数，若 Handle 有对应则调用 `ChangeActivationGroup` 切换
- `RemoveAbilityFromActivationGroup(Group, Handle)` —— 递减计数
- `CancelActivationGroupAbilities(Group, ...)` —— 取消指定组中的能力（通过 `CancelAbilitiesByFunc`）

### 能力组切换流程

```
ULyraGameplayAbility::CanChangeActivationGroup(NewGroup)
  └── ASC::IsActivationGroupBlocked(NewGroup)
        └── 若被阻塞，则拒绝切换

ULyraGameplayAbility::ChangeActivationGroup(NewGroup)
  ├── CanChangeActivationGroup(NewGroup) → 检查
  ├── RemoveAbilityFromActivationGroup(OldGroup)
  ├── 更新 ActivationGroup
  └── AddAbilityToActivationGroup(NewGroup)
        └── 若 NewGroup 是 Exclusive，则自动 Cancel 同组其他能力
```

```cpp
void ULyraAbilitySystemComponent::AddAbilityToActivationGroup(ELyraAbilityActivationGroup Group, FGameplayAbilitySpecHandle Handle)
{
    ++ActivationGroupCounts[Group];
    if (Handle.IsValid())
    {
        // 如果该能力未在激活组计数中，调用 ChangeActivationGroup 调整
    }
}
```

## 激活检查与标签关系

`DoesAbilitySatisfyTagRequirements()` 覆写了 UGameplayAbility 的版本：

```
进行标准 Tag 检查
  └── 通过 ASC::GetAdditionalActivationTagRequirements(Tag, OutRequired, OutBlocked)
        └── 委托给 ULyraAbilityTagRelationshipMapping::GetRequiredAndBlockedActivationTags()
              └── 查询 FLyraAbilityTagRelationship
                    ├── ActivationRequiredTags → 加入 AllRequiredTags
                    └── ActivationBlockedTags → 加入 AllBlockedTags

检查 AllRequiredTags 和 AllBlockedTags 是否满足
```

TagRelationshipMapping 通过 `SetTagRelationshipMapping()` 设置，通常在 PawnData 中配置。

## 能力失败通知

```
ASC::NotifyAbilityFailed(ActorInfo, Handle, FailureTag)
  └── ClientNotifyAbilityFailed (RPC 到客户端)
        └── ULyraAbilitySystemComponent::HandleAbilityFailed(...)
              └── ULyraGameplayAbility::OnAbilityFailedToActivate(FailureTagContainer)
                    └── NativeOnAbilityFailedToActivate(FailureTag)
                          └── 通过 UGameplayMessageSubsystem 广播
                                ├── FailureTagToUserFacingMessages → 显示用户消息
                                └── FailureTagToAnimMontage → 播放失败动画
```

## 动态标签 GE

```cpp
void ULyraAbilitySystemComponent::AddDynamicTagGameplayEffect(FGameplayTag Tag)
{
    // 从 ULyraGameData 获取 DynamicTagGameplayEffect
    // 创建 GE Spec，将 Tag 添加到 DynamicGrantedTags
    // 应用 GE
}

void ULyraAbilitySystemComponent::RemoveDynamicTagGameplayEffect(FGameplayTag Tag)
{
    // 使用 FGameplayEffectQuery::MakeQuery_MatchAnyOwningTags({Tag}) 查询并移除
}
```

## 能力相机模式

在 ULyraGameplayAbility 中通过 `SetCameraMode(TSubclassOf<ULyraCameraMode>)` 和 `ClearCameraMode()` 切换相机模式。

底层调用 `ULyraHeroComponent::SetCameraMode()` / `ClearCameraMode()`，通过 `ActiveCameraMode` 成员变量追踪当前激活的相机模式。在 `EndAbility` 中自动调用 `ClearCameraMode()`。

## 能力消耗

在 `ULyraGameplayAbility::CheckCost()` 和 `ApplyCost()` 中，先调用基类 `UGameplayAbility` 的版本进行标准 Tag/Mana 消耗检查，然后遍历 `AdditionalCosts` 数组进行额外消耗：

```cpp
bool ULyraGameplayAbility::CheckCost(...)
{
    if (!Super::CheckCost(...)) return false;
    for (ULyraAbilityCost* Cost : AdditionalCosts)
    {
        if (!Cost->CheckCost(this, ...)) return false;
    }
    return true;
}

void ULyraGameplayAbility::ApplyCost(...)
{
    Super::ApplyCost(...);
    for (ULyraAbilityCost* Cost : AdditionalCosts)
    {
        // bOnlyApplyCostOnHit 逻辑：检查是否命中
        if (Cost->ShouldOnlyApplyCostOnHit())
        {
            // 检查能力是否有命中目标
            if (!HasHitTarget()) continue;
        }
        Cost->ApplyCost(this, ...);
    }
}
```
