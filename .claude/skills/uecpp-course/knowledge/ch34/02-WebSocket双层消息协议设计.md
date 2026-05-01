# WebSocket 双层消息协议设计

## 设计动机

第三十四章在 XGSampleWSM 插件的基础上构建了**第二层业务消息协议**。插件层负责原始的 WebSocket 连接管理（建立/断开/收发），业务层负责定义消息语义。

```
插件层（XGSampleWSM）         业务层（第三十四章）
┌─────────────────────┐      ┌─────────────────────────┐
│ UXGWSMClient        │      │ FXGMultiMessage          │
│ Subsystem           │ ──►  │ ├── Code: int32          │
│                     │ raw  │ ├── MessageType: enum    │
│ 原始 JSON 字符串     │ JSON │ └── Data: FString (JSON) │
│ 透传                 │      │                           │
│                     │      │ 二级结构体（存入 Data）    │
│ 委托回调广播         │      │ ├── FXGReqInitDSRoleMsg   │
└─────────────────────┘      │ ├── FXGReqInitPlayerMsg   │
                              │ ├── FXGDSInfo             │
                              │ └── FXGRespAllDSInfos     │
                              └─────────────────────────┘
```

## 一级消息结构：FXGMultiMessage

定义在 [XGMultiType.h](../../code/010_XGMultiGame/Source/XGMultiGame/XGMultiType.h) 和 [XGMultiType.h (DSM)](../../code/011_XGMultiManage/Source/XGMultiManage/XGMultiType.h)（两份相同，手动拷贝同步）。

```cpp
USTRUCT()
struct FXGMultiMessage
{
    GENERATED_BODY()

    UPROPERTY()
    int32 Code = -1;

    UPROPERTY()
    EXGMultiMessageType MessageType = EXGMultiMessageType::None;

    UPROPERTY()
    FString Data = TEXT("");
};
```

| 字段 | 类型 | 用途 |
|------|------|------|
| `Code` | `int32` | 状态码（-1 初始，0 表示正常） |
| `MessageType` | `EXGMultiMessageType` | 消息类型枚举，标识语义 |
| `Data` | `FString` | 二级结构体的 JSON 字符串 |

## 消息类型枚举

```cpp
UENUM(BlueprintType)
enum class EXGMultiMessageType : uint8
{
    None,
    ReqInitDSRole,            // DS → DSM: 注册 DS 身份
    RespInitDSRole,           // DSM → DS: 回复注册确认
    ReqInitPlayerRole,        // Player → DSM: 注册玩家身份
    RespInitPlayerRole,       // DSM → Player: 回复注册确认
    ReqPlayerReqAllDSInfos,   // Player → DSM: 请求 DS 列表
    RespPlayerReqAllDSInfos,  // DSM → Player: 返回 DS 列表
    ReqPlayerCreateNewLevel,  // Player → DSM: 请求创建新 DS
    RespPlayerCreateNewLevel, // DSM → Player: 回复创建确认
};
```

### 消息流对应关系

| 消息类型 | 方向 | 二级结构体 |
|---------|------|-----------|
| `ReqInitDSRole` | DS → DSM | `FXGReqInitDSRoleMessage` |
| `RespInitDSRole` | DSM → DS | 无二级数据 |
| `ReqInitPlayerRole` | Player → DSM | `FXGReqInitPlayerRoleMessage` |
| `RespInitPlayerRole` | DSM → Player | 无二级数据 |
| `ReqPlayerReqAllDSInfos` | Player → DSM | 无二级数据 |
| `RespPlayerReqAllDSInfos` | DSM → Player | `FXGRespPlayerAllDSInfosInfo` |
| `ReqPlayerCreateNewLevel` | Player → DSM | 无二级数据 |
| `RespPlayerCreateNewLevel` | DSM → Player | 无二级数据 |

## 二级结构体

### DS 注册信息

DS 启动后向 DSM 注册时携带的身份信息：

```cpp
USTRUCT()
struct FXGReqInitDSRoleMessage
{
    GENERATED_BODY()

    UPROPERTY()
    EXGMultiRoleType RoleType = EXGMultiRoleType::None;

    UPROPERTY()
    FGuid ServerID = FGuid();

    UPROPERTY()
    FString LevelName = TEXT("");

    UPROPERTY()
    int32 ServerPort = -1;

    UPROPERTY()
    FString ServerIP = TEXT("");
};
```

| 字段 | 说明 |
|------|------|
| `RoleType` | 角色类型（DS/Player） |
| `ServerID` | DS 唯一标识（GUID） |
| `LevelName` | DS 当前加载的关卡名 |
| `ServerPort` | DS 游戏服务器监听端口 |
| `ServerIP` | DS 的 IP 地址 |

### 角色枚举

```cpp
UENUM(BlueprintType)
enum class EXGMultiRoleType : uint8
{
    None,
    Player,
    DS,
    Max
};
```

