# AttributeSet 与属性系统

## 两层架构设计

项目采用 AttributeSet 两层继承结构：

```
UXGRPGAttributeSet（基类：基础设施）
    └── UXGRPGCharacterArrtibuteSet（子类：12 个具体属性 + 事件委托）
```

### 基类 UXGRPGAttributeSet

基类提供公共基础设施，不定义具体属性值，只包含辅助方法：

```cpp
UCLASS()
class XGRPG_API UXGRPGAttributeSet : public UAttributeSet
{
    UWorld* GetWorld() const override;
    UXGRPGAbilitySystemComponent* GetXGRPGAbilitySystemComponent() const;
};
```

- `GetWorld()`：从 Outer 对象获取 World 引用
- `GetXGRPGAbilitySystemComponent()`：获取项目自定义的 ASC 组件

### 子类 UXGRPGCharacterArrtibuteSet

子类定义了 12 个具名属性，全部标记为 `ReplicatedUsing`（网络复制，带 OnRep 通知），并定义了 5 个事件委托。

| 属性名 | 类型 | 默认值 | UI 显示 |
|--------|------|--------|---------|
| Health | float | 100.0 | 是 |
| MaxHealth | float | 100.0 | 否 |
| Mana | float | 80.0 | 是 |
| MaxMana | float | 80.0 | 否 |
| Stamina | float | 50.0 | 是 |
| MaxStamina | float | 50.0 | 否 |
| Attack | float | 10.0 | 是 |
| Defense | float | 2.0 | 是 |
| Exp | float | 0.0 | 是 |
| MaxExp | float | 120.0 | 否 |
| Damage | float | — | 否（瞬时伤害传递） |
| Level | float | — | 否 |

**属性初始化**：构造函数中设置默认值，`MaxExp` 跟随 `Exp` 一起复制。

### 属性注册

属性集通过 `GetLifetimeReplicatedProps` 注册网络复制，每个属性都使用 `COND_None`（始终复制）和 `REPNOTIFY_Always`（值不变时也通知）。

每个属性都有对应的 `OnRep_*` 方法，在网络值变更时触发 `GAMEPLAYATTRIBUTE_REPNOTIFY`，广播属性变更事件。

## 事件委托

定义在 `UXGRPGArrtibuteSet` 基类中的委托类型：

```cpp
DECLARE_MULTICAST_DELEGATE_SixParams(FXGRPGAttributeEvent,
    AActor* /*EffectInstigator*/,
    AActor* /*EffectCauser*/,
    const FGameplayEffectSpec* /*EffectSpec*/,
    float /*EffectMagnitude*/,
    float /*OldValue*/,
    float /*NewValue*/);
```

`UXGRPGCharacterArrtibuteSet` 中定义了 5 个事件委托实例：

| 委托 | 触发时机 |
|------|---------|
| `OnHealthChanged` | 生命值变化时 |
| `OnMaxHealthChanged` | 最大生命值变化时 |
| `OnOutOfHealth` | 生命值归零时 |
| `OnManaChanged` | 魔法值变化时 |
| `OnMaxManaChanged` | 最大魔法值变化时 |

## 属性修改与通知

### PreGameplayEffectExecute

GE 执行前调用，保存当前属性值用于后续比较：

```cpp
bool UXGRPGCharacterArrtibuteSet::PreGameplayEffectExecute(
    FGameplayEffectModCallbackData& Data)
{
    HealthBeforeAttributeChange = GetHealth();
    MaxHealthBeforeAttributeChange = GetMaxHealth();
    return true;
}
```

### PostGameplayEffectExecute

当 GameplayEffect 修改属性值后，`PostGameplayEffectExecute` 被调用。这是关键的属性校验和事件分发点：

```cpp
void UXGRPGCharacterArrtibuteSet::PostGameplayEffectExecute(
    const FGameplayEffectModCallbackData& Data)
{
    if (Data.EvaluatedData.Attribute == GetDamageAttribute())
    {
        // Damage 是瞬时属性：转换为生命值减少，然后清零
        SetHealth(FMath::Clamp(GetHealth() - GetDamage(), 0.0f, GetMaxHealth()));
        SetDamage(0.0f);
    }
    else if (Data.EvaluatedData.Attribute == GetHealthAttribute())
    {
        SetHealth(FMath::Clamp(GetHealth(), 0.0f, GetMaxHealth()));
    }
    else if (Data.EvaluatedData.Attribute == GetManaAttribute())
    {
        SetMana(FMath::Clamp(GetMana(), 0, GetMaxMana()));
    }

    // 生命值变化时广播
    if (GetHealth() != HealthBeforeAttributeChange)
    {
        OnHealthChanged.Broadcast(Instigator, Causer, &Data.EffectSpec,
            Data.EvaluatedData.Magnitude, HealthBeforeAttributeChange, GetHealth());
    }

    // 生命值归零时广播
    if ((GetHealth() <= 0.0f) && !bOutOfHealth)
    {
        OnOutOfHealth.Broadcast(Instigator, Causer, &Data.EffectSpec,
            Data.EvaluatedData.Magnitude, HealthBeforeAttributeChange, GetHealth());
    }

    bOutOfHealth = (GetHealth() <= 0.0f);
}
```

