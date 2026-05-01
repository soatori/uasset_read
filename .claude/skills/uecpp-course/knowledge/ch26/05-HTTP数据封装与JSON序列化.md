# HTTP 数据封装与 JSON 序列化

## 概述

本章展示了从简单的**一级数据封装**到复杂的**二级数据封装**（也称商业化封装）的演进过程。两级封装的核心区别在于请求/响应结构的拆分粒度。

## 一级封装（基础版）

一级封装中，`FXGSampleServerRequest` 和 `FXGSampleServerResponse` 各自包含 Type 和 Data：

```
请求 JSON 结构：
{
    "Type": 1,                    ← 请求类型枚举
    "Data": "{ ... JSON 字符串 }"  ← 具体业务数据（字符串嵌套）
}

响应 JSON 结构：
{
    "Result": 0,                   ← 结果枚举
    "Message": "...",              ← 提示消息
    "Data": "{ ... JSON 字符串 }"  ← 业务数据（字符串嵌套）
}
```

Data 字段是字符串类型，内部再包含 JSON 字符串（**字符串嵌套 JSON**）。这种方式的缺点是：在最外层 JSON 解析时，Data 只是字符串，需要二次解析才能获得结构化数据。

## 二级封装（商业化版）

二级封装将所有业务数据平铺为 USTRUCT 字段，由 `FJsonObjectConverter` 反射完成完整序列化：

```
请求 JSON 结构：
{
    "Type": 1,                        ← 请求类型枚举
    "Data": "{ ... }"                 ← 仅保留字符串 Data，实际业务数据通过 USTRUCT 序列化
}

响应 JSON 结构：
{
    "Result": 0,
    "Message": "...",
    "Data": "{ ... }"
}
```

二级封装的实际改进在于：所有业务数据通过独立的 USTRUCT 定义，由 `JsonObjectStringToUStruct` 自动完成属性赋值。这种设计在第二十四章（商业化 JSON 读写）中有详细讲解。

## 请求类型定义

所有请求/响应类型定义在 `Type/` 目录中，客户端和服务端共享相同的结构体定义。

路径：[ServerType.h](../code/013_独立程序源码/XGSampleServer/Private/Type/XGSampleServerServerType.h)，[HttpType.h](../code/013_独立程序源码/XGSampleServer/Private/Type/XGSampleServerHttpType.h)，[RequestType.h](../code/013_独立程序源码/XGSampleServer/Private/Type/XGSampleServerRequestType.h)，[ResponseType.h](../code/013_独立程序源码/XGSampleServer/Private/Type/XGSampleServerResponseType.h)

### 请求类型枚举

```cpp
UENUM()
enum class EXGSampleRequestType : uint8
{
    CheckVersionReq     UMETA(DisplayName = "CheckVersionReq"),
    RegisterReq         UMETA(DisplayName = "RegisterReq"),
    LoginReq            UMETA(DisplayName = "LoginReq"),
};
```

### 请求数据结构

```cpp
USTRUCT()
struct FXGSampleServerRequest
{
    GENERATED_BODY()
    EXGSampleRequestType Type;
    FString Data;
};
```

### 响应结果枚举

```cpp
UENUM()
enum class EXGSampleServerResult : uint8
{
    Success              UMETA(DisplayName = "Success"),
    AuthFail             UMETA(DisplayName = "AuthFail"),
    JsonAnalysisFail     UMETA(DisplayName = "JsonAnalysisFail"),
    BadType              UMETA(DisplayName = "BadType"),
    ParamFail            UMETA(DisplayName = "ParamFail"),
    UserNotFount         UMETA(DisplayName = "UserNotFount"),
    PasswordFail         UMETA(DisplayName = "PasswordFail"),
    UserAlreadyExisting  UMETA(DisplayName = "UserAlreadyExisting"),
    RegisterFail         UMETA(DisplayName = "RegisterFail"),
    UnknownError         UMETA(DisplayName = "UnknownError"),
};
```

