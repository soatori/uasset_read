# Dump 文件调试与多线程 Crash

## 概述

当游戏以 Shipping 构建发布后，断言和日志的排查能力大幅受限。此时 Dump 文件（`.dmp`）是定位崩溃问题的最终手段——它记录了崩溃发生时进程的完整内存快照和调用栈。

## 制造一个可复现的 Crash

### 多线程错误操作

```cpp
void AXGAssertActor::SetLocationWrong()
{
    AsyncTask(ENamedThreads::AnyThread, [this]() {
        UE_LOG(LogTemp, Warning, TEXT("危险操作,非主线程操作Actor类"));

        while (true)
        {
            static int32 LocationAdd = 1;
            LocationAdd++;
            FPlatformProcess::Sleep(0.1);
            SetActorLocation(FVector(100.f, 100.0f, 100.f + LocationAdd));
        }
    });
}
```

- 使用 `AsyncTask(ENamedThreads::AnyThread, Lambda)` 在任意线程执行任务
- Lambda 中调用 `SetActorLocation()` —— 这是 **GameThread 专属操作**
- 在非主线程操作 UObject/Actor 会导致不确定的崩溃

### 除零 Crash

```cpp
void AXGAssertActor::ZeroBug(int32 InZero)
{
    int32 AB = 55 / InZero;  // InZero == 0 时崩溃
}
```

简单可控的 Crash 制造方式，用于演示 Dump 文件分析流程。

## Dump 文件排查流程

### 第一步：打包确认

用 Shipping 配置打包项目，确保生成的 `.exe` 不包含断言检查，正常复现生产环境的崩溃行为。

### 第二步：获取 Dump 文件

崩溃发生时，Windows 会生成 `.dmp` 文件。位置通常在：

- 打包输出目录下的 `Saved/Crashes/`
- 或 Windows 的 `%LOCALAPPDATA%\CrashDumps\`

### 第三步：在 Visual Studio 中打开

1. 双击 `.dmp` 文件
2. 点击"使用 Visual Studio 调试"
3. VS 自动加载崩溃时的调用栈

### 第四步：分析 Call Stack

Dump 文件的关键信息：

- **崩溃线程**：标记出发生崩溃的线程（GameThread 或 Background Worker Thread）
- **调用栈**：从崩溃点向上追溯，找到最终导致 Crash 的代码行
- **模块信息**：崩溃发生在哪个模块中（UE 引擎代码还是项目代码）

### 第五步：确保符号文件可用

- 打包时生成 `.pdb` 符号文件
- `.pdb` 文件与 `.exe` 版本必须完全匹配
- `.pdb` 提供行号信息，否则只能看到汇编级调用栈

## Dump 文件 vs 其他调试手段

| 方法 | 适用场景 | 限制 |
|------|---------|------|
| UE_LOG | 开发阶段追踪运行状态 | Shipping 中日志受限 |
| 断言 | 开发阶段条件检查 | Shipping 中不生效 |
| Dump 文件 | 发布后 Crash 定位 | 需要符号文件，无法即时交互 |
| VS 附加进程 | 运行时实时调试 | 不适用于已发布的游戏 |

Dump 文件是**最终的调试手段**——当所有其他方法都无法在开发现场复现问题时，通过用户端生成的 Dump 文件可以还原崩溃现场。

## 注意事项

- **多线程 Crash 最难复现**：多线程崩溃通常不固定，每次运行的表现可能不同
- Dump 文件分析只能看到崩溃时的状态，无法追溯导致崩溃的完整时序
- 确保符号文件（`.pdb`）归档保存，版本对应才能正确分析

## 配套代码

- [XGAssertActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/017_Assert/XGAssertActor.cpp) — SetLocationWrong（多线程错误操作）和 ZeroBug（除零 Crash）实现
