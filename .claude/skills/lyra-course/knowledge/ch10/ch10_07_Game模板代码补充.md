# Game 模块代码补充

## 概述

本章涵盖了 LyraGame 模块中未在独立章节展开的多个零散但重要的模板代码，包括 PlayerController 的生命周期修复、VerbMessage 在 ALyraPlayerState 中的复制集成、网络模式工具枚举、通用 ProgressBar Widget、以及模拟输入 Widget 系统。

## ALyraPlayerController::CleanupPlayerState

[LyraPlayerController.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraPlayerController.cpp)

为了解决**晚复制（Late Replication）**场景下的 PlayerState 资源泄漏问题，在 PlayerController 销毁时清理与其关联的 PlayerState：

```cpp
void ALyraPlayerController::CleanupPlayerState()
{
    // 当 PlayerController 销毁时，确保 PlayerState 也被正确清理
    if (PlayerState)
    {
        PlayerState->Destroy();
        PlayerState = nullptr;
    }
}
```

典型场景：客户端连接到服务器时，PlayerState 可能因网络延迟晚于 PlayerController 到达，导致状态不同步或泄漏。

## FLyraVerbMessageReplication 集成到 ALyraPlayerState

[LyraVerbMessageReplication.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraVerbMessageReplication.h) / [LyraVerbMessageReplication.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Messages/LyraVerbMessageReplication.cpp)

基于 `FFastArraySerializer` 的消息复制容器，通常作为 `ALyraPlayerState` 或 `ALyraGameState` 的成员，用于将 VerbMessage 从服务器可靠地同步到客户端。

通过在 PlayerState 中嵌入 `FLyraVerbMessageReplication`，服务器端调用 `AddMessage()` 即可自动通过 FastArray 的 `NetDeltaSerialize` 同步到所有客户端。

复制流程：
1. 服务器调用 `AddMessage()` 将消息加入 `CurrentMessages` 数组
2. FastArray 通过 `NetDeltaSerialize` 增量同步到客户端
3. 客户端在 `PostReplicatedAdd` / `PostReplicatedChange` 中通过 `UGameplayMessageSubsystem` 本地重新广播
4. 所有本地监听者收到消息

## EBlueprintExposedNetMode 与 SwitchOnNetMode

[LyraPlayerController.cpp](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraPlayerController.cpp)

UE5 新增的蓝图可访问网络模式枚举，配合 `SwitchOnNetMode` 蓝图节点，允许在蓝图中根据当前网络模式（Client/Server/Standalone/DedicatedServer）执行不同的逻辑分支。

```cpp
UENUM(BlueprintType)
enum EBlueprintExposedNetMode : int
{
    NetMode_Client,
    NetMode_Standalone,
    NetMode_ListenServer,
    NetMode_DedicatedServer,
};
```

## UMaterialProgressBar

通用材质驱动的进度条 Widget，通过更新材质参数（标量/向量）来实现进度显示。

### 核心机制

- 使用 MID（Material Instance Dynamic）作为进度可视化基础
- 支持两种动画模式：`AnimateProgressFromStart`（从起始位置开始动画）和 `AnimateProgressFromCurrent`（从当前位置继续动画）
- 通过材质参数驱动：ScalarParameterValues（标量参数）和 VectorParameterValues（向量参数）

### 使用场景

在 UI 中显示血量、进度等需要平滑过渡的数值，通过材质参数而非 Slate 绘制实现性能优化和视觉效果统一。

## ULyraSimulatedInputWidget 模拟输入 Widget

[LyraSimulatedInputWidget.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/UI/)

用于触屏/移动端的手动输入模拟 Widget 系统。

### 核心类

- **ULyraSimulatedInputWidget**：基础模拟输入 Widget，提供 `InputKeyValue`（单键值）和 `InputKeyValue2D`（二维轴值）两个输入类型。`QueryKeyToSimulate` 方法查询当前应模拟的按键。
- **ULyraJoystickWidget**：触屏摇杆 Widget，通过 `HandleTouchDelta` 处理触摸滑动事件，`StickRange` 定义摇杆的最大偏移范围。
- **ULyraTouchRegion**：触摸区域 Widget，`bShouldSimulateInput` 控制是否启用输入模拟。

### 应用场景

在移动端或触屏设备上，通过这些 Widget 将触摸输入映射为游戏内的按键/轴输入，实现非物理控制器下的操作模拟。
