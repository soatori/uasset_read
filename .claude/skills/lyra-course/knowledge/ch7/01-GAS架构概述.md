# GAS 架构概述

> 对应讲义：[080_GAS的架构](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/docs/UE5_Lyra学习指南_080_GAS的架构.md)

## ULyraAbilitySet

[ULyraAbilitySet](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/LyraAbilitySet.h) 是继承 `UPrimaryDataAsset` 的数据资产，用于将一组 GAS 资源打包授予 ASC。

**核心数据结构：**

| 结构体 | 用途 | 字段 |
|--------|------|------|
| `FLyraAbilitySet_GameplayAbility` | 要授予的 GameplayAbility | `Ability`（TSubclassOf\<ULyraGameplayAbility\>）、`AbilityLevel`（int32）、`InputTag`（FGameplayTag） |
| `FLyraAbilitySet_GameplayEffect` | 要授予的 GameplayEffect | `GameplayEffect`（TSubclassOf\<UGameplayEffect\>）、`EffectLevel`（float） |
| `FLyraAbilitySet_AttributeSet` | 要授予的 AttributeSet | `AttributeSet`（TSubclassOf\<UAttributeSet\>） |
| `FLyraAbilitySet_GrantedHandles` | 已授予内容的句柄集合 | `AbilitySpecHandles`、`GameplayEffectHandles`、`GrantedAttributeSets` |

**核心方法：**
- `GiveToAbilitySystem(ULyraAbilitySystemComponent*, FLyraAbilitySet_GrantedHandles*, UObject* OverrideSourceObject = nullptr)` —— 将 AbilitySet 授予指定 ASC
- `TakeFromAbilitySystem(ULyraAbilitySystemComponent*)` —— 从 ASC 收回所有已授予内容

**成员变量：**
- `GrantedGameplayAbilities` —— 数组，定义要授予的 GA
- `GrantedGameplayEffects` —— 数组，定义要授予的 GE
- `GrantedAttributes` —— 数组，定义要授予的 AttributeSet

InputTag 存储在 `AbilitySpec.GetDynamicSpecSourceTags().AddTag(InputTag)` 中，后续输入系统通过该 Tag 查找对应 AbilitySpec。

## ILyraAbilitySourceInterface

能力来源接口，定义伤害衰减计算。由武器等对象实现。

**核心方法：**
- `GetDistanceAttenuation(float Distance, const FGameplayTagContainer* SourceTags, const FGameplayTagContainer* TargetTags) const` —— 距离衰减
- `GetPhysicalMaterialAttenuation(const UPhysicalMaterial* PhysicalMaterial, const FGameplayTagContainer* SourceTags, const FGameplayTagContainer* TargetTags) const` —— 物理材质衰减

在 GEEC 中通过 FLyraGameplayEffectContext 获取该接口来计算伤害衰减。

## ULyraAbilitySystemComponent

[ULyraAbilitySystemComponent](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/LyraAbilitySystemComponent.h) 是 Lyra 对 UAbilitySystemComponent 的核心扩展，负责输入路由、激活组管理、标签关系映射、动态标签 GE 等能力。详见 [02-ASC与输入激活.md]()。

**扩展关键功能：**
- 输入标签驱动的能力激活管道
- 激活组（Independent / Exclusive_Replaceable / Exclusive_Blocking）
- 标签关系映射（Block / Cancel / Required / Blocked Tags）
- 动态标签 GameplayEffect 管理
- 全局 AbilitySystem 注册

## ULyraGameplayAbility

[ULyraGameplayAbility](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.h) 是所有 Lyra GameplayAbility 的基类。

**核心扩展：**
- `ActivationPolicy` —— 激活策略：`OnInputTriggered`（按下触发）、`WhileInputActive`（按住持续）、`OnSpawn`（生成时激活）
- `ActivationGroup` —— 激活组：`Independent`（独立）、`Exclusive_Replaceable`（互斥可替换）、`Exclusive_Blocking`（互斥阻塞）
- `AdditionalCosts` —— 额外消耗（TagStack、InventoryItem 等）
- `ActiveCameraMode` —— 激活时切换相机模式
- `OnAbilityFailedToActivate(FGameplayTagContainer)` —— 激活失败回调，通过 UGameplayMessageSubsystem 广播

## ULyraAbilitySystemGlobals

[ULyraAbilitySystemGlobals](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/LyraAbilitySystemGlobals.h) 配置类，标记 `Config=Game`。

**覆写方法：**
- `AllocGameplayEffectContext()` —— 返回 `FLyraGameplayEffectContext` 实例，替代默认的 FGameplayEffectContext

在 `DefaultGame.ini` 中配置：

