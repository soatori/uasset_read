# 第二十六章 HTTPServer_自定义登录注册服务器

## 章节概览

本章构建了一个基于虚幻引擎独立程序的 HTTP 登录注册服务器系统。这是课程的**案例 5**，也是最后一个完整案例（之后进入 Capstone 综合项目）。

系统由两部分组成：
- **XGSampleServer** — UE 独立程序（控制台应用），基于 `HTTPServer` 模块提供 HTTP 服务
- **XGSampleClient** — UE 插件，向游戏项目蓝图暴露登录/注册接口

## 素材索引

| 类型 | 路径 | 说明 |
|------|------|------|
| 字幕 | [subtitles/026第二十六章HTTPServer_自定义登录注册服务器/](../subtitles/026第二十六章HTTPServer_自定义登录注册服务器/) | 21 个字幕文件 |
| 服务端源码 | [code/013_独立程序源码/XGSampleServer/](../code/013_独立程序源码/XGSampleServer/) | 完整服务端独立程序 |
| 客户端插件源码 | [code/001_XGSampleDemo/Plugins/XGSampleClient/](../code/001_XGSampleDemo/Plugins/XGSampleClient/) | 客户端插件 |
| BlankProgram 模板 | [code/013_独立程序源码/XGBlankProgram/](../code/013_独立程序源码/XGBlankProgram/) | 基础独立程序模板 |
| Slate 独立程序（对比） | [code/013_独立程序源码/XGSlateSample/](../code/013_独立程序源码/XGSlateSample/) | 第二十三章对比参考 |
| HTTP 打包产物 | [code/008_UEProgram2/](../code/008_UEProgram2/) | 服务器手动打包示例 |
| Slate 打包产物（对比） | [code/007_UEProgram1/](../code/007_UEProgram1/) | Slate 程序打包示例 |

## 细粒度知识文档

| # | 文档 | 核心内容 |
|---|------|---------|
| 01 | [架构总览与客户端-服务端设计](ch26/01-HTTPServer独立程序概述与架构总览.md) | 章节定位、CS 架构图、技术栈、与 Ch23 对比 |
| 02 | [服务端框架搭建与独立程序入口](ch26/02-服务端框架搭建与独立程序入口.md) | Build.cs/Target.cs、主入口 5 步初始化、主循环、关闭序列 |
| 03 | [自定义 INI 配置系统](ch26/03-自定义INI配置系统.md) | 自定义 INI 解析、单例模式、版本校验与自动修复 |
| 04 | [HTTP 端口绑定与请求处理管线](ch26/04-HTTP端口绑定与请求处理管线.md) | Init 绑定端口、ProcessHttpRequest 管线、Token 验证、JSON 解析 |
| 05 | [HTTP 数据封装与 JSON 序列化](ch26/05-HTTP数据封装与JSON序列化.md) | 一级/二级封装、请求/响应 USTRUCT、共享类型定义 |
| 06 | [MD5 令牌验证与安全机制](ch26/06-MD5令牌验证与安全机制.md) | 链式 MD5 哈希、Header Token 传递、密码哈希存储 |
| 07 | [服务端业务逻辑实现](ch26/07-服务端业务逻辑实现.md) | 版本检查、登录、注册完整实现 |
| 08 | [客户端插件架构与蓝图接口](ch26/08-客户端插件架构与蓝图接口.md) | BPLibrary + Subsystem + Delegate 回调三层架构 |
| 09 | [独立程序手动打包与部署](ch26/09-独立程序手动打包与部署.md) | 打包步骤、最小依赖、目录结构、与 Ch23 对比 |

## 架构要点速查

### 服务端初始化序列

```
IMPLEMENT_APPLICATION()
INT32_MAIN_INT32_ARGC_TCHAR_ARGV()
    ├── GEngineLoop.PreInit()                   ← 引擎初始化
    ├── FXGSampleServerConfigManage::Get()->Init()  ← 配置加载
    ├── UXGSampleServerHttpObject::Get()->Init()    ← HTTP 绑定 + 启动
    │       ├── FHttpServerModule::Get()
    │       ├── Router = Server->GetHttpRouter(Port)
    │       ├── Router->BindRoute("/Login", ...)
    │       └── Server->StartAllListeners()
    └── while (!IsEngineExitRequested())     ← 主循环
```

### 请求处理管线

```
HTTP Request → ProcessHttpRequest()
    ├── CheckHttpRequestToken()           ← Header Token 验证
    ├── JsonObjectStringToUStruct()       ← JSON 反序列化
    ├── DispatchHttpRequest()             ← 枚举路由
    │       ├── CheckVersionReq → HanldeCheckVersion()
    │       ├── LoginReq        → HanldeLogin()
    │       └── RegisterReq     → HanldeRegister()
    └── UStructToJsonObjectString() + Return  ← JSON 响应
```

### 客户端接口流程

```
蓝图节点 → BPLibrary::Login()
    → 组装请求数据 (USTRUCT)
    → JSON 序列化
    → Subsystem::SendHttpRequest()
        → FHttpModule::CreateRequest()
        → 设置 URL / Header / Token / Body
        → ProcessRequest()
        → OnResponseReceived()
            → JSON 反序列化
            → Delegate->ExecuteIfBound()
```

## 与第二十三章独立程序的架构对比

