# Subsystem 的 Tick 实现（FTickableGameObject）

## 问题背景

UObject 基类没有 Tick 机制。AActor 可以通过 `PrimaryActorTick.bCanEverTick = true` 开启 Tick，但 UObject（包括 UGameInstanceSubsystem）默认没有 Tick 能力。

要让 Subsystem 获得 Tick 能力，需要实现 `FTickableGameObject` 接口。

## 使用 FTickableGameObject

### 头文件声明

```cpp
#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"

UCLASS()
class UXGSimpleSubsystem : public UGameInstanceSubsystem,
                           public FTickableGameObject
{
    GENERATED_BODY()
public:
    virtual void Tick(float DeltaTime) override;
    virtual bool IsTickable() const override;
    virtual TStatId GetStatId() const override;
};
```

### 三个必须重写的方法

#### Tick(float DeltaTime)

每帧执行逻辑的位置：

```cpp
void UXGSimpleSubsystem::Tick(float DeltaTime)
{
    if (bFirstTick)
    {
        bFirstTick = false;
        // 首次 Tick 初始化
    }
    // 每帧逻辑
}
```

#### IsTickable() const

控制是否允许 Tick 执行。核心规则是排除 CDO（Class Default Object），因为 CDO 不应该参与游戏逻辑 Tick：

```cpp
bool UXGSimpleSubsystem::IsTickable() const
{
    return !IsTemplate();
}
```

`IsTemplate()` 返回 `true` 时表示当前对象是 CDO，应跳过 Tick。

#### GetStatId() const

返回统计追踪 ID，用于性能分析工具（Stat System）：

```cpp
TStatId UXGSimpleSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UXGSimpleSubsystem, STATGROUP_Tickables);
}
```

- 第一个参数是类名
- 第二个参数通常使用 `STATGROUP_Tickables`

## bFirstTick 模式

### 为什么需要

- 在 Subsystem 的 `Initialize()` 中，某些依赖对象可能还未创建
- Actor 的 `BeginPlay()` 执行时机晚于 Subsystem 的 `Initialize()`
- Subsystem 自身没有 BeginPlay 回调

### 工作原理

```cpp
bool bFirstTick = true;

void UXGSimpleSubsystem::Tick(float DeltaTime)
{
    if (bFirstTick)
    {
        bFirstTick = false;
        // 在此处执行需要所有依赖就绪的初始化
    }
}
```

第一个 Tick 帧的时机已经足够晚——此时所有 Actor 的 BeginPlay 都已执行完毕，可以安全访问任何游戏对象。

## 性能注意事项

- **不要在 Tick 中做重操作**：日志打印、Line Trace、复杂计算都不适合放在 Tick 中
- **非必要不使用 Tick**：优先考虑事件驱动模式（如委托），避免轮询
- **如果使用 Tick**：尽量降低频率（通过自定义计时器，而非依赖引擎 Tick 间隔）

## 完整示例

```cpp
// XGSimpleSubsystem.h
UCLASS()
class UXGSimpleSubsystem : public UGameInstanceSubsystem,
                           public FTickableGameObject
{
    GENERATED_BODY()
public:
    virtual void Tick(float DeltaTime) override;
    virtual bool IsTickable() const override;
    virtual TStatId GetStatId() const override;
private:
    bool bFirstTick = true;
};

// XGSimpleSubsystem.cpp
void UXGSimpleSubsystem::Tick(float DeltaTime)
{
    if (bFirstTick)
    {
        bFirstTick = false;
    }
}

bool UXGSimpleSubsystem::IsTickable() const
{
    return !IsTemplate();
}

TStatId UXGSimpleSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UXGSimpleSubsystem, STATGROUP_Tickables);
}
```

## 配套代码

- [XGSimpleSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGSimpleSubsystem.h) — FTickableGameObject 继承与 Tick 声明
- [XGSimpleSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/016_Subsystem/XGSimpleSubsystem.cpp) — Tick/IsTickable/GetStatId 实现
