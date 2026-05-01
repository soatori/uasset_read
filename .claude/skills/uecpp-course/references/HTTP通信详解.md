# HTTP 通信详解

## 概述

UE 的 HTTP 通信基于 FHttpModule 模块，提供异步非阻塞的 HTTP 请求能力。课程覆盖 HTTP GET/POST、HTTPS、文件上传、流式传输四个层次，以及与 UBlueprintAsyncActionBase 结合的异步蓝图节点模式。

## FHttpModule 基础

### 依赖配置

```csharp
PublicDependencyModuleNames.Add("Http");
```

### 请求五步配置

```cpp
TSharedRef<IHttpRequest> Request = FHttpModule::Get().CreateRequest();

Request->SetURL(TEXT("https://api.example.com/time"));
Request->SetVerb(TEXT("GET"));
Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
Request->SetContentAsString(JsonBody);
Request->ProcessRequest();
```

### 响应回调

```cpp
Request->OnProcessRequestComplete().BindLambda([](
    FHttpRequestPtr HttpRequest,
    FHttpResponsePtr HttpResponse,
    bool bSucceeded)
{
    // 三层验证
    if (bSucceeded
        && HttpRequest->GetStatus() == EHttpRequestStatus::Succeeded
        && HttpResponse->GetResponseCode() == 200)
    {
        FString Response = HttpResponse->GetContentAsString();
    }
});
```

| 验证层 | 检查内容 |
|--------|---------|
| 第一层 | `bSucceeded` — 底层传输是否成功 |
| 第二层 | `GetStatus() == Succeeded` — HTTP 请求状态 |
| 第三层 | `GetResponseCode() == 200` — HTTP 状态码 |

### 阻塞等待

```cpp
// 将异步请求同步化
FHttpModule::Get().Flush();
```

## UBlueprintAsyncActionBase 异步节点模式

### 节点声明

```cpp
UCLASS(meta = (HideThen = true))
class UXGSampleHttpTime : public UBlueprintAsyncActionBase
{
    GENERATED_BODY()

    DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FXGSampleHttpTimeDelegate,
        FGuid, AsyncID, bool, bResult, FString, Message, float, TimeValue);

    UPROPERTY(BlueprintAssignable)
    FXGSampleHttpTimeDelegate Then;

    UPROPERTY(BlueprintAssignable)
    FXGSampleHttpTimeDelegate OnSuccess;

    UPROPERTY(BlueprintAssignable)
    FXGSampleHttpTimeDelegate OnFail;

    UFUNCTION(BlueprintCallable,
        meta = (BlueprintInternalUseOnly = "true",
                WorldContext = "WorldContextObject"),
        Category = "XGSample")
    static UXGSampleHttpTime* XGSampleHttpTime(
        UObject* WorldContextObject);
};
```

### 工厂函数与生命周期

```cpp
UXGSampleHttpTime* UXGSampleHttpTime::XGSampleHttpTime(
    UObject* WorldContextObject)
{
    UXGSampleHttpTime* Node = NewObject<UXGSampleHttpTime>();
    Node->RegisterWithGameInstance(WorldContextObject);
    return Node;
}
```

### 错帧执行

```cpp
void UXGSampleHttpTime::Activate()
{
    Super::Activate();

    // 延迟一帧确保蓝图引脚绑定完成
    AsyncTask(ENamedThreads::GameThread, [this]()
    {
        Activate_Internal();
    });

    Then.Broadcast(AsyncID, false, TEXT("开始获取时间..."), 0.0f);
}
```

### JSON 反射解析

```cpp
// USTRUCT 定义
USTRUCT()
struct FTimeResponse
{
    GENERATED_BODY()
    UPROPERTY() FString dateTime;
    UPROPERTY() int64 timestamp;
};

// 解析
FTimeResponse Response;
FJsonObjectConverter::JsonObjectStringToUStruct(
    HttpResponse->GetContentAsString(), &Response);
```

## 摄像头活体检测（HTTP POST + 文件上传）

### RenderTarget 转 PNG

```cpp
// 读取像素
FTextureRenderTargetResource* RTResource = RenderTarget->GameThread_GetRenderTargetResource();
FReadSurfaceDataFlags ReadPixelFlags(RCM_UNorm);
TArray<FColor> Pixels;
RTResource->ReadPixels(Pixels, ReadPixelFlags);

// Alpha 修正
for (auto& Color : Pixels)
    Color.A = 255 - Color.A;

// 异步 PNG 压缩
AsyncTask(ENamedThreads::AnyThread, [Pixels, this]()
{
    TArray<uint8> PNGData;
    FImageUtils::PNGCompressImageArray(Width, Height, Pixels, PNGData);

    AsyncTask(ENamedThreads::GameThread, [PNGData, this]()
    {
        OnCaptureComplete.Broadcast(PNGData);
    });
});
```

### HMAC-SHA256 鉴权

