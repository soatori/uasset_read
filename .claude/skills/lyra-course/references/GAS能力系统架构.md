# GAS 能力系统架构

## 概述

Lyra 对 UE GAS（GameplayAbilitySystem）进行了多层扩展，形成了一套完整的**能力授予→激活→执行→伤害计算**体系。

---

## AbilitySet：能力聚合体

**文件**：`Source/LyraGame/AbilitySystem/LyraAbilitySet.h`

AbilitySet 是一个数据资产，将 GA、GE、AttributeSet 聚合为一个可配置单元。

```cpp
UCLASS(BlueprintType)
class LYRAGAME_API ULyraAbilitySet : public UPrimaryDataAsset
{
    GENERATED_BODY()

public:
    // 要授予的 GameplayAbility
    UPROPERTY(EditDefaultsOnly, Category = "Gameplay Abilities")
    TArray<FLyraAbilitySet_GameplayAbility> GrantedGameplayAbilities;

    // 要应用的 GameplayEffect
    UPROPERTY(EditDefaultsOnly, Category = "Gameplay Effects")
    TArray<FLyraAbilitySet_GameplayEffect> GrantedGameplayEffects;

    // 要初始化的 AttributeSet
    UPROPERTY(EditDefaultsOnly, Category = "Attribute Sets")
    TArray<FLyraAbilitySet_AttributeSet> GrantedAttributes;
};

// 授予流程
void ULyraAbilitySet::GiveToAbilitySystem(
    ULyraAbilitySystemComponent* ASC,
    ULyraEquipmentInstance* SourceObject,
    TArray<FGameplayAbilitySpecHandle>& OutHandles) const
{
    // 1. 授予 GA
    for (const auto& Entry : GrantedGameplayAbilities)
    {
        FGameplayAbilitySpec Spec(Entry.Ability);
        Spec.SourceObject = SourceObject;
        OutHandles.Add(ASC->GiveAbility(Spec));
    }

    // 2. 应用 GE
    for (const auto& Entry : GrantedGameplayEffects)
    {
        FGameplayEffectContextHandle Context = ASC->MakeEffectContext();
        Context.AddSourceObject(SourceObject);
        ASC->BP_ApplyGameplayEffectSpecToSelf(Entry.Effect->MakeSpec());
    }

    // 3. 初始化属性集
    for (const auto& Entry : GrantedAttributes)
    {
        ASC->InitStats(Entry.AttributeSetType, nullptr);
    }
}
```

---

## ActivationGroup：激活组管理

**文件**：`Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility.h`

Lyra 在 `ULyraGameplayAbility` 中引入了 `ActivationGroup` 概念，控制多 GA 同时激活时的行为：

```cpp
UENUM(BlueprintType)
enum class ELyraAbilityActivationGroup : uint8
{
    // 独立激活，不与其他 GA 冲突
    Independent,

    // 独占替换：激活此 GA 时，替换同组中其他 Exclusive_Replaceable GA
    Exclusive_Replaceable,

    // 独占阻塞：激活此 GA 时，阻塞同组中其他 GA 的激活
    Exclusive_Blocking
};

UCLASS()
class LYRAGAME_API ULyraGameplayAbility : public UGameplayAbility
{
    GENERATED_BODY()

public:
    // 此 GA 的激活组
    UPROPERTY(EditDefaultsOnly, Category = "Lyra|Ability")
    ELyraAbilityActivationGroup ActivationGroup;
};
```

激活组规则：
- **Independent**：不与任何 GA 冲突，可同时激活（如移动、跳跃）
- **Exclusive_Replaceable**：被 Exclusive_Blocking 替换时取消；否则可同时存在
- **Exclusive_Blocking**：激活时取消同组所有 Replaceable GA

---

## TagRelationshipMapping：标签关系映射

**文件**：`Source/LyraGame/AbilitySystem/LyraAbilityTagRelationshipMapping.h`

通过数据资产配置 GA 之间的 Cancel/Block 关系：

