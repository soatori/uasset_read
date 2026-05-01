# 第二十五章：HTTP 基础——获取公网时间

## 字幕资源

- 来源：`subtitles/025第二十五章HTTP基础_获取公网时间/`
- 共 5 个字幕文件（001~005）

---

## 本章概述

本章是课程的**案例 4**，完整实现一个通过 HTTP 获取公网时间的异步蓝图节点。覆盖 HTTP 协议基础概念、UE Http 模块集成、UBlueprintAsyncActionBase 异步节点框架、Activate 执行流与错帧设计、JSON 响应反射解析，以及时区偏移计算。

## 知识文档索引

| 序号 | 文档 | 覆盖字幕 | 核心内容 |
|------|------|----------|----------|
| 01 | [HTTP 基础概念与 UE Http 模块入门](ch25/http-basics.md) | 001 | HTTP 请求结构、GET/POST 区别、状态码、UE Http 模块集成、HTTPS SSL 注意事项 |
| 02 | [异步蓝图节点框架与生命周期管理](ch25/async-action-framework.md) | 002 | UBlueprintAsyncActionBase、三引脚设计、HideThen 元数据、工厂函数、NewObject + RegisterWithGameInstance |
| 03 | [Activate 执行流与回调线程切换](ch25/execution-flow.md) | 003, 004 | 错帧执行、Activate_Internal、AsyncTask 线程切换、值拷贝捕获、RealeaseResources |
| 04 | [完整 HTTP 请求链路与 JSON 响应解析](ch25/http-request-chain.md) | 004, 005 | SendHttp 配置、三层状态验证、FJsonObjectConverter 反射解析、时间戳转换、Flush 同步化 |

## 关键类/API 速查

| 类/API | 头文件 | 用途 |
|--------|--------|------|
| `FHttpModule` | `HttpModule.h` | HTTP 模块单例，创建请求 |
| `FHttpRequestRef` | `Http.h` | HTTP 请求智能指针 |
| `FHttpResponsePtr` | `Http.h` | HTTP 响应智能指针 |
| `UBlueprintAsyncActionBase` | `BlueprintAsyncActionBase.h` | 异步蓝图节点基类 |
| `FDateTime` | `Misc/DateTime.h` | 日期时间结构体 |
| `FJsonObjectConverter` | `JsonObjectConverter.h` | JSON ↔ USTRUCT 反射转换 |
| `FCString::Atoi64` | `Containers/UnrealString.h` | 字符串转 int64 |
| `FDateTime::FromUnixTimestamp` | `Misc/DateTime.h` | Unix 时间戳 → FDateTime |
| `FDateTime::Now()` | `Misc/DateTime.h` | 获取本地时间 |
| `FDateTime::UtcNow()` | `Misc/DateTime.h` | 获取 UTC 时间 |
| `AsyncTask` | `Async/Async.h` | 线程切换工具 |
| `DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams` | `DelegateCombinations.h` | 四参数多播委托声明 |
| `DEFINE_LOG_CATEGORY_STATIC` | `Logging/LogMacros.h` | 静态日志类别定义 |

## 代码工程关联

| 目录 | 说明 |
|------|------|
| [code/001_XGSampleDemo/Source/XGSampleDemo/025_HttpTime/](ch25/../code/001_XGSampleDemo/Source/XGSampleDemo/025_HttpTime/) | 本章主代码（XGSampleHttpTime.h/.cpp） |

## 与前序/后续章节的关联

| 关系 | 章节 | 说明 |
|------|------|------|
| 前置依赖 | 第24章 Json 读写 | HTTP 响应解析依赖 JSON 反射序列化 |
| 后续使用 | 第26~28章 HTTP 系列 | 本章框架基础上扩展更多 HTTP 功能 |
| 后续使用 | 第29~31章 WebSocket 系列 | 网络通讯的请求-响应模式通用 |
