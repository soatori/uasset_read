# HTTP 流式数据处理

## 概述

当请求的 `stream = true` 时，百度 API 通过 HTTP 分块传输（chunked transfer）逐段返回数据。每段数据可能包含一个或多个 JSON chunk，需要按分隔符拆分后逐条解析。这是本章最核心的技术点，也是 UE HTTP 模块深度使用的体现。

## 流式数据格式

百度 ERNIE Bot 流式数据格式：

```
data: {"result":"你好","is_safety":true,"usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5}}
data: {"result":"！我是","is_safety":true,"usage":{}}

data: {"result":"文心一言","is_safety":true,"usage":{}}
data: {"is_safety":true,"usage":{"prompt_tokens":3,"completion_tokens":21,"total_tokens":24}}
```

每条消息以 `data: ` 开头，以 `\n\n` 分隔。最后一条数据可能只有 `data:\n\n`（无内容，仅携带 token 统计）。

## Pipeline

```
[OnStreamReady] → 二进制累积 → \n\n 扫描 → 分割 → data: 前缀去除 → JSON 解析 → OnUpdate
                                             └→ 空行检测 → 完成 → OnSuccess
```

## 关键实现

### 1. OnStreamReady 绑定

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/AsyncAction/XGSampleBPAyncAction.cpp#L73-L102)

```cpp
void UXGSampleBDAyncAction::SendHttp(...)
{
    // ... 设置 URL、Body、Headers
    
    HttpRequest->OnStreamReady().BindUObject(this, &UXGSampleBDAyncAction::OnStreamReady);
}
```

`OnStreamReady` 是 UE 5.3+ 新增的委托，类型为：

```cpp
DECLARE_DELEGATE_RetVal_TwoParams(bool, FOnStreamReady, void*, int64);
```

- 返回 `true`：继续接收流式数据
- 返回 `false`：取消流式传输

### 2. 跨线程调度

[OnStreamReady 回调](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/AsyncAction/XGSampleBPAyncAction.cpp#L310-L322)

`OnStreamReady` 在**非游戏线程**回调。直接操作 UObject 或广播蓝图委托会在非游戏线程触发断屏风险（`Ensure` 断言）。解决方案：

```cpp
bool UXGSampleBDAyncAction::OnStreamReady(void* Data, int64 Length)
{
    if (IsEngineExitRequested()) return false;
    
    TArray<uint8> DataArray;
    DataArray.Append((uint8*)Data, Length);
    
    // 切到游戏线程处理
    FFunctionGraphTask::CreateAndDispatchWhenReady(
        [this, DataArray]()
        {
            ContentDataArray.Append(DataArray);
            ParseStreamData();
        },
        TStatId(), nullptr, ENamedThreads::GameThread
    );
    return true;
}
```

通过 `FFunctionGraphTask::CreateAndDispatchWhenReady` 将数据处理调度到游戏线程，避免跨线程 UObject 访问。

### 3. 二进制数据累积

使用 `TArray<uint8>` 作为累积缓冲区，因为流式数据可能在任何位置断裂（包括 UTF-8 多字节字符中间）：

```cpp
TArray<uint8> ContentDataArray;
```

`OnStreamReady` 每次回调时将新数据追加到缓冲区末尾。

### 4. 递归分割解析——ParseStreamData

[实现](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/AsyncAction/XGSampleBPAyncAction.cpp#L327-L370)

```cpp
void UXGSampleBDAyncAction::ParseStreamData()
{
    TArray<uint8> Delimiter = {10, 10};  // \n\n
    int32 Index = FindBytesInArray(ContentDataArray, Delimiter);
    if (Index == INDEX_NONE) return;     // 不完整，等待更多数据
    
    // 1. 提取一个完整 chunk
    TArray<uint8> OneData;
    OneData.Append(ContentDataArray.GetData(), Index);
    
    // 2. 从缓冲区移除已处理部分
    ContentDataArray.RemoveAt(0, Index + 2 /*跳过\n\n*/);
    
    // 3. 去除 "data: " 前缀
    FString OneDataStr = UTF8ToString(OneData);
    OneDataStr.ReplaceInline(TEXT("data: "), TEXT(""));
    
    // 4. 空数据 → 流式结束
    if (OneDataStr.IsEmpty())
    {
        // 处理最终结果并触发出
        CallOnSuccess(...);
        return;
    }
    
    // 5. 解析为 FBDStreamMessage
    FXGSampleBDStreamMessage StreamMessage;
    // 检查是否有 error_stream_data
    // 提取 result、usage、search_info
    
    // 6. 触发 OnUpdate
    CallOnUpdate(AsyncID, true, StreamMessage.result, ...);
    
    // 7. 递归处理可能剩余的完整 chunk
    if (ContentDataArray.Num() > 0)
        ParseStreamData();
}
```

#### 分隔符查找——FindBytesInArray

自定义的字节数组查找函数：

```cpp
int32 UXGSampleBDAyncAction::FindBytesInArray(
    const TArray<uint8>& Data, const TArray<uint8>& Pattern)
{
    for (int32 i = 0; i <= Data.Num() - Pattern.Num(); i++)
    {
        bool bMatch = true;
        for (int32 j = 0; j < Pattern.Num(); j++)
        {
            if (Data[i + j] != Pattern[j]) { bMatch = false; break; }
        }
        if (bMatch) return i;
    }
    return INDEX_NONE;
}
```

#### UTF-8 转 TCHAR

```cpp
FString UTF8ToString(const TArray<uint8>& Data)
{
    FString Result;
    // 使用 TCHAR 编码转换
    // 或者直接 FString::FromUTF8((const ANSICHAR*)Data.GetData(), Data.Num())
}
```

### 5. 流式响应解析

每段 chunk 的 JSON 结构：

```json
{
    "result": "生成的文本片段",
    "is_safety": true,
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
    "search_info": [{"url": "...", "title": "...", "index": 0}]
}
```

解析时先检查 `error_stream_data` 错误标志，然后尝试从 `result` 字段获取文本，从 `usage` 获取 token 消耗，从 `search_info` 获取知识检索引用。

### 6. 流式完成信号

当收到 `data:\n\n`（content 为空）或 `data: [DONE]\n\n` 时，表示流式传输完成。此时：
- `totalStream` 累积了全部文本
- 最后一条消息可能只包含 `usage` 和 `header_info`（token 统计和限流信息）
- 调用 `CallOnSuccess` 传递最终组装好的响应

## 错误处理

流式过程中的错误有两种来源：
1. **stream 结束时检测**：检查 `error_stream_data` 字段
2. **OnStreamReady 期间**：与正常流式数据同格式但内容为错误描述

## 与讯飞交互的对比

| 维度 | 百度流式 | 讯飞 WebSocket |
|------|---------|---------------|
| 传输协议 | HTTP chunked transfer | WebSocket |
| 数据格式 | `data: ` 前缀 + `\n\n` 分隔 | 独立 JSON 消息 |
| 分割复杂度 | 高（需手动扫描分隔符） | 低（每条消息独立） |
| 跨线程处理 | 必须（非游戏线程回调） | 不涉及（WebSocket 已处理） |
| 结束信号 | 空 `data:\n\n` | WebSocket 关闭帧 |

## 参考代码

- [XGSampleBPAyncAction.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Private/AsyncAction/XGSampleBPAyncAction.cpp#L310-L370) — 流式处理核心逻辑（OnStreamReady、ParseStreamData、FindBytesInArray）
- [XGSampleBPAyncAction.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleLink/Source/XGSampleBDLink/Public/AsyncAction/XGSampleBPAyncAction.h) — 成员声明
