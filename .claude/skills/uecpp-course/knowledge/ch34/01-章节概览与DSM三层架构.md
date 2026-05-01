# 章节概览与 DSM 三层架构

## 章节定位

第三十四章是课程案例实践的高潮章节之一，构建了一个**DSM（Dedicated Server Manager）+ DS（Dedicated Server）+ Player（客户端玩家）** 三层分布式多人游戏架构。

| 维度 | 说明 |
|------|------|
| 课程编号 | 第三十四章 |
| 案例编号 | 案例 12 |
| 前置章节 | 第三十一章（XGSampleWSM WebSocket 插件） |
| 代码工程 | `010_XGMultiGame`（DS + 客户端）、`011_XGMultiManage`（DSM） |
| 核心能力 | DS 自动注册、动态 DS 创建、客户端获取 DS 列表 |

### 与前序章节的关系

| 章节 | 关系 |
|------|------|
| **第三十一章** | 提供了 XGSampleWSM WebSocket 通信插件，包含 `UXGWSMServerSubsystem`（服务端子系统和 `UXGWSMClientSubsystem`（客户端子系统）。第三十四章直接复用这两个 Subsystem，在其上层构建业务消息协议 |
| **第三十二章**（TCP） | （间接相关）本章未直接使用 TCP，但 WebSocket 的底层传输机制与 TCP 有相似之处 |
| **第二章 基本架构** | Multiplayer 架构基础知识（DS、Listen Server 等概念） |

### 与第三十一章的继承差异

| 对比维度 | 第三十一章（插件层） | 第三十四章（业务层） |
|---------|------------------|------------------|
| 消息协议 | `FXGWSMMessage`（ActionType + 双 GUID） | `FXGMultiMessage`（Code + MessageType + Data） |
| 编解码 | Base64 编码传输 | 纯 JSON 字符串（双层序列化） |
| 状态机 | 完整状态机（Init→Tick→Quit）+ 3s 心跳 | 无状态机，直接使用连接回调 |
| 连接管理 | TMap 管理多连接，心跳超时检测 | DSM 端 TMap 管理，无心跳依赖 |
| 角色判断 | 无（工具层） | `GetNetMode()` 区分 DS/Player |

## 三层架构

```
┌──────────────────────────────────────────────────────────────┐
│                     DSM (011_XGMultiManage)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  XGMultiManageGameMode                                  │  │
│  │  ├── UXGWSMServerSubsystem (端口 9033, WebSocket Server) │  │
│  │  ├── TArray<FXGDSInfo> DSList          (已注册 DS 列表)  │  │
│  │  ├── TArray<FXGPlayerInfo> PlayerList  (已注册玩家列表)   │  │
│  │  └── CreateNewDS() (FPlatformProcess::CreateProc)        │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────────────────┘
                       │ WebSocket (127.0.0.1:9033)
         ┌─────────────┴─────────────┐
         │                           │
┌────────▼──────────┐    ┌──────────▼───────────┐
│     DS (服务器)    │    │   Player (客户端玩家)  │
│ 010_XGMultiGame   │    │   010_XGMultiGame    │
│                   │    │                      │
│ UXGWSMClient      │    │ UXGWSMClient         │
│ Subsystem         │    │ Subsystem            │
│                   │    │                      │
│ NetMode:          │    │ NetMode:             │
│ NM_DedicatedServer│    │ NM_Client/Standalone │
│                   │    │                      │
│ 注册时发送:        │    │ 注册时发送:           │
│ DSInitInfo        │    │ PlayerInitInfo       │
│（端口/IP/关卡名）   │    │（PlayerID）          │
└───────────────────┘    └──────────────────────┘
```

### 各层职责

| 层 | 工程 | 职责 |
|----|------|------|
| **DSM** | `011_XGMultiManage` | 中央管理服务器，运行 WebSocket Server，维护 DS 实例列表，接收客户端请求，动态拉起新 DS 进程 |
| **DS** | `010_XGMultiGame`（Server 包） | 实际游戏服务器实例，启动后向 DSM 注册自身信息（IP、端口、关卡名），等待玩家连接 |
| **Player** | `010_XGMultiGame`（Client 包） | 客户端玩家，启动后连接 DSM 注册身份，请求 DS 列表，选择并加入游戏服务器 |

### 通信流程

