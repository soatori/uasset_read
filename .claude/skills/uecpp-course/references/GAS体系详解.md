# GAS 体系详解

## 概述

基于 GameplayAbilitySystem 插件的多人网络 RPG 战斗系统（017_XGRPG 项目，约 7600 行 C++）。架构参考 Lyra 项目、MMORPG 教程和 Action RPG 示例，覆盖 ASC 注册、GameplayTag 体系、AttributeSet 属性系统、GEEC 伤害计算、连击/技能/弹道系统、UI 绑定和网络同步。

## 依赖配置

```csharp
PublicDependencyModuleNames.AddRange(
    new string[] {
        "Core", "CoreUObject", "Engine",
        "GameplayAbilities", "GameplayTags", "GameplayTasks"
    });
```

## 核心框架

### ASC 实现

```cpp
UCLASS()
class UXGRPGAbilitySystemComponent : public UAbilitySystemComponent
{
    GENERATED_BODY()

    // 输入处理
    void ProcessPlayerInput();

    // 能力注册
    void GiveCharacterAbilities();
};
```

### 角色基类

```cpp
UCLASS()
class AXGRPGCharacterBase : public ACharacter, public IAbilitySystemInterface
{
    GENERATED_BODY()

    virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override
    {
        return AbilitySystemComponent;
    }

    UPROPERTY()
    UXGRPGAbilitySystemComponent* AbilitySystemComponent;

    UPROPERTY()
    UXGRPGCharacterArrtibuteSet* AttributeSet;
};
```

### 能力注册与激活

```cpp
void UXGRPGAbilitySystemComponent::GiveCharacterAbilities()
{
    FGameplayAbilitySpec Spec(AbilityClass, 1, INDEX_NONE, this);
    Spec.DynamicAbilityTags.AddTag(InputTag);
    GiveAbility(Spec);
}

void UXGRPGAbilitySystemComponent::ProcessPlayerInput()
{
    // 遍历已注册能力的 Spec → 匹配 InputTag → 激活
    for (auto& Spec : GetActivatableAbilities())
    {
        if (Spec.DynamicAbilityTags.HasTag(PressedInputTag))
        {
            TryActivateAbility(Spec.Handle);
        }
    }
}
```

## GameplayTag 体系

```cpp
// 声明
UE_DECLARE_GAMEPLAY_TAG_EXTERN(TagName);

// 定义
UE_DEFINE_GAMEPLAY_TAG_COMMENT(TagName, "描述");
```

| 标签前缀 | 用途 | 示例 |
|---------|------|------|
| `InputTag.` | 输入绑定 | `InputTag.Melee`、`InputTag.Key_1` |
| `GameplayEvent.` | 事件触发 | `GameplayEvent.Death` |
| `SetByCaller.` | 动态数值传递 | `SetByCaller.Damage` |
| `Status.` | 状态标记 | `Status.Death`、`Status.Crouching` |
| `Ability.Behavior.` | 能力行为标记 | `Ability.Behavior.SurvivesDeath` |

## AttributeSet 属性系统

### 两层继承结构

```
UXGRPGAttributeSet (基类，公共基础设施)
  └─ UXGRPGCharacterArrtibuteSet (12 个具体属性 + 5 个事件委托)
```

### 12 个属性

| 属性 | 默认值 | UI | 说明 |
|------|--------|----|------|
| Health | 100.0 | 是 | 生命值 |
| MaxHealth | 100.0 | 否 | |
| Mana | 80.0 | 是 | 魔法值 |
| MaxMana | 80.0 | 否 | |
| Stamina | 50.0 | 是 | 耐力 |
| MaxStamina | 50.0 | 否 | |
| Attack | 10.0 | 是 | 攻击力 |
| Defense | 2.0 | 是 | 防御力 |
| Exp | 0.0 | 是 | 经验值 |
| MaxExp | 120.0 | 否 | |
| Damage | — | 否 | 瞬时伤害传递 |
| Level | — | 否 | |

### 属性访问宏

```cpp
ATTRIBUTE_ACCESSORS(UXGRPGCharacterArrtibuteSet, Health);
// 展开为四个函数：
// GET / SET / INIT / PROPERTY_GETTER
```

### Damage 瞬时传递模式

```cpp
void PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
    if (Data.EvaluatedData.Attribute == GetDamageAttribute())
    {
        float DamageDone = GetDamage();
        SetDamage(0.0f);

        float NewHealth = GetHealth() - DamageDone;
        SetHealth(FMath::Clamp(NewHealth, 0.0f, GetMaxHealth()));

        if (DamageDone > 0.0f)
            OnHealthChanged.Broadcast(this, GetHealth(), DamageDone);
    }
}
```

