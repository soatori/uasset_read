# 第三十四章：部署 MMO 分布式多人游戏

## 章节概览

本章构建了一个 **DSM（Dedicated Server Manager）+ DS（Dedicated Server）+ Player（客户端玩家）** 三层架构的分布式多人游戏系统。DSM 作为中央管理服务器维护 DS 实例列表，DS 启动后自动向 DSM 注册，客户端通过 DSM 获取可加入的服务器列表。DSM 还支持运行时动态创建新的 DS 进程。

| 项目 | 说明 |
|------|------|
| 案例编号 | 案例 12 |
| 前置章节 | 第三十一章（XGSampleWSM WebSocket 插件） |
| 代码工程 | `010_XGMultiGame`（DS + 客户端共用工程）、`011_XGMultiManage`（DSM 管理工程） |
| 核心能力 | DS 自动注册、DS 列表查询、动态创建 DS 进程 |

## 素材来源

- 字幕：`subtitles/034第三十四章部署MMO分布式多人游戏/`（10 个文件）
- 代码：`code/010_XGMultiGame/`（DS/客户端工程）、`code/011_XGMultiManage/`（DSM 管理工程）
- 插件：第三十一章 XGSampleWSM WebSocket 插件

## 知识文档

| 文档 | 内容 |
|------|------|
| [01-章节概览与DSM三层架构](ch34/01-章节概览与DSM三层架构.md) | 章节定位、架构图、通信流程与跨章节关联 |
| [02-WebSocket双层消息协议设计](ch34/02-WebSocket双层消息协议设计.md) | FXGMultiMessage 一级消息、二级结构体、JSON 双层序列化 |
| [03-DSM管理端实现（XGMultiManage）](ch34/03-DSM管理端实现（XGMultiManage）.md) | XGMultiManageGameMode、消息分发、DSList 管理、CreateNewDS |
| [04-DS与客户端注册流程实现](ch34/04-DS与客户端注册流程实现.md) | XGMultiGameInstance、角色判断（GetNetMode）、注册流程 |
| [05-DS动态创建与多Target打包部署](ch34/05-DS动态创建与多Target打包部署.md) | FPlatformProcess::CreateProc、Target.cs 配置、打包与部署 |

## 跨章节关联

| 章节 | 关联内容 |
|------|---------|
| **第三十一章** | 提供 XGSampleWSM 插件的基础 WebSocket 通信能力。ch34 在插件之上构建了第二层业务消息协议（FXGMultiMessage），区别于插件的原生 FXGWSMMessage 协议 |
| **第二章** | Multiplayer 基础知识（DS、Client、NetMode 等概念） |

## 操作日志

操作记录见 [log.md](log.md)。
