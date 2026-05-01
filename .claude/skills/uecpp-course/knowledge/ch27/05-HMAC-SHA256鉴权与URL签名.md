# HMAC-SHA256 鉴权与 URL 签名

科大讯飞静默活体检测 API 使用**三级鉴权**机制（authorization + date + host），通过 HMAC-SHA256 对请求信息签名后拼接到 URL 查询参数中。代码见 [XGSampleXFLinkBase.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L72-L130)。

## 架构说明

加密功能封装在独立的 `XGSampleXFLinkLibrary` 模块中，采用 **ThirdParty** 库类型：

- 通过 `AddEngineThirdPartyPrivateStaticDependencies(Target, "OpenSSL")` 引用 UE 内置的 OpenSSL
- 条件编译：`WITH_SSL=1` / `PLATFORM_SUPPORTS_OPENSSL` 控制 Android/iOS 平台的 OpenSSL 支持
- Build.cs 见 [XGSampleXFLinkLibrary.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/XGSampleXFLinkLibrary.Build.cs#L36-L64)

## HMAC-SHA256 加密

```cpp
struct FXGSampleXFLnikBaseSHA256
{
    uint8 Digest[32];
};

static FXGSampleXFLnikBaseSHA256 HmacSha256(const uint8* Input, size_t InputLen, const uint8* Key, size_t KeyLen)
{
    FXGSampleXFLnikBaseSHA256 Output;
    unsigned int OutputLen = 0;
    HMAC(EVP_sha256(), Key, KeyLen, (const unsigned char*)Input, InputLen, Output.Digest, &OutputLen);
    return Output;
}
```

代码见 [XGSampleXFLinkBase.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L30-L40)。

使用 OpenSSL 的 `HMAC()` 函数配合 `EVP_sha256()` 算法，输出 32 字节（256 位）哈希值。

## 讯飞式签名（XGHMACSHA256）

```cpp
FString FXGSampleXFLinkBase::XGHMACSHA256(const FString& InAPPSecreet, const FString& InData)
{
    FTCHARToUTF8 AppSecretData(InAPPSecreet);
    FTCHARToUTF8 Data(InData);
    
    FXGSampleXFLnikBaseSHA256 XunFeiBaseSHA256 = FXGSampleXFLinkBase::HmacSha256(
        (uint8_t*)Data.Get(), Data.Length(),
        (uint8_t*)AppSecretData.Get(), AppSecretData.Length());
    
    return FBase64::Encode(XunFeiBaseSHA256.Digest, 32);
}
```

代码见 [XGSampleXFLinkBase.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L56-L69)。

区别于百度签名（输出 Hex 字符串），讯飞的签名结果为 Base64 编码。

## URL 签名完整流程

`AssembleAuthUrl()` 函数实现了完整的 URL 签名管道：

```cpp
void FXGSampleXFLinkBase::AssembleAuthUrl(
    FString IniFlyTekURL,   // 原始 API URL
    FString InAPISecret,    // 讯飞 API Secret
    FString InAPIKey,       // 讯飞 API Key
    FString& OutAuthURL,    // 输出：签名后的完整 URL
    FString& OutProtocol,   // 输出：协议（http/https）
    bool bGet)              // HTTP 方法（默认 POST）
```

代码见 [XGSampleXFLinkBase.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L72-L130)。

### 步骤分解

**Step 1 — URL 分割**

```cpp
TArray<FString> URLParts;
IniFlyTekURL.ParseIntoArray(URLParts, TEXT("/"), true);
FString URLDomain = URLParts[1];  // api.xf-yun.com
// URLPath = /v1/private/s67c9c78c
```

**Step 2 — 生成 RFC 1123 日期**

```cpp
FString HttpDate = FDateTime::Now().UtcNow().ToHttpDate();
```

**Step 3 — 构建签名原材料**

```cpp
FString host = TEXT("host: ") + URLDomain + TEXT("\n");
FString date = TEXT("date: ") + HttpDate + TEXT("\n");
FString requireLine = TEXT("POST ") + URLPath + TEXT(" HTTP/1.1");

FString signature_origin = host + date + requireLine;
```

原始签名格式为：
```
host: api.xf-yun.com
date: Wed, 29 Apr 2026 10:00:00 GMT
POST /v1/private/s67c9c78c HTTP/1.1
```

**Step 4 — HMAC-SHA256 签名**

```cpp
FString signature = XGHMACSHA256(InAPISecret, signature_origin);
```

用 API Secret 对签名原材料做 HMAC-SHA256，结果 Base64 编码。

**Step 5 — 构建 authorization 字符串**

```cpp
FString authorization_origin =
    FString::Printf(TEXT("api_key=\"%s\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"%s\""),
        *InAPIKey, *signature);

FString authorization = FBase64::Encode(authorization_origin);
```

**Step 6 — 组装最终 URL**

```cpp
OutAuthURL = IniFlyTekURL + FString::Printf(
    TEXT("?authorization=%s&date=%s&host=%s"),
    *authorization, *URLEncode(HttpDate), *URLDomain);
```

最终 URL 结构：
```
http://api.xf-yun.com/v1/private/s67c9c78c?authorization=<base64>&date=<url-encoded-date>&host=api.xf-yun.com
```

## URLEncode 实现

手动替换特殊字符，代码见 [XGSampleXFLinkBase.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L132-L146)：

```cpp
InURL.ReplaceInline(TEXT("%"), TEXT("%25"));
InURL.ReplaceInline(TEXT(" "), TEXT("%20"));
InURL.ReplaceInline(TEXT(":"), TEXT("%3A"));
InURL.ReplaceInline(TEXT("/"), TEXT("%2F"));
InURL.ReplaceInline(TEXT("="), TEXT("%3D"));
InURL.ReplaceInline(TEXT("&"), TEXT("%26"));
// ...
```

注意顺序：`%` 必须第一个替换，防止二次编码。

## 密钥配置

- `app_id`、`api_key`、`api_secret` 从[科大讯飞开放平台控制台](https://console.xfyun.cn/)获取
- 讯飞提供免费额度，可申请静默活体检测服务的试用
- 三者作为参数传入蓝图的 AsyncAction 工厂方法