### Pre/Post 双钩子模式

```
GameplayEffect 执行
  → PreGameplayEffectExecute（存快照）
  → 属性值修改
  → PostGameplayEffectExecute（裁剪 + 事件广播）
    → Damage → Health 转换 → 清零 Damage
    → Health 裁剪 → 广播 OnHealthChanged / OnOutOfHealth
  → 服务端复制到客户端
    → OnRep_* 方法触发无源广播（UI 更新）
```

## 伤害计算（GEEC）

### 基础伤害 Execution

```cpp
UCLASS()
class UXGRPGDamageExecution : public UGameplayEffectExecutionCalculation
{
    virtual void Execute_Implementation(
        const FGameplayEffectCustomExecutionParameters& ExecutionParams,
        FGameplayEffectCustomExecutionOutput& OutExecutionOutput) const override
    {
        // 捕获 Source.Damage → 输出到 Target.Damage（透明传递）
    }
};
```

### 进阶伤害 Execution（空中版）

```cpp
// 线性攻防公式
float ActualDamage = FMath::Max(0.0f, BaseDamage + Attack - Defense + 5.0f);
// 直接读取 ASC 的 AttributeSet 获取 Attack/Defense
```

### GEEC 数据流

```
GameplayEffect（配置 Execution 类）
  → GEEC.Execute_Implementation（捕获/读取属性，计算伤害）
    → AddOutputModifier（输出到 Target.Damage）
      → AttributeSet.PostGameplayEffectExecute（裁剪 + 事件通知）
```

## 技能系统

### 技能列表

| 技能 | InputTag | 实现方式 |
|------|---------|---------|
| 轻攻击 | InputTag.LightAttack | 多段连击 + 蒙太奇 |
| 重攻击 | InputTag.HeavyAttack | 碰撞盒子伤害 |
| 远程魔法 | InputTag.Skill_1 / Skill_2 | 弹道投射 |
| 冲刺 | InputTag.Dash | AnimNotifyState 冲力 |
| 大招 | InputTag.Ultimate | 大范围 AOE |
| 生命恢复 | InputTag.Skill_3 | Duration+Period GE |
| 魔法恢复 | InputTag.Skill_4 | Duration+Period GE |

### Cost/Cooldown GE 模式

```cpp
// GA 蓝图配置
// Cost GameplayEffect → 资源消耗（Mana/Stamina）
// Cooldown GameplayEffect → 冷却（HasDuration = true）

// 系统自动调用
CheckCost() / ApplyCost()
```

### 冲刺流程

```
GA 激活 → PlayMontage
  → AnimNotifyState_AddForce（每帧施加冲力）
  → AnimNotifyState_StopSpeed（锁定速度）
  → AnimNotifyState_StopRotation（锁定朝向）
  → AnimNotifyState_IgnoreInput（忽略输入）
→ 蒙太奇结束 → EndAbility
```

## UI 系统

### HUD 蓝图绑定

```cpp
void AXGRPGHUD::BeginPlay()
{
    // 创建主 UI → 绑定 ASC 委托
    if (ASC)
    {
        ASC->GetGameplayAttributeValueChangeDelegate(HealthAttribute)
            .AddUObject(this, &AXGRPGHUD::OnHealthChanged);
    }
}
```

## 代码入口

| 文件 | 说明 |
|------|------|
| [XGRPGAbilitySystemComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/017_XGRPG/XGRPG/Source/XGRPG/AbilitySystem/XGRPGAbilitySystemComponent.h) | 自定义 ASC |
| [XGRPGCharacterArrtibuteSet.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/017_XGRPG/XGRPG/Source/XGRPG/AbilitySystem/Attributes/XGRPGCharacterArrtibuteSet.h) | 两层属性集 |
| [XGRPGDamageExecution.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/017_XGRPG/XGRPG/Source/XGRPG/AbilitySystem/Excutions/XGRPGDamageExecution.h) | 基础/进阶 GEEC |
| [XGRPGComboComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/017_XGRPG/XGRPG/Source/XGRPG/Component/XGRPGComboComponent.h) | 连击系统组件 |
| [XGRPGNumberPopComponent_UMG.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/017_XGRPG/XGRPG/Source/XGRPG/FeedBack/NumberPopComponent/XGRPGNumberPopComponent_UMG.h) | 伤害数字组件 |
| [XGRPGInventoryComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/017_XGRPG/XGRPG/Source/XGRPG/Component/XGRPGInventoryComponent.h) | 背包组件 |
| [XGRPGAssetManager.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/017_XGRPG/XGRPG/Source/XGRPG/System/XGRPGAssetManager.h) | AssetManager + GameData |
