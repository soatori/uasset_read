# ControlFlows 详解

## 概述

FControlFlow 是 UE5 实验性异步任务编排框架（源自 Lyra 项目），将多个异步步骤组织为线性链条，避免回调嵌套。在此基础上扩展了 ManageTask 并行子任务模式，通过 FTickableGameObject 的 Tick 轮询检测大量并行子任务的完成状态。

## FControlFlow 核心 API

```cpp
#include "ControlFlowManager.h"
#include "ControlFlow.h"

// 创建命名 ControlFlow，指定任务名和上下文
FControlFlow& Flow = FControlFlowStatics::Create("InitLevel", ContextObject);

// 注册步骤
Flow.QueueStep(TEXT("InitLocalAsset"), [](FControlFlowNodeRef FlowNode, double Value)
{
    // 异步操作
    AsyncTask(ENamedThreads::AnyThread, [FlowNode]()
    {
        // 后台工作...
        AsyncTask(ENamedThreads::GameThread, [FlowNode]()
        {
            // 进入下一步
            FlowNode->ContinueFlow();
        });
    });
});
```

| 方法 | 说明 |
|------|------|
| `FControlFlowStatics::Create(Name, Context)` | 创建命名 ControlFlow 实例 |
| `Flow.QueueStep(Name, Callback)` | 将步骤加入链中 |
| `Flow.ExecuteFlow()` | 启动执行 |
| `FlowNode->ContinueFlow()` | 通知框架进入下一步 |
| `FlowNode->CancelFlow()` | 取消后续步骤 |

### 完整示例

```cpp
void UXGControlFlowsSubsystem::InitLevel()
{
    FControlFlow& Flow = FControlFlowStatics::Create("InitLevel", this);

    Flow.QueueStep(TEXT("InitLocalAsset"), [this](FControlFlowNodeRef FlowNode, double Value)
    {
        AsyncTask(ENamedThreads::AnyThread, [FlowNode]()
        {
            FPlatformProcess::Sleep(1.0f);
            AsyncTask(ENamedThreads::GameThread, [FlowNode]()
            {
                FlowNode->ContinueFlow();
            });
        });
    });

    Flow.QueueStep(TEXT("NotifyMainUI"), [this](FControlFlowNodeRef FlowNode, double Value)
    {
        OnInitFinished.Broadcast(true, TEXT("初始化完成"));
        FlowNode->ContinueFlow();
    });

    Flow.ExecuteFlow();
}
```

## 线程跳跃模式

每个 QueueStep 的回调在 GameThread 触发，内部通过 AsyncTask 切换到后台线程做耗时工作，完成后通过 AsyncTask 切回 GameThread 调用 ContinueFlow。

```
GameThread: QueueStep(InitLocalAsset)
    → AsyncTask(AnyThread) → 耗时工作 → AsyncTask(GameThread) → ContinueFlow
GameThread: QueueStep(InitNetInfo)
    → ... →
GameThread: QueueStep(NotifyMainUI)
```

## ManageTask 并行子任务

ControlFlows 管理串行步骤链，ManageTask 管理并行子任务组。

```cpp
struct FManageTask
{
    FString Name;
    TArray<FXGSubTask> SubTasks;
    EManageTaskStatus Status;
    FOnManageTaskComplete OnComplete;
};

void UXGControlFlowsSubsystem::InitManageTask()
{
    FManageTask& Task = ManageList.AddDefaulted_GetRef();
    Task.Status = EManageTaskStatus::Processing;

    for (int32 i = 0; i < 10; i++)
    {
        FXGSubTask& Sub = Task.SubTasks.AddDefaulted_GetRef();
        Sub.ID = FGuid::NewGuid();

        AsyncTask(ENamedThreads::AnyThread, [this, &Sub]()
        {
            FPlatformProcess::Sleep(1.0f);
            Sub.bFinished = true;
        });
    }
}
```

## Tick 轮询检测

通过 FTickableGameObject 使 Subsystem 每帧 Tick，检查 ManageList 中所有子任务是否完成。

```cpp
void UXGControlFlowsSubsystem::Tick(float DeltaTime)
{
    CheckManageTaskStatus();
}

void UXGControlFlowsSubsystem::CheckManageTaskStatus()
{
    for (auto It = ManageList.CreateIterator(); It; ++It)
    {
        if (It->Status != EManageTaskStatus::Processing)
            continue;

        bool bAllFinished = true;
        for (auto& Sub : It->SubTasks)
        {
            if (!Sub.bFinished)
            {
                bAllFinished = false;
                break;
            }
        }

        if (bAllFinished)
        {
            It->Status = EManageTaskStatus::AllComplete;
            It->OnComplete.ExecuteIfBound(true);
            It.RemoveCurrent();
        }
    }
}
```

关键原则：遍历 TMap 时不可原地删除，用迭代器 + RemoveCurrent 实现二次清理。

## 调试宏

```cpp
// 0 = 模拟失败, 1 = 模拟成功
#define XGCONCTROLRESULT 1

#if XGCONCTROLRESULT
    FlowNode->ContinueFlow();
#else
    FlowNode->CancelFlow();
#endif
```

## 依赖配置

```json
// .uproject Plugins 数组
{
    "Name": "ControlFlows",
    "Enabled": true
}
```

```csharp
// .Build.cs
PublicDependencyModuleNames.AddRange(
    new string[] { "Core", "CoreUObject", "Engine", "ControlFlows" });
```

## 代码入口

| 文件 | 说明 |
|------|------|
| [XGControlFlowsSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsSubsystem.h) | 子系统核心实现 |
| [XGControlFlowsActor.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsActor.h) | Actor 调用入口 |
