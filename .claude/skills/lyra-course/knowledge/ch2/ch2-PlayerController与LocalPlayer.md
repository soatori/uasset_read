# PlayerController 与 LocalPlayer

## ALyraPlayerController

[ALyraPlayerController](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraPlayerController.h) 继承自 `ACommonPlayerController`，同时实现 `ILyraCameraAssistInterface` 和 `ILyraTeamAgentInterface`。

### 构造函数

```cpp
ALyraPlayerController::ALyraPlayerController(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    // 指定相机管理器类
    PlayerCameraManagerClass = ALyraPlayerCameraManager::StaticClass();

#if USING_CHEAT_MANAGER
    // 指定作弊器类
    CheatClass = ULyraCheatManager::StaticClass();
#endif
}
```

### 核心职责

1. **输入转发** — 接收玩家输入并转发给 `ULyraHeroComponent`
2. **相机管理** — 与 `ALyraPlayerCameraManager` 协同管理相机模式
3. **GAS 时序保障** — 确保 ASC 在正确的时机初始化
4. **队伍绑定** — 实现 `ILyraTeamAgentInterface`
5. **旁观者同步** — 管理 `TargetViewRotation` 的网络复制
6. **HttpServer 注册** — 开启 RPC 监听（测试用途）
7. **回放录制** — 控制回放的开始/停止
8. **力反馈** — 处理手柄力反馈设置

### 注册 HttpServer

在 `BeginPlay()` 中注册 Http 路由，用于自动化测试：

```cpp
void ALyraPlayerController::BeginPlay()
{
    Super::BeginPlay();

#if WITH_RPC_REGISTRY
    FHttpServerModule::Get().StartAllListeners();

    int32 RpcPort = 0;
    if (FParse::Value(FCommandLine::Get(), TEXT("rpcport="), RpcPort))
    {
        ULyraGameplayRpcRegistrationComponent* ObjectInstance = 
            ULyraGameplayRpcRegistrationComponent::GetInstance();
        if (ObjectInstance && ObjectInstance->IsValidLowLevel())
        {
            ObjectInstance->RegisterAlwaysOnHttpCallbacks();
            ObjectInstance->RegisterInMatchHttpCallbacks();
        }
    }
#endif
    SetActorHiddenInGame(false);
}
```

注册的路由：

| 路由 | 方法 | 用途 |
|------|------|------|
| `/core/cheatcommand` | POST | 远程执行作弊命令 |
| `/player/status` | GET | 获取玩家状态 |
| `/player/status` | POST | 远程开火 |

### 旁观者视角同步

使用 `TargetViewRotation` 复制属性同步非控制的视角旋转：

```cpp
UPROPERTY(replicated)
FRotator TargetViewRotation;

// 仅同步给拥有者
DOREPLIFETIME_WITH_PARAMS_FAST(APlayerController, TargetViewRotation, Params);
```

### 确保 ASC 的时序

`ALyraPlayerController` 中处理 GAS 的初始化时序问题：

1. **PC 创建时** — 绑定 `OnPossess` / `OnUnPossess` 事件
2. **Possess Pawn** — 检查 Pawn 上的 ASC 是否就绪
3. **专属服务器时序** — 服务器端需要确保 ASC 在 Pawn 创建后立即初始化
4. **输入处理** — `ULyraAbilitySystemComponent` 中的输入处理

### 设置队伍绑定

通过 `ILyraTeamAgentInterface` 实现：

```cpp
void ALyraPlayerController::SetGenericTeamId(const FGenericTeamId& NewTeamID)
{
    // 更新队伍信息
    // 通知团队子系统
    // 设置力反馈
}
```

### 力反馈设置

通过命令行变量 `CVarForceFeedbackScale` 控制力反馈强度：

```cpp
static float CVarForceFeedbackScale = 1.0f;
FAutoConsoleVariableRef CVarForceFeedback(
    TEXT("PlayerController.ForceFeedbackScale"),
    CVarForceFeedbackScale,
    TEXT("力反馈缩放系数"));
```

重写 `APlayerController::PlayDynamicForceFeedback` 方法以支持自定义力反馈逻辑。

### 相机穿透

处理相机被物体遮挡时的穿透逻辑：

1. `ALyraPlayerCameraManager` 检测遮挡
2. 调用 `ILyraCameraAssistInterface` 接口方法
3. 根据遮挡物类型决定处理方式

### 回放

```cpp
void ALyraPlayerController::OnPossess(APawn* InPawn)
{
    Super::OnPossess(InPawn);

    // 检查是否应该录制回放
    if (ShouldRecordReplay())
    {
        StartRecordingReplay();
    }
}
```

## ULyraLocalPlayer

[ULyraLocalPlayer](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraLocalPlayer.h) 继承自 `UCommonLocalPlayer`。

### 职责

1. **持有玩家设置** — 管理 `ULyraSettingsShared`（跨平台同步的设置）
2. **本地玩家身份** — 标识当前机器上的本地玩家
3. **平台绑定** — 处理平台层面的玩家操作

### UCommonLocalPlayer 与 ULocalPlayer

| 特性 | ULocalPlayer | UCommonLocalPlayer |
|------|-------------|-------------------|
| 平台玩家 | 基础平台抽象 | 添加 CommonUI 集成 |
| 输入处理 | 基础输入 | 增强的 CommonInput 支持 |
| 设置 | 基础设置 | 跨平台设置同步 |

## ALyraReplayPlayerController

回放专用的 PlayerController，继承自 `ALyraPlayerController`，用于回放场景：
- 更新的 ViewTarget 逻辑
- 回放状态下禁用输入
- 监听回放状态变化