```cpp
// 百度 AKSK 签名模式
FString GenerateAuthHeader(const FString& SecretKey)
{
    // HMAC-SHA256 签名 → Base64 编码 → Header 添加
    return FBase64::Encode(HMAC_SHA256(SecretKey, SignString));
}
```

## 流式传输（大模型通信）

### 流式绑定

```cpp
// 非流式
Request->OnProcessRequestComplete().BindUObject(this, &UXGSampleBDLink::OnComplete);

// 流式 — Asynchronous Stream Response
Request->OnRequestProgress().BindUObject(this, &UXGSampleBDLink::OnStreamData);
```

### SSE 分隔符解析

```cpp
void UXGSampleBDLink::OnStreamData(
    FHttpRequestPtr Request, int32 BytesSent, int32 BytesReceived)
{
    FString Response = Request->GetResponse()->GetContentAsString();

    // SSE 格式：\n\n 分隔每个 token
    TArray<FString> Tokens;
    Response.ParseIntoArray(Tokens, TEXT("\n\n"), true);

    for (auto& Token : Tokens)
    {
        if (!Token.IsEmpty())
        {
            OnUpdate.Broadcast(AsyncID, true, Token, RespInfo);
        }
    }
}
```

### 手动 JSON 构建

当 FJsonObjectConverter 无法处理条件性字段时，使用 TJsonWriter 手动构建：

```cpp
void FBDReqUtil::Serialize(TSharedRef<FJsonObject> Root)
{
    // FString: 空或 "None" 时跳过
    // int32: -1 时跳过
    // float: -1.0f 时跳过
    // bool: 始终写入
}
```

## POST 文件上传流程

```
1. 采集数据 → 2. Base64 编码 → 3. 构造 JSON 请求体
→ 4. 鉴权签名 → 5. HTTP POST → 6. 响应解析
```

## JSON 序列化与反序列化

UE 提供三种 JSON 操作方式，按场景选用：

### TJsonWriter 手动构建

适用：需要条件性跳过字段、序列化顺序控制

```cpp
FString SerializeCustom()
{
    TSharedRef<TJsonWriter<TCHAR>> Writer = TJsonWriterFactory<TCHAR>::Create(&OutString);
    Writer->WriteObjectStart();
    Writer->WriteValue("name", "Alice");
    Writer->WriteValue("age", 25);
    if (bHasExtra)
        Writer->WriteValue("extra", ExtraData);
    Writer->WriteObjectEnd();
    Writer->Close();
    return OutString;
}
```

### TJsonReader 手动解析

适用：响应结构已知但无 USTRUCT 映射

```cpp
void ParseManual(const FString& Json)
{
    TSharedRef<TJsonReader<TCHAR>> Reader = TJsonReaderFactory<TCHAR>::Create(Json);
    TSharedPtr<FJsonObject> Root;
    FJsonSerializer::Deserialize(Reader, Root);

    FString Name = Root->GetStringField("name");
    int32 Age = Root->GetIntegerField("age");

    // 嵌套对象
    TSharedPtr<FJsonObject> Nested = Root->GetObjectField("data");
}
```

### FJsonObjectConverter 反射转换

适用：响应结构与 USTRUCT 一一对应

```cpp
USTRUCT()
struct FTimeResponse
{
    GENERATED_BODY()
    UPROPERTY() FString dateTime;
    UPROPERTY() int64 timestamp;
};

// 反序列化（一行代码完成反射映射）
FTimeResponse Response;
FJsonObjectConverter::JsonObjectStringToUStruct(
    HttpResponse->GetContentAsString(), &Response);

// 序列化
FString JsonOut;
FJsonObjectConverter::UStructToJsonObjectString(Response, JsonOut);
```

### 三种写法对比

| 方式 | 类型安全 | 动态字段 | 性能 | 适用场景 |
|------|---------|---------|------|---------|
| TJsonWriter | 手动控制 | 支持跳过 | 中等 | 请求体构建（条件性字段） |
| TJsonReader | 手动取值 | 支持缺失 | 中等 | 无 USTRUCT 的响应解析 |
| FJsonObjectConverter | 自动映射 | 不支持 | 快 | 标准 REST API 响应解析 |

## 代码入口

| 文件 | 说明 |
|------|------|
| [XGSampleHttpTime.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/025_HttpTime/XGSampleHttpTime.h) | HTTP 基础异步节点 |
| [XGSamplePictureActionAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSamplePicture/Source/XGSamplePicture/Private/XGSamplePictureActionAction.cpp) | 图片上传异步节点 |
| [XGSampleBDReqType.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/Type/XGSampleBDReqType.cpp) | 手动 JSON 构建工厂 |
| [XGSampleBDRespType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Public/Type/XGSampleBDRespType.h) | 百度 ERNIE Bot 响应类型 |
| [XGJsonWriterTest.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGJsonWriterTest.h) | TJsonWriter 手动构建 |
| [XGJsonReaderTest.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGJsonReaderTest.h) | TJsonReader 手动解析 |
| [XGJsonConverterTest.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGJsonConverterTest.h) | FJsonObjectConverter 反射转换 |
