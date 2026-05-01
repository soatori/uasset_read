# DSM 管理端实现（XGMultiManage）

## 工程结构

DSM 管理端位于 `011_XGMultiManage`，是一个**空白 C++ 项目**，只有一个 GameMode 类。核心代码集中在 `XGMultiManageGameMode` 中。

```
011_XGMultiManage/
├── Source/
│   ├── XGMultiManage/
│   │   ├── XGMultiManageGameMode.h    // DSM 核心逻辑
│   │   ├── XGMultiManageGameMode.cpp  // DSM 核心实现
│   │   ├── XGMultiType.h              // 消息结构体定义
│   │   ├── XGMultiType.cpp            // (空)
│   │   ├── XGMultiManage.Build.cs     // 模块引用
│   │   └── XGMultiManage.h            // 模块头文件
│   ├── XGMultiManage.Target.cs
│   └── XGMultiManageEditor.Target.cs
├── Plugins/XGSampleWSM/               // 第三十一章插件
└── XGMultiManage.uproject
```

## XGMultiManageGameMode 架构

[GameMode.h](../../code/011_XGMultiManage/Source/XGMultiManage/XGMultiManageGameMode.h) | [GameMode.cpp](../../code/011_XGMultiManage/Source/XGMultiManage/XGMultiManageGameMode.cpp)

### 核心成员

```cpp
class AXGMultiManageGameMode : public AGameModeBase
{
    // 子系统引用
    UPROPERTY()
    UXGWSMServerSubsystem* ServerSubsystem;

    // DS 列表
    UPROPERTY()
    TArray<FXGDSInfo> DSList;

    // 玩家列表
    UPROPERTY()
    TArray<FXGPlayerInfo> PlayerList;

    // 动态创建 DS（蓝图可调用）
    UFUNCTION(BlueprintCallable)
    void CreateNewDSProcess(int32 InPort, const FString& InLevelName);
};
```

### 生命周期

```
BeginPlay (StartWebSocketServer:9033)
    │
    ├── OnConnected → 记录连接 (打印 ServerConnectionID)
    ├── OnConnectFail → 打印错误
    ├── OnDisconnected
    │   ├── 从 DSList 中移除（匹配 ServerConnectionID）
    │   └── 从 PlayerList 中移除（匹配 ServerConnectionID）
    └── OnMessageReceived → OnMessageReceivedHandler(msg, connectionID)
            │
            └── MessageSwitch (按 MessageType 分发)
                    ├── ReqInitDSRole       → HandleReqInitDSRole
                    ├── ReqInitPlayerRole   → HandleReqInitPlayerRole
                    ├── ReqPlayerReqAllDSInfos → HandleReqPlayerReqAllDSInfos
                    └── ReqPlayerCreateNewLevel → HandleReqPlayerCreateNewLevel
                        ↓
                        CreateNewDSProcess(指定端口, 关卡名)

EndPlay (StopWebSocketServer)
```

## BeginPlay：启动 WebSocket Server

```cpp
void AXGMultiManageGameMode::BeginPlay()
{
    Super::BeginPlay();

    // 获取 ServerSubsystem
    ServerSubsystem = GetGameInstance()->GetSubsystem<UXGWSMServerSubsystem>();
    if (!ServerSubsystem) return;

    // 绑定事件
    ServerSubsystem->ServerConnectionConnectedSuccessDelegate.AddDynamic(
        this, &AXGMultiManageGameMode::OnConnected);
    ServerSubsystem->ServerConnectionConnectedErrorDelegate.AddDynamic(
        this, &AXGMultiManageGameMode::OnConnectFail);
    ServerSubsystem->ServerConnectionReceiveMessageDelegate.AddDynamic(
        this, &AXGMultiManageGameMode::OnMessageReceived);
    ServerSubsystem->ServerConnectionClosedDelegate.AddDynamic(
        this, &AXGMultiManageGameMode::OnDisconnected);

    // 启动 WebSocket Server（端口 9033）
    ServerSubsystem->StartWebSocketServer(9033);
}
```

### EndPlay

```cpp
void AXGMultiManageGameMode::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (ServerSubsystem)
    {
        ServerSubsystem->StopWebSocketServer();
    }
    Super::EndPlay(EndPlayReason);
}
```

## 消息分发

DSM 收到消息后，先反序列化为一级消息 `FXGMultiMessage`，然后按 `MessageType` 分发：

