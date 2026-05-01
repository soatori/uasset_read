# GA_Jump 与 GA_Dash

> 对应讲义：[082_讲解GA_Jump](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/docs/UE5_Lyra学习指南_082_讲解GA_Jump.md)、[083_讲解GA_Dash](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/docs/UE5_Lyra学习指南_083_讲解GA_Dash.md)
> 核心代码：[LyraGameplayAbility_Jump](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility_Jump.h)

## ULyraGameplayAbility_Jump

**Ability 属性：** `InstancedPerActor`、`NetExecutionPolicy = LocalPredicted`

### 激活检查

```cpp
bool ULyraGameplayAbility_Jump::CanActivateAbility(...)
{
    if (!Super::CanActivateAbility(...)) return false;
    
    ALyraCharacter* LyraCharacter = GetLyraCharacterFromActorInfo();
    return LyraCharacter && LyraCharacter->CanJump();
}
```

委托给 `ALyraCharacter::CanJump()`，继承自 `ACharacter::CanJump()`，检查 `bIsCrouched`、`GetCharacterMovement()->IsFalling()` 等条件。

### 执行流程

```
ActivateAbility()
  ├── CharacterJumpStart()
  │     └── ALyraCharacter::Jump() → ACharacter::Jump()
  │           └── CharacterMovement.SetJumping(true) + 垂直初速度
  │
  └── AbilityTask_WaitInputRelease(bTestInitialState=true)
        └── OnRelease 回调 → CharacterJumpStop()
              └── ALyraCharacter::StopJumping() → ACharacter::StopJumping()
                    └── CharacterMovement.SetJumping(false)
```

`ACharacter::Jump()` / `StopJumping()` 本身具有内置的网络同步能力，因此 GA_Jump 不需要额外的复制逻辑，依赖 CharacterMovement 的复制。

### AbilityTask_WaitInputRelease

[UAbilityTask_WaitInputRelease](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/AbilitySystem/Abilities/LyraGameplayAbility_Jump.h)（自定义版本，非标准 UAbilityTask_WaitInputRelease）：

- 注册回调到 `AbilityReplicatedEventDelegate(InputReleased)`
- `bTestInitialState`：若为 true，在 Activate 时立即检查输入是否已释放，若是则直接触发回调
- 远程客户端通过 `CallReplicatedEventDelegateIfSet` 进行预测回退同步

### AbilityTask_StartAbilityState（已弃用）

`UAbilityTask_StartAbilityState` 虽然标记了 `DEPRECATED`，但 GA_Jump 中仍使用它进行状态生命周期管理。在 `OnDestroy` 中处理：

```cpp
void UAbilityTask_StartAbilityState::OnDestroy(bool bInOwnerFinished)
{
    // 检查是否被外部中断（interrupted）
    // 检查是否正常结束（bWasEnded || AbilityEnded）
    // 根据状态路由到 EndState 或 InterruptedState 回调
}
```

## GA_Dash（Root Motion 冲刺）

**Ability 属性：** `NetExecutionPolicy = LocalPredicted`

### 能力配置

在 Blueprint 中配置以下参数：
- 冲刺方向
- 冲刺距离 / 速度
- 冲刺动画（Montage）
- Root Motion 力的强度

### 执行流程

```
ActivateAbility()
  ├── 计算冲刺方向（仅在客户端/独立计算，服务端跳过）
  │     └── 基于角色朝向或移动输入方向
  │
  ├── UAbilityTask_PlayMontageAndWait
  │     └── ASC::PlayMontage(AnimMontage, Rate, StartSection)
  │           └── 播放蒙太奇，同步到 RepAnimMontageInfo
  │
  └── UAbilityTask_ApplyRootMotionConstantForce
        └── MovementComponent->ApplyRootMotionSource(FRootMotionSource_ConstantForce)
              ├── WorldDirection → 计算的方向
              ├── Strength → 冲刺速度
              ├── Duration → 冲刺持续时间
              ├── bIsAdditive → 是否为叠加
              ├── bUsesGravity → 是否受重力影响
              └── FinishVelocityParams → 结束时的速度行为
```

### 网络同步机制

**Montage 复制：**

```cpp
// ASC::PlayMontageInternal()
ASC->PlayMontageInternal(...)
{
    // 更新 RepAnimMontageInfo
    RepAnimMontageInfo.AnimMontage = MontageToPlay;
    RepAnimMontageInfo.SectionIdToPlay = 0;
    // ...
    ASC->ForceNetUpdate();  // 强制网络更新
}
```

`FGameplayAbilityRepAnimMontage` / `RepAnimMontageInfo` 通过属性复制同步到客户端。客户端收到后记录 montage 数据用于重放。预测键拒绝时绑定 `OnPredictiveMontageRejected` 回调。

**Root Motion 复制：**

Root Motion 本身作为移动属性通过 CharacterMovement 复制，不需要额外同步代码。`LocalPredicted` 策略确保客户端预测冲刺位置，服务端验证后修正。

### 距离计算

GA_Dash 的冲刺距离不是由动画驱动的 Root Motion 决定的，而是通过 `ApplyRootMotionConstantForce` 的 `Strength * Duration` 手动计算。这使得冲刺距离与动画解耦，便于调整和复用。
