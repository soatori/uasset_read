# ParallelFor 并行循环

## 概述

`ParallelFor` 是 UE 提供的并行循环函数，将循环迭代分派到多个 TaskGraph 工作线程同时执行，利用多核 CPU 加速计算密集型任务。

## ParallelFor 函数

```cpp
#include "Async/ParallelFor.h"

void ParallelFor(
    int32 Count,                                // 迭代次数
    TFunctionRef<void(int32)> Body,             // 循环体
    EParallelForFlags Flags = EParallelForFlags::Default,  // 标志位
    int32 ChunkSize = -1                        // 数据块大小（-1 自动）
);
```

参数：
- **Count**：循环迭代次数（0 到 Count-1）
- **Body**：循环体 Lambda，接收 `int32 Index` 参数
- **Flags**：并行标志位
- **ChunkSize**：每次取出的数据块大小，-1 表示自动

## EParallelForFlags 枚举

| 值 | 说明 |
|----|------|
| `EParallelForFlags::Default` | 默认行为，TaskGraph 线程池执行 |
| `EParallelForFlags::ForceSingleThread` | **单线程执行**（测试用，用于对比性能） |
| `EParallelForFlags::Unbalanced` | **不平衡模式**，每个迭代计算量差异大时用 |
| `EParallelForFlags::BackgroundPriority` | 后台优先级执行 |
| `EParallelForFlags::PushToRenderThread` | 将任务推送到渲染线程执行 |

多个标志位可以按位组合：

```cpp
ParallelFor(Count, Body,
    EParallelForFlags::BackgroundPriority | EParallelForFlags::Unbalanced);
```

### ForceSingleThread

用于**性能对比测试**。强制串行执行，与并行版本对比耗时差异：

```cpp
// 串行版本（ForceSingleThread）
int64 Start = FDateTime::Now().GetTicks();
ParallelFor(10, Body, EParallelForFlags::ForceSingleThread);
int64 End = FDateTime::Now().GetTicks();
// 记录串行耗时

// 并行版本
int64 Start2 = FDateTime::Now().GetTicks();
ParallelFor(10, Body);
int64 End2 = FDateTime::Now().GetTicks();
// 记录并行耗时（比串行快许多）
```

### Unbalanced

当每次迭代的计算量不均匀时使用：

```
迭代 0：Sleep(0)  — 瞬间完成
迭代 1：Sleep(1)  — 1 秒
迭代 2：Sleep(2)  — 2 秒
迭代 3：Sleep(0)  — 瞬间完成
```

在默认模式下，迭代被平均分块，不均匀负载导致某些线程很早完成而空闲。`Unbalanced` 模式采用**工作窃取**算法，空闲线程可以窃取其他线程未完成的任务。

### BackgroundPriority

降低任务在 TaskGraph 中的优先级，适用于不紧急的后台计算。

## 基本用法

### 基础 ParallelFor

```cpp
void UXGThreadSubsystem::InitParallelFor()
{
    // 串行版本（测试基准）
    int64 Start = FDateTime::Now().GetTicks();
    for (size_t i = 0; i < 10; i++)
        FPlatformProcess::Sleep(0.2);
    int64 TickDelta = FDateTime::Now().GetTicks() - Start;

    // 并行版本
    Start = FDateTime::Now().GetTicks();
    ParallelFor(10, [](int32 Index) {
        UE_LOG(LogTemp, Display, TEXT("ParallelFor:%d"), Index);
        FPlatformProcess::Sleep(0.2);
    }, EParallelForFlags::ForceSingleThread | EParallelForFlags::BackgroundPriority | EParallelForFlags::Unbalanced);
    TickDelta = FDateTime::Now().GetTicks() - Start;
}
```

串行耗时 ≈ `10 × 0.2s = 2s`
并行耗时 ≈ `0.2s`（4 核 CPU 下，10 个任务分到约 4 个线程）

### ParallelFor + 锁保护

当并行循环中的不同迭代需要访问**共享变量**时，必须用锁保护：

```cpp
void UXGThreadSubsystem::InitParallelFor_Lock()
{
    // 串行版本
    int32 MaxNum = 0;
    int64 Start = FDateTime::Now().GetTicks();
    for (size_t i = 0; i < 10; i++)
    {
        MaxNum += i;
        FPlatformProcess::Sleep(i % 3);  // 不均匀负载
    }
    int64 TickDelta = FDateTime::Now().GetTicks() - Start;

    // 并行版本 + 锁保护
    FCriticalSection NumCriticalSection;
    MaxNum = 0;

    Start = FDateTime::Now().GetTicks();
    ParallelFor(10, [&MaxNum, &NumCriticalSection](int32 Index) {
        FPlatformProcess::Sleep(Index % 3);  // 不均匀负载

        FScopeLock Lock(&NumCriticalSection);
        MaxNum += Index;  // 共享变量累加，锁保护
    }, EParallelForFlags::BackgroundPriority | EParallelForFlags::Unbalanced);

    TickDelta = FDateTime::Now().GetTicks() - Start;
}
```

关键点：
- `MaxNum` 是**引用捕获**传入的共享变量
- `FCriticalSection` 也是**引用捕获**
- 每个迭代对 `MaxNum` 的累加都在 `FScopeLock` 保护下执行

## 性能对比（来自课程演示数据）

| 方式 | 10 次迭代 × Sleep(0.2) | 加速比 |
|------|------------------------|--------|
| 串行（单线程） | ~2000ms | 1x |
| ParallelFor（4 核） | ~200ms | ~10x |

> 注意：实际加速效果取决于 CPU 核心数、任务计算量和锁竞争程度。

## 注意事项

### 不要在 ParallelFor 中执行长时间阻塞操作

```cpp
// ❌ 错误：长时间 Sleep 阻塞 TaskGraph 线程池
ParallelFor(100, [](int32 Index) {
    FPlatformProcess::Sleep(2.0f);  // 阻塞 TaskGraph 工作线程 2 秒
});
```

因为 ParallelFor 在 **TaskGraph 线程池**中执行，长时间阻塞会影响引擎其他系统（物理、音频等）。

### 不要低估并行开销

- 任务拆分和线程间通信有额外开销
- 迭代次数很少或迭代体很简单时，串行可能更快
- 建议迭代次数至少大于 CPU 核心数

### Lambda 捕获

- 共享变量用引用捕获 `&`
- 每个迭代的独立数据用值捕获

## 代码参考

- [XGThreadSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.cpp) — InitParallelFor（L375-L412），InitParallelFor_Lock（L414-L463）
- [XGThreadSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/020_Thread/XGThreadSubsystem.h) — 函数声明

## 相关章节

- [03-加锁与线程安全](03-加锁与线程安全.md)
- [08-经典卡主线程的方式](08-经典卡主线程的方式.md)
