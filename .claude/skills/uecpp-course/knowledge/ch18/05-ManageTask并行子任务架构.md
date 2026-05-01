# ManageTask 并行子任务架构

## 概述

ManageTask 是课程自行实现的并行子任务管理系统，用于在一个 FControlFlow 步骤中创建 N 个并行执行的子任务，通过 Tick 轮询检测所有子任务的完成状态。当全部完成或被检测到失败时，通过委托回调通知 ControlFlow 推进或终止。

## 数据结构

### 子任务状态枚举

```cpp
enum class EXGControlFlowsTaskStatus : uint8
{
    None,       // 初始状态，未被处理
    Succeed,    // 子任务执行成功
    Failed,     // 子任务执行失败
    Max
};
```

### 管理任务状态枚举

```cpp
enum class EXGControlFlowsMangeTaskStatus : uint8
{
    None,       // 初始状态
    Succeed,    // 所有子任务都成功
    Failed,     // 至少一个子任务失败
    Processing, // 仍在等待子任务完成
    Max
};
```

### 子任务结构体

```cpp
struct FXGControlFlowsTask : public TSharedFromThis<FXGControlFlowsTask>
{
    FXGControlFlowsTask()
        : TaskID(FGuid::NewGuid())
        , BelongToManageTaskID(FGuid())
        , TaskStatus(EXGControlFlowsTaskStatus::None)
        , TaskMessage(TEXT("None"))
    {}

    FGuid TaskID;                       // 唯一标识，构造时自动生成
    FGuid BelongToManageTaskID;         // 所属管理任务的 ID
    EXGControlFlowsTaskStatus TaskStatus; // 当前状态
    FString TaskMessage;                // 附加消息（错误信息等）
};
```

### 管理任务结构体

```cpp
struct FXGControlFlowsManageTask : public TSharedFromThis<FXGControlFlowsManageTask>
{
    FXGControlFlowsManageTask()
        : ManageTaskID(FGuid::NewGuid())
        , MangeTaskStatus(EXGControlFlowsMangeTaskStatus::None)
        , ManagTaskMessage(TEXT("None"))
    {}

    FGuid ManageTaskID;                              // 唯一标识
    EXGControlFlowsMangeTaskStatus MangeTaskStatus;  // 当前状态
    FString ManagTaskMessage;                        // 汇总消息
    int32 TaskNum;                                   // 预期子任务数量（>=1）
    TArray<TSharedPtr<FXGControlFlowsTask>> Tasks;   // 子任务数组
    FXGControlFlowsManageTaskResponseResult ManageTaskResponse; // 完成回调委托
};
```

## 状态检测算法

`CheckManageTaskStatus()` 是核心检测函数，遍历所有子任务判断管理任务的状态：

```cpp
EXGControlFlowsMangeTaskStatus CheckManageTaskStatus()
{
    // 条件 1：子任务数量尚未达到预期 → Processing
    if (TaskNum != Tasks.Num())
    {
        MangeTaskStatus = EXGControlFlowsMangeTaskStatus::Processing;
        return MangeTaskStatus;
    }

    ManagTaskMessage = TEXT("");
    MangeTaskStatus = EXGControlFlowsMangeTaskStatus::Succeed;

    for (auto& TmpTask : Tasks)
    {
        // 条件 2：任一子任务失败 → Failed
        if (TmpTask->TaskStatus == EXGControlFlowsTaskStatus::Failed)
        {
            ManagTaskMessage += TEXT("Task Failed -Guid:") + TmpTask->TaskID.ToString()
                + TEXT("--TaskMessage:") + TmpTask->TaskMessage;
            MangeTaskStatus = EXGControlFlowsMangeTaskStatus::Failed;
        }

        // 条件 3：任一子任务仍为 None → Processing（立即返回）
        if (TmpTask->TaskStatus == EXGControlFlowsTaskStatus::None)
        {
            MangeTaskStatus = EXGControlFlowsMangeTaskStatus::Processing;
            return EXGControlFlowsMangeTaskStatus::Processing;
        }

        ManagTaskMessage += TEXT("\r\n--SubTaskID:") + TmpTask->TaskID.ToString()
            + TEXT("--TaskMessage:") + TmpTask->TaskMessage;
    }

    return MangeTaskStatus;
}
```

**状态判定逻辑**：

| 条件 | 结果状态 |
|------|----------|
| `Tasks.Num() < TaskNum`（尚未创建足够子任务） | Processing |
| 任一子任务状态为 `Failed` | Failed |
| 任一子任务状态为 `None`（尚未完成） | Processing |
| 全部子任务为 `Succeed` | Succeed |

**注意**：Failed 优先级高于 None。如果一个子任务失败而另一个尚未完成，状态为 Failed。

## 并行子任务创建（InitNetInfo）

