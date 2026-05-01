# 讯飞 TTS 认证与 WebSocket 通信

## 认证方式

TTS 使用 **HMAC-SHA256** 鉴权，通过 `AssembleAuthUrl` 生成带签名的 WebSocket URL。与第二十七章 HTTP 的 URL 签名类似，但输出为 WebSocket URL 而非 HTTP URL。

### AssembleAuthUrl

```cpp
FString AssembleAuthUrl(const FString& InAppID, const FString& InAPISecret, const FString& InAPIKey)
{
    // 1. 获取当前 GMT 时间
    FString GMTTime = GetGMTTime(); // e.g. "Thu, 01 Dec 2024 00:00:00 GMT"

    // 2. 拼接签名原文字符串
    FString SignatureOrigin = FString::Printf(TEXT("host: tts-api.xfyun.cn\ndate: %s\nGET /v2/tts HTTP/1.1"), *GMTTime);

    // 3. HMAC-SHA256 加密
    TArray<uint8> HMACOutput;
    // HMAC-SHA256(InAPISecret, SignatureOrigin) → HMACOutput (32 bytes)

    // 4. Base64 编码签名
    FString SignatureBase64 = FBase64::Encode(HMACOutput);

    // 5. 拼接 Authorization
    FString Authorization = FString::Printf(
        TEXT("api_key=\"%s\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"%s\""),
        *InAPIKey, *SignatureBase64
    );

    // 6. URL Encode
    FString EncodedAuthorization = FGenericPlatformHttp::UrlEncode(Authorization);

    // 7. 组装完整 URL
    return FString::Printf(TEXT("ws://tts-api.xfyun.cn/v2/tts?authorization=%s&date=%s&host=tts-api.xfyun.cn"),
        *EncodedAuthorization, *GenericPlatformHttp::UrlEncode(GMTTime));
}
```

认证流程：
1. 获取 GMT 时间字符串
2. 拼接签名原文：`host: tts-api.xfyun.cn\ndate: {GMT}\nGET /v2/tts HTTP/1.1`
3. 使用 API Secret 对原文进行 **HMAC-SHA256**（输出 32 字节）
4. HMAC 输出 → **Base64** 编码
5. 拼接待权头：`api_key="xxx", algorithm="hmac-sha256", headers="host date request-line", signature="xxxx"`
6. 对 Authorization 字符串进行 **URL Encode**
7. 组装完整 WebSocket URL

### 完整 URL 示例

```
ws://tts-api.xfyun.cn/v2/tts?authorization=api_key%3Dxxx%2C...&date=Thu%2C+...&host=tts-api.xfyun.cn
```

## WebSocket 通信

### 创建连接

```cpp
void UXGSampleTTSAsyncAction::CreateWebSocket()
{
    FString AuthURL = AssembleAuthUrl(InAppID, InAPISecret, InAPIKey);
    Socket = FWebSocketsModule::Get().CreateWebSocket(AuthURL);

    Socket->OnConnected().AddUObject(this, &UXGSampleTTSAsyncAction::OnWebSocketConnected);
    Socket->OnConnectionError().AddUObject(this, &UXGSampleTTSAsyncAction::OnWebSocketConnectionError);
    Socket->OnClosed().AddUObject(this, &UXGSampleTTSAsyncAction::OnWebSocketClosed);
    Socket->OnMessage().AddUObject(this, &UXGSampleTTSAsyncAction::OnWebSocketMessage);

    Socket->Connect();
}
```

### OnConnected — 发送 JSON 请求

连接成功后，通过 `FJsonObjectConverter::UStructToJsonObjectString` 将请求参数序列化为 JSON 文本发送：

```cpp
void UXGSampleTTSAsyncAction::OnWebSocketConnected(const FString& InStr)
{
    FXGXunFeiTTSReqInfo ReqInfo;
    ReqInfo.common.app_id = InAppID;
    // ... 填充 business/data 字段 ...

    FString JsonStr;
    FJsonObjectConverter::UStructToJsonObjectString(ReqInfo, JsonStr);
    Socket->Send(JsonStr);
}
```

### OnMessage — 接收音频数据

```cpp
void UXGSampleTTSAsyncAction::OnWebSocketMessage(const FString& InStr)
{
    // 解析 JSON
    FXGXunFeiTTSRespInfo RespInfo;
    if (!FJsonObjectConverter::JsonObjectStringToUStruct(InStr, &RespInfo))
    {
        OnSoundWaveFail.Broadcast(TEXT("响应解析失败"));
        RealeaseResources();
        return;
    }

    // 检查状态码
    if (RespInfo.code != 0)
    {
        OnSoundWaveFail.Broadcast(FString::Printf(TEXT("服务器错误: %d %s"), RespInfo.code, *RespInfo.message));
        RealeaseResources();
        return;
    }

    // Base64 解码音频数据
    TArray<uint8> AudioChunk;
    FBase64::Decode(RespInfo.data.audio, AudioChunk);
    AllAudioData.Append(AudioChunk);

    // 检查是否为最后一帧
    if (RespInfo.data.status == 2)
    {
        // 所有音频数据接收完成
        ProcessCompleteAudio();
    }
}
```

### 通信流程

```
客户端 → 服务器：JSON 请求（含 Base64 文本）
    {
        "common": { "app_id": "xxx" },
        "business": { "aue": "raw", "vcn": "xiaoyan", ... },
        "data": { "text": "5Lit5Zu95Lq65rCR", "status": 2 }
    }

服务器 → 客户端：JSON 响应（含 Base64 音频）
    {
        "code": 0,
        "message": "success",
        "data": { "audio": "//uQxAAA...", "status": 2, "ced": "xxx" }
    }
```

由于 TTS 是"文本→音频"的转换，通常服务器一次返回所有数据（`status=2`），不会像 STT 那样分多次返回中间帧。
