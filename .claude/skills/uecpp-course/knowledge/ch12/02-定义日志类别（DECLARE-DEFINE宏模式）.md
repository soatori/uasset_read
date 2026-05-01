# 定义日志类别（DECLARE/DEFINE 宏模式）

日志类别（Log Category）是 UE 日志系统的命名空间，每个 `UE_LOG` 调用必须先指定一个日志类别。类别定义的宏模式与 GameplayTag 的 `UE_DECLARE_GAMEPLAY_TAG_EXTERN`/`UE_DEFINE_GAMEPLAY_TAG` 模式类似，分为声明（extern）和定义（实现）两个步骤。

## 模块级日志类别

一个供多个文件共享的日志类别，需要在头文件中声明，在 `.cpp` 中定义。

**头文件声明**：

```cpp
#pragma once
#include "CoreMinimal.h"

DECLARE_LOG_CATEGORY_EXTERN(LogXGSample, Log, All);
```

- `LogXGSample` — 类别名称，约定以 `Log` 开头
- `Log` — 默认级别（即在未作任何配置时的输出级别）
- `All` — 编译期最高级别（编译时即决定哪些级别的日志会被编译进去，`All` 表示编译所有级别）

**实现文件定义**：

```cpp
#include "XGLogType.h"
DEFINE_LOG_CATEGORY(LogXGSample);
```

`DEFINE_LOG_CATEGORY` 为声明提供实际的存储空间，一个模块级类别有且仅有一个 `.cpp` 中定义。

## 文件级静态日志类别

如果日志类别只在当前 `.cpp` 中使用，不需要被其他文件引用，使用静态宏：

```cpp
#include "XGLogActor.h"
#include "XGLogType.h"

DEFINE_LOG_CATEGORY_STATIC(LogXGLogActor, Log, All)
```

- 不需要在头文件中声明 `extern`
- 作用域仅限于当前 `.cpp` 文件
- 与模块级类别可以共存（一个模块可以有多个静态类别）
- 不能从其他文件中引用

## 命名约定

| 元素 | 约定 | 示例 |
|------|------|------|
| 前缀 | 统一以 `Log` 开头 | `LogXGSample`、`LogXGLogActor` |
| 后缀 | 无固定后缀 | 见上 |
| 风格 | PascalCase | `LogMyGame`、`LogNetwork`、`LogAI` |

某些内置类别也遵循此约定：`LogTemp`、`LogBlueprint`、`LogNet`。

## 两个级别参数的含义

`DECLARE_LOG_CATEGORY_EXTERN(CategoryName, DefaultVerbosity, CompileTimeVerbosity)` 和 `DEFINE_LOG_CATEGORY_STATIC(CategoryName, DefaultVerbosity, CompileTimeVerbosity)` 的第二个和第三个参数容易混淆：

| 参数 | 含义 | 典型值 |
|------|------|--------|
| `DefaultVerbosity` | 运行时默认的显示级别（无任何配置时的表现） | `Log`、`Display`、`Error` |
| `CompileTimeVerbosity` | 编译期最高级别（高于此级别的日志根本不会被编译） | `All`（保留全部）、`Fatal`（最小化影响） |

大多数情况下使用 `Log, All` 即可。

## 配套代码

- [XGLogType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/015_Log/XGLogType.h) — `DECLARE_LOG_CATEGORY_EXTERN(LogXGSample, Log, All)` 声明
- [XGLogType.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/015_Log/XGLogType.cpp) — `DEFINE_LOG_CATEGORY(LogXGSample)` 定义
- [XGLogActor.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Source/XGSampleDemo/015_Log/XGLogActor.cpp) — `DEFINE_LOG_CATEGORY_STATIC(LogXGLogActor, Log, All)` 文件级类别
