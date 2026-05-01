# FControlFlow 异步编排框架

## 概述

`FControlFlow` 是 UE5 实验性插件 **ControlFlows**（源自 Lyra 项目）提供的异步任务编排 API。它将多个异步步骤组织为线性链条，每个步骤完成时调用 `ContinueFlow()` 触发下一步，从根本上避免回调地狱。

## 核心 API

### 创建 ControlFlow

```cpp
#include "ControlFlow.h"
#include "ControlFlowManager.h"

FControlFlow& Flow = FControlFlowStatics::Create(this, TEXT("XGControlFlowInitLevel"));
```

- **this**：上下文 UObject 指针，用于生命周期管理
- **TEXT("XGControlFlowInitLevel")**：调试名称，在日志中标识该 Flow 实例
- 返回 `FControlFlow&` 引用，用于链式调用

### 添加步骤

```cpp
Flow.QueueStep(TEXT("InitLocalAsset"), this, &UXGControlFlowsSubsystem::InitLocalAsset, 0.1);
```

参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| DebugName | FName | 调试名称，用于日志识别 |
| Context | UObject* | 上下文对象，生命周期保护 |
| FuncPtr | 成员函数指针 | 回调函数，签名 `(FControlFlowNodeRef, double)` |
| ProgressValue | double | 进度值（0~1），传递给回调 |

回调函数签名：

```cpp
void InitLocalAsset(FControlFlowNodeRef SubFlow, double InProgreesValue);
```

- **SubFlow（FControlFlowNodeRef）**：控制节点引用，调用 `ContinueFlow()` 或 `CancelFlow()` 推进或终止流程
- **InProgreesValue**：QueueStep 时传入的进度值

### 启动流程

```cpp
Flow.ExecuteFlow();
```

调用 `ExecuteFlow()` 后，第一个 QueueStep 的回调被立即执行。

### 步骤推进与终止

```cpp
// 推进到下一步
SubFlow->ContinueFlow();

// 终止整个流程
SubFlow->CancelFlow();
```

- **ContinueFlow()**：标记当前步骤成功，框架自动执行下一个 QueueStep
- **CancelFlow()**：标记当前步骤失败，终止整个 Flow，后续步骤不再执行

## 完整用法

```cpp
void UXGControlFlowsSubsystem::InitLevel()
{
    FControlFlow& Flow = FControlFlowStatics::Create(this, TEXT("XGControlFlowInitLevel"));

    Flow.QueueStep(TEXT("InitLocalAsset"), this, &UXGControlFlowsSubsystem::InitLocalAsset, 0.1);
    Flow.QueueStep(TEXT("InitNetInfo"), this, &UXGControlFlowsSubsystem::InitNetInfo, 0.2);
    Flow.QueueStep(TEXT("InitUserInfo"), this, &UXGControlFlowsSubsystem::InitUserInfo, 0.5);
    Flow.QueueStep(TEXT("NotifyMainUI"), this, &UXGControlFlowsSubsystem::NotifyMainUI, 0.8);
    Flow.QueueStep(TEXT("FinishThisInit"), this, &UXGControlFlowsSubsystem::FinishThisInit, 1.0);

    Flow.ExecuteFlow();
}
```

## 生命周期管理

`FControlFlow` 实例通过 `FControlFlowStatics::Create` 注册到框架内部的静态 `TArray<FSharedControlFlow>` 数组中。只要 Flow 未完成或取消，该数组持有智能指针防止实例被销毁。Flow 完成后自动从数组中移除。

## 帧计数器

```cpp
uint64 FrameIndex = GFrameCounter;
UE_LOG(LogTemp, Warning, TEXT("[%s]--FramIndex:[%d]"), *FString(__FUNCTION__), FrameIndex);
```

`GFrameCounter`（定义于 `FrameCounter.h`）是全局帧计数器，用于在日志中标注每个步骤执行的帧号，便于观察异步步骤是否跨帧执行。

## 重入保护

```cpp
if (bIniting)
{
    UE_LOG(LogTemp, Warning, TEXT("正在初始化过程中"));
    return;
}
```

`bIniting` 标志位防止 `InitLevel()` 在流程未完成时被重复调用。

## 代码参考

- [XGControlFlowsSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsSubsystem.h) — InitLevel 声明（L163）
- [XGControlFlowsSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsSubsystem.cpp) — InitLevel 实现（L96-L131）
- [XGControlFlowsActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsActor.cpp) — Actor 中调用 InitLevel 的入口

## 相关章节

- [04-异步执行与线程跳跃模式](04-异步执行与线程跳跃模式.md)
- [05-ManageTask并行子任务架构](05-ManageTask并行子任务架构.md)