```cpp
USTRUCT()
struct FLyraAbilityRelationshipMappingEntry
{
    FGameplayTagContainer AbilityTagsToMatch;
    FGameplayTagContainer CancelAbilitiesWithTag;
    FGameplayTagContainer BlockAbilitiesWithTag;
};

UCLASS()
class ULyraAbilityTagRelationshipMapping : public UDataAsset
{
    GENERATED_BODY()
    // 配置条目
    UPROPERTY(EditDefaultsOnly)
    TArray<FLyraAbilityRelationshipMappingEntry> AbilityRelationshipMappingEntries;
};
```

引擎框架在激活 GA 前自动检查 TagRelationshipMapping，决定是否取消或阻塞已有 GA。

---

## 属性集（AttributeSet）

Lyra 采用多层属性集设计：

| 属性集 | 文件路径 | 核心属性 |
|--------|---------|---------|
| ULyraHealthSet | `AbilitySystem/Attributes/LyraHealthSet.h` | Health、MaxHealth、DamageResistance |
| ULyraCombatSet | `AbilitySystem/Attributes/LyraCombatSet.h` | BaseDamage、MoveSpeed |

**ClampAttribute 机制**：HealthSet 使用 `FOnAttributeChangeRequest` 在属性变更前拦截，确保属性值不越界：

```
属性预变更事件
    → ClampAttribute（检测是否超出 [Min, Max]）
    → 超出时修正为边界值
    → 实际属性变更
```

---

## FLyraGameplayEffectContext

**文件**：`Source/LyraGame/AbilitySystem/LyraGameplayEffectContext.h`

扩展 GE Context 以携带额外伤害信息：

```cpp
USTRUCT()
struct FLyraGameplayEffectContext : public FGameplayEffectContext
{
    // 弹药 ID（用于区分同一武器不同子弹的伤害）
    int32 CartridgeID;
};
```

`CartridgeID` 用于伤害回溯——当伤害 Apply 后，可通过 CartridgeID 关联到特定的子弹或武器实例。

---

## 伤害计算（GEEC）

**文件**：`Source/LyraGame/AbilitySystem/Executions/LyraDamageExecution.h`

```cpp
UCLASS()
class ULyraDamageExecution : public UGameplayEffectExecutionCalculation
{
    GENERATED_BODY()

public:
    ULyraDamageExecution();

    virtual void Execute_Implementation(
        const FGameplayEffectCustomExecutionParameters& Params,
        FGameplayEffectCustomExecutionOutput& Output) const override;
};
```

伤害计算公式：
```
最终伤害 = BaseDamage × DistanceAttenuation × PhysicalMaterialAttenuation
           × DamageInteractionAllowedMultiplier
```

| 因子 | 来源 | 说明 |
|------|------|------|
| BaseDamage | ULyraCombatSet | 武器基础伤害 |
| DistanceAttenuation | 曲线表 | 距离衰减曲线 |
| PhysicalMaterialAttenuation | 物理材质表 | 不同材质减伤比 |
| DamageInteractionAllowedMultiplier | DamageInteractionAllowed 标签 | 是否允许友伤或对特定目标类型 |

---

## ASC 输入激活管线

**文件**：`Source/LyraGame/AbilitySystem/LyraAbilitySystemComponent.h`

Lyra 扩展了 ASC，实现了显式的**三阶段输入处理管线**，而非依赖默认的 `AbilityLocalInputPressed`：

```cpp
UCLASS()
class LYRAGAME_API ULyraAbilitySystemComponent : public UAbilitySystemComponent
{
    GENERATED_BODY()

public:
    // 输入按下：记录到 PressedSpecHandles
    void AbilityInputPressed(const FGameplayTag& InputTag);

    // 输入释放：从 Pressed 移到 Released
    void AbilityInputReleased(const FGameplayTag& InputTag);

    // 每帧执行：处理三阶段输入
    void ProcessAbilityInput(float DeltaTime, bool bGamePaused);

protected:
    // 当前帧按下的输入
    TArray<FGameplayTag> InputPressedSpecHandles;

    // 按住未释放的输入
    TArray<FGameplayTag> InputHeldSpecHandles;

    // 当前帧释放的输入
    TArray<FGameplayTag> InputReleasedSpecHandles;

    // 是否被阻塞（如 Modal UI 打开时）
    bool bBlockInput = false;
};
```

### ProcessAbilityInput 三阶段处理

