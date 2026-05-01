# STT 子系统与状态机

## 子系统注册

`UXGSampleSTTSubsystem` 继承自 `UGameInstanceSubsystem`，由引擎自动创建和销毁：

```cpp
// XGSampleSTTSubsystem.h
UCLASS()
class XGSAMPLEXFLINK_API UXGSampleSTTSubsystem : public UGameInstanceSubsystem
{
    // ...
};
```

子系统通过静态指针 `RealTimeSTTSubsystemPtr` 暴露自身，供消费线程跨模块访问：

```cpp
static TSoftClassPtr<UXGSampleSTTSubsystem> RealTimeSTTSubsystemPtr;
```

## 状态机

使用 `EXGSampleSTTStatus` 枚举管理 WebSocket 连接生命周期：

| 状态 | 含义 | 触发时机 |
|------|------|---------|
| Ready | 空闲/就绪 | 初始状态，或资源释放完成后 |
| Init | 初始化中 | `BeginRealTimeSpeechToText` 被调用后，WebSocket 连接建立前 |
| WaitToServerClose | 等待服务器关闭 | 用户停止识别后，发送结束帧等待服务器确认关闭 |

状态转换：

```
Ready → Init: XGBeginRealTimeSpeechToText 调用
Init → Ready: 连接失败（OnConnectionError）
Init → (WebSocket 已连接): Connected 回调
(Streaming) → WaitToServerClose: XGStopRealTimeSpeechToText 调用
WaitToServerClose → Ready: WebSocket 关闭（OnClosed）
任意状态 → Ready: ForceToStop 强制清理
```

## WebSocket 生命周期

### 创建连接

```cpp
void UXGSampleSTTSubsystem::CreateWebSocket(const FString& InAppID, const FString& InAPIKey)
{
    FString WebSocketURL = FString::Printf(TEXT("ws://rtasr.xfyun.cn/v1/ws?%s"), *GenerateRequireParams(InAppID, InAPIKey));
    Socket = FWebSocketsModule::Get().CreateWebSocket(WebSocketURL);
    Socket->OnConnected().AddUObject(this, &UXGSampleSTTSubsystem::OnWebSocketConnected);
    Socket->OnConnectionError().AddUObject(this, &UXGSampleSTTSubsystem::OnWebSocketConnectionError);
    Socket->OnClosed().AddUObject(this, &UXGSampleSTTSubsystem::OnWebSocketClosed);
    Socket->OnMessage().AddUObject(this, &UXGSampleSTTSubsystem::OnWebSocketMessage);
    Socket->OnMessageSent().AddUObject(this, &UXGSampleSTTSubsystem::OnWebSocketMessageSent);
    Socket->Connect();  // 非阻塞，异步连接
}
```

### 五个回调

**OnConnected**（游戏线程回调）
- 调用 `AsyncTask(ENamedThreads::GameThread, ...)` 确保在游戏线程执行
- 设置 STTStatus = Init
- 回调 `OnInitRealTimeSTTDelegate`（告诉蓝图连接成功）
- 启动音频采集和消费线程

**OnConnectionError**
- 同样通过 `AsyncTask` 回到游戏线程
- 调用 `CallInitRealTimeSTTDelegate(false)` 通知失败
- 清理资源

**OnClosed**
- 调用 `CallRealTimeSTTCloseDelegate` 通知蓝图关闭
- 设置状态回到 Ready

**OnMessage**
- 解析服务器返回的 JSON 文本
- 提取识别结果或错误信息
- 调用 `CallRealTimeSTTRespDelegate` 回调蓝图

**OnMessageSent**
- 记录发送状态，仅用于日志/跟踪

## 资源释放链

```cpp
void UXGSampleSTTSubsystem::RealeaseWebSocketAllInfoForSTT()
{
    RealeaseVoiceGenerateRunnale();     // 停止音频采集
    RealeaseVoiceConsumeRunnable();     // 停止消费线程
    EndSendVoiceData();                 // 标记停止发送
    RealeaseWebSocket();                // 关闭 WebSocket
    RealeaseSTTInfo();                  // 清空 STT 信息
    RealTimeSTTSubsystemPtr = nullptr;  // 清除指针
}
```

资源释放顺序严格：**先停数据源，再停线程，最后关连接**，避免竞态条件。

## 跨线程安全

所有 WebSocket 回调通过 `AsyncTask(ENamedThreads::GameThread, ...)` 回到游戏线程再执行，防止多线程竞争：

```cpp
void UXGSampleSTTSubsystem::OnWebSocketConnected(const FString& InStr)
{
    AsyncTask(ENamedThreads::GameThread, [this, InStr]()
    {
        // 安全地在游戏线程操作
    });
}
```