### 响应数据结构

```cpp
USTRUCT()
struct FXGSampleServerResponse
{
    GENERATED_BODY()
    EXGSampleServerResult Result;
    FString Message;
    FString Data;

    FXGSampleServerResponse()
        : Result(EXGSampleServerResult::UnknownError) {}
};
```

### 各业务请求数据

**版本检查请求**：空数据（仅验证服务器运行状态）。

**登录请求**：
```cpp
USTRUCT()
struct FXGSampleServerLoginRequestData
{
    GENERATED_BODY()
    FString UserName;
    FString Password;
};
```

**注册请求**：
```cpp
USTRUCT()
struct FXGSampleServerRegisterRequestData
{
    GENERATED_BODY()
    FString UserName;
    FString Password;
    FString Phone;
    FString Mail;
};
```

### 各业务响应数据

**登录响应**：
```cpp
USTRUCT()
struct FXGSampleServerLoginResponseData
{
    GENERATED_BODY()
    FString UserID;
    FString UserName;
};
```

**注册响应**：
```cpp
USTRUCT()
struct FXGSampleServerRegisterResponseData
{
    GENERATED_BODY()
    int32 UserID;
    FString UserName;
    FString Phone;
    FString Mail;
    FString RegisterTime;
};
```

**版本检查响应**：
```cpp
USTRUCT()
struct FXGSampleServerCheckVersionResponseData
{
    GENERATED_BODY()
    FString Version;
};
```

## JSON 序列化核心模式

服务端和客户端两端使用完全相同的 JSON 序列化模式：

### 服务端（反序列化请求 + 序列化响应）

```cpp
// 请求反序列化
FXGSampleServerRequest RequestData;
FJsonObjectConverter::JsonObjectStringToUStruct(JsonStr, &RequestData, 0, 0);

// 响应序列化
FXGSampleServerResponse ResponseData;
FString ResponseJson;
FJsonObjectConverter::UStructToJsonObjectString(ResponseData, ResponseJson);
```

### 客户端（序列化请求 + 反序列化响应）

```cpp
// 请求序列化
FXGSampleServerRequest RequestData;
RequestData.Type = EXGSampleRequestType::LoginReq;
RequestData.Data = BusinessJsonStr; // 业务数据的 JSON 字符串
FString RequestJson;
FJsonObjectConverter::UStructToJsonObjectString(RequestData, RequestJson);

// 响应反序列化
FXGSampleServerResponse ResponseData;
FJsonObjectConverter::JsonObjectStringToUStruct(ResponseJsonStr, &ResponseData, 0, 0);

// 业务数据二次反序列化
FXGSampleServerLoginResponseData LoginData;
FJsonObjectConverter::JsonObjectStringToUStruct(ResponseData.Data, &LoginData, 0, 0);
```

## 客户端与服务端的类型共享

客户端插件和服务端的 Type 目录包含同名文件（`XGSampleServerHttpType.h`、`XGSampleServerRequestType.h`、`XGSampleServerResponseType.h`），定义完全相同的结构体。这是最常见的做法——手动维护两端的数据类型定义一致（而非通过共享头文件的方式），因为客户端是 UE 插件（有 UClass 限制），服务端是独立程序（无 UClass 限制）。

## JSON 序列化流转

```
客户端
  业务数据 (USTRUCT)
    │
    ▼
  FJsonObjectConverter::UStructToJsonObjectString()
    │
    ▼
  JSON 字符串 (FString)
    │
    ▼
  通过 FHttpRequest::SetContentAsString() 设置请求体
    │
    ▼   HTTP 传输
服务端
    │
    ▼
  从 FHttpServerRequest.Body 读取字节
    │
    ▼
  FJsonObjectConverter::JsonObjectStringToUStruct()
    │
    ▼
  业务数据 (USTRUCT)
```
