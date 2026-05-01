# WebSocket 通信详解

## 概述

UE 的 WebSocket 通信基于 WebSocketNetworking 模块（服务端）和 WebSockets 模块（客户端）。课程覆盖三个层次：语音识别 STT（客户端→第三方 WebSocket）、语音合成 TTS（客户端→第三方 WebSocket）、MMO 分布式服务器通信（客户端+服务端双角色）。

## 依赖配置

```csharp
// 客户端
PublicDependencyModuleNames.Add("WebSockets");

// 服务端
PublicDependencyModuleNames.Add("WebSocketNetworking");
```

## 客户端 WebSocket（WebSockets 模块）

### 连接与回调

```cpp
#include "WebSocketsModule.h"

TSharedPtr<IWebSocket> Socket = FWebSocketsModule::Get().CreateWebSocket(URL, Protocols);

Socket->OnConnected().AddLambda([]()
{
    UE_LOG(LogTemp, Log, TEXT("WebSocket Connected"));
});

Socket->OnConnectionError().AddLambda([](const FString& Error)
{
    UE_LOG(LogTemp, Error, TEXT("WebSocket Error: %s"), *Error);
});

Socket->OnMessage().AddLambda([](const FString& Message)
{
    UE_LOG(LogTemp, Log, TEXT("Received: %s"), *Message);
});

Socket->OnClosed().AddLambda([](int32 Status, const FString& Reason, bool bWasClean)
{
    UE_LOG(LogTemp, Log, TEXT("WebSocket Closed: %d %s"), Status, *Reason);
});

Socket->Connect();
```

### 发送消息

```cpp
// 文本
Socket->Send(JsonString);

// 二进制
TArray<uint8> BinaryData;
Socket->Send(BinaryData, true);
```

### 生命周期

```cpp
// 关闭
Socket->Close();
```

## 服务端 WebSocket（WebSocketNetworking 模块）

### 创建服务器

```cpp
#include "WebSocketNetworkingModule.h"

IWebSocketServer* Server = FModuleManager::LoadModuleChecked<
    IWebSocketNetworkingModule>("WebSocketNetworking").CreateWebSocketServer();

Server->Init(Port, Protocols, [](FWebSocketClient* Client)
{
    // 新连接回调
});

// Tick 驱动
void Tick(float DeltaTime)
{
    Server->Tick();
}
```

### 连接管理

```cpp
struct FXGWSMServerConnection
{
    FWebSocket* Socket;
    FGuid ConnectionID;
    FGuid ServerID;
    EConnectionStatus Status;
    double LastTickTime;
};

TMap<FGuid, FXGWSMServerConnection> ServerConnections;
```

### 心跳检测

```cpp
void TickServerConnections(float DeltaTime)
{
    // 遍历 Tick
    for (auto& Pair : ServerConnections)
    {
        if (Pair.Value.Status == EConnectionStatus::Tick)
        {
            // 超时检测
            if (FPlatformTime::Seconds() - Pair.Value.LastTickTime > 10.0f)
                Pair.Value.Status = EConnectionStatus::OutOfTime;
        }
    }

    // 二次清理
    for (auto It = ServerConnections.CreateIterator(); It; ++It)
    {
        if (It.Value().Status == EConnectionStatus::Quit
            || It.Value().Status == EConnectionStatus::OutOfTime)
            It.RemoveCurrent();
    }
}
```

## 消息协议

### 双 GUID 配对

```cpp
USTRUCT()
struct FXGWSMMessage
{
    GENERATED_BODY()

    UPROPERTY() EXGWSMActionType Action;
    UPROPERTY() int32 Code;
    UPROPERTY() FGuid ClientConnectionID;
    UPROPERTY() FGuid ServerConnectionID;
    UPROPERTY() FString MessageBody;
};
```

- `Code == 0` 成功，`Code != 0` 直接断开
- 双 GUID 在多连接场景下精准区分会话

### X 形关闭机制

```
客户端断开: ClientReqQuit → ServerAllowClientQuit → 客户端关闭
服务端断开: ServerReqQuit → ClientAllowServerQuit → 服务端关闭
```

## 音频采集与 WebSocket 结合（STT）

### 生产者-消费者模式

```
音频回调(OnAudioGenerate) → 存入缓冲区 → 消费线程(FRunnable)轮询
→ 重采样(48K→16K) → 格式转换(float→int16→uint8) → Socket->Send(Binary)
```

### 重采样算法

```cpp
// 48KHz → 16KHz：步进降采样（每 3 取 1）
// 44.1KHz → 16KHz：线性插值
float LinearResample(const TArray<float>& In, int32 OutIdx)
{
    float ResampleScale = 44100.0f / 16000.0f;
    float SrcPos = OutIdx * ResampleScale;
    int32 Idx0 = FMath::FloorToInt(SrcPos);
    int32 Idx1 = FMath::Min(Idx0 + 1, In.Num() - 1);
    float t = SrcPos - Idx0;
    return FMath::Lerp(In[Idx0], In[Idx1], t);
}
```

### 音频格式链路

```
float(-1.0~1.0) → clamp → *32767 → int16 → LSB + MSB → uint8[2]
```

## USoundWave 创建（TTS）

### 三种方式

```cpp
// 方式 1：RawPCMData（UE4 经典，已弃用）
SoundWave->RawPCMData = (uint8*)FMemory::Malloc(Data.Num());
FMemory::Memcpy(SoundWave->RawPCMData, Data.GetData(), Data.Num());

// 方式 2：RawData（UE5 推荐，次选）
SoundWave->RawData = FSharedBuffer::Clone(Data.GetData(), Data.Num());

// 方式 3：FSampleBuffer（UE5 原生，最终使用）
Audio::FSampleBuffer SampleBuffer(Data.GetData(), Data.Num() / 2, 1, 16000);
SoundWave->RawData = SampleBuffer.GetAsSharedBuffer();
```

## 完整 TTS 流程

```
Activate → 参数校验
→ CreateWebSocket(wss://...) → Connect
→ OnConnected → 构造三层嵌套 JSON → Send(JsonStr)
→ OnMessage → 解析 JSON → Base64 解码 → 累积音频
→ status==2(完成) → 创建 USoundWave → 回调蓝图
```

## 代码入口

| 文件 | 说明 |
|------|------|
| [XGSampleSTTSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Public/Subsystem/XGSampleSTTSubsystem.h) | STT 子系统 + 状态机 |
| [XGSampleAudioCaptureSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Public/Subsystem/XGSampleAudioCaptureSubsystem.h) | 音频采集子系统 |
| [XGSampleTTSAsyncAction.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Public/AsyncAction/XGSampleTTSAsyncAction.h) | TTS 异步节点 |
| [XGSampleWSM](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleWSM/) | MMO 分布式通信插件 |
