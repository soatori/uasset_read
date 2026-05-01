# 日志系统

## 日志类别定义

日志类别通过两个宏配对使用：

**头文件（.h）中声明**：
```cpp
LYRAGAME_API DECLARE_LOG_CATEGORY_EXTERN(LogLyra, Log, All);
```

**源文件（.cpp）中定义**：
```cpp
DEFINE_LOG_CATEGORY(LogLyra);
```

## 各日志类别定义位置

| 日志分类 | 默认级别 | 所在文件 |
|----------|---------|---------|
| `LogLyra` | Log | [LyraLogChannels.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/LyraLogChannels.h) |
| `LogLyraExperience` | Log | [LyraLogChannels.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/LyraLogChannels.h) |
| `LogLyraAbilitySystem` | Log | [LyraLogChannels.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/LyraLogChannels.h) |
| `LogLyraTeams` | Log | [LyraLogChannels.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/LyraLogChannels.h) |
| `LogLyraEditor` | Log | LyraEditor.h |
| `LogLyraGamePhase` | Log | LyraGamePhaseLog.h |
| `LogLyraCheat` | Log | LyraCheatManager.h |
| `LogLyraGameSettingRegistry` | Log | LyraGameSettingRegistry.h |
| `LogLyraRepGraph` | Display | LyraReplicationGraph.h |

## 日志详细级别

| 级别 | 控制台输出 | 编辑器日志 | 文本颜色 | 说明 |
|------|-----------|-----------|---------|------|
| Fatal | 是 | 不适用 | 不适用 | 会话崩溃 |
| Error | 是 | 是 | 红色 | — |
| Warning | 是 | 是 | 黄色 | — |
| Display | 是 | 是 | 灰色 | — |
| Log | 否 | 是 | 灰色 | 默认级别 |
| Verbose | 否 | 否 | 不适用 | — |
| VeryVerbose | 否 | 否 | 不适用 | 日志掩码可设颜色 |

## 静态日志与普通日志

```cpp
// 仅可在定义的文件中访问（文件局部静态）
DEFINE_LOG_CATEGORY_STATIC(SourceFilterPresets, Display, Display);

// 可在其他文件中通过 extern 访问
DEFINE_LOG_CATEGORY(LogLyra);
```

## 获取上下文对象方法

[LyraLogChannels.h](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Source/LyraGame/LyraLogChannels.h) 中定义了辅助函数：

```cpp
FString GetClientServerContextString(UObject* ContextObject = nullptr);
```

该函数在 `ULyraExperienceManagerComponent` 中调用，用于打印 Experience 加载日志。传递的对象通常是 `GameState`，该对象具有网络同步属性。

### FWorldContext

`FWorldContext` 是引擎层面管理 `UWorld` 的上下文环境：

- 每个 `WorldContext` 可视为一条轨道（track）
- 游戏引擎：默认只有一个 `WorldContext`
- 编辑器引擎：可能有一个用于编辑器世界、一个用于 PIE 世界
- `GPlayInEditorContextString`：PIE 模式下的调试辅助变量，在场景世界切换/地图加载时更新
- `UGameplayMessageSubsystem::BroadcastMessageInternal` 中也访问此变量，用于获取消息发生的世界类型
