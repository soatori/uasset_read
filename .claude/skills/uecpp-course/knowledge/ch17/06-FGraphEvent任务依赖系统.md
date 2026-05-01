# FGraphEvent 任务依赖系统

## 概述

FGraphEvent 是 UE TaskGraph 系统中的事件/任务依赖机制，允许构建**有向无环图（DAG）** 的任务依赖关系。开发者可以定义任务 A 必须在任务 B 完成后才能开始执行。

## 核心类型

| 类型 | 说明 |
|------|------|
| `FGraphEventRef` | GraphEvent 的引用计数智能指针 |
| `FGraphEventArray` | FGraphEventRef 的数组，用于表示多个先决条件 |
| `FFunctionGraphTask` | 基于 Lambda 的轻量级 GraphTask 工厂 |
| `TGraphTask<T>` | 模板类，适用于自定义 Task 类 |

## FFunctionGraphTask 工厂方法

```cpp
#include "Async/TaskGraphInterfaces.h"

// 创建并派发一个 GraphEvent
FGraphEventRef Event = FFunctionGraphTask::CreateAndDispatchWhenReady(
    Callable,           // TUniqueFunction<void()> 或类似签名
    TStatId(),          // 统计 ID，默认无效
    nullptr,            // Prerequisites（FGraphEventRef* 或 FGraphEventArray*）
    ENamedThreads::AnyThread  // 执行线程
);
```

参数：
- **Callable**：可调用对象。签名可以是 `void()` 或 `void(ENamedThreads::Type, const FGraphEventRef&)`
- **TStatId**：性能统计 ID，通常传 `TStatId()`（无效）
- **Prerequisites**：先决条件数组指针，该任务将在所有先决条件完成后才执行
- **ENamedThreads::Type**：指定在哪个线程执行

## 单个 GraphEvent

```cpp
void UXGThreadSubsystem::GraphEvent()
{
    // 创建并派发一个简单事件
    FGraphEventRef SimpleEvent = FFunctionGraphTask::CreateAndDispatchWhenReady([]() {
        PrintWarning(TEXT("SimpleEvent开始执行"));
        FPlatformProcess::Sleep(3);
        PrintWarning(TEXT("SimpleEvent执行完成"));
    });

    // 检查是否还在执行（未完成）
    check(!SimpleEvent->IsComplete());

    // 阻塞等待该事件完成
    SimpleEvent->Wait();
}
```

## 批量 GraphEvent

```cpp
void UXGThreadSubsystem::GraphEvent()
{
    FGraphEventArray SimpleEventArray;

    for (size_t index = 0; index < 20; index++)
    {
        SimpleEventArray.Add(FFunctionGraphTask::CreateAndDispatchWhenReady([index]() {
            FPlatformProcess::Sleep(index / 3);
            // 每个事件独立并发执行
        }));
    }

    // 阻塞等待所有事件完成
    FTaskGraphInterface::Get().WaitUntilTasksComplete(MoveTemp(SimpleEventArray));
}
```

## 任务依赖（DAG）

FGraphEvent 支持构建任务间的依赖关系。任务 B 可以设置任务 A 为先决条件，B 会在 A 完成后才开始执行。

### 依赖链语法

```cpp
// 方式 1：单个先决条件（构造函数参数）
FGraphEventRef B = FFunctionGraphTask::CreateAndDispatchWhenReady(
    []() { /* B 的工作 */ },
    TStatId(),
    A  // FGraphEventRef — B 在 A 完成后执行
);

// 方式 2：多个先决条件（FGraphEventArray 指针）
FGraphEventArray Prerequisites;
Prerequisites.Add(EventA1);
Prerequisites.Add(EventC);

FGraphEventRef D = FFunctionGraphTask::CreateAndDispatchWhenReady(
    []() { /* D 的工作 */ },
    TStatId(),
    &Prerequisites  // D 在所有先决条件完成后执行
);
```

### Lambda 签名

FFunctionGraphTask 的 Callable 支持两种签名：

```cpp
// 无参数签名
[]() {
    // 简单工作
}

// 带线程和事件引用的签名
[](ENamedThreads::Type Thread, const FGraphEventRef& Event) {
    // Thread：实际执行该任务的线程
    // Event：当前任务的 FGraphEventRef
}
```

### 示例：DAG 依赖链

```
    A
   / \
  B   A1
  |   |
  C   |
   \ /
    D
```

实现：

```cpp
void UXGThreadSubsystem::BatchGraphEvent()
{
    // A — 无先决条件，立即执行
    FGraphEventRef A = FFunctionGraphTask::CreateAndDispatchWhenReady([]() {
        FPlatformProcess::Sleep(2);
    });

    // B — 依赖 A
    FGraphEventRef B = FFunctionGraphTask::CreateAndDispatchWhenReady([]() {
        FPlatformProcess::Sleep(2);
    }, TStatId{}, A);

    // C — 依赖 B
    FGraphEventRef C = FFunctionGraphTask::CreateAndDispatchWhenReady([]() {
        FPlatformProcess::Sleep(2);
    }, TStatId{}, B);

    // A1 — 依赖 A（A 完成后并行执行 C 和 A1）
    FGraphEventRef A1 = FFunctionGraphTask::CreateAndDispatchWhenReady([]() {
        FPlatformProcess::Sleep(1);
    }, TStatId{}, A);

    // D — 依赖 A1 和 C
    FGraphEventArray Prerequisite;
    Prerequisite.Add(A1);
    Prerequisite.Add(C);

    FGraphEventRef D = FFunctionGraphTask::CreateAndDispatchWhenReady([]() {
        FPlatformProcess::Sleep(2);
    }, TStatId{}, &Prerequisite);

    // 等待 D 完成
    D->Wait();

    PrintWarning(TEXT("所有任务均已完成"));
}
```

## 等待机制

| 方法 | 说明 |
|------|------|
| `Event->Wait()` | 阻塞当前线程直到该事件完成 |
| `Event->IsComplete()` | 非阻塞检查事件是否完成 |
| `FTaskGraphInterface::Get().WaitUntilTaskCompletes(Event)` | 阻塞等待单个事件 |
| `FTaskGraphInterface::Get().WaitUntilTasksComplete(Array)` | 阻塞等待一组事件 |

## FGraphEvent 适用于流水线作业

DAG 依赖机制非常适合**流水线作业**：

```
原始数据处理 → 中间计算 → 格式转换 → 最终输出
                           ↓
                    并行分支A → 合并
                    并行分支B → 
```

每个阶段依赖前一个阶段的结果，部分阶段可以并行执行。

## 注意事项

- FGraphEvent 的所有任务在 **TaskGraph 线程池** 中执行
- `Wait()`/`WaitUntilTaskCompletes()` 会**阻塞**调用线程
- 在 GameThread 调用 `Wait()` 会阻塞主线程——需谨慎使用
- 依赖链中不要产生循环依赖（DAG 必须是无环的）
- FFunctionGraphTask 的 Lambda 在创建时即被派发，先决条件未满足时会排队等待

## 代码参考

- [XGThreadSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.cpp) — GraphEvent（L257-L298），BatchGraphEvent（L300-L373）
- [XGThreadSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.h) — 函数声明

## 相关章节

- [04-AsyncTask异步任务](04-AsyncTask异步任务.md)
- [05-Async函数与TFuture](05-Async函数与TFuture.md)
- [08-经典卡主线程的方式](08-经典卡主线程的方式.md)