```
1. 启动顺序
   DSM 先启动 → WebSocket Server 监听 9033 端口
   DS 启动 → WebSocket Client → 连接 DSM → 发送 DSInitInfo
   Player 启动 → WebSocket Client → 连接 DSM → 发送 PlayerInitInfo

2. 注册流程
   DS  → DSM:  { Type: ReqInitDSRole, Data: { ServerID, LevelName, ServerPort, ServerIP } }
   DSM → DS:   { Type: RespInitDSRole }
   Player → DSM: { Type: ReqInitPlayerRole, Data: { PlayerName } }
   DSM → Player: { Type: RespInitPlayerRole }

3. 查询 DS 列表
   Player → DSM: { Type: ReqPlayerReqAllDSInfos }
   DSM → Player: { Type: RespPlayerReqAllDSInfos, Data: { DSList: [...] } }

4. 动态创建 DS
   Player → DSM: { Type: ReqPlayerCreateNewLevel }
   DSM → Player: { Type: RespPlayerCreateNewLevel }
   DSM: FPlatformProcess::CreateProc(...)  // 拉起新 DS 进程
```

## 通信拓扑

| 特征 | 说明 |
|------|------|
| 通信协议 | WebSocket（通过 XGSampleWSM 插件） |
| DSM 监听端口 | 9033 |
| DS 游戏端口 | 手动指定（如 7777、8888、8889），由 .bat 文件的 `-port=` 参数传入 |
| 客户端连接 | 从 DSM 获取 DS 信息后，通过 `open IP:Port` 连接 DS |
| 消息格式 | JSON 双层序列化（`FXGMultiMessage` 包含 `Data` 字段，Data 是二级结构体的 JSON 字符串） |

## 代码工程概览

| 工程 | 路径 | 生成包 |
|------|------|--------|
| 010_XGMultiGame | `code/010_XGMultiGame/` | Client 包 + Server 包（同一代码，不同 Target 配置打出两个包） |
| 011_XGMultiManage | `code/011_XGMultiManage/` | DSM 管理包（可在编辑器运行，不打包也可） |
| XGSampleWSM 插件 | `010_XGMultiGame/Plugins/XGSampleWSM/` 和 `011_XGMultiManage/Plugins/XGSampleWSM/` | 两个工程各有一份插件拷贝 |

## 关键文件索引

| 文件路径 | 说明 |
|---------|------|
| [XGMultiManageGameMode.h](../../code/011_XGMultiManage/Source/XGMultiManage/XGMultiManageGameMode.h) | DSM 端 GameMode——WebSocket Server 启动、消息分发、DSList 管理 |
| [XGMultiManageGameMode.cpp](../../code/011_XGMultiManage/Source/XGMultiManage/XGMultiManageGameMode.cpp) | DSM 端实现——四个消息类型的 Switch 分发、CreateNewDS |
| [XGMultiType.h (DSM)](../../code/011_XGMultiManage/Source/XGMultiManage/XGMultiType.h) | DSM 端消息类型定义（与 010 端手动拷贝同步） |
| [XGMultiGameInstance.h](../../code/010_XGMultiGame/Source/XGMultiGame/XGMultiGameInstance.h) | DS/Player 端 GameInstance——连接 DSM、注册身份 |
| [XGMultiGameInstance.cpp](../../code/010_XGMultiGame/Source/XGMultiGame/XGMultiGameInstance.cpp) | DS/Player 端实现——角色判断、消息收发 |
| [XGMultiGameGameMode.h](../../code/010_XGMultiGame/Source/XGMultiGame/XGMultiGameGameMode.h) | DS 端 GameMode——DS 注册触发点（通过 GameInstance 的委托） |
| [XGMultiGameGameMode.cpp](../../code/010_XGMultiGame/Source/XGMultiGame/XGMultiGameGameMode.cpp) | DS 端 GameMode——`OnConnectionSuccess` 构建 DSInitInfo 并发送 |
| [XGMultiType.h (Game)](../../code/010_XGMultiGame/Source/XGMultiGame/XGMultiType.h) | DS/Player 端消息类型定义 |
| [XGMultiGame.Build.cs](../../code/010_XGMultiGame/Source/XGMultiGame/XGMultiGame.Build.cs) | 模块依赖（含 XGSampleWSM + Json + JsonUtilities） |
| [XGMultiGameServer.Target.cs](../../code/010_XGMultiGame/Source/XGMultiGameServer.Target.cs) | Server Target 配置 |
| [XGMultiGameClient.Target.cs](../../code/010_XGMultiGame/Source/XGMultiGameClient.Target.cs) | Client Target 配置 |
