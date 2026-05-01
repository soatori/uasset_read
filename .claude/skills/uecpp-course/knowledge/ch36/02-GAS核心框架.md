# GAS 核心框架

## AbilitySystemComponent（ASC）

`XGRPGAbilitySystemComponent` 继承自 `UAbilitySystemComponent`，是 GAS 核心的注册和管理中枢。

### 关键职责

- 管理所有 GameplayAbility 的注册、激活、取消
- 持有 AttributeSet 实例
- 处理 GameplayEffect 的应用和移除
- 处理输入标签到能力的映射
- 通过 GameplayEvent 触发特定能力（如死亡能力）

### 输入处理

ASC 通过 `ProcessPlayerInput` 机制实现输入到能力的解耦绑定：

1. 玩家控制器接收输入事件
2. 将按下的输入标签存入 `InputPressedTags` 容器
3. 遍历 ASC 中已注册的能力 Spec
4. 查找与输入标签匹配的能力并尝试激活
5. 释放按键时向 ASC 发送输入释放通知

这种方式不需要为每个技能单独绑定按键事件，所有能力通过 GameplayTag 统一管理。

### 网络同步

- 网络同步模式设为 `Full` / `Mixed` / `Minimal` 根据角色身份决定
- 客户端通过 `NetUpdateFrequency = 100` 优化网络更新频率
- 专属服务器上部分功能通过 `WITH_SERVER_CODE` 宏限定

## GameplayAbility（能力基类）

`XGRPGGameplayAbility` 继承自 `UGameplayAbility`，是所有能力的基类。

### 配置策略

| 策略 | 设置 | 说明 |
|------|------|------|
| 实例化策略 | `InstancedPerActor` | 每个角色拥有独立实例，保存运行时状态 |
| 网络执行策略 | `LocalPredicted`（默认） | 本地预测执行，服务端权威验证 |
| 复制策略 | `ReplicateYes` | 能力激活和结束信息在网络间复制 |
| 触发方式 | InputTag（按键）/ GameplayEvent（事件） | 两种触发路径 |

### 能力注册

能力通过 `GiveAbility` 方法注册到 ASC：

```cpp
FGameplayAbilitySpec Spec(AbilityClass, Level, InputTag, SourceObject);
AbilityHandle = ASC->GiveAbility(Spec);
```

- `AbilityClass`：能力的 UClass
- `Level`：能力等级
- `InputTag`：绑定到输入系统的 GameplayTag
- `SourceObject`：来源对象（通常为角色自身或武器）

死亡能力的注册方式不同，它不需要 InputTag，而是通过 `FAbilityTriggerData` 由 GameplayEvent 触发。

### ActorInfo 与上下文

能力执行时通过 `FGameplayAbilityActorInfo` 获取 Actor 上下文信息：
- OwnerActor、AvatarActor
- PlayerController
- AbilitySystemComponent
- SkeletalMeshComponent（用于蒙太奇播放）

## GameplayTag 体系

`XGRPGGameplayTags` 采用 `NativeGameplayTags` 机制，在 C++ 中声明所有标签：

```cpp
// 头文件声明（摘自 XGRPGGameplayTag.h）
namespace XGRPGGameplayTags
{
    // 输入标签
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Move);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Jump);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Look_Mouse);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Look_Stick);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Crouch);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_AutoRun);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Melee);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_AirAttack);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Key_1);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Key_2);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Key_3);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(InputTag_Key_4);

    // 事件标签
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(GameplayEvent_Death);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(GameplayEvent_Reset);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(GameplayEvent_RequestReset);

    // SetByCaller 标签
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Damage);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(SetByCaller_Heal);

    // 状态标签
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Crouching);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_AutoRunning);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Death);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Death_Dying);
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(Status_Death_Dead);

    // 能力行为标记
    UE_DECLARE_GAMEPLAY_TAG_EXTERN(Ability_Behavior_SurvivesDeath);
}
```

```cpp
// 实现文件定义（摘自 XGRPGGameplayTag.cpp）
UE_DEFINE_GAMEPLAY_TAG_COMMENT(InputTag_Move, "InputTag.Move", "Move input.");
UE_DEFINE_GAMEPLAY_TAG_COMMENT(InputTag_Melee, "InputTag.Melee", "Left Button Little Attack .");
UE_DEFINE_GAMEPLAY_TAG_COMMENT(GameplayEvent_Death, "GameplayEvent.Death", "Event that fires on death. This event only fires on the server.");
UE_DEFINE_GAMEPLAY_TAG_COMMENT(Ability_Behavior_SurvivesDeath, "Ability.Behavior.SurvivesDeath", "An ability with this type tag should not be canceled due to death.");
```

### 标签分类

| 标签前缀 | 用途 | 示例 |
|---------|------|------|
| `InputTag.` | 输入绑定 | `InputTag.Melee`、`InputTag.Key.1` |
| `GameplayEvent.` | 事件触发 | `GameplayEvent.Death`、`GameplayEvent.Reset` |
| `SetByCaller.` | 动态数值传递 | `SetByCaller.Damage`、`SetByCaller.Heal` |
| `Status.` | 状态标记 | `Status.Death`、`Status.Crouching` |
| `Ability.Behavior.` | 能力行为标记 | `Ability.Behavior.SurvivesDeath` |

### 标签的双重作用

- **触发能力**：通过输入标签或事件标签激活能力
- **能力过滤**：死亡能力通过 `SurvivesDeath` 标签标记那些不会被死亡取消的能力
- **GameplayCue 路由**：GameplayCue 标签决定播放哪种受击反馈效果

## Prediction Key（预测密钥）

UE 5.4 到 5.5 版本间 Prediction Key 的 API 存在差异。当遇到过时警告时，通过以下宏处理：

```cpp
PRAGMA_DISABLE_DEPRECATION_WARNINGS
// 涉及 Prediction Key 的代码
PRAGMA_ENABLE_DEPRECATION_WARNINGS
```

这个是临时兼容方案，在升级引擎版本后应替换为新 API。

## IAbilitySystemInterface

角色基类 `XGRPGCharacterBase` 实现 `IAbilitySystemInterface` 接口，提供统一的 ASC 访问入口：

```cpp
class AXGRPGCharacterBase : public ACharacter, public IAbilitySystemInterface
{
    virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override;
};
```