```
ProcessAbilityInput 每帧执行
    │
    ├── 阶段一：处理 Pressed（新按下）
    │   → 遍历 InputPressedSpecHandles
    │   → 查找 Tag 匹配的 GA
    │   → 调用 TryActivateAbility（检查 InputBlocked Tag）
    │   → 若激活成功，将 Handle 加入 InputHeldSpecHandles
    │
    ├── 阶段二：处理 Held（按住持续）
    │   → 遍历 InputHeldSpecHandles
    │   → 对持续型 GA（如冲刺）检查是否需要更新
    │
    └── 阶段三：处理 Released（释放）
        → 遍历 InputReleasedSpecHandles
        → 通知对应 GA 输入已释放
        → 清理 InputHeldSpecHandles 中的条目
```

### 输入阻塞

当 `bBlockInput = true` 时（如 Modal UI 层激活），`ProcessAbilityInput` 跳过所有处理，但不清空队列。阻塞解除后输入继续正常处理。

---

## GA 实现模板：GA_Jump

以下是一个完整的 GA 实现模板（示意代码，非 Lyra 仓库中的实际文件），展示了 Lyra 中 GA 的标准结构：

```cpp
UCLASS()
class UGA_Jump : public ULyraGameplayAbility
{
    GENERATED_BODY()

public:
    UGA_Jump()
    {
        // 激活组设为 Independent，不与其他技能冲突
        ActivationGroup = ELyraAbilityActivationGroup::Independent;

        // 激活时拥有的标签
        ActivationOwnedTags.AddTag(TAG_Gameplay_Ability_Jump);
    }

    // 检查是否能激活：角色必须在地面上
    virtual bool CanActivateAbility(
        const FGameplayAbilitySpecHandle Handle,
        const FGameplayAbilityActorInfo* ActorInfo,
        const FGameplayTagContainer* SourceTags,
        const FGameplayTagContainer* TargetTags,
        FGameplayTagContainer* OptionalRelevantTags) const override
    {
        if (!Super::CanActivateAbility(Handle, ActorInfo, SourceTags, TargetTags, OptionalRelevantTags))
        {
            return false;
        }

        const ACharacter* Character = Cast<ACharacter>(ActorInfo->AvatarActor);
        return Character && Character->CanJump();
    }

    virtual void ActivateAbility(
        const FGameplayAbilitySpecHandle Handle,
        const FGameplayAbilityActorInfo* ActorInfo,
        const FGameplayAbilityActivationInfo ActivationInfo,
        const FGameplayEventData* TriggerEventData) override
    {
        Super::ActivateAbility(Handle, ActorInfo, ActivationInfo, ActorInfo, TriggerEventData);

        // 1. 应用 Root Motion（可选）
        // 2. 播放 Montage
        // 3. 等待输入释放（AbilityTask_WaitInputRelease）
        // 4. 应用 GameplayEffect（如消耗 Stamina）
        // 5. CommitAbility 消耗 Cost

        if (CommitAbility(Handle, ActorInfo, ActivationInfo))
        {
            // 跳跃成功
            Character->Jump();
        }
        else
        {
            EndAbility(Handle, ActorInfo, ActivationInfo, true, false);
        }
    }

    virtual void EndAbility(
        const FGameplayAbilitySpecHandle Handle,
        const FGameplayAbilityActorInfo* ActorInfo,
        const FGameplayAbilityActivationInfo ActivationInfo,
        bool bReplicateEndAbility,
        bool bWasCancelled) override
    {
        // 清理状态
        if (ACharacter* Character = Cast<ACharacter>(ActorInfo->AvatarActor))
        {
            Character->StopJumping();
        }

        Super::EndAbility(Handle, ActorInfo, ActivationInfo, bReplicateEndAbility, bWasCancelled);
    }
};
```

---

## HealthComponent：生命值组件与死亡状态机

**文件**：`Source/LyraGame/Character/LyraHealthComponent.h`

`ULyraHealthComponent` 是属性集（数据层）和游戏事件（表现层）之间的桥梁：

