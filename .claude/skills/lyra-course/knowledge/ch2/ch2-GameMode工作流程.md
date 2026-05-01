# GameMode 工作流程

## ALyraGameMode

[ALyraGameMode](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraGameMode.h) 继承自 `AModularGameModeBase`，是 Lyra 游戏模式基类。

## 初始化流程

### InitGame

UE 引擎启动 GameMode 的入口。Lyra 在此处绑定 Experience 加载：

```cpp
void ALyraGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);

    // 等待下一帧，给初始化启动设置留出时间
    GetWorld()->GetTimerManager().SetTimerForNextTick(
        this, &ThisClass::HandleMatchAssignmentIfNotExpectingOne);
}
```

调用堆栈：
```
ALyraGameMode::InitGame
UWorld::InitializeActorsForPlay
UGameInstance::StartPlayInEditorGameInstance
UEditorEngine::CreateInnerProcessPIEGameInstance
UEditorEngine::CreateNewPlayInEditorInstance
UEditorEngine::StartPlayInEditorSession
UEditorEngine::Tick
UUnrealEdEngine::Tick
ULyraEditorEngine::Tick
FEngineLoop::Tick
```

### InitGameState

在 `RouteActorInitialize` 阶段调用。`ALyraGameMode` 在 `InitGameState` 中执行 Experience 相关的状态初始化。

### HandleMatchAssignmentIfNotExpectingOne

此函数在 InitGame 的下一帧执行，核心逻辑：

```cpp
void ALyraGameMode::HandleMatchAssignmentIfNotExpectingOne()
{
    // 如果已有 Experience 请求，跳过
    if (bPendingAssignment) return;

    // 从 OptionsString 或 WorldSettings 中获取默认 Experience
    FString ExperienceName;
    if (!FParse::Value(OptionsString, TEXT("Experience="), ExperienceName))
    {
        // 未指定时从 WorldSettings 获取默认
        if (ALyraWorldSettings* WS = Cast<ALyraWorldSettings>(GetWorld()->GetWorldSettings()))
        {
            ExperienceName = WS->DefaultExperience.GetAssetName();
        }
    }

    // 检查是否就绪（等待热修复、GSI 等子系统）
    if (!IsReadyToProcessMatchAssignment())
    {
        // 未就绪，下帧重试
        GetWorld()->GetTimerManager().SetTimerForNextTick(
            this, &ThisClass::HandleMatchAssignmentIfNotExpectingOne);
        return;
    }

    // 就绪后，开始加载 Experience
    bPendingAssignment = true;
    StartExperienceLoading(ExperienceName);
}
```

### IsReadyToProcessMatchAssignment

检查以下子系统是否就绪：
- 热修复管理器（`ULyraHotfixManager`）是否完成初始化
- GSI（GameStateInterface）是否可用
- 其他需要在加载 Experience 前完成的系统

### OnExperienceLoaded 回调

当 `ULyraExperienceManagerComponent` 完成 Experience 加载后，通知 GameMode：

```cpp
void ALyraGameMode::OnExperienceLoaded(const ULyraExperienceDefinition* Experience)
{
    // 注册 GameFeature 插件中的 Actor 类型
    // 初始化 Bot 创建组件
    // 标记 Experience 加载完成
}
```

从此刻开始，`PreLogin` 允许玩家进入。

## OptionsString

`OptionsString` 是 GameMode 传递启动参数的方式，存储在 `AGameModeBase::OptionsString` 中。用于：

- 传递 Experience 选择：`?Experience=ExperienceName`
- 传递地图加载参数
- 传递调试选项

## 玩家登录流程

### 创建控制器

```
PreLogin → Login → PostLogin
```

1. **PreLogin** — 验证玩家是否可以加入（Experience 加载完成为前提）
2. **Login** — 创建 PlayerController
3. **PostLogin** — 初始化玩家状态，触发玩家生成

### Pawn 创建流程

```
ALyraGameMode::HandleStartingNewPlayer
  → 调用 ULyraPlayerSpawningManagerComponent 获取生成点
  → 调用 SpawnDefaultPawnAtTransform
  → 创建角色（ALyraCharacter / ALyraPawn）
  → Possess Pawn
```

### 寻找出生点

玩家生成点使用 `APlayerStart` 的子类（Lyra 自定义的玩家生成点类型），由 `ULyraPlayerSpawningManagerComponent` 统一管理。

## DS 的初始化启动

专用服务器（Dedicated Server）的启动流程：

```
Server → InitGame → 加载 Experience → 等待玩家加入
       → 不需要加载 UI 资源
       → 不需要音频和渲染资源
```

## 修复 UI 的策略加载

Experience 加载期间需要正确处理 UI 的加载策略：

- 使用 `AsyncMixin` 在加载完成前显示加载界面
- 避免在 Experience 加载完成前渲染主菜单
- `CommonLoadingScreen` 插件提供统一的加载屏幕

## 创建游戏基础类

在 `LyraGameMode.cpp` 顶部通过模块加载回调重写游戏类：

```cpp
// 通过 StaticClass 或 FCoreDelegates 注册默认类
// 类似 UE 的 GameMode 默认值设置
// 包括默认的 GameState、PlayerController、PlayerState、HUD 等
```

### NearClipPlane

`GNearClippingPlane` 是引擎的全局裁剪平面变量，用于设置近裁剪面距离：

```cpp
// 设置近裁剪面（值越小，能看到的物体越近）
GNearClippingPlane = 15.0f;
```

在 `ALyraPlayerCameraManager` 中可能根据当前相机模式调整此值，避免场景物体穿模。

## 最终流程总结

```
1. UWorld::SetGameMode() → 创建 ALyraGameMode
2. UWorld::InitializeActorsForPlay() → 调用 InitGame()
3. InitGame() → SetTimerForNextTick → HandleMatchAssignmentIfNotExpectingOne
4. HandleMatchAssignment → 检查就绪性 → 开始加载 Experience
5. ExperienceManagerComponent → 异步加载插件和资产
6. OnExperienceLoaded → GameMode 收到通知
7. RouteActorInitialize → InitGameState / PreInitializeComponents
8. 玩家登录：PreLogin → Login → PostLogin
9. PostLogin → HandleStartingNewPlayer → 生成 Pawn → Possess
```
