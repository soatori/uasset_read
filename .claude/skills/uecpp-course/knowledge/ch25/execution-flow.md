# Activate 执行流与回调线程切换

## 整体执行链路

```
蓝图调用 → 工厂函数（static）→ NewObject → RegisterWithGameInstance
    → Activate() → AsyncTask(下一帧) → Activate_Internal()
        → 实际工作（本地时间/HTTP请求）
    → 回调 → AsyncTask(GameThread) → 广播委托 → RealeaseResources()
```

## Activate()：错帧执行

```cpp
void UXGSampleHttpTimeAsyncAction::Activate()
{
    Super::Activate();
    AsyncTask(ENamedThreads::GameThread, [this]() {
        this->Activate_Internal();
    });

    FXGSampleNetTimeRespInfo RespInfo;
    Then.Broadcast(AsyncID, false,
        TEXT("UXGSampleHttpTimeAsyncAction is just started,please wait to be finished!"),
        RespInfo);
}
```

- `Activate()` 是 UE 蓝图异步节点的入口，在蓝图 VM 调用工厂函数后自动触发
- **核心设计**：使用 `AsyncTask(ENamedThreads::GameThread, ...)` 将 `Activate_Internal()` 推迟到**下一帧执行**
- **Then 引脚同步触发**：`Then.Broadcast()` 在 `Activate()` 内部同步调用，通知调用方"节点已启动"
- 此时 `Then` 引脚携带的是一个中间状态（`bResult = false`），告知调用方结果尚未到达

### 错帧执行的目的

| 场景 | 问题 | 错帧解决方案 |
|------|------|------------|
| 蓝图节点刚连接完就发送 HTTP | 嵌套请求或竞争条件导致回调丢失 | 等待一帧，确保节点完全初始化 |
| `RegisterWithGameInstance` 刚完成就触发回调 | GameInstance 引用尚未稳定 | 下一帧执行保证对象关系稳定 |
| 多个异步节点同时创建 | 回调交叉触发 | 错帧分散触发时序 |

错帧执行是一种"防御性设计"，在大规模异步系统中避免序依赖问题。

## Activate_Internal()：异步工作入口

```cpp
void UXGSampleHttpTimeAsyncAction::Activate_Internal()
{
    FString TimeServerURL = TEXT("");
    switch (NetTimeType)
    {
    case EXGSampleNetTimeType::Local:
        break;
    case EXGSampleNetTimeType::TaoBao:
        TimeServerURL = TEXT("https://api.m.taobao.com/rest/api3.do?api=mtop.common.getTimestamp");
        break;
    case EXGSampleNetTimeType::XGServer:
        TimeServerURL = TEXT("http://47.108.203.10:8036/NetTime");
        break;
    case EXGSampleNetTimeType::MaxNum:
    default:
        break;
    }

    if (!TimeServerURL.IsEmpty())
    {
        SendHttp(TimeServerURL);
        return;
    }

    // 本地时间模式：直接返回
    FXGSampleNetTimeRespInfo RespInfo;
    RespInfo.BeijingDateTime = FDateTime::Now();
    RespInfo.UTCDateTime = FDateTime::UtcNow();
    CallOnSuccess(AsyncID, true, TEXT("这是本地时间"), RespInfo);
    RealeaseResources();
}
```

- 根据用户选择的 `NetTimeType` 决定请求哪个时间服务器
- 有 URL → 调用 `SendHttp()` 发起 HTTP 请求
- 无 URL（Local 模式）→ 直接填充本地时间并通过 `CallOnSuccess` 返回

## 回调线程切换：CallOnSuccess / CallOnFail

```cpp
void UXGSampleHttpTimeAsyncAction::CallOnSuccess(
    FGuid InAsyncID, bool bInResult, FString InMessage,
    FXGSampleNetTimeRespInfo RespInfo)
{
    FXGSampleNetTimeDelegate TempDelegate = OnSuccess;

    AsyncTask(ENamedThreads::GameThread, [=]() {
        TempDelegate.Broadcast(InAsyncID, bInResult, InMessage, RespInfo);
    });
}
```

- **值拷贝捕获**：使用 `[=]`（值捕获），所有参数通过拷贝进入 Lambda
- `FXGSampleNetTimeDelegate` 是快照拷贝，即使 `OnSuccess` 在 Lambda 执行前被 `Clear()`，快照仍持有原始委托列表
- `AsyncTask(ENamedThreads::GameThread, ...)` 确保回调在 GameThread 上执行，因为蓝图委托只能在 GameThread 广播
- **线程安全**：HTTP 回调在后台线程触发，通过 `AsyncTask` 切回 GameThread

## RealeaseResources：清理与销毁

```cpp
void UXGSampleHttpTimeAsyncAction::RealeaseResources()
{
    Then.Clear();
    OnSuccess.Clear();
    OnFail.Clear();
    SetReadyToDestroy();
}
```

- 清除三个委托，防止回调在对象销毁后仍被触发
- `SetReadyToDestroy()` 通知 GC 此对象可被回收
- 此方法在异步操作完成后一定调用，在析构函数中作为兜底

> **代码位置**：[XGSampleHttpTime.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/025_HttpTime/XGSampleHttpTime.cpp) — Activate、Activate_Internal、CallOnSuccess/CallOnFail、RealeaseResources 完整实现
>
> **字幕位置**：025 第二十五章 003、004
