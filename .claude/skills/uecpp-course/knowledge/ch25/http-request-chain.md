# 完整 HTTP 请求链路与 JSON 响应解析

## SendHttp：发起 HTTP 请求

```cpp
void UXGSampleHttpTimeAsyncAction::SendHttp(const FString& InServerURL)
{
    FHttpRequestRef Request = FHttpModule::Get().CreateRequest();

    Request->OnProcessRequestComplete().BindUObject(
        this,
        &UXGSampleHttpTimeAsyncAction::OnHttpRespReceived,
        AsyncID);

    Request->SetURL(InServerURL);
    Request->SetVerb("Post");
    Request->SetHeader("XGGuid", AsyncID.ToString());
    Request->SetHeader("Content-Type", "application/json");
    Request->SetContentAsString(TEXT(""));
    Request->ProcessRequest();
}
```

### FHttpModule 单例

`FHttpModule::Get()` 返回全局唯一的 Http 模块实例，通过 `CreateRequest()` 创建请求对象。返回的 `FHttpRequestRef` 是智能指针（`TSharedRef`），无需手动管理生命周期。

### 请求配置顺序

配置请求时需在 `ProcessRequest()` 之前完成所有设置：

| 步骤 | 方法 | 说明 |
|------|------|------|
| 1 | `SetURL()` | 设置请求目标地址 |
| 2 | `SetVerb()` | 设置请求方法（GET/POST/PUT/DELETE） |
| 3 | `SetHeader()` | 设置请求头键值对 |
| 4 | `SetContentAsString()` | 设置请求体字符串 |
| 5 | `ProcessRequest()` | 发起请求 |

### BindUObject 回调绑定

```cpp
Request->OnProcessRequestComplete().BindUObject(
    this,
    &UXGSampleHttpTimeAsyncAction::OnHttpRespReceived,
    AsyncID);
```

- `BindUObject(this, ...)`：自动处理对象生命周期，`this` 被销毁时自动取消绑定
- 额外参数传递：`BindUObject` 支持在回调签名基础上附加参数（此例中传递 `FGuid AsyncID`）

## OnHttpRespReceived：响应处理

```cpp
void UXGSampleHttpTimeAsyncAction::OnHttpRespReceived(
    FHttpRequestPtr HttpRequest,
    FHttpResponsePtr HttpResponse,
    bool bSucceeded,
    FGuid InAsyncID)
{
    // 三层验证
    if (bSucceeded &&
        HttpRequest->GetStatus() == EHttpRequestStatus::Succeeded &&
        HttpResponse->GetResponseCode() == 200)
    {
        // 处理成功响应
    }
    else
    {
        // 处理失败
    }
}
```

### 三层状态验证

| 层 | 检查项 | 说明 |
|----|--------|------|
| 1 | `bSucceeded` | 底层传输是否成功（TCP 连接是否建立） |
| 2 | `GetStatus() == Succeeded` | HTTP 请求状态是否完成 |
| 3 | `GetResponseCode() == 200` | HTTP 状态码是否为 200 |

**常见错误场景**：URL 拼写错误时 `HttpResponse` 为空指针（`nullptr`），访问空指针会导致崩溃。三层验证中 `bSucceeded` 为 `false` 时即提前退出，避免空指针访问。

### 请求-响应关联

两种方式将请求与响应关联：

1. **BindUObject 参数传递**：回调签名中直接携带 `FGuid InAsyncID`
2. **Header 追踪**：请求时设置 `SetHeader("XGGuid", AsyncID.ToString())`，响应时读取 `HttpRequest->GetHeader(TEXT("XGGuid"))`

在支持委托重载的 UE 版本中，方式 1 更简洁。Header 追踪方式兼容性更广，且支持在代理服务器日志中追踪请求链路。

## JSON 响应解析

```cpp
FString ResponseJson = HttpResponse->GetContentAsString();

FXGSampleNetTimeRespMessage RespMessage;
bool bParseJson = FJsonObjectConverter::JsonObjectStringToUStruct(
    ResponseJson, &RespMessage);

if (bParseJson)
{
    FString TickString = RespMessage.data.t;
    int64 TickTime = FCString::Atoi64(*TickString) / 1000;

    RespInfo.UTCDateTime = FDateTime::FromUnixTimestamp(TickTime);
    RespInfo.BeijingDateTime = FDateTime::FromUnixTimestamp(
        TickTime + 8 * 60 * 60);
    ...
}
```

### FJsonObjectConverter 反射解析

`FJsonObjectConverter::JsonObjectStringToUStruct()` 将 JSON 字符串直接解析为匹配的 USTRUCT 对象，无需手动逐个字段赋值。要求：

- USTRUCT 的字段名与 JSON 键名一致
- 嵌套结构体对应嵌套 JSON 对象
- `TArray<FString>` 对应 JSON 数组

### 时间戳处理流程

```
响应 JSON 中的 "t" 字段（毫秒级字符串）
    → FCString::Atoi64(*TickString) 转为 int64
    → / 1000 将毫秒转为秒
    → FDateTime::FromUnixTimestamp() 转为 FDateTime
    → + 8 * 60 * 60 偏移为北京时间（UTC+8）
```

- `FCString::Atoi64()`：将 `FString` 解析为 `int64`，处理大时间戳
- `FDateTime::FromUnixTimestamp(int64)`：将 Unix 时间戳（秒级）转为 UE 的 `FDateTime`
- **UTC+8 时区偏移**：`8 * 60 * 60` 秒 = 8 小时偏移量

## FHttpModule::Flush()：同步化 HTTP

```cpp
FHttpModule::Get().Flush();
```

`Flush()` 是阻塞调用，让 HttpManager 在**当前线程**进入等待状态直到请求完成。适用于需要顺序执行多个 HTTP 请求的场景（A 完成后 B 再开始），将异步模型同步化为线性执行流。

在 GameThread 调用 `Flush()` 会阻塞主线程，仅适合短请求或加载阶段的特殊场景。

## 流式传输

`FHttpRequest::OnRequestProgress` 提供了请求进度回调，可用于获取传输进度百分比。但不推荐使用 HTTP 做流式数据传输，流式场景应使用 WebSocket。

## 日志定义

```cpp
DEFINE_LOG_CATEGORY_STATIC(LogXGSampleNetTime, Display, All);
```

- `DEFINE_LOG_CATEGORY_STATIC`：定义仅在当前 .cpp 文件可见的日志类别
- `Display, All`：默认日志级别为 Display，最高捕获 All 级别
- 使用 `UE_LOG(LogXGSampleNetTime, Display, TEXT("..."))` 输出日志

> **代码位置**：[XGSampleHttpTime.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/025_HttpTime/XGSampleHttpTime.cpp) — SendHttp、OnHttpRespReceived、FHttpModule 调用完整实现
>
> **字幕位置**：025 第二十五章 004、005