**Damage 属性的特殊处理**：Damage 是一个瞬时传递属性，GEEC 计算出的伤害值先写入 Damage，然后在 PostGameplayEffectExecute 中转换为生命值减少，最后将 Damage 归零，这样不会累积伤害值。

### PostAttributeChange

属性基础值变化后的回调，用于保证生命值不超过最大生命值：

```cpp
void UXGRPGCharacterArrtibuteSet::PostAttributeChange(
    const FGameplayAttribute& Attribute, float OldValue, float NewValue)
{
    if (Attribute == GetMaxHealthAttribute() && GetHealth() > NewValue)
    {
        GetXGRPGAbilitySystemComponent()
            ->ApplyModToAttribute(GetHealthAttribute(),
                EGameplayModOp::Override, NewValue);
    }

    if (bOutOfHealth && GetHealth() > 0.0f)
        bOutOfHealth = false;
}
```

### ClampAttribute

辅助方法，用于在 PreAttributeChange 中裁剪属性值到合法范围：

```cpp
void UXGRPGCharacterArrtibuteSet::ClampAttribute(
    const FGameplayAttribute& Attribute, float& NewValue) const
{
    if (Attribute == GetHealthAttribute())
        NewValue = FMath::Clamp(NewValue, 0.0f, GetMaxHealth());
    else if (Attribute == GetMaxHealthAttribute())
        NewValue = FMath::Max(NewValue, 1.0f);
}
```

## 网络同步机制

### OnRep_* 属性复制回调

所有属性都有 `OnRep_*` 方法，客户端收到属性更新后调用。Health 和 Mana 的 OnRep 会触发无源广播（Instigator/Causer/Spec 均为 nullptr），用于更新 UI：

```cpp
void UXGRPGCharacterArrtibuteSet::OnRep_Health(const FGameplayAttributeData& OldValue)
{
    GAMEPLAYATTRIBUTE_REPNOTIFY(UXGRPGCharacterArrtibuteSet, Health, OldValue);

    OnHealthChanged.Broadcast(nullptr, nullptr, nullptr,
        EstimatedMagnitude, OldValue.GetCurrentValue(), CurrentHealth);

    if (!bOutOfHealth && CurrentHealth <= 0.0f)
        OnOutOfHealth.Broadcast(nullptr, nullptr, nullptr,
            EstimatedMagnitude, OldValue.GetCurrentValue(), CurrentHealth);

    bOutOfHealth = (CurrentHealth <= 0.0f);
}
```

### 属性数据的网络流向

```
服务端（权威）
  │ 属性通过 GE 或直接修改
  │
  ├──→ PostGameplayEffectExecute（服务端触发事件 + 广播）
  │
  └──→ 属性复制到客户端（DOREPLIFETIME）
        │
        ├──→ OnRep_Health/OnRep_Mana（客户端触发广播）
        │
        └──→ UI 绑定的委托收到通知 → 更新显示
```

## 属性的五个重写方法

`UXGRPGCharacterArrtibuteSet` 重写以下方法：

| 方法 | 触发时机 | 用途 |
|------|---------|------|
| `PreGameplayEffectExecute` | GE 执行前 | 保存修改前的属性快照 |
| `PostGameplayEffectExecute` | GE 执行后 | 属性裁剪、事件分发 |
| `PreAttributeBaseChange` | 基础值即将改变 | 预留预处理 |
| `PreAttributeChange` | 属性值即将改变 | 预留预处理 |
| `PostAttributeChange` | 属性值改变后 | 健康检查（如 Health <= MaxHealth） |
| `GetLifetimeReplicatedProps` | 网络初始化 | 注册所有属性的网络复制 |
| `ClampAttribute` | 值裁剪 | 辅助方法，确保属性值合法 |

## ATTRIBUTE_ACCESSORS 宏

`ATTRIBUTE_ACCESSORS(ClassName, PropertyName)` 展开为四个函数声明，使属性可以在 GE 中被引用，方便在蓝图中配置 Magnitude 等参数。

该宏定义在 `XGRPGArrtibuteSet.h` 中，项目参考了 Lyra 的 ULyraHealthSet 中的用法：

```cpp
#define ATTRIBUTE_ACCESSORS(ClassName, PropertyName) \
    GAMEPLAYATTRIBUTE_PROPERTY_GETTER(ClassName, PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_GETTER(PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_SETTER(PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_INITTER(PropertyName)
```