```cpp
void AXGMultiManageGameMode::OnMessageReceivedHandler(
    const FString& Message, const FGuid& ConnectionID)
{
    // 反序列化一级消息
    FXGMultiMessage MultiMessage;
    FJsonObjectConverter::JsonObjectStringToUStruct(Message, &MultiMessage);

    // 按类型分发
    switch (MultiMessage.MessageType)
    {
        case EXGMultiMessageType::ReqInitDSRole:
            HandleReqInitDSRole(MultiMessage, ConnectionID);
            break;
        case EXGMultiMessageType::ReqInitPlayerRole:
            HandleReqInitPlayerRole(MultiMessage, ConnectionID);
            break;
        case EXGMultiMessageType::ReqPlayerReqAllDSInfos:
            HandleReqPlayerReqAllDSInfos(MultiMessage, ConnectionID);
            break;
        case EXGMultiMessageType::ReqPlayerCreateNewLevel:
            HandleReqPlayerCreateNewLevel(MultiMessage, ConnectionID);
            break;
        default:
            break;
    }
}
```

## 消息处理逻辑

### ReqInitDSRole（DS 注册）

```cpp
void AXGMultiManageGameMode::HandleReqInitDSRole(
    const FXGMultiMessage& MultiMessage, const FGuid& ConnectionID)
{
    // 反序列化二级结构体
    FXGReqInitDSRoleMessage DSRoleMessage;
    FJsonObjectConverter::JsonObjectStringToUStruct(
        MultiMessage.Data, &DSRoleMessage);

    // 构建 DS 信息
    FXGDSInfo NewDSInfo;
    NewDSInfo.ServerConnectionID = DSRoleMessage.ServerID;
    NewDSInfo.ServerID = DSRoleMessage.ServerID;
    NewDSInfo.LevelName = DSRoleMessage.LevelName;
    NewDSInfo.ServerPort = DSRoleMessage.ServerPort;
    NewDSInfo.ServerIP = DSRoleMessage.ServerIP;

    // 添加到 DS 列表（AddUnique 防重复）
    DSList.AddUnique(NewDSInfo);

    // 发送注册成功回复
    FXGMultiMessage ResponseMessage;
    ResponseMessage.MessageType = EXGMultiMessageType::RespInitDSRole;
    FString ResponseJson;
    FJsonObjectConverter::UStructToJsonObjectString(ResponseMessage, ResponseJson);
    ServerSubsystem->SendMessageToPointedClient(ResponseJson, ConnectionID);
}
```

| 步骤 | 说明 |
|------|------|
| 1. 提取 `MultiMessage.Data` 中的 JSON 字符串 | 反序列化为 `FXGReqInitDSRoleMessage` |
| 2. 构建 `FXGDSInfo` | 从 DSInitInfo 拷贝字段，用 `ConnectionID` 标记连接 |
| 3. `DSList.AddUnique()` | 防重复注册（依赖 `operator==` 按 `ServerConnectionID` 比较） |
| 4. 发送回复 | 构建 `RespInitDSRole` 消息，通过 `SendMessageToPointedClient` 发送 |

### ReqInitPlayerRole（玩家注册）

```cpp
void AXGMultiManageGameMode::HandleReqInitPlayerRole(
    const FXGMultiMessage& MultiMessage, const FGuid& ConnectionID)
{
    // 反序列化玩家信息
    FXGReqInitPlayerRoleMessage PlayerRoleMessage;
    FJsonObjectConverter::JsonObjectStringToUStruct(
        MultiMessage.Data, &PlayerRoleMessage);

    // 添加到玩家列表
    FXGPlayerInfo NewPlayerInfo;
    NewPlayerInfo.ServerConnectionID = ConnectionID;
    NewPlayerInfo.PlayerName = PlayerRoleMessage.PlayerName;
    PlayerList.AddUnique(NewPlayerInfo);

    // 发送回复
    FXGMultiMessage ResponseMessage;
    ResponseMessage.MessageType = EXGMultiMessageType::RespInitPlayerRole;
    FString ResponseJson;
    FJsonObjectConverter::UStructToJsonObjectString(ResponseMessage, ResponseJson);
    ServerSubsystem->SendMessageToPointedClient(ResponseJson, ConnectionID);
}
```

### ReqPlayerReqAllDSInfos（请求 DS 列表）

```cpp
void AXGMultiManageGameMode::HandleReqPlayerReqAllDSInfos(
    const FXGMultiMessage& MultiMessage, const FGuid& ConnectionID)
{
    // 构建 DS 列表响应
    FXGRespPlayerAllDSInfosInfo AllDSInfos;
    AllDSInfos.DSList = DSList;

    // 序列化为 JSON
    FString AllDSInfosJson;
    FJsonObjectConverter::UStructToJsonObjectString(AllDSInfos, AllDSInfosJson);

    // 构建一级消息
    FXGMultiMessage ResponseMessage;
    ResponseMessage.Code = 0;
    ResponseMessage.MessageType = EXGMultiMessageType::RespPlayerReqAllDSInfos;
    ResponseMessage.Data = AllDSInfosJson;

    FString ResponseJson;
    FJsonObjectConverter::UStructToJsonObjectString(ResponseMessage, ResponseJson);
    ServerSubsystem->SendMessageToPointedClient(ResponseJson, ConnectionID);
}
```

