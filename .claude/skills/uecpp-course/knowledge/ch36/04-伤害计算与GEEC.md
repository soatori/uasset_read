# 伤害计算与 GEEC

## 概述

项目中有两个伤害执行计算类（GameplayEffectExecutionCalculation，GEEC），分别对应不同的伤害计算复杂度：

- `UXGRPGDamageExecution`：基础伤害计算
- `UXGRPGDamageExecution_Air`：带攻防公式的进阶伤害计算（空中版）

GEEC 仅在服务端执行，通过 `WITH_SERVER_CODE` 宏限定。

## 基础伤害执行（UXGRPGDamageExecution）

### 捕获属性

基础 GEEC 只捕获 `Damage` 属性（来自 Source/攻击者），不做攻防计算：

```cpp
UXGRPGDamageExecution::UXGRPGDamageExecution()
{
    // 只捕获 Source 的 Damage 属性
    DEFINE_ATTRIBUTE_CAPTUREDEF(UXGRPGCharacterArrtibuteSet,
        Damage, Source, true);
}
```

### 执行计算

将 GE 中配置的 Damage 值直接作为伤害输出，不做任何公式运算：

```cpp
void UXGRPGDamageExecution::Execute_Implementation(
    const FGameplayEffectCustomExecutionParameters& ExecutionParams,
    FGameplayEffectCustomExecutionOutput& OutExecutionOutput) const
{
    const FGameplayEffectSpec& Spec = ExecutionParams.GetOwningSpec();
    FAggregatorEvaluateParameters EvaluationParameters;

    float BaseDamage = 0.0f;
    ExecutionParams.AttemptCalculateCapturedAttributeMagnitude(
        DamageStatics().DamageDef, EvaluationParameters, BaseDamage);

    OutExecutionOutput.AddOutputModifier(
        FGameplayModifierEvaluatedData(DamageStatics().DamageProperty,
            EGameplayModOp::Additive, BaseDamage));
}
```

基础 GEEC 的本质角色是"透明直传"——伤害值在 GE 的 Modifier 中配置，GEEC 只负责从 Source 捕获并输出到 Target 的 Damage 属性，不介入任何运算。

## 进阶攻防计算（UXGRPGDamageExecution_Air）

增加了攻防属性的参与计算。

### 捕获属性

捕获 `Damage` 属性，同时通过 ASC 直接读取 `Attack` 和 `Defense` 属性值：

```cpp
UXGRPGDamageExecution_Air::UXGRPGDamageExecution_Air()
{
    DEFINE_ATTRIBUTE_CAPTUREDEF(UXGRPGCharacterArrtibuteSet,
        Damage, Source, true);
}
```

### 攻防公式

```
实际伤害 = Max(0, 基础伤害 + 攻击力 - 防御力)
```

这是一个线性加减公式，相比纯减法逻辑，附加的攻击力可以在小数值区间内提供足够的伤害区分度。

### 执行计算

```cpp
void UXGRPGDamageExecution_Air::Execute_Implementation(
    const FGameplayEffectCustomExecutionParameters& ExecutionParams,
    FGameplayEffectCustomExecutionOutput& OutExecutionOutput) const
{
    float BaseDamage = 0.0f;
    ExecutionParams.AttemptCalculateCapturedAttributeMagnitude(
        DamageStatics().DamageDef, EvaluationParameters, BaseDamage);

    // 从 Source 的 ASC 中直接读取攻击力和防御力
    UAbilitySystemComponent* SourceASC = ExecutionParams.GetSourceAbilitySystemComponent();
    float Attack = 0.0f, Defense = 0.0f;
    if (const UXGRPGCharacterArrtibuteSet* SourceAttr =
        Cast<UXGRPGCharacterArrtibuteSet>(SourceASC->GetAttributeSet(
            UXGRPGCharacterArrtibuteSet::StaticClass())))
    {
        Attack = SourceAttr->GetAttack();
        Defense = SourceAttr->GetDefense();
    }

    float BaseAirDamageDone =
        FMath::Max(0.0f, BaseDamage + Attack - Defense + 5.0f);

    OutExecutionOutput.AddOutputModifier(
        FGameplayModifierEvaluatedData(DamageStatics().DamageProperty,
            EGameplayModOp::Additive, BaseAirDamageDone));
}
```

**实现细节**：
- `Attack` 和 `Defense` 不是通过捕获（Capture）获取，而是通过 `GetAttributeSet` 直接读取
- Attack 和 Defense 都从 Source 的 ASC 读取（非分别从 Source 和 Target 读取）
- 额外叠加 5.0 的保底加成，确保小数值区间的体验

### 数据流

```
GameplayEffect（配置伤害系数）
    → GEEC Execute（读取攻防属性，计算最终伤害）
        → 输出 Damage 属性修改
            → PostGameplayEffectExecute（裁剪 + 事件通知）
```

## GEEC 与 GameplayEffect 的关系

GEEC 是 GameplayEffect 的"执行计算"模块：

- GameplayEffect 配置 `Execution` 数组指向 GEEC 类
- GEEC 在 `Execute_Implementation` 中做自定义计算
- 计算结果通过 `OutExecutionOutput` 的 `AddOutputModifier` 输出
- 输出的属性修改直接作用到目标的 AttributeSet

## 设置方式（蓝图）

1. 创建 GameplayEffect 蓝图
2. 在 Details 面板的 Executions 数组中添加条目
3. 将 Execution Class 设为对应的 GEEC C++ 类
4. 配置 Modifier 等可选参数
5. 将此 GE 绑定到 GameplayAbility 的激活效果或碰撞盒子的效果中

## 注意事项

- GEEC 只能在服务端执行，专属服务器不受影响
- 属性捕获时需区分 Source（攻击者）和 Target（被攻击者）
- 如果只需简单的加减法伤害，可使用 GE 内置 Modifier 而不需要 GEEC
- GEEC 适合需要自定义公式、条件判断或复杂计算逻辑的场景
