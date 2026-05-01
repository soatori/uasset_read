# UE_LOGFMT 结构化日志（UE5.2+）

## 概述

`UE_LOGFMT` 是 UE5.2 引入的结构化日志宏，相比 `UE_LOG` 的 printf 风格格式化，提供了更安全、更可读的日志方式。

**必要条件**：

```cpp
#include "Logging/StructuredLog.h"
```

## 基本语法

```cpp
UE_LOGFMT(CategoryName, Verbosity, "Message with {Placeholder}", Variable);
```

与 `UE_LOG` 的关键区别：
- 格式字符串**不包裹 `TEXT()`**（直接写字符串字面量）
- 占位符使用 `{Name}` 命名方式（不用 `%d`/`%s`/`%f`）
- 类型是安全的——不需要人工匹配格式说明符

## 两种绑定形式

### 形式一：位置绑定

变量按顺序映射到占位符：

```cpp
FString MyName = TEXT("XG");
int32 ErrorCode = 998;

UE_LOGFMT(LogXGSample, Warning,
    "Loading `{Name}` failed with error {Error}",
    MyName, ErrorCode);
```

第一个变量 `MyName` 对应 `{Name}`，第二个变量 `ErrorCode` 对应 `{Error}`。

### 形式二：命名绑定（TTuple 风格）

使用 `("Name", Value)` 键值对显式指定映射关系，顺序可以任意：

```cpp
UE_LOGFMT(LogXGSample, Warning,
    "Loading `{Name}` failed with error {Error}",
    ("Name", MyName), ("Error", ErrorCode), ("Flags", LoadFlags));
```

这种方式在占位符数量多、或同一占位符出现多次时更清晰。

## 与 UE_LOG 的对比

| 维度 | UE_LOG | UE_LOGFMT |
|------|--------|-----------|
| 格式字符串 | `TEXT("...")` 包裹 | 普通字符串字面量 |
| 占位符风格 | printf（`%d`/`%s`/`%f`） | 命名式（`{Name}`） |
| 类型安全 | 依赖人工匹配，不匹配会崩溃 | 自动匹配，编译期安全 |
| 参数顺序 | 必须按占位符顺序 | 命名绑定时可任意顺序 |
| 引入版本 | 所有 UE 版本 | UE5.2+ |
| 头文件 | CoreMinimal.h 已包含 | 需额外 `#include "Logging/StructuredLog.h"` |
| 可搜索性 | 日志在文件中无结构化元数据 | 结构化日志可附带元数据便于检索 |

## 屏幕调试信息

除了日志文件输出，还可以将调试信息直接显示在游戏画面上：

```cpp
if (GEngine)
{
    GEngine->AddOnScreenDebugMessage(-1, 5.f, FColor::White,
        TEXT("This is an Example on-screen debug message."));
}
```

| 参数 | 含义 | 说明 |
|------|------|------|
| `Key`（第一个参数） | 消息标识 | `-1` 表示每次创建新消息；相同 Key 会覆盖旧消息 |
| `TimeToDisplay` | 显示时长 | `5.f` 表示 5 秒后消失 |
| `Color` | 文字颜色 | `FColor::White`、`FColor::Red` 等 |
| `Text` | 显示内容 | 必须是 `TEXT()` 包裹 |

## 配套代码

- [XGLogActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/015_Log/XGLogActor.cpp) — `XGLogFormatString()` 和 `BeginPlay()` 中的屏幕调试信息