```ini
[/Script/GameplayAbilities.AbilitySystemGlobals]
GlobalGameplayCueManagerClass=/Script/LyraGame.LyraGameplayCueManager
+GameplayCueNotifyPaths=/Script/LyraGame
ReplicateActivationOwnedTags=True
MinimalReplicationTagCountISM=16
AbilitySystemInvalidationServerKey=1
AbilitySystemInvalidationClientKey=2
ActivateFailCooldownTag=/Script/LyraGame.Default.__GameplayAbilityActivateFailCooldown
ActivateFailCostTag=/Script/LyraGame.Default.__GameplayAbilityActivateFailCost
ActivateFailNetworkingTag=/Script/LyraGame.Default.__GameplayAbilityActivateFailNetworking
ActivateFailTagsBlockedTag=/Script/LyraGame.Default.__GameplayAbilityActivateFailTagsBlocked
ActivateFailTagsMissingTag=/Script/LyraGame.Default.__GameplayAbilityActivateFailTagsMissing
bUseDebugTargetFromHud=True
```

## ULyraAbilityTagRelationshipMapping

[ULyraAbilityTagRelationshipMapping](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/LyraAbilityTagRelationshipMapping.h) 是 DataAsset，定义 AbilityTag 之间的关系。

**FLyraAbilityTagRelationship 结构体：**
- `AbilityTag` —— 能力标签
- `AbilityTagsToBlock` —— 此能力激活时阻塞其他能力的标签
- `AbilityTagsToCancel` —— 此能力激活时取消其他能力的标签
- `ActivationRequiredTags` —— 额外需要的激活标签
- `ActivationBlockedTags` —— 额外阻塞的激活标签

**测试辅助方法：** `IsAbilityCancelledByTag()` —— 检查能力是否被指定动作标签取消。

## FLyraGameplayEffectContext

[FLyraGameplayEffectContext](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/LyraGameplayEffectContext.h) 扩展自 `FGameplayEffectContext`，支持网络序列化。

**扩展字段：**
- `CartridgeID`（int32）—— 子弹批次 ID
- `AbilitySourceObject`（TWeakObjectPtr\<const UObject\>）—— 能力来源对象（不网络同步）

**核心方法：**
- `ExtractEffectContext(FGameplayEffectContextHandle)` —— 静态方法，从 Handle 提取本类型上下文
- `SetAbilitySource(const ILyraAbilitySourceInterface*, float)` —— 设置来源和等级
- `GetAbilitySource()` —— 获取来源接口
- `Duplicate()` —— 深拷贝（含 HitResult）

## FLyraGameplayAbilityTargetData_SingleTargetHit

扩展自 `FGameplayAbilityTargetData_SingleTargetHit`，增加 `CartridgeID` 字段，网络序列化时一并同步。`AddTargetDataToContext()` 方法将 TargetData 中的 CartridgeID 传播到 EffectContext。

## ULyraGlobalAbilitySystem

[ULyraGlobalAbilitySystem](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/LyraGlobalAbilitySystem.h) 是 `UWorldSubsystem`，管理全局注册的 ASC，支持批量应用/移除能力和效果。

**辅助结构体：**
- `FGlobalAppliedAbilityList` —— `Handles`（Map\<ASC, SpecHandle\>），方法：`AddToASC`、`RemoveFromASC`、`RemoveFromAll`
- `FGlobalAppliedEffectList` —— 同上，但管理 EffectHandle

**核心方法：**
- `ApplyAbilityToAll(TSubclassOf\<UGameplayAbility\>)` —— 向所有已注册 ASC 应用能力
- `ApplyEffectToAll(TSubclassOf\<UGameplayEffect\>)` —— 向所有已注册 ASC 应用效果
- `RemoveAbilityFromAll` / `RemoveEffectFromAll`
- `RegisterASC(ULyraAbilitySystemComponent*)` —— 注册 ASC 并应用当前全局效果
- `UnregisterASC(ULyraAbilitySystemComponent*)` —— 反注册并移除全局效果

**注册时机：** `ULyraAbilitySystemComponent::InitAbilityActorInfo()` 中调用 `GlobalAbilitySystem->RegisterASC(this)`；`EndPlay()` 中调用 `UnregisterASC(this)`。

## ALyraTaggedActor

实现了 `IGameplayTagAssetInterface` 接口的 Actor，在编辑器模式下可配置 GameplayTag。用于化身系统中标记性别/体型等标签。

## 损伤/治疗计算

- **ULyraDamageExecution**（`UGameplayEffectExecutionCalculation`）—— 伤害执行计算，捕获 BaseDamage，结合衰减和队伍检测计算最终伤害
- **ULyraHealExecution** —— 治疗执行计算，捕获 BaseHeal，输出 Healing 属性

详见 [06-GEEC伤害计算.md]()。

## ULyraAbilityCost

[ULyraAbilityCost](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Abilities/LyraAbilityCost.h) 是对象基类（`EditInlineNew`），定义能力消耗接口。

**方法：**
- `CheckCost()` —— 检查能否支付消耗
- `ApplyCost()` —— 应用消耗
- `ShouldOnlyApplyCostOnHit()` —— 是否仅在命中时消耗

**派生类：**
- `LyraAbilityCost_PlayerTagStack` —— 消耗玩家 TagStack
- `LyraAbilityCost_ItemTagStack` —— 消耗物品 TagStack
- `LyraAbilityCost_InventoryItem` —— 消耗背包物品
