# HTTPServer 独立程序概述与架构总览

## 章节定位

本章是课程的**案例 5**，构建一个基于虚幻引擎独立程序的 HTTP 登录注册服务器系统。系统分为两部分：

- **服务端**：基于 UE 独立程序（BlankProgram 模板）的 HTTP Server，绑定端口接收请求，处理登录/注册/版本检查
- **客户端**：基于 UE 插件（XGSampleClient）的 HTTP Client，封装请求/响应数据，暴露蓝图接口

这是本章与第二十三章（Slate 独立程序）的共性——都基于 BlankProgram 模板构建独立程序骨架，都需要处理手动打包。核心区别在于：第二十三章是**前端 UI 程序**（Slate 渲染），本章是**后端服务器程序**（纯控制台，无 UI，仅网络通信）。

## 客户端-服务端架构

```
┌─────────────────────────────────────────────────────────────────┐
│ 客户端 (UE 游戏项目)                                             │
│  ┌─────────────────────────────────────┐                        │
│  │ XGSampleClient 插件                  │                        │
│  │  ┌──────────────┐   ┌────────────┐  │                        │
│  │  │ BPLibrary     │──▶│ Subsystem  │  │  HTTP POST /Login      │
│  │  │ (蓝图入口)     │   │ (请求管理)  │  │─────────────────────▶  │
│  │  └──────────────┘   └─────┬──────┘  │  Header: Token         │
│  │                            │         │  Body: JSON           │
│  │                     ┌──────▼──────┐  │                        │
│  │                     │ Delegate Map │  │                        │
│  │                     │ (回调管理)    │  │                        │
│  │                     └─────────────┘  │                        │
│  └─────────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 服务端 (UE 独立程序)                                             │
│  ┌─────────────────────────────────────┐                        │
│  │ XGSampleServer 独立程序              │                        │
│  │  ┌──────────────┐   ┌────────────┐  │                        │
│  │  │ INI Config    │   │ HttpObject │  │                        │
│  │  │ (端口/令牌配置) │   │ (单例路由)  │  │                        │
│  │  └──────────────┘   └─────┬──────┘  │                        │
│  │                            │         │                        │
│  │                     ┌──────▼──────┐  │                        │
│  │                     │ 处理管线:     │  │                        │
│  │                     │ Token验证 →  │  │                        │
│  │                     │ JSON解析 →   │  │                        │
│  │                     │ 枚举路由 →   │  │                        │
│  │                     │ 业务处理 →   │  │                        │
│  │                     │ JSON响应     │  │                        │
│  │                     └─────────────┘  │                        │
│  └─────────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

## 技术栈

| 技术 | 用途 |
|------|------|
| `IHttpServerModule` (UE `HTTPServer` 模块) | 服务端 HTTP 监听与路由 |
| `FHttpModule` (UE `HTTP` 模块) | 客户端 HTTP 请求 |
| `FJsonObjectConverter` | JSON ↔ UStruct 反射序列化 |
| `FMD5` | MD5 哈希（令牌/密码加密） |
| `EXGSampleRequestType` 枚举 | 请求类型路由（版本检查/登录/注册） |
| `UBlueprintFunctionLibrary` | 客户端蓝图接口入口 |
| `UGameInstanceSubsystem` | 客户端请求管理与回调分发 |
| `FFileHelper::LoadFileToStringArray` | 服务端自定义 INI 配置读取 |
| BlankProgram 模板 | 服务端独立程序骨架 |

## 与第二十三章的架构对比

| 维度 | 第二十三章 (Slate) | 第二十六章 (HTTPServer) |
|------|-------------------|----------------------|
| 程序类型 | Windows GUI 应用 | 控制台应用 |
| 入口函数 | `WinMain` | `INT32_MAIN_INT32_ARGC_TCHAR_ARGV()` |
| 主循环 | `FSlateApplication` 事件循环 | 手工 `Sleep + ProcessThreadUntilIdle` 循环 |
| 核心依赖 | Slate/SlateCore/StandaloneRenderer | HTTP/HTTPServer/Json |
| 帧率控制 | 60 FPS（Slate 事件驱动） | 100 FPS（手工 Sleep） |
| 包体 | 较大（含 Slate 图标资源） | 较小（无 UI 资源） |
| 打包子文件夹 | `ExeBinariesSubFolder = "XGPrograms"` | 无特殊配置 |
| UObject 使用 | Core 管理器中包含 UObject | UXGSampleServerHttpObject 作为 UObject 单例 |

## 代码工程关联

| 目录 | 说明 |
|------|------|
| [XGSampleServer/](../code/013_独立程序源码/XGSampleServer/) | 服务端独立程序完整源码 |
| [XGSampleClient/](../code/001_XGSampleDemo/Plugins/XGSampleClient/) | 客户端插件完整源码 |
| [XGBlankProgram/](../code/013_独立程序源码/XGBlankProgram/) | 空白独立程序模板 |
| [XGSlateSample/](../code/013_独立程序源码/XGSlateSample/) | Slate 独立程序（第二十三章，对比参考） |
| [007_UEProgram1/](../code/007_UEProgram1/) | Slate 独立程序打包产物（5.4.2） |
| [008_UEProgram2/](../code/008_UEProgram2/) | HTTP 独立程序打包产物（5.4.2） |
