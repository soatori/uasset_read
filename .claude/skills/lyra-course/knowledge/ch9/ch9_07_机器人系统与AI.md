# 机器人系统与 AI

## 架构概览

机器人系统负责在游戏中生成 AI 控制的玩家（Bot），将其分配到队伍，并驱动它们参与游戏。AI 行为基于行为树和 GAS 集成。

## 机器人创建

[ULyraBotCreationComponent](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/)

```cpp
UCLASS()
class ULyraBotCreationComponent : public UGameStateComponent
{
    // 需要创建的 Bot 数量
    UPROPERTY(EditDefaultsOnly)
    int32 NumBotsToCreate = 5;

    // Bot 的 Pawn 类
    UPROPERTY(EditDefaultsOnly)
    TSubclassOf<APawn> BotPawnClass;

    // 创建 Bot
    void ServerCreateBots();
};
```

### Bot 创建流程

1. 在 Experience 加载完成后调用 `ServerCreateBots`
2. 服务器端生成 `ALyraPlayerBotController`
3. 将 Bot Controller 注册到队伍系统
4. 后续由生成管理器（`ULyraPlayerSpawningManagerComponent`）分配出生点

## Bot 控制器

[ALyraPlayerBotController](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/)

```cpp
UCLASS()
class ALyraPlayerBotController : public AModularAIController, public ILyraTeamAgentInterface
{
    // 队伍相关
    virtual void OnPossess(APawn* InPawn) override;
    virtual void OnUnPossess() override;

    // 队伍 ID 管理
    UPROPERTY()
    FOnLyraTeamIndexChangedDelegate OnTeamIndexChanged;
    int32 MyTeamID;

    // 重启
    void ServerRestartController();
};
```

- 继承 `AModularAIController` 支持模块化组件
- 实现 `ILyraTeamAgentInterface` 参与队伍系统
- 被击杀后通过 `ServerRestartController` 重新生成

### Bot 作弊

[ULyraBotCheats](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/)

- 控制台命令：生成/销毁 Bot
- 切换 Bot 行为

## 行为树与环境查询

### 行为树（Behavior Tree）

- 定义 Bot 的行为逻辑：巡逻、搜索、战斗、追击
- 通过黑板（Blackboard）存储目标、位置、状态

- AI 感知系统驱动行为树节点
- Bot 使用视觉感知检测敌人，使用听觉感知检测事件

### 环境查询（EQS）

- 选择最佳射击位置、掩护位置、移动目标
- 测试条件：可见性、距离、队伍关系

### GAS 集成

- Bot 通过 GAS 释放技能、响应 GameplayEvent
- Bot 拥有与人类玩家相同的 AbilitySet
- 通过 `ULyraAbilitySystemComponent` 处理技能激活和冷却
- Bot 的行为树节点调用 GAS 相关功能

### LyraShooterBot 控制器

流程：
1. 生成 `ALyraPlayerBotController`
2. 初始化队伍 ID
3. 生成 Pawn → Possess → 应用 Experience 的 AbilitySet
4. 启动行为树
5. 死亡 → 等待重生 → 重新 Possess
