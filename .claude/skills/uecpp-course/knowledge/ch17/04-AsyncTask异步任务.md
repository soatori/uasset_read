# AsyncTask 异步任务

## 概述

`AsyncTask` 是 UE 提供的简易异步任务 API，用于将 Lambda 或函数对象投递到指定的线程/线程池执行。与 FRunnable 不同，AsyncTask 不需要定义单独的类，适合轻量级异步操作。

## AsyncTask 函数

```cpp
#include "Async/TaskGraphInterfaces.h"

AsyncTask(ENamedThreads::Type Thread, TUniqueFunction<void()> Task);
```

参数：
- **Thread**：指定在哪个线程执行任务
- **Task**：要执行的可调用对象（Lambda、函数等）

### ENamedThreads 枚举（常用值）

| 值 | 执行线程 | 说明 |
|----|----------|------|
| `ENamedThreads::GameThread` | **主线程** | 在主线程执行任务 |
| `ENamedThreads::AnyThread` | **TaskGraph 线程池** | 在任何可用的 TaskGraph 工作线程执行 |
| `ENamedThreads::RenderThread` | 渲染线程 | 在渲染线程执行 |

## 基本用法

### 在主线程执行

```cpp
void UXGThreadSubsystem::InitAsynTask()
{
    AsyncTask(ENamedThreads::GameThread, []() {
        // 在 GameThread 执行
        // 可以安全操作 UObject
        UE_LOG(LogTemp, Warning, TEXT("我是主线程"));
    });
}
```

### 在后台线程执行 + 结果回传

这是最常见的异步工作模式：**后台线程计算，主线程应用结果**：

```cpp
void UXGThreadSubsystem::InitAsynTask_ALotOfWork()
{
    int32 CopyNum = MyNum;  // 在主线程取当前值（副本捕获）

    AsyncTask(ENamedThreads::AnyThread, [this, CopyNum]() {
        // 在 TaskGraph 后台线程执行耗时计算
        int32 Max = CopyNum;
        for (size_t i = 0; i < 10000; i++)
        {
            Max += i;
        }

        FPlatformProcess::Sleep(0.5);

        // 耗时计算完成后，推回 GameThread 更新结果
        AsyncTask(ENamedThreads::GameThread, [this, Max]() {
            SetMyNum(Max);  // 在 GameThread 安全更新 UObject 数据
        });
    });
}
```

### 嵌套 AsyncTask 模式

```
GameThread:   取数据副本 → (立即返回)
                          ↓ AsyncTask(AnyThread)
AnyThread:    耗时计算 → Sleep(0.5)
                          ↓ AsyncTask(GameThread)
GameThread:   应用结果 → SetMyNum(Max)
```

## AsyncTask 的跨线程通信

AsyncTask 是在 TaskGraph 线程池中调度的。这意味着：
- `ENamedThreads::GameThread` 的任务在 GameThread 执行
- `ENamedThreads::AnyThread` 的任务在 TaskGraph 工作线程执行
- 和所有其他系统（物理、音频等）**共享**同一个线程池

因为共享线程池，如果大量长时间运行的 AsyncTask 占用了所有工作线程，会导致引擎的其他系统也无法获得线程执行任务。这就是"阻塞主线程"问题的根源之一（参见 [08-经典卡主线程的方式](08-经典卡主线程的方式.md)）。

## AsyncTask 的线程安全日志

由于 AsyncTask 可能在非 GameThread 执行，不能直接使用 UE_LOG。推荐通过 AsyncTask 将日志推回 GameThread：

```cpp
void PrintWarning(FString InStr)
{
    AsyncTask(ENamedThreads::GameThread, [InStr]() {
        UE_LOG(LogTemp, Warning, TEXT("ThreadLog:[%s]"), *InStr);
    });
}
```

## Async vs AsyncTask 说明

| | AsyncTask | Async |
|--|-----------|-------|
| 头文件 | Async/TaskGraphInterfaces.h | Async/Async.h |
| 线程参数 | ENamedThreads | EAsyncExecution |
| 返回值 | void | TFuture\<T\> |
| 使用场景 | 即发即忘的异步任务 | 需要获取结果的异步任务 |

AsyncTask 更轻量（无返回值），适合"通知—执行"场景。Async 支持返回值（通过 TFuture），适合"计算—获取结果"场景。

## 代码参考

- [XGThreadSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.cpp) — InitAsynTask（L71-L98），InitAsynTask_ALotOfWork（L101-L134）
- [XGThreadSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.h) — 函数声明

## 相关章节

- [05-Async函数与TFuture](05-Async函数与TFuture.md)
- [08-经典卡主线程的方式](08-经典卡主线程的方式.md)
