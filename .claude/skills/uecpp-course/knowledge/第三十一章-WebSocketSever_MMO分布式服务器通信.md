# 第三十一章：WebSocketServer——MMO 分布式服务器通信

## 章节说明

本章构建一个自包含的 WebSocket 服务器插件 **XGSampleWSM**（XiaoGang Sample WebSocket Message），用于 MMO 分布式服务器间的通信。与第二十九/三十章（客户端单向连接第三方 WebSocket 服务）不同，本章同时实现**服务器端**和**客户端**两套 WebSocket 能力，形成完整的双向通信框架。

| 对比维度 | 第二十九/三十章（STT/TTS） | 第三十一章（WSM） |
|---------|--------------------------|------------------|
| 角色 | 纯客户端 | 客户端 + 服务器端双角色 |
| 服务器 | 第三方 API（讯飞） | 自建 WebSocket 服务器 |
| 通信拓扑 | 单点连接 | 多容器单播/广播（future） |
| 连接管理 | 单一连接 | TMap 容器管理多连接 |
| 消息协议 | 服务端定义格式 | 自定 JSON 协议（ActionType + 双 GUID） |
| 生命周期 | 单一状态 | 完整状态机（Init → Tick → Quit + 超时） |
| 心跳 | 由服务端控制 | 客户端 3s 发送 → 服务端 10s 超时检测 |

> **后续章节关联**：第三十四章（MMO 实例服务器）将基于本章完成的插件构建。

## 字幕资源

- 来源：`subtitles/031第三十一章WebSocketSever_MMO分布式服务器通信/`
- 共 15 个字幕文件（001~015）

## 文件索引

| 子系统 | 文件路径 | 说明 |
|-------|---------|------|
| 插件定义 | `Plugins/XGSampleWSM/XGSampleWSM.uplugin` | 插件描述文件 |
| 模块配置 | `Plugins/XGSampleWSM/Source/XGSampleWSM/XGSampleWSM.Build.cs` | 模块依赖 + 平台白名单 |
| 模块入口 | `Public/XGSampleWSM.h` / `Private/XGSampleWSM.cpp` | 模块启动/关闭 |
| 日志 | `Public/Log/LogXGWSM.h` / `Private/Log/LogXGWSM.cpp` | 客户端/服务端日志分类 |
| BP 库 | `Public/XGSampleWSMBPLibrary.h/.cpp` | 蓝图函数库基类 |
| **类型系统** | `Public/Type/XGWSMType.h` | 核心类型：连接状态枚举、ActionType 枚举、消息体结构 |
| **编解码** | `Public/Util/XGWSMUtil.h` / `Private/Util/XGWSMUtil.cpp` | Base64 编码/解码工具 |
| **服务器连接** | `Public/Connection/XGWSMSeverConnection.h` / `Private/Connection/XGWSMSeverConnection.cpp` | 服务端连接结构（WebSocket 指针 + 双 GUID + 状态 + Tick） |
| **客户端连接** | `Public/Connection/XGWSMClientConnection.h` / `Private/Connection/XGWSMClientConnection.cpp` | 客户端连接结构（IWebSocket 智能指针 + 3s 心跳 + 10s 超时） |
| **服务器子系统** | `Public/Subsystem/XGWSMServerSubsystem.h` / `Private/Subsystem/XGWSMServerSubsystem.cpp` | 服务端 UGameInstanceSubsystem 实现 |
| **客户端子系统** | `Public/Subsystem/XGWSMClientSubsystem.h` / `Private/Subsystem/XGWSMClientSubsystem.cpp` | 客户端 UGameInstanceSubsystem 实现 |

## 细粒度知识文档

| 文档 | 内容 |
|------|------|
| [01-知识概览](ch31/01-知识概览.md) | 整体 Pipeline + 架构图 + 文件层级 |
| [02-MMOARPG分布式服务器架构与通讯拓扑](ch31/02-MMOARPG分布式服务器架构与通讯拓扑.md) | 服务器层次、容器拓扑、端口策略 |
| [03-消息协议与编解码](ch31/03-消息协议与编解码.md) | JSON 消息格式、ActionType 枚举、Base64 加解密 |
| [04-插件架构与子系统设计](ch31/04-插件架构与子系统设计.md) | Build.cs 配置、Subsystem 模式、三模块拆分计划 |
| [05-服务器端实现](ch31/05-服务器端实现.md) | IWebSocketServer、ServerConnection、Tick 心跳、容器管理 |
| [06-客户端实现与全流程通讯](ch31/06-客户端实现与全流程通讯.md) | IWebSocket 回调、数据重组、消息分发、状态机 |
| [07-蓝图测试与多实例调试](ch31/07-蓝图测试与多实例调试.md) | 蓝图面板绑定、Postman 测试、多编辑器实例 |

> 本章知识文档于 2026-04-29 完成首次提取。
