# 第二章 Experience 与 Gameplay 框架

## 概述

本章是 Lyra 架构的核心。Experience（体验）系统替代了传统 GameMode 硬编码玩法逻辑的方式，通过数据资产动态声明游戏模式需要加载的各类资产、GameplayAbility、GameFeature 插件和动作集。GameMode 在初始化时自动触发 Experience 的加载，串联起整个 Gameplay 框架中的关键对象：GameState、PlayerState、PlayerController、LocalPlayer 以及玩家生成管理。

## 讲义范围

| 讲义编号 | 标题 | 对应知识文件 |
|----------|------|-------------|
| 010 | 定义 Experience | [ch2-Experience定义与加载](ch2/ch2-Experience定义与加载.md) |
| 011 | 管理 Experience | [ch2-Experience定义与加载](ch2/ch2-Experience定义与加载.md) |
| 011_泽_01 | 异步资产加载和 Bundle | [ch2-AssetManager与异步加载](ch2/ch2-AssetManager与异步加载.md) |
| 012 | AssetManager 类 | [ch2-AssetManager与异步加载](ch2/ch2-AssetManager与异步加载.md) |
| 012_泽_01 | TSoftObjectPtr 与 FSoftObjectPath | [ch2-AssetManager与异步加载](ch2/ch2-AssetManager与异步加载.md) |
| 012_泽_02 | 性能优化的宏 | [ch2-AssetManager与异步加载](ch2/ch2-AssetManager与异步加载.md) |
| 013 | 游戏实例 | [ch2-GameInstance与登录流程](ch2/ch2-GameInstance与登录流程.md) |
| 013_泽_01 | DTLS 概念 | [ch2-GameInstance与登录流程](ch2/ch2-GameInstance与登录流程.md) |
| 013_泽_02 | 令牌验证流程 | [ch2-GameInstance与登录流程](ch2/ch2-GameInstance与登录流程.md) |
| 014 | 创建游戏基础类 | [ch2-GameMode工作流程](ch2/ch2-GameMode工作流程.md) |
| 014_泽_01 | NearClipPlane | [ch2-GameMode工作流程](ch2/ch2-GameMode工作流程.md) |
| 015 | 开发者设置 | [ch2-开发者设置与模拟平台](ch2/ch2-开发者设置与模拟平台.md) |
| 016 | 模拟平台设置 | [ch2-开发者设置与模拟平台](ch2/ch2-开发者设置与模拟平台.md) |
| 017 | 用户体验定义 | [ch2-开发者设置与模拟平台](ch2/ch2-开发者设置与模拟平台.md) |
| 018 | 玩家生成点 | [ch2-玩家生成系统](ch2/ch2-玩家生成系统.md) |
| 019 | 玩家生成管理组件 | [ch2-玩家生成系统](ch2/ch2-玩家生成系统.md) |
| 020 | GameMode 工作流程 | [ch2-GameMode工作流程](ch2/ch2-GameMode工作流程.md) |
| 020_泽_01 | OptionsString | [ch2-GameMode工作流程](ch2/ch2-GameMode工作流程.md) |
| 021 | GameState 工作流程 | [ch2-GameState与PlayerState](ch2/ch2-GameState与PlayerState.md) |
| 021_泽_01 | 常见 G 开头的全局变量 | [ch2-GameState与PlayerState](ch2/ch2-GameState与PlayerState.md) |
| 022 | 修复 UI 的策略加载 | [ch2-GameMode工作流程](ch2/ch2-GameMode工作流程.md) |
| 023 | 异步询问体验加载 | [ch2-Experience定义与加载](ch2/ch2-Experience定义与加载.md) |
| 024 | PlayerState 工作流程 | [ch2-GameState与PlayerState](ch2/ch2-GameState与PlayerState.md) |
| 025 | Tag 的 FastArray 容器 | [ch2-GameState与PlayerState](ch2/ch2-GameState与PlayerState.md) |
| 026 | PlayerController 工作流程 | [ch2-PlayerController与LocalPlayer](ch2/ch2-PlayerController与LocalPlayer.md) |
| 027 | LocalPlayer | [ch2-PlayerController与LocalPlayer](ch2/ch2-PlayerController与LocalPlayer.md) |

## 源码目录

