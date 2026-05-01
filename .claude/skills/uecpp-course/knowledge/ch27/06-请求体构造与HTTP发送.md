# 请求体构造与 HTTP 发送

## 请求体结构

科大讯飞静默活体检测 API 的请求体为 JSON 格式，包含三个顶层对象：`header`、`parameter`、`payload`。

代码见 [XGSampleXFSilentBiopsyReqType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Public/Type/SilentBiopsy/XGSampleXFSilentBiopsyReqType.h#L115-L132) 和 [SilentBiopsyAsyncAction.cpp Activate_Internal()](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Private/AsyncAction/XGSampleXFSilentBiopsyAyncAction.cpp#L59-L98)。

### 结构体层级

```
FXGSampleXFSilentBiopsyReqInfo
├── header: FXGSampleXFSilentBiopsyReqHeaderInfo
│   ├── app_id: FString          ← 讯飞 AppID
│   └── status: int32 = 3       ← 单次请求固定为 3
├── parameter: FXGSampleXFSilentBiopsyReqParameterInfo
│   └── s67c9c78c: FXGSampleXFSilentBiopsyReqParameterS67c9c78cInfo
│       ├── service_kind: "anti_spoof"
│       └── anti_spoof_result: FXGSampleXFSilentBiopsyReqParameterAntiSpoofResultInfo
│           ├── encoding: "utf8"
│           ├── compress: "raw"
│           └── format: "json"
└── payload: FXGSampleXFSilentBiopsyReqPayloadInfo
    └── input1: FXGSampleXFBiopsyReqPayloadInputInfo
        ├── encoding: FString    ← 图片类型（jpg/jpeg/png/bmp）
        ├── status: int32 = 3
        └── image: FString       ← Base64 编码后的图片二进制数据
```

### 生成的 JSON 示例

```json
{
    "header": {
        "app_id": "your_app_id",
        "status": 3
    },
    "parameter": {
        "s67c9c78c": {
            "service_kind": "anti_spoof",
            "anti_spoof_result": {
                "encoding": "utf8",
                "compress": "raw",
                "format": "json"
            }
        }
    },
    "payload": {
        "input1": {
            "encoding": "png",
            "status": 3,
            "image": "/9j/4AAQ...<base64 encoded data>"
        }
    }
}
```

### 结构体可见性说明

- **ReqHeaderInfo** → `USTRUCT()`（无 BlueprintType）— 仅用于 JSON 序列化/反序列化，不在蓝图中暴露
- **ReqParameterInfo** → 各层子结构均为 `USTRUCT()` 无 BlueprintType — 内部 JSON 构建
- **ReqPayloadInfo** → `USTRUCT()` 含 `friend class` 声明 — 允许异步 Action 类直接访问私有 payload 字段
- **ReqInfo** → `USTRUCT(BlueprintType)` — 顶层结构，带 BlueprintType 方便调试

## 构建请求体的代码流程

在 `Activate_Internal()` 中：

```cpp
// 1. 构建签名 URL
FXGSampleXFLinkBase::AssembleAuthUrl(iFlyTekURL, APISecret, APIKey, AuthURL, Protocol);

// 2. 设置 AppID
ReqInfo.header.app_id = AppID;

// 3. 设置图片编码类型
ReqInfo.payload.input1.encoding = ConvertImgTypeToString(ImgType);

// 4. Base64 编码图片
FString ImgBase64String = FBase64::Encode(ImgBinaryData);

// 5. 大小检查（4MB 限制）
uint64 FileMaxSize = 4 * 1024 * 1024;
if (ImgBase64String.IsEmpty() || ImgBase64String.GetAllocatedSize() > FileMaxSize)
{
    CallOnFail(...);
    RealeaseResources();
    return;
}

// 6. 设置 Base64 图片数据
ReqInfo.payload.input1.image = ImgBase64String;

// 7. 结构体 → JSON 字符串
FString ContentString = TEXT("");
FJsonObjectConverter::UStructToJsonObjectString(ReqInfo, ContentString);

// 8. 发送 HTTP 请求
SendHttp(AuthURL, ContentString);
```

图片编码类型枚举定义见 [ReqType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Public/Type/SilentBiopsy/XGSampleXFSilentBiopsyReqType.h#L6-L13)：

```cpp
UENUM(BlueprintType)
enum class EXGSampleXFSilentBiopsyImgTpye : uint8
{
    Jpg, Jpeg, Png, Bmp
};
```

## HTTP 请求发送

```cpp
void UXGSampleXFSilentBiopsyAyncAction::SendHttp(const FString& InServerURL, const FString& InContentString)
{
    FHttpRequestRef Request = FHttpModule::Get().CreateRequest();
    
    Request->OnProcessRequestComplete().BindUObject(this, &UXGSampleXFSilentBiopsyAyncAction::OnHttpRespReceived);
    Request->SetURL(InServerURL);
    Request->SetVerb("Post");
    Request->SetHeader("Content-Type", "application/json");
    Request->SetContentAsString(InContentString);
    Request->ProcessRequest();
}
```

代码见 [SilentBiopsyAsyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleXFLink/Private/AsyncAction/XGSampleXFSilentBiopsyAyncAction.cpp#L100-L117)。

关键点：
- URL 使用**签名后的完整 URL**（包含 authorization/date/host 查询参数）
- HTTP Verb 固定为 **POST**
- Content-Type 为 **application/json**
- `BindUObject(this, ...)` 绑定响应处理函数，UObject 生命周期由 UE GC 管理
- HTTPS 需将 SSL 证书文件复制到项目目录（本课程使用 HTTP 简化部署）

## 4MB 大小限制说明

科大讯飞接口对 Base64 编码后的图片数据有 4MB 上限（约 3MB 原始 PNG 数据）。超过此限制应在 BP 层对图片做降采样或裁剪处理。
