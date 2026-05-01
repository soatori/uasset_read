# 百度 AKSK 鉴权签名

## 概述

百度 ERNIE Bot API 使用**AKSK（Access Key / Secret Key）签名**进行身份验证。签名结果放在 HTTP Header 的 `Authorization` 字段中，而非像讯飞那样拼接到 URL 上。

## 鉴权流程

```
Secret Key + authStringPrefix → HMAC-SHA256(hex) → signingKey
signingKey + canonicalRequest → HMAC-SHA256(hex) → signature
Authorization = authStringPrefix + "/host;x-bce-date/" + signature
```

## 步骤分解

### 1. 生成 authStringPrefix

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L197)

```cpp
FString authStringPrefix = TEXT("bce-auth-v1/") + InAPIKey
    + TEXT("/") + InTimestamp + TEXT("/") + FString::FromInt(ValiditySecond);
```

格式：`bce-auth-v1/{access_key}/{timestamp}/{expiry_period}`

默认有效期 1800 秒（30 分钟）。

### 2. 构造 canonicalRequest

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L199-L208)

```cpp
canonicalRequest += TEXT("POST");     // HTTP method
canonicalRequest += TEXT("\n");
canonicalRequest += Point;            // URL path
canonicalRequest += TEXT("\n");
canonicalRequest += TEXT("\n");
canonicalRequest += TEXT("host:") + Host;
canonicalRequest += TEXT("\n");
canonicalRequest += TEXT("x-bce-date:") + URLEncode(InTimestamp);
```

格式：`POST\n{path}\n\nhost:{domain}\nx-bce-date:{encoded_timestamp}`

其中 path 和 host 通过 `AnalyseBDURL` 解析：

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L221-L244)

```cpp
void FXGSampleXFLinkBase::AnalyseBDURL(const FString& InURL,
    FString& OutHost, FString& OutPoint)
{
    TArray<FString> URLParts;
    InURL.ParseIntoArray(URLParts, TEXT("/"), true);
    OutHost = URLParts[1];
    // 剩余部分拼接为 path
}
```

### 3. HMAC-SHA256 签名（十六进制输出）

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L42-L54)

```cpp
FString FXGSampleXFLinkBase::BDHMACSHA256(
    const FString& InAPPSecreet, const FString& InData)
{
    int len1 = strlen((char*)TCHAR_TO_UTF8(*InAPPSecreet));
    int len2 = strlen((char*)TCHAR_TO_UTF8(*InData));
    FXGSampleXFLnikBaseSHA256 BaseSHA256 = HmacSha256(
        (uint8_t*)TCHAR_TO_UTF8(*InData), len2,
        (uint8_t*)TCHAR_TO_UTF8(*InAPPSecreet), len1);
    FString HexStr = FString::FromHexBlob(BaseSHA256.Digest, 32);
    HexStr.ToLowerInline();
    return HexStr;
}
```

与讯飞 `XGHMACSHA256` 的区别：

| 函数 | 输出格式 | 用途 |
|------|----------|------|
| BDHMACSHA256 | `FString::FromHexBlob` → **hex 小写** | 百度鉴权 |
| XGHMACSHA256 | `FBase64::Encode` → **Base64** | 讯飞鉴权 |

两者底层都调用相同的 `HmacSha256`（OpenSSL EVP_sha256）。

### 4. 组装最终 Authorization

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L189-L219)

```cpp
FString signingKey = BDHMACSHA256(InInAPISecret, authStringPrefix);
FString signature = BDHMACSHA256(signingKey, canonicalRequest);
Authorization = authStringPrefix + TEXT("/host;x-bce-date/") + signature;
```

## HTTP Header 组装

[GenerateBDHeaders](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp#L166-L187)

```cpp
TMap<FString, FString> FXGSampleXFLinkBase::GenerateBDHeaders(
    const FString& InURL, const FString& InAPIKey, const FString& InInAPISecret)
{
    OutHeaders.Add(TEXT("Content-Type"), TEXT("application/json"));
    // ISO8601 时间戳，去除毫秒部分
    FString Timestamp = FDateTime::UtcNow().ToIso8601();
    Timestamp = Timestamp.Left(IndexPoint) + TEXT("Z");
    OutHeaders.Add(TEXT("x-bce-date"), Timestamp);
    OutHeaders.Add(TEXT("Authorization"), GenerateBDAuthorizationToken(...));
}
```

Headers 包含三个字段：
- `Content-Type: application/json`
- `x-bce-date`: ISO8601 格式时间戳（无毫秒，末尾 +Z）
- `Authorization`: 上述鉴权流程生成的完整签名串

## 在 Activate_Internal 中的使用

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/AsyncAction/XGSampleBPAyncAction.cpp#L56-L71)

```cpp
void UXGSampleBDAyncAction::Activate_Internal()
{
    FString BaiDuURL = TEXT("https://aip.baidubce.com/rpc/2.0/"
        "ai_custom/v1/wenxinworkshop/chat/ernie-lite-8k");
    TMap<FString, FString> Headers =
        FXGSampleXFLinkBase::GenerateBDHeaders(BaiDuURL, APIKey, APISecret);
    FString ConentString = ReqInfo.ToJsonString();
    SendHttp(BaiDuURL, ConentString, Headers);
}
```

## 与讯飞 Xunfei 鉴权的对比

| 维度 | 百度 (Baidu) | 讯飞 (Xunfei) |
|------|-------------|---------------|
| 鉴权位置 | HTTP Header `Authorization` | URL Query 参数 |
| HMAC 输出 | Hex 小写 | Base64 |
| 时间戳格式 | ISO8601（x-bce-date） | RFC1123（date） |
| 签名材料 | canonicalRequest | host + date + request-line |
| 加密函数 | BDHMACSHA256 | XGHMACSHA256 |
| URL 解析 | AnalyseBDURL（host + path） | AssembleAuthUrl（domain + path） |

## 参考代码

- [XGSampleXFLinkBase.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Private/XGSampleXFLinkBase.cpp) — 完整签名实现（BDHMACSHA256、GenerateBDHeaders、GenerateBDAuthorizationToken、AnalyseBDURL）
- [XGSampleXFLinkBase.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/ThirdParty/XGSampleXFLinkLibrary/Public/XGSampleXFLinkBase.h) — 函数声明
- [XGSampleBPAyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/AsyncAction/XGSampleBPAyncAction.cpp#L56-L71) — Activate_Internal 中调用签名