```cpp
void UXGControlFlowsSubsystem::InitNetInfo(FControlFlowNodeRef SubFlow, double InProgreesValue)
{
    // 创建管理任务
    TSharedPtr<FXGControlFlowsManageTask> XGManageTaskPtr = MakeShared<FXGControlFlowsManageTask>();
    XGManageTaskPtr->TaskNum = 10;

    // 绑定管理任务完成回调
    XGManageTaskPtr->ManageTaskResponse.AddLambda([SubFlow, InProgreesValue, this](bool bResult, FString Message)
    {
        if (bResult)
        {
            CallInitProgress(InitAsyncID, InProgreesValue);
            SubFlow->ContinueFlow();
        }
        else
        {
            CallInitResult(InitAsyncID, bResult, Message);
            SubFlow->CancelFlow();
            bIniting = false;
            InitAsyncID = {};
        }
    });

    // 注册到 ManageList
    ManageList.Add(XGManageTaskPtr->ManageTaskID, XGManageTaskPtr);

    // 创建 10 个并行子任务
    for (size_t i = 0; i < 10; i++)
    {
        TSharedPtr<FXGControlFlowsTask> TaskPtr = MakeShared<FXGControlFlowsTask>();
        TaskPtr->BelongToManageTaskID = XGManageTaskPtr->ManageTaskID;
        FGuid ManageTaskID = TaskPtr->BelongToManageTaskID;
        FGuid TaskID = TaskPtr->TaskID;
        XGManageTaskPtr->Tasks.Add(TaskPtr);

        bool bSucceed = true;
        if (i == 6)
        {
            bSucceed = (XGCONCTROLRESULT != 0);  // 宏控制第 7 个子任务成败
        }

        // 子任务在 AnyThread 异步执行
        AsyncTask(ENamedThreads::AnyThread, [this, bSucceed, TaskID, i, ManageTaskID]()
        {
            FPlatformProcess::Sleep(i % 3);  // 不同子任务随机时长

            FString TaskMessage = FDateTime::Now().ToHttpDate();

            // 回 GameThread 更新状态
            AsyncTask(ENamedThreads::GameThread, [this, TaskID, ManageTaskID, bSucceed, TaskMessage]()
            {
                UpdateTaskStatus(TaskID, ManageTaskID, bSucceed, TaskMessage);
            });
        });
    }
}
```

## UpdateTaskStatus 实现

```cpp
void UXGControlFlowsSubsystem::UpdateTaskStatus(FGuid InTaskID, FGuid InManageTaskID, bool bResult, FString Message)
{
    TSharedPtr<FXGControlFlowsManageTask>* ManageTaskPtrPtr = ManageList.Find(InManageTaskID);

    if (ManageTaskPtrPtr)
    {
        for (auto& TmpTask : (*ManageTaskPtrPtr)->Tasks)
        {
            if (TmpTask->TaskID == InTaskID)
            {
                TmpTask->TaskStatus = bResult ? EXGControlFlowsTaskStatus::Succeed : EXGControlFlowsTaskStatus::Failed;
                TmpTask->TaskMessage = Message;
            }
        }
    }
}
```

通过 TMap 查找 ManageTask，再遍历其 Tasks 数组匹配 TaskID。更新后由 Tick 在下一帧检测状态变化。

## 完整工作流

```
InitNetInfo 调用
  ├─ 创建 FXGControlFlowsManageTask（TaskNum=10）
  ├─ 绑定 ManageTaskResponse 回调
  ├─ 加入 ManageList（TMap<FGuid, TSharedPtr>）
  └─ For 循环创建 10 个子任务
       └─ 每个子任务：
          AnyThread: Sleep(i % 3) → 耗时操作
                      ↓ AsyncTask(GameThread)
          GameThread: UpdateTaskStatus → 设置 TaskStatus
                      ↓ （本帧 Tick）
          Tick: CheckManageTaskStatus()
                ├─ 未完成 → 跳过，等待下一帧
                └─ 全部完成 → Broadcast ManageTaskResponse
                              ├─ 成功 → ContinueFlow + 广播进度
                              └─ 失败 → CancelFlow + 广播结果
```

## 设计要点

- **FGuid 唯一标识**：每个 ManageTask 和每个 Task 构造时自动生成 FGuid，无需手动管理
- **TMap 集中管理**：ManageList 持有所有活跃 ManageTask，便于 Tick 轮询和子任务 UpdateTaskStatus 查找
- **TSharedPtr 生命周期**：所有 Task 和 ManageTask 通过 TSharedPtr 管理，配合 TMap 保证引用有效性
- **宏控制失败模拟**：`XGCONCTROLRESULT` 在编译期决定第 7 个子任务的成败
- **延迟绑定**：Task 先创建，ManageTaskResponse 回调后绑定，不影响子任务并行执行

## 代码参考

- [XGControlFlowsSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsSubsystem.h) — 结构体定义（L20-L128）、ManageList 声明（L208）
- [XGControlFlowsSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsSubsystem.cpp) — InitNetInfo（L210-L320）、UpdateTaskStatus（L157-L181）

## 相关章节

- [06-Tick状态检测与资源清理](06-Tick状态检测与资源清理.md)
- [04-异步执行与线程跳跃模式](04-异步执行与线程跳跃模式.md)