### 玩家注册信息

```cpp
USTRUCT()
struct FXGReqInitPlayerRoleMessage
{
    GENERATED_BODY()

    UPROPERTY()
    EXGMultiRoleType RoleType = EXGMultiRoleType::None;

    UPROPERTY()
    FString PlayerName = TEXT("");
};
```

### DSM 内部存储结构

DSM 使用 `FXGDSInfo` 存储每个已注册 DS 的完整信息：

```cpp
USTRUCT()
struct FXGDSInfo
{
    GENERATED_BODY()

    UPROPERTY()
    FGuid ServerConnectionID = FGuid();  // DSM 侧连接标识

    UPROPERTY()
    FGuid ServerID = FGuid();            // DS 的唯一 ID

    UPROPERTY()
    FString LevelName = TEXT("");

    UPROPERTY()
    FString ServerIP = TEXT("");

    UPROPERTY()
    int32 ServerPort = -1;

    bool operator==(const FXGDSInfo& Other) const
    {
        return ServerConnectionID == Other.ServerConnectionID ? true : false;
    }
};
```

### DS 列表响应

```cpp
USTRUCT()
struct FXGRespPlayerAllDSInfosInfo
{
    GENERATED_BODY()

    UPROPERTY()
    TArray<FXGDSInfo> DSList;
};
```

### 玩家信息存储

```cpp
USTRUCT()
struct FXGPlayerInfo
{
    GENERATED_BODY()

    UPROPERTY()
    FGuid ServerConnectionID = FGuid();

    UPROPERTY()
    FString PlayerName = TEXT("");

    bool operator==(const FXGPlayerInfo& Other) const
    {
        return ServerConnectionID == Other.ServerConnectionID ? true : false;
    }
};
```

## JSON 双层序列化流程

### 发送端（序列化）

```cpp
// 第 1 层：二级结构体 → JSON 字符串
FXGReqInitDSRoleMessage DSRoleMessage;
DSRoleMessage.LevelName = LevelName;
DSRoleMessage.ServerPort = MyDSPort;
// ...
FString DataJson;
FJsonObjectConverter::UStructToJsonObjectString(DSRoleMessage, DataJson);

// 第 2 层：一级消息 + Data(JSON字符串) → 完整 JSON
FXGMultiMessage ReqMessage;
ReqMessage.MessageType = EXGMultiMessageType::ReqInitDSRole;
ReqMessage.Data = DataJson;
FString ReqMessageJson;
FJsonObjectConverter::UStructToJsonObjectString(ReqMessage, ReqMessageJson);

// 通过插件发送
ClientSubsystem->SendMessageToServer(ReqMessageJson, ClientConnectionID);
```

### 接收端（反序列化）

```cpp
// 第 1 层：完整 JSON → 一级消息
FXGMultiMessage MultiMessage;
FJsonObjectConverter::JsonObjectStringToUStruct(Message, &MultiMessage);

// 判断类型
switch (MultiMessage.MessageType)
{
    case EXGMultiMessageType::ReqInitDSRole:
    {
        // 第 2 层：Data JSON → 二级结构体
        FXGReqInitDSRoleMessage DSRoleMessage;
        FJsonObjectConverter::JsonObjectStringToUStruct(
            MultiMessage.Data, &DSRoleMessage);
        // ...处理逻辑
        break;
    }
    // ...
}
```

## 与第三十一章插件消息协议的对比

| 对比维度 | 第三十一章（插件原生协议） | 第三十四章（业务层协议） |
|---------|------------------------|------------------------|
| 消息体 | `FXGWSMMessage`（ActionType + 双 GUID + Data） | `FXGMultiMessage`（Code + MessageType + Data） |
| 传输编码 | Base64（二进制传输） | 纯 JSON 字符串（文本传输） |
| 编解码方式 | `XGMessageEncode/Decode` | `FJsonObjectConverter::UStructToJsonObjectString` |
| 消息分发 | 插件内部 OnMessageDispatch → 5 种 ActionType | 业务层 Switch 分发 → 8 种 MessageType |
| 状态关联 | 有（等待 InitServerConnection） | 无（收到消息立即处理） |
| 心跳 | 3s 发送 + 10s 超时 | 无心跳依赖 |
| 设计层级 | 通用通信层 | 业务语义层 |

## 关键注意事项

| 注意点 | 说明 |
|--------|------|
| 两份 XGMultiType.h 需手动同步 | DSM 和 DS/Client 工程各维护一份，修改结构体时需手动拷贝 |
| Data 字段为空时也要序列化 | 即使没有二级数据（如 `RespInitDSRole`），`Data` 字段仍设为空字符串 |
| `check(bParse)` | 反序列化失败直接断言崩溃，调试阶段安全，正式环境应增加容错 |
| 跨工程 JSON 兼容 | 两个工程的 `FXGMultiMessage` 定义必须完全一致，否则反序列化失败 |
