# FJsonObjectConverter 反射序列化

## 概述

FJsonObjectConverter 是 UE 提供的**基于反射系统**的 JSON 自动序列化方案。只需定义 `USTRUCT()` + `GENERATED_BODY()` + `UPROPERTY()`，无需手写读写逻辑。这是自建前后端场景中的推荐方式。

## 头文件

```cpp
#include "JsonObjectConverter.h"
```

## 核心 API

| API | 方向 | 说明 |
|-----|------|------|
| `FJsonObjectConverter::UStructToJsonObjectString(Struct, OutString)` | 序列化 | USTRUCT → JSON 字符串 |
| `FJsonObjectConverter::JsonObjectStringToUStruct(JsonString, &Struct)` | 反序列化 | JSON 字符串 → USTRUCT |
| `FJsonObjectConverter::JsonArrayStringToUStruct(JsonString, &OutArray)` | 反序列化 | JSON 数组字符串 → TArray\<USTRUCT\> |

## 简单结构体示例

### USTRUCT 定义

```cpp
USTRUCT()
struct FXGSampleServerInfo
{
    GENERATED_BODY()

    UPROPERTY()
    FString ServerName;

    UPROPERTY()
    FString ServerVersion;

    UPROPERTY()
    FString TestInfo;

    FString NotWrite = TEXT("没有被序列化");  // 无 UPROPERTY，不会被序列化
};
```

**关键规则**：
- 必须 `USTRUCT()` + `GENERATED_BODY()`
- 只有标记 `UPROPERTY()` 的字段才会被序列化
- 无 `UPROPERTY()` 的字段（如 `NotWrite`）完全被忽略
- 有 `UPROPERTY()` 但没有赋值的字段会序列化为 `""`（空字符串）或默认值
- **名字必须匹配**：反序列化时 JSON key 与 UPROPERTY 变量名一一对应

### 使用

```cpp
FXGSampleServerInfo ServerInfo;
ServerInfo.ServerName = TEXT("XGServer");
ServerInfo.ServerVersion = TEXT("1.3.3");
ServerInfo.NotWrite = TEXT("没有被序列化");  // 此字段不会出现在 JSON 中

// 序列化
FString ServerInfoJson;
FJsonObjectConverter::UStructToJsonObjectString(ServerInfo, ServerInfoJson);

// 反序列化
FXGSampleServerInfo BackServerInfo;
FJsonObjectConverter::JsonObjectStringToUStruct(ServerInfoJson, &BackServerInfo);
```

生成的 JSON：
```json
{"ServerName":"XGServer","ServerVersion":"1.3.3","TestInfo":""}
```

- `NotWrite` 不出现（无 UPROPERTY）
- `TestInfo` 出现但为空字符串（有 UPROPERTY 但未赋值）

## 复杂嵌套结构体

### 定义嵌套关系

```cpp
USTRUCT()
struct FXGSampleCoderInfo
{
    GENERATED_BODY()
    UPROPERTY() FString Name = TEXT("None");
    UPROPERTY() double WorkYear = -1.f;
};

USTRUCT()
struct FXGSampleMessageInfo
{
    GENERATED_BODY()
    UPROPERTY() int32 Code = -1;
    UPROPERTY() FString Message;
    UPROPERTY() FString Data;
    UPROPERTY() FString Sid;

    UPROPERTY() FXGSampleServerInfo Info;               // 嵌套对象
    UPROPERTY() TArray<int32> WorkerIDs;                // 简单数组
    UPROPERTY() TArray<FXGSampleCoderInfo> Coders;      // 结构体数组

    FString NotWrite = TEXT("111");                     // 不序列化
    UPROPERTY() FDateTime TempTime;                     // FDateTime 也会自动序列化
};
```

### 使用

```cpp
FXGSampleMessageInfo Msg;
Msg.Code = 10087;
Msg.Message = TEXT("这是测试信息");
Msg.Info.ServerName = TEXT("XGServer");
Msg.Info.ServerVersion = TEXT("1.3.4");
Msg.WorkerIDs.Add(2); Msg.WorkerIDs.Add(4); Msg.WorkerIDs.Add(6);

// 结构体数组
Msg.Coders.AddDefaulted();  // 或 AddDefaulted_GetRef()
Msg.Coders.Last().Name = TEXT("XG");
Msg.Coders.Last().WorkYear = 3.2;

Msg.TempTime = FDateTime::Now();

// 一次调用完成全部序列化
FString Json;
FJsonObjectConverter::UStructToJsonObjectString(Msg, Json);

// 反序列化
FXGSampleMessageInfo BackMsg;
FJsonObjectConverter::JsonObjectStringToUStruct(Json, &BackMsg);
```

生成的 JSON 自动包含所有嵌套：
```json
{
  "Code": 10087,
  "Message": "这是测试信息",
  "Data": "",
  "Sid": "",
  "Info": {"ServerName":"XGServer","ServerVersion":"1.3.4","TestInfo":""},
  "WorkerIDs": [2,4,6],
  "Coders": [{"Name":"XG","WorkYear":3.2}],
  "TempTime": "2024-01-15T10:30:00.000Z"
}
```

## 特殊类型支持

FJsonObjectConverter 基于反射可自动处理以下类型：

| 类型 | 序列化结果 |
|------|----------|
| `int32` / `float` / `double` / `bool` | 对应 JSON 数值/布尔 |
| `FString` / `FName` / `FText` | JSON 字符串 |
| `FDateTime` | ISO 8601 格式字符串 |
| `TArray<T>` | JSON 数组 |
| 其他 `USTRUCT` | 嵌套 JSON 对象 |
| 枚举（`UENUM`） | JSON 字符串（枚举名） |

**注意**：枚举值前后端必须一致，否则反序列化会失败（找不到对应枚举名）。

## JsonArrayStringToUStruct — 批量反序列化

当后端返回的是一个 JSON 数组（多个结构体的列表）而非单个对象时：

```json
[
  {"Name": "XG", "WorkYear": 3.2},
  {"Name": "GX", "WorkYear": 1.3}
]
```

```cpp
TArray<FXGSampleCoderInfo> Coders;
FJsonObjectConverter::JsonArrayStringToUStruct(JsonArrayString, &Coders);
```

## 三种方式选择指南

| 条件 | 推荐方式 |
|------|----------|
| 自建前后端，结构体可控 | FJsonObjectConverter（方式三） |
| 对接第三方 API，格式固定但无法改 | TJsonWriter/TJsonReader（方式二） |
| 极度简单的键值对配置 | FString::Printf 也可（但不推荐） |

## 配套代码

| 函数 | 文件 | 行 |
|------|------|----|
| `AXGSampleJson::GoodSturctJson()` | [XGSampleJson.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.cpp#L375) | 375~402 |
| `AXGSampleJson::GoodSturctJson2()` | [XGSampleJson.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.cpp#L404) | 404~448 |
| 结构体定义 | [XGSampleJson.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/024_Json/XGSampleJson.h#L59) | 59~128 |
