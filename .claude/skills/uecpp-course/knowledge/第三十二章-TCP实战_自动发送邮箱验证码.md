# 第三十二章：TCP 实战——自动发送邮箱验证码

## 字幕资源

- 来源：`subtitles/032第三十二章TCP实战_自动发送邮箱验证码/`
- 共 10 个字幕文件（001~010）

---

## 核心知识点

### 1. XGSampleEMail 插件架构（四类核心设计）
- **AsyncAction**（`TSharedFromThis` 体系）：异步行动封装，持有 Runnable 智能指针，管理 SMTP 状态机
- **Runnable**（`FRunnable`）：TCP 线程主体，收发原始字节流
- **Subsystem**（C++ 单例）：管理所有 AsyncAction 实例
- **BPLibrary**（`UObject`）：蓝图层统一调用入口
- 详见 [ch32/01-插件架构与四类核心设计](ch32/01-插件架构与四类核心设计.md)

### 2. SMTP 协议状态机
- 完整交互流程：220→EHLO→250→AUTH LOGIN→334→Base64(用户名)→334→Base64(密码)→235→MAIL FROM→250→RCPT TO→250→DATA→354→邮件内容+ `\r\n.\r\n` →250→QUIT→221
- 状态枚举 `EXGSampleEMailStatus` 直接映射 SMTP 协议阶段
- 认证方式：AUTH LOGIN（Base64 编码）
- 详见 [ch32/02-SMTP协议状态机实现](ch32/02-SMTP协议状态机实现.md)

### 3. FRunnable 多线程 TCP 通信
- `FTcpSocketBuilder` 创建阻塞模式 Socket
- 域名解析：`ISocketSubsystem::GetAddressFromString()`
- 主循环：`HasPendingConnection` → `HasPendingData` → `Recv`
- 回调异步：线程内回调通过委托拷贝、AsyncTask 回到游戏线程
- 资源安全：先 Stop 线程、后释放 Runnable
- 详见 [ch32/03-FRunnable多线程TCP通信](ch32/03-FRunnable多线程TCP通信.md)

### 4. 关键设计决策
| 决策 | 原因 |
|------|------|
| AsyncAction 继承 `TSharedFromThis` 而非 `UBlueprintAsyncActionBase` | 脱离 UObject 体系，支持独立程序运行 |
| Build.cs 不含 `Engine` 模块 | 为独立程序预留兼容性 |
| Subsystem 为 C++ 单例而非 `UGameInstanceSubsystem` | 不依赖引擎子系统框架 |
| 内部类不加导出宏 | 封装内部实现，外部不可见 |
| Runnable 只收发字节流，不关心业务协议 | 职责分离，TCP 层与 SMTP 逻辑解耦 |

## 关键类/API

| 类/API | 头文件路径 |
|--------|-----------|
| `XGSampleEMailAsyncAction` | [AsyncAction/XGSampleEMailAsyncAction.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Public/AsyncAction/XGSampleEMailAsyncAction.h) |
| `XGSampleEMailRunnable` | [Thread/XGSampleEMailRunnable.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Public/Thread/XGSampleEMailRunnable.h) |
| `XGSampleEMailSubsystem` | [Subsystem/XGSampleEMailSubsystem.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Public/Subsystem/XGSampleEMailSubsystem.h) |
| `UXGSampleEMailBPLibrary` | [XGSampleEMailBPLibrary.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Public/XGSampleEMailBPLibrary.h) |
| `EXGSampleEMailStatus` | [Type/XGSampleEMailType.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/Public/Type/XGSampleEMailType.h) |
| `FTcpSocketBuilder` | 引擎 `Sockets` 模块 |
| `ISocketSubsystem` | 引擎 `Sockets` 模块 |

## 代码工程关联

| 内容 | 路径 |
|------|------|
| 完整插件源码 | `code/001_XGSampleDemo/Plugins/XGSampleEMail/` |
| 插件配置文件 | [XGSampleEMail.uplugin](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/XGSampleEMail.uplugin) |
| 模块构建配置 | [XGSampleEMail.Build.cs](file:///d:/UPS/GitLab/XGUnrealNote/Courses/UE-CPP-Basic-to-Advanced/code/001_XGSampleDemo/Plugins/XGSampleEMail/Source/XGSampleEMail/XGSampleEMail.Build.cs) |

---

## 细粒度知识文档

| 文档 | 内容覆盖 |
|------|----------|
| [ch32/01-插件架构与四类核心设计](ch32/01-插件架构与四类核心设计.md) | 插件架构总览、AsyncAction/Runnable/Subsystem/BPLibrary 四类核心设计、Build.cs 依赖 |
| [ch32/02-SMTP协议状态机实现](ch32/02-SMTP协议状态机实现.md) | SMTP 完整通信流程、状态枚举、OnMessage 状态机实现、Base64 认证、邮件内容格式 |
| [ch32/03-FRunnable多线程TCP通信](ch32/03-FRunnable多线程TCP通信.md) | FRunnable 生命周期、Socket 创建/连接/收发、线程安全回调、资源关闭流程、Bug 修复 |

> 本章知识文档已提取（2026-04-29）。操作记录见 [log.md](log.md)。
