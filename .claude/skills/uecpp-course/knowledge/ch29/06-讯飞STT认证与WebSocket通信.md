# 讯飞 STT 认证与 WebSocket 通信

## 认证方式

讯飞实时语音识别（RTASR）的鉴权采用 **HMAC-SHA1 算法**，通过 WebSocket URL 的查询参数传递，而非 HTTP Header。

### GenerateRequireParams

```cpp
FString UXGSampleSTTSubsystem::GenerateRequireParams(const FString& InAppID, const FString& InAPIKey)
{
    // 1. 生成时间戳（秒级）
    FString Ts = FString::FromInt(FDateTime::UtcNow().ToUnixTimestamp());

    // 2. 生成签名（appid + ts 拼接，HMAC-SHA1 加密）
    FString Signa = FString::Printf(TEXT("%s%s"), *InAppID, *Ts);
    Signa = FBase64::Encode(FGenericPlatformHttp::GetUrlEncodedString(Signa));
    // ↑ 实际 HMAC-SHA1 计算后 Base64 + URLEncode

    // 3. 拼接 URL 参数
    return FString::Printf(TEXT("appid=%s&ts=%s&signa=%s"), *InAppID, *Ts, *Signa);
}
```

认证流程：
1. 拼接 `appid + ts` 字符串
2. 使用 **HMAC-SHA1** 加密（秘钥为 APIKey，消息为拼接后的字符串）
3. HMAC-SHA1 输出（20 字节）→ **Base64** 编码
4. Base64 结果 → **URL Encode**
5. 组装为 URL 查询参数：`appid={appid}&ts={ts}&signa={signa}`

### 完整 WebSocket URL

```
ws://rtasr.xfyun.cn/v1/ws?appid=xxxxx&ts=1234567890&signa=xxxxxxxxxxxx
```

## 通信协议

### 第一帧：发送空音频数据（触发识别）

WebSocket 连接建立后，需要先发送一帧空音频数据来启动服务器的识别引擎。这是讯飞 RTASR 协议的固定要求。

### 持续帧：实时音频数据

每帧包含一个 `status` 字段：

| status | 含义 |
|--------|------|
| 0 | 中间帧（识别中，持续发送） |
| 1 | 最后一帧（最后一段音频，停止后发送） |
| 2 | 无效/结束（服务器端使用） |

音频数据格式：**PCM S16LE**（16bit 有符号整型，小端字节序，单声道，16KHz）

### 结束帧

用户调用 `StopRealTimeSpeechToText` 时：
1. 发送 status=1 的最后一帧音频
2. 等待服务器返回最终识别结果
3. 收到服务器确认后关闭 WebSocket

## 009_WebSocketJson 协议模板

`code/009_WebSocketJson/` 目录提供各阶段 JSON 协议模板，用于参考：

### InitJson.txt — 初始化 JSON

```json
{
    "type": "ClientCallServerInit",
    "init": {
        "app_id": "appid",
        "ts": "xxxx"
    }
}
```

### MessJson.txt — 消息发送

```json
{
    "type": "ClientMessageToServer",
    "data": {
        "content": "xxxxxxxx"
    }
}
```

### TickJson.txt — 心跳请求

```json
{
    "type": "ClientCallTick",
    "tick": {
        "time": "xxxx"
    }
}
```

### ClientReqQuitJson.txt — 客户端退出请求

```json
{
    "type": "ClientReqQuit",
    "quit": {
        "time": "xxxx"
    }
}
```

> 这些协议模板是通用的 WebSocket JSON 通信参考，实际 STT 子系统使用二进制 PCM 数据发送（非 JSON 文本）。

## WebSocket 模块依赖

```cpp
// XGSampleXFLink.Build.cs
PublicDependencyModuleNames.AddRange(new string[] {
    "WebSockets",       // FWebSocketsModule, IWebSocket
    "Json",             // FJsonObject, FJsonObjectConverter
    "JsonUtilities",
    "AudioCapture",     // UAudioCaptureFunctionLibrary
});
```

关键 API：
- `FWebSocketsModule::Get().CreateWebSocket(URL)` — 创建 WebSocket 实例
- `IWebSocket::Connect()` — 异步连接
- `IWebSocket::Send(data, size, true)` — 发送二进制数据
- `IWebSocket::Send(text)` — 发送文本数据
- `IWebSocket::Close()` — 关闭连接
