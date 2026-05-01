# SetTimer 基本使用与循环控制

## 概述

`SetTimer` 是 FTimerManager 的核心 API，用于注册定时器回调。本节通过 `ATimerActor` 的完整实现，讲解定时器的创建、参数配置、循环控制和清理模式。

## 核心 API：SetTimer

```cpp
FTimerManager& TimerManager = GetWorldTimerManager();
TimerManager.SetTimer(
    FTimerHandle& InOutHandle,        // [出参] 定时器句柄
    UObject* InObj,                    // 回调所属对象
    FuncType InTimerMethod,            // 成员函数指针
    float InRate,                      // 触发间隔（秒）
    bool InbLoop,                      // 是否循环
    float InFirstDelay                 // 首次延迟（秒）
);
```

| 参数 | 类型 | 说明 |
|------|------|------|
| InOutHandle | FTimerHandle& | 输出绑定的句柄；传入有效句柄会覆盖旧定时器 |
| InObj | UObject* | 回调所属对象，用于生命周期保护 |
| InTimerMethod | 函数指针 | 回调函数的地址 |
| InRate | float | 触发间隔（秒），<= 0 则不合法 |
| InbLoop | bool | true=循环执行，false=执行一次后自动清理 |
| InFirstDelay | float | 首次触发的延迟时间（秒），默认与 InRate 相同 |

## 必须在 BeginPlay 中创建定时器

定时器必须在 **BeginPlay** 中创建，**不能在构造函数中创建**：

```cpp
void ATimerActor::BeginPlay()
{
    Super::BeginPlay();
    FTimerManager& ThisTimeManager = GetWorldTimerManager();
    ThisTimeManager.SetTimer(MyTimerHandle, this, &ATimerActor::RepeatingFunction, 1.0f, true, 2.0f);
}
```

原因：构造函数调用时还没有有效的 World 上下文（Actor 仍在 CDO 构建阶段），`GetWorldTimerManager()` 返回无效引用。BeginPlay 阶段 World 已完全就绪。

## 循环控制模式

### 计数器控制

在回调函数中使用成员计数变量控制循环次数，达到上限后调用 ClearTimer 停止：

[TimerActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/TimerActor.h)

```cpp
FTimerHandle MyTimerHandle;
int32 RepeatingCallsRemaining = 3;
```

[TimerActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/TimerActor.cpp)

```cpp
void ATimerActor::RepeatingFunction()
{
    if (RepeatingCallsRemaining < 0)
    {
        GetWorldTimerManager().ClearTimer(MyTimerHandle);
        UE_LOG(LogTemp, Warning, TEXT("Timer End!"));
    }
    else
    {
        --RepeatingCallsRemaining;
        UE_LOG(LogTemp, Warning, TEXT("Timer Working! Remained Num: %d"), RepeatingCallsRemaining);
    }
}
```

执行流程：
1. BeginPlay 中 SetTimer：**2 秒**后首次触发，之后每 **1 秒**触发一次
2. 前 3 次回调：`RepeatingCallsRemaining` 从 3 递减到 0，打印 "Timer Working!"
3. 第 4 次回调：`RepeatingCallsRemaining` 为 -1 满足 `< 0` 条件，调用 `ClearTimer`

### 关键细节

- `RepeatingCallsRemaining = 3` 意味着实际执行 **4 次**（3, 2, 1, 0 然后清空），因为判断条件是 `< 0` 而递减在每次调用时发生
- `InbLoop = true` 是必须的；如果设为 false，定时器执行一次后自动清理，无法使用计数器控制
- `ClearTimer` 使 `MyTimerHandle` 失效，后续 `IsTimerActive` 返回 false

## 定时器查询 API

在 Tick 中查询定时器状态：

```cpp
void ATimerActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    bool bActive = GetWorldTimerManager().IsTimerActive(MyTimerHandle);
    float Rate = GetWorldTimerManager().GetTimerRate(MyTimerHandle);
    float Elapsed = GetWorldTimerManager().GetTimerElapsed(MyTimerHandle);
}
```

| API | 返回值 | 说明 |
|-----|--------|------|
| `IsTimerActive(Handle)` | bool | 定时器是否在运行中 |
| `GetTimerRate(Handle)` | float | 定时器的触发间隔 |
| `GetTimerElapsed(Handle)` | float | 当前周期已过去的时间 |

## 其他控制 API

| API | 作用 |
|-----|------|
| `PauseTimer(Handle)` | 暂停定时器，不触发回调但保留状态 |
| `UnPauseTimer(Handle)` | 恢复已暂停的定时器 |
| `ClearTimer(Handle)` | 清理指定定时器 |
| `ClearAllTimersForObject(Object)` | 清理关联对象的所有定时器 |

## 代码参考

- [TimerActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/TimerActor.h)
- [TimerActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/011_Timer/TimerActor.cpp)
