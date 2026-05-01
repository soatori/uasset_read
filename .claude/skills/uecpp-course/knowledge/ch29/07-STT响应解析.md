# STT 响应解析

## 消息格式

讯飞 RTASR 服务器通过 WebSocket `OnMessage` 回调返回 JSON 文本：

```json
{
    "action": "started",     // 或 "result", "error"
    "code": "0",             // "0" 成功，非 0 失败
    "data": "识别文本内容",
    "desc": "描述信息"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| action | string | 动作类型：started / result / error |
| code | string | 状态码："0" 成功 |
| data | string | 识别结果文本 |
| desc | string | 额外描述信息 |

## 响应类型

### started（启动确认）

服务器收到第一帧数据后返回，表示识别引擎已启动：

```json
{
    "action": "started",
    "code": "0",
    "data": "",
    "desc": ""
}
```

此时可以继续发送音频帧。

### result（识别结果）

服务器返回实时识别结果：

```json
{
    "action": "result",
    "code": "0",
    "data": "今天天气怎么样",
    "desc": ""
}
```

`data` 字段包含已识别的文本，可能为空字符串（服务器尚未识别出有效语音）。

### error（错误通知）

```json
{
    "action": "error",
    "code": "10105",
    "data": "",
    "desc": "引擎繁忙"
}
```

常见错误码：

| 错误码 | 说明 |
|--------|------|
| 10105 | 引擎繁忙（并发超限） |
| 10106 | 授权失败（appid/key 校验未通过） |
| 10313 | 音频参数不合规（采样率/格式错误） |
| 10316 | 音频帧异常 |
| 10400 | 参数错误 |

## 解析实现

```cpp
void UXGSampleSTTSubsystem::OnWebSocketMessage(const FString& InStr)
{
    // 解析 JSON
    TSharedPtr<FJsonObject> JsonObj;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(InStr);
    if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
        return;

    // 提取字段
    FString Action = JsonObj->GetStringField(TEXT("action"));
    FString Code = JsonObj->GetStringField(TEXT("code"));
    FString MsgData = JsonObj->GetStringField(TEXT("data"));
    FString Desc;

    // desc 字段可能没有，需要判断
    if (JsonObj->HasField(TEXT("desc")))
        Desc = JsonObj->GetStringField(TEXT("desc"));

    // 回调蓝图
    if (Action == TEXT("result") && Code == TEXT("0"))
    {
        // 识别成功，回调识别结果
        CallRealTimeSTTRespDelegate(true, MsgData);
    }
    else if (Action == TEXT("error"))
    {
        // 识别错误
        CallRealTimeSTTRespDelegate(false, FString::Printf(TEXT("[%s]%s"), *Code, *Desc));
    }
    // started 仅做日志记录，不回调蓝图
}
```

## 回调至蓝图

解析结果通过动态多播委托传递到蓝图：

```cpp
void UXGSampleSTTSubsystem::CallRealTimeSTTRespDelegate(bool bSuccess, const FString& RespContent)
{
    if (OnSTTInitDelegate.IsBound())
    {
        OnSTTInitDelegate.Execute(bSuccess, RespContent);
    }
}
```

三个独立的委托对应三种回调场景：

| 委托 | 触发时机 | 参数说明 |
|------|---------|---------|
| `FXGSampleInitSTTDelegate` | WebSocket 连接成功/失败 | 是否成功 |
| `FXGSampleSTTRespDelegate` | 收到识别结果或错误 | 是否成功 + 文本内容 |
| `FXGSampleSTTCloseDelegate` | WebSocket 关闭 | 无参数 |
