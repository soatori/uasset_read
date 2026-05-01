# 第七章 GAS 能力系统

> 对应讲义：080~090 | AbilitySystem/、Interaction/、Inventory/ 源码目录

## 知识地图

| 知识文件 | 对应讲义 | 说明 |
|---------|---------|------|
| [ch7/01-GAS架构概述](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/01-GAS架构概述.md) | 080 | AbilitySet、AbilitySystemGlobals、EffectContext、GlobalAbilitySystem、AbilityTagRelationshipMapping、AbilityCost 等全貌 |
| [ch7/02-ASC与输入激活](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/02-ASC与输入激活.md) | 081 | ASC 输入管线、ProcessAbilityInput、激活组、标签关系、能力失败、动态 GE、相机模式 |
| [ch7/03-GA_Jump与GA_Dash](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/03-GA_Jump与GA_Dash.md) | 082, 083 | 跳越能力（CharacterMovement 驱动）、冲刺能力（RootMotion 驱动）、AbilityTask 详解 |
| [ch7/04-GA_Melee](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/04-GA_Melee.md) | 084 | 近战能力：Capsule Trace、友军检查、伤害 GEEC、Lunge |
| [ch7/05-属性集与HealthSet](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/05-属性集与HealthSet.md) | 085 | 属性集层级、HealthSet、元属性机制、ClampAttribute、ATTRIBUTE_ACCESSORS |
| [ch7/06-GEEC伤害计算](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/06-GEEC伤害计算.md) | 086 | DamageExecution、HealExecution、捕获/衰减/队伍伤害、伤害公式 |
| [ch7/07-生命值组件](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/07-生命值组件.md) | 087 | HealthComponent、死亡状态机、属性事件桥接、网络同步 |
| [ch7/08-库存系统](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/08-库存系统.md) | 088 | InventoryManager、ItemDefinition/Fragment/Instance、FFastArraySerializer、IPickupable |
| [ch7/09-交互系统](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/knowledge/ch7/09-交互系统.md) | 089, 090 | IInteractableTarget、FInteractionOption、ALyraWorldCollectable、拾取流程 |

## 核心架构图

```
Input Tag
  │
  v
ULyraHeroComponent ──> ULyraAbilitySystemComponent ──> ProcessAbilityInput()
  │                             │
  │                    TagRelationshipMapping
  │                    ActivationGroup
  │                    GlobalAbilitySystem
  │
  v
ULyraGameplayAbility
  ├── GA_Jump (CharacterMovement)
  ├── GA_Dash (RootMotion)
  ├── GA_Melee (Capsule Trace)
  └── GA_Interact (交互)
        │
        v
  ULyraAbilitySet (PawnData → PlayerState → GiveToAbilitySystem)
        │
  UL yraDamageExecution / ULyraHealExecution (GEEC)
        │
  FLyraGameplayEffectContext (DamageAttenuation)
        │
  ULyraHealthSet ──> ULyraHealthComponent ──> DeathState
        │
  ULyraInventoryManagerComponent
        ├── FLyraInventoryList (FFastArraySerializer)
        ├── ULyraInventoryItemDefinition (Fragments)
        └── ULyraInventoryItemInstance (StatTags)
        │
  ALyraWorldCollectable (IInteractableTarget + IPickupable)
```

## 关键机制一览

| 机制 | 说明 | 关键文件 |
|------|------|---------|
| 输入激活 | EnhancedInput → HeroComponent → ASC::AbilityInputTagPressed → ProcessAbilityInput | [02](ch7/02-ASC与输入激活.md) |
| 激活组 | Independent / Exclusive_Replaceable / Exclusive_Blocking | [02](ch7/02-ASC与输入激活.md) |
| 标签关系 | AbilityTag → Block/Cancel/Required/Blocked Tags | [01](ch7/01-GAS架构概述.md) |
| 能力授予 | PawnData → AbilitySet → PlayerState::SetPawnData | [01](ch7/01-GAS架构概述.md) |
| 属性集 | HealthSet 元属性模式（Damage→-Health, Healing→+Health） | [05](ch7/05-属性集与HealthSet.md) |
| 伤害计算 | GEEC：BaseDamage × DistanceAtten × PhysMatAtten × TeamMultiplier | [06](ch7/06-GEEC伤害计算.md) |
| 死亡流 | NotDead → DeathStarted → DeathFinished | [07](ch7/07-生命值组件.md) |
| 物品系统 | Definition/Fragment (设计时) → Instance (运行时) → List (复制) | [08](ch7/08-库存系统.md) |
| 交互拾取 | IInteractableTarget::GatherInteractionOptions → IPickupable::GetPickupInventory | [09](ch7/09-交互系统.md) |
