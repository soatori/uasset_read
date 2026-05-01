# Tick 状态检测与资源清理

## 概述

Subsystem 通过继承 `FTickableGameObject` 获得每帧 Tick 能力，在 Tick 中轮询所有活跃 ManageTask 的完成状态。当检测到管理任务完成（成功或失败）时，广播委托回调并清理已完成的 ManageTask。

## FTickableGameObject

### 声明

```cpp
UCLASS()
class XGSAMPLEDEMO_API UXGControlFlowsSubsystem : public UGameInstanceSubsystem, public FTickableGameObject
{
    GENERATED_BODY()

public:
    virtual void Tick(float DeltaTime) override;
    virtual bool IsTickable() const override;
    virtual TStatId GetStatId() const override;
};
```

### 接口实现

```cpp
bool UXGControlFlowsSubsystem::IsTickable() const
{
    return !IsTemplate();  // CDO 不 Tick
}

TStatId UXGControlFlowsSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UXGControlFlowsSubsystem, STATGROUP_Tickables);
}
```

- **IsTickable**：返回 `!IsTemplate()` 确保只在实例化对象上 Tick，CDO（Class Default Object）不参与
- **GetStatId**：返回统计 ID，用于性能分析器识别

## Tick 轮询逻辑

```cpp
void UXGControlFlowsSubsystem::Tick(float DeltaTime)
{
    TArray<FGuid> FinishManageTaskIDs;

    // 阶段 1：遍历所有活跃管理任务，检测完成状态
    for (auto& TmpManageTaskPair : ManageList)
    {
        // 跳过尚未达到预期子任务数量的管理任务
        if (TmpManageTaskPair.Value->TaskNum != TmpManageTaskPair.Value->Tasks.Num())
        {
            continue;
        }

        EXGControlFlowsMangeTaskStatus MangeTaskStatus =
            TmpManageTaskPair.Value->CheckManageTaskStatus();

        if (MangeTaskStatus == EXGControlFlowsMangeTaskStatus::Failed
            || MangeTaskStatus == EXGControlFlowsMangeTaskStatus::Succeed)
        {
            FinishManageTaskIDs.Add(TmpManageTaskPair.Key);
        }
    }

    // 阶段 2：广播已完成管理任务的回调
    for (auto& TmpManageTaskID : FinishManageTaskIDs)
    {
        TSharedPtr<FXGControlFlowsManageTask> XGManageTaskPtr = ManageList[TmpManageTaskID];

        bool bManageTaskResult =
            XGManageTaskPtr->MangeTaskStatus == EXGControlFlowsMangeTaskStatus::Succeed;

        XGManageTaskPtr->ManageTaskResponse.Broadcast(bManageTaskResult,
            XGManageTaskPtr->ManagTaskMessage);
    }

    // 阶段 3：从 ManageList 中移除已完成的管理任务
    for (auto& TmpManageTaskID : FinishManageTaskIDs)
    {
        ManageList.Remove(TmpManageTaskID);
    }
}
```

**三段式结构**：

| 阶段 | 操作 | 说明 |
|------|------|------|
| 1. 检测 | 遍历 ManageList，调用 CheckManageTaskStatus() | 收集已完成的 ManageTask ID |
| 2. 广播 | 遍历完成列表，广播 ManageTaskResponse | 通知回调方（ControlFlow Continue/Cancel） |
| 3. 清理 | 从 ManageList 中移除 | 释放资源，管理任务生命周期结束 |

**设计要点**：

- **三遍循环分离**：检测和广播分离，避免在遍历 ManageList 时触发回调修改容器
- **条件跳过**：`TaskNum != Tasks.Num()` 跳过尚未创建足够子任务的管理任务
- **统一删除**：广播完成后统一清理，防止回调中对 ManageList 的并发修改

## 管理任务生命周期

```
创建（InitNetInfo）
  │  ManageList.Add(ManageTaskID, Ptr)
  ▼
等待（Tick 多帧轮询）
  │  CheckManageTaskStatus() → Processing
  ▼
完成（Tick 单帧）
  │  CheckManageTaskStatus() → Succeed/Failed
  │  → Broadcast ManageTaskResponse
  │  → ManageList.Remove(ManageTaskID)
  ▼
销毁（TSharedPtr 引用归零）
```

## 常见 Bug 与修复

### Bug 1：FGuid 未初始化

**问题**：`FXGControlFlowsTask` 的 `TaskID` 未调用 `FGuid::NewGuid()`，导致所有子任务的 GUID 为全零。

**修复**：在构造函数中显式初始化：

```cpp
FXGControlFlowsTask()
    : TaskID(FGuid::NewGuid()), ...
{}
```

### Bug 2：ManageTaskStatus 未初始化

**问题**：`FXGControlFlowsManageTask::MangeTaskStatus` 未显式初始化，默认值取决于内存分配状态。

**修复**：在构造函数中设置为 `None`：

```cpp
FXGControlFlowsManageTask()
    : MangeTaskStatus(EXGControlFlowsMangeTaskStatus::None), ...
{}
```

### Bug 3：CheckManageTaskStatus 默认返回 Processing

**问题**：子任务默认状态为 `None`，而 `CheckManageTaskStatus` 中将 `None` 视为仍在处理中，导致状态检测永远不返回 Succeed。

**修复（代码层面）**：

1. 子任务创建后，其 `TaskStatus` 保持 `None`
2. 子任务完成时，`UpdateTaskStatus` 将其设置为 `Succeed` 或 `Failed`
3. `CheckManageTaskStatus` 正确区分 `None`（未完成）与 `Succeed/Failed`（已完成）

**实际代码中的正确状态**：
- 初始：`TaskStatus = None`（表示未处理）
- 完成：`TaskStatus = Succeed/Failed`
- 检测：`None` → Processing，`Succeed` → 继续检查，`Failed` → 标记 Failed

## 代码参考

- [XGControlFlowsSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsSubsystem.h) — FTickableGameObject 声明（L136, L153-L157）、ManageList（L208）
- [XGControlFlowsSubsystem.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/021_ControlFlows/XGControlFlowsSubsystem.cpp) — Tick（L38-L84）、IsTickable（L86-L89）、GetStatId（L91-L94）

## 相关章节

- [05-ManageTask并行子任务架构](05-ManageTask并行子任务架构.md)
- [04-异步执行与线程跳跃模式](04-异步执行与线程跳跃模式.md)
