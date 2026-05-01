# 玩家生成系统

## 概述

Lyra 的玩家生成系统由 `ULyraPlayerSpawningManagerComponent` 统一管理，它替代了传统的 `AGameModeBase::ChoosePlayerStart` 和 `FindPlayerStart` 方法。

## ULyraPlayerSpawningManagerComponent

[ULyraPlayerSpawningManagerComponent](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraPlayerSpawningManagerComponent.h) 继承自 `UGameStateComponent`，挂在 `ALyraGameState` 上。

### 职责

1. **管理所有玩家生成点** — 收集场景中的 `APlayerStart` 和自定义起点
2. **分配生成点** — 实现队伍生成逻辑、避免冲突
3. **处理重生** — 管理玩家死亡后的重生流程

### 核心逻辑

```cpp
UCLASS()
class ULyraPlayerSpawningManagerComponent : public UGameStateComponent
{
    GENERATED_BODY()

public:
    // 获取玩家起始点
    virtual AActor* OnChoosePlayerStart(AController* Player, TArray<APlayerStart*>& Starts);

    // 获取最近的可玩家起始点
    APlayerStart* GetBestPlayerStart(AController* Player);

    // 初始化生成点
    virtual void InitializeStarts();

protected:
    // 所有玩家起始点的缓存
    TArray<APlayerStart*> PlayerStarts;

    // 已分配的生成点
    TSet<APlayerStart*> OccupiedStarts;
};
```

## 玩家生成点

### UE 内建的 APlayerStart

`APlayerStart` 是 UE 内建的玩家起始点 Actor，包含：
- `PlayerStartTag` — 用于标记特定队伍的起始点
- 位置和旋转 — 生成时的位置和朝向

### Lyra 的扩展

Lyra 中使用自定义的玩家生成点，可能包含：
- 队伍归属标记
- 优先级设置
- 特殊生成规则（如随机、最远等）

## 生成流程

```
ALyraGameMode::HandleStartingNewPlayer
  → ULyraPlayerSpawningManagerComponent::OnChoosePlayerStart
    → 从 PlayerStarts 中选择合适的起点
    → 考虑：队伍归属、是否被占用、优先级
  → SpawnDefaultPawnAtTransform
    → 创建 ALyraPawn
    → 初始化 PawnExtensionComponent
  → Possess Pawn
    → PlayerController 控制 Pawn
```

## 队伍生成逻辑

对于团队模式，不同队伍的玩家应生成在不同位置：

- 从 `PlayerStarts` 中筛选匹配队伍标签的起点
- 同一队伍的起点分区布置
- 避免队伍间生成点距离过近
