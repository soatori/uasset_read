# GA_Melee（近战能力）

> 对应讲义：[084_讲解GA_Melee](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/docs/UE5_Lyra学习指南_084_讲解GA_Melee.txt)

GA_Melee 是基于 Blueprint 实现的近战攻击能力，使用 Capsule Trace（胶囊体扫描）作为命中检测手段。

## 能力配置

| 属性 | 值 |
|------|-----|
| InputTag | `InputTag.Ability.Melee` |
| NetExecutionPolicy | LocalPredicted |
| InstancingPolicy | InstancedPerActor |

## 执行流程

```
InputTag.Ability.Melee Pressed
  └── TryActivateAbility()
        └── ActivateAbility()
              ├── 播放近战动画 Montage
              │     ├── 挥舞攻击动画
              │     └── 冲剌（Lunge）动画 — 向前位移
              │
              ├── 命中检测（Capsule Trace）
              │     ├── 前端扇形范围扫描
              │     ├── 检测到 Actor → 检查友军伤害
              │     └── 检查遮挡（Obstruction Check）
              │
              ├── 命中时
              │     ├── 应用伤害 GE（通过 GEEC）
              │     ├── 播放命中音效（Hit Sound）
              │     └── 播放打击感效果
              │
              ├── 未命中时
              │     └── 播放挥空音效（Swing Sound）
              │
              └── EndAbility()
```

## 伤害计算

近战伤害使用与远程武器相同的 GEEC（ULyraDamageExecution），因此伤害公式一致：

```
最终伤害 = BaseDamage × DistanceAttenuation × PhysicalMaterialAttenuation × DamageInteractionAllowedMultiplier
```

近战的距离衰减（DistanceAttenuation）通常为 1.0（近战衰减系数为 1），物理材质衰减由被击中部位的物理材质决定。

## 冲剌（Lunge）机制

近战攻击时角色会向前位移一段距离，接近目标。Lunge 运动通过 Montage 中的 Root Motion 驱动，而非像 GA_Dash 使用 `ApplyRootMotionConstantForce`。

## 友军伤害检查

命中检测后的过滤步骤：
1. 检测到 Actor
2. 获取目标上的 Team 信息（通过团队子系统）
3. 若为友军（同一团队），则跳过伤害应用
4. 若为敌军或中立，则执行伤害 GE

## 音效管理

| 事件 | 音效 |
|------|------|
| 挥舞攻击 | Swing Sound |
| 命中目标 | Hit Sound |
| 冲剌 | Lunge Sound |
