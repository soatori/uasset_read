# 请求体构造与 JSON 工厂

## 概述

百度 ERNIE Bot 的请求体为扁平 JSON 格式，以 `messages` 数组为主体。不同于讯飞的三层嵌套结构（header/parameter/payload），百度直接使用顶层 key-value 组织参数。

## 请求结构体

[头文件](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Public/Type/XGSampleBDReqType.h#L56-L101)

```cpp
USTRUCT(BlueprintType)
struct FXGSampleBDReqInfo
{
    TArray<FXGSampleBDReqMessageInfo> messages;  // 对话消息列表
    float temperature = -1.0f;     // 温度，-1 表示未设置
    float top_p = -1.0f;           // 核采样
    float penalty_score = -1.0f;   // 惩罚分数
    bool stream = false;           // 是否流式输出
    FString system = TEXT("None"); // 系统提示词
    TArray<FString> stop;          // 停止词列表
    bool disable_search = false;   // 禁用搜索
    bool enable_citation = false;  // 开启引用
    bool enable_trace = false;     // 开启追踪
    int32 max_output_tokens = -1;  // 最大输出 token 数
    FString response_format = TEXT("text"); // 响应格式
    FString user_id = TEXT("None");// 用户标识
};
```

### 消息结构体

[定义](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Public/Type/XGSampleBDReqType.h#L32-L52)

```cpp
USTRUCT(BlueprintType)
struct FXGSampleBDReqMessageInfo
{
    FString role = TEXT("user");    // [user, assistant]
    FString content = TEXT("");
    FString name = TEXT("None");
};
```

## 手动 JSON 构建——FBDReqUtil

使用手动 JSON 构建而非 `FJsonObjectConverter` 的原因是：**可选字段需要条件性包含**。`FJsonObjectConverter` 会序列化所有 UPROPERTY 字段，无法按条件跳过不需要的字段。

[FBDReqUtil 定义](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Public/Type/XGSampleBDReqType.h#L14-L25)

```cpp
struct FXGSampleBDReqUti
{
    static bool WriteJsonValue(..., const FString& InName, const FString& InStringValue);
    static bool WriteJsonValue(..., const FString& InName, int32 InIntValue);
    static bool WriteJsonValue(..., const FString& InName, float InFloatValue);
    static bool WriteJsonValue(..., const FString& InName, bool InBoolValue);
};
```

### 条件写入规则

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/Type/XGSampleBDReqType.cpp)

| 类型 | 跳过条件 | 示例 |
|------|----------|------|
| FString | 空字符串 或 等于 "None"/"none" | `system = "None"` → 不写入 |
| int32 | 等于 -1 | `max_output_tokens = -1` → 不写入 |
| float | 等于 -1.0f | `temperature = -1.0f` → 不写入 |
| bool | 始终写入 | `stream = false` → 始终输出 |

### 消息数组序列化

每个消息通过 `ToJsonWriter` 序列化：

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/Type/XGSampleBDReqType.cpp#L50-L61)

```cpp
void FXGSampleBDReqMessageInfo::ToJsonWriter(ReqJsonWriter)
{
    ReqJsonWriter->WriteObjectStart();
    FXGSampleBDReqUti::WriteJsonValue(ReqJsonWriter, TEXT("role"), role);
    FXGSampleBDReqUti::WriteJsonValue(ReqJsonWriter, TEXT("content"), content);
    FXGSampleBDReqUti::WriteJsonValue(ReqJsonWriter, TEXT("name"), name);
    ReqJsonWriter->WriteObjectEnd();
}
```

### ToJsonString 完整流程

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/Type/XGSampleBDReqType.cpp#L64-L119)

```
WriteObjectStart
  WriteArrayStart("messages")
    messages[0].ToJsonWriter → {role, content, name}
    messages[1].ToJsonWriter → {role, content, name}
    ...
  WriteArrayEnd
  WriteJsonValue("temperature")      (conditional)
  WriteJsonValue("top_p")            (conditional)
  WriteJsonValue("penalty_score")    (conditional)
  WriteJsonValue("stream")
  WriteJsonValue("system")           (conditional)
  WriteArrayStart("stop")            (if stop.Num() > 0)
    ...
  WriteArrayEnd
  WriteJsonValue("disable_search")
  WriteJsonValue("enable_citation")
  WriteJsonValue("enable_trace")
  WriteJsonValue("max_output_tokens") (conditional)
  WriteJsonValue("response_format")   (conditional)
  WriteJsonValue("user_id")           (conditional)
WriteObjectEnd
```

## 输出示例（非流式，单轮对话）

```json
{
  "messages": [
    {"role": "user", "content": "你是谁"}
  ],
  "stream": false
}
```

## 与讯飞请求体的对比

| 维度 | 百度 ERNIE Bot | 讯飞 Spark |
|------|---------------|-----------|
| 结构 | 扁平 JSON | 三层嵌套（header/parameter/payload） |
| 对话消息 | messages 数组（role/content） | payload.message.text 数组（role/content） |
| 序列化方式 | 手动 TJsonWriter + FBDReqUtil | FJsonObjectConverter + 手动补充 |
| 可选字段 | -1 / "None" 哨兵值 + 条件写入 | 同样通过条件判断跳过 |
| 鉴权 | Header 中的 Authorization | URL 上的 authorization/date/host |

## 参考代码

- [XGSampleBDReqType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Public/Type/XGSampleBDReqType.h) — 请求类型定义
- [XGSampleBDReqType.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/Type/XGSampleBDReqType.cpp) — JSON 序列化实现
