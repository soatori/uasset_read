# 属性集与 HealthSet

> 对应讲义：[085_讲解属性集](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/docs/UE5_Lyra学习指南_085_讲解属性集.md)
> 核心代码：[LyraAttributeSet](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Attributes/)、[LyraHealthSet](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Attributes/LyraHealthSet.h)

## 属性集层级

```
UAttributeSet（引擎基类）
  └── ULyraAttributeSet（Lyra 基类，增加初始化检查）
        ├── ULyraCombatSet（战斗属性：BaseDamage, BaseHeal）
        └── ULyraHealthSet（生命属性：Health, MaxHealth, Healing, Damage）
```

## ULyraCombatSet

[ULyraCombatSet](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Attributes/LyraCombatSet.h) 定义战斗相关的基础属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `BaseDamage` | FGameplayAttributeData | 基础伤害值 |
| `BaseHeal` | FGameplayAttributeData | 基础治疗值 |

通过 `ATTRIBUTE_ACCESSORS(ULyraCombatSet, BaseDamage)` 宏生成 `GetBaseDamage()`、`SetBaseDamage()`、`InitBaseDamage()` 等方法。

## ULyraHealthSet

[ULyraHealthSet](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Attributes/LyraHealthSet.h) 是生命值系统的核心属性集。

### 属性定义

| 属性 | Replicated | 说明 |
|------|-----------|------|
| `Health` | 是 | 当前生命值 |
| `MaxHealth` | 是 | 最大生命值 |
| `Healing` | 否 | 元属性：传入的治疗量 |
| `Damage` | 否 | 元属性：传入的伤害量 |

**元属性机制：** Damage 和 Healing 是元属性，它们不会被持久化存储，而是在 `PostGameplayEffectExecute` 中被转换为 Health 的变化。Damage 映射为 -Health，Healing 映射为 +Health。

### Tag 定义

| Tag | 用途 |
|------|------|
| `TAG_Gameplay_Damage` | 通用伤害标签 |
| `TAG_Gameplay_DamageImmunity` | 伤害免疫标签 |
| `TAG_Gameplay_DamageSelfDestruct` | 自毁伤害标签 |
| `TAG_Gameplay_FellOutOfWorld` | 掉落伤害标签 |
| `TAG_Lyra_Damage_Message` | 伤害消息标签 |

### PreGameplayEffectExecute

在 GE 执行前保存旧值，检查伤害免疫和特殊伤害类型：

```cpp
void ULyraHealthSet::PreGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
    // 保存变更前的 Health 和 MaxHealth
    HealthBeforeAttributeChange = Health.GetCurrentValue();
    MaxHealthBeforeAttributeChange = MaxHealth.GetCurrentValue();

    // 检查 Damage 源
    if (Data.EvaluatedData.Attribute == GetDamageAttribute())
    {
        // 检查伤害免疫 tag
        if (Data.Target.HasTag(TAG_Gameplay_DamageImmunity))
        {
            // 跳过非自毁/非掉落类型的伤害
        }
    }
}
```

### PostGameplayEffectExecute

将元属性转换为实际的 Health 变化，广播变化事件：

```cpp
void ULyraHealthSet::PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
    if (Data.EvaluatedData.Attribute == GetDamageAttribute())
    {
        // Damage → -Health
        SetHealth(FMath::Clamp(GetHealth() - GetDamage(), 0.0f, GetMaxHealth()));
        SetDamage(0.0f);  // 清零元属性
    }
    else if (Data.EvaluatedData.Attribute == GetHealingAttribute())
    {
        // Healing → +Health
        SetHealth(FMath::Clamp(GetHealth() + GetHealing(), 0.0f, GetMaxHealth()));
        SetHealing(0.0f);  // 清零元属性
    }

    // 广播变化事件
    if (Data.EvaluatedData.Attribute == GetHealthAttribute())
    {
        OnHealthChanged.Broadcast(this, HealthBeforeAttributeChange, GetHealth(), ...);
    }

    // 检测是否死亡
    if (GetHealth() <= 0.0f && !bOutOfHealth)
    {
        bOutOfHealth = true;
        OnOutOfHealth.Broadcast(this);
    }
}
```

### ClampAttribute 钳制逻辑

```cpp
void ULyraHealthSet::ClampAttribute(const FGameplayAttribute& Attribute, float& NewValue) const
{
    if (Attribute == GetHealthAttribute())
    {
        NewValue = FMath::Clamp(NewValue, 0.0f, GetMaxHealth());
    }
    else if (Attribute == GetMaxHealthAttribute())
    {
        NewValue = FMath::Max(NewValue, 1.0f);
    }
}
```

在以下时机调用 `ClampAttribute`：
- `PreAttributeBaseChange()` —— 属性基值变更前
- `PreAttributeChange()` —— 属性当前值变更前
- `PostAttributeChange()` —— 属性变更后

### OnRep 网络同步

```cpp
void ULyraHealthSet::OnRep_Health(const FGameplayAttributeData& OldHealth)
{
    GAMEPLAYATTRIBUTE_REPNOTIFY(ULyraHealthSet, Health, OldHealth);
    // 在客户端触发 OnHealthChanged 事件
    OnHealthChanged.Broadcast(this, OldHealth, GetHealth(), ...);  // Instigator=nullptr
}

void ULyraHealthSet::OnRep_MaxHealth(const FGameplayAttributeData& OldMaxHealth)
{
    GAMEPLAYATTRIBUTE_REPNOTIFY(ULyraHealthSet, MaxHealth, OldMaxHealth);
    OnMaxHealthChanged.Broadcast(this, OldMaxHealth, GetMaxHealth(), ...);
}
```

## ATTRIBUTE_ACCESSORS 宏

```cpp
#define ATTRIBUTE_ACCESSORS(ClassName, PropertyName) \
    GAMEPLAYATTRIBUTE_PROPERTY_GETTER(ClassName, PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_GETTER(PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_SETTER(PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_INITTER(PropertyName)
```

该宏展开为：
- `GetXxx()` —— 获取属性值
- `SetXxx(float)` —— 设置属性值
- `InitXxx(float)` —— 初始化属性值
- `GetXxxAttribute()` —— 获取属性 FProperty 指针