```cpp
UCLASS()
class ULyraHealthComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    // 绑定到 ASC 的 HealthSet
    void InitializeWithAbilitySystem(ULyraAbilitySystemComponent* ASC);

    // 解除绑定
    void UninitializeFromAbilitySystem();

    // 死亡状态查询
    bool IsDeadOrDying() const;
    ELyraDeathState GetDeathState() const;

    // 触发死亡
    void StartDeath();
    void FinishDeath();

    // 事件委托
    FOnHealthChangedDelegate OnHealthChanged;
    FOnHealthChangedDelegate OnMaxHealthChanged;
    FOnDeathStartedDelegate OnDeathStarted;
    FOnDeathFinishedDelegate OnDeathFinished;

protected:
    // 三态死亡状态机
    ELyraDeathState DeathState;
};
```

### 死亡状态机

```
NotDead ──→ DeathStarted ──→ DeathFinished
               │                    │
               │ 禁用输入           │ 清理 GameplayTag
               │ 播放死亡蒙太奇     │ 禁用碰撞
               │ 解除 Pawn 控制     │ 销毁/隐藏 Actor
               ▼                    ▼
           OnDeathStarted      OnDeathFinished
```

### 调用流程

```
GE 应用伤害
    → ULyraDamageExecution (GEEC) 计算最终伤害
    → HealthSet::Health 属性减少
    → HealthComponent::OnHealthChanged 回调
    → 检测 Health <= 0
    → StartDeath()
        → 广播 OnDeathStarted
        → 禁用输入
        → 播放死亡动画
    → FinishDeath()
        → 广播 OnDeathFinished
        → 清理 GameplayTag
        → 隐藏/销毁角色
```

---

## AbilityCost：消耗系统

**文件**：`Source/LyraGame/AbilitySystem/Abilities/LyraAbilityCost.h`

Lyra 通过 `ULyraAbilityCost` 抽象类实现可扩展的能力消耗：

```cpp
UCLASS(Abstract, DefaultToInstanced, EditInlineNew)
class ULyraAbilityCost : public UObject
{
    GENERATED_BODY()

public:
    // 执行消耗检查（能否支付）
    virtual bool CheckCost(
        const ULyraGameplayAbility* Ability,
        const FGameplayAbilitySpecHandle Handle,
        const FGameplayAbilityActorInfo* ActorInfo,
        FGameplayTagContainer* OptionalRelevantTags) const;

    // 执行消耗扣除
    virtual void ApplyCost(
        const ULyraGameplayAbility* Ability,
        const FGameplayAbilitySpecHandle Handle,
        const FGameplayAbilityActorInfo* ActorInfo,
        const FGameplayAbilityActivationInfo ActivationInfo);
};
```

### 内置消耗类型

| 消耗类 | 用途 |
|--------|------|
| ULyraAbilityCost_ItemTagStack | 消耗 InventoryItemInstance 上的 TagStack 计数（如弹药） |
| ULyraAbilityCost_AttributeSetBased | 基于 AttributeSet 属性的消耗（如体力值） |

配置方式：在 `ULyraGameplayAbility` 的 `AdditionalCosts` 数组中添加：
```cpp
UCLASS()
class UMyShootAbility : public ULyraGameplayAbility
{
    // 在编辑器中配置 AdditionalCosts
    // Example: ULyraAbilityCost_ItemTagStack → 每次射击消耗 1 发弹药
};
```

---

## 关键设计要点

1. **AbilitySet 可装配** — GA/GE/AttributeSet 以数据资产形式组合，可在运行时通过 EquipmentInstance 授予和回收
2. **ActivationGroup 策略化** — 将 GA 的并发控制从硬编码提升为声明式配置
3. **TagRelationshipMapping 外部化** — Cancel/Block 关系放在数据资产中，不需要修改 C++ 代码调整技能关系
4. **GE Context 可扩展** — CartridgeID 机制支持单次射击多次伤害的精确归因
5. **ProcessAbilityInput 三阶段管线** — Pressed/Held/Released 分桶管理，支持输入阻塞和持续型技能
6. **GA 模板标准结构** — CanActivateAbility → ActivateAbility → CommitAbility → 表现 → EndAbility
7. **HealthComponent 死亡状态机** — NotDead→DeathStarted→DeathFinished 三态转换，委托驱动事件广播
