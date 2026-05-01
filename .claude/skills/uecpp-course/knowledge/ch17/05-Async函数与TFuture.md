# Async 函数与 TFuture

## 概述

`Async` 是 UE 提供的函数模板，用于创建可以获取执行结果的异步任务。与 `AsyncTask` 不同，`Async` 返回 `TFuture<T>`，允许调用方获取异步操作的返回值。

## Async 函数

```cpp
#include "Async/Async.h"

TFuture<T> Async(EAsyncExecution Execution, TUniqueFunction<T()> Task);
```

参数：
- **Execution**：异步执行模式（EAsyncExecution 枚举）
- **Task**：要执行的可调用对象，返回值类型为 T

## EAsyncExecution 枚举

| 值 | 执行位置 | 说明 |
|----|----------|------|
| `EAsyncExecution::TaskGraphMainThread` | GameThread | 在主线程执行 |
| `EAsyncExecution::TaskGraph` | TaskGraph 线程池 | 在任意工作线程执行（任务有优先级） |
| `EAsyncExecution::Thread` | **独立线程** | 创建**专用操作系统线程**执行 |
| `EAsyncExecution::ThreadPool` | 线程池 | 在全局线程池执行 |

### EAsyncExecution::Thread 的说明

`EAsyncExecution::Thread` 会创建**独立的操作系统线程**，与 TaskGraph 线程池无关。这是它与 `TaskGraph` / `AnyThread` 的关键区别：

- `TaskGraph`：使用共享线程池，不创建新线程
- `Thread`：每次都创建新线程，不阻塞 TaskGraph

### 性能警告

> "性能是特别特别差的，不要用 Async" —— 课程原话

使用 `EAsyncExecution::Thread` 创建大量线程时：
- 每次调用创建新的操作系统线程，开销巨大
- CPU 占用率高
- 频繁的线程创建和销毁影响性能

适合少量、长时间运行的任务。不适合大量、短时间的小任务。

## 基本用法

### 在独立线程执行

```cpp
void UXGThreadSubsystem::InitAsyn()
{
    AsyncTask(ENamedThreads::AnyThread, []() {
        for (size_t i = 0; i < 100; i++)
        {
            Async(EAsyncExecution::Thread, []() {
                // 在独立线程执行，不阻塞 TaskGraph
                FPlatformProcess::Sleep(10);

                uint32 CurrentID = FPlatformTLS::GetCurrentThreadId();
                FString CurrentThread = FThreadManager::Get().GetThreadName(CurrentID);
                // 线程名通常为 "TaskGraphThread N"
            });
        }
    });
}
```

### Lambda 捕获模式

Async 的 Lambda 支持值捕获和引用捕获。在多线程场景中值捕获更安全：

```cpp
int32 SleepTime = 5;

// 值捕获——安全
Async(EAsyncExecution::Thread, [SleepTime]() {
    FPlatformProcess::Sleep(SleepTime);
});

// 引用捕获——风险（必须确保被引用对象在 Lambda 执行时仍存活）
Async(EAsyncExecution::Thread, [&SleepTime]() {
    FPlatformProcess::Sleep(SleepTime);  // 可能访问已销毁的变量
});
```

### Inline Lambda 写法

```cpp
Async(EAsyncExecution::Thread, [this, MyData]() {
    // 在独立线程执行长时间任务
    FPlatformProcess::Sleep(2.0f);

    // 完成后推回主线程
    Async(EAsyncExecution::TaskGraphMainThread, [this, Result = MyData]() {
        UE_LOG(LogTemp, Warning, TEXT("计算完成: %d"), Result);
    });
});
```

## TFuture 与 TPromise

`TFuture<T>` 用于获取异步任务的结果，`TPromise<T>` 用于从异步任务中设置结果。

### TFuture::Get()

`Get()` 是**阻塞调用**——调用线程会等待直到异步任务完成并返回结果：

```cpp
TFuture<int32> Future = Async(EAsyncExecution::Thread, [SleepTime]() {
    FPlatformProcess::Sleep(SleepTime);
    return SleepTime;
});

// 阻塞等待，直到 Async 任务完成
int32 Result = Future.Get();
UE_LOG(LogTemp, Warning, TEXT("Result: %d"), Result);
```

### 批量 TFuture

```cpp
void UXGThreadSubsystem::GetAsynFuture()
{
    AsyncTask(ENamedThreads::AnyThread, []() {
        TArray<TFuture<int32>> FutureResults;

        // 构建 100 个异步任务
        for (size_t i = 0; i < 100; i++)
        {
            FutureResults.AddDefaulted();
            FutureResults.Last() = Async(EAsyncExecution::Thread, [i]() -> int32 {
                int32 SleepTime = i % 5;
                FPlatformProcess::Sleep(SleepTime);
                return SleepTime;
            });
        }

        // 所有任务构建完毕（此时任务在并发执行）
        PrintWarning(TEXT("所有任务构建完毕"));

        // 逐个获取结果（阻塞等待每个任务完成）
        for (auto& TmpFuture : FutureResults)
        {
            int32 SleepTime = TmpFuture.Get();
            PrintWarning(FString::FromInt(SleepTime));
        }

        // 所有任务执行完毕
        PrintWarning(TEXT("所有任务执行完毕"));
    });
}
```

### TPromise 生命周期

`TPromise` 必须保证在异步操作完成前有效。如果 `TPromise` 在任务完成前被销毁，尝试获取 `TFuture::Get()` 的线程将收到错误。

```cpp
// 手动创建 Promise/Future 模式
TPromise<int32> Promise;
TFuture<int32> Future = Promise.GetFuture();

Async(EAsyncExecution::Thread, [Promise = MoveTemp(Promise)]() mutable {
    // Promise 在此 Lambda 中存活
    Promise.SetValue(42);  // 设置结果
});

int32 Result = Future.Get();  // 等待结果
```

## EAsyncExecution::Thread 执行流程

```
主线程调用 Async(Thread, Lambda)
    ↓
创建操作系统线程
    ↓
Lambda 在独立线程执行（线程名为 "TaskGraphThread N"）
    ↓
Lambda 返回 → 自动设置 TFuture 值
    ↓
线程被销毁
    ↓
Future.Get() 返回结果
```

## 代码参考

- [XGThreadSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.cpp) — InitAsyn（L182-L203），GetAsynFuture（L206-L252）
- [XGThreadSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.h) — 函数声明

## 相关章节

- [04-AsyncTask异步任务](04-AsyncTask异步任务.md)
- [06-FGraphEvent任务依赖系统](06-FGraphEvent任务依赖系统.md)
- [08-经典卡主线程的方式](08-经典卡主线程的方式.md)