- `LyraGame/GameModes/` — Experience 定义、GameMode、GameState、WorldSettings
- `LyraGame/Player/` — PlayerController、PlayerState、LocalPlayer、生成管理
- `LyraGame/System/` — GameInstance、AssetManager

## 核心架构

### Experience 驱动模式

Lyra 的 Experience 设计模式：
1. `ALyraWorldSettings` 指定默认的 `ULyraExperienceDefinition`
2. `ALyraGameMode::InitGame()` 触发 Experience 分配
3. `ULyraExperienceManagerComponent`（挂在 GameState 上）管理加载过程
4. Experience 加载完成时，通过 `OnExperienceLoaded` 事件通知 GameMode
5. GameMode 收到事件后允许玩家登录（`PreLogin` 之前持续阻塞）

### 游戏启动流程

```
UWorld::SetGameMode()
  → ALyraGameMode::InitGame()
    → HandleMatchAssignmentIfNotExpectingOne()  // 下一帧
      → 从 WorldSettings 读取默认 Experience
      → 调用 IsReadyToProcessMatchAssignment()
        → 等待热修复、GSI 等子系统就绪
      → 开始加载 Experience
        → ExperienceManagerComponent 执行加载
        → 激活 GameFeature 插件
        → 授予 GA/GE/Attribute 等
      → OnExperienceLoaded_Failed/K2
        → GameMode 收到通知，允许玩家登录
  → APlayerController::PreLogin/Login/PostLogin
  → 玩家生成
```

## 关键类列表

| 类名 | 继承自 | 所在文件 | 用途 |
|------|--------|---------|------|
| `ULyraExperienceDefinition` | `UPrimaryDataAsset` | [LyraExperienceDefinition.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraExperienceDefinition.h) | Experience 数据资产定义 |
| `ULyraExperienceManagerComponent` | `UGameStateComponent` | [LyraExperienceManagerComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraExperienceManagerComponent.h) | Experience 加载与状态管理 |
| `ULyraExperienceActionSet` | `UPrimaryDataAsset` | [LyraExperienceActionSet.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraExperienceActionSet.h) | Experience 动作集 |
| `ULyraGameInstance` | `UCommonGameInstance` | [LyraGameInstance.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/System/LyraGameInstance.h) | 游戏实例，管理会话和登录 |
| `ALyraGameMode` | `AModularGameModeBase` | [LyraGameMode.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraGameMode.h) | 游戏模式基类 |
| `ALyraGameState` | `AModularGameStateBase` | [LyraGameState.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraGameState.h) | 游戏状态，持有 ExperienceManager |
| `ALyraPlayerState` | `AModularPlayerState` | [LyraPlayerState.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraPlayerState.h) | 玩家状态，TagStack 持有者 |
| `ALyraPlayerController` | `ACommonPlayerController` | [LyraPlayerController.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraPlayerController.h) | 玩家控制器 |
| `ULyraLocalPlayer` | `UCommonLocalPlayer` | [LyraLocalPlayer.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraLocalPlayer.h) | 本地玩家 |
| `ULyraPlayerSpawningManagerComponent` | `UGameStateComponent` | [LyraPlayerSpawningManagerComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/Player/LyraPlayerSpawningManagerComponent.h) | 玩家生成管理 |
| `ALyraWorldSettings` | `AWorldSettings` | [LyraWorldSettings.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraWorldSettings.h) | 世界设置，指定默认 Experience |
| `ULyraUserFacingExperienceDefinition` | `UPrimaryDataAsset` | [LyraUserFacingExperienceDefinition.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraUserFacingExperienceDefinition.h) | 前端用户体验定义 |
| `ULyraBotCreationComponent` | `UGameStateComponent` | [LyraBotCreationComponent.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/GameModes/LyraBotCreationComponent.h) | Bot 创建组件 |

## 依赖关系

```
ALyraWorldSettings (默认 Experience)
       ↓
ALyraGameMode → ULyraGameInstance → ULyraAssetManager
       │                                  │
       │                                  └─ Asset 异步加载
       │
       └─→ ALyraGameState
              ├─ ULyraExperienceManagerComponent (加载 Experience)
              ├─ ULyraPlayerSpawningManagerComponent
              └─→ ALyraPlayerState (TagStack 持有者)
                        │
                        └─→ ALyraPlayerController
                               └─→ ULyraLocalPlayer
```
