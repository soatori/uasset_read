# UObject 生命周期管理

本章的异步 Action 继承自 `UBlueprintAsyncActionBase`，其生命周期由 UE 的 GC 系统管理。若管理不当，会导致 HTTP 回调有时触发有时不触发。

## 问题现象

- HTTP 请求发送成功，但 `OnProcessRequestComplete` 回调不执行
- 回调"有时触发，有时不触发"
- 无明显报错日志

## 原因分析

`UBlueprintAsyncActionBase` 是 `UObject` 子类，受 UE GC 管理。当 Action 对象在执行异步操作期间被 GC 回收后，`BindUObject(this, ...)` 绑定的回调对象变为无效，HTTP 响应到达时无法触发委托。

## 解决方案

### 1. RegisterWithGameInstance

在工厂方法中调用 `RegisterWithGameInstance()`，将 AsyncAction 注册到 GameInstance 的 Root Set 中，防止 GC 回收：

```cpp
UXGSampleXFSilentBiopsyAyncAction* AsyncAction = NewObject<UXGSampleXFSilentBiopsyAyncAction>();
AsyncAction->AppID = InAppID;
// ... 设置其他参数
AsyncAction->RegisterWithGameInstance(WorldContextObject);
return AsyncAction;
```

代码见 [SilentBiopsyAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Private/AsyncAction/XGSampleXFSilentBiopsyAyncAction.cpp#L22-L37) L22-37 和 [PictureAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSamplePicture/Source/XGSamplePicture/Private/XGSamplePictureActionAction.cpp#L25-L39) L25-39。

### 2. Super::Activate()

覆盖 `Activate()` 时必须调用 `Super::Activate()`：

```cpp
void UXGSampleXFSilentBiopsyAyncAction::Activate()
{
    Super::Activate();  // 必须调用
    
    AsyncTask(ENamedThreads::GameThread, [this]() {
        this->Activate_Internal();
    });
    
    Then.Broadcast(AsyncID, false, TEXT("SilentBiopsy is just started"), RespInfo);
}
```

代码见 [SilentBiopsyAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Private/AsyncAction/XGSampleXFSilentBiopsyAyncAction.cpp#L39-L57)。

如果子类覆盖 `Activate()` 而忘记调用父类实现，`UBlueprintAsyncActionBase::Activate()` 内部的初始化逻辑不会执行，可能导致回调无法正常工作。这是课程开发过程中的一个实际 Bug。

### 3. SetReadyToDestroy()

资源释放函数末尾调用 `SetReadyToDestroy()`：

```cpp
void UXGSampleXFSilentBiopsyAyncAction::RealeaseResources()
{
    Then.Clear();
    OnSuccess.Clear();
    OnFail.Clear();
    // ... 重置其他成员
    
    SetReadyToDestroy();
}
```

代码见 [SilentBiopsyAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Private/AsyncAction/XGSampleXFSilentBiopsyAyncAction.cpp#L257-L281) L257-281。

`SetReadyToDestroy()` 标记该 UObject 可被销毁，不等同于立即销毁。真正的销毁由 GC 在下一次收集周期处理。不调用该函数会导致 UObject 泄漏。

### 4. 清空委托绑定

在 SilentBiopsy 的 `RealeaseResources()` 中额外调用了 `Then.Clear()`、`OnSuccess.Clear()`、`OnFail.Clear()`，防止委托持有对已销毁对象的引用导致崩溃。

### 5. 响应回调中的对象有效性

`OnHttpRespReceived()` 由 `BindUObject(this, ...)` 绑定，如果 Action 对象在 HTTP 请求周期内被 GC 回收，该回调不会执行。因此 `RegisterWithGameInstance` 是**必需的**而非可选的优化。

## 最佳实践总结

| 操作 | 位置 | 目的 |
|------|------|------|
| `RegisterWithGameInstance()` | 工厂方法末尾 | 防止 GC 回收 |
| `Super::Activate()` | Activate() 第一行 | 确保父类初始化 |
| `SetReadyToDestroy()` | RealeaseResources() 末尾 | 标记可销毁 |
| `Clear()` 委托 | 资源释放时 | 防止悬挂引用 |