| 维度 | 第二十三章 (Slate) | 第二十六章 (HTTPServer) |
|------|-------------------|----------------------|
| 程序类型 | Windows GUI 应用 | 控制台应用 |
| 入口函数 | WinMain | INT32_MAIN_INT32_ARGC_TCHAR_ARGV() |
| 主循环 | FSlateApplication 事件循环 | Sleep + ProcessThreadUntilIdle |
| 核心模块 | Slate / SlateCore | HTTPServer / HTTP / Json |
| UObject 单例 | FXGSSPCore（原生 C++） | UXGSampleServerHttpObject（UObject） |
| 配置系统 | FFileHelper 自定义解析 | FFileHelper 自定义解析 |
| 打包子文件夹 | ExeBinariesSubFolder = "XGPrograms" | 无 |
| Slate 资源依赖 | 需要 | 不需要 |
| 客户方 | 无 | 有独立插件（XGSampleClient） |

## 代码文件索引

### 服务端（XGSampleServer）

| 文件 | 关键类/函数 |
|------|------------|
| [XGSampleServer.cpp](../code/013_独立程序源码/XGSampleServer/Private/XGSampleServer.cpp) | 主入口 `INT32_MAIN_INT32_ARGC_TCHAR_ARGV()`，主循环 |
| [XGSampleServer.Build.cs](../code/013_独立程序源码/XGSampleServer/XGSampleServer.Build.cs) | 模块依赖（HTTPServer/HTTP/Json） |
| [XGSampleServer.Target.cs](../code/013_独立程序源码/XGSampleServer/XGSampleServer.Target.cs) | TargetType.Program，Monolithic，控制台 |
| [XGSampleServerConfig.h/.cpp](../code/013_独立程序源码/XGSampleServer/Private/Config/XGSampleServerConfig.cpp) | `FXGSampleServerConfigManage` 单例 |
| [XGSampleServerHttpObject.h/.cpp](../code/013_独立程序源码/XGSampleServer/Private/ServerObject/XGSampleServerHttpObject.cpp) | HTTP 服务端核心、请求处理管线、业务逻辑 |
| [XGSampleServerUtil.h/.cpp](../code/013_独立程序源码/XGSampleServer/Private/Util/XGSampleServerUtil.cpp) | `EncryptionToken()` MD5 加密 |
| [LogXGSampleServer.h](../code/013_独立程序源码/XGSampleServer/Private/Log/LogXGSampleServer.h) | 日志类别声明 |
| [XGSampleServerRequestType.h](../code/013_独立程序源码/XGSampleServer/Private/Type/XGSampleServerRequestType.h) | `FXGSampleServerLoginRequestData`、`FXGSampleServerRegisterRequestData` |
| [XGSampleServerResponseType.h](../code/013_独立程序源码/XGSampleServer/Private/Type/XGSampleServerResponseType.h) | `FXGSampleServerLoginResponseData`、`FXGSampleServerRegisterResponseData` |
| [XGSampleServerHttpType.h](../code/013_独立程序源码/XGSampleServer/Private/Type/XGSampleServerHttpType.h) | `EXGSampleServerResult`、`EXGSampleRequestType` |
| [XGSampleServerServerType.h](../code/013_独立程序源码/XGSampleServer/Private/Type/XGSampleServerServerType.h) | `FXGSampleServerUserInfo`、`FXGSampleServerCheckVersionResponseData` |
| [PlatformWorkarounds.cpp](../code/013_独立程序源码/XGSampleServer/Private/PlatformWorkarounds.cpp) | `GFileRootDirectory`、`GSandboxName` |

### 客户端插件（XGSampleClient）

| 文件 | 关键类/函数 |
|------|------------|
| [XGSampleClientBPLibrary.h/.cpp](../code/001_XGSampleDemo/Plugins/XGSampleClient/Source/XGSampleClient/Public/XGSampleClientBPLibrary.h) | `Login()`、`Register()` 蓝图接口 |
| [XGSampleClientSubsystem.h/.cpp](../code/001_XGSampleDemo/Plugins/XGSampleClient/Source/XGSampleClient/Public/Subsystem/XGSampleClientSubsystem.h) | `SendHttpRequest()`、Delegate Map 回调管理 |
| [XGSampleClientSettings.h](../code/001_XGSampleDemo/Plugins/XGSampleClient/Source/XGSampleClient/Public/Config/XGSampleClientSettings.h) | `ServerURL`、`Token`、`MD5Num` 配置 |
| [XGSampleServerUtil.h/.cpp](../code/001_XGSampleDemo/Plugins/XGSampleClient/Source/XGSampleClient/Public/Util/XGSampleServerUtil.h) | `EncryptionToken()`（与服务端相同） |

### 对比参考

| 文件 | 说明 |
|------|------|
| [XGSlateSample.cpp](../code/013_独立程序源码/XGSlateSample/Private/XGSlateSample.cpp) | Slate 独立程序入口（对比 WinMain 与 INT32_MAIN） |
| [XGBlankProgram.cpp](../code/013_独立程序源码/XGBlankProgram/Private/XGBlankProgram.cpp) | 空白独立程序模板（最简入口） |
| [007_UEProgram1/](../code/007_UEProgram1/) | Slate 独立程序打包产物 |
| [008_UEProgram2/](../code/008_UEProgram2/) | HTTP Server 打包产物 |
