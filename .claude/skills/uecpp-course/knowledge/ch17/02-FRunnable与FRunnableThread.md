# FRunnable 与 FRunnableThread

## 概述

FRunnable 是 UE 提供的跨平台线程接口，允许创建和管理独立的操作系统线程。与 TaskGraph/AsyncTask 不同，FRunnable 创建的线程是**独立线程**，不占用 TaskGraph 线程池资源。

## FRunnable 接口

FRunnable 定义了 4 个虚方法：

| 方法 | 调用线程 | 说明 |
|------|----------|------|
| `Init()` | 新创建的线程 | 初始化资源，返回 true 继续执行，false 终止 |
| `Run()` | 新创建的线程 | 主要工作循环，返回线程退出码 |
| `Stop()` | **外部线程**（调用方线程） | 通知线程停止工作的信号 |
| `Exit()` | 新创建的线程 | 清理资源 |

### 执行顺序

```
FRunnableThread::Create() → [新线程启动] → Init() → Run() → [Stop() 被外部线程调用] → Run() 退出 → Exit()
```

### Init()

在新线程中执行，用于初始化线程特有的资源。返回 `false` 将导致 Run() 不被执行，线程直接退出。

### Run()

新线程的主函数。通常会实现一个**工作循环**：

```cpp
uint32 Run() override
{
    while (bRunning)
    {
        FPlatformProcess::Sleep(0.04f);  // 避免 CPU 空转

        if (!bRunning)
            break;

        // 执行实际工作
        DoWork();
    }
    return 0;
}
```

### Stop()

**注意：Stop() 不是在创建的新线程中调用，而是在外部调用方的线程中调用**（例如主线程）。Stop() 的设置需要配合 Run() 中的检测机制。

### Exit()

在新线程退出前调用，用于清理线程特有资源。

## FRunnableThread::Create 工厂方法

`FRunnableThread::Create` 将 Runnable 对象和新线程绑定：

```cpp
FRunnableThread* Thread = FRunnableThread::Create(
    Runnable,           // FRunnable* - 要执行的 Runnable 对象
    *ThreadName,        // const TCHAR* - 线程名（用于调试）
    0,                  // uint32 StackSize - 栈大小，0 表示默认
    TPri_Normal         // EThreadPriority - 线程优先级
);
```

参数详解：
- **Runnable**：实现了 FRunnable 接口的对象指针
- **ThreadName**：线程名称，在 FThreadManager 中注册，可通过 `FThreadManager::Get().GetThreadName(ThreadID)` 查询
- **StackSize**：0 表示使用系统默认栈大小
- **优先级**：`TPri_Normal` / `TPri_Highest` / `TPri_Lowest` / `TPri_BelowNormal` / `TPri_AboveNormal` / `TPri_TimeCritical` / `TPri_SlightlyBelowNormal`

返回值：若创建成功，返回一个 `FRunnableThread*` 指针；失败返回 nullptr。

## 生命周期管理

### 使用 TSharedPtr 管理 Runnable

```cpp
TSharedPtr<FXGSimpleRunnable> Runnable = MakeShared<FXGSimpleRunnable>(TEXT("MyThread"));
FRunnableThread* Thread = FRunnableThread::Create(Runnable.Get(), *Runnable->GetThreadName());
```

### 停止和销毁线程

```cpp
void ReleaseThread()
{
    // 1. 先发送停止信号
    if (Runnable.IsValid())
    {
        Runnable->Stop();
    }

    // 2. 等待线程执行完毕
    if (Thread)
    {
        Thread->WaitForCompletion();  // 阻塞直到 Run() 返回
    }
}
```

**Dekinaitize 时释放线程**：在 UGameInstanceSubsystem 的 `Deinitialize()` 中调用释放方法，确保子系统销毁前线程已清理。

## 线程识别与日志

通过以下 API 可以获取当前线程信息：

```cpp
uint32 CurrentID = FPlatformTLS::GetCurrentThreadId();
FString CurrentName = FThreadManager::Get().GetThreadName(CurrentID);
```

静态工具方法设计：

```cpp
static void PrintThreadInfo(const FString& InInfo)
{
    uint32 ThreadID = FPlatformTLS::GetCurrentThreadId();
    FString ThreadName = FThreadManager::Get().GetThreadName(ThreadID);
    FString Message = FString::Printf(TEXT("--CurrentID:[%d]--CurrentThreadName:[%s]"), ThreadID, *ThreadName);
    PrintWarning(Message);
}
```

## 线程休眠

`FPlatformProcess::Sleep(float Seconds)` 使当前线程休眠指定时间（秒为单位，浮点数精度）。

示例中使用的 0.04f 秒 = 40ms，约等于 25 FPS 的 Tick 间隔，适合不需要高频率响应的工作循环。

## 线程安全注意事项

- FRunnable 的成员变量（如 `bRunning`）会被**多个线程**同时访问——Run() 在新线程中读取，Stop() 在外部线程中写入
- 共享变量需要锁保护（FCriticalSection + FScopeLock）或使用原子类型（FThreadSafeBool / std::atomic<bool>）
- 不能在非 GameThread 调用 UObject 相关 API
- 不能在非 GameThread 直接使用 UE_LOG（需通过 AsyncTask 推回 GameThread）

## 线程安全的日志模式

```cpp
static void PrintWarning(FString InStr)
{
    AsyncTask(ENamedThreads::GameThread, [InStr]() {
        UE_LOG(LogTemp, Warning, TEXT("ThreadLog:[%s]"), *InStr);
    });
}
```

将日志通过 AsyncTask 推送到 GameThread 输出，避免非主线程直接调用 UE_LOG 的潜在问题。

## 代码参考

- [XGSimpleRunnable.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGSimpleRunnable.h) — FRunnable 接口声明，FCriticalSection + bRunning 模式
- [XGSimpleRunnable.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGSimpleRunnable.cpp) — Init/Run/Stop/Exit 完整实现
- [XGThreadSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.h) — TSharedPtr 管理 Runnable + FRunnableThread* 的声明
- [XGThreadSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.cpp) — InitXGSimpleThread / ReleaseXGSimpleThread 完整实现

## 相关章节

- [01-虚幻多线程基础架构](01-虚幻多线程基础架构.md)
- [03-加锁与线程安全](03-加锁与线程安全.md)