### ReqPlayerCreateNewLevel（请求创建新 DS）

```cpp
void AXGMultiManageGameMode::HandleReqPlayerCreateNewLevel(
    const FXGMultiMessage& MultiMessage, const FGuid& ConnectionID)
{
    // 分配端口（硬编码 7777 → 手动递增）
    int32 NewDSPort = NextAvailablePort++;

    // 拉起新 DS 进程
    CreateNewDSProcess(NewDSPort, TEXT("ThirdPersonMap"));

    // 发送创建成功回复
    FXGMultiMessage ResponseMessage;
    ResponseMessage.MessageType = EXGMultiMessageType::RespPlayerCreateNewLevel;
    FString ResponseJson;
    FJsonObjectConverter::UStructToJsonObjectString(ResponseMessage, ResponseJson);
    ServerSubsystem->SendMessageToPointedClient(ResponseJson, ConnectionID);
}
```

## DS 动态创建

```cpp
void AXGMultiManageGameMode::CreateNewDSProcess(
    int32 InPort, const FString& InLevelName)
{
    // 构建可执行文件路径
    FString ExePath = FPaths::ProjectDir() + TEXT(
        "Server/XGMultiGame.exe");

    // 构建命令行参数
    FString Params = FString::Printf(TEXT(
        " -log -port=%d"), InPort);

    // 拉起进程
    FPlatformProcess::CreateProc(
        *ExePath,
        *Params,
        true,   // bLaunchDetached
        false,  // bLaunchHidden
        false,  // bLaunchReallyHidden
        nullptr,// ProcessID
        0,      // PriorityModifier
        nullptr,// WorkingDirectory
        nullptr // PipeWrite
    );
}
```

| 参数 | 值 | 说明 |
|------|-----|------|
| `ExePath` | `ProjectDir/Server/XGMultiGame.exe` | 打包生成的 DS 可执行文件 |
| `Params` | `-log -port=XXXX` | `-log` 显示控制台窗口，`-port=` 指定服务端端口 |
| `bLaunchDetached` | `true` | 独立进程（不随 DSM 关闭） |

`FPlatformProcess::CreateProc` 返回值是 `FProcHandle`，可用于后续进程管理（如监控、关闭）。

## 断开连接处理

当 DS 或 Player 的 WebSocket 连接断开时，DSM 需要清理对应记录：

```cpp
void AXGMultiManageGameMode::OnDisconnected(const FGuid& ConnectionID)
{
    // 从 DS 列表中移除
    FXGDSInfo RemoveDSInfo;
    RemoveDSInfo.ServerConnectionID = ConnectionID;
    DSList.Remove(RemoveDSInfo);  // 依赖 operator== 按 ServerConnectionID 比较

    // 从玩家列表中移除
    FXGPlayerInfo RemovePlayerInfo;
    RemovePlayerInfo.ServerConnectionID = ConnectionID;
    PlayerList.Remove(RemovePlayerInfo);
}
```

## 模块配置

[Build.cs](../../code/011_XGMultiManage/Source/XGMultiManage/XGMultiManage.Build.cs)：

```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core",
    "CoreUObject",
    "Engine",
    "InputCore",
    "XGSampleWSM",
    "Json",
    "JsonUtilities"
});
```

关键依赖说明：

| 模块 | 用途 |
|------|------|
| `XGSampleWSM` | WebSocket 通信插件（第三十一章） |
| `Json` + `JsonUtilities` | `FJsonObjectConverter` 序列化/反序列化 |

## Target 配置

[管理端 Target.cs](../../code/011_XGMultiManage/Source/XGMultiManage.Target.cs) 使用默认设置（Editor 包），不在打包环节单独处理。DSM 可直接在编辑器中运行测试，无需打包。

## DSM 端口分配

| 端口 | 用途 |
|------|------|
| 9033 | WebSocket Server 监听端口（DSM 固定） |
| 7777/8888/8889... | DS 游戏服务器端口（手动指定，CreateNewDS 时分配） |

## 测试提示

| 场景 | 操作 |
|------|------|
| 启动 DSM | 在编辑器中打开 `XGMultiManage.uproject`，PIE 运行 |
| 连接 DS | 手动启动打包好的 `XGMultiGameServer.exe -log -port=8888` |
| 验证注册 | 观察 DSM 输出日志，确认收到 `ReqInitDSRole` 消息 |
| 验证断开 | 关闭 DS 进程，检查 DSM OnDisconnected 能否正常移除 |
