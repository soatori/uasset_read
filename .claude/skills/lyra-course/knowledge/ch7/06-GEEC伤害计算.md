# GEEC 伤害计算

> 对应讲义：[086_讲解GEEC](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/docs/UE5_Lyra学习指南_086_讲解GEEC.md)
> 核心代码：[LyraDamageExecution](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Executions/LyraDamageExecution.h)、[LyraHealExecution](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Executions/LyraHealExecution.h)

## ULyraDamageExecution

继承自 `UGameplayEffectExecutionCalculation`，实现自定义伤害计算。

### FDamageStatics

私有静态结构体，缓存属性捕获定义：

```cpp
struct FDamageStatics
{
    // 声明属性捕获
    DECLARE_ATTRIBUTE_CAPTUREDEF(BaseDamage);  // 从 Source CombatSet 捕获

    FDamageStatics()
    {
        DEFINE_ATTRIBUTE_CAPTUREDEF(ULyraCombatSet, BaseDamage, Source, true);
    }
};

static const FDamageStatics& GetDamageStatics()
{
    static FDamageStatics Statics;
    return Statics;
}
```

### Execute_Implementation 执行流程

```
ULyraDamageExecution::Execute_Implementation(ExecutionParams, OutExecutionOutput)
  ├── 1. 捕获 BaseDamage
  │     └── ExecutionParams.AttemptCalculateCapturedAttributeMagnitude(
  │           GetDamageStatics().BaseDamageDef, EvaluationParams, BaseDamage)
  │
  ├── 2. 获取 EffectContext
  │     └── FLyraGameplayEffectContext::ExtractEffectContext(Params.GetEffectContext())
  │           └── 提取 HitResult、AbilitySource
  │
  ├── 3. 计算队伍伤害系数
  │     ├── 从 HitResult 获取目标 Actor
  │     ├── 查询团队子系统（ULyraTeamSubsystem）
  │     │     └── 比较 Source 和 Target 的团队 ID
  │     ├── 若同队：DamageInteractionAllowedMultiplier = 0.0（禁止友军伤害）
  │     └── 若敌队：DamageInteractionAllowedMultiplier = 1.0（正常伤害）
  │
  ├── 4. 计算衰减
  │     ├── 从 AbilitySource 获取 ILyraAbilitySourceInterface
  │     ├── 计算距离衰减
  │     │     └── AbilitySource->GetDistanceAttenuation(Distance, SourceTags, TargetTags)
  │     └── 计算物理材质衰减
  │           └── AbilitySource->GetPhysicalMaterialAttenuation(PhysMat, SourceTags, TargetTags)
  │
  ├── 5. 最终伤害公式
  │     └── FinalDamage = BaseDamage × DistanceAttenuation × PhysicalMaterialAttenuation × DamageInteractionAllowedMultiplier
  │
  └── 6. 输出伤害
        └── OutExecutionOutput.AddOutputModifier(
              FGameplayModifierEvaluatedData(GetDamageAttribute(), EGameplayModOp::Additive, FinalDamage))
```

### 最终伤害公式

```
FinalDamage = BaseDamage × DistanceAttenuation × PhysicalMaterialAttenuation × DamageInteractionAllowedMultiplier
```

| 因子 | 来源 | 说明 |
|------|------|------|
| BaseDamage | CombatSet | 武器/能力的基础伤害值 |
| DistanceAttenuation | AbilitySource 接口 | 根据距离的衰减曲线 |
| PhysicalMaterialAttenuation | AbilitySource 接口 | 根据物理材质的衰减系数 |
| DamageInteractionAllowedMultiplier | 队伍子系统 | 0.0（友军）/ 1.0（敌军） |

## ULyraHealExecution

治疗执行计算，与 UL yraDamageExecution 结构对称。

### FHealStatics

```cpp
struct FHealStatics
{
    DECLARE_ATTRIBUTE_CAPTUREDEF(BaseHeal);  // 从 Source CombatSet 捕获

    FHealStatics()
    {
        DEFINE_ATTRIBUTE_CAPTUREDEF(ULyraCombatSet, BaseHeal, Source, true);
    }
};
```

### 执行流程

```
ULyraHealExecution::Execute_Implementation(ExecutionParams, OutExecutionOutput)
  ├── 捕获 BaseHeal
  └── 输出 Healing 属性
        └── 不涉及衰减或队伍检查
```

注意：ULyraHealExecution 包裹在 `#if WITH_SERVER_CODE` 中，仅在服务器编译。

## FLyraGameplayEffectContext 在 GEEC 中的角色

FLyraGameplayEffectContext 在 GEEC 中承担数据传递职责：

```
GE Spec → FLyraGameplayEffectContext
  ├── HitResult（命中信息，含 PhysMat）
  ├── AbilitySourceObject（武器/能力来源）
  └── CartridgeID（子弹批次 ID）
        └── GEEC 中 Extract 后使用：
              ├── HitResult → 获取目标 Actor、物理材质、距离
              ├── AbilitySource → 获取衰减系数
              └── → 送入最终伤害计算
```
